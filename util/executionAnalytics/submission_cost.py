#!/usr/bin/env python3
"""Cost + execution breakdown for a single Terra submission.

Reuses the extraction performed by ``Notebooks/Terra-Cromwell Workflow Metadata.ipynb`` but:
  * scopes to one submission instead of listing every submission in the workspace,
  * carries Terra's actual per-workflow ``cost`` / ``costType`` (the notebook drops it),
  * authenticates over the Terra REST API with the local ``gcloud`` access token,
    so it runs anywhere ``gcloud auth login`` works (no Colab / Drive mount needed).

Terra attaches actual cost only at the workflow level; per-task rows carry the
execution metadata (machine type, GPU, runtime, docker) so you can see where the
money went. Per-SKU dollar costs per task come from the GCP billing export
(``query_billing``; needs BigQuery access to that export table), with an offline
list-price estimate as fallback.

Outputs (``submission_<id8>_*.csv``):
  _cost.csv            one row per task call attempt (Cromwell metadata)
  _workflows.csv       one row per workflow: entity, #series, voxels/slices/MB (idc-index),
                       per-task runtime + attempts + $, config (docker digests, radiomics
                       engine, region) -- the input to cost_model.py fit / evaluate
  _series.csv          one row per series: idc-index features + notebook timings
  _billing.csv         actual per-(workflow, task, SKU) $ (billing export)      } one of
  _cost_estimate.csv   offline list-price estimate per workflow (fallback)      } the two
  _cost_vs_voxels.csv  legacy MOOSE per-workflow cost vs voxels (when lz4/json metrics exist)

Works for both the legacy MOOSE/TotalSegmentator workflows (``*UsageMetrics*.lz4|.json``)
and the harmonized ``Segmentator`` workflow (``inference_UsageMetrics.csv`` /
``output_conversion_UsageMetrics.csv`` / ``run_summary.json``). Per-series voxel counts
for harmonized runs come from ``idc-index`` (``idc_features.py``) keyed on
SeriesInstanceUID, so no notebook change is needed.

Usage:
    python submission_cost.py <submission-url-or-id> [--workspace ns/name] [--out file.csv]
                              [--region-rates region_rates.json] [--no-bq] [--no-metrics]

The billing project / workspace are parsed from a Terra submission_history URL, or
pass --workspace explicitly (e.g. terra-billing-datester/kyle-testing).
"""
import argparse
import csv
import io
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone, date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

FIRECLOUD = "https://api.firecloud.org/api"

# Approximate GCP list prices ($/unit/hour), US regions. Spot ~= preemptible.
# Fallback only -- pass --region-rates (from region_prices.py) for per-region rates.
PRICES = {
    "ondemand": {"n1_vcpu": 0.031611, "n1_ram_gb": 0.004237, "gpu_t4": 0.35},
    "spot":     {"n1_vcpu": 0.006655, "n1_ram_gb": 0.000892, "gpu_t4": 0.105},
}
PD_GB_HR = {"HDD": 0.04 / 730, "SSD": 0.17 / 730}  # PD standard / SSD, $/GB/hour
GPU_KEY = {"nvidia-tesla-t4": "gpu_t4"}

# GCP billing export that carries the Terra cost labels (actual, authoritative $).
BILLING_TABLE = ("idc-terra-explore-admin.terra_cost_exports."
                 "gcp_billing_export_v1_01E8DE_3FD7A1_F95FEE")
BQ_JOB_PROJECT = "idc-external-031"  # project to run the query under (needs bigquery.jobUser)


def _num(x):
    """First number in a string/int/float, else 0."""
    if x is None:
        return 0.0
    m = re.search(r"[\d.]+", str(x))
    return float(m.group()) if m else 0.0


def _region_of(zone):
    """'us-east4-a,us-east4-b' or 'us-east4-a' -> 'us-east4'."""
    if not zone:
        return None
    z = str(zone).split(",")[0].strip().split()[0]
    return z.rsplit("-", 1)[0] if re.match(r"^[a-z]+-[a-z]+\d+-[a-z]$", z) else z


def rate_for_task(r, rates):
    """$/h for a task call from a region_prices.py rate file, or None.
    Prefers a shape with the task's own name; else first GPU/non-GPU shape as appropriate."""
    if not rates:
        return None
    region = _region_of(r.get("zone"))
    tables = rates.get("rates", {})
    shapes = rates.get("shapes", {})
    task = r.get("wdlTask") or ""
    cand = [n for n in tables if n.lower() == task.lower()]
    if not cand:
        want_gpu = bool(r.get("gpuType"))
        cand = [n for n in tables if bool(shapes.get(n, {}).get("gpu")) == want_gpu]
    for n in cand:
        row = tables[n].get(region)
        if row:
            return row["total_hr"], n, region
    return None


