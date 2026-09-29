# Harmonized Segmentator Workflow

A single, model-agnostic Terra/WDL workflow that runs **any** segmentation model
(MOOSE, TotalSegmentator, or a future model) through **one** pipeline. Only the
*inference* notebook and its Docker image are model-specific; input conversion and
output conversion are shared.

> **Status: pre-release.** The framework, contracts, Dockerfiles, unified SNOMED
> mappings, WDL, and all three notebooks are in place, and the workflow has been run
> end-to-end on Terra/GPU for both MOOSE and TotalSegmentator (Sep 2026 batches, all
> succeeded). The four `imagingdatacommons/cloudsegmentator-*` images are **not yet
> published**; until they are, override the image inputs with your own build (see
> *Known gaps*). The legacy `workflows/MOOSE` and `workflows/TotalSegmentator` pipelines remain the
> supported path until then.

**More docs:** [operations.md](operations.md) — submitting, monitoring, triaging and
checking delivered outputs; [development.md](development.md) — changing the notebooks
and WDL safely, reproducing failures locally.

## Architecture

Three notebooks, two hand-off contracts, one parameterized WDL
([`Terra/twoVM.wdl`](../Terra/twoVM.wdl), `workflow Segmentator`):

```
Task 1  (GPU, per-model image)          Task 2  (CPU, output_conversion image)
┌────────────────────────────────┐      ┌───────────────────────────────────┐
│ nb1  convert  (SHARED)         │      │ nb3  output conversion  (SHARED)  │
│   DICOM → NIfTI                │      │   NIfTI seg → DICOM-SEG           │
│        │ Boundary A            │      │   + pyradiomics                   │
│        ▼                       │      │   + DICOM SR (TID1500)            │
│ nb2  inference  (PER-MODEL)    │ ---> │                                   │
│   NIfTI → segmentations        │  B   │                                   │
└────────────────────────────────┘      └───────────────────────────────────┘
```

- **nb1** [`common/Notebooks/convertNotebook.ipynb`](../../common/Notebooks/convertNotebook.ipynb) — download (IDC or private GCS) + `dcm2niix`.
- **nb2** `models/<model>/Notebooks/inference.ipynb` — the *only* per-model piece.
- **nb3** [`common/Notebooks/outputConversionNotebook.ipynb`](../../common/Notebooks/outputConversionNotebook.ipynb) — SEG + radiomics + delivery.

### Contracts (both are `tar.lz4` archives passed as WDL `File`s)

**Boundary A — nb1 → nb2** (`converted_nifti.tar.lz4`):
```
<SeriesInstanceUID>/<SeriesInstanceUID>.nii.gz      # primary CT volume
convert_manifest.json
```

