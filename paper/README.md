# Analysis and figures for the 2026 paper

The scripts and tidy data behind the execution figures and numbers in the paper on running
CloudSegmentator at scale on Terra (Thiriveedhi et al., in preparation, 2026). It has two case
studies:

- **Case study 1:** TotalSegmentator on NLST CT series, in cohorts of 1k, 10k and 126,088
  series, Jun 2023 – Jan 2024 (`workflows/TotalSegmentator`). The 126k run fetched its
  notebooks from `v1.2.0`.
- **Case study 2:** TotalSegmentator and MOOSE on CMB and CPTAC CT series, Oct 2026, with the
  harmonized workflow (`workflows/harmonized`).

Unlike `util/`, this folder records fixed runs. Submission IDs, workspaces and buckets are
written into the scripts, and `data/` holds tables derived from those runs. `AGENTS.md` exempts
the folder from the repository's rules on both.

## Figures and their numbers

The manuscript cites figures by keyword, as in "Figure [stage-times]" or
"Figure [workflow-diagram]B", so that figures can be added, dropped or reordered without
renumbering. Code uses the same keyword:

- Outputs are written to `out/` as `<keyword>.pdf` and `<keyword>.png` (`.svg` too for the
  diagram). The `make_figures*.py` scripts also write `<keyword>_values.csv`, which holds every
  plotted number. Variants and intermediate files use the pattern `<keyword>_<variant>.*`.
- The function that draws a figure has the keyword's name, with hyphens replaced by underscores.
- [`figures.csv`](figures.csv) lists every keyword, the script that draws it, and its figure
  number. A keyword with no number is not in the manuscript.

The numbers in `figures.csv` follow the manuscript as numbered on 4 Nov 2026, and they answer
the question "which code drew Figure 3?" for a reader of the published paper. Figure 7 is made
of panels drawn separately, so two keywords share its number: `sample-result`, the top row, is
a set of screenshots from the IDC viewer and 3D Slicer, and `cs2-sample-result`, bottom left,
is the two-row layout from [`example-case/`](example-case/). Its bottom-right panel, a chart
of the structures segmented in case study 2, is not drawn here.

Once the manuscript cites figures by number, `number_figures.py` checks those citations
against `figures.csv`. Before that, it can number the figures in order of first citation:

```
uv run paper/number_figures.py --manuscript manuscript.md            # check what it cites
uv run paper/number_figures.py --manuscript manuscript.md --assign   # number by first citation
uv run paper/number_figures.py --export submission/                  # figure-1.pdf, ...
```

To add a figure, add a row to `figures.csv` with a new keyword, and name its outputs and its
function by that keyword.

## What runs with what

Anyone can redraw every figure from `data/`, because the `make_*` scripts need no credentials.
The `build_*` scripts read the Terra workspaces and the billing export, which require project
access. They are kept as the record of how `data/` was made. Every script declares its
dependencies inline for `uv run`.

| Script | Makes | Needs |
|---|---|---|
| `make_figures.py` | case study 1 figures | `data/` |
| `make_figures_cs2.py` | case study 2 figures, and `cs1-peak-memory` | `data/` |
| `make_workflow_diagram.py` | `workflow-diagram`, plus an editable `.drawio` copy | nothing |
| `memory_comparison.py` | prints the comparison of peak memory between the case studies | `data/` |
| `number_figures.py` | checks `figures.csv`, assigns numbers, exports numbered files | `out/` |
| `build_data.py` | case study 1 tables, from Cromwell logs and BigQuery | `gcloud`, `bq`: case study 1 workspace bucket, `idc-external-025`; ~1 GB of logs, ~40 min |
| `build_data_cs2.py` | case study 2 tables, from the Terra API, the workflows' metrics files and the billing export | `gcloud`: case study 2 workspace; `bq`: billing export; ~3 min. `--reruns-only` skips BigQuery |
| `build_data_memory.py` | `cs1_peak_memory`, `cs2_series_order` | `gcloud`: both workspace buckets; `lz4`; ~15 min |
| `build_series_geometry_cs2.py` | `cs2_series_geometry` | nothing (idc-index, IDC v25) |
| `build_anatomy_coverage.py` | `remaining_series`; prints how much of IDC has anatomy segmented | nothing; `--refresh-cs2` needs `bq` on `idc-external-031` |
| `example-case/` | `cs2-sample-result` | 3D Slicer and the case's DICOM; see [its README](example-case/README.md) |

