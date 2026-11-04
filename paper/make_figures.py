# /// script
# requires-python = ">=3.11"
# dependencies = ["pandas>=2.2", "matplotlib==3.11.2", "numpy"]
# ///
"""Draw the case study 1 execution-analytics figures from paper/data/ (see build_data.py).

    uv run paper/make_figures.py

Writes vector PDF and 300 dpi PNG to paper/out/, plus a CSV of the plotted
values for each figure. A figure's files, and the function that draws it, are named
by its keyword; README.md lists which figure of the paper each keyword is.
SB-CGC is omitted throughout.

Colour means the kind of VM a task ran on - blue GPU, orange CPU - in every
figure. Distributions are drawn as a box spanning the interquartile range, a bar
at the median (value printed) and whiskers: 5th-95th percentile, except in stage-times,
which follows the original Tableau figure (1.5 IQR, every batch beyond drawn).
"""

from pathlib import Path

import matplotlib as mpl
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch, Rectangle

HERE = Path(__file__).parent
DATA, OUT = HERE / "data", HERE / "out"

INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"
NEUTRAL = "#52514e"  # marks that carry no categorical identity
VM_COLOR = {"GPU": "#2a78d6", "CPU": "#eb6834"}
CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
COST_CATS = ["GPU", "CPU", "RAM", "Network egress", "External IP", "Disk"]
FULL_W = 7.0  # inches, double column

TASK_VM = {
    "totalSegmentatorEndToEnd": "GPU",
    "downloadDicomAndConvertAndInferenceTotalSegmentator": "GPU",
    "inferenceTotalSegmentator": "GPU",
    "downloadAndConvert": "CPU",
    "dicomsegAndRadiomicsSR": "CPU",
}
TASK_SHORT = {
    "totalSegmentatorEndToEnd": "All steps",
    "downloadDicomAndConvertAndInferenceTotalSegmentator": "Conversion\n+ inference",
    "downloadAndConvert": "Conversion",
    "inferenceTotalSegmentator": "Inference",
    "dicomsegAndRadiomicsSR": "Features\n+ output",
}
TASK_ORDER = list(TASK_SHORT)
CONFIGS = ["oneVM", "twoVM", "threeVM"]
COHORTS = ["1k", "10k", "126k"]
# Series per cohort, as in Table 1 (its cost per series is total / these) and in the name
# of the Terra API export, terra_api_data_1037_10000_126088_series_021524.csv.
COHORT_SERIES = {"1k": 1037, "10k": 10000, "126k": 126088}
REGION_NAME = {
    "us-west4": "us-west4 (Las Vegas)",
    "us-east4": "us-east4 (N. Virginia)",
    "europe-west4": "europe-west4 (Netherlands)",
    "europe-west2": "europe-west2 (London)",
    "asia-northeast1": "asia-northeast1 (Tokyo)",
    "asia-southeast1": "asia-southeast1 (Singapore)",
}

mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "font.size": 7.5, "axes.labelsize": 7.5, "xtick.labelsize": 7, "ytick.labelsize": 7,
    "legend.fontsize": 7, "legend.frameon": False,
    "text.color": INK, "axes.labelcolor": INK2,
    "axes.edgecolor": AXIS, "axes.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False,
    "xtick.color": AXIS, "ytick.color": AXIS, "xtick.labelcolor": INK2, "ytick.labelcolor": INK2,
    "xtick.major.size": 0, "ytick.major.size": 0, "xtick.major.pad": 3, "ytick.major.pad": 3,
    "grid.color": GRID, "grid.linewidth": 0.5,
    "pdf.fonttype": 42, "ps.fonttype": 42,
    "savefig.dpi": 300, "savefig.bbox": "tight", "savefig.pad_inches": 0.03,
})


# ---------------------------------------------------------------- helpers

def value_grid(ax, axis):
    ax.grid(True, axis=axis)
    ax.set_axisbelow(True)


