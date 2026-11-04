# /// script
# requires-python = ">=3.11"
# dependencies = ["pandas>=2.2"]
# ///
"""Rebuild the tidy data behind the case study 2 execution figures.

Two Terra submissions on the same 2,959 CPTAC/CMB CT series, launched together on
15 Oct 2026 in workspace terra-billing-datester/kyle-testing: TotalSegmentator
(total + lung_vessels) and MOOSE (ten clin_ct_* models), both twoVM.

    uv run paper/build_data_cs2.py --cache <dir-for-raw-files> [--reruns-only]

Sources, all still live (unlike case study 1's):
- Cromwell metadata from the Terra API, per workflow. Under the GCP Batch backend
  it records each Batch job state change, so phases come from `executionEvents`.
- `combined_UsageMetrics.csv` that each workflow writes to the workspace bucket:
  per-series (and per-model) step timings logged by the workflow's notebooks.
- The Terra billing export in BigQuery, by the `cromwell-workflow-id` label.
- Each inference call's `inference_errors.txt` and, where a failure was memory-related,
  its executed notebook, for the attempt-wide peak RAM.

Needs `gcloud` (logged in, with access to the workspace) and `bq` with read access
to the billing export. Writes paper/data/cs2_*.csv.gz.
"""

import argparse
import csv
import io
import json
import re
import subprocess
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

WORKSPACE = "terra-billing-datester/kyle-testing"
BUCKET = "gs://fc-63cbe829-cad1-490e-a4ea-23e9c4059281"
BILLING = "idc-terra-explore-admin.terra_cost_exports.gcp_billing_export_v1_01E8DE_3FD7A1_F95FEE"
BQ_PROJECT = "idc-external-025"
GCP_PROJECT = "terra-2e3cb896"
DATA = Path(__file__).parent / "data"
API = "https://api.firecloud.org/api/workspaces/" + WORKSPACE

RUNS = pd.DataFrame(
    [
        ("0702d858-ae72-49df-816c-a2e7d3ec3394", "TotalSegmentator"),
        ("f4b9a107-e336-4f81-b80d-ebe5cd066479", "MOOSE"),
    ],
    columns=["submission", "model"],
)

# Reruns, 21-22 Oct 2026, of the series that lost results to memory (and of batch 140,
# whose output conversion failed), each series in its own workflow, with RAM raised one
# step at a time. Pass 2 reran what pass 1 still lost. The MOOSE reruns of memory
# failures ran only the three models that had failed.
RERUNS = pd.DataFrame(
    [
        ("19e47648-1bed-4a59-830e-ef5f245eea82", "TotalSegmentator", 1, 32, 16),
        ("2a8daf77-79bf-4687-9b09-b73e649b95e3", "MOOSE", 1, 26, 16),
        ("db2df084-8ffb-4f58-b760-f725153b6e42", "MOOSE", 1, 16, 32),
        ("60825e39-c0fc-41d2-8924-2a7ad065c324", "MOOSE", 1, 16, 16),
        ("9cf194e4-9712-4e50-baa6-91006bffb939", "TotalSegmentator", 2, 48, 16),
        ("354b5ab6-0826-415b-af97-005eb523dc4f", "TotalSegmentator", 2, 48, 16),
        ("6d7ed2ac-0819-42e6-90cd-007d1707a2a2", "TotalSegmentator", 2, 32, 32),
        ("8080dba5-dc83-4c95-b590-43c3354a08b4", "MOOSE", 2, 26, 16),
        ("1e09a874-4cf5-4767-9d62-4d2de3a68893", "MOOSE", 2, 26, 16),
    ],
    columns=["submission", "model", "rerun_pass", "inference_ram_gib", "output_conversion_ram_gib"],
)
MOOSE_SUBMISSIONS = set(pd.concat([RUNS, RERUNS]).query("model == 'MOOSE'").submission)

