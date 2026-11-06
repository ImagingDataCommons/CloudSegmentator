# /// script
# requires-python = ">=3.11"
# dependencies = ["pandas>=2.2", "matplotlib==3.11.2", "numpy"]
# ///
"""Draw the case study 2 figures - cs2-stage-times, cs2-cost-breakdown, cs2-peak-memory and
cs2-structures - and cs1-peak-memory and idc-structures from paper/data/ (see
build_data_cs2.py and build_data_structures_*.py).

    uv run paper/make_figures_cs2.py

Same style and conventions as make_figures.py, whose helpers it reuses: colour is
the kind of VM (blue GPU, orange CPU); boxes span the IQR with the median marked
and printed; whiskers at 1.5 IQR with every batch beyond drawn, as in stage-times.
"""

import textwrap

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import to_rgb
from matplotlib.legend_handler import HandlerTuple
from matplotlib.patches import Patch
from matplotlib.ticker import NullLocator
from matplotlib.transforms import ScaledTranslation

from make_figures import (AXIS, CATEGORICAL, COST_CATS, DATA, FULL_W, INK, INK2, LABEL_BOX, MUTED,
                          NEUTRAL, VM_COLOR, cost_share_bars, panel_label, range_bar, save,
                          value_grid)

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

# The case study 2 cohort, as checked against the data.
COHORT = {"CT series": 3059, "patients": 578, "collections": 18}
# Every structure in cs2_structures, grouped by hand for the figure. Spine and ribs are
# in anatomical order, so their bars trace the usual scan range; the other groups are
# sorted by count.
RIBS = ["First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh", "Eighth", "Ninth",
        "Tenth", "Eleventh", "Twelfth"]
STRUCTURE_GROUPS = {
    "Body regions and tissue": ["Trunk", "Head", "Upper limb", "Lower limb",
                                "Skeletal muscle structure", "Adipose tissue of abdomen",
                                "Subcutaneous fat"],
    "Organs": ["Brain", "Spinal cord", "Thyroid gland", "Esophagus", "Stomach", "Duodenum",
               "Small Intestine", "Colon", "Liver", "Gallbladder", "Pancreas", "Spleen",
               "Adrenal gland", "Kidney", "Kidney cyst", "Urinary bladder", "Prostate"],
    "Lungs and airways": ["Trachea", "Trachea and bronchus", "Upper lobe of lung",
                          "Middle lobe of right lung", "Lower lobe of lung"],
    "Heart and vessels": ["Heart", "Myocardium", "Left atrium", "Right atrium",
                          "Left ventricle of heart", "Right ventricle of heart",
                          "Auricular appendage", "Aorta", "Pulmonary artery", "Pulmonary vein",
                          "Superior vena cava", "Inferior vena cava", "Brachiocephalic artery",
                          "Brachiocephalic vein", "Subclavian artery", "Common carotid artery",
                          "Common iliac artery", "Common iliac vein",
                          "Portal vein and splenic vein"],
    "Muscles": ["Deep muscle of back", "Iliopsoas muscle", "Gluteus maximus muscle",
                "Gluteus medius muscle", "Gluteus minimus muscle"],
    "Spine": ([f"C{i} vertebra" for i in range(1, 8)] + [f"T{i} vertebra" for i in range(1, 13)]
              + [f"L{i} vertebra" for i in range(1, 7)] + ["S1 vertebra", "Sacrum"]),
    "Ribs and sternum": [f"{r} rib" for r in RIBS] + ["Costal cartilage", "Sternum"],
    "Other bones": ["Skull", "Clavicle", "Scapula", "Humerus", "Radius", "Ulna", "Carpus",
                    "Metacarpal bones", "Fingers", "Hip", "Femur", "Patella", "Tibia", "Fibula",
                    "Tarsal bones", "Metatarsal", "Toe"],
}
ANATOMICAL_ORDER = {"Spine", "Ribs and sternum"}
# A hue per group, in an order where neighbouring groups stay apart in colour-vision
# deficiency too (dataviz validate_palette.js, light: all checks pass, worst pair ΔE 15.2).
GROUP_COLOR = dict(zip(STRUCTURE_GROUPS, ["#6250d6", "#eb6834", "#2a78d6", "#e34948", "#eda100",
                                          "#e87ba4", "#008300", "#1baf7a"]))
# Two rows, to fill a half-width cell beside the two-row example case.
STRUCTURE_ROWS = [["Body regions and tissue", "Organs", "Lungs and airways", "Heart and vessels",
                   "Muscles"],
                  ["Spine", "Ribs and sternum", "Other bones"]]
