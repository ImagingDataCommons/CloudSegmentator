# /// script
# requires-python = ">=3.11"
# dependencies = ["pandas>=2.2"]
# ///
"""Rebuild the tidy data behind the paper's execution-analytics figures.

Replaces the Terra-API extract that the preprint's analysis notebook read
(`terra_api_data_1037_10000_126088_series_021524.csv`), which is no longer
available. Timings are reconstructed from the Cromwell logs that
remain in the Terra workspace bucket; costs and GPU regions come from BigQuery.

    uv run paper/build_data.py --cache <dir-for-raw-logs>

Writes gzip-compressed CSVs to paper/data/. Raw logs (~1 GB for all five runs) go to
--cache and are reused on later runs. Needs `gcloud` and `bq` on PATH, logged in
with read access to the workspace bucket and to idc-external-025.
"""

import argparse
import io
import json
import re
import subprocess
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

BUCKET = "gs://fc-5af492dc-6993-4c91-bbf6-3e2747868642"
BQ_PROJECT = "idc-external-025"
DATA = Path(__file__).parent / "data"

# Terra submissions behind the published numbers (matched on the totals in the text).
RUNS = pd.DataFrame(
    [
        ("3cae21b5-2b5b-4ae4-b966-d572b81ba05d", "1k", "oneVM"),
        ("4eb81ea3-dd59-4a39-b186-819b529d1841", "1k", "twoVM"),
        ("1cf0924f-38ff-46ff-a2b7-0c100de04efa", "1k", "threeVM"),
        ("3068f71e-6e83-4fb2-9350-1af1dedf6ec8", "10k", "twoVM"),
        ("f835e545-da03-4a6f-89b6-6460a9497ac1", "126k", "twoVM"),
    ],
    columns=["submission", "cohort", "config"],
)

# Cromwell task name -> the stage label used in the paper.
TASK_STAGE = {
    "totalSegmentatorEndToEnd": "All steps",
    "downloadDicomAndConvertAndInferenceTotalSegmentator": "Input conversion and inference",
    "downloadAndConvert": "Input conversion",
    "inferenceTotalSegmentator": "Inference",
    "dicomsegAndRadiomicsSR": "Feature extraction and output conversion",
}

WF_TS = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d),(\d{3}) ")
ATTEMPT = re.compile(r"TotalSegmentator\.(\w+):NA:(\d+)\]")
STATUS = re.compile(r"Status change from (\S+) to (\w+)")
TASK_TS = re.compile(r"^(\d{4}/\d\d/\d\d \d\d:\d\d:\d\d) (.*)")
SERIES = re.compile(r'"SeriesInstanceUIDs": \[([^\]]*)\]')
# Cromwell logs this when a call becomes runnable, before it waits for an execution
# token and is submitted. It is the closest logged event to the start of `Pending`.
STARTING = re.compile(r"\]: Starting TotalSegmentator\.(\w+)$")


def sync_logs(submission: str, cache: Path) -> Path:
    """Mirror only the *.log files of one submission into the cache."""
    dest = cache / submission
    if not (dest / "workflow.logs").is_dir():
        dest.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["gcloud", "storage", "rsync", "--recursive",
             "--exclude=^(?!.*\\.log$).*", f"{BUCKET}/submissions/{submission}", str(dest)],
            check=True, stdin=subprocess.DEVNULL,
        )
    return dest


def parse_workflow_log(path: Path) -> tuple[dict, list[dict], list[str]]:
    """One workflow log -> (workflow row, one row per task attempt, series UIDs)."""
    wf = {"workflow": path.name.removeprefix("workflow.").removesuffix(".log")}
    attempts: dict[tuple[str, int], dict] = {}
    starting: dict[str, pd.Timestamp] = {}  # task -> latest "Starting" line
    series: list[str] = []
    for line in path.read_text(errors="replace").splitlines():
        m = WF_TS.match(line)
        if not m:
            if not series and (s := SERIES.search(line)):
                series = re.findall(r"[\d.]+", s.group(1))
            continue
        ts = pd.Timestamp(f"{m.group(1)}.{m.group(2)}")
        wf.setdefault("start", ts)
        if "Restarting TotalSegmentator." in line:
            # Cromwell restarted and replayed results from its job store, overwriting
            # the original log: the timings in this file are not the run's.
            wf["restarted"] = True
        if "Workflow TotalSegmentator complete" in line:
            wf["end"], wf["status"] = ts, "Succeeded"
        elif "Workflow TotalSegmentator failed" in line:
            wf["end"], wf["status"] = ts, "Failed"
        elif "WorkflowExecutionActor" in line and "] aborted:" in line:
            wf["end"], wf["status"] = ts, "Aborted"
        if not series and (s := SERIES.search(line)):
            series = re.findall(r"[\d.]+", s.group(1))
        if st := STARTING.search(line.rstrip()):
            starting[st.group(1)] = ts
        if not (a := ATTEMPT.search(line)):
            continue
        key = (a.group(1), int(a.group(2)))
        row = attempts.setdefault(key, {"workflow": wf["workflow"], "task": key[0],
                                        "attempt": key[1], "starting": starting.get(key[0]),
                                        "first_event": ts})
        if st := STATUS.search(line):
            prev, new = st.groups()
            if prev == "-":
                row["created"] = ts
            if new == "Running":
                row["running"] = ts
            if prev == "Running" and new != "Running":
                row["terminal"], row["outcome"] = ts, new
    return wf, list(attempts.values()), series