# As build_data.COST_CATEGORY_SQL, except that disk is matched on 'PD Capacity':
# these VMs bill 'Balanced PD Capacity' as well as 'Storage PD Capacity'.
COST_CATEGORY_SQL = """
    CASE
      WHEN sku.description LIKE 'Licensing%' THEN 'Other'
      WHEN sku.description LIKE '%GPU%' THEN 'GPU'
      WHEN sku.description LIKE '%Core%' THEN 'CPU'
      WHEN sku.description LIKE '%Ram%' THEN 'RAM'
      WHEN sku.description LIKE '%External IP%' THEN 'External IP'
      WHEN sku.description LIKE '%PD Capacity%' THEN 'Disk'
      WHEN sku.description LIKE 'Network%' THEN 'Network egress'
      ELSE 'Other'
    END"""


def token() -> str:
    return subprocess.run(["gcloud", "auth", "print-access-token"], check=True,
                          capture_output=True, text=True).stdout.strip()


def get_json(url: str, tok: str) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)


def fetch_metadata(cache: Path, submissions) -> dict[str, list[dict]]:
    """Workflow metadata per submission, cached as <cache>/metadata/<sub>_<wf>.json.
    Only workflows that had not reached a terminal state are re-fetched."""
    tok, out = token(), {}
    (cache / "metadata").mkdir(parents=True, exist_ok=True)
    for sub in submissions:
        s = get_json(f"{API}/submissions/{sub}", tok)
        (cache / f"submission_{sub}.json").write_text(json.dumps(s))

        def one(w):
            p = cache / "metadata" / f"{sub}_{w['workflowId']}.json"
            if p.exists():
                m = json.loads(p.read_text())
                if m.get("status") in ("Succeeded", "Failed", "Aborted"):
                    return m
            m = get_json(f"{API}/submissions/{sub}/workflows/{w['workflowId']}"
                         "?excludeKey=submittedFiles&excludeKey=commandLine", tok)
            p.write_text(json.dumps(m))
            return m

        with ThreadPoolExecutor(16) as ex:
            out[sub] = list(ex.map(one, s["workflows"]))
    return out


def ts(x):
    return pd.Timestamp(x) if x else pd.NaT


def parse_attempt(c: dict) -> dict:
    """Phase boundaries of one call attempt from its Batch job state changes."""
    ev = sorted(c.get("executionEvents", []), key=lambda e: e["startTime"])
    running = [e for e in ev if e["description"].startswith("Job state is set from SCHEDULED to RUNNING")]
    vm_starts = [e for e in ev if e["description"] == "vmStartTime"]
    r = dict(start=ts(c.get("start")), end=ts(c.get("end")),
             vm_requests=len(vm_starts),
             quota_errors=sum("CODE_GCE_QUOTA_EXCEEDED" in e["description"] for e in ev),
             stockout_errors=sum("ZONE_RESOURCE_POOL_EXHAUSTED" in e["description"] for e in ev),
             vm_timeouts=sum(e["description"].startswith("VMs not functioning") for e in ev))
    if running:
        run = running[-1]
        r["running"], r["running_end"] = ts(run["startTime"]), ts(run["endTime"])
        # The VM start that led to RUNNING is the last one to begin before it.
        before = [e for e in vm_starts if ts(e["startTime"]) <= r["running"]]
        r["vm_start"] = ts(before[-1]["startTime"]) if before else pd.NaT
    return r


def attempts_table(meta: dict[str, list[dict]]) -> pd.DataFrame:
    rows = []
    for sub, wfs in meta.items():
        for m in wfs:
            for name, calls in m.get("calls", {}).items():
                for c in calls:
                    zones = c.get("runtimeAttributes", {}).get("zones", "")
                    rows.append(dict(submission=sub, workflow=m["id"], task=name.split(".")[-1],
                                     attempt=c.get("attempt"), status=c.get("executionStatus"),
                                     preemptible=c.get("preemptible"),
                                     vm_cost_per_hour=c.get("vmCostPerHour"),
                                     region=zones.split("-")[0] + "-" + zones.split("-")[1] if zones else None,
                                     **parse_attempt(c)))
    a = pd.DataFrame(rows)
    for col in ["start", "end", "running", "running_end", "vm_start"]:
        a[col] = pd.to_datetime(a[col], utc=True)
    m = lambda x, y: (a[y] - a[x]).dt.total_seconds() / 60  # noqa: E731
    a["wait_vm_min"] = m("start", "vm_start")        # quota, stockouts, failed VM starts
    a["vm_startup_min"] = m("vm_start", "running")   # the VM that ran, to Batch RUNNING
    a["running_min"] = m("running", "running_end")   # image pull, file transfer, analysis
    a["deallocation_min"] = m("running_end", "end")  # Batch done -> Cromwell records it
    a["attempt_min"] = m("start", "end")
    return a.sort_values(["submission", "workflow", "task", "attempt"]).reset_index(drop=True)


