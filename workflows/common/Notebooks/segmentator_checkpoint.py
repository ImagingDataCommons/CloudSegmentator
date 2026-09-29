"""Checkpoint / resume helper for the harmonized Segmentator inference task.

The GPU task runs nb1 (convert) + nb2 (inference) on one preemptible VM. When the VM
is preempted, Cromwell re-runs the whole task on a fresh VM; without a checkpoint all
finished work of that attempt is lost (the Aug-2026 pilot measured ~40 % of GPU
VM-minutes wasted on a bad day). This module keeps two layers of state in GCS, both
namespaced by ``run_id`` (the Cromwell workflow id, passed in by the WDL, so retries
of the same workflow resume and different submissions never share state)::

    <checkpoint_gcs>/<run_id>/nifti/all.tar.lz4         nb1: every converted NIfTI (one bundle,
                                                        written once after the convert phase)
    <checkpoint_gcs>/<run_id>/seg/<uid>/<model>.tar.lz4  nb2: one model's Boundary-B output for one
                                                        series (<uid>/<model>/**), written after
                                                        each (series, model) finishes
    <checkpoint_gcs>/<run_id>/out/<uid>.tar.lz4          nb3: one series' DICOM-SEG + radiomics
                                                        output, written after each series

On a retry: nb1 restores the bundle and skips download + dcm2niix for restored series;
nb2 restores finished (series, model) outputs and skips their inference; nb3 restores
finished series outputs. When output conversion succeeds, nb3 deletes the run's prefix
(``cleanup()``). nb2 does not: its task can still be preempted after the notebook ends,
and a retry then restores from the prefix. So a run that fails, or is aborted, before
nb3 succeeds leaves its whole prefix behind (useful for recovery, see development.md);
expire old prefixes with a bucket lifecycle rule (operations.md).

No-op when ``gcs_prefix`` is empty. Auth = the VM's service account (ADC); a Terra
workspace bucket is writable by the pet SA. Requires ``google-cloud-storage`` (in the
cloudsegmentator-base image).

Usage (papermill parameters ``checkpoint_gcs`` / ``run_id`` come from the WDL)::

    from segmentator_checkpoint import Checkpointer
    ckpt = Checkpointer(checkpoint_gcs, run_id)
    restored = ckpt.restore_nifti_bundle(NIFTI_DIR)        # nb1
    ckpt.save_nifti_bundle(NIFTI_DIR)                      # nb1, after converting
    done = ckpt.restore_segs(SEG_DIR)                      # nb2: {(uid, model), ...}
    ckpt.save_seg(SEG_DIR, uid, model)                     # nb2, after each (uid, model)
    done = ckpt.restore_series_outputs({"dicom_seg": D, "radiomics": R})   # nb3
    ckpt.save_series_output(uid, {"dicom_seg": D, "radiomics": R})        # nb3, per series
    ckpt.cleanup()                                         # nb3, on success
"""
import json
import shlex
import subprocess
import tempfile
import time
from pathlib import Path

TMP = Path(tempfile.gettempdir())


