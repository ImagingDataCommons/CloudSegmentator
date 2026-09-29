#!/usr/bin/env python3
"""Compare the radiomics output of two or more harmonized-workflow runs.

Each run is the per-series JSON output of nb3 (outputConversionNotebook.ipynb):
either a directory containing radiomics/<SeriesInstanceUID>/<model>_<i>.json
files, a radiomics.tar.lz4 archive, or a directory that holds one. Runs may come
from different radiomics engines (pyradiomics vs Radiomics.jl), different code
versions, or different submissions of the same series -- feature keys are
normalized to the canonical <class>_<snake_case> names, so legacy outputs
(original_shape_Elongation, shape3d_mesh_volume, first_order_mean, ...) compare
cleanly against current ones.

The first run is the baseline; every other run is compared against it, joined on
(SeriesInstanceUID, model, label_id).

Outputs (into --out):
  inventory.csv         metric x run: on how many labels each metric is present
  missing.csv           metrics absent from a run but present in another
  pairwise_metrics.csv  per metric, per run-vs-baseline: n compared, counts
                        within 1e-9 / 0.1% / 1%, median + max relative diff,
                        and the worst-agreeing label
  outlier_labels.csv    every (label, metric) pair >1% off baseline -- the table
                        to read when masks or engines disagree
  duplicate_values.csv  labels within one run/series sharing an identical value
                        of a normally-unique metric (the signature of the
                        Radiomics.jl multi-label thread race)
  plots/*.png           with --plots: agreement scatter per feature class,
                        ECDF of relative differences, worst-metric bars

Relative difference = |a - b| / max(|a|, |b|)  (0 when both are 0).

Usage:
  python radiomics_compare.py pyrad=submA/radiomics.tar.lz4 radjl=submB/radiomics.tar.lz4
  python radiomics_compare.py old=run1_extracted/ new=run2_extracted/ --plots
  python radiomics_compare.py a=... b=... c=... --baseline b --out cmp_abc
"""
import argparse
import io
import json
import math
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from collections import defaultdict
from pathlib import Path

import pandas as pd

META_KEYS = {"SeriesInstanceUID", "model", "radiomics_method", "label_id", "label_name"}

# ---------------------------------------------------------------------------
# Canonical feature naming (mirror of outputConversionNotebook.ipynb)
# ---------------------------------------------------------------------------
_CANON_SPECIAL = {
    "firstorder_10_percentile": "firstorder_percentile10",
    "firstorder_90_percentile": "firstorder_percentile90",
    "shape_maximum2_d_diameter_column": "shape_maximum_2d_diameter_column",
    "shape_maximum2_d_diameter_row": "shape_maximum_2d_diameter_row",
    "shape_maximum2_d_diameter_slice": "shape_maximum_2d_diameter_slice",
    "shape_maximum3_d_diameter": "shape_maximum_3d_diameter",
}


def _snake(name):
    s = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", name)
    s = re.sub(r"(?<=[A-Z])([A-Z][a-z])", r"_\1", s)
    return s.lower()


def canonical_key(key):
    """Any engine's / any vintage's feature key -> canonical name, or None if the
    key is not a feature (metadata, diagnostics)."""
    k = str(key)
    if k in META_KEYS or k.lower().startswith(("diagnosis", "diagnostics")):
        return None
    m = re.match(r"^original_([a-z]+)_(.+)$", k)   # legacy pyradiomics naming
    if m:
        cls, feat = m.group(1), m.group(2)
        if feat[:2] in ("10", "90"):
            feat = feat[:2] + "_" + feat[2:]
        cand = f"{cls}_{_snake(feat)}"
        return _CANON_SPECIAL.get(cand, cand)
    k = k.lower()
    for pre, canon in (("first_order_", "firstorder_"), ("shape3d_", "shape_")):
        if k.startswith(pre):
            k = canon + k[len(pre):]
            break
    return _CANON_SPECIAL.get(k, k)


def feature_class(canon):
    return canon.split("_", 1)[0]


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def _iter_jsons(root):
    for f in sorted(Path(root).rglob("*.json")):
        if f.name in ("run_summary.json",):
            continue
        try:
            data = json.loads(f.read_text())
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if isinstance(data, list):
            yield from (e for e in data if isinstance(e, dict) and "label_id" in e)


def _extract_archive(archive, dest):
    """radiomics.tar[.lz4] -> dest. For .lz4, prefer the python lz4 module, else the CLI."""
    if not str(archive).endswith(".lz4"):
        with tarfile.open(str(archive)) as tar:
            tar.extractall(dest)
        return
    try:
        import lz4.frame
        with lz4.frame.open(str(archive), "rb") as fh:
            with tarfile.open(fileobj=io.BytesIO(fh.read())) as tar:
                tar.extractall(dest)
        return
    except ImportError:
        pass
    if not shutil.which("lz4"):
        sys.exit(f"cannot extract {archive}: need either `pip install lz4` or the lz4 CLI")
    subprocess.run(f"lz4 -d -c {archive} | tar -xf - -C {dest}", shell=True, check=True)