def fetch_usage_metrics(meta: dict[str, list[dict]], cache: Path) -> pd.DataFrame:
    """Per-series step timings from each workflow's combined_UsageMetrics.csv."""
    d = cache / "usage_metrics"
    d.mkdir(parents=True, exist_ok=True)
    jobs = []
    for sub, wfs in meta.items():
        for m in wfs:
            url = (m.get("outputs") or {}).get("Segmentator.combinedUsageMetricsCsv")
            if url is None:
                calls = m.get("calls", {}).get("Segmentator.outputConversion", [])
                url = next((c["outputs"].get("combinedUsageMetricsCsv") for c in calls[::-1]
                            if c.get("executionStatus") == "Done"), None)
            if url:
                jobs.append((sub, m["id"], url, d / f"{sub}_{m['id']}.csv"))

    def get(j):
        if not j[3].exists():
            subprocess.run(["gcloud", "storage", "cp", "-q", j[2], str(j[3])], check=True,
                           capture_output=True)

    with ThreadPoolExecutor(16) as ex:
        list(ex.map(get, jobs))

    frames = []
    for sub, wf, _, path in jobs:
        section, lines = None, {}
        for line in path.read_text().splitlines():
            if line.startswith("# source:"):
                section = line.split(":", 1)[1].strip().removesuffix("_UsageMetrics.csv")
                lines[section] = []
            elif line.strip():
                lines[section].append(line)
        for section, ls in lines.items():
            f = pd.read_csv(io.StringIO("\n".join(ls)))
            f.insert(0, "section", section)
            f.insert(0, "workflow", wf)
            f.insert(0, "submission", sub)
            frames.append(f)
    return pd.concat(frames, ignore_index=True)


def step_times(um: pd.DataFrame) -> pd.DataFrame:
    """Per-batch sums of the per-series step timings, in minutes. A series restored
    from the checkpoint logs zero for the steps its earlier, preempted attempt did, so
    a batch with any restored series in a section is left out of that section."""
    um = um.copy()
    um["restored"] = um.checkpoint_restored.astype(str).eq("True")
    out = []
    spec = {
        "convert": {"download_s": "dicom_download", "dcm2niix_s": "dicom_to_nifti"},
        "inference": {"model_inference_s": "inference"},
        "output_conversion": {"model_seg_s": "nifti_to_seg", "model_radiomics_s": "radiomics",
                              "model_sr_s": "features_to_sr"},
    }
    for section, cols in spec.items():
        s = um[um.section == section]
        clean = s.groupby(["submission", "workflow"]).restored.transform("any").eq(False)
        g = s[clean].groupby(["submission", "workflow"])
        t = g[list(cols)].sum().rename(columns=cols) / 60
        if section == "output_conversion":
            # The reference DICOM is downloaded once per series, repeated on each model row.
            ref = (s[clean].drop_duplicates(["workflow", "SeriesInstanceUID"])
                   .groupby(["submission", "workflow"]).ref_download_s.sum() / 60)
            t.insert(0, "reference_download", ref)
        t = t.add_suffix("_min")
        t[f"{section}_series"] = g.SeriesInstanceUID.nunique()
        out.append(t)
    return pd.concat(out, axis=1).reset_index()