def panel_label(ax, letter, x=-0.12):
    ax.text(x, 1.06, letter, transform=ax.transAxes, fontsize=9, fontweight="bold",
            ha="left", va="bottom", color=INK)


def text_on(hex_color):
    """White or ink, whichever reads on a fill of this colour."""
    rgb = np.array(mpl.colors.to_rgb(hex_color))
    lin = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    lum = lin @ [0.2126, 0.7152, 0.0722]
    return "white" if 1.05 / (lum + 0.05) >= 3 else INK


LABEL_BOX = dict(boxstyle="round,pad=0.12", facecolor="white", edgecolor="none", alpha=0.85)
MIN_N_FOR_BOX = 10  # below this, percentiles mean little: draw the points and the median


def range_bar(ax, pos, values, color, fmt, horizontal=False, width=0.46, points=False, seed=0,
              label="end", tukey=False):
    """Whisker line, IQR box, median bar and its printed value. Returns the stats.

    Whiskers span p5-p95 by default. tukey=True puts them at the furthest values within
    1.5 IQR of the box and draws every value beyond as a point (the convention of the
    original Tableau figures). points=True draws every value. label="end" prints the
    median past the whisker end (horizontal only); "above" prints it above the whisker
    (vertical) or above the box (horizontal)."""
    v = np.asarray(values, float)
    v = v[np.isfinite(v)]
    p5, q1, med, q3, p95 = np.percentile(v, [5, 25, 50, 75, 95])
    lo, hi = p5, p95
    if tukey:
        lo = v[v >= q1 - 1.5 * (q3 - q1)].min()
        hi = v[v <= q3 + 1.5 * (q3 - q1)].max()
    few = len(v) < MIN_N_FOR_BOX
    if points or few or tukey:
        shown = v if (points or few) else v[(v < lo) | (v > hi)]
        jit = np.random.default_rng(seed).uniform(-width / 2.4, width / 2.4, len(shown))
        xy = (shown, pos + jit) if horizontal else (pos + jit, shown)
        ax.scatter(*xy, s=9 if few else 2.5, color=color, alpha=0.8 if few else 0.35,
                   linewidths=0, zorder=1, rasterized=not few)
    if horizontal:
        if not few:
            ax.hlines(pos, lo, hi, color=color, lw=1, zorder=2)
            ax.add_patch(Rectangle((q1, pos - width / 2), q3 - q1, width, facecolor=color,
                                   alpha=0.25, lw=0, zorder=2))
        ax.vlines(med, pos - width / 2, pos + width / 2, color=color, lw=2, zorder=3)
        if label == "end":
            ax.annotate(fmt(med), (max(hi, v.max() if few else hi), pos), xytext=(4, 0),
                        textcoords="offset points", ha="left", va="center", fontsize=6.5,
                        color=INK, bbox=LABEL_BOX, zorder=4)
        else:
            ax.annotate(fmt(med), (med, pos - width / 2), xytext=(0, 1.5), textcoords="offset points",
                        ha="center", va="bottom", fontsize=6.5, color=INK, bbox=LABEL_BOX, zorder=4)
    else:
        if not few:
            ax.vlines(pos, lo, hi, color=color, lw=1, zorder=2)
            ax.add_patch(Rectangle((pos - width / 2, q1), width, q3 - q1, facecolor=color,
                                   alpha=0.25, lw=0, zorder=2))
        ax.hlines(med, pos - width / 2, pos + width / 2, color=color, lw=2, zorder=3)
        ax.annotate(fmt(med), (pos, hi), xytext=(0, 3), textcoords="offset points", ha="center",
                    va="bottom", fontsize=6.5, color=INK, bbox=LABEL_BOX, zorder=4)
    return dict(n=len(v), min=v.min(), p5=p5, q1=q1, median=med, q3=q3, p95=p95, max=v.max())


def vm_legend(ax, **kw):
    handles = [Patch(color=VM_COLOR[k], label=f"{k} VM") for k in VM_COLOR]
    ax.legend(handles=handles, handlelength=1, handleheight=0.8, **kw)