**Boundary B — nb2 → nb3** (`segmentations.tar.lz4`):
```
<SeriesInstanceUID>/<model>/segmentations/*.nii.gz  # multilabel mask(s)
<SeriesInstanceUID>/<model>/label_map.json          # {"model": ..., "model_id": ..., "labels": {label_id: label_name}}
engine_provenance.json                              # {"engine": ..., "version": ...}
```
`<model>` is one directory per sub-model: each MOOSE model (`clin_ct_organs`, …) or
each TotalSegmentator task (`total`, `lung_vessels`).
The `label_map.json` sidecar is emitted by nb2 **at inference time** (moosez's own
`organ_indices`; TotalSegmentator's `class_map[<task>]`), so label IDs are always
authoritative and never hand-transcribed. nb3 joins each `label_name` against the
model's SNOMED CSV to build the dcmqi labelmap config. `model_id` names the model that
actually ran — the directory name, except TotalSegmentator `total` with `fast=True`,
which is `total_fast` (older archives without the field fall back to the directory name).

`engine_provenance.json` records the inference engine and its package version
(moosez / TotalSegmentator). nb3 stamps it into every SEG following the IDC
convention, extended with the `model_id`: `SegmentAlgorithmName`
`"MOOSE v<ver> clin_ct_organs"` / `"TotalSegmentator v<ver> total_fast"`, a versioned
`SeriesDescription`, and `ContentCreatorName` `"IDC"`. The paired SR carries the same
string in its `SeriesDescription` (`"<…> Radiomics"`) and in each measurement group's
`AlgorithmParameters` (`segmentation=<…>`), and every radiomics JSON row has
`model_id`, `seg_engine`, and `seg_engine_version`. Archives without the
sidecar fall back to the `modelName` input, unversioned. Each derived object gets a
distinct, run-stable `SeriesNumber`: MOOSE models keep their legacy slots 1–10,
TotalSegmentator tasks take 11–13 (by `model_id`, so `total_fast` gets 12), unknown models overflow to the next free slot, and
each paired SR is in a +50 block.

## Running on Terra

1. Import `SegmentatorTwoVmWorkflowOnTerra` (registered in [`.dockstore.yml`](../../../.dockstore.yml)).
2. Pick a model preset and set it as the workflow inputs:
   - MOOSE: [`models/moose/inputs.moose.json`](../../models/moose/inputs.moose.json) (all 10 `clin_ct_*` models)
   - TotalSegmentator: [`models/totalseg/inputs.totalseg.json`](../../models/totalseg/inputs.totalseg.json) (`total` task)
   - TotalSegmentator lung vessels: [`models/totalseg/inputs.totalseg_lung_vessels.json`](../../models/totalseg/inputs.totalseg_lung_vessels.json) (`lung_vessels` task)

   The presets fetch the notebooks from `ImagingDataCommons/CloudSegmentator` / `main`
   (`gitRepo` / `gitBranch` — override them to run a fork or a dev branch) and use the
   `imagingdatacommons/cloudsegmentator-*:main` images, which are not published yet.
3. Point `yamlListOfSeriesInstanceUIDs` at `this.SeriesInstanceUIDs` (or set `inputUri`
   + `secretProject` for a private GCS bucket — same HMAC/Secret-Manager setup as the
   legacy MOOSE workflow, see [`workflows/MOOSE/Docs/README.md`](../../MOOSE/Docs/README.md)).
4. Run.

To submit and monitor batches from the command line, see [operations.md](operations.md).

### Key inputs

| Input | Purpose |
|---|---|
| `inferenceDocker` | Per-model GPU image (`imagingdatacommons/cloudsegmentator-inference-<model>`). |
| `inferenceNotebookPath` | Repo path to the model's nb2. |
| `snomedMappingPath` | Repo path to the model's unified SNOMED CSV. |
| `inferenceParamsYaml` | Generic papermill passthrough for model knobs — new models need **no WDL change**. See *Model knobs* below. |
| `gitRepo` / `gitBranch` | Where notebooks + SNOMED CSV are fetched from (override for dev/fork branches). |
| `runRadiomics` / `runStructuredReport` | Harmonized output toggles (nb3). `runStructuredReport` emits one DICOM SR (TID1500, dcmqi `tid1500writer`) per SEG object (`structured_reports_dicom.tar`, meta-JSONs in `structured_reports_json.tar`), encoding each feature that has an IBSI quantity code + UCUM units in [`common/resources/radiomicsFeaturesMaps.csv`](../../common/resources/radiomicsFeaturesMaps.csv) — currently the first-order + shape classes; uncoded features (texture classes, engine extras) stay JSON-only. Requires `runRadiomics=true`. |
| `radiomicsMethod` | Radiomics engine when `runRadiomics=true`: `pyradiomics` (default) or `radiomicsjl` (JuliaHealth-style [`pzaffino/Radiomics.jl`](https://github.com/pzaffino/Radiomics.jl)). One engine per run — see *Comparing radiomics engines*. |
| `radiomicsFeatureClasses` | Comma-separated feature classes computed by whichever engine is selected, using engine-neutral pyradiomics-style names: `firstorder`, `shape`, `glcm`, `glrlm`, `glszm`, `ngtdm`, `gldm`, or `all`. Default `firstorder,shape`. Texture classes are much more expensive; unknown names are warned about and ignored. Recorded in `run_summary.json` as `radiomics_feature_classes`. |
| `radiomicsMaxRoiMvox` | Skip radiomics (SEG still written) for any label whose ROI exceeds this many Mvoxels; default `5.0` (organs/lungs/liver are < ~3 Mvox, a whole-body mask is 10–60). Skipped labels are listed in the radiomics JSON with a `radiomics_skipped` reason and counted in `output_conversion_UsageMetrics.csv` / `run_summary.json`. `<= 0` disables. |
| `outputConversionJuliaThreads` | Julia threads for the Radiomics.jl worker. Default **`0`** = all vCPUs (Radiomics.jl parallelises across the labels of a seg file). Needs Radiomics.jl ≥ 2.0.0, which the `output_conversion` image pins: earlier releases have a multi-label data race with > 1 thread (labels receive another label's values, or none), fixed upstream in PR #34. Verified Sep 2026: 2.0.0 at 4 threads is bit-identical to 1.3.3 at 1 thread on 450 real labels. |
| `inputUri` / `secretProject` | Private-GCS input (optional). |
| `checkpointGcsPath` | GCS prefix (e.g. the workspace bucket, `gs://fc-<id>/segmentator_ckpt`) for checkpoint/resume of the preemptible GPU task: nb1 bundles the converted NIfTIs there once, nb2 saves each finished (series, model) output, nb3 saves each finished series' DICOM-SEG + radiomics; a preempted VM's retry restores them and skips the done work (`checkpoint_restored` column in the usage-metrics CSVs); the run's prefix is deleted on success. Namespaced by the Cromwell workflow id, so different submissions never share state. Implemented in [`common/Notebooks/segmentator_checkpoint.py`](../../common/Notebooks/segmentator_checkpoint.py), fetched by the WDL next to the notebooks. Empty = disabled. |
| `dicomSegBucketUri` / `dicomStoreImportUri` | GCS upload + Healthcare API import (optional). The upload writes each SEG and its paired TID1500 SR side by side (`<SeriesInstanceUID>/<model>_<idx>_sr.dcm`), and the store import's `**.dcm` pattern picks up both. The GCS upload has been used in production runs; the **DICOM-store import has not been tested yet**. |
| `inferenceCpus` / `inferenceRAM` | GPU VM shape; see *Sizing* below. |

### Model knobs (`inferenceParamsYaml`)

| Model | Knob | Default | Purpose |
|---|---|---|---|
| MOOSE | `moose_models` | `clin_ct_organs,clin_ct_ribs,clin_ct_vertebrae` | Comma-separated moosez models; each becomes a `<uid>/<model>/` dir. |
| MOOSE | `series_timeout_s` | `1800` | Wall-clock cap per (series, worker launch). moosez runs in a worker subprocess per series, so a hung worker or native crash (e.g. kernel death) is recorded in `inference_errors.txt` for the in-flight model, and the worker is relaunched for the remaining models. `0` = no cap. |
| TotalSegmentator | `task` | `total` | Comma/space-separated task list, e.g. `total,lung_vessels`, which share one VM's download/convert/boot cost. Each task gets its own `<uid>/<task>/` dir, label map, and checkpoint. |
| TotalSegmentator | `fast` | `False` | 3 mm model; applies to the `total` task only. |
| TotalSegmentator | `task_timeout_min` | `90` | Wall-clock cap per (series, task); a hung/livelocked task is killed and recorded as an inference error instead of burning the VM. `0` = no cap. |

### Sizing

- **`lung_vessels` needs ~14 GiB RAM** on large volumes. At the default
  `inferenceRAM=16` it can livelock the VM (thrashing, not OOM-killed);
  `task_timeout_min` bounds the damage, but give it more RAM.
- Terra rounds the GPU VM up to a machine type that fits the RAM, so
  `inferenceRAM=32` silently becomes a 6-vCPU VM (~+14 % $/series). Measured sweet
  spots: **16 for MOOSE, 26 for TotalSegmentator** (including `lung_vessels`).

### Run metrics

Every notebook ends with a *Run metrics summary* cell: phase timers
(unpack/restore/pack/upload), compute sums, peak RAM, errors, and every prior
preempted or failed VM attempt of the same call (with its runtime, units done, last phase,
and peak RAM). The attempt ledger is kept under the checkpoint prefix, so it needs
`checkpointGcsPath`. The usage-metrics CSVs gain peak-RAM columns (append-only, so
`util/executionAnalytics` stays compatible), and `run_summary.json` carries
`phases_s`, `peak_mem_gb`, and prior-attempt counts (`prior_attempts`,
`prior_preempted_attempts`, `prior_attempts_vm_s`). nb3's summary also has a
`delivery` block with the outcome of the GCS upload and DICOM-store import, which
do not fail the task. When nb3 resumes from its checkpoint, the SEG / radiomics / SR
errors of restored series are reported again, so the error counts and files cover
the whole run.

## Adding a new model

1. Write `models/<model>/Notebooks/inference.ipynb` — read `converted_nifti.tar.lz4`,
   run the model, emit `segmentations.tar.lz4` in the **Boundary-B** layout (multilabel
   mask + `label_map.json`, plus `engine_provenance.json` so the SEGs carry a versioned
   algorithm name). nb3's `SeriesNumber` table also needs a slot for the new model;
   without one it overflows to the next free slot.
2. Write `models/<model>/Dockerfile` — `FROM imagingdatacommons/cloudsegmentator-base` and add
   only the model framework + baked weights.
3. Add `models/<model>/resources/snomed_mapping.csv` in the unified schema
   (`model,label_name,label_id,` + SNOMED columns; `label_id` may be blank — nb3 keys on
   `label_name`).
4. Add `models/<model>/inputs.<model>.json`.

nb1, nb3, the base image, and the WDL are reused unchanged.

## Docker build order

Four images. The GPU side (base + model inference) is **Python 3.12** on a CUDA
base; the CPU output-conversion image is **Python 3.11**, because the DICOM-SEG /
pyradiomics stack (`dcmqi`, `pyradiomics`, `pandas==1.5.3`) has no Python 3.12
wheels — this is the same proven 3.11 environment the previous post-process images
used.

```
GIT_HASH=$(git rev-parse HEAD)

# 1. CUDA base (convert + inference shared tooling: dcm2niix, s5cmd, papermill,
#    idc-index, gcloud libs). Python 3.12.
docker build -t imagingdatacommons/cloudsegmentator-base:main \
  --build-arg GIT_HASH=$GIT_HASH workflows/common/Dockerfiles/base

# 2. Per-model inference images (FROM the base + ML framework + weights)
docker build -t imagingdatacommons/cloudsegmentator-inference-moose:main \
  --build-arg GIT_HASH=$GIT_HASH workflows/models/moose
docker build -t imagingdatacommons/cloudsegmentator-inference-totalseg:main \
  --build-arg GIT_HASH=$GIT_HASH workflows/models/totalseg

# 3. Output-conversion image (nb3: DICOM-SEG + pyradiomics + Radiomics.jl). Python
#    3.11 for the DICOM-SEG/pyradiomics stack, plus a Julia 1.10 runtime with
#    Radiomics.jl precompiled for the `radiomicsMethod=radiomicsjl` path.
docker build -t imagingdatacommons/cloudsegmentator-output-conversion:main \
  --build-arg GIT_HASH=$GIT_HASH workflows/common/Dockerfiles/output_conversion
```

nb1 (convert) runs on the model inference image (which is `FROM cloudsegmentator-base`);
nb3 (output conversion) runs on `output_conversion`. Each model image is base + one
ML framework.

## Verifying the contracts locally

Each notebook runs standalone with papermill on a small IDC series list, so the
boundaries can be checked without Terra:

```
papermill common/Notebooks/convertNotebook.ipynb out1.ipynb \
  -y "SeriesInstanceUIDs: [<uid>]"                       # → converted_nifti.tar.lz4
papermill models/moose/Notebooks/inference.ipynb out2.ipynb \
  -p converted_nifti_path converted_nifti.tar.lz4 \
  -p moose_models clin_ct_organs                         # → segmentations.tar.lz4
papermill common/Notebooks/outputConversionNotebook.ipynb out3.ipynb \
  -p segmentationArchivePath segmentations.tar.lz4 \
  -p modelName moose                                     # → dicom_seg.tar + radiomics.tar
```
For MOOSE, `snomedMappingPath` is omitted: nb2 bundles moosez's own
`moose_snomed_mapping.csv` into the archive and nb3 reads that bundled copy.
Models that do not bundle a table into the archive (e.g. TotalSegmentator) instead
pass a curated CSV, e.g. `-p snomedMappingPath models/totalseg/resources/snomed_mapping.csv`
(derived from upstream's `totalsegmentator_snomed_mapping.csv`, plus rows for the
v2 `lung_vessels` classes that upstream does not map).
Confirm each archive matches the layout in *Contracts* above, and that
`dicom_seg.tar` imported into a Healthcare API store renders in OHIF
(`itkimage2segimage` preserves the source `StudyInstanceUID`).

## Comparing radiomics engines

nb3 can compute radiomics with either **pyradiomics** (Python, default) or
**Radiomics.jl** (Julia, [`pzaffino/Radiomics.jl`](https://github.com/pzaffino/Radiomics.jl),
IBSI-1 compliant). It is a **selector — one engine per run**; compare by running
the workflow twice with the same series list and different `radiomicsMethod`:

```
papermill common/Notebooks/outputConversionNotebook.ipynb out_py.ipynb \
  -p segmentationArchivePath segmentations.tar.lz4 -p modelName moose        # pyradiomics
papermill common/Notebooks/outputConversionNotebook.ipynb out_jl.ipynb \
  -p segmentationArchivePath segmentations.tar.lz4 -p modelName moose \
  -p radiomicsMethod radiomicsjl                                             # Radiomics.jl
```

Each emitted radiomics JSON row is stamped with `radiomics_method`, and
`run_summary.json` records the engine, so archives from the two runs are
self-describing when diffed.

**How it is wired.** Radiomics runs entirely in nb3, so `radiomicsMethod` is a
plain `String` WDL input threaded to the `outputConversion` task and on to the
notebook (mirroring `runRadiomics`). The Julia runtime + Radiomics.jl are baked
into the `output_conversion` image; the thin driver
[`common/Notebooks/radiomics_jl_extract.jl`](../../common/Notebooks/radiomics_jl_extract.jl)
(fetched next to nb3 by the WDL, so it can be iterated without an image rebuild)
owns all Radiomics.jl-specific API. nb3 runs it as **one persistent worker per
run** (`julia -t <outputConversionJuliaThreads|auto> radiomics_jl_extract.jl --worker`,
JSON request per segmentation file over stdin/stdout, all labels at once) so the
~8–10 s Julia startup/JIT is paid once per workflow rather than once per
(series × sub-model) — MOOSE emits 10 seg files per series — and Radiomics.jl can
parallelise across labels on the VM's vCPUs. The one-shot CLI form is kept for
manual use. Feature scope is the `radiomicsFeatureClasses` WDL input (papermill
`-p radiomicsFeatureClasses "firstorder,shape,glcm"`): nb3 normalizes the names and
maps them to pyradiomics feature classes or to Radiomics.jl symbols
(`firstorder`→`:first_order`, `shape`→`:shape3d`, texture names are identical), which
it sends to the worker with every request (`"features": [...]`).

> **Cost note (pilot, Aug 2026).** Radiomics time scales with ROI voxels; MOOSE's
> `clin_ct_body` (whole-body mask, 2 labels) alone took ~1170 s/series of the
> ~1500 s/series MOOSE nb3 total, with only first-order + 3D shape enabled. This is
> why `radiomicsMaxRoiMvox` (default 5) skips radiomics for such labels; set it to
> `0` to compute everything.

> **Feature-set caveat.** The two engines' feature *names/definitions* differ, so a
> head-to-head only makes sense on matching feature classes. Because
> `radiomicsFeatureClasses` is engine-neutral, the same value (e.g.
> `firstorder,shape,glcm`) enables the corresponding class in both engines; run the
> two `radiomicsMethod` values with an identical `radiomicsFeatureClasses`. Note
> the pilot cost numbers below were measured with the default first-order + shape.

## Estimating cost

`util/executionAnalytics/` holds the cost-measurement protocol: pick the cheapest region
for the two VM shapes (`region_prices.py`), build a designed pilot + a full-run Terra data
table from the same IDC cohort (`make_terra_manifest.py`), pull per-task billing and
per-series timings for a submission (`submission_cost.py`), fit a per-task
`a + b·nSeries + c·Mvoxels` model on the pilot and predict / evaluate the larger run
(`cost_model.py`), with figures of cost vs #series / voxels / slices and a per-phase time
profile. See [`util/executionAnalytics/README.md`](../../../util/executionAnalytics/README.md).
For the pilot and the full run keep the configuration identical (image digests,
`radiomicsMethod`, region, machine shapes); `radiomicsMethod=radiomicsjl` makes nb3 ~8×
cheaper than pyradiomics on the same series.

## Known gaps

- **Release images**: all four images are built and in use, but only under a personal
  dev namespace. They still need pushing as `imagingdatacommons/cloudsegmentator-{base,
  inference-moose,inference-totalseg,output-conversion}:main`, which is what the WDL
  defaults and the presets expect. The names deliberately differ from the legacy
  `imagingdatacommons/inference_{moose,totalseg}`, which belong to the per-model
  workflows and must not be overwritten.
- **DICOM-store import** (`dicomStoreImportUri`) has never been exercised end-to-end.
- **dcmqi `Invalid Value`**: ~2.4 % of series fail SEG conversion with this dcmqi error;
  they are recorded in `dicom_seg_error_file.txt` and the rest of the batch completes.
- **Radiomics.jl single-slice ROIs**: labels confined to one slice are computed as 2D
  (no `shape3d` features; `total_energy` misses the z spacing) — an upstream regression
  in 1.3.3 that 2.0.0 still has, independent of the thread count. Unreported upstream;
  see `common/Docs/radiomicsjl-upstream-issues/`.
- **SR feature coverage**: only features with a coded row in
  `common/resources/radiomicsFeaturesMaps.csv` (first-order + shape) appear in the
  TID1500 SRs; texture-class features would need IBSI codes added to the CSV.
- **Base-image pinning**: the base pins pip deps by `==` but the CUDA base tag is not
  yet pinned by `@sha256` (follow the TotalSegmentator Dockerfile discipline before release).
- **CWL / SevenBridges** parity is out of scope for this iteration (WDL-first).
