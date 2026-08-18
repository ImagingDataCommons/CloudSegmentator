#!/usr/bin/env python3
"""Fit a per-task cost/time model on a pilot run, predict a larger run, evaluate it, plot.

Inputs are the ``submission_<id>_workflows.csv`` / ``_series.csv`` tables written by
``submission_cost.py`` (one or more may be given -- they are concatenated), a Terra data
table TSV for prediction, and a ``region_rates.json`` from ``region_prices.py`` for
re-pricing.

Model (per WDL task k, per workflow w)::

    time_k(w)  = a_k + b_k * nSeries(w) + c_k * Mvoxels(w)          [minutes, incl. retries]
    cost_k(w)  = a'_k + b'_k * nSeries(w) + c'_k * Mvoxels(w)       [$, billing export]

both fitted by OLS on the pilot; the $ model is calibrated to what was actually billed
(so VM boot / queue time, disk, egress, IP charges are absorbed into the coefficients).
When predicting for a *different region*, cost is scaled by
``rate(target)/rate(pilot)`` per task from the rate file (compute rates are the only
region-dependent piece; time is region-independent). Predictions carry a 95 % interval
from the OLS residuals + coefficient covariance.

Subcommands
  fit       --workflows W.csv [W2.csv ...] [--series S.csv ...] --out model.json
  predict   --model model.json (--manifest table.tsv | --workflows W.csv)
            [--rates region_rates.json --region us-west4] --out predicted.csv
  evaluate  --predicted predicted.csv --actual W.csv [--out evaluation.csv] [--plots DIR]
  report    --workflows W.csv [...] [--series S.csv ...] [--billing B.csv ...]
            [--model model.json] --plots DIR      # metrics + figures (cost vs series/voxels...)

Only numpy/pandas are required; matplotlib is optional (plots are skipped without it).
"""
import argparse
import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

Z95 = 1.96
FEATURES = ["nSeries", "Mvox"]          # predictors; Mvox = sumVoxels / 1e6
EXCLUDE_TASK_TOKENS = ()                 # all tasks are modelled


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def load_tables(paths):
    if not paths:
        return pd.DataFrame()
    frames = []
    for p in paths:
        df = pd.read_csv(p, dtype={"entity": str, "seriesUID": str, "workflowId": str})
        df["_source"] = Path(p).name
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def task_names(df):
    return [c[:-len("_runtimeMin")] for c in df.columns
            if c.endswith("_runtimeMin") and not c.endswith("_doneRuntimeMin")]


def prep_features(df):
    df = df.copy()
    df["Mvox"] = pd.to_numeric(df["sumVoxels"], errors="coerce").fillna(0) / 1e6
    df["nSeries"] = pd.to_numeric(df["nSeries"], errors="coerce").fillna(0)
    return df


def ols(X, y):
    """Least squares with intercept handling done by the caller (X already has a 1 column).
    Returns dict(coef, resid_sd, r2, n, p, XtX_inv)."""
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    n, p = X.shape
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    yhat = X @ coef
    resid = y - yhat
    dof = max(n - p, 1)
    sd = float(np.sqrt((resid ** 2).sum() / dof))
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - float((resid ** 2).sum()) / ss_tot if ss_tot > 0 else float("nan")
    try:
        xtx_inv = np.linalg.pinv(X.T @ X)
    except np.linalg.LinAlgError:
        xtx_inv = np.zeros((p, p))
    return {"coef": coef.tolist(), "resid_sd": sd, "r2": r2, "n": int(n), "p": int(p),
            "XtX_inv": xtx_inv.tolist(), "dof": int(dof)}


def design(df, cols):
    X = np.ones((len(df), 1 + len(cols)))
    for j, c in enumerate(cols):
        X[:, j + 1] = df[c].to_numpy(float)
    return X


def fit_reduced(df, y):
    """Fit y ~ 1 + nSeries + Mvox, falling back to fewer predictors when the pilot is
    too small or the design is degenerate. Returns (fit, cols)."""
    y = np.asarray(y, float)
    mask = np.isfinite(y)
    df = df[mask]
    y = y[mask]
    candidates = [FEATURES, ["Mvox"], ["nSeries"], []]
    for cols in candidates:
        if len(df) < len(cols) + 2 and cols:
            continue
        X = design(df, cols)
        if np.linalg.matrix_rank(X) < X.shape[1]:
            continue
        f = ols(X, y)
        f["cols"] = cols
        return f
    f = ols(np.ones((max(len(df), 1), 1)), y if len(y) else np.zeros(1))
    f["cols"] = []
    return f


def predict_with(fit, df):
    """Point prediction and per-row prediction SD (residual + coefficient uncertainty)."""
    X = design(df, fit["cols"])
    coef = np.asarray(fit["coef"], float)
    xtx = np.asarray(fit["XtX_inv"], float)
    yhat = X @ coef
    sd = fit["resid_sd"]
    lev = np.einsum("ij,jk,ik->i", X, xtx, X)
    se = sd * np.sqrt(1 + lev)
    # variance of the *sum* over rows: sd^2 * n + sd^2 * (sum x)' XtX_inv (sum x)
    xs = X.sum(axis=0)
    var_sum = sd ** 2 * len(df) + sd ** 2 * float(xs @ xtx @ xs)
    return yhat, se, math.sqrt(max(var_sum, 0))