def save(fig, name, table):
    OUT.mkdir(exist_ok=True)
    fig.savefig(OUT / f"{name}.pdf", metadata={"CreationDate": None})  # reproducible bytes
    fig.savefig(OUT / f"{name}.png")
    pd.DataFrame(table).to_csv(OUT / f"{name}_values.csv", index=False)
    plt.close(fig)
    print("wrote", name)


usd = lambda x: f"${x:.2f}"  # noqa: E731
hours = lambda x: f"{x:.2f} h"  # noqa: E731
minutes = lambda x: f"{x:.2f}" if x < 0.1 else f"{x:.1f}"  # noqa: E731


def load():
    runs = pd.read_csv(DATA / "runs.csv.gz")
    batches = pd.read_csv(DATA / "batches.csv.gz", parse_dates=["start", "end"])
    attempts = pd.read_csv(DATA / "task_attempts.csv.gz")
    attempts["vm"] = attempts.task.map(TASK_VM)
    costs = pd.read_csv(DATA / "costs_by_workflow.csv.gz").merge(runs, on="submission")
    stages = pd.read_csv(DATA / "stage_times_126k.csv.gz")
    gpu = pd.read_csv(DATA / "gpu_vms_126k.csv.gz", parse_dates=["running", "terminal"])
    return runs, batches, attempts, costs, stages, gpu


def preemptions(attempts, batches, sel):
    """Preemption events per task as a share of batches, the paper's definition."""
    rows = []
    for (cohort, config), a in attempts[sel(attempts)].groupby(["cohort", "config"]):
        n_batches = len(batches[(batches.cohort == cohort) & (batches.config == config)])
        for task in [t for t in TASK_ORDER if t in set(a.task)]:
            n = int(((a.task == task) & (a.outcome == "Preempted")).sum())
            rows.append(dict(cohort=cohort, config=config, task=task, vm=TASK_VM[task],
                             preemptions=n, batches=n_batches, rate_pct=100 * n / n_batches))
    return pd.DataFrame(rows)


def cost_per_batch(costs):
    return costs.groupby(["cohort", "config", "workflow"]).cost_usd.sum().reset_index()


def preemption_bars(ax, pre, groups, key):
    """Bars per (group, task), coloured by VM kind, labelled with count and rate."""
    x, ticks, labels, centers = 0.0, [], [], []
    for g in groups:
        rows = pre[pre[key] == g].set_index("task").loc[[t for t in TASK_ORDER if t in set(pre[pre[key] == g].task)]]
        start = x
        for task, r in rows.iterrows():
            ax.bar(x, r.rate_pct, width=0.62, color=VM_COLOR[r.vm], lw=0)
            ax.text(x, r.rate_pct + 0.6, f"{r.rate_pct:.1f}%\n({r.preemptions})", ha="center",
                    va="bottom", fontsize=6, color=INK, linespacing=1.05)
            ticks.append(x)
            labels.append(TASK_SHORT[task])
            x += 0.8
        centers.append((start + x - 0.8) / 2)
        x += 0.55
    ax.set_xticks(ticks, labels, fontsize=6.5)
    for c, g in zip(centers, groups):
        ax.text(c, -0.2, g, transform=ax.get_xaxis_transform(), ha="center", va="top",
                fontsize=7.5, fontweight="bold", color=INK)
    ax.set_xlim(-0.6, x - 0.75)
    value_grid(ax, "y")


# ---------------------------------------------------------------- figures

