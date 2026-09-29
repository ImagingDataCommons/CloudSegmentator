#!/usr/bin/env python3
"""Per-region GCP price tables for the CloudSegmentator task shapes.

Rebuilt on the Cloud Billing Catalog API (``services/6F81-5844-456A/skus`` =
Compute Engine), the same source ``util/pricingOptimization/Top_20_cheapest_GPUs.ipynb``
uses; the SKU-matching helpers here are lifted from that notebook so both agree.

Two uses:

  1. Rank regions for the harmonized ``Segmentator`` workflow (GPU inference VM +
     CPU output-conversion VM) and pick the cheapest one to run in::

         python region_prices.py rank                     # WDL default shapes
         python region_prices.py rank --weights inference=0.85,outputConversion=0.15
         python region_prices.py rank --out region_rates.json

  2. Produce a *rate table* (``region_rates.json``) that ``submission_cost.py`` and
     ``cost_model.py`` use to convert measured task wall-clock into dollars for any
     region -- so a cost model fitted on time in one region can be re-priced for another.

Shapes default to the ``twoVM.wdl`` runtime defaults; override with ``--shapes shapes.json``
(same structure as ``DEFAULT_SHAPES`` below).

Notes
  * Spot *prices* are per region and come from the catalog; spot *preemption rates* do
    not. Preemption/retry overhead has to be measured (``cost_model.py`` fits it from
    the pilot's attempt counts).
  * The catalog needs an OAuth token: ``gcloud auth login`` first (``gcloud auth
    print-access-token`` is used, like ``submission_cost.py``).
  * GPU availability per zone is looked up with ``gcloud compute accelerator-types
    list`` when a ``--gpu-project`` is given (or the gcloud default project works);
    otherwise it is skipped and only priced regions are listed.
"""
import argparse
import json
import re
import subprocess
import sys
import urllib.request

COMPUTE_SERVICE = "6F81-5844-456A"  # Compute Engine, from cloudbilling services.list

# machine family -> (vCPU SKU description, RAM SKU description) for the *predefined* type.
FAMILY_SKU = {
    "N1":  ("N1 Predefined Instance Core", "N1 Predefined Instance Ram"),
    # Cromwell/PAPI/Batch build *custom* N1 machine types (custom-4-16384) from the WDL
    # cpu/memory, billed as "Custom Instance Core/Ram" (see the billing export SKUs).
    "N1_CUSTOM": ("Custom Instance Core", "Custom Instance Ram"),
    "N2D_CUSTOM": ("N2D AMD Custom Instance Core", "N2D AMD Custom Instance Ram"),
    "N2":  ("N2 Instance Core", "N2 Instance Ram"),
    "N2D": ("N2D AMD Instance Core", "N2D AMD Instance Ram"),
    "E2":  ("E2 Instance Core", "E2 Instance Ram"),
    "C2":  ("Compute optimized Core", "Compute optimized Ram"),
    "C2D": ("C2D AMD Instance Core", "C2D AMD Instance Ram"),
    "C3":  ("C3 Instance Core", "C3 Instance Ram"),
    "N4":  ("N4 Instance Core", "N4 Instance Ram"),
    "G2":  ("G2 Instance Core", "G2 Instance Ram"),
}
# Description fragments that mark non-standard SKU variants we never price on.
_EXCLUDE = re.compile(r"Commitment|Reserved|DWS|Calendar|Sole Tenancy|Premium|vGPU")

# Persistent-disk SKU descriptions ($/GB/month in the catalog).
DISK_SKU = {"HDD": "Storage PD Capacity", "SSD": "SSD backed PD Capacity",
            "BALANCED": "Balanced PD Capacity"}
HOURS_PER_MONTH = 730.0

# WDL runtime defaults from workflows/harmonized/Terra/twoVM.wdl. Cromwell/PAPI boot
# disks are Balanced PD by default (see the "Balanced PD Capacity" SKU in the billing
# export of the legacy runs), so bootDiskGb is priced as BALANCED.
DEFAULT_SHAPES = {
    "inference": {"family": "N1_CUSTOM", "vcpu": 4, "ram_gb": 16, "gpu": "T4", "gpu_count": 1,
                  "disk_gb": 50, "disk_type": "HDD", "boot_disk_gb": 30},
    "outputConversion": {"family": "N2D", "vcpu": 4, "ram_gb": 16, "gpu": None, "gpu_count": 0,
                         "disk_gb": 20, "disk_type": "HDD", "boot_disk_gb": 30},
}
# Regions offering T4 GPUs per https://cloud.google.com/compute/docs/gpus/gpu-regions-zones
# (snapshot 2026-08; used only when `gcloud compute accelerator-types list` is not
# available -- pass --gpu-project to get the live list, or --gpu-regions to override).
T4_REGIONS_STATIC = [
    "asia-east1", "asia-east2", "asia-northeast1", "asia-northeast3", "asia-south1",
    "asia-southeast1", "asia-southeast2", "australia-southeast1", "europe-central2",
    "europe-west1", "europe-west2", "europe-west3", "europe-west4", "me-west1",
    "northamerica-northeast1", "southamerica-east1", "us-central1", "us-east1", "us-east4",
    "us-west1", "us-west2", "us-west4",
]