def fmt_eq(fit, unit):
    terms = [f"{fit['coef'][0]:.4g}"]
    for c, b in zip(fit["cols"], fit["coef"][1:]):
        terms.append(f"{b:+.4g}*{c}")
    return f"{' '.join(terms)}  [{unit}; n={fit['n']}, R2={fit['r2']:.2f}, sd={fit['resid_sd']:.3g}]"


def _cfg(df, tasks):
    """Run configuration that a prediction is only valid for."""
    cfg = {}
    for c in ["model", "radiomicsMethod", "radiomicsEnabled", "region"]:
        if c in df.columns:
            vals = sorted({str(v) for v in df[c].dropna().unique()})
            if vals:
                cfg[c] = vals[0] if len(vals) == 1 else vals
    for t in tasks:
        for suffix in ("_docker", "_machine", "_gpu"):
            c = f"{t}{suffix}"
            if c in df.columns:
                vals = sorted({str(v) for v in df[c].dropna().unique()})
                if vals:
                    cfg[c] = vals[0] if len(vals) == 1 else vals
    return cfg


# ---------------------------------------------------------------------------
# fit
# ---------------------------------------------------------------------------
def cmd_fit(args):
    wf = prep_features(load_tables(args.workflows))
    if "status" in wf.columns and not args.keep_failed:
        ok = wf["status"].astype(str).str.lower().isin(["succeeded", "done"])
        if (~ok).any():
            print(f"[fit] dropping {(~ok).sum()} non-succeeded workflow(s) (use --keep-failed to keep)")
        wf = wf[ok]
    tasks = task_names(wf)
    if not tasks:
        sys.exit("No <task>_runtimeMin columns found in the workflows CSV.")
    print(f"Fitting on {len(wf)} workflows, {int(wf['nSeries'].sum())} series, "
          f"{wf['Mvox'].sum():.0f} Mvox; tasks: {tasks}")
    print(f"  nSeries range {wf['nSeries'].min():.0f}-{wf['nSeries'].max():.0f}, "
          f"Mvox/workflow range {wf['Mvox'].min():.0f}-{wf['Mvox'].max():.0f}")
    # design diagnostics: both predictors need spread, and must not move together
    for c in FEATURES:
        cv = wf[c].std() / wf[c].mean() if wf[c].mean() else 0
        if len(wf) > 2 and cv < 0.15:
            print(f"  WARNING: {c} varies little across the pilot (CV={cv:.2f}); its coefficient "
                  f"will be poorly identified. Vary batch sizes / series sizes in the pilot manifest.")
    if len(wf) > 2 and wf["nSeries"].std() > 0 and wf["Mvox"].std() > 0:
        r = float(np.corrcoef(wf["nSeries"], wf["Mvox"])[0, 1])
        if abs(r) > 0.9:
            print(f"  WARNING: nSeries and Mvox are nearly collinear in the pilot (r={r:.2f}); "
                  f"per-series vs per-voxel effects cannot be separated.")
    cost_source = sorted(wf["costSource"].dropna().unique()) if "costSource" in wf else []
    if cost_source and cost_source != ["billing"]:
        print(f"  WARNING: cost source is {cost_source}, not the billing export -- $ fit is "
              f"against Terra-reported/estimated cost")

    model = {"tasks": {}, "config": _cfg(wf, tasks), "features": FEATURES,
             "cost_source": cost_source,
             "pilot": {"n_workflows": int(len(wf)), "n_series": int(wf["nSeries"].sum()),
                       "Mvox": float(wf["Mvox"].sum()),
                       "nSeries_range": [float(wf["nSeries"].min()), float(wf["nSeries"].max())],
                       "Mvox_range": [float(wf["Mvox"].min()), float(wf["Mvox"].max())],
                       "sources": sorted(wf["_source"].unique().tolist()),
                       "labels": sorted({str(x) for x in wf.get("label", pd.Series(dtype=str)).dropna().unique()})}}
    total_cost = 0.0
    for t in tasks:
        tm = {}
        rt = pd.to_numeric(wf[f"{t}_runtimeMin"], errors="coerce")
        tm["time"] = fit_reduced(wf, rt)
        print(f"\n  {t}")
        print(f"    time : {fmt_eq(tm['time'], 'min')}")
        done_col = f"{t}_doneRuntimeMin"
        if done_col in wf.columns:
            done = pd.to_numeric(wf[done_col], errors="coerce")
            if done.notna().any() and done.sum() > 0:
                tm["preempt_overhead"] = float(rt.sum() / done.sum() - 1)
                tm["time_done"] = fit_reduced(wf, done)
                print(f"    successful-attempt time: {fmt_eq(tm['time_done'], 'min')}")
                print(f"    preemption/retry overhead: {100 * tm['preempt_overhead']:.1f}% "
                      f"(attempts: {pd.to_numeric(wf[f'{t}_attempts'], errors='coerce').sum():.0f} "
                      f"for {len(wf)} workflows)")
        cost_col = f"{t}_cost" if f"{t}_cost" in wf.columns else f"{t}_estCost"
        cost = pd.to_numeric(wf[cost_col], errors="coerce")
        tm["cost_col"] = cost_col
        tm["cost"] = fit_reduced(wf, cost)
        hours = rt.sum() / 60.0
        tm["eff_rate_hr"] = float(cost.sum() / hours) if hours else None
        rate_col = f"{t}_rateHr"
        if rate_col in wf.columns and wf[rate_col].notna().any():
            tm["catalog_rate_hr"] = float(pd.to_numeric(wf[rate_col], errors="coerce").mean())
        tm["region"] = model["config"].get("region")
        total_cost += float(cost.sum())
        print(f"    cost : {fmt_eq(tm['cost'], '$')}   [{cost_col}]")
        print(f"    effective billed rate ${tm['eff_rate_hr']:.4f}/h vs catalog "
              f"${tm.get('catalog_rate_hr') or float('nan'):.4f}/h  "
              f"(ratio {((tm['eff_rate_hr'] or 0) / tm['catalog_rate_hr']) if tm.get('catalog_rate_hr') else float('nan'):.2f})")
        model["tasks"][t] = tm

    other_col = "otherCost"
    if other_col in wf.columns:
        oc = pd.to_numeric(wf[other_col], errors="coerce").fillna(0)
        model["other_cost_per_workflow"] = float(oc.mean())
        total_cost += float(oc.sum())
    else:
        model["other_cost_per_workflow"] = 0.0
    model["pilot"]["total_cost"] = total_cost
    model["pilot"]["cost_per_series"] = total_cost / max(int(wf["nSeries"].sum()), 1)
    model["pilot"]["cost_per_Mvox"] = total_cost / max(float(wf["Mvox"].sum()), 1e-9)

    # per-series cross-check on the notebook timings
    if args.series:
        se = load_tables(args.series)
        se["Mvox"] = pd.to_numeric(se["voxels"], errors="coerce") / 1e6
        model["per_series"] = {}
        for col, label in [("inferenceSec", "inference s"), ("outputConversionSec", "outputConversion s"),
                           ("downloadSec", "download s"), ("dcm2niixSec", "dcm2niix s"),
                           ("refDownloadSec", "ref-DICOM download s"), ("segSec", "SEG s"),
                           ("radiomicsSec", "radiomics s")]:
            if col in se.columns and se[col].notna().sum() >= 3:
                sub = se[se[col].notna() & se["Mvox"].notna()]
                f = ols(design(sub, ["Mvox"]), sub[col].to_numpy(float))
                f["cols"] = ["Mvox"]
                model["per_series"][col] = f
                print(f"  per-series {label:<20}: {fmt_eq(f, 's')}  "
                      f"(median {sub[col].median():.1f}s, {len(sub)} series)")
        if "sizeMb" in se.columns and "downloadSec" in se.columns and se["downloadSec"].notna().sum() >= 3:
            sub = se[se["downloadSec"].notna() & se["sizeMb"].notna()]
            mbps = (sub["sizeMb"] / sub["downloadSec"].replace(0, np.nan)).median()
            model["per_series"]["download_MBps_median"] = float(mbps)
            print(f"  median download throughput: {mbps:.1f} MB/s")

    with open(args.out, "w") as f:
        json.dump(model, f, indent=1)
    print(f"\n  pilot total ${total_cost:.3f}  = ${model['pilot']['cost_per_series']:.4f}/series, "
          f"${model['pilot']['cost_per_Mvox']:.5f}/Mvox")
    print(f"  config: {json.dumps(model['config'])}")
    print(f"Wrote {args.out}")