def configurations_1k(runs, batches, attempts, costs):
    """1k cohort on Terra: the three workflow configurations."""
    c1k = costs[costs.cohort == "1k"]
    per_batch = cost_per_batch(c1k)
    ok = batches[(batches.cohort == "1k") & (batches.status == "Succeeded")]
    pre = preemptions(attempts, batches, lambda a: a.cohort == "1k")

    fig = plt.figure(figsize=(FULL_W, 4.5))
    grid = fig.add_gridspec(2, 3, height_ratios=[1, 1.05], hspace=0.62, wspace=0.55)
    a, b, d = (fig.add_subplot(grid[0, i]) for i in range(3))
    c = fig.add_subplot(grid[1, :])
    table = []

    totals = c1k.groupby("config").cost_usd.sum().reindex(CONFIGS)
    a.bar(range(3), totals.values, width=0.5, color=NEUTRAL, lw=0)
    for i, v in enumerate(totals.values):
        a.text(i, v, f"${v:.2f}", ha="center", va="bottom", fontsize=7, color=INK)
        table.append(dict(panel="A", config=CONFIGS[i], total_cost_usd=v))
    a.set_xticks(range(3), CONFIGS)
    a.set_ylim(0, totals.max() * 1.15)
    a.set_ylabel("Total cost (USD)")
    a.yaxis.set_major_formatter(lambda v, _: f"${v:.0f}")
    value_grid(a, "y")

    for i, cfg in enumerate(CONFIGS):
        s = range_bar(b, i, per_batch[per_batch.config == cfg].cost_usd, NEUTRAL, usd, points=True, seed=i)
        table.append(dict(panel="B", config=cfg, **s))
    b.set_ylabel("Cost per batch (USD)")
    b.yaxis.set_major_formatter(lambda v, _: f"${v:.2f}")

    for i, cfg in enumerate(CONFIGS):
        s = range_bar(d, i, ok[ok.config == cfg].wall_clock_h, NEUTRAL, hours, points=True, seed=10 + i)
        table.append(dict(panel="C", config=cfg, **s))
    d.set_ylabel("Batch wall-clock time (h)")
    for ax in (b, d):
        ax.set_xticks(range(3), CONFIGS)
        ax.set_xlim(-0.6, 2.6)
        ax.set_ylim(0, ax.get_ylim()[1] * 1.08)
        value_grid(ax, "y")

    preemption_bars(c, pre, CONFIGS, "config")
    c.set_ylabel("Preemptions (% of batches)")
    c.set_ylim(0, pre.rate_pct.max() * 1.35)
    vm_legend(c, loc="upper right")
    table += [dict(panel="D", **r) for r in pre.to_dict("records")]

    for ax, L in zip([a, b, d], "ABC"):
        panel_label(ax, L, x=-0.42)
    panel_label(c, "D", x=-0.09)
    save(fig, "configurations-1k", table)


def cost_share_bars(ax, series, labels, n_series=None):
    """One 100% bar per row, with the total at the right and, given n_series, the cost
    per series beneath it."""
    table = []
    for i, (lab, s) in enumerate(zip(labels, series)):
        total, left = s.sum(), 0.0
        for j, cat in enumerate(COST_CATS):
            pct = 100 * s.get(cat, 0.0) / total
            ax.barh(i, pct, left=left, height=0.56, color=CATEGORICAL[j], edgecolor="white", linewidth=1.2)
            if pct >= 7:
                ax.text(left + pct / 2, i, f"{pct:.0f}%", ha="center", va="center", fontsize=6.5,
                        color=text_on(CATEGORICAL[j]))
            table.append(dict(row=lab, category=cat, cost_usd=s.get(cat, 0.0), share_pct=pct))
            left += pct
        ax.text(101.5, i, f"${total:,.2f}", ha="left", va="center", fontsize=7, color=INK)
        if n_series is not None:
            ax.text(101.5, i + 0.32, f"${total / n_series[i]:.4f}/series", ha="left", va="center",
                    fontsize=6, color=MUTED)
    ax.set_yticks(range(len(labels)), labels)
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"])
    ax.spines["left"].set_visible(False)
    ax.text(101.5, -0.75, "Total", ha="left", va="center", fontsize=6.5, color=MUTED)
    handles = [Patch(color=CATEGORICAL[j], label=c) for j, c in enumerate(COST_CATS)]
    ax.legend(handles=handles, ncol=6, loc="lower left", bbox_to_anchor=(0, 1.02), handlelength=1,
              handleheight=0.8, columnspacing=1.2, borderaxespad=0)
    return table