def estimate_task_cost(r, rates=None):
    """Estimate $ for one task call from its runtime attributes + wall-clock minutes.
    Returns {gpu, cpu, ram, disk, total, tier, rate_hr, rate_shape}. With a rate file the
    breakdown comes from that region's shape (gpu/vcpu/ram/disk components); otherwise the
    hard-coded US list prices are used. CPU here = n1 vCPU + RAM (the VM compute)."""
    hours = (r.get("runtimeMin") or 0) / 60.0
    tier = "spot" if _num(r.get("preemptible")) > 0 else "ondemand"
    hit = rate_for_task(r, rates)
    if hit:
        rate_hr, shape, region = hit
        comp = rates["rates"][shape][region]
        return {"gpu": comp["gpu_hr"] * hours, "cpu": comp["vcpu_hr"] * hours,
                "ram": comp["ram_hr"] * hours, "disk": comp["disk_hr"] * hours,
                "total": rate_hr * hours, "tier": rates.get("tier", tier),
                "rate_hr": rate_hr, "rate_shape": f"{shape}@{region}"}
    p = PRICES[tier]
    vcpu = _num(r.get("cpu"))
    ram = _num(r.get("memory"))
    gpu_key = GPU_KEY.get(r.get("gpuType"))
    gpu_n = _num(r.get("gpuCount")) if r.get("gpuType") else 0
    # disks: boot (PD standard) + the "local-disk <GB> <HDD|SSD>" working disk.
    disk_gb_hdd = _num(r.get("bootDiskGb"))
    disk_gb_ssd = 0.0
    dstr = str(r.get("disks") or "")
    dsize = _num(dstr)
    if "SSD" in dstr.upper():
        disk_gb_ssd += dsize
    else:
        disk_gb_hdd += dsize
    gpu = gpu_n * p.get(gpu_key, 0) * hours if gpu_key else 0.0
    cpu = vcpu * p["n1_vcpu"] * hours
    ram_c = ram * p["n1_ram_gb"] * hours
    disk = (disk_gb_hdd * PD_GB_HR["HDD"] + disk_gb_ssd * PD_GB_HR["SSD"]) * hours
    total = gpu + cpu + ram_c + disk
    return {"gpu": gpu, "cpu": cpu, "ram": ram_c, "disk": disk, "total": total, "tier": tier,
            "rate_hr": (total / hours) if hours else None, "rate_shape": "builtin-us"}


def sku_category(sku):
    """Bucket a billing SKU description into a coarse cost category."""
    s = (sku or "").lower()
    if "gpu" in s:
        return "GPU"
    if "core" in s:
        return "vCPU"
    if "ram" in s:
        return "RAM"
    if "ip" in s:
        return "External IP"
    if "network" in s or "data transfer" in s:
        return "Egress"
    if "pd" in s or "storage" in s or "disk" in s:
        return "Disk"
    return "Other"


def query_billing(sub_id, since_date, table, bq_project):
    """Return actual per-(workflow, task, sku) costs from the GCP billing export, or None.

    The label *values* are prefixed: ``terra-<submissionId>`` and ``cromwell-<workflowId>``.
    Runs ``bq query`` via stdin (avoids shell-quoting the multi-line SQL); requires
    bigquery.dataViewer on the export dataset + bigquery.jobUser on ``bq_project``."""
    sql = f"""
SELECT
  wf.value AS workflow_label,
  COALESCE(task.value, '(no task)') AS wdl_task,
  service.description AS service,
  sku.description AS sku,
  SUM(cost) AS gross,
  SUM(cost) + SUM(IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0)) AS net,
  SUM(usage.amount_in_pricing_units) AS usage_amount,
  ANY_VALUE(usage.pricing_unit) AS usage_unit
FROM `{table}`
  LEFT JOIN UNNEST(labels) sub  ON sub.key  = 'terra-submission-id'
  LEFT JOIN UNNEST(labels) wf   ON wf.key   = 'cromwell-workflow-id'
  LEFT JOIN UNNEST(labels) task ON task.key = 'wdl-task-name'
WHERE sub.value = 'terra-{sub_id}'
  AND _PARTITIONTIME >= TIMESTAMP('{since_date}')
GROUP BY workflow_label, wdl_task, service, sku
"""
    cmd = (f"bq --project_id={bq_project} query --use_legacy_sql=false "
           f"--format=csv --quiet --max_rows=100000")
    res = subprocess.run(cmd, input=sql, capture_output=True, text=True, shell=True)
    if res.returncode != 0:
        last = res.stderr.strip().splitlines()[-1] if res.stderr.strip() else "unknown error"
        print(f"\n[billing] BigQuery lookup failed via project '{bq_project}': {last}\n"
              f"[billing] falling back to the offline price estimate.")
        return None
    lines = [ln for ln in res.stdout.splitlines() if ln.strip()]
    if len(lines) <= 1:
        print("\n[billing] no billing rows for this submission yet "
              "(export lag, or different billing account); using estimate.")
        return None
    out = []
    for row in csv.DictReader(lines):
        wfl = row.get("workflow_label") or ""
        out.append({
            "workflowId": wfl[len("cromwell-"):] if wfl.startswith("cromwell-") else wfl,
            "wdlTask": row.get("wdl_task"),
            "service": row.get("service"),
            "sku": row.get("sku"),
            "gross": float(row.get("gross") or 0),
            "net": float(row.get("net") or 0),
            "usageAmount": float(row.get("usage_amount") or 0),
            "usageUnit": row.get("usage_unit"),
        })
    return out


def get_token():
    # shell=True so Windows resolves gcloud.cmd via PATHEXT.
    out = subprocess.run(
        "gcloud auth print-access-token",
        capture_output=True, text=True, check=True, shell=True,
    )
    return out.stdout.strip()


def parse_target(arg, workspace):
    """Return (billing_project, workspace_name, submission_id)."""
    sub_id = arg
    ns = name = None
    m = re.search(r"workspaces/([^/]+)/([^/]+)/submission_history/([0-9a-f-]+)", arg)
    if m:
        ns, name, sub_id = m.group(1), m.group(2), m.group(3)
    if workspace:
        ns, name = workspace.split("/", 1)
    if not (ns and name):
        sys.exit("Could not determine workspace; pass --workspace ns/name")
    return ns, name, sub_id


def api_get(path, token, allow_fail=False):
    req = urllib.request.Request(
        f"{FIRECLOUD}{path}", headers={"Authorization": f"Bearer {token}"}
    )
    try:
        with urllib.request.urlopen(req) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if allow_fail:
            return None
        sys.exit(f"Terra API {e.code} on {path}: {e.read().decode()[:300]}")


