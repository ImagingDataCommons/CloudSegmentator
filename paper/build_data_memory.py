# /// script
# requires-python = ">=3.11"
# dependencies = ["pandas>=2.2", "idc-index==0.13.2", "idc-index-data==25.0.2"]
# ///
"""Rebuild the data behind the memory comparison of case study 1 with case study 2,
and the check for memory carried over between series in case study 2.

    uv run paper/build_data_memory.py --cache <dir-for-raw-files>

Writes two tables to paper/data/:

- cs1_peak_memory: per-series peak RAM in use on case study 1's GPU VM, with the
  series' geometry. The v1.2.0 inference notebook's MemoryMonitor sampled psutil
  `total - available` once a second while each series was downloaded, converted and
  segmented, and saved the trace in each workflow's `inferenceUsageMetrics.lz4`, in MB
  of 10^6 bytes. Converted here to GiB, the unit of case study 2's MemSampler. All
  successful inference attempts of the twoVM runs (1k, 10k, 126k), located from
  task_attempts.csv.gz. Geometry is defined exactly as in build_series_geometry_cs2.py.
- cs2_series_order: for each case study 2 inference attempt with a memory-related
  failure, the order its series ran in and how many failed tasks or models preceded
  each one, from the attempt's executed inference notebook.

Needs `gcloud` with read access to both workspace buckets, and `lz4`.
"""

import argparse
import io
import json
import re
import subprocess
import urllib.parse
import urllib.request
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).parent / "data"
CS1_BUCKET = "gs://fc-5af492dc-6993-4c91-bbf6-3e2747868642"
CS2_BUCKET = "gs://fc-63cbe829-cad1-490e-a4ea-23e9c4059281"
CS1_TASK = "downloadDicomAndConvertAndInferenceTotalSegmentator"
MB_TO_GIB = 1e6 / 2**30
RESAMPLED_MM = 1.5   # as build_series_geometry_cs2.py
MEMORY_CAUSES = ["killed (signal 9)", "timed out (90 min cap)", "export worker killed (RAM)"]
# Lines of the executed inference notebooks. A series starts with
# "[T+4.0s] <uid>:" (TotalSegmentator) or "[T+6.1s] Series <uid>" (MOOSE).
SERIES_LINE = re.compile(r"\[T\+[\d.]+s\] (?:Series )?([\d.]{20,}):?$")
# A memory-related failure: a TotalSegmentator timeout, rc=-9 (killed) or rc=1 (the
# export worker was killed), or a MOOSE worker killed by signal 9.
FAILURE_LINE = re.compile(r"(ERROR .*(timed out|rc=-?[19]\b)|CRASH .*signal 9)")


def token() -> str:
    return subprocess.run(["gcloud", "auth", "print-access-token"], check=True,
                          capture_output=True, text=True).stdout.strip()


def fetch(pairs: list[tuple[str, Path]]) -> None:
    """Download gs:// objects to local paths through the JSON API, 48 at a time."""
    tok = token()

    def one(pair):
        url, dest = pair
        if dest.exists() and dest.stat().st_size:
            return
        bucket, obj = url[5:].split("/", 1)
        req = urllib.request.Request(
            f"https://storage.googleapis.com/{bucket}/{urllib.parse.quote(obj)}",
            headers={"Authorization": f"Bearer {tok}"})
        with urllib.request.urlopen(req, timeout=120) as r:
            dest.write_bytes(r.read())

    with ThreadPoolExecutor(48) as ex:
        list(ex.map(one, pairs))


def _numbers(s) -> np.ndarray:
    # The traces are str() of nested Python lists; literal_eval is much slower.
    if not isinstance(s, str):
        return np.array([])
    return np.array(re.findall(r"-?\d+(?:\.\d+)?(?:e-?\d+)?", s), dtype=float)


def _parse_usage(path: Path) -> list[dict]:
    submission, workflow = path.stem.split("_")
    raw = subprocess.run(["lz4", "-dc", str(path)], capture_output=True, check=True).stdout
    d = pd.read_csv(io.BytesIO(raw), usecols=["SeriesInstanceUID", "total_segmentator_time",
                                              "ram_usage_mb", "ram_total_mb"])
    rows = []
    for r in d.itertuples():
        ram, total = _numbers(r.ram_usage_mb), _numbers(r.ram_total_mb)
        rows.append(dict(
            submission=submission, workflow=workflow, SeriesInstanceUID=r.SeriesInstanceUID,
            peak_gib=ram.max() * MB_TO_GIB if ram.size else np.nan,
            start_gib=ram[0] * MB_TO_GIB if ram.size else np.nan,
            samples=ram.size, vm_ram_gib=total.max() * MB_TO_GIB if total.size else np.nan,
            totalsegmentator_s=r.total_segmentator_time))
    return rows