def cost_breakdown_1k(costs):
    c = costs[costs.cohort == "1k"]
    series = [c[c.config == cfg].groupby("category").cost_usd.sum() for cfg in CONFIGS]
    fig, ax = plt.subplots(figsize=(FULL_W, 1.55))
    table = cost_share_bars(ax, series, CONFIGS)
    ax.set_xlabel("Share of total cost, 1k cohort")
    save(fig, "cost-breakdown-1k", table)


def cost_breakdown(costs):
    c = costs[costs.config == "twoVM"]
    series = [c[c.cohort == k].groupby("category").cost_usd.sum() for k in COHORTS]
    fig, ax = plt.subplots(figsize=(FULL_W, 1.55))
    table = cost_share_bars(ax, series, COHORTS, [COHORT_SERIES[k] for k in COHORTS])
    ax.set_xlabel("Share of total cost, twoVM configuration")
    save(fig, "cost-breakdown", table)


def cohorts_twovm(batches, attempts, costs):
    """twoVM configuration across the 1k, 10k and 126k cohorts."""
    two = lambda df: df[df.config == "twoVM"]  # noqa: E731
    pre = preemptions(attempts, batches, lambda a: a.config == "twoVM")
    per_batch = cost_per_batch(two(costs))
    ok = two(batches)[two(batches).status == "Succeeded"]
    n_batches = two(batches).groupby("cohort").size()
    cohort_labels = [f"{k}\nn = {n_batches[k]:,}" for k in COHORTS]

    fig, (a, b, c) = plt.subplots(1, 3, figsize=(FULL_W, 2.5), gridspec_kw=dict(wspace=0.45))
    table = []

    x = np.arange(3)
    for off, task in [(-0.17, "downloadDicomAndConvertAndInferenceTotalSegmentator"),
                      (0.17, "dicomsegAndRadiomicsSR")]:
        r = pre[pre.task == task].set_index("cohort").reindex(COHORTS)
        a.bar(x + off, r.rate_pct, width=0.3, color=VM_COLOR[TASK_VM[task]], lw=0)
        for xi, (rate, n) in zip(x + off, zip(r.rate_pct, r.preemptions)):
            a.text(xi, rate + 0.4, f"{rate:.1f}%\n({n:,})", ha="center", va="bottom", fontsize=5.5,
                   linespacing=1.05)
    table += [dict(panel="A", **r) for r in pre.to_dict("records")]
    a.set_xticks(x, cohort_labels)
    a.set_ylim(0, pre.rate_pct.max() * 1.35)
    a.set_ylabel("Preemptions (% of batches)")
    value_grid(a, "y")
    vm_legend(a, loc="upper left", bbox_to_anchor=(0, 1.02))

    for i, k in enumerate(COHORTS):
        s = range_bar(b, i, per_batch[per_batch.cohort == k].cost_usd, NEUTRAL, usd)
        table.append(dict(panel="B", cohort=k, **s))
        s = range_bar(c, i, ok[ok.cohort == k].wall_clock_h, NEUTRAL, hours)
        table.append(dict(panel="C", cohort=k, **s))
    for ax in (b, c):
        ax.set_xticks(x, cohort_labels)
        ax.set_xlim(-0.6, 2.6)
        ax.set_ylim(0, ax.get_ylim()[1] * 1.1)
        value_grid(ax, "y")
    b.set_ylabel("Cost per batch of 12 series (USD)")
    b.yaxis.set_major_locator(mpl.ticker.MultipleLocator(0.05))
    b.yaxis.set_major_formatter(lambda v, _: f"${v:.2f}")
    c.set_ylabel("Batch wall-clock time (h)")

    for ax, L in zip([a, b, c], "ABC"):
        panel_label(ax, L, x=-0.28)
    save(fig, "cohorts-twovm", table)


