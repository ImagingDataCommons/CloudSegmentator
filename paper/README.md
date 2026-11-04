# Analysis and figures for the 2026 paper

The scripts and tidy data behind the figures in the paper on running CloudSegmentator at scale
on Terra (Thiriveedhi et al., in preparation, 2026). It has two case studies:

- **Case study 1:** TotalSegmentator on NLST CT series, in cohorts of 1k, 10k and 126,088
  series, Jun 2023 – Jan 2024 (`workflows/TotalSegmentator`). The 126k run fetched its
  notebooks from `v1.2.0`.
- **Case study 2:** TotalSegmentator and MOOSE on CMB and CPTAC CT series, Oct 2026, with the
  harmonized workflow (`workflows/harmonized`).

Unlike `util/`, this folder records fixed runs. Submission IDs, workspaces and buckets are
written into the scripts, and `data/` holds tables derived from those runs. `AGENTS.md` exempts
the folder from the repository's rules on both.

## Figures

Each figure has a keyword. Its outputs and the function that draws it are named after that
keyword:

- Outputs are written to `out/` as `<keyword>.pdf` and `<keyword>.png` (`.svg` too for the
  diagram). The `make_figures*.py` scripts also write `<keyword>_values.csv`, which holds every
  plotted number. Variants and intermediate files use the pattern `<keyword>_<variant>.*`.
- The function that draws a figure has the keyword's name, with hyphens replaced by underscores.

Figure numbers follow the manuscript as numbered on 4 Nov 2026. Figure 8 is made of panels
drawn separately.

| Figure | Keyword | Drawn by |
|---|---|---|
| 1 | `workflow-diagram` | `make_workflow_diagram.py` |
| 2 | `stage-times` | `make_figures.py` |
| 3 | `gpu-allocation` | `make_figures.py` |
| 4 | `cost-breakdown` | `make_figures.py` |
| 5 | `cs2-stage-times` | `make_figures_cs2.py` |
| 6 | `cs2-cost-breakdown` | `make_figures_cs2.py` |
| 7 | `cs2-peak-memory` | `make_figures_cs2.py` |
| 8, top row | `sample-result` | not drawn here: screenshots from the IDC viewer and 3D Slicer |
| 8, bottom left | `cs2-sample-result` | [`example-case/`](example-case/), the two-row layout, `cs2-sample-result_two-rows.png` |
| 8, bottom right | `cs2-structures` | `make_figures_cs2.py` |

The scripts also draw figures that are not in the paper: `preemption-loss`,
`configurations-1k`, `cost-breakdown-1k` and `cohorts-twovm` (`make_figures.py`), and
`cs1-peak-memory` and `idc-structures` (`make_figures_cs2.py`).

The scripts pin matplotlib to 3.11.2, the version the paper's figures were drawn with. Other
versions lay out text slightly differently, so the images change size even though the plotted
values stay the same.

## What runs with what

Anyone can redraw every figure from `data/`, because the `make_*` scripts need no credentials.
The `build_*` scripts read the Terra workspaces and the billing export, which require project
access. They are kept as the record of how `data/` was made. Every script declares its
dependencies inline for `uv run`.

