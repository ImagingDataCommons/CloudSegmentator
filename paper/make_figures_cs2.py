# /// script
# requires-python = ">=3.11"
# dependencies = ["pandas>=2.2", "matplotlib>=3.9", "numpy"]
# ///
"""Draw the case study 2 figures - cs2-stage-times, cs2-cost-breakdown and
cs2-peak-memory - and cs1-peak-memory from paper/data/ (see build_data_cs2.py).

    uv run paper/make_figures_cs2.py

Same style and conventions as make_figures.py, whose helpers it reuses: colour is
the kind of VM (blue GPU, orange CPU); boxes span the IQR with the median marked
and printed; whiskers at 1.5 IQR with every batch beyond drawn, as in stage-times.
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from make_figures import (CATEGORICAL, COST_CATS, DATA, FULL_W, INK, LABEL_BOX, MUTED, VM_COLOR,
                          cost_share_bars, panel_label, range_bar, save, value_grid)

MODELS = ["TotalSegmentator", "MOOSE"]
TASKS = [("inference", "GPU", "Input conversion and inference (GPU VM)"),
         ("outputConversion", "CPU", "Feature extraction and output conversion (CPU VM)")]
PHASES = [("Waiting for a VM", "wait_vm_min"),
          ("VM start-up", "vm_startup_min"),
          ("Running", "running_min"),
          ("Deallocation", "deallocation_min")]
STEPS = {"inference": [("Downloading DICOM", "dicom_download_min"),
                       ("DICOM to NIfTI", "dicom_to_nifti_min"),
                       ("Model inference", "inference_min")],
         "outputConversion": [("Downloading reference DICOM", "reference_download_min"),
                              ("NIfTI to DICOM SEG", "nifti_to_seg_min"),
                              ("Radiomics features", "radiomics_min"),
                              ("Features to DICOM SR", "features_to_sr_min")]}
LOG_TICKS = [(1, "1 min"), (10, "10 min"), (60, "1 h"), (600, "10 h")]
# Panel B is per series: batches here hold 2-39 series (case study 1: always 12), so
# per-batch sums would mostly show batch size. Each point is one batch's mean.
SERIES_COL = {"dicom_download_min": "convert_series", "dicom_to_nifti_min": "convert_series",
              "inference_min": "inference_series"}


def with_unit(x):
    if x < 1:
        return f"{x * 60:.0f} s"
    return f"{x:.1f} min" if x < 60 else f"{x / 60:.1f} h"


def minutes(x):
    return f"{x:.2f}" if x < 0.1 else f"{x:.1f}"


def grouped_rows(ax, groups, color, table, title, part, seed0, fmt):
    """One heading row per group, then a row per model beneath it."""
    y, ticks, tick_labels, sub = 0, [], [], []
    for gi, (heading, values) in enumerate(groups):
        ticks.append(y), tick_labels.append(heading), sub.append(False)
        y += 1
        for mi, model in enumerate(MODELS):
            v = values[model]
            s = range_bar(ax, y, v, color, fmt, horizontal=True, width=0.5, tukey=True,
                          seed=seed0 + 10 * gi + mi, label="end")
            table.append(dict(task=title, part=part, row=heading, model=model, **s))
            ticks.append(y), tick_labels.append("   " + model), sub.append(True)
            y += 1
        y += 0.3
    ax.set_yticks(ticks, tick_labels)
    for tick, is_sub in zip(ax.get_yticklabels(), sub):
        tick.set_color(MUTED if is_sub else INK)
    ax.spines["left"].set_visible(False)
    value_grid(ax, "x")
    return y - 0.6


def cs2_stage_times(attempts, steps):
    done = attempts[attempts.status == "Done"]
    fig, axs = plt.subplots(2, 2, figsize=(FULL_W, 6.4),
                            gridspec_kw=dict(wspace=0.9, hspace=0.28, height_ratios=[12.9, 15.2]))
    table, bottoms, bottoms_b = [], [], []
    for col, (task, vm, title) in enumerate(TASKS):
        color = VM_COLOR[vm]
        d = done[done.task == task]
        groups = [(lab, {m: d.loc[d.model == m, c] for m in MODELS}) for lab, c in PHASES]
        bottoms.append(grouped_rows(axs[0, col], groups, color, table, title, "phase", 100 * col,
                                    with_unit))
        axs[0, col].set_xscale("log")
        axs[0, col].set_xlim(0.1, 4000)
        axs[0, col].set_xticks([t for t, _ in LOG_TICKS], [s for _, s in LOG_TICKS])
        axs[0, col].minorticks_off()
        axs[0, col].set_title(title, fontsize=7.5, loc="left", color=INK, pad=8)
        axs[0, col].set_xlabel("Time per batch, successful attempt (log scale)")

        per_series = lambda m, c: (steps.loc[steps.model == m, c]  # noqa: E731
                                   / steps.loc[steps.model == m, SERIES_COL.get(c, "output_conversion_series")])
        groups = [(lab, {m: per_series(m, c) for m in MODELS}) for lab, c in STEPS[task]]
        bottoms_b.append(grouped_rows(axs[1, col], groups, color, table, title, "step",
                                      100 * col + 50, minutes))
        axs[1, col].set_xlabel("Minutes per series (mean over the batch)")
    # Same row pitch in both columns, so the two tasks line up.
    for row, b in ((0, bottoms), (1, bottoms_b)):
        for ax in axs[row]:
            ax.set_ylim(max(b), -0.7)
    axs[1, 1].set_xlim(0, axs[1, 1].get_xlim()[1])
    axs[1, 0].set_xlim(0, axs[1, 1].get_xlim()[1])
    panel_label(axs[0, 0], "A", x=-0.85)
    panel_label(axs[1, 0], "B", x=-0.85)
    save(fig, "cs2-stage-times", table)


def cs2_cost_breakdown(costs, runs):
    series = [costs[costs.model == m].groupby("category").cost_usd.sum() for m in MODELS]
    fig, ax = plt.subplots(figsize=(FULL_W, 1.1))
    n = runs.set_index("model").series
    table = cost_share_bars(ax, series, MODELS, [n[m] for m in MODELS])
    ax.set_xlabel("Share of total cost, twoVM configuration")
    save(fig, "cs2-cost-breakdown", table)


# RAM of each VM shape (GiB), from the runtime blocks: n1-highmem-4 for TotalSegmentator
# inference, custom 4 vCPU / 16 GiB for MOOSE, N2D 4 vCPU / 16 GB for output conversion.
# Case study 1's GPU VM had 13 GiB (CloudSegmentator v1.2.0 twoVM.wdl defaults).
VM_RAM = {("GPU", "TotalSegmentator"): 26, ("GPU", "MOOSE"): 16,
          ("CPU", "TotalSegmentator"): 16, ("CPU", "MOOSE"): 16}
CS1_GPU_RAM = 13
MEM_ROWS = [("GPU", "TotalSegmentator", "total", "TotalSegmentator, total"),
            ("GPU", "TotalSegmentator", "lung_vessels", "TotalSegmentator, lung_vessels"),
            ("GPU", "MOOSE", "all models", "MOOSE, ten models (per series)"),
            ("CPU", "TotalSegmentator", "output conversion", "TotalSegmentator"),
            ("CPU", "MOOSE", "output conversion", "MOOSE")]
FAIL_MARK = dict(marker="x", s=14, color=INK, linewidths=0.9, zorder=5)
RERUN_MARK = dict(marker="o", s=14, facecolors="none", edgecolors=INK, linewidths=0.8, zorder=6)


def rerun_peaks(rerun_peak):
    """Peak of each series' last rerun, for reruns given more RAM than the main run's VM
    on that task. Those are the series that failed for memory: what they needed."""
    r = rerun_peak.copy()
    more = np.where(r.vm == "GPU",
                    r.inference_ram_gib > [VM_RAM[("GPU", m)] for m in r.model],
                    r.output_conversion_ram_gib > [VM_RAM[("CPU", m)] for m in r.model])
    r = r[more].sort_values("rerun_pass")
    return r.drop_duplicates(["model", "SeriesInstanceUID", "vm", "unit"], keep="last")


def memory_failures(fail, peak):
    """Units that failed for a memory-class cause, placed at the attempt-wide peak. That
    peak is attributable to the failed unit only when it exceeds every unit that
    finished in the same attempt; check it rather than assume it."""
    f = fail[fail.cause.isin(["killed (signal 9)", "export worker killed (RAM)",
                              "timed out (90 min cap)"])].copy()
    f["unit"] = np.where(f.model == "MOOSE", "all models", f.unit)
    f = f.drop_duplicates(["workflow", "SeriesInstanceUID", "unit"])
    gpu = peak[peak.vm == "GPU"]
    # MOOSE's window spans the whole series, crashed workers included, so the series'
    # own row already holds its peak; use that rather than the attempt-wide one.
    own = gpu.set_index(["workflow", "SeriesInstanceUID", "unit"]).peak_gb
    key = pd.MultiIndex.from_frame(f[["workflow", "SeriesInstanceUID", "unit"]])
    mine = own.reindex(key).to_numpy()
    moose = (f.model == "MOOSE").to_numpy() & np.isfinite(mine)
    f["run_peak_gb"] = np.where(moose, mine, f.run_peak_gb)
    f["attributable"] = moose | np.array([
        r.run_peak_gb > gpu[(gpu.workflow == r.workflow)
                            & ~((gpu.SeriesInstanceUID == r.SeriesInstanceUID) & (gpu.unit == r.unit))
                            ].peak_gb.max()
        for r in f.itertuples()])
    return f


# Lower panels of cs2-peak-memory: each model against the size of the volume it works on.
# `total` and MOOSE track voxels after resampling to 1.5 mm, TotalSegmentator's working
# resolution; `lung_vessels` tracks voxels as acquired.
SIZE_PANELS = [("TotalSegmentator", "total", "mvox_1p5mm", "Voxels at 1.5 mm (millions)",
                "TotalSegmentator, total", (3, 250), [3, 10, 30, 100]),
               ("TotalSegmentator", "lung_vessels", "mvox_native", "Voxels as acquired (millions)",
                "TotalSegmentator, lung_vessels", (8, 900), [10, 30, 100, 300]),
               ("MOOSE", "all models", "mvox_1p5mm", "Voxels at 1.5 mm (millions)",
                "MOOSE, ten models", (3, 250), [3, 10, 30, 100])]


def cs2_peak_memory(peak, fail, geo, order, rerun_peak):
    f = memory_failures(fail, peak)
    rr = rerun_peaks(rerun_peak)
    # A TotalSegmentator rerun redid both tasks; on the GPU VM keep the ones that had failed.
    failed = set(zip(f.model, f.SeriesInstanceUID, f.unit))
    rr = rr[(rr.vm == "CPU")
            | np.array([k in failed for k in zip(rr.model, rr.SeriesInstanceUID, rr.unit)])]
    fig = plt.figure(figsize=(FULL_W, 5.4))
    # Two grids, so the scatter row can use the width panel A gives to its row labels.
    ax = fig.add_subplot(fig.add_gridspec(1, 1, left=0.3, right=0.98, top=0.97, bottom=0.6)[0])
    gs = fig.add_gridspec(1, 3, left=0.09, right=0.98, top=0.45, bottom=0.14, wspace=0.1)
    table, ticks, labels, y = [], [], [], 0
    for i, (vm, model, unit, label) in enumerate(MEM_ROWS):
        if i in (0, 3):
            ticks.append(y), labels.append("GPU VM: input conversion and inference" if vm == "GPU"
                                           else "CPU VM: output conversion")
            y += 1
        v = peak[(peak.vm == vm) & (peak.model == model) & (peak.unit == unit)].peak_gb
        s = range_bar(ax, y, v, VM_COLOR[vm], lambda x: f"{x:.1f} GiB", horizontal=True,
                      width=0.5, tukey=True, seed=i, label="end")
        ff = f[(f.model == model) & (f.unit == unit)] if vm == "GPU" else f.iloc[:0]
        ax.scatter(ff.run_peak_gb, np.full(len(ff), y), **FAIL_MARK)
        rv = rr[(rr.vm == vm) & (rr.model == model) & (rr.unit == unit)].peak_gb
        ax.scatter(rv, np.full(len(rv), y), **RERUN_MARK)
        ram = VM_RAM[(vm, model)]
        ax.vlines(ram, y - 0.42, y + 0.42, color=INK, lw=1.4, zorder=4)
        table.append(dict(vm=vm, model=model, unit=unit, vm_ram_gib=ram, **s,
                          n_over_13=int((v > 13).sum()), n_within_1_of_ram=int((v > ram - 1).sum()),
                          n_failed_memory=len(ff), n_rerun=len(rv),
                          rerun_peak_max=rv.max() if len(rv) else None))
        ticks.append(y), labels.append("   " + label)
        y += 1
        if i == 2:
            gpu_bottom = y - 0.5
            y += 0.3
    ax.vlines(CS1_GPU_RAM, -0.5, gpu_bottom, color=MUTED, lw=0.8, ls=(0, (3, 2)), zorder=1)
    ax.annotate(f"case study 1 GPU VM, {CS1_GPU_RAM} GiB", (CS1_GPU_RAM, -0.5), xytext=(3, 0),
                textcoords="offset points", fontsize=6, color=MUTED, va="center")
    ax.set_yticks(ticks, labels)
    for t, lab in zip(ax.get_yticklabels(), labels):
        t.set_color(MUTED if lab.startswith("   ") else INK)
    ax.set_ylim(y - 0.6, -0.9)
    ax.set_xlim(0, 36)
    ax.spines["left"].set_visible(False)
    value_grid(ax, "x")
    ax.set_xlabel("Peak RAM in use on the VM (GiB), per series or per task")
    ax.legend(handles=[plt.Line2D([], [], color=INK, lw=1.4, label="VM RAM"),
                       plt.Line2D([], [], ls="", marker="x", color=INK, markeredgewidth=0.9,
                                  markersize=4, label="failed, memory-related")],
              loc="lower right", fontsize=6, frameon=False)
    panel_label(ax, "A", x=-0.36)

    # B-D: peak RAM against the size of the volume each model works on, from IDC geometry.
    # TotalSegmentator tasks that ran after a failure in the same attempt are drawn hollow:
    # a timed-out task leaves RAM behind that inflates every later one (cs2_series_order).
    after = order[order.failures_before > 0].set_index(["workflow", "SeriesInstanceUID"]).index
    axb = None
    for col, (model, unit, xcol, xlabel, title, xlim, xticks) in enumerate(SIZE_PANELS):
        axb = fig.add_subplot(gs[0, col], sharey=axb)
        p = peak[(peak.vm == "GPU") & (peak.model == model) & (peak.unit == unit)]
        p = p.merge(geo[["SeriesInstanceUID", xcol]], on="SeriesInstanceUID").dropna(subset=[xcol])
        late = (p.set_index(["workflow", "SeriesInstanceUID"]).index.isin(after)
                & (model == "TotalSegmentator"))
        clean = p[~late]
        axb.scatter(clean[xcol], clean.peak_gb, s=3, color=VM_COLOR["GPU"], alpha=0.35,
                    linewidths=0, rasterized=True, zorder=2)
        axb.scatter(p[late][xcol], p[late].peak_gb, s=7, facecolors="none", edgecolors=MUTED,
                    linewidths=0.6, zorder=3)
        ff = f[(f.model == model) & (f.unit == unit)].merge(geo[["SeriesInstanceUID", xcol]],
                                                            on="SeriesInstanceUID")
        axb.scatter(ff[xcol], ff.run_peak_gb, **FAIL_MARK)
        rv = rr[(rr.vm == "GPU") & (rr.model == model) & (rr.unit == unit)].merge(
            geo[["SeriesInstanceUID", xcol]], on="SeriesInstanceUID")
        axb.scatter(rv[xcol], rv.peak_gb, **RERUN_MARK)
        ram = VM_RAM[("GPU", model)]
        axb.axhline(ram, color=INK, lw=1, zorder=1)
        axb.annotate(f"VM RAM, {ram} GiB", (0.03, ram), xycoords=("axes fraction", "data"),
                     xytext=(0, 2), textcoords="offset points", fontsize=6)
        axb.axhline(CS1_GPU_RAM, color=MUTED, lw=0.8, ls=(0, (3, 2)), zorder=1)
        axb.set_xscale("log")
        axb.set_xlim(*xlim)
        axb.set_xticks(xticks, [f"{t:,}" for t in xticks])
        axb.minorticks_off()
        axb.set_title(title, fontsize=7.5, loc="left", color=INK)
        axb.set_xlabel(xlabel)
        # Over units that finished and did not run after a failure.
        rho = clean.peak_gb.rank().corr(clean[xcol].rank())
        rho_mb = clean.peak_gb.rank().corr(clean.download_mb.rank())
        axb.annotate(f"Spearman ρ = {rho:.2f}\nagainst DICOM MB: {rho_mb:.2f}", (0.97, 0.04),
                     xycoords="axes fraction", ha="right", va="bottom", fontsize=6, color=MUTED)
        value_grid(axb, "y")
        table.append(dict(vm="GPU", model=model, unit=f"{unit} against {xcol} (panel {'BCD'[col]})",
                          n=len(clean), n_after_failure=int(late.sum()), spearman_vs_size=rho,
                          spearman_vs_mb=rho_mb, n_failed_memory=len(ff), n_rerun=len(rv)))
        if col == 0:
            axb.set_ylabel("Peak RAM on the GPU VM (GiB)")
        else:
            plt.setp(axb.get_yticklabels(), visible=False)
        panel_label(axb, "BCD"[col], x=-0.28 if col == 0 else -0.08)
    axb.set_ylim(0, 36)
    fig.legend(handles=[plt.Line2D([], [], ls="", marker="o", color=VM_COLOR["GPU"], alpha=0.6,
                                   markersize=2.5, markeredgewidth=0, label="finished"),
                        plt.Line2D([], [], ls="", marker="o", markerfacecolor="none",
                                   markeredgecolor=MUTED, markersize=3.5, markeredgewidth=0.6,
                                   label="finished, after a failure in the same attempt"),
                        plt.Line2D([], [], ls="", marker="x", color=INK, markeredgewidth=0.9,
                                   markersize=4, label="failed, memory-related"),
                        plt.Line2D([], [], ls="", marker="o", markerfacecolor="none", color=INK,
                                   markeredgewidth=0.8, markersize=4,
                                   label="rerun with more RAM, succeeded"),
                        plt.Line2D([], [], color=MUTED, lw=0.8, ls=(0, (3, 2)),
                                   label=f"case study 1 GPU VM, {CS1_GPU_RAM} GiB")],
               loc="lower center", ncol=5, fontsize=6, frameon=False, bbox_to_anchor=(0.5, -0.01))
    save(fig, "cs2-peak-memory", table)
    print("memory-related failures:", len(f), "attributable to the failed unit:", int(f.attributable.sum()))


STUDY_COLOR = {"cs1": CATEGORICAL[0], "cs2": CATEGORICAL[2]}
CS1_RUNS = [("126k", "126k cohort"), ("10k", "10k cohort"), ("1k", "1k cohort")]
MVOX_BINS = np.geomspace(3, 200, 22)


def binned_median(ax, x, y, color, label, label_xy, min_n=30):
    """Median per log-spaced size bin, as a line with the p5-p95 band; bins under min_n
    series are left out."""
    b = pd.cut(x, MVOX_BINS)
    g = pd.DataFrame({"x": x, "y": y, "b": b}).groupby("b", observed=True)
    s = g.agg(x=("x", "median"), med=("y", "median"), lo=("y", lambda v: v.quantile(.05)),
              hi=("y", lambda v: v.quantile(.95)), n=("y", "size"))
    s = s[s.n >= min_n]
    ax.fill_between(s.x, s.lo, s.hi, color=color, alpha=0.15, lw=0, zorder=2)
    ax.plot(s.x, s.med, color=color, lw=2, zorder=3, solid_capstyle="round")
    ax.annotate(label, label_xy, ha="right", va="center", fontsize=6.5, color=INK, bbox=LABEL_BOX,
                zorder=4)
    return s


def cs1_peak_memory(cs1, peak, fail, geo, order):
    """Case study 1's peak RAM per series, and against case study 2 at the same scan size.
    Series that TotalSegmentator never ran on (its time logged as 0; 37 of 137,113) are
    left out: their peak is the idle VM's."""
    cs1 = cs1[cs1.totalsegmentator_s > 0]
    fig = plt.figure(figsize=(FULL_W, 5.0))
    gs = fig.add_gridspec(2, 2, height_ratios=[0.8, 1.2], hspace=0.6, wspace=0.32)
    table = []

    # A: case study 1 per run, against its VM.
    ax = fig.add_subplot(gs[0, :])
    for y, (cohort, label) in enumerate(CS1_RUNS):
        v = cs1[cs1.cohort == cohort].peak_gib
        s = range_bar(ax, y, v, STUDY_COLOR["cs1"], lambda x: f"{x:.1f} GiB", horizontal=True,
                      width=0.5, tukey=True, seed=y, label="above")
        table.append(dict(panel="A", series=f"case study 1, {cohort}", **s))
    ram = cs1.vm_ram_gib.max()
    ax.vlines(ram, -0.5, len(CS1_RUNS) - 0.5, color=INK, lw=1.4, zorder=4)
    ax.annotate(f"VM RAM, {CS1_GPU_RAM} GiB ({ram:.1f} usable)", (ram, -0.5), xytext=(-3, 0),
                textcoords="offset points", ha="right", va="center", fontsize=6, color=INK)
    ax.set_yticks(range(len(CS1_RUNS)), [f"{lab}  (n = {(cs1.cohort == c).sum():,})" for c, lab in CS1_RUNS])
    ax.set_ylim(len(CS1_RUNS) - 0.4, -0.9)
    ax.set_xlim(0, 14)
    ax.spines["left"].set_visible(False)
    value_grid(ax, "x")
    ax.set_xlabel("Peak RAM in use on the GPU VM per series (GiB): case study 1, TotalSegmentator 1.5.6 total")
    panel_label(ax, "A", x=-0.2)

    # B: peak against size at TotalSegmentator's working resolution, both case studies.
    # Case study 2 leaves out tasks that ran after a failure in the same attempt, which
    # carry RAM left behind by a timed-out task.
    after = order[order.failures_before > 0].set_index(["workflow", "SeriesInstanceUID"]).index
    t = peak[(peak.vm == "GPU") & (peak.unit == "total")].merge(geo, on="SeriesInstanceUID")
    t = t[~t.set_index(["workflow", "SeriesInstanceUID"]).index.isin(after)].dropna(subset=["mvox_1p5mm"])
    c1 = cs1.dropna(subset=["mvox_1p5mm"])
    axb = fig.add_subplot(gs[1, 0])
    axb.scatter(c1.mvox_1p5mm, c1.peak_gib, s=1.5, color=STUDY_COLOR["cs1"], alpha=0.06,
                linewidths=0, rasterized=True, zorder=1)
    axb.scatter(t.mvox_1p5mm, t.peak_gb, s=2.5, color=STUDY_COLOR["cs2"], alpha=0.35,
                linewidths=0, rasterized=True, zorder=1)
    for key, x, y, lab, xy in [("cs1", c1.mvox_1p5mm, c1.peak_gib, "case study 1", (80, 4.3)),
                               ("cs2", t.mvox_1p5mm, t.peak_gb, "case study 2", (28, 11))]:
        s = binned_median(axb, x, y, STUDY_COLOR[key], lab, xy)
        table += [dict(panel="B", series=lab, mvox_1p5mm=r.x, median=r.med, p5=r.lo, p95=r.hi, n=r.n)
                  for r in s.itertuples()]
    f = fail[(fail.model == "TotalSegmentator") & (fail.unit == "total")
             & fail.cause.isin(["killed (signal 9)", "export worker killed (RAM)", "timed out (90 min cap)"])]
    f = f.drop_duplicates("SeriesInstanceUID").merge(geo, on="SeriesInstanceUID")
    axb.scatter(f.mvox_1p5mm, f.run_peak_gb, **FAIL_MARK)
    table.append(dict(panel="B", series="case study 2 total, failed (memory)", n=len(f),
                      min=f.mvox_1p5mm.min(), max=f.mvox_1p5mm.max()))
    for r, lab, style in [(CS1_GPU_RAM, f"case study 1 VM, {CS1_GPU_RAM} GiB", dict(color=MUTED, lw=0.8, ls=(0, (3, 2)))),
                          (VM_RAM[("GPU", "TotalSegmentator")], "case study 2 VM, 26 GiB", dict(color=INK, lw=1))]:
        axb.axhline(r, **style, zorder=0)
        axb.annotate(lab, (0.02, r), xycoords=("axes fraction", "data"), xytext=(0, 2),
                     textcoords="offset points", fontsize=6, color=style["color"])
    axb.set_ylim(0, 28)
    axb.set_ylabel("Peak RAM, TotalSegmentator total (GiB)")
    axb.legend(handles=[plt.Line2D([], [], ls="", marker="x", color=INK, markeredgewidth=0.9,
                                   markersize=4, label="case study 2, failed (memory)")],
               loc="upper left", bbox_to_anchor=(0, 0.9), fontsize=6, frameon=False)
    panel_label(axb, "B", x=-0.2)

    # C: how many series each cohort has at each size.
    axc = fig.add_subplot(gs[1, 1], sharex=axb)
    two = geo[geo.SeriesInstanceUID.isin(peak.SeriesInstanceUID)].mvox_1p5mm.dropna()
    for key, v, lab in [("cs1", c1.drop_duplicates("SeriesInstanceUID").mvox_1p5mm, "NLST (case study 1)"),
                        ("cs2", two, "CPTAC and CMB (case study 2)")]:
        v = np.sort(v.to_numpy())
        share = 1 - np.arange(len(v)) / len(v)
        axc.step(v, 100 * share, where="post", color=STUDY_COLOR[key], lw=2)
        i = np.searchsorted(v, 30)
        table.append(dict(panel="C", series=lab, n=len(v), median=np.median(v), max=v.max(),
                          share_over_30_mvox=100 * (1 - i / len(v))))
    axc.annotate("NLST\n(case study 1)", (15, 0.5), ha="right", va="center", fontsize=6.5,
                 color=INK, bbox=LABEL_BOX)
    axc.annotate("CPTAC and CMB\n(case study 2)", (45, 20), ha="left", va="center", fontsize=6.5,
                 color=INK, bbox=LABEL_BOX)
    axc.set_yscale("log")
    axc.set_ylim(0.01, 130)
    axc.set_yticks([0.01, 0.1, 1, 10, 100], ["0.01%", "0.1%", "1%", "10%", "100%"])
    axc.minorticks_off()
    axc.set_ylabel("Series at least this large")
    panel_label(axc, "C", x=-0.2)

    for a in (axb, axc):
        a.set_xscale("log")
        a.set_xlim(3, 200)
        a.set_xticks([3, 10, 30, 100], ["3", "10", "30", "100"])
        a.minorticks_off()
        a.set_xlabel("Voxels after resampling to 1.5 mm (millions, log scale)")
        value_grid(a, "y")
    save(fig, "cs1-peak-memory", table)