def stage_times(attempts, stages):
    """126k cohort, the paper's layout: phases of a batch on top, the steps inside core
    analysis below; one column per task."""
    a126 = attempts[(attempts.cohort == "126k") & (attempts.outcome == "Success")]
    phase = lambda task, col: a126.loc[a126.task == task, col]  # noqa: E731
    gpu_t, cpu_t = "downloadDicomAndConvertAndInferenceTotalSegmentator", "dicomsegAndRadiomicsSR"
    tasks = [(gpu_t, "Input conversion and inference (GPU VM)"),
             (cpu_t, "Feature extraction and output conversion (CPU VM)")]
    phases = [("Allocation and set-up", False, "allocation_setup_min"),
              ("Core analysis", False, "core_analysis_min"),
              ("Deallocation", False, "deallocation_min")]
    steps = {gpu_t: [("Downloading DICOM", "dicom_download_time_min"),
                     ("DICOM to NIfTI", "dicom_conversion_time_min"),
                     ("TotalSegmentator inference", "total_segmentator_time_min"),
                     ("Archiving NIfTI", "nifti_archiving_time_min")],
             cpu_t: [("NIfTI to DICOM SEG", "itkimage2segimage_time_min"),
                     ("Radiomics features", "radiomics_time_min"),
                     ("Features to DICOM SR", "structuredReportsGenerationTime_min"),
                     ("Archiving SEG and SR", "seg_sr_archiving_time_min")]}

    fig, axs = plt.subplots(2, 2, figsize=(FULL_W, 4.3), sharex=True,
                            gridspec_kw=dict(wspace=0.75, hspace=0.32))
    table, xmax = [], 0
    for col, (task, title) in enumerate(tasks):
        color = VM_COLOR[TASK_VM[task]]
        rows = [(lab, sub, phase(task, c)) for lab, sub, c in phases]
        rows_b = [(lab, False, stages[c]) for lab, c in steps[task]]
        for r, (ax, rr, part) in enumerate([(axs[0, col], rows, "phase"), (axs[1, col], rows_b, "step")]):
            for i, (label, sub, vals) in enumerate(rr):
                s = range_bar(ax, i, vals, color, minutes, horizontal=True, width=0.46,
                              tukey=True, seed=10 * col + i, label="above")
                xmax = max(xmax, s["p95"], float(np.nanmax(vals)))
                table.append(dict(task=title, part=part, row=label, **s))
            ax.set_yticks(range(len(rr)), [("   " + x[0]) if x[1] else x[0] for x in rr])
            for tick, x in zip(ax.get_yticklabels(), rr):
                tick.set_color(MUTED if x[1] else INK)
            ax.set_ylim(len(rr) - 0.45, -0.75)
            ax.spines["left"].set_visible(False)
            value_grid(ax, "x")
        axs[0, col].set_title(title, fontsize=7.5, loc="left", color=INK, pad=8)
        axs[1, col].set_xlabel("Minutes per batch of 12 series")
    axs[0, 0].set_xlim(0, xmax * 1.03)
    panel_label(axs[0, 0], "A", x=-0.75)
    panel_label(axs[1, 0], "B", x=-0.75)
    save(fig, "stage-times", table)


def preemption_loss(attempts):
    """126k cohort: how long preempted attempts ran before they were lost."""
    p = attempts[(attempts.cohort == "126k") & (attempts.outcome == "Preempted")]
    rows = []
    for task in ["downloadDicomAndConvertAndInferenceTotalSegmentator", "dicomsegAndRadiomicsSR"]:
        for k in sorted(p[p.task == task].attempt.unique()):
            v = p[(p.task == task) & (p.attempt == k)].attempt_min
            rows.append((task, k, v))
    fig, ax = plt.subplots(figsize=(FULL_W * 0.62, 0.42 * len(rows) + 0.6))
    table, labels = [], []
    for i, (task, k, v) in enumerate(rows):
        s = range_bar(ax, i, v, VM_COLOR[TASK_VM[task]], minutes, horizontal=True, width=0.5,
                      points=True, seed=i, label="above")
        table.append(dict(task=task, preempted_attempt=k, **s))
        name = "Conversion + inference" if TASK_VM[task] == "GPU" else "Features + output"
        labels.append(f"{name}, attempt {k}  (n = {len(v):,})")
    ax.set_yticks(range(len(rows)), labels)
    ax.set_ylim(len(rows) - 0.4, -0.6)
    ax.set_xlim(left=0)
    ax.spines["left"].set_visible(False)
    value_grid(ax, "x")
    ax.set_xlabel("Minutes the attempt ran before its VM was preempted")
    vm_legend(ax, loc="lower right")
    save(fig, "preemption-loss", table)