class Checkpointer:
    def __init__(self, gcs_prefix, run_id, verbose=True):
        self.enabled = bool(gcs_prefix)
        self.verbose = verbose
        self.stats = {"restored_nifti": 0, "restored_seg": 0, "saved_seg": 0,
                      "saved_nifti_bundle": False, "errors": 0}
        if not self.enabled:
            self._log("Checkpointing OFF (checkpoint_gcs not set)")
            return
        if not str(gcs_prefix).startswith("gs://"):
            raise ValueError(f"checkpoint_gcs must start with gs:// -- got {gcs_prefix!r}")
        if not run_id:
            raise ValueError("checkpoint_gcs is set but run_id is empty")
        try:
            from google.cloud import storage
        except ImportError as exc:
            raise RuntimeError("checkpoint_gcs is set but google-cloud-storage is not installed "
                               "in this image") from exc
        bucket_name, _, prefix = str(gcs_prefix)[len("gs://"):].partition("/")
        self._bucket = storage.Client().bucket(bucket_name)
        self._root = "/".join(p for p in (prefix.strip("/"), str(run_id).strip("/")) if p)
        self.uri = f"gs://{bucket_name}/{self._root}"
        self._log(f"Checkpointing ON -> {self.uri}")

    # ------------------------------------------------------------------ utils
    def _log(self, msg):
        if self.verbose:
            print(f"  [checkpoint] {msg}", flush=True)

    def _blob(self, rel):
        return self._bucket.blob(f"{self._root}/{rel}")

    def _list(self, sub):
        base = f"{self._root}/{sub}/"
        return [b.name[len(base):] for b in self._bucket.list_blobs(prefix=base)
                if b.name != base]

    @staticmethod
    def _tar(src_root, members, out_file):
        joined = " ".join(shlex.quote(str(m)) for m in members)
        subprocess.run(f"tar -cf - -C {shlex.quote(str(src_root))} {joined} | lz4 > "
                       f"{shlex.quote(str(out_file))}", shell=True, check=True)

    @staticmethod
    def _untar(archive, dest_root):
        Path(dest_root).mkdir(parents=True, exist_ok=True)
        subprocess.run(f"lz4 -d -c {shlex.quote(str(archive))} | tar -xf - -C "
                       f"{shlex.quote(str(dest_root))}", shell=True, check=True)

    def _safe(self, what, fn):
        """Checkpointing must never fail the run: log and carry on."""
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            self.stats["errors"] += 1
            self._log(f"WARNING: {what} failed: {exc}")
            return None

    # ------------------------------------------------------- nb1: NIfTI bundle
    def restore_nifti_bundle(self, nifti_dir):
        """Extract <run>/nifti/all.tar.lz4 into nifti_dir; return the set of series uids
        restored (directories present afterwards)."""
        if not self.enabled:
            return set()

        def _do():
            blob = self._blob("nifti/all.tar.lz4")
            if not blob.exists():
                return set()
            local = TMP / "_ckpt_nifti_all.tar.lz4"
            t0 = time.time()
            blob.download_to_filename(str(local))
            self._untar(local, nifti_dir)
            local.unlink(missing_ok=True)
            uids = {d.name for d in Path(nifti_dir).iterdir() if d.is_dir()}
            self.stats["restored_nifti"] = len(uids)
            self._log(f"restored NIfTI bundle: {len(uids)} series in {time.time() - t0:.1f}s")
            return uids
        return self._safe("NIfTI bundle restore", _do) or set()

    def save_nifti_bundle(self, nifti_dir, extra_files=()):
        """Upload every <uid>/ directory under nifti_dir (+ extra_files, e.g. the manifest)
        as one bundle. Called once after the convert phase."""
        if not self.enabled:
            return

        def _do():
            nifti_dir_p = Path(nifti_dir)
            members = sorted(d.name for d in nifti_dir_p.iterdir() if d.is_dir())
            members += [Path(f).name for f in extra_files if (nifti_dir_p / Path(f).name).exists()]
            if not members:
                return
            local = TMP / "_ckpt_nifti_all.tar.lz4"
            t0 = time.time()
            self._tar(nifti_dir_p, members, local)
            self._blob("nifti/all.tar.lz4").upload_from_filename(str(local))
            mb = local.stat().st_size / 1e6
            local.unlink(missing_ok=True)
            self.stats["saved_nifti_bundle"] = True
            self._log(f"saved NIfTI bundle ({len(members)} entries, {mb:.1f} MB) in {time.time() - t0:.1f}s")
        self._safe("NIfTI bundle save", _do)

    # ----------------------------------------------- nb2: per (series, model)
    def restore_segs(self, seg_dir):
        """Download + extract every seg/<uid>/<model>.tar.lz4 into seg_dir.
        Returns {(uid, model)} restored."""
        if not self.enabled:
            return set()

        def _do():
            done = set()
            names = [n for n in self._list("seg") if n.endswith(".tar.lz4") and "/" in n]
            t0 = time.time()
            for n in names:
                uid, model = n.split("/", 1)[0], n.split("/", 1)[1][:-len(".tar.lz4")]
                local = TMP / f"_ckpt_seg_{uid}_{model}.tar.lz4"
                self._blob(f"seg/{n}").download_to_filename(str(local))
                self._untar(local, seg_dir)
                local.unlink(missing_ok=True)
                done.add((uid, model))
            if done:
                self.stats["restored_seg"] = len(done)
                self._log(f"restored {len(done)} (series, model) segmentation(s) in {time.time() - t0:.1f}s")
            return done
        return self._safe("segmentation restore", _do) or set()

    def save_seg(self, seg_dir, uid, model):
        """Upload seg_dir/<uid>/<model>/** as seg/<uid>/<model>.tar.lz4."""
        if not self.enabled:
            return

        def _do():
            rel = Path(uid) / model
            if not (Path(seg_dir) / rel).is_dir():
                return
            local = TMP / f"_ckpt_seg_{uid}_{model}.tar.lz4"
            self._tar(seg_dir, [rel], local)
            self._blob(f"seg/{uid}/{model}.tar.lz4").upload_from_filename(str(local))
            local.unlink(missing_ok=True)
            self.stats["saved_seg"] += 1
        self._safe(f"segmentation save {uid}/{model}", _do)

    # ------------------------------------------- nb3: per-series output bundles
    # out/<uid>.tar.lz4 holds <name>/<uid>/** for each (name -> root dir) given, e.g.
    # {"dicom_seg": DICOM_SEG_DIR, "radiomics": RADIOMICS_DIR}; restored into the same roots.
    def save_series_output(self, uid, roots):
        if not self.enabled:
            return

        def _do():
            import shutil
            stage = TMP / f"_ckpt_out_{uid}"
            if stage.exists():
                shutil.rmtree(stage)
            members = []
            for name, root in roots.items():
                src = Path(root) / uid
                if src.is_dir():
                    shutil.copytree(src, stage / name / uid)
                    members.append(name)
            if not members:
                return
            local = TMP / f"_ckpt_out_{uid}.tar.lz4"
            self._tar(stage, members, local)
            self._blob(f"out/{uid}.tar.lz4").upload_from_filename(str(local))
            local.unlink(missing_ok=True)
            shutil.rmtree(stage, ignore_errors=True)
            self.stats["saved_out"] = self.stats.get("saved_out", 0) + 1
        self._safe(f"series output save {uid}", _do)

    def restore_series_outputs(self, roots):
        """Restore every out/<uid>.tar.lz4 into the given roots; return {uid} restored."""
        if not self.enabled:
            return set()

        def _do():
            import shutil
            done = set()
            t0 = time.time()
            for n in self._list("out"):
                if not n.endswith(".tar.lz4"):
                    continue
                uid = n[:-len(".tar.lz4")]
                local = TMP / f"_ckpt_out_{uid}.tar.lz4"
                stage = TMP / f"_ckpt_out_{uid}"
                if stage.exists():
                    shutil.rmtree(stage)
                self._blob(f"out/{n}").download_to_filename(str(local))
                self._untar(local, stage)
                local.unlink(missing_ok=True)
                for name, root in roots.items():
                    src = stage / name / uid
                    if src.is_dir():
                        dst = Path(root) / uid
                        if dst.exists():
                            shutil.rmtree(dst)
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(src), str(dst))
                shutil.rmtree(stage, ignore_errors=True)
                done.add(uid)
            if done:
                self.stats["restored_out"] = len(done)
                self._log(f"restored {len(done)} series output bundle(s) in {time.time() - t0:.1f}s")
            return done
        return self._safe("series output restore", _do) or set()

    # --------------------------------------------------------- attempt ledger
    # A preempted VM cannot report its own death, so every attempt leaves a small
    # progress record under attempts/<kind>/<id>.json (updated at phase / work-unit
    # boundaries). The attempt that finally succeeds reads the others' records and
    # can summarize the run INCLUDING its preempted predecessors: how long each ran
    # (as of its last update), how many units it completed, its last phase and
    # peak RAM. Records die with the run prefix on cleanup().
    def attempt_start(self, kind):
        """Register this VM attempt; call once, right after constructing the ckpt."""
        if not self.enabled:
            return
        self._attempt = {"kind": kind, "id": str(int(time.time() * 1000)),
                         "start_epoch": round(time.time(), 1), "elapsed_s": 0.0,
                         "units_done": 0, "phase": "start", "peak_mem_gb": 0.0}
        self.attempt_update()

    def attempt_update(self, units_done=None, phase=None, peak_mem_gb=None):
        """Refresh this attempt's ledger record (cheap: one small GCS write)."""
        a = getattr(self, "_attempt", None)
        if not self.enabled or a is None:
            return
        if units_done is not None:
            a["units_done"] = units_done
        if phase is not None:
            a["phase"] = phase
        if peak_mem_gb:
            a["peak_mem_gb"] = max(a["peak_mem_gb"], round(float(peak_mem_gb), 2))
        a["elapsed_s"] = round(time.time() - a["start_epoch"], 1)

        def _do():
            self._blob(f"attempts/{a['kind']}/{a['id']}.json").upload_from_string(
                json.dumps(a), content_type="application/json")
        self._safe("attempt ledger update", _do)

    def prior_attempts(self, kind):
        """Records left by earlier attempts of this run (preempted / failed VMs),
        oldest first. Read this BEFORE cleanup()."""
        if not self.enabled:
            return []

        def _do():
            me = getattr(self, "_attempt", {}).get("id")
            recs = []
            for n in self._list(f"attempts/{kind}"):
                if not n.endswith(".json") or n[:-len(".json")] == me:
                    continue
                recs.append(json.loads(self._blob(f"attempts/{kind}/{n}").download_as_text()))
            return sorted(recs, key=lambda r: r.get("start_epoch", 0))
        return self._safe("attempt ledger read", _do) or []

    # ---------------------------------------------------------------- cleanup
    def cleanup(self):
        """Delete everything under <checkpoint_gcs>/<run_id>/ (call on success)."""
        if not self.enabled:
            return

        def _do():
            blobs = list(self._bucket.list_blobs(prefix=f"{self._root}/"))
            for b in blobs:
                b.delete()
            self._log(f"cleaned up {len(blobs)} checkpoint object(s) under {self.uri}")
        self._safe("cleanup", _do)