| Script | Makes | Needs |
|---|---|---|
| `make_figures.py` | case study 1 figures | `data/` |
| `make_figures_cs2.py` | case study 2 figures, `cs1-peak-memory` and `idc-structures` | `data/` |
| `make_workflow_diagram.py` | `workflow-diagram`, plus an editable `.drawio` copy | nothing |
| `build_data.py` | case study 1 tables, from Cromwell logs and BigQuery | `gcloud`, `bq`: case study 1 workspace bucket, `idc-external-025`; ~1 GB of logs, ~40 min |
| `build_data_cs2.py` | case study 2 tables, from the Terra API, the workflows' metrics files and the billing export | `gcloud`: case study 2 workspace; `bq`: billing export; ~3 min. `--reruns-only` skips BigQuery |
| `build_data_memory.py` | `cs1_peak_memory`, `cs2_series_order` | `gcloud`: both workspace buckets; `lz4`; ~15 min |
| `build_series_geometry_cs2.py` | `cs2_series_geometry` | nothing (idc-index, IDC v25) |
| `build_data_structures_cs2.py` | `cs2_structures`, from the SEGs in the case study 2 DICOM store's BigQuery export | `bq` on `idc-external-031` |
| `build_data_structures_idc.py` | `idc_structures`, `idc_structures_totals`, from IDC v25 in BigQuery and the case study 2 query | `bq` on `idc-external-031` |
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
| `cs2_structures` | structure (SNOMED segmented property type, left and right merged): the models that segment it, the CT series it was found in (any model, TotalSegmentator, MOOSE) and its segments | the SEGs in `idc-external-031.not_a_challenge.idc-segmentations-20261014`, read 30 Oct 2026 |
| `idc_structures` | structure segmented in IDC v25 on CT, MR or PET, or by case study 2 (codes for one concept merged): its codes, names, IDC sources, segments, and the series it is in: in IDC (by modality, and case study 1's), in case study 2, added by case study 2, and the union | `bigquery-public-data.idc_v25` and the above, read 30 Oct 2026 |
| `idc_structures_totals` | modality (CT, MR, PET): series with any segment in IDC, in case study 2 and in the union; SEG instances, segments and sources in IDC | as above |

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

**Structures** in `cs2-structures` and `idc-structures`:

- **Structure:** a segmented property type, so left and right merge and the two tools pool
  where they share a code. Case study 2 has 111 structures, or 155 counting laterality.
  `idc-structures` also merges codes for one concept (`SAME_AS` in
  `build_data_structures_idc.py`): legacy SNOMED RT codes join their SNOMED CT counterparts,
  and a few others are mapped by hand. Background (DCM 125040) is dropped. That leaves 143
  structures: 80 in both IDC and case study 2, 31 only in case study 2, and 32 only in IDC.
- **Found:** the structure is a segment in a SEG for that series. A SEG lists only the segments
  its model found, so any voxels count; there is no size threshold.
- **Series:** from each SEG's referenced series. The ten case study 2 SEGs that lack one are
  mapped from their bucket folder (`UNREFERENCED` in `build_data_structures_cs2.py`). In IDC,
  1,030 SEGs lack one and are placed by frame of reference, each frame counting as one series;
  two cannot be placed and are left out. A series counts once per structure, whatever the
  number of SEGs on it.
- **Scope of `idc-structures`:** every SEG in IDC v25 whose segmented series is CT, MR or PET,
  which leaves out slide microscopy, and phantom collections. The faded part of a bar is the
  series where a SEG in IDC has the structure; the solid part above is the CT series case
  study 2 adds, where no SEG in IDC had it. On the log axis, its height is the factor by which
  case study 2 multiplies the count.
- **Groups, colours and names:** groups are made by hand (`STRUCTURE_GROUPS` and `IDC_GROUPS`
  in `make_figures_cs2.py`). Spine and ribs are in anatomical order, the other groups sorted by
  count. Each group has one hue, for identity only, kept across both figures; lesions are not
  anatomy and are drawn in grey. Names are the SNOMED meanings, the shorter where the tools
  differ, and TotalSegmentator's "Cyst" with anatomic region Kidney is shown as "Kidney cyst".
- **L6:** the short bar inside the spine is the L6 vertebra, found in 261 series by MOOSE
  (`clin_ct_vertebrae`) only. A sixth lumbar vertebra is an anatomical variant; whether these
  are true L6 or mislabelled L5 or S1 is unchecked.

A bar can fall short of the all-series line for two reasons the figures do not separate:
the structure was outside the scan, or the model that segments it produced no output for that
series. The second is not negligible. 24 series have no output at all, and
`clin_ct_body_composition` has 2,800 SEGs against 2,895–3,033 for the other models, which is
why its three tissues stop at about 2,800. The `cs2-structures` header counts the 3,059 series
of the cohort; 3,035 of them have output.

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