def main():
    attempts = pd.read_csv(DATA / "cs2_task_attempts.csv.gz")
    steps = pd.read_csv(DATA / "cs2_step_times.csv.gz")
    costs = pd.read_csv(DATA / "cs2_costs_by_workflow.csv.gz")
    runs = pd.read_csv(DATA / "cs2_runs.csv.gz")
    peak = pd.read_csv(DATA / "cs2_peak_memory.csv.gz")
    fail = pd.read_csv(DATA / "cs2_inference_failures.csv.gz")
    # Per-series cost over the series submitted, not those with metrics: the failed
    # MOOSE batch was paid for.
    runs["series"] = runs.series.max()
    cs2_stage_times(attempts, steps)
    cs2_cost_breakdown(costs, runs)
    # Geometry and series order from build_series_geometry_cs2.py and build_data_memory.py.
    geo = pd.read_csv(DATA / "cs2_series_geometry.csv.gz")
    order = pd.read_csv(DATA / "cs2_series_order.csv.gz")
    # Memory reruns, from build_data_cs2.py --reruns-only.
    rerun_peak = pd.read_csv(DATA / "cs2_rerun_peak_memory.csv.gz")
    cs2_peak_memory(peak, fail, geo, order, rerun_peak)
    # Case study 1 against case study 2.
    cs1_peak_memory(pd.read_csv(DATA / "cs1_peak_memory.csv.gz"), peak, fail, geo, order)


if __name__ == "__main__":
    main()