def geometry() -> pd.DataFrame:
    """Series geometry, defined exactly as in build_series_geometry_cs2.py."""
    from idc_index import IDCClient
    idc = IDCClient()
    for name in ("ct_index", "volume_geometry_index"):
        idc.fetch_index(name)
    geo = idc.sql_query("""
        SELECT i.SeriesInstanceUID, i.collection_id, i.instanceCount AS slices,
               c.Rows, c.Columns, c.PixelSpacing_row_mm, c.PixelSpacing_col_mm,
               g.slice_spacing_mm
        FROM index i JOIN ct_index c USING (SeriesInstanceUID)
        LEFT JOIN volume_geometry_index g USING (SeriesInstanceUID)
        WHERE i.collection_id = 'nlst'""")
    geo["fov_row_mm"] = geo.Rows * geo.PixelSpacing_row_mm
    geo["fov_col_mm"] = geo.Columns * geo.PixelSpacing_col_mm
    geo["length_mm"] = (geo.slices - 1) * geo.slice_spacing_mm
    geo["mvox_native"] = geo.Rows * geo.Columns * geo.slices / 1e6
    geo["mvox_1p5mm"] = geo.fov_row_mm * geo.fov_col_mm * geo.length_mm / RESAMPLED_MM**3 / 1e6
    return geo


def cs1_peak_memory(cache: Path) -> pd.DataFrame:
    t = pd.read_csv(DATA / "task_attempts.csv.gz")
    t = t[(t.task == CS1_TASK) & (t.outcome == "Success")]
    dest = cache / "cs1_usage"
    dest.mkdir(parents=True, exist_ok=True)
    pairs = [(f"{CS1_BUCKET}/submissions/{r.submission}/TotalSegmentator/{r.workflow}/call-{CS1_TASK}/"
              + ("" if r.attempt == 1 else f"attempt-{r.attempt}/") + "inferenceUsageMetrics.lz4",
              dest / f"{r.submission}_{r.workflow}.lz4") for r in t.itertuples()]
    fetch(pairs)
    with ProcessPoolExecutor() as ex:
        rows = [row for rows in ex.map(_parse_usage, [p for _, p in pairs], chunksize=50) for row in rows]
    cohort = t.drop_duplicates("submission").set_index("submission").cohort
    df = pd.DataFrame(rows)
    df["cohort"] = df.submission.map(cohort)
    return df.merge(geometry(), on="SeriesInstanceUID", how="left")


def cs2_series_order(cache: Path) -> pd.DataFrame:
    fl = pd.read_csv(DATA / "cs2_inference_failures.csv.gz")
    batches = fl[fl.cause.isin(MEMORY_CAUSES)][["submission", "model", "workflow"]].drop_duplicates()
    dest = cache / "cs2_notebooks"
    dest.mkdir(parents=True, exist_ok=True)
    rows = []
    for b in batches.itertuples():
        nb = dest / f"{b.workflow}.ipynb"
        if not nb.exists():
            # The last attempt's notebook: its metrics are the ones in cs2_peak_memory.
            ls = subprocess.run(["gcloud", "storage", "ls",
                                 f"{CS2_BUCKET}/submissions/{b.submission}/Segmentator/{b.workflow}/call-inference/**"],
                                capture_output=True, text=True).stdout.split()
            ls = [p for p in ls if p.endswith("/inferenceOutputNotebook.ipynb")]
            attempt = lambda p: int(m[1]) if (m := re.search(r"/attempt-(\d+)/", p)) else 1
            fetch([(max(ls, key=attempt), nb)])
        cells = json.loads(nb.read_text())["cells"]
        text = "\n".join("".join(o.get("text", "")) for c in cells for o in c.get("outputs", []))
        position, failures = -1, 0
        for line in text.splitlines():
            line = line.strip()
            if m := SERIES_LINE.match(line):
                position += 1
                rows.append(dict(submission=b.submission, model=b.model, workflow=b.workflow,
                                 SeriesInstanceUID=m[1], position=position,
                                 failures_before=failures, restored=False))
            elif position >= 0 and "restored from checkpoint:" in line:
                rows[-1]["restored"] = True
            elif FAILURE_LINE.match(line):
                failures += 1
    return pd.DataFrame(rows)


def write(df: pd.DataFrame, name: str) -> None:
    df.round(4).to_csv(DATA / f"{name}.csv.gz", index=False,
                       compression={"method": "gzip", "compresslevel": 9, "mtime": 0})
    print(f"{name}: {len(df):,} rows")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache", type=Path, required=True, help="directory for raw metrics and notebooks")
    args = ap.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    write(cs2_series_order(args.cache), "cs2_series_order")
    write(cs1_peak_memory(args.cache), "cs1_peak_memory")


if __name__ == "__main__":
    main()