# ---------------------------------------------------------------------------
# predict
# ---------------------------------------------------------------------------
def load_manifest(path):
    """Terra data-table TSV -> DataFrame(entity, nSeries, sumVoxels, sumSlices, uids)."""
    import re
    from idc_features import series_features
    df = pd.read_csv(path, sep="\t", dtype=str)
    ent_col = next((c for c in df.columns if c.startswith("entity:")), df.columns[0])
    uid_col = "SeriesInstanceUIDs"
    rows = []
    all_uids = []
    for _, r in df.iterrows():
        raw = r[uid_col]
        uids = []
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                parsed = parsed.get("SeriesInstanceUIDs", [])
            uids = [str(u) for u in parsed]
        except Exception:
            uids = [u for u in re.split(r"[\s,\[\]\"']+", str(raw)) if re.fullmatch(r"[\d.]+", u)]
        rows.append({"entity": r[ent_col], "uids": uids})
        all_uids += uids
    feats = series_features(all_uids).set_index("SeriesInstanceUID")
    out = []
    for r in rows:
        f = feats.reindex(r["uids"])
        out.append({"entity": r["entity"], "nSeries": len(r["uids"]),
                    "nSeriesWithFeatures": int(f["voxels"].notna().sum()),
                    "sumVoxels": float(f["voxels"].fillna(0).sum()),
                    "sumSlices": float(f["instanceCount"].fillna(0).sum()),
                    "sumSizeMb": float(f["series_size_MB"].fillna(0).sum())})
    return pd.DataFrame(out)