def peak_memory(um: pd.DataFrame) -> pd.DataFrame:
    """Per-series peak RAM in use on the VM (GiB): MemTotal - MemAvailable from
    /proc/meminfo, sampled every 5 s by MemSampler (workflows/common/Notebooks/
    segmentator_checkpoint.py), bracketed per unit of work. TotalSegmentator brackets
    each task (total, lung_vessels); MOOSE runs all its models in one worker process,
    so its value is per series, repeated on every model row. Restored rows are blank."""
    size = (um[um.section == "convert"].drop_duplicates(["workflow", "SeriesInstanceUID"])
            [["workflow", "SeriesInstanceUID", "download_dcm_files", "download_mb"]])
    inf = um[(um.section == "inference") & um.model_peak_mem_gb.notna()]
    moose = inf.submission.isin(MOOSE_SUBMISSIONS)
    gpu = pd.concat([
        inf[~moose].assign(vm="GPU", unit=inf.model),
        inf[moose].drop_duplicates(["workflow", "SeriesInstanceUID"]).assign(vm="GPU", unit="all models"),
    ]).rename(columns={"model_peak_mem_gb": "peak_gb"})
    oc = um[(um.section == "output_conversion") & um.series_peak_mem_gb.notna()]
    cpu = (oc.drop_duplicates(["workflow", "SeriesInstanceUID"])
           .assign(vm="CPU", unit="output conversion").rename(columns={"series_peak_mem_gb": "peak_gb"}))
    cols = ["submission", "workflow", "SeriesInstanceUID", "vm", "unit", "peak_gb"]
    out = pd.concat([gpu[cols], cpu[cols]]).merge(size, on=["workflow", "SeriesInstanceUID"], how="left")
    return out.sort_values(cols[:5]).reset_index(drop=True)


# How each inference error message reads, most specific first. The two memory kills are
# the kernel OOM killer (SIGKILL) and nnU-Net's own report of its export worker dying.
CAUSES = [("killed by signal 9", "killed (signal 9)"),
          ("rc=-9", "killed (signal 9)"),
          ("killed by signal 11", "segfault (signal 11)"),
          ("insufficient available CPU RAM", "export worker killed (RAM)"),
          ("timed out after", "timed out (90 min cap)"),
          ("produced no output", "no output"),
          ("Invalid dtype", "RGB input"),
          ("Chunks and shape must be of the same length", "RGB input")]
MEMORY_CAUSES = {"killed (signal 9)", "export worker killed (RAM)", "timed out (90 min cap)"}


def gcs_text(url: str, path: Path) -> str:
    if not path.exists():
        subprocess.run(["gcloud", "storage", "cp", "-q", url, str(path)], check=True,
                       capture_output=True)
    return path.read_text(errors="replace")


def inference_failures(meta: dict[str, list[dict]], cache: Path) -> pd.DataFrame:
    """One row per (series, unit) that the final inference attempt reported as failed,
    from its inference_errors.txt, with the cause. A failed unit writes no metrics row,
    so its peak RAM is missing from peak_memory(); for the memory-class causes,
    run_peak_gb is the whole attempt's peak, printed at the end of the executed
    notebook ("peak system RAM this attempt"). It is the peak across every series in
    the batch, so it belongs to the failed unit only when it exceeds every unit that
    finished; peak_memory() has those to compare against."""
    d = cache / "inference_errors"
    d.mkdir(parents=True, exist_ok=True)
    jobs = []
    for sub, wfs in meta.items():
        for m in wfs:
            calls = m.get("calls", {}).get("Segmentator.inference", [])
            url = next(((c.get("outputs") or {}).get("inferenceErrors") for c in calls[::-1]
                        if (c.get("outputs") or {}).get("inferenceErrors")), None)
            if url:
                jobs.append((sub, m["id"], url))

    def one(j):
        sub, wf, url = j
        rows, cur = [], None
        for line in gcs_text(url, d / f"{wf}.txt").splitlines():
            h = re.match(r"^(\d[\d.]*\d)(?:/(\w+))?: (.*)", line)
            if h:
                cur = dict(submission=sub, workflow=wf, SeriesInstanceUID=h[1], unit=h[2], text=h[3])
                rows.append(cur)
            elif cur:
                cur["text"] += "\n" + line
        for r in rows:
            r["cause"] = next((c for k, c in CAUSES if k in r["text"]), "other")
            del r["text"]
        if any(r["cause"] in MEMORY_CAUSES for r in rows):
            nb = gcs_text(url.rsplit("/", 1)[0] + "/inferenceOutputNotebook.ipynb",
                          d / f"{wf}.ipynb")
            peak = re.search(r"peak system RAM this attempt: ([\d.]+)", nb)
            for r in rows:
                r["run_peak_gb"] = float(peak[1]) if peak else None
        return rows

    with ThreadPoolExecutor(16) as ex:
        rows = [r for rs in ex.map(one, jobs) for r in rs]
    return pd.DataFrame(rows).sort_values(["submission", "workflow", "SeriesInstanceUID", "unit"])