# Bars named on the axis: the levels that orient the spine and ribs.
STRUCTURE_TICKS = {"C1 vertebra": "C1", "T1 vertebra": "T1", "L1 vertebra": "L1",
                   "S1 vertebra": "S1", "First rib": "1", "Twelfth rib": "12"}
# Bars named above. Upright beside the bar where tall neighbours leave no room...
STRUCTURE_CALLOUTS = ["Head", "Prostate", "Brain"]
# ...and level, on a leader that rises and turns right (+1) or left (-1), where there is: below
# the all-series line, or on one of two levels above it. Where two leaders share a span, the
# one further back takes the upper level, so no leader crosses a name. L6 is an anatomical
# variant, and only MOOSE segments it.
ABOVE_LINE = (3400, 3880)
STRUCTURE_ELBOWS = {
    "Subcutaneous fat": ("Subcutaneous fat", ABOVE_LINE[1], 1),
    "Liver": ("Liver", ABOVE_LINE[0], 1),
    "Thyroid gland": ("Thyroid gland", ABOVE_LINE[1], 1),
    "Trachea": ("Trachea", ABOVE_LINE[0], -1),
    "Aorta": ("Aorta", ABOVE_LINE[0], 1),
    "Iliopsoas muscle": ("Iliopsoas muscle", ABOVE_LINE[1], -1),
    "L6 vertebra": ("L6", 2150, 1),
    "Sternum": ("Sternum", ABOVE_LINE[0], 1),
    "Femur": ("Femur", 2700, 1),
    "Skull": ("Skull", 2250, 1),
    "Fingers": ("Fingers", 1800, 1),
    "Toe": ("Toe", 1350, 1),
}

# The same groups for every structure segmented in IDC, with what only IDC has. Kidney
# cyst joins the lesions, which are not anatomy and so take no hue of their own. "Normal"
# is normal-appearing peripheral zone, marked beside prostate lesions.
LESIONS = "Lesions and findings"
IDC_GROUPS = {g: [s for s in names if s != "Kidney cyst"] for g, names in STRUCTURE_GROUPS.items()}
IDC_GROUPS["Body regions and tissue"] += ["Face", "upper arm"]
IDC_GROUPS["Organs"] += ["Breast", "Breast Fibroglandular Tissue", "Fatty tissue of breast",
                         "Peripheral zone of prostate", "Transition zone of prostate",
                         "Anterior fibromuscular stroma of prostate", "Prostatic Urethra",
                         "Brain ventricle", "Mediastinal lymph node", "abdominal lymph node"]
IDC_GROUPS["Lungs and airways"] += ["Lung"]
IDC_GROUPS["Heart and vessels"] += ["Abdominal aorta", "Portal vein", "Vein"]
IDC_GROUPS[LESIONS] = ["Nodule", "Mass", "Lesion", "Neoplasm", "Neoplasm, Primary",
                       "Morphologically Abnormal Structure", "Tissue", "FDG-Avid Tumor",
                       "DWI Tumor", "Enhancing Lesion", "Edema", "Necrosis", "Glioma",
                       "Residual tumor", "Excision of brain", "Kidney cyst", "Normal"]
IDC_GROUP_COLOR = GROUP_COLOR | {LESIONS: NEUTRAL}
IDC_ROWS = [STRUCTURE_ROWS[0], STRUCTURE_ROWS[1] + [LESIONS]]
# Every bar is named on the axis, so long names are shortened there; the values table keeps
# them whole.
IDC_SHORT = ({f"{c}{i} vertebra": f"{c}{i}" for c, n in [("C", 7), ("T", 12), ("L", 6)]
              for i in range(1, n + 1)}
             | {f"{r} rib": f"Rib {i}" for i, r in enumerate(RIBS, 1)}
             | {"S1 vertebra": "S1", "Skeletal muscle structure": "Skeletal muscle",
                "Adipose tissue of abdomen": "Abdominal fat", "upper arm": "Upper arm",
                "Small Intestine": "Small intestine", "Breast Fibroglandular Tissue":
                "Fibroglandular tissue", "Fatty tissue of breast": "Breast fat",
                "Peripheral zone of prostate": "Peripheral zone",
                "Transition zone of prostate": "Transition zone",
                "Anterior fibromuscular stroma of prostate": "Fibromuscular stroma",
                "Prostatic Urethra": "Prostatic urethra",
                "abdominal lymph node": "Abdominal lymph node",
                "Upper lobe of lung": "Upper lobe", "Lower lobe of lung": "Lower lobe",
                "Middle lobe of right lung": "Middle lobe",
                "Left ventricle of heart": "Left ventricle",
                "Right ventricle of heart": "Right ventricle",
                "Portal vein and splenic vein": "Portal and splenic vein",
                "Deep muscle of back": "Deep back muscle", "Iliopsoas muscle": "Iliopsoas",
                "Gluteus maximus muscle": "Gluteus maximus",
                "Gluteus medius muscle": "Gluteus medius",
                "Gluteus minimus muscle": "Gluteus minimus",
                "Neoplasm, Primary": "Primary neoplasm",
                "Morphologically Abnormal Structure": "Abnormal structure",
                "Enhancing Lesion": "Enhancing lesion"})