def rate_scale(model, task, rates, region):
    """rate(target region)/rate(pilot region) for the task's shape from a rate file."""
    if not rates or not region:
        return 1.0, None
    tm = model["tasks"][task]
    pilot_region = tm.get("region") or model["config"].get("region")
    tables = rates.get("rates", {})
    shape = next((n for n in tables if n.lower() == task.lower()), None)
    if shape is None:
        shapes = rates.get("shapes", {})
        want_gpu = bool(model["config"].get(f"{task}_gpu"))
        shape = next((n for n in tables if bool(shapes.get(n, {}).get("gpu")) == want_gpu), None)
    if shape is None or region not in tables[shape] or pilot_region not in tables[shape]:
        return 1.0, f"(no rate for {task} in {region}/{pilot_region}; unscaled)"
    tgt, src = tables[shape][region]["total_hr"], tables[shape][pilot_region]["total_hr"]
    return tgt / src, f"{shape}: {pilot_region} ${src:.4f}/h -> {region} ${tgt:.4f}/h (x{tgt/src:.3f})"


def cmd_predict(args):
    with open(args.model) as f:
        model = json.load(f)
    if args.manifest:
        df = load_manifest(args.manifest)
        src = args.manifest
    else:
        df = load_tables(args.workflows)
        src = ",".join(args.workflows)
    df = prep_features(df)
    rates = None
    if args.rates:
        with open(args.rates) as f:
            rates = json.load(f)
    region = args.region or model["config"].get("region")

    pr = model["pilot"]
    print(f"Predicting {len(df)} workflows / {int(df['nSeries'].sum())} series / "
          f"{df['Mvox'].sum():.0f} Mvox from {src}")
    print(f"  model fitted on {pr['n_workflows']} workflows / {pr['n_series']} series "
          f"(nSeries {pr['nSeries_range']}, Mvox/workflow {pr['Mvox_range']}); "
          f"config {json.dumps(model['config'])}")
    out_of_range = ((df["nSeries"] < pr["nSeries_range"][0]) | (df["nSeries"] > pr["nSeries_range"][1]) |
                    (df["Mvox"] < pr["Mvox_range"][0]) | (df["Mvox"] > pr["Mvox_range"][1]))
    if out_of_range.any():
        print(f"  NOTE: {out_of_range.sum()} workflow(s) fall outside the pilot's nSeries/Mvox "
              f"range -- those rows are extrapolations.")

    total_var = 0.0
    total_cost = np.zeros(len(df))
    total_min = np.zeros(len(df))
    for t, tm in model["tasks"].items():
        yh, se, _ = predict_with(tm["time"], df)
        df[f"{t}_predMin"] = np.round(yh, 2)
        scale, note = rate_scale(model, t, rates, region)
        if note:
            print(f"  {t}: {note}")
        ch, cse, csum_sd = predict_with(tm["cost"], df)
        ch, cse, csum_sd = ch * scale, cse * scale, csum_sd * scale
        df[f"{t}_predCost"] = np.round(ch, 4)
        df[f"{t}_predCostSd"] = np.round(cse, 4)
        total_cost += ch
        total_min += yh
        total_var += csum_sd ** 2
    other = model.get("other_cost_per_workflow", 0.0)
    total_cost += other
    df["predRuntimeMin"] = np.round(total_min, 2)
    df["predCost"] = np.round(total_cost, 4)
    # per-row 95% interval (independent residuals per task; conservative sum of sds)
    row_sd = np.sqrt(sum(df[f"{t}_predCostSd"] ** 2 for t in model["tasks"]))
    df["predCostLo95"] = np.round(np.maximum(total_cost - Z95 * row_sd, 0), 4)
    df["predCostHi95"] = np.round(total_cost + Z95 * row_sd, 4)
    df["region"] = region
    df["modelFile"] = args.model
    df.to_csv(args.out, index=False)

    tot = float(total_cost.sum())
    sd_tot = math.sqrt(total_var)
    print(f"\n  PREDICTED TOTAL: ${tot:.2f}   95% interval ${max(tot - Z95 * sd_tot, 0):.2f} - "
          f"${tot + Z95 * sd_tot:.2f}   (region {region})")
    for t in model["tasks"]:
        print(f"    {t:<20} ${df[f'{t}_predCost'].sum():>8.2f}   {df[f'{t}_predMin'].sum() / 60:>7.1f} VM-hours")
    if other:
        print(f"    {'other (per wf)':<20} ${other * len(df):>8.2f}")
    print(f"    ${tot / max(df['nSeries'].sum(), 1):.4f}/series   "
          f"${tot / max(df['Mvox'].sum(), 1e-9):.5f}/Mvox   "
          f"{df['predRuntimeMin'].sum() / 60:.1f} total VM-hours")
    print(f"Wrote {args.out}")