`util/executionAnalytics/submission_cost.py` covers much of the same ground as
`build_data_cs2.py`: the Terra metadata, the metrics files, and the billing export matched on
the `cromwell-workflow-id` label. The paper's copy is kept as it ran, so that the published
numbers do not move.

## Runs

**Case study 1** ran in workspace `terra-billing-datester/TotalSegmentator`. Its five
submissions were identified by matching their billed totals to the preprint.

| Cohort | Configuration | Terra submission |
|---|---|---|
| 1k | oneVM | `3cae21b5-2b5b-4ae4-b966-d572b81ba05d` |
| 1k | twoVM | `4eb81ea3-dd59-4a39-b186-819b529d1841` |
| 1k | threeVM | `1cf0924f-38ff-46ff-a2b7-0c100de04efa` |
| 10k | twoVM | `3068f71e-6e83-4fb2-9350-1af1dedf6ec8` |
| 126k | twoVM | `f835e545-da03-4a6f-89b6-6460a9497ac1` |

**Case study 2** ran in workspace `terra-billing-datester/kyle-testing`. Both submissions were
launched on 15 Oct 2026 and shared one quota of 16 preemptible T4 GPUs, so their waits are not
independent. Each used the twoVM layout with 186 batches, T4 inference and N2D output
conversion in us-west4, Radiomics.jl first-order and shape features, and checkpointing.

| Model | Terra submission | Series | Billed |
|---|---|---|---|
| TotalSegmentator (`total`, `lung_vessels`) | `0702d858-ae72-49df-816c-a2e7d3ec3394` | 2,959 | $76.50 |
| MOOSE (ten `clin_ct_*` models) | `f4b9a107-e336-4f81-b80d-ebe5cd066479` | 2,959 | $93.92 |

On 21–22 Oct 2026 the series that had lost results to memory were rerun, one series per
workflow, with RAM raised a step at a time. The rerun submissions are listed as `RERUNS` in
`build_data_cs2.py`.

## Data

Every file is gzip-compressed CSV; pandas reads them as they are.

| File | One row per | Source |
|---|---|---|
| `runs` | case study 1 run | the table above |
| `batches` | case study 1 batch (Cromwell workflow) | workflow logs: first line, completion, status |
| `task_attempts` | case study 1 task attempt | workflow logs, plus the per-task log of each successful attempt (container set-up, user action, delocalization) |
| `costs_by_workflow` | case study 1 batch × cost category | BigQuery `idc-external-025.012624.terraCostAnalysis` |
| `stage_times_126k` | 126k batch | BigQuery `012624.126k-inference-series-level-times` and `012624.126k-radiomics-features-series-level-times`, summed per batch |
| `gpu_vms_126k` | 126k GPU VM | the non-preempted inference attempt in `task_attempts`; region from `012624.gpus_total_hourly` |
| `cs2_runs` | case study 2 run | Terra |
| `cs2_task_attempts` | task attempt, with phase durations and counts of VM requests, quota errors, stockouts and timeouts | Cromwell metadata from the Terra API |
| `cs2_step_times` | batch: sums of the per-series step timings, and series counts | each workflow's `combined_UsageMetrics.csv` |
| `cs2_costs_by_workflow` | batch × task × cost category | Terra billing export, by `cromwell-workflow-id` |
| `cs2_peak_memory` | series × unit of work: peak RAM in use, with DICOM size | the workflows' metrics files |
| `cs2_inference_failures` | (series, model or task) that the final inference attempt reported as failed, with the cause | each workflow's `inference_errors.txt`, and the executed notebook for the attempt's peak RAM |
| `cs2_rerun_*` | the same as their main-run counterparts, for the reruns, with the rerun pass and the RAM given | as above |
| `cs2_series_geometry` | series: matrix, spacing, field of view, length, voxels as acquired and at 1.5 mm, peak RAM, memory failures | idc-index (IDC v25) |
| `cs2_series_order` | series in each inference attempt with a memory-related failure: position, failures before it, restored from checkpoint | executed inference notebooks |
| `cs1_peak_memory` | case study 1 series (twoVM 1k, 10k, 126k): peak RAM on the GPU VM, with geometry | each workflow's `inferenceUsageMetrics.lz4` |
| `cs2_output_series` | source CT series with at least one case study 2 SEG | `ReferencedSeriesSequence` in `idc-external-031.not_a_challenge.idc-segmentations-20261014`, read 2 Nov 2026 |
| `remaining_series` | IDC v25 CT, MR or PT series that can be segmented and has no whole-body anatomy | idc-index |