def parse_task_log(path: Path) -> dict:
    """PAPI task log -> container-setup / user-action / delocalization timestamps."""
    out = {}
    marks = {
        "Starting container setup.": "container_setup",
        "Running user action:": "user_action_start",
        "Starting delocalization.": "delocalization_start",
        "Done delocalization.": "delocalization_end",
    }
    for line in path.read_text(errors="replace").splitlines():
        if m := TASK_TS.match(line):
            for text, col in marks.items():
                if m.group(2).startswith(text):
                    out.setdefault(col, pd.Timestamp(m.group(1).replace("/", "-")))
    return out


def parse_submission(submission: str, cache: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    root = sync_logs(submission, cache)
    logs = sorted((root / "workflow.logs").glob("workflow.*.log"))
    with ProcessPoolExecutor() as pool:
        parsed = list(pool.map(parse_workflow_log, logs, chunksize=64))
    workflows = pd.DataFrame([p[0] for p in parsed]).assign(submission=submission)
    attempts = pd.DataFrame([a for p in parsed for a in p[1]]).assign(submission=submission)
    series = pd.DataFrame(
        [(p[0]["workflow"], s) for p in parsed for s in p[2]], columns=["workflow", "SeriesInstanceUID"]
    ).assign(submission=submission)

    # Task logs exist only for attempts that were not preempted; attempt 1 lives
    # directly under call-<task>/, later attempts under call-<task>/attempt-N/.
    def task_log(r):
        d = root / "TotalSegmentator" / r.workflow / f"call-{r.task}"
        if r.attempt > 1:
            d = d / f"attempt-{r.attempt}"
        f = d / f"{r.task}.log"
        return parse_task_log(f) if f.exists() else {}

    done = attempts[attempts.outcome == "Success"]
    task_times = pd.DataFrame([task_log(r) for r in done.itertuples()], index=done.index)
    attempts = attempts.join(task_times)
    return workflows, attempts, series


def bq_csv(sql: str) -> pd.DataFrame:
    # stdin=DEVNULL: bq can stop at an interactive prompt and, with an inherited
    # stdin that never closes, wait on it forever.
    res = subprocess.run(
        ["bq", "query", f"--project_id={BQ_PROJECT}", "--use_legacy_sql=false",
         "--format=csv", "--max_rows=100000000", "--quiet", sql],
        check=True, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=1800,
    )
    return pd.read_csv(io.StringIO(res.stdout))


COST_CATEGORY_SQL = """
    CASE
      WHEN skuDescription LIKE 'Licensing%' THEN 'Other'
      WHEN skuDescription LIKE '%GPU%' THEN 'GPU'
      WHEN skuDescription LIKE '%Core%' THEN 'CPU'
      WHEN skuDescription LIKE '%Ram%' THEN 'RAM'
      WHEN skuDescription LIKE '%External IP%' THEN 'External IP'
      WHEN skuDescription LIKE 'Storage PD%' THEN 'Disk'
      WHEN skuDescription LIKE 'Network%' THEN 'Network egress'
      ELSE 'Other'
    END"""


def costs() -> pd.DataFrame:
    """Billed cost per workflow and category, long format. Pivoted in BigQuery so the
    result is one row per workflow - the bq CLI pages large results very slowly."""
    ids = ", ".join(f"'terra-{s}'" for s in RUNS.submission)
    wide = bq_csv(f"""
        SELECT * FROM (
          SELECT REGEXP_EXTRACT(submissionId, r'terra-(.*)') AS submission,
                 REGEXP_EXTRACT(workflowId, r'cromwell-(.*)') AS workflow,
                 {COST_CATEGORY_SQL} AS category, total
          FROM `{BQ_PROJECT}.012624.terraCostAnalysis`
          WHERE submissionId IN ({ids}))
        PIVOT (SUM(total) FOR category IN
          ('GPU', 'CPU', 'RAM', 'Network egress' AS Network_egress, 'External IP' AS External_IP,
           'Disk', 'Other'))
        ORDER BY submission, workflow""")
    long = wide.melt(id_vars=["submission", "workflow"], var_name="category", value_name="cost_usd")
    long["category"] = long.category.str.replace("_", " ")
    # BigQuery sums in no fixed order, so round away the last-bit noise; sort so that
    # rebuilding unchanged data gives a byte-identical file.
    long["cost_usd"] = long.cost_usd.round(9)
    return (long.dropna(subset=["cost_usd"])
            .sort_values(["submission", "workflow", "category"]).reset_index(drop=True))


def gpu_regions() -> pd.DataFrame:
    # Region of the GPU VM that completed inference, per workflow (126k run only),
    # as extracted from the Terra API by the original analysis.
    return bq_csv(f"""
        SELECT DISTINCT REGEXP_EXTRACT(tempId, r'cromwell-(.*)') AS workflow, region
        FROM `{BQ_PROJECT}.012624.gpus_total_hourly`""")


def series_times() -> pd.DataFrame:
    return bq_csv(f"""
        SELECT i.SeriesInstanceUID,
               i.dicom_download_time, i.dicom_conversion_time, i.total_segmentator_time,
               i.archiving_time AS nifti_archiving_time,
               r.itkimage2segimage_time, r.radiomics_time, r.structuredReportsGenerationTime,
               r.archiving_time AS seg_sr_archiving_time
        FROM `{BQ_PROJECT}.012624.126k-inference-series-level-times` i
        LEFT JOIN `{BQ_PROJECT}.012624.126k-radiomics-features-series-level-times` r
        USING (SeriesInstanceUID)""")


def write(df: pd.DataFrame, name: str) -> None:
    """data/<name>.csv.gz. mtime=0 keeps unchanged data byte-identical across rebuilds."""
    df.to_csv(DATA / f"{name}.csv.gz", index=False,
              compression={"method": "gzip", "compresslevel": 9, "mtime": 0})
    WRITTEN[name] = len(df)


WRITTEN: dict[str, int] = {}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache", type=Path, required=True, help="directory for raw Cromwell logs")
    args = ap.parse_args()
    DATA.mkdir(exist_ok=True)

    wfs, atts, sers = [], [], []
    for sub in RUNS.submission:
        w, a, s = parse_submission(sub, args.cache)
        wfs.append(w), atts.append(a), sers.append(s)
        print(f"{sub}: {len(w)} workflows, {len(a)} task attempts, {len(s)} series")
    workflows = pd.concat(wfs).merge(RUNS, on="submission")
    attempts = pd.concat(atts).merge(RUNS, on="submission")
    attempts["stage"] = attempts.task.map(TASK_STAGE)

    # Batch wall clock: Cromwell picks the workflow up -> workflow complete.
    workflows["wall_clock_h"] = (workflows.end - workflows.start).dt.total_seconds() / 3600
    if "restarted" in workflows:
        workflows.loc[workflows.restarted.fillna(False).astype(bool), "status"] = "Restarted"
    write(workflows, "batches")

    # Per attempt. Allocation mirrors the notebook's Pending -> UserAction start, and
    # includes the wait for an execution token before submission (queue_min);
    # teardown runs from the start of delocalization to Cromwell recording success.
    m = lambda a, b: (attempts[b] - attempts[a]).dt.total_seconds() / 60  # noqa: E731
    attempts["queue_min"] = m("starting", "created")
    attempts["allocation_setup_min"] = m("starting", "user_action_start")
    attempts["core_analysis_min"] = m("user_action_start", "delocalization_start")
    attempts["deallocation_min"] = m("delocalization_start", "terminal")
    attempts["attempt_min"] = m("starting", "terminal")  # time lost when preempted
    write(attempts, "task_attempts")

    c = costs()
    write(c, "costs_by_workflow")

    # 126k run: per-batch sums of the per-series stage timings the notebooks logged.
    s126 = pd.concat(sers)
    s126 = s126[s126.submission == RUNS.submission.iloc[-1]]
    per_batch = (
        s126.merge(series_times(), on="SeriesInstanceUID", how="left")
        .drop(columns=["SeriesInstanceUID", "submission"])
        .groupby("workflow").sum(min_count=1) / 60
    )
    write(per_batch.add_suffix("_min").reset_index(), "stage_times_126k")

    # 126k run: GPU VM intervals (non-preempted inference attempts) with region.
    gpu = attempts[(attempts.submission == RUNS.submission.iloc[-1])
                   & (attempts.task == "downloadDicomAndConvertAndInferenceTotalSegmentator")
                   & (attempts.outcome == "Success")][["workflow", "running", "terminal"]]
    write(gpu.merge(gpu_regions(), on="workflow", how="left"), "gpu_vms_126k")

    write(RUNS, "runs")
    print(json.dumps(WRITTEN, indent=1))


if __name__ == "__main__":
    main()