# ---------------------------------------------------------------------------
# evaluate
# ---------------------------------------------------------------------------
def cmd_evaluate(args):
    pred = pd.read_csv(args.predicted, dtype={"entity": str})
    act = prep_features(load_tables(args.actual))
    act = act.rename(columns={"totalCost": "actualCost", "totalRuntimeMin": "actualRuntimeMin"})
    m = pred.merge(act, on="entity", suffixes=("_pred", ""), how="inner")
    if m.empty:
        sys.exit("No entities in common between predicted and actual tables.")
    tasks = [c[:-len("_predCost")] for c in pred.columns if c.endswith("_predCost")]
    m["absErr"] = (m["predCost"] - m["actualCost"]).abs()
    m["pctErr"] = 100 * (m["predCost"] - m["actualCost"]) / m["actualCost"].replace(0, np.nan)
    m["inInterval"] = (m["actualCost"] >= m["predCostLo95"]) & (m["actualCost"] <= m["predCostHi95"])
    tp, ta = float(m["predCost"].sum()), float(m["actualCost"].sum())
    print(f"Evaluated {len(m)} workflows ({len(pred) - len(m)} predicted rows unmatched)")
    print(f"  TOTAL   predicted ${tp:.2f}   actual ${ta:.2f}   error {100 * (tp - ta) / ta:+.1f}%")
    for t in tasks:
        col = f"{t}_cost" if f"{t}_cost" in m.columns else f"{t}_estCost"
        if col in m.columns:
            p_, a_ = m[f"{t}_predCost"].sum(), m[col].sum()
            pm, am = m[f"{t}_predMin"].sum(), m[f"{t}_runtimeMin"].sum()
            print(f"  {t:<18} $ pred {p_:>7.2f} act {a_:>7.2f} ({100 * (p_ - a_) / a_ if a_ else float('nan'):+.1f}%)"
                  f"   min pred {pm:>7.0f} act {am:>7.0f} ({100 * (pm - am) / am if am else float('nan'):+.1f}%)")
    print(f"  per-workflow MAPE {m['pctErr'].abs().mean():.1f}%   median APE {m['pctErr'].abs().median():.1f}%"
          f"   95%-interval coverage {100 * m['inInterval'].mean():.0f}%")
    print(f"  $/series  pred {tp / m['nSeries'].sum():.4f}  act {ta / m['nSeries'].sum():.4f};   "
          f"$/Mvox pred {tp / m['Mvox'].sum():.5f}  act {ta / m['Mvox'].sum():.5f}")
    if "actualRuntimeMin" in m.columns:
        print(f"  VM-hours  pred {m['predRuntimeMin'].sum() / 60:.1f}  act {m['actualRuntimeMin'].sum() / 60:.1f}")
    out = args.out or Path(args.predicted).with_name(Path(args.predicted).stem + "_evaluation.csv")
    keep = ["entity", "nSeries", "Mvox", "sumSlices", "predCost", "predCostLo95", "predCostHi95",
            "actualCost", "absErr", "pctErr", "inInterval", "predRuntimeMin", "actualRuntimeMin"]
    keep += [c for c in m.columns if any(c.startswith(t + "_") for t in tasks)
             and (c.endswith("_predCost") or c.endswith("_cost") or c.endswith("_estCost")
                  or c.endswith("_predMin") or c.endswith("_runtimeMin"))]
    m[[c for c in keep if c in m.columns]].to_csv(out, index=False)
    print(f"Wrote {out}")
    if args.plots:
        plot_evaluation(m, tasks, Path(args.plots))


# ---------------------------------------------------------------------------
# report / plots
# ---------------------------------------------------------------------------
def _plt():
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        return plt
    except Exception as exc:  # pragma: no cover
        print(f"[plots] matplotlib unavailable ({exc}); skipping figures")
        return None


def _scatter_fit(ax, x, y, groups=None, xlabel="", ylabel="", title=""):
    if groups is None:
        ax.scatter(x, y, s=28)
    else:
        for g in sorted(pd.Series(groups).dropna().unique()):
            mk = (groups == g)
            ax.scatter(x[mk], y[mk], s=28, label=str(g))
        ax.legend(fontsize=7)
    xx = np.asarray(x, float); yy = np.asarray(y, float)
    ok = np.isfinite(xx) & np.isfinite(yy)
    subsets = [("", ok)]
    if groups is not None and pd.Series(groups).nunique() > 1:
        subsets = [(str(g), ok & (np.asarray(groups) == g)) for g in pd.Series(groups).dropna().unique()]
    notes = []
    for gname, mk in subsets:
        if mk.sum() >= 3 and np.ptp(xx[mk]) > 0:
            b, a = np.polyfit(xx[mk], yy[mk], 1)
            r = np.corrcoef(xx[mk], yy[mk])[0, 1]
            xs = np.linspace(xx[mk].min(), xx[mk].max(), 50)
            ax.plot(xs, a + b * xs, "--", lw=1, color="gray")
            notes.append(f"{gname + ': ' if gname else ''}slope {b:.3g}, r={r:.2f}")
    ax.set_title(f"{title}" + (f"  ({'; '.join(notes)})" if notes else ""), fontsize=8)
    ax.set_xlabel(xlabel); ax.set_ylabel(ylabel)
    ax.grid(alpha=0.3)