def gpu_allocation(gpu):
    """126k cohort: GPU VMs running at each minute, by region."""
    gpu = gpu.dropna(subset=["running", "terminal"]).copy()
    gpu["region"] = gpu.region.fillna("unknown")
    gpu_hours = ((gpu.terminal - gpu.running).dt.total_seconds() / 3600).groupby(gpu.region).sum()
    order = gpu_hours.sort_values(ascending=False).index.tolist()
    t = pd.date_range(gpu.running.min().floor("5min"), gpu.terminal.max().ceil("5min"), freq="1min")
    tv = t.values
    counts = []
    for r in order:
        d = gpu[gpu.region == r]
        s, e = np.sort(d.running.values), np.sort(d.terminal.values)
        counts.append(np.searchsorted(s, tv, side="right") - np.searchsorted(e, tv, side="right"))
    counts = np.array(counts)
    total = counts.sum(axis=0)

    fig, ax = plt.subplots(figsize=(FULL_W, 2.6))
    colors = [CATEGORICAL[i] if r != "unknown" else AXIS for i, r in enumerate(order)]
    ax.stackplot(t, counts, colors=colors, edgecolor="white", linewidth=0.4)
    i = int(total.argmax())
    ax.plot(t[i], total[i], "o", ms=4, color=INK, mec="white", mew=1, zorder=5)
    ax.annotate(f"Peak: {total[i]:,} GPUs at {t[i]:%H:%M} UTC", (t[i], total[i]), xytext=(8, 4),
                textcoords="offset points", fontsize=7, color=INK)
    ax.set_ylabel("GPU VMs running")
    ax.set_ylim(0, total.max() * 1.12)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:,.0f}")
    ax.xaxis.set_major_locator(mdates.HourLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax.set_xlim(t[0], t[-1])
    ax.set_xlabel(f"Time (UTC), {t[0]:%-d}–{t[-1]:%-d %b %Y}")
    value_grid(ax, "y")
    handles = [Patch(color=c, label=f"{REGION_NAME.get(r, r)}: {gpu_hours[r]:,.0f} GPU-h")
               for r, c in zip(order, colors)][::-1]
    # Matplotlib fills legend columns first; reorder so the entries read row by row.
    ncol = 3
    nrow = -(-len(handles) // ncol)
    handles = [handles[r * ncol + c] for c in range(ncol) for r in range(nrow)
               if r * ncol + c < len(handles)]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=ncol,
              handlelength=1, handleheight=0.8, columnspacing=1.5,
              title="Region, top of stack first", title_fontsize=7)
    table = pd.DataFrame(counts.T, columns=order).assign(time_utc=t, total=total)
    save(fig, "gpu-allocation", table)
    return dict(peak=int(total[i]), peak_time=str(t[i]), gpu_hours=float(gpu_hours.sum()))


def main():
    runs, batches, attempts, costs, stages, gpu = load()
    configurations_1k(runs, batches, attempts, costs)
    cost_breakdown_1k(costs)
    cohorts_twovm(batches, attempts, costs)
    stage_times(attempts, stages)
    preemption_loss(attempts)
    peak = gpu_allocation(gpu)
    cost_breakdown(costs)
    print("GPU concurrency:", peak)


if __name__ == "__main__":
    main()
