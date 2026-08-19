# Harmonized Segmentator Workflow

A single, model-agnostic Terra/WDL workflow that runs **any** segmentation model
(MOOSE, TotalSegmentator, or a future model) through **one** pipeline. Only the
*inference* notebook and its Docker image are model-specific; input conversion and
output conversion are shared.

> **Status: pre-release.** The framework, contracts, Dockerfiles, unified SNOMED
> mappings, WDL, and all four notebooks are in place. It has **not yet been validated
> end-to-end on Terra/GPU**, the `imagingdatacommons/segmentator-base` and per-model
> images still need building/pushing, and DICOM SR (TID1500) encoding in nb3 is not
> yet ported (see *Known gaps*). The legacy `workflows/MOOSE` and
> `workflows/TotalSegmentator` pipelines remain the supported path until this is
> validated.

## Architecture

Three notebooks, two hand-off contracts, one parameterized WDL
([`Terra/twoVM.wdl`](../Terra/twoVM.wdl), `workflow Segmentator`):

```
Task 1  (GPU, per-model image)          Task 2  (CPU, output_conversion image)
┌───────────────────────────────┐      ┌───────────────────────────────────┐
│ nb1  convert  (SHARED)         │      │ nb3  output conversion  (SHARED)  │
│   DICOM → NIfTI                │      │   NIfTI seg → DICOM-SEG           │
│        │ Boundary A            │      │   + pyradiomics                   │
│        ▼                       │      │   + (SR: see Known gaps)          │
│ nb2  inference  (PER-MODEL)    │ ───▶ │                                   │
│   NIfTI → segmentations        │  B   │                                   │
└───────────────────────────────┘      └───────────────────────────────────┘
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
<SeriesInstanceUID>/<model>/label_map.json          # {"model": ..., "labels": {label_id: label_name}}
```
The `label_map.json` sidecar is emitted by nb2 **at inference time** (moosez's own
`organ_indices`; TotalSegmentator's `class_map['total']`), so label IDs are always
authoritative and never hand-transcribed. nb3 joins each `label_name` against the
model's SNOMED CSV to build the dcmqi labelmap config.

## Running on Terra

1. Import `SegmentatorTwoVmWorkflowOnTerra` (registered in [`.dockstore.yml`](../../../.dockstore.yml)).
2. Pick a model preset and set it as the workflow inputs:
   - MOOSE: [`models/moose/inputs.moose.json`](../../models/moose/inputs.moose.json)
   - TotalSegmentator: [`models/totalseg/inputs.totalseg.json`](../../models/totalseg/inputs.totalseg.json)
3. Point `yamlListOfSeriesInstanceUIDs` at `this.SeriesInstanceUIDs` (or set `inputUri`
   + `secretProject` for a private GCS bucket — same HMAC/Secret-Manager setup as the
   legacy MOOSE workflow, see [`workflows/MOOSE/Docs/README.md`](../../MOOSE/Docs/README.md)).
4. Run.

### Key inputs

| Input | Purpose |
|---|---|
| `inferenceDocker` | Per-model GPU image (`imagingdatacommons/inference_<model>`). |
| `inferenceNotebookPath` | Repo path to the model's nb2. |
| `snomedMappingPath` | Repo path to the model's unified SNOMED CSV. |
| `inferenceParamsYaml` | Generic papermill passthrough for model knobs (`moose_models`, `fast`, …) — new models need **no WDL change**. |
| `gitRepo` / `gitBranch` | Where notebooks + SNOMED CSV are fetched from (override for dev/fork branches). |
| `runRadiomics` / `runStructuredReport` | Harmonized output toggles (nb3). |
| `radiomicsMethod` | Radiomics engine when `runRadiomics=true`: `pyradiomics` (default) or `radiomicsjl` (JuliaHealth-style [`pzaffino/Radiomics.jl`](https://github.com/pzaffino/Radiomics.jl)). One engine per run — see *Comparing radiomics engines*. |
| `radiomicsMaxRoiMvox` | Skip radiomics (SEG still written) for any label whose ROI exceeds this many Mvoxels; default `5.0` (organs/lungs/liver are < ~3 Mvox, a whole-body mask is 10–60). Skipped labels are listed in the radiomics JSON with a `radiomics_skipped` reason and counted in `output_conversion_UsageMetrics.csv` / `run_summary.json`. `<= 0` disables. |
| `outputConversionJuliaThreads` | Julia threads for the Radiomics.jl worker (`0` = all vCPUs). |
| `inputUri` / `secretProject` | Private-GCS input (optional). |
| `dicomSegBucketUri` / `dicomStoreImportUri` | GCS upload + Healthcare API import (optional). |

## Adding a new model

1. Write `models/<model>/Notebooks/inference.ipynb` — read `converted_nifti.tar.lz4`,
   run the model, emit `segmentations.tar.lz4` in the **Boundary-B** layout (multilabel
   mask + `label_map.json`).
2. Write `models/<model>/Dockerfile` — `FROM imagingdatacommons/segmentator-base` and add
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
docker build -t imagingdatacommons/segmentator-base:main \
  --build-arg GIT_HASH=$GIT_HASH workflows/common/Dockerfiles/base

# 2. Per-model inference images (FROM the base + ML framework + weights)
docker build -t imagingdatacommons/inference_moose:main \
  --build-arg GIT_HASH=$GIT_HASH workflows/models/moose
docker build -t imagingdatacommons/inference_totalseg:main \
  --build-arg GIT_HASH=$GIT_HASH workflows/models/totalseg

# 3. Output-conversion image (nb3: DICOM-SEG + pyradiomics + Radiomics.jl). Python
#    3.11 for the DICOM-SEG/pyradiomics stack, plus a Julia 1.10 runtime with
#    Radiomics.jl precompiled for the `radiomicsMethod=radiomicsjl` path.
docker build -t imagingdatacommons/output_conversion:main \
  --build-arg GIT_HASH=$GIT_HASH workflows/common/Dockerfiles/output_conversion
```

nb1 (convert) runs on the model inference image (which is `FROM segmentator-base`);
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
  -p modelName moose                                     # → dicom_seg.tar.lz4 + radiomics.tar.lz4
```
For MOOSE, `snomedMappingPath` is omitted: nb2 bundles moosez's own
`moose_snomed_mapping.csv` into the archive and nb3 reads that bundled copy.
Models whose engine ships no SNOMED table (e.g. TotalSegmentator v1.5.6) instead
pass a curated CSV, e.g. `-p snomedMappingPath models/totalseg/resources/snomed_mapping.csv`.
Confirm each archive matches the layout in *Contracts* above, and that
`dicom_seg.tar.lz4` imported into a Healthcare API store renders in OHIF
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
manual use. Feature scope for each engine is a one-line edit:
`PYRADIOMICS_FEATURE_CLASSES` in nb3, `FEATURES` in the `.jl` driver.

> **Cost note (pilot, Aug 2026).** Radiomics time scales with ROI voxels; MOOSE's
> `clin_ct_body` (whole-body mask, 2 labels) alone took ~1170 s/series of the
> ~1500 s/series MOOSE nb3 total, with only first-order + 3D shape enabled. This is
> why `radiomicsMaxRoiMvox` (default 5) skips radiomics for such labels; set it to
> `0` to compute everything.

> **Feature-set caveat.** The two engines' feature *names/definitions* differ, so a
> head-to-head only makes sense on matching feature classes. The pyradiomics config
> defaults to first-order + shape; Radiomics.jl additionally offers texture matrices
> (GLCM/GLSZM/GLRLM/NGTDM/GLDM). To compare a given class, enable it on **both**
> sides (e.g. add `glcm`/`firstorder` to `PYRADIOMICS_FEATURE_CLASSES` and the
> corresponding `:glcm`/`:first_order` to the driver's `FEATURES`).

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

- **End-to-end Terra/GPU validation** has not been run yet.
- **Docker images** (`segmentator-base`, `inference_moose`, `inference_totalseg`) still
  need building and pushing to Docker Hub before the presets resolve.
- **DICOM SR (TID1500)** encoding in nb3 is not yet ported from
  `TotalSegmentator/Notebooks/dicomsegAndRadiomicsSR_Notebook.ipynb`; `runStructuredReport`
  currently emits only the radiomics-measurement JSON bundle
  (`structured_reports_json.tar.lz4`), not `structured_reports_dicom.tar.lz4`.
- **Base-image pinning**: the base pins pip deps by `==` but the CUDA base tag is not
  yet pinned by `@sha256` (follow the TotalSegmentator Dockerfile discipline before release).
- **Checkpoint/resume** (`checkpointGcsPath`) is threaded through the WDL and nb2
  parameter cells but not yet implemented in the split notebooks.
- **CWL / SevenBridges** parity is out of scope for this iteration (WDL-first).