def plot_report(wf, se, bill, tasks, model, outdir):
    plt = _plt()
    if plt is None:
        return []
    outdir.mkdir(parents=True, exist_ok=True)
    made = []
    grp = wf["label"] if "label" in wf.columns and wf["label"].notna().any() else wf["_source"]

    # 1. cost vs workload (nSeries, Mvox, slices, MB)
    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    _scatter_fit(axes[0, 0], wf["nSeries"], wf["totalCost"], grp, "series per workflow", "$ per workflow", "cost vs #series")
    _scatter_fit(axes[0, 1], wf["Mvox"], wf["totalCost"], grp, "Mvoxels per workflow", "$ per workflow", "cost vs voxels")
    _scatter_fit(axes[1, 0], wf["sumSlices"], wf["totalCost"], grp, "slices per workflow", "$ per workflow", "cost vs slices")
    if "sumSizeMb" in wf.columns:
        _scatter_fit(axes[1, 1], wf["sumSizeMb"], wf["totalCost"], grp, "MB per workflow", "$ per workflow", "cost vs input MB")
    fig.suptitle("Workflow cost vs workload"); fig.tight_layout()
    p = outdir / "cost_vs_workload.png"; fig.savefig(p, dpi=120); plt.close(fig); made.append(p)

    # 2. per-task runtime vs voxels / series
    fig, axes = plt.subplots(len(tasks), 2, figsize=(11, 3.6 * len(tasks)), squeeze=False)
    for i, t in enumerate(tasks):
        rt = pd.to_numeric(wf[f"{t}_runtimeMin"], errors="coerce")
        _scatter_fit(axes[i, 0], wf["Mvox"], rt, grp, "Mvoxels per workflow", "minutes", f"{t} runtime vs voxels")
        _scatter_fit(axes[i, 1], wf["nSeries"], rt, grp, "series per workflow", "minutes", f"{t} runtime vs #series")
    fig.suptitle("Task wall-clock vs workload"); fig.tight_layout()
    p = outdir / "task_runtime_vs_workload.png"; fig.savefig(p, dpi=120); plt.close(fig); made.append(p)

    # 3. unit costs
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.8))
    for ax, col, lab in [(axes[0], "costPerSeries", "$/series"), (axes[1], "costPerMvoxel", "$/Mvox"),
                         (axes[2], "costPerSlice", "$/slice")]:
        if col in wf.columns:
            _scatter_fit(ax, wf["nSeries"], wf[col], grp, "series per workflow", lab, f"{lab} vs batch size")
    fig.suptitle("Unit cost vs batch size (fixed overhead amortization)"); fig.tight_layout()
    p = outdir / "unit_cost_vs_batch_size.png"; fig.savefig(p, dpi=120); plt.close(fig); made.append(p)

    # 4. per-task cost split per workflow (stacked bars)
    cost_cols = [f"{t}_cost" if f"{t}_cost" in wf.columns else f"{t}_estCost" for t in tasks]
    if all(c in wf.columns for c in cost_cols):
        fig, ax = plt.subplots(figsize=(max(6, 0.45 * len(wf) + 2), 4))
        order = wf.sort_values("Mvox")
        bottom = np.zeros(len(order))
        for t, c in zip(tasks, cost_cols):
            v = pd.to_numeric(order[c], errors="coerce").fillna(0).to_numpy()
            ax.bar(range(len(order)), v, bottom=bottom, label=t)
            bottom += v
        if "otherCost" in order.columns:
            v = pd.to_numeric(order["otherCost"], errors="coerce").fillna(0).to_numpy()
            ax.bar(range(len(order)), v, bottom=bottom, label="other", color="lightgray")
        ax.set_xticks(range(len(order)))
        ax.set_xticklabels([f"{e}\n{n:.0f}s/{m:.0f}M" for e, n, m in zip(order["entity"], order["nSeries"], order["Mvox"])],
                           fontsize=6, rotation=90)
        ax.set_ylabel("$"); ax.set_title("Cost per workflow by task (entity / #series / Mvox), sorted by voxels")
        ax.legend(fontsize=8); ax.grid(axis="y", alpha=0.3); fig.tight_layout()
        p = outdir / "cost_by_task_per_workflow.png"; fig.savefig(p, dpi=120); plt.close(fig); made.append(p)

    # 5. per-series timings vs voxels (profile)
    if se is not None and len(se):
        se = se.copy()
        se["Mvox"] = pd.to_numeric(se["voxels"], errors="coerce") / 1e6
        cols = [c for c in ["downloadSec", "dcm2niixSec", "inferenceSec", "refDownloadSec", "segSec",
                            "radiomicsSec", "outputConversionSec"]
                if c in se.columns and se[c].notna().sum() >= 2]
        if cols:
            n = len(cols)
            fig, axes = plt.subplots(1, n, figsize=(4.2 * n, 3.8), squeeze=False)
            sgrp = se["entity"].astype(str) if len(se["entity"].unique()) <= 12 else None
            for ax, c in zip(axes[0], cols):
                _scatter_fit(ax, se["Mvox"], pd.to_numeric(se[c], errors="coerce"), sgrp,
                             "Mvoxels (series)", "seconds", f"{c} vs voxels")
            fig.suptitle("Per-series phase timings vs series size"); fig.tight_layout()
            p = outdir / "series_phase_timings.png"; fig.savefig(p, dpi=120); plt.close(fig); made.append(p)

            # phase breakdown per workflow (stacked) + unexplained overhead
            agg = se.groupby("workflowId")[cols].sum(min_count=1) / 60.0
            wfo = wf.sort_values("Mvox")
            agg = agg.reindex(wfo["workflowId"]).fillna(0)
            fig, ax = plt.subplots(figsize=(max(6, 0.45 * len(agg) + 2), 4))
            bottom = np.zeros(len(agg))
            for c in cols:
                ax.bar(range(len(agg)), agg[c].to_numpy(), bottom=bottom, label=c)
                bottom += agg[c].to_numpy()
            tot_rt = wfo["totalRuntimeMin"].fillna(0).to_numpy(float)
            ax.bar(range(len(agg)), np.maximum(tot_rt - bottom, 0), bottom=bottom, label="VM time not in phases (boot/pull/queue/etc.)",
                   color="lightgray")
            ax.set_xticks(range(len(agg)))
            ax.set_xticklabels([f"{e}\n{n:.0f}s/{m:.0f}M" for e, n, m in zip(wfo["entity"], wfo["nSeries"], wfo["Mvox"])],
                               fontsize=6, rotation=90)
            ax.set_ylabel("minutes"); ax.set_title("Where the VM time goes, per workflow")
            ax.legend(fontsize=7); ax.grid(axis="y", alpha=0.3); fig.tight_layout()
            p = outdir / "phase_breakdown_per_workflow.png"; fig.savefig(p, dpi=120); plt.close(fig); made.append(p)

        if "sizeMb" in se.columns and "downloadSec" in se.columns and se["downloadSec"].notna().sum() >= 2:
            fig, ax = plt.subplots(figsize=(5, 3.8))
            _scatter_fit(ax, se["sizeMb"], pd.to_numeric(se["downloadSec"], errors="coerce"), None,
                         "series MB", "download s", "download time vs series size")
            fig.tight_layout(); p = outdir / "download_vs_size.png"; fig.savefig(p, dpi=120); plt.close(fig); made.append(p)

    # 6. billing SKU categories
    if bill is not None and len(bill):
        cat = bill.groupby("category")["net"].sum().sort_values(ascending=False)
        fig, axes = plt.subplots(1, 2, figsize=(10, 3.8))
        axes[0].pie(cat.values, labels=[f"{k} ({100 * v / cat.sum():.0f}%)" for k, v in cat.items()],
                    textprops={"fontsize": 7})
        axes[0].set_title("Actual $ by SKU category")
        bt = bill.groupby("wdlTask")["net"].sum().sort_values(ascending=False)
        axes[1].bar(bt.index, bt.values); axes[1].set_title("Actual $ by WDL task"); axes[1].tick_params(axis="x", labelsize=7)
        fig.tight_layout(); p = outdir / "billing_breakdown.png"; fig.savefig(p, dpi=120); plt.close(fig); made.append(p)

    # 7. model overlay: fitted plane slices
    if model:
        fig, axes = plt.subplots(1, len(model["tasks"]), figsize=(5 * len(model["tasks"]), 3.8), squeeze=False)
        for ax, (t, tm) in zip(axes[0], model["tasks"].items()):
            f = tm["cost"]
            col = tm.get("cost_col", f"{t}_cost")
            if col in wf.columns:
                yh, _, _ = predict_with(f, wf)
                ax.scatter(pd.to_numeric(wf[col], errors="coerce"), yh, s=28)
                lim = [0, max(float(np.nanmax(yh)), float(pd.to_numeric(wf[col], errors="coerce").max())) * 1.05]
                ax.plot(lim, lim, "--", color="gray", lw=1)
                ax.set_xlabel("actual $"); ax.set_ylabel("fitted $")
                ax.set_title(f"{t}: {fmt_eq(f, '$')}", fontsize=7); ax.grid(alpha=0.3)
        fig.suptitle("Model fit (in-sample)"); fig.tight_layout()
        p = outdir / "model_fit.png"; fig.savefig(p, dpi=120); plt.close(fig); made.append(p)
    return made