How case study 1's BigQuery tables were made, as far as can be told:

- `012624.terraCostAnalysis` has the six columns that
  `util/executionAnalytics/sqlQueries/terraCostAnalysisETL.sql` (`v1.2.0`) writes from the
  Terra billing export. That it is a full run of that query is **inferred** from the identical
  schema. Its totals reproduce the preprint's to the cent. Cost categories are assigned from
  `skuDescription` (`COST_CATEGORY_SQL` in `build_data.py`), and every `Network …` item counts
  as egress.
- The `126k-*-series-level-times` tables are **inferred** to be loaded from the per-task
  `UsageMetrics.lz4` files that the `v1.2.0` notebooks write.
- `012624.gpus_total_hourly` is the preprint's hourly GPU table, loaded to BigQuery.

## Definitions

**Case study 1 phases** come from the Cromwell logs. The preprint used Cromwell's events from
the Terra API, in an extract that is no longer available, and the logs record fewer events.

- **Allocation and set-up:** from Cromwell's `Starting` line for the attempt to the start of the
  user action. It includes the wait for an execution token, which is recorded separately as
  `queue_min`.
- **Core analysis:** the user action, up to the start of delocalization.
- **Deallocation:** from the start of delocalization to Cromwell recording success.
- **Batch wall clock:** from Cromwell picking the workflow up to its completion. It excludes
  time queued in Terra before that.
- **Time lost to a preemption:** the preempted attempt's span, from its `Starting` line to the
  preemption.
- **Preemption rate:** preemption events for a task divided by the number of batches in the run.
- **GPU allocation:** non-preempted inference VMs running at each minute. The preprint's version
  counted distinct VMs active in each clock hour. That count is generally higher, because VMs
  that do not overlap in time still count in the same hour.

**Case study 2 phases** come from the Batch job events that Cromwell records under the GCP
Batch backend:

- **Waiting for a VM:** from `Pending` to the start of the VM that eventually ran. This covers
  quota refusals, stockouts and VM starts that timed out.
- **VM start-up:** from that VM's start to Batch `RUNNING`.
- **Running:** Batch `RUNNING`. It covers image pull, file transfer and the analysis, which are
  not separable here.
- **Deallocation:** from Batch `SUCCEEDED` to Cromwell recording completion.

The steps in `cs2-stage-times` are shown per series, as the mean over each batch. A series
restored from a checkpoint logs zero for the work its preempted attempt did, so a batch with any
restored series is left out of that task's steps.

**Peak memory** in case study 2 comes from `MemSampler` (`workflows/common/Notebooks/segmentator_checkpoint.py`),
which samples MemTotal − MemAvailable every 5 s. That is RAM in use on the whole VM, with page
cache excluded. A unit of work that fails writes no metrics row. For a failure related to
memory, the unit is assigned the attempt's overall peak, but only where that peak exceeds every
unit that finished in the same attempt. Case study 1's `MemoryMonitor` (`v1.2.0`) sampled
psutil `total − available` once a second. Its values are converted from MB of 10⁶ bytes to GiB.

**Distributions** are drawn as a box spanning the interquartile range, with a bar at the median
and whiskers at the 5th and 95th percentiles. In `stage-times` and `cs2-stage-times` the
whiskers reach the furthest value within 1.5 IQR, and every batch beyond that is drawn as a
point. Groups of fewer than 10 are drawn as points.

## Gaps

- Case study 1's Docker-pull time cannot be recovered. The logs do not record it, and the Life
  Sciences API operations that did no longer exist.
- One 126k batch (`97ae3e29`) has no usable timings. Cromwell restarted, replayed its results
  from the job store and overwrote its log.
- Six 10k batches were aborted after five failed attempts. They are left out of wall-clock
  distributions but not out of costs.
- MOOSE batch 140 of case study 2 failed in output conversion. It has no step timings, but its
  cost is included.
- Case study 2 costs are gross, before credits, which is the figure Terra reports. They were
  read on 17 Oct 2026 and match Terra's per-submission totals to within 2 cents.