FADED = 0.35  # share of the group hue in a bar's IDC part, the rest white


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
    fig = plt.figure(figsize=(FULL_W, 5.7))
    # Two grids, so the scatter row can use the width panel A gives to its row labels.
    # The gap between them holds panel A's legend.
    ax = fig.add_subplot(fig.add_gridspec(1, 1, left=0.3, right=0.98, top=0.97, bottom=0.62)[0])
    gs = fig.add_gridspec(1, 3, left=0.09, right=0.98, top=0.425, bottom=0.13, wspace=0.1)
    table, ticks, labels, y = [], [], [], 0
    for i, (vm, model, unit, label) in enumerate(MEM_ROWS):
        if i in (0, 3):
            ticks.append(y), labels.append("GPU VM: input conversion and inference" if vm == "GPU"
                                           else "CPU VM: output conversion")
            y += 1
        v = peak[(peak.vm == vm) & (peak.model == model) & (peak.unit == unit)].peak_gb
        # Median above the box: past the whisker it collides with the outliers and failures.
        s = range_bar(ax, y, v, VM_COLOR[vm], lambda x: f"{x:.1f} GiB", horizontal=True,
                      width=0.5, tukey=True, seed=i, label="above")
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
    # Panel A has its own legend, so it keys every black mark it draws; the figure legend
    # below reuses the same keys.
    fail_key = plt.Line2D([], [], ls="", marker="x", color=INK, markeredgewidth=0.9,
                          markersize=4, label="failed, memory-related")
    rerun_key = plt.Line2D([], [], ls="", marker="o", markerfacecolor="none", color=INK,
                           markeredgewidth=0.8, markersize=4, label="rerun with more RAM, succeeded")
    # One row under the axis label, like the legend of B-D: inside the axes it crowds the marks.
    ax.legend(handles=[plt.Line2D([], [], color=INK, lw=1.4, label="VM RAM"), fail_key, rerun_key],
              loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=3, fontsize=6, frameon=False)
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
                        fail_key, rerun_key,
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


def lay_out(structures, groups, rows):
    """A slot per structure, group after group along each row, two slots between groups.
    Returns the structures with their group, row and slot; each group's (row, first slot,
    last slot); and the slots in the longest row."""
    listed = [s for names in groups.values() for s in names]
    assert sorted(listed) == sorted(structures.meaning), set(listed) ^ set(structures.meaning)
    assert [g for row in rows for g in row] == list(groups)
    by_name = structures.set_index("meaning")
    parts, spans, width = [], {}, 0
    for i, row in enumerate(rows):
        x0 = 0
        for group in row:
            g = by_name.loc[groups[group]].reset_index()
            if group not in ANATOMICAL_ORDER:
                g = g.sort_values("n_series", ascending=False, kind="stable")
            g.insert(0, "group", group)
            g["row"], g["x"] = i, np.arange(x0, x0 + len(g))
            parts.append(g)
            spans[group] = (i, x0, x0 + len(g) - 1)
            x0 += len(g) + 2
        width = max(width, x0 - 2)
    return pd.concat(parts, ignore_index=True), spans, width