# Approximate GCS -> VM data-transfer $/GB by destination continent, for data that lives
# in US buckets (IDC public data + Terra workspace buckets). Intra-US transfer to a US
# region billed ~0 in the legacy runs (see submission_6e801668_billing.csv "Egress");
# cross-continent GCS egress is list-priced. Approximate -- override with --egress-rates.
EGRESS_FROM_US_PER_GB = {"us": 0.0, "northamerica": 0.01, "southamerica": 0.08,
                         "europe": 0.02, "asia": 0.08, "australia": 0.08, "me": 0.08,
                         "africa": 0.08}


def egress_rate(region, table=EGRESS_FROM_US_PER_GB):
    return table.get(region.split("-", 1)[0], 0.08)


# WDL gpuType -> catalog GPU model name.
GPU_TYPE_TO_MODEL = {"nvidia-tesla-t4": "T4", "nvidia-tesla-p100": "P100",
                     "nvidia-tesla-p4": "P4", "nvidia-tesla-v100": "V100", "nvidia-l4": "L4"}
GPU_MODEL_TO_TYPE = {v: k for k, v in GPU_TYPE_TO_MODEL.items()}


def get_token():
    out = subprocess.run("gcloud auth print-access-token", shell=True,
                         capture_output=True, text=True)
    tok = out.stdout.strip()
    if not tok:
        sys.exit("No access token. Run `gcloud auth login` first.\n" + out.stderr)
    return tok


def fetch_skus(service=COMPUTE_SERVICE, token=None):
    """Every SKU for a Cloud Billing service, following pagination (~31k for Compute)."""
    token = token or get_token()
    base = f"https://cloudbilling.googleapis.com/v1/services/{service}/skus?pageSize=5000"
    skus, page = [], None
    while True:
        url = base + (f"&pageToken={page}" if page else "")
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        d = json.load(urllib.request.urlopen(req))
        skus += d.get("skus", [])
        page = d.get("nextPageToken")
        if not page:
            break
    return skus


def _price(s):
    """$/unit from a SKU's last pricing tier (units + nanos)."""
    r = s["pricingInfo"][0]["pricingExpression"]["tieredRates"][-1]["unitPrice"]
    return int(r.get("units", 0)) + r.get("nanos", 0) / 1e9


def _by_region(skus, want_desc, usage):
    """{region: min $/unit/hr} for the core/ram SKU matching `want_desc` (Spot prefix stripped)."""
    out = {}
    for s in skus:
        c = s.get("category", {})
        if c.get("usageType") != usage or _EXCLUDE.search(s["description"]):
            continue
        desc = re.sub(r"^(Spot )?Preemptible ", "", s["description"].split(" running")[0])
        if desc != want_desc:
            continue
        for reg in s["serviceRegions"]:
            out[reg] = min(out.get(reg, 1e9), _price(s))
    return out


def _gpu_by_region(skus, model, usage):
    """{region: min $/GPU/hr} for a bare Nvidia <model> GPU (excludes bundled/DWS variants)."""
    pat = re.compile(rf"Nvidia (Tesla )?{re.escape(model)} GPU")
    out = {}
    for s in skus:
        c = s.get("category", {})
        if c.get("resourceGroup") != "GPU" or c.get("usageType") != usage:
            continue
        if _EXCLUDE.search(s["description"]) or "attached to DWS" in s["description"]:
            continue
        if not pat.search(s["description"]):
            continue
        for reg in s["serviceRegions"]:
            out[reg] = min(out.get(reg, 1e9), _price(s))
    return out


def _disk_by_region(skus, disk_type):
    """{region: $/GB/hour} for a persistent-disk type (catalog is $/GB/month; PD is never Spot)."""
    want = DISK_SKU[disk_type.upper()]
    out = {}
    for s in skus:
        if _EXCLUDE.search(s["description"]) or "Regional" in s["description"] or "Snapshot" in s["description"]:
            continue
        if not s["description"].startswith(want):
            continue
        for reg in s["serviceRegions"]:
            out[reg] = min(out.get(reg, 1e9), _price(s) / HOURS_PER_MONTH)
    return out


