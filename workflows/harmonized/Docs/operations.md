# Operating the harmonized workflow on Terra

How to submit batches, watch them, triage failures, and check what was delivered.
For what the workflow does and its inputs, see [README.md](README.md); for changing
it, see [development.md](development.md); for cost, see
[`util/executionAnalytics/README.md`](../../../util/executionAnalytics/README.md).

## Command-line tooling

[`util/terraOps/`](../../../util/terraOps) drives the Terra REST API
(auth: `gcloud auth print-access-token`; run `gcloud auth login` once). Every
script takes its target from a flag or an environment variable:

| Setting | Flag | Env var | What |
|---|---|---|---|
| Workspace | `--workspace` | `TERRA_WORKSPACE` | `<namespace>/<name>` |
| Method config | `--config` | `TERRA_METHOD_CONFIG` | `<namespace>/<name>` |
| Image registry | `--registry` | `SEGMENTATOR_REGISTRY` | Docker Hub namespace of the `cloudsegmentator-inference-{moose,totalseg}:main` and `cloudsegmentator-output-conversion:main` images |
| Delivery bucket | `--bucket` | `SEGMENTATOR_DELIVERY_BUCKET` | `dicomSegBucketUri`; `none` disables delivery; unset leaves the config's value |

| Script | Does |
|---|---|
| `upload_table.py <name>` | Uploads `manifests/<name>_terra_data_table.tsv` (root entity `twoVM_<name>`) and an entity set `<name>_all` over every row. |
| `submit_wave.py <rootType> <entity> [entityType] [expression]` | Submits MOOSE (all 10 `clin_ct_*` models) and TotalSegmentator (`total,lung_vessels`) by editing then submitting the shared method config; `--models` to pick. Sets `inferenceRAM` per engine (see [Sizing](README.md#sizing)). |
| `watch_wave.py label:submissionId ...` | Prints a line per status change; exits when all are terminal; warns hourly after 3 h. |
| `check_outputs.py <submissionId>` | Per-workflow status, run summaries, and every error file. |

## Before any submission

1. **Commit and push** the branch the method config points at (`gitRepo` /
   `gitBranch`). Notebooks, `segmentator_checkpoint.py`, `radiomics_jl_extract.jl`
   and the SNOMED CSVs are fetched from GitHub raw **at run time** — local edits
   do not run.
2. **Check Dockstore synced the WDL** (webhook, usually instant):
   ```
   curl -s "https://dockstore.org/api/ga4gh/trs/v2/tools/%23workflow%2Fgithub.com%2F<org>%2FCloudSegmentator%2FSegmentatorTwoVmWorkflowOnTerra/versions/<branch>/PLAIN-WDL/descriptor" | grep '<changed text>'
   ```
3. If a Dockerfile changed, make sure the image is rebuilt — configs pin `:main`,
   so Terra runs whatever `:main` currently is. On upstream `main`,
   `.github/workflows/harmonized_images.yml` rebuilds and pushes the affected images
   automatically (wait for the run to finish; check the Actions tab). On a fork or dev
   branch, build and push to your own registry and submit with `--registry`.
4. Try risky changes on **one small entity** (~3 series, ~$0.10, 15–60 min)
   before a batch.

## Submitting a batch

```
cd util/executionAnalytics
python make_terra_manifest.py full --collections '<idc collection pattern>' ... \
  --n-series 60 --batch-target 900000000 --seed <n> \
  --exclude manifests/*_series.csv --name <name> --outdir manifests
python ../terraOps/upload_table.py <name>
python ../terraOps/submit_wave.py twoVM_<name> <name>_all twoVM_<name>_set this.twoVM_<name>s
# one entity:  python ../terraOps/submit_wave.py twoVM_<name> <entity id>
```

- `--batch-target 900000000` voxels ≈ 20 series per entity, the measured
  $/series knee (the default target, ~6 per entity, is below it).
- Exclude every earlier `*_series.csv` unless you mean to re-run series.
- The method config is a shared mutable slot, but Terra snapshots it per
  submission, so reconfigure-then-submit per engine is safe.

## Monitoring

- Typical wall clock for a 20-series entity on spot T4s: TotalSegmentator 1–3 h,
  MOOSE 1.5–4.5 h; 3-series entities 12–60 min.
- **Preemption varies a lot**: identical workloads have seen zero preemptions
  and 3–8 attempts per workflow in the same week. After
  `inferencePreemptibleTries` / `outputConversionPreemptibleTries` spot attempts
  (default 3) a task falls back to on-demand (2.2× spot). With `checkpointGcsPath` set,
  a retry restores the NIfTI bundle and finished (series, task) outputs in ~12 s.
- **Stuck vs slow**: a workflow "Running" for hours with no new objects under
  `<checkpointGcsPath>/<submissionId>_<workflowId>/` is wedged. Read the call's
  live log in the workspace bucket
  (`submissions/<sid>/Segmentator/<wid>/call-inference/stderr`, retries under
  `attempt-N/`; synced lazily) and abort with
  `DELETE /api/workspaces/{ns}/{name}/submissions/{sid}` — other workflows in
  the submission keep their results.
- nb3 runs on a 16 GB VM; series ≳300 Mvox can crash its Radiomics.jl worker,
  losing that (series, task)'s radiomics + SR (the SEG survives).
- **Checkpoint storage**: a run's `<checkpointGcsPath>/<submissionId>_<workflowId>/`
  prefix (NIfTIs plus every segmentation, often GBs per batch) is deleted only when
  output conversion succeeds. Failed and aborted runs keep it, for recovery. Expire
  old ones with a lifecycle rule on the bucket, e.g. delete objects under the
  checkpoint prefix after 14 days.

## Triage

Known failure signatures — check these before treating an error as new:

| Signature | Meaning |
|---|---|
| `itkimage2segimage ... Invalid Value` | A small class of series (~2 %) fails SEG conversion for all models and both engines (dcmqi; unfixed). Recorded in `dicom_seg_error_file.txt`; the rest of the batch completes. |
| `radiomics_jl_extract.jl ... NaN not allowed` | A NaN feature (e.g. std/skew/kurtosis of a 1-voxel label) dropped one (series, model)'s radiomics + SR. The driver now skips non-finite values; only in runs of older code. |
| `body_composition: moose produced no output` | No L3 in the field of view — benign. |
| `Radiomics.jl worker crashed twice` | nb3 RAM pressure on a very large series. |
| Missing lungs / ribs / lung_vessels files for a series | Empty mask outside the field of view — by design. |
| `delivery gcs_upload: failed` / `dicom_store_import: failed` (check_outputs.py) | Nothing, or only part, reached the bucket or store although the workflow Succeeded — usually IAM on the bucket or store. The import is `skipped` whenever the upload failed. |

Terra's `cost` field is an estimate (it has been 3× off under preemption churn,
and exact on calm days); measure with `util/executionAnalytics/submission_cost.py`
once billing settles, 24–48 h after the run.

## Delivered outputs

### GCS bucket

With `dicomSegBucketUri = gs://<bucket>/<prefix>/` (writable by the Terra pet
service account; no secrets needed), nb3 uploads every SEG and its TID1500 SR as
`<prefix>/<SeriesInstanceUID>/<model>_<idx>[_sr].dcm`.

- **Overwrites but never deletes.** Names are deterministic, so a re-run
  replaces files in place, but a file the new run did not produce (e.g. an SR
  lost to a failed radiomics step) stays behind with old metadata. Judge
  freshness by object timestamp (`gcloud storage ls -l`), not by folder.
- Upload and DICOM-store import failures do **not** fail the workflow. nb3
  records each step's outcome (`ok` / `failed` / `timeout` / `skipped`, file
  counts, error text) in the `delivery` block of `run_summary.json`, and
  `check_outputs.py` prints it. Still spot-check the bucket after enabling it on
  a new config.