class MemSampler:
    """Background system-RAM peak sampler (/proc/meminfo; used = MemTotal-MemAvailable).

    Answers "how close did this VM sail to the memory ceiling" — the question the
    Sep-2026 lung_vessels livelock (14 GiB peak on a 16 GB swapless VM) needed a
    local repro to answer. `peak_gb` is the whole-run peak; `mark()` +
    `window_peak_gb()` bracket one work unit (a series / a task) for per-unit
    attribution. Linux-only: silently reports zeros where /proc/meminfo is absent.
    The sampler thread is a daemon — no explicit stop needed.
    """

    def __init__(self, interval_s=5.0):
        self.peak_gb = 0.0
        self._window_gb = 0.0
        self._ok = Path("/proc/meminfo").exists()
        if self._ok:
            import threading
            threading.Thread(target=self._loop, args=(float(interval_s),),
                             daemon=True).start()

    @staticmethod
    def _read_gb():
        total = avail = 0
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                total = int(line.split()[1])
            elif line.startswith("MemAvailable:"):
                avail = int(line.split()[1])
        return max(total - avail, 0) / (1024.0 * 1024.0)

    def _loop(self, interval_s):
        while True:
            try:
                g = self._read_gb()
                self.peak_gb = max(self.peak_gb, g)
                self._window_gb = max(self._window_gb, g)
            except Exception:
                pass
            time.sleep(interval_s)

    def mark(self):
        """Start a new attribution window (e.g. before one series / task)."""
        try:
            self._window_gb = self._read_gb() if self._ok else 0.0
        except Exception:
            self._window_gb = 0.0

    def window_peak_gb(self):
        return round(self._window_gb, 2)