def rate_tables(skus, shapes, spot=True):
    """{shape_name: {region: {gpu_hr, vcpu_hr, ram_hr, disk_hr, total_hr}}} for every
    region where all of the shape's components are priced. Rates are $/hour for the
    whole VM shape (vcpu_hr already multiplied by vCPU count, etc.)."""
    usage = "Preemptible" if spot else "OnDemand"
    out = {}
    for name, sh in shapes.items():
        core_d, ram_d = FAMILY_SKU[sh["family"]]
        cpu_p, ram_p = _by_region(skus, core_d, usage), _by_region(skus, ram_d, usage)
        gpu_p = _gpu_by_region(skus, sh["gpu"], usage) if sh.get("gpu") else None
        disk_p = _disk_by_region(skus, sh.get("disk_type", "HDD"))
        boot_p = _disk_by_region(skus, "BALANCED")
        regions = set(cpu_p) & set(ram_p)
        if gpu_p is not None:
            regions &= set(gpu_p)
        table = {}
        for reg in sorted(regions):
            gpu_hr = (gpu_p[reg] * sh.get("gpu_count", 1)) if gpu_p is not None else 0.0
            vcpu_hr = cpu_p[reg] * sh["vcpu"]
            ram_hr = ram_p[reg] * sh["ram_gb"]
            disk_hr = (disk_p.get(reg, 0.0) * sh.get("disk_gb", 0)
                       + boot_p.get(reg, 0.0) * sh.get("boot_disk_gb", 0))
            table[reg] = {"gpu_hr": round(gpu_hr, 6), "vcpu_hr": round(vcpu_hr, 6),
                          "ram_hr": round(ram_hr, 6), "disk_hr": round(disk_hr, 6),
                          "total_hr": round(gpu_hr + vcpu_hr + ram_hr + disk_hr, 6)}
        out[name] = table
    return out


def gpu_zones(gpu_type, project=None):
    """{region: [zones]} where `gpu_type` (e.g. nvidia-tesla-t4) is offered, via gcloud.
    Returns None if gcloud/compute API is unavailable."""
    cmd = (f'gcloud compute accelerator-types list --filter="name={gpu_type}" '
           f'--format="value(zone)"' + (f" --project={project}" if project else ""))
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if res.returncode != 0:
        return None
    zones = sorted({z.strip().split("/")[-1] for z in res.stdout.splitlines() if z.strip()})
    out = {}
    for z in zones:
        out.setdefault(z.rsplit("-", 1)[0], []).append(z)
    return out


def rank_regions(tables, weights, zones_by_region=None, min_zones=1,
                 data_gb_per_hour=0.0, region_prefix=None, egress_table=None):
    """Sort regions by the weighted sum of shape $/h (+ approximate data-transfer $/h).
    `weights` maps shape name -> share of run time (need not sum to 1);
    `data_gb_per_hour` = GB pulled from US buckets per weighted hour. Regions missing
    any weighted shape are dropped."""
    names = [n for n in weights if n in tables]
    regions = set.intersection(*(set(tables[n]) for n in names)) if names else set()
    rows = []
    for reg in regions:
        if region_prefix and not reg.startswith(region_prefix):
            continue
        if zones_by_region is not None:
            zs = zones_by_region.get(reg, [])
            if len(zs) < min_zones:
                continue
        else:
            zs = None
        w = sum(weights[n] * tables[n][reg]["total_hr"] for n in names)
        eg = data_gb_per_hour * egress_rate(reg, egress_table or EGRESS_FROM_US_PER_GB)
        row = {"region": reg, "weighted_hr": round(w + eg, 6), "compute_hr": round(w, 6),
               "egress_hr": round(eg, 6)}
        for n in names:
            row[f"{n}_hr"] = tables[n][reg]["total_hr"]
        row["gpu_zones"] = zs
        rows.append(row)
    return sorted(rows, key=lambda r: r["weighted_hr"])


def load_rates(path):
    with open(path) as f:
        return json.load(f)


def shape_from_runtime(family, vcpu, ram_gb, gpu_type=None, gpu_count=0,
                       disk_gb=0, disk_type="HDD", boot_disk_gb=30):
    """Build a shape dict from Cromwell runtime attributes (used by submission_cost.py)."""
    return {"family": family, "vcpu": vcpu, "ram_gb": ram_gb,
            "gpu": GPU_TYPE_TO_MODEL.get(gpu_type) if gpu_type else None,
            "gpu_count": gpu_count if gpu_type else 0,
            "disk_gb": disk_gb, "disk_type": disk_type, "boot_disk_gb": boot_disk_gb}