- Each SEG/SR is a new DICOM series inside the **source study**. Re-uploading
  creates new SOPInstanceUIDs, so a DICOM store that imported the old version
  keeps both.

The metadata stamped on each object is described under
[Contracts](README.md#contracts-both-are-tarlz4-archives-passed-as-wdl-files).

### Checking SEG metadata with pydicom

dcmqi **labelmap** SEGs start with a background segment (SegmentNumber 0) whose
`SegmentAlgorithmName` is empty and `SegmentAlgorithmType` is `MANUAL`. Skip it —
reading `SegmentSequence[0]` wrongly suggests the metadata is missing:

```python
ds = pydicom.dcmread(f, stop_before_pixels=True)
segs = [s for s in ds.SegmentSequence if int(s.SegmentNumber) != 0]
```

### Healthcare DICOM store import (not yet validated)

nb3's `dicomStoreImportUri` path (GCS → `dicomStores.import`, polled) has not run
successfully end-to-end. Prerequisites:

1. The store's project has **active billing** and the Healthcare API enabled.
2. The pet service account has `roles/healthcare.dicomEditor` on the dataset.
3. That project's Healthcare service agent
   (`service-<PROJECT_NUMBER>@gcp-sa-healthcare.iam.gserviceaccount.com`) can
   read the staging bucket — if you don't administer the bucket, its owner has
   to grant this.
4. The URI is the bare resource name
   `projects/P/locations/L/datasets/D/dicomStores/S` (no `https://`, no
   `/dicomWeb`). The import pattern `<bucket>/**.dcm` picks up SEGs and SRs.
5. Deflate transfer syntax (used by the SEGs) is supported by the Healthcare API.
6. Import failures only warn in the output notebook — verify in the store.