def bq_csv(sql: str) -> pd.DataFrame:
    res = subprocess.run(
        ["bq", "query", f"--project_id={BQ_PROJECT}", "--use_legacy_sql=false",
         "--format=csv", "--max_rows=100000000", "--quiet", sql],
        check=True, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=1800,
    )
    return pd.read_csv(io.StringIO(res.stdout))


def costs() -> pd.DataFrame:
    """Billed cost per workflow, task and category (gross, before credits - the figure
    Terra reports). Rows without a workflow label are not attributable to a run."""
    ids = ", ".join(f"'terra-{s}'" for s in RUNS.submission)
    c = bq_csv(f"""
        SELECT REGEXP_EXTRACT(sub, r'terra-(.*)') AS submission,
               REGEXP_EXTRACT(wf, r'cromwell-(.*)') AS workflow, task, category,
               ROUND(SUM(cost), 9) AS cost_usd
        FROM (
          SELECT (SELECT value FROM UNNEST(labels) WHERE key = 'terra-submission-id') AS sub,
                 (SELECT value FROM UNNEST(labels) WHERE key = 'cromwell-workflow-id') AS wf,
                 (SELECT value FROM UNNEST(labels) WHERE key = 'wdl-task-name') AS task,
                 {COST_CATEGORY_SQL} AS category, cost
          FROM `{BILLING}`
          WHERE project.id = '{GCP_PROJECT}' AND usage_start_time >= '2026-10-14')
        WHERE sub IN ({ids})
        GROUP BY 1, 2, 3, 4
        HAVING cost_usd != 0
        ORDER BY 1, 2, 3, 4""")
    return c


WRITTEN: dict[str, int] = {}


def write(df: pd.DataFrame, name: str) -> None:
    df.to_csv(DATA / f"{name}.csv.gz", index=False,
              compression={"method": "gzip", "compresslevel": 9, "mtime": 0})
    WRITTEN[name] = len(df)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache", type=Path, required=True, help="directory for raw metadata and metrics")
    ap.add_argument("--reruns-only", action="store_true",
                    help="build only the rerun tables (no BigQuery needed)")
    args = ap.parse_args()
    DATA.mkdir(exist_ok=True)

    meta = fetch_metadata(args.cache, RERUNS.submission)
    a = attempts_table(meta)
    write(a.merge(RERUNS, on="submission"), "cs2_rerun_task_attempts")
    um = fetch_usage_metrics(meta, args.cache)
    write(peak_memory(um).merge(RERUNS, on="submission"), "cs2_rerun_peak_memory")
    write(inference_failures(meta, args.cache).merge(RERUNS, on="submission"),
          "cs2_rerun_inference_failures")
    if args.reruns_only:
        print(json.dumps(WRITTEN, indent=1))
        return

    meta = fetch_metadata(args.cache, RUNS.submission)
    a = attempts_table(meta).merge(RUNS, on="submission")
    write(a, "cs2_task_attempts")

    um = fetch_usage_metrics(meta, args.cache)
    write(step_times(um).merge(RUNS, on="submission"), "cs2_step_times")
    write(peak_memory(um).merge(RUNS, on="submission"), "cs2_peak_memory")
    write(inference_failures(meta, args.cache).merge(RUNS, on="submission"), "cs2_inference_failures")

    write(costs().merge(RUNS, on="submission"), "cs2_costs_by_workflow")

    series = um[um.section == "convert"].groupby("submission").SeriesInstanceUID.nunique()
    write(RUNS.assign(series=RUNS.submission.map(series)), "cs2_runs")
    print(json.dumps(WRITTEN, indent=1))


if __name__ == "__main__":
    main()
