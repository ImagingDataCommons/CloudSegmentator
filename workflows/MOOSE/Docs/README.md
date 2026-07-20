# MOOSE Workflow

This workflow runs [MOOSE](https://github.com/QIMP-Team/MOOSE) (`moosez`) clinical
CT segmentation on Terra. It downloads a DICOM series (from Imaging Data Commons or
a private GCS bucket), converts it to NIfTI, runs one or more `moosez` models, and
converts the resulting masks to DICOM-SEG.

See the root [README](../../../README.md) for general background on Dockstore/Terra
and how to import a workflow into a workspace before following the steps below.

## Which WDL to use

| | [`twoVM.wdl`](../Terra/splitWorkflow/twoVM.wdl) | [`oneVM.wdl`](../Terra/splitWorkflow/oneVM.wdl) |
|---|---|---|
| Recommended | Yes | No (legacy/simple) |
| Tasks | 2: GPU inference, then CPU post-processing | 1: everything on a single GPU VM |
| Input source | IDC **or** a private GCS bucket | IDC only |
| DICOM-SEG output | Yes | No (NIfTI masks only) |
| Output bucket / Healthcare API upload | Yes | No |
| Checkpoint/resume on preemption | Yes | No |

`twoVM` splits inference (GPU) from DICOM-SEG generation (CPU-only), which is
cheaper since the CPU post-processing task doesn't hold a GPU idle. The rest of
this document describes `twoVM`; `oneVM` is a minimal subset of the same
inference parameters (`yamlListOfSeriesInstanceUIDs`, `mooseModels`,
`accelerator`, plus compute-shape overrides) with no bucket or secret setup.

## Running the workflow on Terra

1. Import [`MOOSEtwoVmWorkflowOnTerra`](https://dockstore.org/organizations/ImagingDataCommons/collections/CloudSegmentator)
   into a Terra workspace (see the root README's *Importing workflows into Terra*
   section).
2. Import a data table of series to process. A sample manifest is at
   [`Docs/sampleManifests/batch_1.yaml`](sampleManifests/batch_1.yaml).
3. Under `WORKFLOWS`, choose the imported workflow, then
   **Run workflow(s) with inputs defined by data table**, and select the
   imported data table as the root entity.
4. Under `INPUTS`, set `yamlListOfSeriesInstanceUIDs` to `this.SeriesInstanceUIDs`.
   Leave everything else at its default for a first run.
5. Under `OUTPUTS`, use defaults, then **RUN ANALYSIS**.

For a private-bucket input instead of IDC, or to copy/import results
somewhere, see [Downloading private data](#downloading-private-data--storing-secrets)
and [Output bucket setup](#output-bucket-setup) below — both are one-time
setup, then a couple of extra workflow inputs per run.

## Argument reference (`twoVM.wdl`)

### Input source

| Argument | Default | Description |
|---|---|---|
| `yamlListOfSeriesInstanceUIDs` | `""` | YAML list of SeriesInstanceUIDs to pull from IDC. Required unless `inputUri` is set. |
| `inputUri` | `""` | `gs://` URI to read DICOM from instead of IDC; series are discovered by reading each file's SeriesInstanceUID tag. Requires `secretProject`. See [Downloading private data](#downloading-private-data--storing-secrets). |
| `secretProject` | `""` | GCP project holding the `s5cmd-hmac-key-id` / `s5cmd-hmac-secret` secrets. Only needed when `inputUri` is set. |

### Analysis parameters

| Argument | Default | Description |
|---|---|---|
| `mooseModels` | `clin_ct_body,clin_ct_body_composition,clin_ct_cardiac,clin_ct_digestive,clin_ct_lungs,clin_ct_muscles,clin_ct_organs,clin_ct_peripheral_bones,clin_ct_ribs,clin_ct_vertebrae` | Comma-separated `moosez` clinical CT model names to run. |
| `accelerator` | `cuda` | `cuda` for GPU, `cpu` for CPU-only. Falls back to `cpu` automatically if `cuda` is requested but no GPU is detected. |
| `checkpointGcsPath` | `""` | GCS prefix (e.g. `gs://fc-<bucket>/moose_ckpt`) for per-series checkpoints. When set, a preempted inference VM restores already-finished series/models on restart instead of redoing the whole batch. Must be writable by the VM pet service account — a Terra workspace bucket already is. Empty disables checkpointing. |

### Inference task (GPU)

| Argument | Default | Description |
|---|---|---|
| `mooseInferenceDocker` | `sunderlandkyl/moose-test:latest` | Docker image for Task 1. Built from [`Dockerfiles/inference_moose`](../Dockerfiles/inference_moose/Dockerfile). |
| `mooseInferencePreemptibleTries` | `3` | Preemptible retry count. |
| `mooseInferenceCpus` | `4` | vCPUs. |
| `mooseInferenceRAM` | `16` | RAM, GiB. |
| `mooseInferenceDiskGB` | `50` | Local disk, GB. |
| `mooseInferenceDiskType` | `HDD` | Disk type. |
| `mooseInferenceGpuType` | `nvidia-tesla-t4` | GPU model. |
| `mooseInferenceGpuCount` | `1` | GPU count. |
| `mooseInferenceZones` | `us-east4-a us-east4-b us-east4-c` | Candidate zones — must all be in one region (Google Cloud Batch requirement) and must have the requested GPU type available. |

### Post-processing task (CPU)

| Argument | Default | Description |
|---|---|---|
| `moosePostProcessDocker` | `sunderlandkyl/post_process_moose:latest` | Docker image for Task 2. Built from [`Dockerfiles/post_process_moose`](../Dockerfiles/post_process_moose/Dockerfile). |
| `moosePostProcessPreemptibleTries` | `3` | Preemptible retry count. |
| `moosePostProcessCpus` | `4` | vCPUs. |
| `moosePostProcessRAM` | `16` | RAM, GiB. |
| `moosePostProcessDiskGB` | `20` | Local disk, GB. In IDC mode each series is downloaded/used/deleted one at a time, so usage stays bounded to ~1 series. In GCS mode (`inputUri` set) the whole cohort downloads before per-series cleanup, so a large cohort may need more. |
| `moosePostProcessDiskType` | `HDD` | Disk type. |
| `moosePostProcessCpuFamily` | `AMD Rome` | CPU platform — cheapest CPU family on Terra per Thiriveedhi et al. |
| `moosePostProcessZones` | `us-east4-a us-east4-b us-east4-c` | Candidate zones. |

### Optional: copy DICOM-SEG to a GCS bucket

| Argument | Default | Description |
|---|---|---|
| `dicomSegBucketUri` | `""` | GCS prefix, e.g. `gs://idc-not-a-challenge/kyle/`. When set, per-series uncompressed `.dcm` SEG files are uploaded there under `<SeriesInstanceUID>/`. Empty skips upload. **Not a secret** — authenticated via the VM's own service account, see [Output bucket setup](#output-bucket-setup). |

### Optional: import DICOM-SEG into a Healthcare API DICOM store

| Argument | Default | Description |
|---|---|---|
| `dicomStoreImportUri` | `""` | Full dicomStore resource name: `projects/PROJECT/locations/LOCATION/datasets/DATASET/dicomStores/STORE`. Triggers a `dicomStores.import` job pulling from `dicomSegBucketUri` (which must also be set). The store may live in a different GCP project. Empty skips import. **Not a secret**, see [Output bucket setup](#output-bucket-setup). |

### Outputs

| Output | Description |
|---|---|
| `mooseInferenceNotebook`, `moosePostProcessNotebook` | Executed notebooks (logs) for each task, for debugging. |
| `mooseSegmentations` | `moose_segmentations.tar.lz4` — NIfTI masks + source NIfTI volumes. |
| `mooseStatsCSVs` | `moose_stats.tar.lz4` — per-series, per-model volume + HU intensity CSVs written natively by `moosez`. |
| `mooseDicomSegFiles` | `moose_dicom_seg.tar.lz4` — generated DICOM-SEG files. |
| `mooseInferenceUsageMetricsCsv`, `moosePostProcessUsageMetricsCsv`, `combinedUsageMetricsCsv` | Per-phase and combined CPU/GPU/timing metrics. |
| `mooseRunSummary` | Optional JSON summary of the run (series counts, errors, GPU/timing facts). |
| `downloadErrors`, `dcm2niixErrors`, `mooseInferenceErrors`, `dicomSegErrors`, `statsUploadErrors` | Optional error files, only produced when something failed. |

## Downloading private data & storing secrets

By default the workflow pulls DICOM from Imaging Data Commons — no credentials
needed. To instead read from a private GCS bucket, set `inputUri` to a `gs://`
path. Both the inference task (Task 1) and the post-processing task (Task 2,
which re-downloads reference DICOM for `itkimage2segimage`) use the same
mechanism.

Reading a private bucket uses [`s5cmd`](https://github.com/peak/s5cmd), which
needs **HMAC keys** rather than the VM's own identity, so it can be pointed at
any bucket you have access to, independent of the VM's own project/IAM. This
is a one-time setup per source bucket:

1. **Create a dedicated reader service account** in the GCP project that owns
   the data bucket (e.g. `s5cmd-data-reader`), and grant it
   `roles/storage.objectViewer` on that bucket.
2. **Generate an HMAC key** for that service account — Cloud Storage >
   Settings > Interoperability in the Console, or:
   ```
   gcloud storage hmac create s5cmd-data-reader@PROJECT.iam.gserviceaccount.com
   ```
   Save the returned access key ID and secret — the secret is shown only once.
3. **Store the HMAC key as two secrets** in Secret Manager, in a GCP project
   of your choice (this is what the `secretProject` workflow input points at
   — it can be the data bucket's project or any other project you control):
   ```
   gcloud secrets create s5cmd-hmac-key-id --replication-policy=automatic
   gcloud secrets create s5cmd-hmac-secret --replication-policy=automatic
   echo -n "ACCESS_KEY_ID" | gcloud secrets versions add s5cmd-hmac-key-id --data-file=-
   echo -n "SECRET"        | gcloud secrets versions add s5cmd-hmac-secret --data-file=-
   ```
4. **Grant your Terra proxy group access to both secrets.** Find your proxy
   group on your Terra profile page (`PROXY_<hash>@firecloud.org`), then grant
   it `roles/secretmanager.secretAccessor` on `s5cmd-hmac-key-id` and
   `s5cmd-hmac-secret` in `secretProject`, so workflows running under your
   Terra identity can fetch them at runtime.
5. **Set the workflow inputs**: `inputUri` (the `gs://` path to read) and
   `secretProject` (the project from step 3). Leave
   `yamlListOfSeriesInstanceUIDs` empty — it's ignored when `inputUri` is set.

At runtime, both notebooks fetch the two secrets via the
`google-cloud-secret-manager` client, write them to `~/.aws/credentials`, and
run `s5cmd --endpoint-url https://storage.googleapis.com cp s3://<bucket>/<prefix>/*`
to stage the files, then sort them into per-series folders by reading each
file's SeriesInstanceUID tag.

## Output bucket setup

There are three independent, optional places the workflow can write to a GCS
bucket. Unlike the private-data-download setup above, **none of these use
HMAC keys or secrets** — they authenticate as the VM's own pet/proxy service
account via Application Default Credentials (ADC), so the only setup is
granting that service account the right IAM role on the destination.

If you don't know the VM's pet service account email, the default Terra
workspace bucket already grants it write access — using
`gs://<your-workspace-bucket>/...` as the destination for any of the three
paths below works without any extra IAM changes. For a bucket outside the
workspace, find the pet SA under your Terra workspace's Cloud Information
panel, then grant it the roles below on that bucket with, e.g.:
```
gcloud storage buckets add-iam-policy-binding gs://YOUR_BUCKET \
  --member="serviceAccount:PET_SA_EMAIL" --role="ROLE"
```

### 1. Copy generated DICOM-SEG files (`dicomSegBucketUri`)

Set `dicomSegBucketUri` to a `gs://bucket/prefix` (e.g.
`gs://idc-not-a-challenge/kyle/`). Post-processing uploads each series'
`.dcm` SEG files there, preserving a `<SeriesInstanceUID>/<file>.dcm` layout.
Grant the VM's pet service account `roles/storage.objectAdmin` (or at least
`objectCreator`) on the bucket. Empty (default) skips upload — the
`mooseDicomSegFiles` workflow output still carries every SEG regardless.

### 2. Import DICOM-SEG into a Healthcare API DICOM store (`dicomStoreImportUri`)

Set `dicomStoreImportUri` to a full dicomStore resource name:
`projects/PROJECT/locations/LOCATION/datasets/DATASET/dicomStores/STORE`.
Requires `dicomSegBucketUri` to also be set, since the import job reads the
`.dcm` files from that GCS location server-side (not pushed). The store may
live in a different GCP project than the one running the workflow — the
resource name fully qualifies the target, and Healthcare API authorization is
IAM-based on that resource rather than the calling project. Two grants are
needed, both in whichever project hosts the dataset:
- The VM's pet service account needs `roles/healthcare.dicomEditor` on the
  dataset (this is what triggers the import).
- The **Cloud Healthcare API service agent** in that project needs
  `roles/storage.objectViewer` on the source bucket (this is what lets the
  import job actually read the files).

The import runs as a long-running operation, polled until completion (30
minute timeout) or failure. Since `itkimage2segimage` preserves the source
`StudyInstanceUID`, imported SEGs attach to the existing study and render as
overlays in OHIF — the source images must already be in the store.

### 3. Checkpoint/resume storage (`checkpointGcsPath`)

Set `checkpointGcsPath` to a `gs://bucket/prefix` (e.g.
`gs://fc-<bucket>/moose_ckpt`). The inference task writes converted NIfTI and
finished (series, model) segmentation results there as it goes, so a
preempted VM resumes from checkpoint instead of redoing the whole batch. Must
be writable by the VM pet service account (`roles/storage.objectAdmin` or
`objectCreator`) — a Terra workspace bucket already is. Empty (default)
disables checkpointing.

## Docker images

| Image | Dockerfile | Used by |
|---|---|---|
| `imagingdatacommons/inference_moose` | [`Dockerfiles/inference_moose`](../Dockerfiles/inference_moose/Dockerfile) | `mooseInference` task (Task 1) |
| `imagingdatacommons/post_process_moose` | [`Dockerfiles/post_process_moose`](../Dockerfiles/post_process_moose/Dockerfile) | `moosePostProcess` task (Task 2) |

Both notebooks can also be run standalone (e.g. via the "Open in Colab" badge
at the top of each notebook) for local testing outside of Terra — in that
mode `input_uri`/`dicomSegBucketUri`/`dicomStoreImportUri` all default to
empty (skipped) and only IDC download + local NIfTI/DICOM-SEG output is
exercised.