def cs2_structures(structures):
    """cs2-structures: for every structure either tool segments, the CT series it was found
    in, both tools and all twelve models pooled. The values table is the full list, with
    SNOMED codes and the count per tool."""
    t, spans, width = lay_out(structures, STRUCTURE_GROUPS, STRUCTURE_ROWS)
    at = {m: (r, x, n) for m, r, x, n in zip(t.meaning, t.row, t.x, t.n_series)}
    height = {(r, x): n for r, x, n in zip(t.row, t.x, t.n_series)}
    n_ct = COHORT["CT series"]

    # Half the double-column width, shaped like the example case beside it.
    fig, axs = plt.subplots(len(STRUCTURE_ROWS), 1, figsize=(FULL_W / 2, 2.88), sharey=True)
    fig.subplots_adjust(left=0.13, right=0.995, top=0.875, bottom=0.11, hspace=0.62)
    for i, ax in enumerate(axs):
        r = t[t.row == i]
        ax.bar(r.x, r.n_series, width=0.7, color=r.group.map(GROUP_COLOR), lw=0, zorder=2)
        ax.axhline(n_ct, color=MUTED, lw=0.6, ls=(0, (3, 2)), zorder=1)
        ax.set_xlim(-1, width)
        ax.set_ylim(0, 4000)
        ax.set_yticks([0, 1000, 2000, 3000], ["0", "1,000", "2,000", "3,000"])
        value_grid(ax, "y")
        ticks = [(at[s][1], lab) for s, lab in STRUCTURE_TICKS.items() if at[s][0] == i]
        ax.set_xticks([x for x, _ in ticks], [lab for _, lab in ticks], fontsize=6)
        # Groups as brackets under the axis, as in the example case beside it.
        tr = ax.get_xaxis_transform() + ScaledTranslation(0, -11 / 72, fig.dpi_scale_trans)
        end = 2 / 72 / (ax.get_position().height * fig.get_figheight())  # 2 pt, in axes units
        for group, (row, a, b) in spans.items():
            if row != i:
                continue
            ax.plot([a - 0.4, a - 0.4, b + 0.4, b + 0.4], [end, 0, 0, end], transform=tr,
                    color=AXIS, lw=0.6, clip_on=False)
            ax.annotate("\n".join(textwrap.wrap(group, 12)), ((a + b) / 2, 0), xycoords=tr,
                        xytext=(0, -2), textcoords="offset points", ha="center", va="top",
                        fontsize=6.5, color=INK2, annotation_clip=False)
    # A name is wider than a bar, so it starts clear of the taller neighbour, with a leader.
    leader = dict(arrowstyle="-", color=MUTED, lw=0.5, shrinkA=0, shrinkB=1)
    for name in STRUCTURE_CALLOUTS:
        i, x, n = at[name]
        top = max(height.get((i, x + d), 0) for d in (-1, 0, 1))
        axs[i].annotate(name, (x, n), xytext=(x, top + 60), textcoords="data", rotation=90,
                        ha="center", va="bottom", fontsize=6, color=INK2,
                        arrowprops=leader if top > n + 100 else None)
    for name, (label, y, side) in STRUCTURE_ELBOWS.items():
        i, x, n = at[name]
        axs[i].annotate(label, (x, n), xytext=(x + side, y), textcoords="data",
                        ha="left" if side > 0 else "right", va="center", fontsize=6, color=INK2,
                        arrowprops=leader | dict(connectionstyle="angle,angleA=0,angleB=90,rad=0"))
    # On the lower row, as the upper one has names above the line at the right.
    axs[-1].annotate("all series", (1, n_ct), xycoords=("axes fraction", "data"),
                    xytext=(0, 2), textcoords="offset points", ha="right", va="bottom",
                    fontsize=6, color=MUTED)
    fig.supylabel("CT series with the structure", x=0.01, fontsize=7.5, color=INK2)
    fig.text(0.995, 0.995, f"{n_ct:,} CT series · {COHORT['patients']} patients · "
             f"{COHORT['collections']} collections", ha="right", va="top", fontsize=7.5,
             color=INK)
    fig.text(0.995, 0.945, f"{len(t)} structures · {t.n_segments.sum():,} segments",
             ha="right", va="top", fontsize=6.5, color=INK2)

    table = pd.DataFrame({
        "group": t.group, "structure": t.meaning.str.capitalize(), "snomed_code": t.code,
        "models": t.models, "ct_series": t.n_series,
        "ct_series_totalsegmentator": t.n_series_totalsegmentator,
        "ct_series_moose": t.n_series_moose, "segments": t.n_segments})
    save(fig, "cs2-structures", table)


