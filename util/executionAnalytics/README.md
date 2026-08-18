# Execution analytics: measuring and predicting the cost of a Terra run

Tools to (1) measure what a Terra submission of the harmonized `Segmentator` workflow
(or the legacy MOOSE / TotalSegmentator workflows) actually cost and where the time went,
(2) fit a cost model on a small **pilot**, (3) **predict** the cost of a larger run before
launching it, in any GCP region, and (4) check how well the prediction extrapolated.

```
region_prices.py        Cloud Billing Catalog -> per-region $/h for the workflow's VM shapes; region ranking
make_terra_manifest.py  idc-index cohort -> designed pilot TSV + full-run TSV (Terra data tables)
submission_cost.py      one Terra submission -> per-task metadata, billing $, per-series timings + features
idc_features.py         SeriesInstanceUID -> slices / rows / cols / voxels / MB / collection (idc-index)
cost_model.py           fit | predict | evaluate | report  (+ figures)
```

All scripts are plain Python 3 (`pandas`, `numpy`, `idc-index`; `matplotlib` optional for
figures) and authenticate with `gcloud auth print-access-token` (Terra API, Billing Catalog)
and `bq` (billing export). Run `gcloud auth login` once.

## The approach

**Cost ≈ Σ_task rate(region, VM shape) × task wall-clock.** In the billing export of the
legacy MOOSE runs the GPU SKU is ~72 % of the bill, vCPU+RAM ~23 %, disk ~4 %, external IP
and network < 2 %. So the region only changes the *rate*; what has to be modelled is *time*,
and time is a function of the workload. For each WDL task `k` and workflow `w`
(one Terra entity = one workflow = one batch of series):

```
time_k(w) = a_k + b_k · nSeries(w) + c_k · Mvoxels(w)      minutes (incl. retries)
cost_k(w) = a'_k + b'_k · nSeries(w) + c'_k · Mvoxels(w)   $ from the billing export
```

* `a` = fixed per-VM overhead (boot, image pull, model weights, packaging, queueing --
  15–20 min/workflow in the runs so far), `b` = per-series fixed work (IDC download,
  dcm2niix, reference-DICOM re-download in nb3, per-series model setup), `c` = per-voxel work.
* `Mvoxels = Σ instanceCount × Rows × Columns / 1e6` is known **before** a run from
  `idc-index` (`idc_features.py`), so a manifest can be priced before it is submitted. It is
  the same metric `Preprocessing.ipynb` batches on.
* Both models are fitted by OLS on the pilot; the `$` model is calibrated to what was
  actually billed. For another region the `$` prediction is scaled by
  `rate(target)/rate(pilot)` per task from `region_rates.json`. Predictions carry a 95 %
  interval (residual + coefficient uncertainty).
* Preemption/retry overhead is measured (`attempts`, `runtimeMin` vs `doneRuntimeMin`) and
  reported per task -- spot *prices* are in the catalog, spot *preemption rates* are not.

**Pilot design.** The two predictors must vary independently or `b` and `c` cannot be
separated (the June MOOSE batches were all ~300–350 Mvox, so `c` was unidentifiable there).
`make_terra_manifest.py pilot` samples series stratified over the cohort's voxel
distribution and builds, for each batch size in `--batch-sizes`, one entity of *small*
series and one of *large* series before any mixed ones (60 series → ~12 entities,
corr(nSeries, Mvox) ≈ 0.6). Everything else must be held equal between pilot and full run:
docker image digests, `inferenceParamsYaml`, `runRadiomics` / `radiomicsMethod`,
machine shapes, preemptible tries, **region**. `submission_cost.py` records all of these in
`_workflows.csv`; `cost_model.py fit` stores them in `model.json` and `evaluate` warns on drift.

**Measure from the billing export, not Terra's estimate.** Terra shows `costType=Estimated`
for a long time (and its estimate was 3× off on a small harmonized run); the export
(`terra-submission-id` / `cromwell-workflow-id` / `wdl-task-name` labels) settles ~24–48 h
after the run. `submission_cost.py` uses it when available and falls back to a
region-aware list-price estimate otherwise (`costSource` column says which).

**Commit the prediction before the large run**, then `evaluate` after: total error, per-task
error, per-workflow MAPE, interval coverage, predicted-vs-actual scatter.

## Runbook (per model: MOOSE, TotalSegmentator)