def load_run(name, path, tmp_root):
    """-> {(series, model, label_id): {label_name, features{canon: float}}}"""
    p = Path(path)
    if p.is_dir() and not any(p.rglob("*_0.json")):
        for cand in ("radiomics.tar", "radiomics.tar.lz4"):
            if (p / cand).exists():
                p = p / cand
                break
    if p.is_file():
        dest = Path(tmp_root) / name
        dest.mkdir(parents=True, exist_ok=True)
        _extract_archive(p, dest)
        p = dest
    if not p.is_dir():
        sys.exit(f"run {name!r}: {path} is neither a directory nor an archive")

    rows = {}
    for e in _iter_jsons(p):
        key = (e.get("SeriesInstanceUID", ""), e.get("model", ""), int(e["label_id"]))
        feats = {}
        for k, v in e.items():
            canon = canonical_key(k)
            if canon and isinstance(v, (int, float)) and not isinstance(v, bool) \
                    and not (isinstance(v, float) and math.isnan(v)):
                feats[canon] = float(v)
        rows[key] = {"label_name": e.get("label_name", ""), "features": feats}
    if not rows:
        sys.exit(f"run {name!r}: no radiomics rows found under {path}")
    return rows


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------
def rel_diff(a, b):
    d = max(abs(a), abs(b))
    return 0.0 if d == 0 else abs(a - b) / d


def inventory(runs):
    recs = []
    for name, rows in runs.items():
        counts = defaultdict(int)
        for r in rows.values():
            for k in r["features"]:
                counts[k] += 1
        for k, n in counts.items():
            recs.append({"metric": k, "class": feature_class(k), "run": name,
                         "labels_present": n, "labels_total": len(rows)})
    df = pd.DataFrame(recs)
    pivot = df.pivot_table(index=["class", "metric"], columns="run",
                           values="labels_present", fill_value=0).astype(int)
    return pivot.reset_index()


def missing_table(inv, run_names):
    out = []
    for _, row in inv.iterrows():
        absent = [r for r in run_names if row.get(r, 0) == 0]
        if absent:
            present = [r for r in run_names if row.get(r, 0) > 0]
            out.append({"metric": row["metric"], "class": row["class"],
                        "missing_in": ",".join(absent), "present_in": ",".join(present)})
    return pd.DataFrame(out)