def plot_evaluation(m, tasks, outdir):
    plt = _plt()
    if plt is None:
        return
    outdir.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    ax = axes[0]
    ax.errorbar(m["actualCost"], m["predCost"],
                yerr=[m["predCost"] - m["predCostLo95"], m["predCostHi95"] - m["predCost"]],
                fmt="o", ms=4, elinewidth=0.6, capsize=2)
    lim = [0, float(max(m["actualCost"].max(), m["predCostHi95"].max())) * 1.05]
    ax.plot(lim, lim, "--", color="gray", lw=1)
    ax.set_xlabel("actual $ per workflow"); ax.set_ylabel("predicted $ (95% interval)")
    ax.set_title(f"Predicted vs actual, {len(m)} workflows"); ax.grid(alpha=0.3)
    ax = axes[1]
    ax.scatter(m["Mvox"], m["pctErr"], s=24)
    ax.axhline(0, color="gray", lw=1)
    ax.set_xlabel("Mvoxels per workflow"); ax.set_ylabel("prediction error %"); ax.set_title("Error vs workload"); ax.grid(alpha=0.3)
    fig.tight_layout()
    p = outdir / "predicted_vs_actual.png"; fig.savefig(p, dpi=120); plt.close(fig)
    print(f"  wrote {p}")