def idc_structures(structures, totals):
    """idc-structures: for every structure segmented in IDC v25 on CT, MR or PET, or by case
    study 2, the series it was segmented in, on a log axis. A bar's faded part is IDC before
    case study 2; the solid part on top is the CT series case study 2 adds, those where no
    SEG in IDC had the structure. The values table is the full list, with codes, the count
    per modality and the IDC sources."""
    t, spans, width = lay_out(structures, IDC_GROUPS, IDC_ROWS)
    fade = lambda c: 1 - FADED * (1 - np.array(to_rgb(c)))  # noqa: E731
    floor = 0.6  # a log axis has no zero; one series still shows

    fig, axs = plt.subplots(len(IDC_ROWS), 1, figsize=(FULL_W, 5.2), sharey=True)
    fig.subplots_adjust(left=0.07, right=0.995, top=0.885, bottom=0.135, hspace=0.95)
    for i, ax in enumerate(axs):
        r = t[t.row == i]
        hue = r.group.map(IDC_GROUP_COLOR)
        ax.bar(r.x, r.n_series - floor, bottom=floor, width=0.72, color=hue, lw=0, zorder=2)
        idc = r[r.n_series_idc > 0]
        ax.bar(idc.x, idc.n_series_idc - floor, bottom=floor, width=0.72, lw=0, zorder=3,
               color=[fade(c) for c in idc.group.map(IDC_GROUP_COLOR)])
        ax.set_yscale("log")
        ax.set_ylim(floor, 4e5)
        ax.set_yticks([10 ** k for k in range(6)], [f"{10 ** k:,}" for k in range(6)])
        ax.yaxis.set_minor_locator(NullLocator())
        value_grid(ax, "y")
        ax.set_xlim(-1, width)
        ax.set_xticks(r.x, [IDC_SHORT.get(m, m) for m in r.meaning], rotation=90, fontsize=5)
        ax.tick_params(axis="x", pad=2)
        # Groups named above, over a rule in their hue.
        for group, (row, a, b) in spans.items():
            if row != i:
                continue
            ax.plot([a - 0.4, b + 0.4], [1.03, 1.03], transform=ax.get_xaxis_transform(),
                    color=IDC_GROUP_COLOR[group], lw=1, solid_capstyle="butt", clip_on=False)
            ax.annotate(group, ((a + b) / 2, 1.03), xycoords=ax.get_xaxis_transform(),
                        xytext=(0, 2), textcoords="offset points", ha="center", va="bottom",
                        fontsize=6.5, color=INK2, annotation_clip=False)
    fig.supylabel("Series with the structure", x=0.005, fontsize=7.5, color=INK2)

    tot = totals.set_index("modality")
    n_idc = tot.n_series_idc.sum()
    added = tot.n_series.sum() - n_idc
    hues = list(IDC_GROUP_COLOR.values())
    fig.legend([tuple(Patch(color=fade(c)) for c in hues), tuple(Patch(color=c) for c in hues)],
               ["Segmented in IDC v25", "Added by case study 2"],
               handler_map={tuple: HandlerTuple(ndivide=None, pad=0)}, handlelength=4,
               handleheight=0.8, loc="upper left", bbox_to_anchor=(0.06, 0.972), ncols=2,
               columnspacing=1.5, borderaxespad=0)
    fig.text(0.995, 0.995, f"{n_idc:,} series segmented in IDC v25 "
             f"({tot.n_series_idc.CT:,} CT · {tot.n_series_idc.MR:,} MR · "
             f"{tot.n_series_idc.PT:,} PET), {added:,} more CT series by case study 2",
             ha="right", va="top", fontsize=7.5, color=INK)
    fig.text(0.995, 0.965, f"{len(t)} structures · {tot.n_segments_idc.sum():,} segments in "
             f"IDC, {t.n_segments_cs2.sum():,} from case study 2", ha="right", va="top",
             fontsize=6.5, color=INK2)

    table = pd.DataFrame({
        "group": t.group, "structure": t.meaning.str[:1].str.upper() + t.meaning.str[1:],
        "codes": t.codes, "series": t.n_series, "series_idc": t.n_series_idc,
        "series_idc_ct": t.n_series_idc_ct, "series_idc_mr": t.n_series_idc_mr,
        "series_idc_pet": t.n_series_idc_pt, "series_idc_case_study_1": t.n_series_cs1,
        "series_case_study_2": t.n_series_cs2,
        "series_added_by_case_study_2": t.n_series_cs2_new, "idc_sources": t.idc_sources})
    save(fig, "idc-structures", table)


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
    # Structures found, from build_data_structures_cs2.py.
    cs2_structures(pd.read_csv(DATA / "cs2_structures.csv.gz", dtype={"code": str}))
    # The same, over every structure segmented in IDC, from build_data_structures_idc.py.
    idc_structures(pd.read_csv(DATA / "idc_structures.csv.gz"),
                   pd.read_csv(DATA / "idc_structures_totals.csv.gz"))


if __name__ == "__main__":
    main()