def pairwise(runs, baseline):
    base = runs[baseline]
    metric_rows, outliers, diffs_by_pair = [], [], defaultdict(list)
    for name, rows in runs.items():
        if name == baseline:
            continue
        common = set(base) & set(rows)
        per_metric = defaultdict(list)
        for key in common:
            bf, rf = base[key]["features"], rows[key]["features"]
            for k in set(bf) & set(rf):
                d = rel_diff(bf[k], rf[k])
                per_metric[k].append((d, key, bf[k], rf[k]))
                diffs_by_pair[name].append(d)
                if d > 0.01:
                    outliers.append({
                        "run": name, "metric": k, "SeriesInstanceUID": key[0],
                        "model": key[1], "label_id": key[2],
                        "label_name": base[key]["label_name"],
                        baseline: bf[k], name: rf[k], "rel_diff_pct": round(d * 100, 3)})
        for k, vals in per_metric.items():
            rels = sorted(v[0] for v in vals)
            worst = max(vals, key=lambda v: v[0])
            metric_rows.append({
                "metric": k, "class": feature_class(k), "run": name,
                "n": len(rels),
                "exact_1e9": sum(r < 1e-9 for r in rels),
                "within_0.1pct": sum(r < 1e-3 for r in rels),
                "within_1pct": sum(r < 1e-2 for r in rels),
                "median_rel_pct": round(rels[len(rels) // 2] * 100, 6),
                "max_rel_pct": round(worst[0] * 100, 4),
                "worst_label": base[worst[1]]["label_name"],
                "worst_series": worst[1][0][-12:],
                f"worst_{baseline}": worst[2], f"worst_{name}": worst[3]})
    metric_df = pd.DataFrame(metric_rows).sort_values(
        ["run", "max_rel_pct"], ascending=[True, False]) if metric_rows else pd.DataFrame()
    outlier_df = pd.DataFrame(outliers).sort_values(
        "rel_diff_pct", ascending=False) if outliers else pd.DataFrame()
    return metric_df, outlier_df, diffs_by_pair


# Metrics whose exact value is essentially unique per ROI; an exact duplicate
# across different labels of one series is the thread-race / copied-result smell.
_UNIQUENESS_PROBES = ("shape_voxel_volume", "shape_mesh_volume", "firstorder_energy")


def duplicate_values(runs):
    recs = []
    for name, rows in runs.items():
        per_series = defaultdict(lambda: defaultdict(list))
        for (series, model, lid), r in rows.items():
            for probe in _UNIQUENESS_PROBES:
                v = r["features"].get(probe)
                if v is not None and v != 0:
                    per_series[(series, model)][(probe, v)].append((lid, r["label_name"]))
        for (series, model), groups in per_series.items():
            for (probe, v), labels in groups.items():
                if len(labels) > 1:
                    recs.append({"run": name, "SeriesInstanceUID": series, "model": model,
                                 "metric": probe, "value": v,
                                 "labels": "; ".join(f"{lid}:{nm}" for lid, nm in labels)})
    return pd.DataFrame(recs)


# ---------------------------------------------------------------------------
# Plots (optional; requires matplotlib). Palette/chrome: the validated default
# data-viz palette (categorical slot order blue, orange, aqua, yellow; scatter
# panels stay single-hue). Light mode only -- these are static report PNGs.
# ---------------------------------------------------------------------------
_CAT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
_SURFACE, _INK, _INK2, _MUTED, _GRID, _AXIS = \
    "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"


def _style_axes(ax):
    ax.set_facecolor(_SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(_AXIS)
    ax.tick_params(colors=_MUTED, labelsize=8)
    ax.xaxis.label.set_color(_INK2)
    ax.yaxis.label.set_color(_INK2)
    ax.title.set_color(_INK)
    ax.grid(True, color=_GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def make_plots(runs, baseline, metric_df, diffs_by_pair, out_dir):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:  # broken/absent matplotlib must not sink the tables
        print(f"WARNING: plots skipped (matplotlib unavailable: {exc})")
        return
    plots = Path(out_dir) / "plots"
    plots.mkdir(parents=True, exist_ok=True)
    base = runs[baseline]
    others = [n for n in runs if n != baseline]

    # 1. agreement scatter, one panel per feature class, single hue per panel
    for name in others:
        rows = runs[name]
        by_class = defaultdict(list)
        for key in set(base) & set(rows):
            bf, rf = base[key]["features"], rows[key]["features"]
            for k in set(bf) & set(rf):
                by_class[feature_class(k)].append((bf[k], rf[k]))
        classes = sorted(by_class)
        if not classes:
            continue
        ncol = min(3, len(classes))
        nrow = -(-len(classes) // ncol)
        fig, axes = plt.subplots(nrow, ncol, figsize=(4.2 * ncol, 4.0 * nrow),
                                 facecolor=_SURFACE, squeeze=False)
        for ax in axes.ravel()[len(classes):]:
            ax.axis("off")
        for ax, cls in zip(axes.ravel(), classes):
            pts = by_class[cls]
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            _style_axes(ax)
            loglog = all(v > 0 for v in xs + ys)
            if loglog:
                ax.set_xscale("log")
                ax.set_yscale("log")
            lo = min(xs + ys)
            hi = max(xs + ys)
            ax.plot([lo, hi], [lo, hi], color=_AXIS, linewidth=1, zorder=1)
            ax.scatter(xs, ys, s=9, color=_CAT[0], alpha=0.55, linewidths=0, zorder=2)
            ax.set_title(f"{cls} ({len(pts)} values)", fontsize=10)
            ax.set_xlabel(baseline)
            ax.set_ylabel(name)
        fig.suptitle(f"Radiomics agreement: {name} vs {baseline}",
                     color=_INK, fontsize=12)
        fig.tight_layout(rect=(0, 0, 1, 0.96))
        fig.savefig(plots / f"scatter_{name}_vs_{baseline}.png", dpi=150,
                    facecolor=_SURFACE)
        plt.close(fig)

    # 2. ECDF of relative differences, one line per compared run
    fig, ax = plt.subplots(figsize=(6.4, 4.2), facecolor=_SURFACE)
    _style_axes(ax)
    for i, name in enumerate(others):
        ds = sorted(max(d, 1e-12) for d in diffs_by_pair.get(name, []))
        if not ds:
            continue
        ys = [(j + 1) / len(ds) * 100 for j in range(len(ds))]
        color = _CAT[i % len(_CAT)]
        ax.plot([d * 100 for d in ds], ys, color=color, linewidth=2,
                label=f"{name} vs {baseline}")
        ax.annotate(name, (ds[-1] * 100, ys[-1]), color=color, fontsize=8,
                    xytext=(4, -2), textcoords="offset points")
    ax.set_xscale("log")
    ax.set_xlabel("relative difference (%)  [log]")
    ax.set_ylabel("% of (label, metric) values at or below")
    if len(others) == 1:
        ax.set_title(f"Agreement ECDF: {others[0]} vs {baseline}")
    else:
        ax.set_title("Agreement ECDF")
        ax.legend(frameon=False, fontsize=8, labelcolor=_INK2)
    fig.tight_layout()
    fig.savefig(plots / "ecdf_rel_diff.png", dpi=150, facecolor=_SURFACE)
    plt.close(fig)

    # 3. worst metrics by max relative difference, per compared run
    if not metric_df.empty:
        for name in others:
            sub = metric_df[metric_df["run"] == name].nlargest(15, "max_rel_pct")
            if sub.empty:
                continue
            fig, ax = plt.subplots(figsize=(7.2, 0.34 * len(sub) + 1.4),
                                   facecolor=_SURFACE)
            _style_axes(ax)
            ax.grid(True, axis="x", color=_GRID, linewidth=0.6)
            ax.grid(False, axis="y")
            ypos = range(len(sub))[::-1]
            ax.barh(list(ypos), sub["max_rel_pct"], height=0.62, color=_CAT[0])
            ax.set_yticks(list(ypos))
            ax.set_yticklabels(sub["metric"], fontsize=8, color=_INK2)
            ax.set_xlabel("max relative difference vs baseline (%)")
            ax.set_title(f"Least-agreeing metrics: {name} vs {baseline}", fontsize=11)
            for y, v in zip(ypos, sub["max_rel_pct"]):
                ax.annotate(f"{v:.2g}", (v, y), xytext=(4, -2),
                            textcoords="offset points", fontsize=8, color=_INK2)
            fig.tight_layout()
            fig.savefig(plots / f"worst_metrics_{name}.png", dpi=150,
                        facecolor=_SURFACE)
            plt.close(fig)
    print(f"plots -> {plots}")


# ---------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("runs", nargs="+", metavar="name=path",
                    help="two or more runs: label=path (dir of per-series JSONs, "
                         "radiomics.tar.lz4, or a dir containing one)")
    ap.add_argument("--baseline", help="run name used as reference (default: first)")
    ap.add_argument("--out", default="radiomics_compare_out", help="output directory")
    ap.add_argument("--plots", action="store_true", help="also write PNG plots")
    args = ap.parse_args(argv)

    specs = []
    for spec in args.runs:
        if "=" not in spec:
            ap.error(f"run spec {spec!r} must be name=path")
        specs.append(spec.split("=", 1))
    names = [n for n, _ in specs]
    if len(set(names)) != len(names):
        ap.error("run names must be unique")
    baseline = args.baseline or names[0]
    if baseline not in names:
        ap.error(f"--baseline {baseline!r} is not one of {names}")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        runs = {name: load_run(name, path, tmp) for name, path in specs}

        for name, rows in runs.items():
            print(f"run {name}: {len(rows)} labels over "
                  f"{len({k[0] for k in rows})} series "
                  f"({'baseline' if name == baseline else 'vs ' + baseline})")

        inv = inventory(runs)
        inv.to_csv(out_dir / "inventory.csv", index=False)
        miss = missing_table(inv, names)
        miss.to_csv(out_dir / "missing.csv", index=False)
        print(f"\nmetrics: {inv['metric'].nunique()} total")
        if miss.empty:
            print("no metric is missing from any run")
        else:
            print("missing metrics:")
            print(miss.to_string(index=False))

        metric_df, outlier_df, diffs_by_pair = pairwise(runs, baseline)
        metric_df.to_csv(out_dir / "pairwise_metrics.csv", index=False)
        outlier_df.to_csv(out_dir / "outlier_labels.csv", index=False)
        if not metric_df.empty:
            print(f"\nper-metric agreement vs {baseline} (worst 10 by max rel diff):")
            cols = ["run", "metric", "n", "exact_1e9", "within_1pct",
                    "median_rel_pct", "max_rel_pct", "worst_label"]
            print(metric_df.nlargest(10, "max_rel_pct")[cols].to_string(index=False))
            print(f"\n(label, metric) pairs >1% off baseline: {len(outlier_df)}"
                  f"  -> outlier_labels.csv")

        dup = duplicate_values(runs)
        dup.to_csv(out_dir / "duplicate_values.csv", index=False)
        if not dup.empty:
            print(f"\nWARNING: {len(dup)} duplicated unique-metric values across labels "
                  f"(thread-race signature) -> duplicate_values.csv")

        if args.plots:
            make_plots(runs, baseline, metric_df, diffs_by_pair, out_dir)

    print(f"\ntables -> {out_dir}")


if __name__ == "__main__":
    main()