```bash
cd util/executionAnalytics

# 0. Region: rank by $/h of the workflow's two VM shapes (+ approx. cross-continent transfer)
python region_prices.py rank --out region_rates.json            # all regions with T4
python region_prices.py rank --region-prefix us-                # US only
#    -> set Segmentator.inferenceZones / outputConversionZones in the inputs JSON to
#       "<region>-a <region>-b ..." (all zones in ONE region, and only zones that have T4:
#       pass --gpu-project <project-with-compute-api> for the live zone list).

# 1. Manifests: designed pilot + full run from the same cohort (pilot series excluded)
python make_terra_manifest.py pilot --name moose_pilot --n-series 60 --batch-sizes 1,3,6,10 --seed 0
python make_terra_manifest.py full  --name moose_full  --n-series 300 --exclude moose_pilot_series.csv --seed 0
#    Upload *_terra_data_table.tsv to the workspace; root entity twoVM_<name>;
#    yamlListOfSeriesInstanceUIDs = this.SeriesInstanceUIDs. Use radiomicsMethod=radiomicsjl
#    unless you specifically want to price pyradiomics (85 vs 11 min nb3 on the same 4 series).

# 2. Run the pilot on Terra. Wait ~24-48 h for the billing export.
python submission_cost.py <pilot submission URL> --region-rates region_rates.json --label moose-pilot
#    -> submission_<id>_workflows.csv, _series.csv, _billing.csv (or _cost_estimate.csv), _cost.csv

# 3. Fit, then predict the full run (optionally in another region) BEFORE launching it
python cost_model.py fit --workflows submission_<pilot>_workflows.csv --series submission_<pilot>_series.csv --out model_moose.json
python cost_model.py predict --model model_moose.json --manifest moose_full_terra_data_table.tsv \
       --rates region_rates.json --region us-west4 --out predicted_moose_full.csv

# 4. Run the full set; wait; measure; evaluate
python submission_cost.py <full submission URL> --region-rates region_rates.json --label moose-full
python cost_model.py evaluate --predicted predicted_moose_full.csv --actual submission_<full>_workflows.csv --plots figs_moose

# 5. Metrics + figures for any set of runs (cost vs #series / voxels / slices / MB, per-task
#    runtime, unit costs vs batch size, per-series phase timings, SKU breakdown, model fit)
python cost_model.py report --workflows submission_*_workflows.csv --series submission_*_series.csv \
       --billing submission_*_billing.csv --model model_moose.json --plots figs_all
```

## Files

`submission_<id8>_workflows.csv` (one row per workflow; the fit/evaluate input)

| column | meaning |
|---|---|
| `label, submissionId, workflowId, entity, status` | identity (`--label` tags the run) |
| `model, radiomicsMethod, radiomicsEnabled` | from nb3 `run_summary.json` |
| `nSeries, sumVoxels, sumSlices, sumSizeMb, meanVoxels, maxVoxels` | a-priori workload (entity series list + idc-index) |
| `sumInferenceSec, sumOutputConversionSec, dicomSegErrors, radiomicsErrors` | notebook-reported totals |
| `<task>_runtimeMin` | wall-clock of all attempts of the task (what is billed) |
| `<task>_doneRuntimeMin, _attempts, _preempted` | successful attempt only; retry counts |
| `<task>_machine, _gpu, _docker, _rateHr` | shape, GPU, image digest, catalog $/h used for the estimate |
| `<task>_cost` / `<task>_estCost` | billing-export $ (net of credits) / list-price estimate |
| `region, totalRuntimeMin, terraCost, terraCostType, otherCost, totalCost, costSource` | `costSource` ∈ billing, terra, estimate |
| `costPerSeries, costPerMvoxel, costPerSlice` | unit costs |

`submission_<id8>_series.csv` (one row per series): idc-index features (`collection, modality,
bodyPart, manufacturer, slices, rows, cols, voxels, sliceThicknessMm, pixelSpacingMm, sizeMb`)
+ notebook timings (`downloadSec, dcm2niixSec` from nb1; `inferenceSec, nModels, modelTimings`
from nb2; `refDownloadSec, segSec, radiomicsSec, nLabels, outputConversionSec` from nb3).

`region_rates.json`: `{tier, shapes, rates: {shape: {region: {gpu_hr, vcpu_hr, ram_hr, disk_hr,
total_hr}}}, gpu_zones, ranking}`.

`model.json`: per task `time` / `time_done` / `cost` fits (`coef, cols, resid_sd, r2, n,
XtX_inv`), `preempt_overhead`, `eff_rate_hr` vs `catalog_rate_hr`, plus `config` (docker
digests, machine shapes, radiomics engine, region) and the pilot's feature ranges.

## Where the pipeline exposes timings

* nb1 `convert_UsageMetrics.csv` -- `download_s, download_dcm_files, download_mb, dcm2niix_s`
  per series (now a WDL output of the `inference` task and part of nb3's combined CSV).
* nb2 `inference_UsageMetrics.csv` -- `model_inference_s` per (series, sub-model).
* nb3 `output_conversion_UsageMetrics.csv` -- `model_seg_s, model_radiomics_s, n_labels,
  ref_download_s, series_total_s, radiomics_method` per (series, model); `run_summary.json`.
* Cromwell call metadata (via the Terra API): start/end per attempt, runtime attributes,
  image digest -- what `_cost.csv` holds.

`cost_model.py report` turns these into a phase breakdown per workflow (download / dcm2niix /
inference / ref-download / SEG / radiomics / *VM time not in any phase*), which is the
first-order profile for deciding what to optimise next.

## Caveats

* Billing-export lag (24–48 h); `Estimated` vs `Actual` Terra cost; export task labels are
  lowercased (handled).
* Spot prices in the catalog change over time (the June effective T4 rate in us-east4 was
  ~$0.16/h vs $0.19/h in the catalog in August); the `$` model is calibrated to the pilot's
  actual bill, and re-pricing to another region uses catalog *ratios*.
* Cromwell `runtimeMin` (start→end of the call) is longer than the billed VM time (queueing,
  provisioning), so `eff_rate_hr` < `catalog_rate_hr`; this is why the `$` model, not
  `time × rate`, is used for prediction in the same region.
* Regions outside the US pay GCS cross-continent transfer for IDC downloads (~$0.02–0.08/GB);
  `region_prices.py rank` adds an approximate per-GB adder (`--data-gb-per-hour`).
* Preemption frequency differs by region and time of day; the pilot's measured overhead is
  applied as-is.
* Model configuration must match between pilot and full run (`evaluate` warns on digest /
  engine / region drift). Notably `radiomicsMethod` changes nb3 cost by ~8× (pyradiomics vs
  Radiomics.jl on the same series).