def _parse_weights(s):
    if not s:
        return {"inference": 0.8, "outputConversion": 0.2}
    out = {}
    for part in s.split(","):
        k, v = part.split("=")
        out[k.strip()] = float(v)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("rank", help="rank regions by weighted $/h of the workflow's task shapes")
    r.add_argument("--shapes", help="JSON file: {shapeName: {family,vcpu,ram_gb,gpu,...}}")
    r.add_argument("--weights", help="share of wall-clock per shape, e.g. inference=0.8,outputConversion=0.2")
    r.add_argument("--on-demand", action="store_true", help="price on-demand instead of Spot")
    r.add_argument("--gpu-project", help="GCP project for accelerator-types list (zone availability)")
    r.add_argument("--no-zones", action="store_true", help="skip the GPU availability filter entirely")
    r.add_argument("--gpu-regions", help="comma-separated regions that offer the GPU (overrides gcloud/static list)")
    r.add_argument("--min-zones", type=int, default=3, help="require N GPU zones (default 3)")
    r.add_argument("--data-gb-per-hour", type=float, default=0.6,
                   help="GB downloaded from US buckets per weighted VM-hour, for the approximate "
                        "cross-continent transfer adder (default 0.6 ~ legacy MOOSE runs; 0 to ignore)")
    r.add_argument("--region-prefix", help="only consider regions starting with this, e.g. us-")
    r.add_argument("--top", type=int, default=15)
    r.add_argument("--out", help="write region_rates.json (all regions, all shapes) here")
    args = ap.parse_args()

    shapes = DEFAULT_SHAPES
    if args.shapes:
        with open(args.shapes) as f:
            shapes = json.load(f)
    weights = _parse_weights(args.weights)
    spot = not args.on_demand

    print("Fetching Compute Engine SKUs from the Cloud Billing Catalog ...", file=sys.stderr)
    skus = fetch_skus()
    print(f"  {len(skus)} SKUs", file=sys.stderr)
    tables = rate_tables(skus, shapes, spot=spot)

    zones = None
    min_zones = 1
    gpu_shape = next((s for s in shapes.values() if s.get("gpu")), None)
    if gpu_shape and not args.no_zones:
        if args.gpu_regions:
            zones = {r.strip(): ["?"] for r in args.gpu_regions.split(",") if r.strip()}
        else:
            zones = gpu_zones(GPU_MODEL_TO_TYPE.get(gpu_shape["gpu"], "nvidia-tesla-t4"),
                              args.gpu_project)
            if zones is not None:
                min_zones = args.min_zones
            elif gpu_shape["gpu"] == "T4":
                print("  (gcloud accelerator-types lookup unavailable; filtering to the static "
                      "T4 region list -- pass --gpu-project for a live check)", file=sys.stderr)
                zones = {r: ["?"] for r in T4_REGIONS_STATIC}
            else:
                print("  (GPU zone lookup via gcloud failed; ranking without availability filter)",
                      file=sys.stderr)

    ranked = rank_regions(tables, weights, zones, min_zones,
                          data_gb_per_hour=args.data_gb_per_hour, region_prefix=args.region_prefix)
    tier = "Spot" if spot else "On-demand"
    print(f"\n{tier} $/hour by region (weights: {weights}); shapes:")
    for n, s in shapes.items():
        gpu = f"{s.get('gpu_count', 0)}x{s['gpu']}" if s.get("gpu") else "-"
        print(f"  {n:<18} {s['family']} {s['vcpu']}vCPU/{s['ram_gb']}GB gpu={gpu} "
              f"disk={s.get('disk_gb', 0)}{s.get('disk_type', 'HDD')}"
              f"+{s.get('boot_disk_gb', 0)}boot")
    names = [n for n in weights if n in tables]
    hdr = (f"  {'region':<24} {'total$/h':>9} {'compute':>8} {'xfer':>7} "
           + " ".join(f"{n[:16]+'$/h':>18}" for n in names) + "  gpu zones")
    print(hdr)
    for row in ranked[:args.top]:
        zs = (",".join(z.rsplit("-", 1)[1] for z in row["gpu_zones"])
              if row["gpu_zones"] and row["gpu_zones"] != ["?"] else "?")
        line = (f"  {row['region']:<24} {row['weighted_hr']:>9.4f} {row['compute_hr']:>8.4f} "
                f"{row['egress_hr']:>7.4f} "
                + " ".join(f"{row[f'{n}_hr']:>18.4f}" for n in names)
                + f"  {zs}")
        print(line)
    print(f"  (xfer = {args.data_gb_per_hour} GB/h x approx GCS US->continent $/GB; "
          f"spot prices are the catalog's current values and change over time)")
    if ranked:
        best = ranked[0]["region"]
        print(f"\nCheapest: {best}")
        print(f'  Segmentator.inferenceZones        = '
              f'"{best}-a {best}-b {best}-c"   (verify zones above)')
        print(f'  Segmentator.outputConversionZones = '
              f'"{best}-a {best}-b {best}-c"')

    if args.out:
        payload = {"tier": "spot" if spot else "ondemand", "shapes": shapes, "rates": tables,
                   "gpu_zones": zones, "ranking": ranked}
        with open(args.out, "w") as f:
            json.dump(payload, f, indent=1)
        print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
