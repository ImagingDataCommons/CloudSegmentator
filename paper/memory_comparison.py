# /// script
# requires-python = ">=3.11"
# dependencies = ["pandas>=2.2", "scipy"]
# ///
"""Print the numbers behind the comparison of peak memory in case studies 1 and 2,
and the check for memory carried over after a timeout. Reads only paper/data/, no
credentials:

    uv run paper/memory_comparison.py

Inputs: cs1_peak_memory and cs2_series_order (build_data_memory.py),
cs2_series_geometry (build_series_geometry_cs2.py), cs2_peak_memory and
cs2_inference_failures (build_data_cs2.py).
"""

from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).parent / "data"
BINS = [0, 10, 15, 20, 25, 30, 40, 60, 100, 1000]


def main():
    cs1 = pd.read_csv(DATA / "cs1_peak_memory.csv.gz")
    print(f"case study 1 series TotalSegmentator did not run on (time 0), left out: "
          f"{(cs1.totalsegmentator_s == 0).sum()}")
    cs1 = cs1[cs1.totalsegmentator_s > 0]
    geo = pd.read_csv(DATA / "cs2_series_geometry.csv.gz")[
        ["SeriesInstanceUID", "slices", "Rows", "mvox_native", "mvox_1p5mm", "length_mm", "fov_col_mm"]]
    order = pd.read_csv(DATA / "cs2_series_order.csv.gz")
    cs2 = pd.read_csv(DATA / "cs2_peak_memory.csv.gz")
    cs2 = (cs2[cs2.vm == "GPU"].merge(geo, on="SeriesInstanceUID", how="left")
           .merge(order[["workflow", "SeriesInstanceUID", "failures_before"]],
                  on=["workflow", "SeriesInstanceUID"], how="left"))
    cs2["after_failure"] = cs2.failures_before.fillna(0) > 0

    print("== Case study 1, peak RAM per series on the GPU VM (GiB)")
    print(cs1.groupby("cohort").peak_gib.describe(percentiles=[.5, .95, .99]).round(2).to_string())
    print(f"VM RAM seen by the notebook: {sorted(cs1.vm_ram_gib.round(2).unique())} GiB; "
          f"RAM in use at the start of each series, median {cs1.start_gib.median():.2f} GiB")
    print(f"series without geometry: {cs1.mvox_1p5mm.isna().sum()} of {len(cs1):,}")

    print("\n== Geometry, NLST (case study 1) vs case study 2: p50 / p90 / p99 / max")
    two = geo[geo.SeriesInstanceUID.isin(cs2.SeriesInstanceUID)]
    for col in ["slices", "mvox_native", "fov_col_mm", "length_mm", "mvox_1p5mm"]:
        q = lambda s: np.round(s.quantile([.5, .9, .99, 1]).values, 0)
        print(f"  {col:12s} NLST {q(cs1[col])}   case study 2 {q(two[col])}")
    print(f"  non-512 matrices: NLST {(cs1.Rows != 512).sum()}, case study 2 {(two.Rows != 512).sum()}")
    for t in (30, 40, 60, 100):
        print(f"  > {t} Mvox at 1.5 mm: NLST {(cs1.mvox_1p5mm > t).sum()} of {cs1.mvox_1p5mm.notna().sum():,}, "
              f"case study 2 {(two.mvox_1p5mm > t).sum()} of {two.mvox_1p5mm.notna().sum():,}")

    print("\n== Spearman rho of peak RAM: slices / native voxels / voxels at 1.5 mm")
    units = [("case study 1 total", cs1, "peak_gib")] + [
        (f"case study 2 {u}", cs2[(cs2.unit == u) & ~cs2.after_failure], "peak_gb")
        for u in ("total", "lung_vessels", "all models")]
    for name, d, y in units:
        d = d.dropna(subset=["mvox_1p5mm"])
        print(f"  {name:28s} n={len(d):7,d}",
              [round(d[y].corr(d[c], method="spearman"), 2) for c in ("slices", "mvox_native", "mvox_1p5mm")])

    print("\n== Peak RAM by voxels at 1.5 mm: n / median / max (GiB)."
          " Case study 2 leaves out units that ran after a failure in the same attempt")
    tab = lambda d, y: d.groupby(pd.cut(d.mvox_1p5mm, BINS), observed=False)[y].agg(
        n="count", median="median", max="max")
    ok = cs2[~cs2.after_failure]
    t = pd.concat({"cs1 total": tab(cs1, "peak_gib"),
                   "cs2 total": tab(ok[ok.unit == "total"], "peak_gb"),
                   "cs2 MOOSE": tab(ok[ok.model == "MOOSE"], "peak_gb")}, axis=1).round(1)
    print(t.to_string())
    print("ratio of medians, cs2 total / cs1 total:",
          (t[("cs2 total", "median")] / t[("cs1 total", "median")]).dropna().round(2).tolist())

    print("\n== Memory carried over after a failure (case study 2)")
    print(f"attempts read: {order.workflow.nunique()}; series that ran after a failure: "
          f"{(order.failures_before > 0).sum()} in {order[order.failures_before > 0].workflow.nunique()} attempts")
    for name, d, x in [("TotalSegmentator total", cs2[cs2.unit == "total"], "mvox_1p5mm"),
                       ("TotalSegmentator lung_vessels", cs2[cs2.unit == "lung_vessels"], "mvox_native"),
                       ("MOOSE", cs2[cs2.model == "MOOSE"], "mvox_1p5mm")]:
        d = d.dropna(subset=[x]).copy()
        b, a = np.polyfit(d[~d.after_failure][x], d[~d.after_failure].peak_gb, 1)
        d["excess"] = d.peak_gb - (a + b * d[x])
        print(f"  {name:30s} units after a failure {d.after_failure.sum():3d}; "
              f"peak above the {x} fit, median {d[d.after_failure].excess.median():+.1f} GiB "
              f"(others {d[~d.after_failure].excess.median():+.1f}); "
              f">13 GiB {(d.peak_gb > 13).sum()} ({(d.after_failure & (d.peak_gb > 13)).sum()} after a failure), "
              f">16 GiB {(d.peak_gb > 16).sum()} ({(d.after_failure & (d.peak_gb > 16)).sum()})")
    ts = order[order.model == "TotalSegmentator"]
    fl = pd.read_csv(DATA / "cs2_inference_failures.csv.gz")
    fl = fl[(fl.model == "TotalSegmentator") & fl.cause.isin(
        ["killed (signal 9)", "timed out (90 min cap)", "export worker killed (RAM)"])]
    f = fl.merge(ts, on=["workflow", "SeriesInstanceUID"])
    print(f"  TotalSegmentator memory failures on a series that ran after an earlier failure: "
          f"{(f.failures_before > 0).sum()} of {len(f)}")

    print("\n  TotalSegmentator tasks after a failure, by the attempt's first failure:"
          " GiB above the size fit")
    first = f.sort_values("position").groupby("workflow").first().cause
    for unit, x in (("total", "mvox_1p5mm"), ("lung_vessels", "mvox_native")):
        d = cs2[cs2.unit == unit].dropna(subset=[x]).copy()
        b, a = np.polyfit(d[~d.after_failure][x], d[~d.after_failure].peak_gb, 1)
        d["excess"] = d.peak_gb - (a + b * d[x])
        d = d[d.after_failure].assign(first_failure=lambda e: e.workflow.map(first))
        print(d.groupby("first_failure").agg(tasks=("excess", "size"), attempts=("workflow", "nunique"),
                                             median=("excess", "median"), min=("excess", "min"),
                                             max=("excess", "max")).round(1).to_string())
    both = pd.concat([cs2[(cs2.unit == u) & cs2.after_failure].assign(
        first_failure=lambda e: e.workflow.map(first)) for u in ("total", "lung_vessels")])
    print("  both tasks, after a timeout:", (both.first_failure == "timed out (90 min cap)").sum(),
          "tasks in", both[both.first_failure == "timed out (90 min cap)"].workflow.nunique(), "attempts")

    print("\n== lung_vessels by native Mvox (n / median / max GiB), units not after a failure;"
          " NLST series in each bin")
    lv = ok[ok.unit == "lung_vessels"]
    nb = [0, 50, 100, 150, 210, 300, 700]
    t = lv.groupby(pd.cut(lv.mvox_native, nb), observed=False).peak_gb.agg(["count", "median", "max"]).round(1)
    t["NLST"] = pd.cut(cs1.mvox_native, nb).value_counts()
    print(t.to_string())


if __name__ == "__main__":
    main()