def cmd_report(args):
    wf = prep_features(load_tables(args.workflows))
    tasks = task_names(wf)
    se = load_tables(args.series) if args.series else None
    bill = load_tables(args.billing) if args.billing else None
    model = None
    if args.model:
        with open(args.model) as f:
            model = json.load(f)
    outdir = Path(args.plots)
    outdir.mkdir(parents=True, exist_ok=True)

    lines = []
    def P(s=""):
        print(s); lines.append(s)
    P(f"# Cost report: {', '.join(sorted(wf['_source'].unique()))}")
    P(f"workflows {len(wf)}, series {int(wf['nSeries'].sum())}, Mvox {wf['Mvox'].sum():.0f}, "
      f"slices {int(wf['sumSlices'].sum())}, region {sorted(wf['region'].dropna().unique().tolist())}, "
      f"cost source {sorted(wf['costSource'].dropna().unique().tolist()) if 'costSource' in wf else '?'}")
    tot = float(pd.to_numeric(wf["totalCost"], errors="coerce").sum())
    P(f"total ${tot:.3f}  = ${tot / max(wf['nSeries'].sum(), 1):.4f}/series, "
      f"${tot / max(wf['Mvox'].sum(), 1e-9):.5f}/Mvox, ${tot / max(wf['sumSlices'].sum(), 1):.6f}/slice, "
      f"{wf['totalRuntimeMin'].sum() / 60:.1f} VM-hours")
    P()
    P("| task | VM-min total | VM-min/series | VM-min/Mvox | attempts | preempted | $ | $ share | eff $/h | catalog $/h |")
    P("|---|---|---|---|---|---|---|---|---|---|")
    for t in tasks:
        rt = pd.to_numeric(wf[f"{t}_runtimeMin"], errors="coerce").sum()
        cc = f"{t}_cost" if f"{t}_cost" in wf.columns else f"{t}_estCost"
        c = pd.to_numeric(wf[cc], errors="coerce").sum()
        att = pd.to_numeric(wf.get(f"{t}_attempts"), errors="coerce").sum()
        pre = pd.to_numeric(wf.get(f"{t}_preempted"), errors="coerce").sum()
        rate = pd.to_numeric(wf.get(f"{t}_rateHr"), errors="coerce").mean()
        P(f"| {t} | {rt:.0f} | {rt / max(wf['nSeries'].sum(), 1):.2f} | {rt / max(wf['Mvox'].sum(), 1e-9):.3f} | "
          f"{att:.0f} | {pre:.0f} | {c:.3f} | {100 * c / tot if tot else 0:.0f}% | "
          f"{c / (rt / 60) if rt else float('nan'):.4f} | {rate:.4f} |")
    if se is not None and len(se):
        P()
        P("Per-series phase timings (median s / s per Mvox slope):")
        se2 = se.copy(); se2["Mvox"] = pd.to_numeric(se2["voxels"], errors="coerce") / 1e6
        for c in ["downloadSec", "dcm2niixSec", "inferenceSec", "refDownloadSec", "segSec",
                  "radiomicsSec", "outputConversionSec"]:
            if c in se2.columns and se2[c].notna().sum() >= 2:
                sub = se2[se2[c].notna() & se2["Mvox"].notna()]
                slope = np.polyfit(sub["Mvox"], sub[c], 1)[0] if len(sub) >= 3 and sub["Mvox"].nunique() > 1 else float("nan")
                P(f"  {c:<22} median {sub[c].median():>7.1f}s  mean {sub[c].mean():>7.1f}s  "
                  f"slope {slope:>7.2f} s/Mvox  n={len(sub)}")
        if "modelTimings" in se2.columns and se2["modelTimings"].notna().any():
            tot_m = {}
            for s in se2["modelTimings"].dropna():
                try:
                    for k, v in json.loads(s).items():
                        tot_m[k] = tot_m.get(k, 0) + (v or 0)
                except Exception:
                    pass
            if tot_m:
                P("  inference time by sub-model (total s):")
                for k, v in sorted(tot_m.items(), key=lambda kv: -kv[1])[:15]:
                    P(f"    {k:<40} {v:>9.1f}")
    if bill is not None and len(bill):
        P()
        cat = bill.groupby("category")["net"].sum().sort_values(ascending=False)
        P("Actual $ by SKU category: " + ", ".join(f"{k} {v:.3f} ({100 * v / cat.sum():.0f}%)" for k, v in cat.items()))
    made = plot_report(wf, se, bill, tasks, model, outdir)
    if made:
        P()
        P("Figures: " + ", ".join(p.name for p in made))
    (outdir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {outdir / 'report.md'}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fit", help="fit per-task time/cost models on pilot workflows CSV(s)")
    f.add_argument("--workflows", nargs="+", required=True)
    f.add_argument("--series", nargs="*")
    f.add_argument("--keep-failed", action="store_true")
    f.add_argument("--out", default="model.json")
    f.set_defaults(func=cmd_fit)

    p = sub.add_parser("predict", help="predict a run from a Terra data table (or a workflows CSV)")
    p.add_argument("--model", required=True)
    p.add_argument("--manifest", help="Terra data table TSV (entity:..._id, SeriesInstanceUIDs)")
    p.add_argument("--workflows", nargs="*", help="alternative: predict rows of a workflows CSV")
    p.add_argument("--rates", help="region_rates.json (needed only when --region differs from the pilot)")
    p.add_argument("--region", help="target region (default: the pilot's)")
    p.add_argument("--out", default="predicted.csv")
    p.set_defaults(func=cmd_predict)

    e = sub.add_parser("evaluate", help="compare a prediction with the actual workflows CSV")
    e.add_argument("--predicted", required=True)
    e.add_argument("--actual", nargs="+", required=True)
    e.add_argument("--out")
    e.add_argument("--plots", help="directory for predicted_vs_actual.png")
    e.set_defaults(func=cmd_evaluate)

    r = sub.add_parser("report", help="metrics + figures for one or more runs")
    r.add_argument("--workflows", nargs="+", required=True)
    r.add_argument("--series", nargs="*")
    r.add_argument("--billing", nargs="*")
    r.add_argument("--model")
    r.add_argument("--plots", required=True, help="output directory (report.md + PNGs)")
    r.set_defaults(func=cmd_report)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