def parse_ts(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def duration_min(start, end):
    a, b = parse_ts(start), parse_ts(end)
    if a and b:
        return round((b - a).total_seconds() / 60, 2)
    return None


def gsutil(arg_str):
    """Run gsutil (shell=True so Windows resolves gsutil.cmd) and return CompletedProcess."""
    return subprocess.run(f"gsutil {arg_str}", capture_output=True, shell=True)


def _gs_list(pattern):
    listing = gsutil(f'ls "{pattern}"')
    return [ln.strip() for ln in listing.stdout.decode("utf-8", "ignore").splitlines()
            if ln.strip().startswith("gs://")]


def _gs_cat(path):
    return gsutil(f'cp "{path}" -').stdout


def load_usage_metrics(submission_root, wf_ids):
    """LEGACY workflows: fetch every *UsageMetrics*.lz4 / .json under the submission and
    bucket the per-series workload metrics by workflowId. Only files carrying series
    ``total_pixels`` (the inference notebook's image metrics) are kept.
    Returns {wf_id: {series, gpu_util}}."""
    out = {w: {"series": {}, "gpu_util": []} for w in wf_ids}
    paths = _gs_list(f"{submission_root}/**UsageMetrics*.lz4") + \
        _gs_list(f"{submission_root}/**UsageMetrics*.json")
    for p in paths:
        wf = next((w for w in wf_ids if w in p), None)
        if not wf:
            continue
        raw = _gs_cat(p)
        if not raw:
            continue
        try:
            if p.endswith(".lz4"):
                import lz4.frame
                raw = lz4.frame.decompress(raw)
            d = json.loads(raw)
        except Exception:
            continue
        series = d.get("series") if isinstance(d, dict) else None
        if isinstance(series, dict) and any(
            isinstance(v, dict) and "total_pixels" in v for v in series.values()
        ):
            out[wf]["series"].update(series)
            out[wf]["gpu_util"] += [
                g.get("gpu_util_pct") for g in d.get("gpu", [])
                if isinstance(g, dict) and g.get("gpu_util_pct") is not None
            ]
    return out


def _f(x):
    try:
        return float(x) if x not in (None, "") else None
    except (TypeError, ValueError):
        return None


def load_harmonized_metrics(submission_root, wf_ids):
    """HARMONIZED Segmentator workflow: read the per-task CSVs + run_summary.json.
    Returns {wf_id: {"series": {uid: {...}}, "run_summary": {...}, "found": bool}} where
    the per-series dict merges nb1 (download_s, download_mb, dcm2niix_s), nb2
    (model_inference_s per model -> models_s, inference_s total) and nb3 (model_seg_s per
    model -> seg_s, series_total_s)."""
    out = {w: {"series": {}, "run_summary": {}, "found": False} for w in wf_ids}
    paths = _gs_list(f"{submission_root}/**UsageMetrics.csv") + \
        _gs_list(f"{submission_root}/**run_summary.json")
    for p in paths:
        wf = next((w for w in wf_ids if w in p), None)
        if not wf:
            continue
        name = p.rsplit("/", 1)[-1]
        if name == "combined_UsageMetrics.csv":
            continue  # concatenation of the others
        raw = _gs_cat(p)
        if not raw:
            continue
        text = raw.decode("utf-8", "ignore")
        ser = out[wf]["series"]
        if name == "run_summary.json":
            try:
                out[wf]["run_summary"] = json.loads(text)
                out[wf]["found"] = True
            except ValueError:
                pass
            continue
        rows = list(csv.DictReader(io.StringIO(text)))
        if not rows:
            continue
        cols = set(rows[0].keys())
        out[wf]["found"] = True
        if "model_inference_s" in cols:               # nb2 inference_UsageMetrics.csv
            for r in rows:
                s = ser.setdefault(r["SeriesInstanceUID"], {})
                s.setdefault("models_s", {})[r.get("model") or ""] = _f(r.get("model_inference_s"))
                s["inference_run_total_s"] = _f(r.get("run_total_elapsed_s"))
        elif "model_seg_s" in cols:                   # nb3 output_conversion_UsageMetrics.csv
            for r in rows:
                s = ser.setdefault(r["SeriesInstanceUID"], {})
                s.setdefault("seg_s", {})[r.get("model") or ""] = _f(r.get("model_seg_s"))
                s["series_total_s"] = _f(r.get("series_total_s"))
                if "model_radiomics_s" in cols:        # newer nb3 (per-phase profiling columns)
                    s.setdefault("radiomics_s", {})[r.get("model") or ""] = _f(r.get("model_radiomics_s"))
                    s.setdefault("n_labels", {})[r.get("model") or ""] = _f(r.get("n_labels"))
                    s["ref_download_s"] = _f(r.get("ref_download_s"))
                    if r.get("radiomics_method"):
                        s["radiomics_method"] = r.get("radiomics_method")
        elif "dcm2niix_s" in cols:                    # nb1 convert_UsageMetrics.csv
            for r in rows:
                s = ser.setdefault(r["SeriesInstanceUID"], {})
                s["download_s"] = _f(r.get("download_s"))
                s["download_mb"] = _f(r.get("download_mb"))
                s["download_dcm_files"] = _f(r.get("download_dcm_files"))
                s["dcm2niix_s"] = _f(r.get("dcm2niix_s"))
                s["convert_run_total_s"] = _f(r.get("run_total_elapsed_s"))
        elif "total_pixels" in cols or "moose_s" in cols:   # legacy 17-col CSV
            for r in rows:
                s = ser.setdefault(r["SeriesInstanceUID"], {})
                for k, v in r.items():
                    if k != "SeriesInstanceUID":
                        s[k] = _f(v) if _f(v) is not None else v
    for w in out.values():
        for s in w["series"].values():
            if "models_s" in s:
                s["inference_s"] = sum(v or 0 for v in s["models_s"].values())
            if "seg_s" in s:
                s["seg_total_s"] = sum(v or 0 for v in s["seg_s"].values())
            if "radiomics_s" in s:
                s["radiomics_total_s"] = sum(v or 0 for v in s["radiomics_s"].values())
            if "n_labels" in s:
                s["n_labels_total"] = sum(v or 0 for v in s["n_labels"].values())
    return out


def _entity_uids(entity_attrs):
    """SeriesInstanceUIDs from a Terra entity's attributes (JSON string, dict, or list)."""
    raw = (entity_attrs or {}).get("SeriesInstanceUIDs")
    if raw is None:
        return []
    if isinstance(raw, dict) and "items" in raw:        # Terra attribute list form
        raw = raw["items"]
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except ValueError:
            try:
                import yaml
                parsed = yaml.safe_load(raw)
            except Exception:
                parsed = raw
        raw = parsed
    if isinstance(raw, dict):
        raw = raw.get("SeriesInstanceUIDs", [])
    if isinstance(raw, str):
        raw = re.split(r"[\s,]+", raw)
    return [u for u in (str(x).strip() for x in (raw or [])) if re.fullmatch(r"[\d.]+", u)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("submission", help="Terra submission URL or submission UUID")
    ap.add_argument("--workspace", help="billing_project/workspace override")
    ap.add_argument("--out", help="output CSV path")
    ap.add_argument("--no-metrics", action="store_true",
                    help="skip the usage-metrics join from the submission bucket")
    ap.add_argument("--no-idc", action="store_true",
                    help="skip the idc-index feature lookup (voxels/slices per series)")
    ap.add_argument("--bq-project", default=BQ_JOB_PROJECT,
                    help="GCP project to run the billing query under (needs bigquery.jobUser)")
    ap.add_argument("--billing-table", default=BILLING_TABLE,
                    help="fully-qualified GCP billing export table")
    ap.add_argument("--no-bq", action="store_true",
                    help="skip the BigQuery billing lookup; use the offline price estimate instead")
    ap.add_argument("--region-rates", help="region_rates.json from region_prices.py; makes the "
                                           "offline estimate region-aware")
    ap.add_argument("--label", help="tag stored in the workflows CSV (e.g. moose-pilot)")
    args = ap.parse_args()

    ns, name, sub_id = parse_target(args.submission, args.workspace)
    prefix = f"submission_{sub_id[:8]}"
    out_path = args.out or f"{prefix}_cost.csv"
    token = get_token()
    rates = None
    if args.region_rates:
        with open(args.region_rates) as f:
            rates = json.load(f)

    base = f"/workspaces/{ns}/{name}/submissions/{sub_id}"
    sub = api_get(base, token)

    rows = []
    workflows = sub.get("workflows", [])
    wf_meta = {}
    for wf in workflows:
        wf_id = wf.get("workflowId")
        entity = (wf.get("workflowEntity") or {}).get("entityName")
        wf_cost = wf.get("cost")
        cost_type = wf.get("costType")
        if not wf_id:
            continue
        meta = api_get(f"{base}/workflows/{wf_id}", token)
        wf_meta[wf_id] = meta
        calls = meta.get("calls", {})
        if not calls:
            rows.append({
                "workflowId": wf_id, "entity": entity, "workflowCost": wf_cost,
                "costType": cost_type, "wdlTask": None, "callIndex": None,
            })
            continue
        for task_name, attempts in calls.items():
            for a in attempts:
                jes = a.get("jes", {})
                rt = a.get("runtimeAttributes", {})
                # jes is often empty on Terra; fall back to runtimeAttributes.
                cpu, mem = rt.get("cpu"), rt.get("memory")
                machine = jes.get("machineType")
                if not machine and cpu and mem:
                    machine = f"custom cpu={cpu} mem={mem}"
                zone = jes.get("zone") or rt.get("zones")
                rows.append({
                    "workflowId": wf_id,
                    "entity": entity,
                    "workflowCost": wf_cost,
                    "costType": cost_type,
                    "wdlTask": task_name.split(".")[-1],
                    "callIndex": a.get("shardIndex"),
                    "attempt": a.get("attempt"),
                    "executionStatus": a.get("executionStatus"),
                    "machineType": machine,
                    "zone": zone,
                    "gpuType": rt.get("gpuType"),
                    "gpuCount": rt.get("gpuCount"),
                    "cpu": cpu,
                    "memory": mem,
                    "disks": rt.get("disks"),
                    "bootDiskGb": rt.get("bootDiskSizeGb"),
                    "preemptible": rt.get("preemptible"),
                    "dockerImage": a.get("dockerImageUsed"),
                    "dockerSizeGb": round(float(a.get("compressedDockerSize", 0)) / 1073741824, 3),
                    "start": a.get("start"),
                    "end": a.get("end"),
                    "runtimeMin": duration_min(a.get("start"), a.get("end")),
                })

    if not rows:
        sys.exit("No workflows found for this submission.")

    cols = list(dict.fromkeys(k for r in rows for k in r))
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    # ---- printed summary -------------------------------------------------
    total = sub.get("cost")
    print(f"\nSubmission {sub_id}")
    print(f"  workspace : {ns}/{name}")
    print(f"  method    : {sub.get('methodConfigurationName')}")
    print(f"  submitted : {sub.get('submissionDate')}   status: {sub.get('status')}")
    print(f"  TOTAL COST: ${total}   (per-workflow cost cap ${sub.get('perWorkflowCostCap')})")
    print(f"\n  Per-workflow actual cost ({len(workflows)} workflows):")
    wf_total = 0.0
    for wf in workflows:
        c = wf.get("cost") or 0
        wf_total += c
        ent = (wf.get("workflowEntity") or {}).get("entityName")
        print(f"    {wf.get('workflowId')}  entity={str(ent):<8}  ${c:<6} {wf.get('costType')}  {wf.get('status')}")
    print(f"    {'sum of workflow costs':<55} ${round(wf_total, 2)}")

    task_rows = [r for r in rows if r.get("wdlTask")]
    if task_rows:
        print(f"\n  Heaviest tasks by runtime ({len(task_rows)} call attempts total):")
        for r in sorted(task_rows, key=lambda r: r.get("runtimeMin") or 0, reverse=True)[:10]:
            gpu = f"{r.get('gpuCount')}x{r.get('gpuType')}" if r.get("gpuType") else "-"
            spec = f"cpu{r.get('cpu')}/{r.get('memory')}"
            print(f"    {r['wdlTask']:<28} {spec:<14} gpu={gpu:<16} {r.get('runtimeMin')} min  [{r.get('executionStatus')}]")

    written = [out_path]

    # ---- entity series lists (a-priori: what each workflow was asked to process) ----
    entity_uids = {}
    for wf in workflows:
        we = wf.get("workflowEntity") or {}
        et, en = we.get("entityType"), we.get("entityName")
        if et and en:
            ent = api_get(f"/workspaces/{ns}/{name}/entities/{et}/{en}", token, allow_fail=True)
            entity_uids[wf.get("workflowId")] = _entity_uids((ent or {}).get("attributes"))

    # ---- usage-metrics join: cost vs. workload (voxels) ------------------
    metrics, hmetrics = {}, {}
    root = sub.get("submissionRoot")
    wf_ids = [wf.get("workflowId") for wf in workflows if wf.get("workflowId")]
    if not args.no_metrics and root:
        hmetrics = load_harmonized_metrics(root, wf_ids)
        if not any(v["found"] for v in hmetrics.values()):
            hmetrics = {}
            try:
                metrics = load_usage_metrics(root, wf_ids)
            except Exception as exc:  # lz4 missing etc.
                print(f"\n[metrics] legacy metrics load failed: {exc}")
                metrics = {}

    if metrics:
        combined, series_rows = [], []
        model_totals = {}
        for wf in workflows:
            w = wf.get("workflowId")
            series = (metrics.get(w) or {}).get("series", {})
            if not w or not series:
                continue
            ent = (wf.get("workflowEntity") or {}).get("entityName")
            cost = wf.get("cost") or 0.0
            util = (metrics.get(w) or {}).get("gpu_util", [])
            vox = sum(v.get("total_pixels", 0) for v in series.values())
            moose = sum(v.get("moose_s", 0) or 0 for v in series.values())
            mvox = vox / 1e6
            combined.append({
                "entity": ent, "workflowId": w, "cost": round(cost, 4),
                "series": len(series), "voxelsM": round(mvox, 1),
                "mooseInferenceSec": round(moose, 1),
                "dollarsPerMvoxel": round(cost / mvox, 5) if mvox else None,
                "dollarsPerSeries": round(cost / len(series), 5) if series else None,
                "gpuUtilMinPct": min(util) if util else None,
                "gpuUtilMaxPct": max(util) if util else None,
            })
            for uid, v in series.items():
                models = v.get("moose_models_s", {}) or {}
                for mk, mv in models.items():
                    model_totals[mk] = model_totals.get(mk, 0) + (mv or 0)
                top = max(models.items(), key=lambda kv: kv[1] or 0) if models else (None, None)
                series_rows.append({
                    "workflowId": w, "entity": ent, "seriesUID": uid,
                    "slices": v.get("slices"), "rows": v.get("rows"), "cols": v.get("cols"),
                    "voxels": v.get("total_pixels"), "downloadMb": v.get("download_mb"),
                    "downloadSec": v.get("download_s"), "dcm2niixSec": v.get("dcm2niix_s"),
                    "mooseSec": v.get("moose_s"),
                    "topModelStage": top[0], "topModelStageSec": top[1],
                    "modelTimings": json.dumps(models),
                })

        if combined:
            cv_path = f"{prefix}_cost_vs_voxels.csv"
            with open(cv_path, "w", newline="") as f:
                w_ = csv.DictWriter(f, fieldnames=list(combined[0].keys()))
                w_.writeheader(); w_.writerows(combined)
            written.append(cv_path)

            print(f"\n  Cost vs. workload (voxels), {len(combined)} workflows:")
            hdr = f"    {'case':>5} {'cost$':>6} {'series':>6} {'voxels(M)':>10} {'moose_s':>8} {'$/Mvox':>8} {'$/series':>9} {'GPU%':>7}"
            print(hdr)
            tc = tv = ts = 0.0
            for c in sorted(combined, key=lambda r: -(r["voxelsM"] or 0)):
                gpu = (f"{c['gpuUtilMinPct']}-{c['gpuUtilMaxPct']}"
                       if c["gpuUtilMinPct"] is not None else "-")
                print(f"    {str(c['entity']):>5} {c['cost']:>6.2f} {c['series']:>6} "
                      f"{c['voxelsM']:>10.1f} {c['mooseInferenceSec']:>8.0f} "
                      f"{(c['dollarsPerMvoxel'] or 0):>8.4f} {(c['dollarsPerSeries'] or 0):>9.4f} {gpu:>7}")
                tc += c["cost"]; tv += c["voxelsM"]; ts += c["series"]
            print(f"    {'TOT':>5} {tc:>6.2f} {ts:>6.0f} {tv:>10.1f} {'':>8} "
                  f"{(tc/tv if tv else 0):>8.4f} {(tc/ts if ts else 0):>9.4f}")

            print(f"\n  Top model stages by total inference time (across {len(series_rows)} series):")
            for mk, mv in sorted(model_totals.items(), key=lambda kv: -kv[1])[:10]:
                print(f"    {mk:<40} {mv:>8.1f} s")

            print(f"\n  Heaviest series by inference time:")
            for r in sorted(series_rows, key=lambda r: r.get("mooseSec") or 0, reverse=True)[:10]:
                vx = (r["voxels"] or 0) / 1e6
                print(f"    case {str(r['entity']):>4} {r['seriesUID'][:24]:<24} "
                      f"{vx:>6.1f} Mvox  {r['mooseSec']:>7.1f}s  top={r['topModelStage']}")
    elif not args.no_metrics and root and not hmetrics:
        print("\n[metrics] no UsageMetrics files with per-series data found for this submission.")

    # ---- ACTUAL SKU/task cost from the billing export (fallback: estimate) ----
    sub_date = (sub.get("submissionDate") or "")[:10]
    try:
        since = (date.fromisoformat(sub_date) - timedelta(days=1)).isoformat()
    except ValueError:
        since = "2020-01-01"
    billing = None if args.no_bq else query_billing(
        sub_id, since, args.billing_table, args.bq_project)

    ent_by_wf = {wf.get("workflowId"): (wf.get("workflowEntity") or {}).get("entityName")
                 for wf in workflows}
    terra_by_wf = {wf.get("workflowId"): wf.get("cost") for wf in workflows}
    est_by_wf = {}
    if billing:
        bill_path = f"{prefix}_billing.csv"
        with open(bill_path, "w", newline="") as f:
            w_ = csv.DictWriter(f, fieldnames=["workflowId", "entity", "wdlTask",
                                               "category", "service", "sku", "gross", "net",
                                               "usageAmount", "usageUnit"])
            w_.writeheader()
            for r in sorted(billing, key=lambda r: -r["net"]):
                w_.writerow({"workflowId": r["workflowId"], "entity": ent_by_wf.get(r["workflowId"]),
                             "wdlTask": r["wdlTask"], "category": sku_category(r["sku"]),
                             "service": r["service"], "sku": r["sku"],
                             "gross": round(r["gross"], 4), "net": round(r["net"], 4),
                             "usageAmount": round(r["usageAmount"], 4), "usageUnit": r["usageUnit"]})
        written.append(bill_path)

        by_cat, by_task, by_wf = {}, {}, {}
        for r in billing:
            by_cat[sku_category(r["sku"])] = by_cat.get(sku_category(r["sku"]), 0) + r["net"]
            by_task[r["wdlTask"]] = by_task.get(r["wdlTask"], 0) + r["net"]
            by_wf[r["workflowId"]] = by_wf.get(r["workflowId"], 0) + r["net"]
        tot = sum(by_cat.values())

        print(f"\n  ACTUAL cost by SKU category (billing export, net of credits):")
        for cat, v in sorted(by_cat.items(), key=lambda kv: -kv[1]):
            print(f"    {cat:<12} ${v:>8.4f}  {(100 * v / tot if tot else 0):>4.0f}%")
        print(f"    {'TOTAL':<12} ${tot:>8.4f}")

        print(f"\n  ACTUAL cost by WDL task:")
        for t, v in sorted(by_task.items(), key=lambda kv: -kv[1]):
            print(f"    {str(t):<24} ${v:>8.4f}")

        print(f"\n  Per-workflow: billing vs Terra-reported:")
        print(f"    {'case':>5} {'billing$':>9} {'terra$':>8}")
        for w, v in sorted(by_wf.items(), key=lambda kv: -kv[1]):
            print(f"    {str(ent_by_wf.get(w)):>5} {v:>9.4f} {str(terra_by_wf.get(w)):>8}")

    # ---- offline estimate (always computed; primary only when billing is missing) ----
    for r in task_rows:
        e = estimate_task_cost(r, rates)
        w = r["workflowId"]
        agg = est_by_wf.setdefault(w, {"entity": r.get("entity"),
                                       "actual": r.get("workflowCost") or 0.0,
                                       "gpu": 0.0, "cpu": 0.0, "ram": 0.0,
                                       "disk": 0.0, "est": 0.0, "tier": e["tier"],
                                       "tasks": {}})
        for k in ("gpu", "cpu", "ram", "disk"):
            agg[k] += e[k]
        agg["est"] += e["total"]
        t = agg["tasks"].setdefault(r["wdlTask"], {"est": 0.0, "rate_hr": e.get("rate_hr"),
                                                   "rate_shape": e.get("rate_shape")})
        t["est"] += e["total"]

    if not billing and est_by_wf:
        est_path = f"{prefix}_cost_estimate.csv"
        ecols = ["entity", "workflowId", "tier", "actualCost", "estCost",
                 "gpu", "vcpuRam", "disk", "estVsActual"]
        with open(est_path, "w", newline="") as f:
            w_ = csv.DictWriter(f, fieldnames=ecols)
            w_.writeheader()
            for w, a in est_by_wf.items():
                w_.writerow({
                    "entity": a["entity"], "workflowId": w, "tier": a["tier"],
                    "actualCost": round(a["actual"], 4), "estCost": round(a["est"], 4),
                    "gpu": round(a["gpu"], 4), "vcpuRam": round(a["cpu"] + a["ram"], 4),
                    "disk": round(a["disk"], 4),
                    "estVsActual": round(a["est"] / a["actual"], 2) if a["actual"] else None,
                })
        written.append(est_path)

        src = f"region rates from {args.region_rates}" if rates else "built-in US T4/n1 list prices"
        print(f"\n  Estimated SKU split ({next(iter(est_by_wf.values()))['tier']}, {src} "
              f"x wall-clock; not billing-authoritative):")
        print(f"    {'case':>5} {'actual$':>8} {'est$':>7} {'GPU$':>7} {'vCPU+RAM$':>10} {'disk$':>7} {'GPU%':>6}")
        ta = te = tg = tc = td = 0.0
        for a in sorted(est_by_wf.values(), key=lambda a: -a["est"]):
            cr = a["cpu"] + a["ram"]
            gpct = 100 * a["gpu"] / a["est"] if a["est"] else 0
            print(f"    {str(a['entity']):>5} {a['actual']:>8.2f} {a['est']:>7.2f} "
                  f"{a['gpu']:>7.2f} {cr:>10.2f} {a['disk']:>7.3f} {gpct:>5.0f}%")
            ta += a["actual"]; te += a["est"]; tg += a["gpu"]; tc += cr; td += a["disk"]
        print(f"    {'TOT':>5} {ta:>8.2f} {te:>7.2f} {tg:>7.2f} {tc:>10.2f} {td:>7.3f} "
              f"{(100 * tg / te if te else 0):>5.0f}%")
        if ta:
            print(f"    estimate = {100 * te / ta:.0f}% of Terra-reported cost (differences: storage / "
                  f"egress / IP not modeled; Cromwell call time > billed VM time; spot price drift).")

    # ======================================================================
    # Per-workflow feature + cost table (input to cost_model.py) and per-series table
    # ======================================================================
    task_names = list(dict.fromkeys(r["wdlTask"] for r in task_rows))

    # per-series a-priori features from idc-index
    all_uids = set()
    for w in wf_ids:
        all_uids.update(entity_uids.get(w, []))
        all_uids.update(((hmetrics.get(w) or {}).get("series") or {}).keys())
        all_uids.update(((metrics.get(w) or {}).get("series") or {}).keys())
    feats = {}
    if all_uids and not args.no_idc:
        try:
            from idc_features import features_by_uid
            feats = features_by_uid(sorted(all_uids))
        except Exception as exc:
            print(f"\n[idc] idc-index feature lookup failed ({exc}); voxels from runtime metrics only.")

    # billing $ per (workflow, task) -- task names in the export are lowercased
    bill_wf_task, bill_wf_other = {}, {}
    if billing:
        lower_tasks = {t.lower(): t for t in task_names}
        for r in billing:
            t = lower_tasks.get((r["wdlTask"] or "").lower())
            if t:
                bill_wf_task[(r["workflowId"], t)] = bill_wf_task.get((r["workflowId"], t), 0.0) + r["net"]
            else:
                bill_wf_other[r["workflowId"]] = bill_wf_other.get(r["workflowId"], 0.0) + r["net"]

    wf_rows, series_rows2 = [], []
    for wf in workflows:
        w = wf.get("workflowId")
        if not w:
            continue
        ent = ent_by_wf.get(w)
        hm = hmetrics.get(w) or {}
        lm = metrics.get(w) or {}
        rs = hm.get("run_summary") or {}
        uids = list(entity_uids.get(w) or [])
        if not uids:
            uids = list((hm.get("series") or lm.get("series") or {}).keys())
        # per-series merge: idc features + runtime metrics
        vox = slices = mb = 0.0
        n_feat = 0
        max_vox = 0
        for uid in uids:
            fe = feats.get(uid, {})
            hs = (hm.get("series") or {}).get(uid, {})
            ls = (lm.get("series") or {}).get(uid, {})
            v = fe.get("voxels") or ls.get("total_pixels")
            sl = fe.get("instanceCount") or ls.get("slices")
            size = fe.get("series_size_MB") or hs.get("download_mb") or ls.get("download_mb")
            if v:
                vox += float(v); n_feat += 1; max_vox = max(max_vox, float(v))
            if sl:
                slices += float(sl)
            if size:
                mb += float(size)
            models_s = hs.get("models_s") or ls.get("moose_models_s") or {}
            series_rows2.append({
                "workflowId": w, "entity": ent, "seriesUID": uid,
                "collection": fe.get("collection_id"), "modality": fe.get("Modality"),
                "bodyPart": fe.get("BodyPartExamined"), "manufacturer": fe.get("Manufacturer"),
                "slices": sl, "rows": fe.get("Rows") or ls.get("rows"),
                "cols": fe.get("Columns") or ls.get("cols"), "voxels": v,
                "sliceThicknessMm": fe.get("SliceThickness"),
                "pixelSpacingMm": fe.get("PixelSpacing_row_mm"),
                "sizeMb": size,
                "downloadSec": hs.get("download_s") if hs.get("download_s") is not None else ls.get("download_s"),
                "dcm2niixSec": hs.get("dcm2niix_s") if hs.get("dcm2niix_s") is not None else ls.get("dcm2niix_s"),
                "inferenceSec": hs.get("inference_s") if hs.get("inference_s") is not None else ls.get("moose_s"),
                "nModels": len(models_s) if models_s else None,
                "segSec": hs.get("seg_total_s"),
                "radiomicsSec": hs.get("radiomics_total_s"),
                "refDownloadSec": hs.get("ref_download_s"),
                "nLabels": hs.get("n_labels_total"),
                "outputConversionSec": hs.get("series_total_s"),
                "modelTimings": json.dumps(models_s) if models_s else None,
            })
        row = {
            "label": args.label or "", "submissionId": sub_id, "workflowId": w, "entity": ent,
            "status": wf.get("status"),
            "model": rs.get("model") or "",
            "radiomicsMethod": rs.get("radiomics_method") or next(
                (v.get("radiomics_method") for v in (hm.get("series") or {}).values() if v.get("radiomics_method")), ""),
            "radiomicsEnabled": rs.get("radiomics_enabled"),
            "nSeries": len(uids), "nSeriesWithFeatures": n_feat,
            "sumVoxels": int(vox), "sumSlices": int(slices), "sumSizeMb": round(mb, 1),
            "meanVoxels": int(vox / n_feat) if n_feat else None, "maxVoxels": int(max_vox) or None,
            "sumInferenceSec": round(sum((r_.get("inferenceSec") or 0) for r_ in series_rows2
                                         if r_["workflowId"] == w), 1),
            "sumOutputConversionSec": round(sum((r_.get("outputConversionSec") or 0)
                                                for r_ in series_rows2 if r_["workflowId"] == w), 1),
            "dicomSegErrors": rs.get("dicom_seg_errors"), "radiomicsErrors": rs.get("radiomics_errors"),
        }
        region = None
        total_runtime = 0.0
        for t in task_names:
            calls = [r for r in task_rows if r["workflowId"] == w and r["wdlTask"] == t]
            rt_sum = sum((c.get("runtimeMin") or 0) for c in calls)
            done = [c for c in calls if c.get("executionStatus") == "Done"]
            total_runtime += rt_sum
            region = region or _region_of(calls[0].get("zone")) if calls else region
            row[f"{t}_runtimeMin"] = round(rt_sum, 2) if calls else None
            row[f"{t}_doneRuntimeMin"] = round(done[-1].get("runtimeMin") or 0, 2) if done else None
            row[f"{t}_attempts"] = len(calls) or None
            row[f"{t}_preempted"] = (len(calls) - 1) if calls else None
            row[f"{t}_machine"] = calls[-1].get("machineType") if calls else None
            row[f"{t}_gpu"] = (f"{calls[-1].get('gpuCount')}x{calls[-1].get('gpuType')}"
                               if calls and calls[-1].get("gpuType") else None)
            row[f"{t}_docker"] = calls[-1].get("dockerImage") if calls else None
            row[f"{t}_estCost"] = round(est_by_wf.get(w, {}).get("tasks", {}).get(t, {}).get("est", 0.0), 4)
            row[f"{t}_rateHr"] = est_by_wf.get(w, {}).get("tasks", {}).get(t, {}).get("rate_hr")
            if billing:
                row[f"{t}_cost"] = round(bill_wf_task.get((w, t), 0.0), 4)
        row["region"] = region
        row["totalRuntimeMin"] = round(total_runtime, 2)
        row["terraCost"] = terra_by_wf.get(w)
        row["terraCostType"] = wf.get("costType")
        row["estCost"] = round(est_by_wf.get(w, {}).get("est", 0.0), 4)
        if billing:
            row["otherCost"] = round(bill_wf_other.get(w, 0.0), 4)
            row["totalCost"] = round(sum(v for (ww, _), v in bill_wf_task.items() if ww == w)
                                     + bill_wf_other.get(w, 0.0), 4)
            row["costSource"] = "billing"
        elif terra_by_wf.get(w) is not None and (wf.get("costType") or "").lower() == "actual":
            row["totalCost"] = terra_by_wf.get(w)
            row["costSource"] = "terra"
        else:
            row["totalCost"] = row["estCost"]
            row["costSource"] = "estimate"
        tc_ = row["totalCost"] or 0.0
        row["costPerSeries"] = round(tc_ / len(uids), 5) if uids else None
        row["costPerMvoxel"] = round(tc_ / (vox / 1e6), 5) if vox else None
        row["costPerSlice"] = round(tc_ / slices, 6) if slices else None
        wf_rows.append(row)

    if wf_rows:
        wf_path = f"{prefix}_workflows.csv"
        wcols = list(dict.fromkeys(k for r in wf_rows for k in r))
        with open(wf_path, "w", newline="") as f:
            w_ = csv.DictWriter(f, fieldnames=wcols)
            w_.writeheader(); w_.writerows(wf_rows)
        written.append(wf_path)
        if series_rows2:
            sr_path = f"{prefix}_series.csv"
            with open(sr_path, "w", newline="") as f:
                w_ = csv.DictWriter(f, fieldnames=list(series_rows2[0].keys()))
                w_.writeheader(); w_.writerows(series_rows2)
            written.append(sr_path)

        print(f"\n  Per-workflow workload vs cost ({wf_rows[0]['costSource']} $):")
        tcols = [t for t in task_names]
        hdr = (f"    {'case':>5} {'series':>6} {'Mvox':>8} {'slices':>6} "
               + " ".join(f"{t[:14]+'min':>17}" for t in tcols)
               + f" {'$total':>7} {'$/series':>8} {'$/Mvox':>8}")
        print(hdr)
        for r in sorted(wf_rows, key=lambda r: -(r["sumVoxels"] or 0)):
            print(f"    {str(r['entity']):>5} {r['nSeries']:>6} {r['sumVoxels']/1e6:>8.1f} {r['sumSlices']:>6} "
                  + " ".join(f"{(r.get(t+'_runtimeMin') or 0):>13.1f}(x{r.get(t+'_attempts') or 0})"
                             for t in tcols)
                  + f" {(r['totalCost'] or 0):>7.3f} {(r['costPerSeries'] or 0):>8.4f} "
                    f"{(r['costPerMvoxel'] or 0):>8.5f}")
        n_s = sum(r["nSeries"] for r in wf_rows)
        v_s = sum(r["sumVoxels"] for r in wf_rows) / 1e6
        c_s = sum((r["totalCost"] or 0) for r in wf_rows)
        print(f"    {'TOT':>5} {n_s:>6} {v_s:>8.1f} {'':>6} "
              + " ".join(f"{sum((r.get(t+'_runtimeMin') or 0) for r in wf_rows):>13.1f}     "
                         for t in tcols)
              + f" {c_s:>7.3f} {(c_s/n_s if n_s else 0):>8.4f} {(c_s/v_s if v_s else 0):>8.5f}")
        cfg = {k: v for k, v in wf_rows[0].items() if k.endswith("_docker") or k in
               ("model", "radiomicsMethod", "region")}
        print(f"    config: {json.dumps(cfg)}")

    print(f"\nWrote: {', '.join(written)}")


if __name__ == "__main__":
    main()
