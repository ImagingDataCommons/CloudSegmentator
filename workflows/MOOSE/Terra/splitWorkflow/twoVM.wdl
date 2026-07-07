version 1.0

# ============================================================================
# MOOSE twoVM Workflow
# ----------------------------------------------------------------------------
# Task 1 (GPU): Download DICOM → Convert to NIfTI → Run moosez inference
# Task 2 (CPU): Post-process segmentations → Generate DICOM-SEG → Compress
#
# Based on twoVM pattern from Thiriveedhi et al. 2024 (CloudSegmentator).
# ============================================================================

workflow MOOSE {
  input {
    # ------------------------------------------------------------------------
    # INPUT SOURCE: IDC series list (default) OR a GCS bucket
    # ------------------------------------------------------------------------
    # Using a GCS bucket (inputUri) requires one-time setup, since s5cmd needs
    # HMAC keys rather than the VM's own pet service account / ADC:
    #   1. In the GCP project that owns the data bucket, create a dedicated
    #      service account (e.g. s5cmd-data-reader) and grant it
    #      roles/storage.objectViewer on that bucket.
    #   2. Generate an HMAC key for that service account (Cloud Storage >
    #      Settings > Interoperability, or `gcloud storage hmac create`) --
    #      save the access key ID and secret, the secret is shown only once.
    #   3. In a GCP project you control (this is what secretProject below
    #      points at -- it can be any project, the data bucket's project or
    #      otherwise), enable the Secret Manager API and store the HMAC key as
    #      two secrets: s5cmd-hmac-key-id and s5cmd-hmac-secret.
    #   4. Find your Terra proxy group on your Terra profile page (looks like
    #      PROXY_<hash>@firecloud.org) and grant it
    #      roles/secretmanager.secretAccessor on both secrets, so that
    #      workflows running under your Terra identity can fetch them at
    #      runtime.

    # YAML list of SeriesInstanceUIDs to process via IDC (passed verbatim to
    # papermill -y). Required for IDC mode; ignored when inputUri is set.
    String yamlListOfSeriesInstanceUIDs = ""

    # If empty, downloads DICOM from IDC using yamlListOfSeriesInstanceUIDs (default).
    # If set to a gs:// URI, downloads from that GCS path instead and discovers
    # series by SeriesInstanceUID DICOM tag. yamlListOfSeriesInstanceUIDs is ignored
    # when this is set. Requires the one-time setup above.
    String inputUri = ""

    # GCP project where the s5cmd-hmac-key-id / s5cmd-hmac-secret secrets live
    # (step 3 above). Only needed when inputUri is set.
    String secretProject = ""

    # ------------------------------------------------------------------------
    # ANALYSIS PARAMETERS (commonly overridden per run)
    # ------------------------------------------------------------------------

    # Comma-separated moosez model names
    # Available: clin_ct_body, clin_ct_body_composition, clin_ct_cardiac,
    #            clin_ct_digestive, clin_ct_lungs, clin_ct_muscles,
    #            clin_ct_organs, clin_ct_peripheral_bones, clin_ct_ribs,
    #            clin_ct_vertebrae
    String mooseModels = "clin_ct_body,clin_ct_body_composition,clin_ct_cardiac,clin_ct_digestive,clin_ct_lungs,clin_ct_muscles,clin_ct_organs,clin_ct_peripheral_bones,clin_ct_ribs,clin_ct_vertebrae"

    # Accelerator for moosez: 'cuda' for GPU, 'cpu' for CPU-only
    String accelerator = "cuda"

    # OPTIONAL: GCS prefix for per-series checkpoints (e.g. gs://fc-<bucket>/moose_ckpt).
    # When set, a preempted inference VM restores already-finished series from GCS and
    # only recomputes the remainder, instead of redoing the whole batch. Empty = disabled.
    # Must be writable by the VM pet service account (your Terra workspace bucket works).
    String checkpointGcsPath = ""

    # ------------------------------------------------------------------------
    # INFERENCE TASK (GPU) — download, convert, run moosez
    # ------------------------------------------------------------------------

    String mooseInferenceDocker = "sunderlandkyl/moose-test:latest"

    Int mooseInferencePreemptibleTries = 3
    Int mooseInferenceCpus = 4
    Int mooseInferenceRAM = 16
    Int mooseInferenceDiskGB = 50
    String mooseInferenceDiskType = "HDD"

    String mooseInferenceGpuType = "nvidia-tesla-t4"
    Int mooseInferenceGpuCount = 1

    # Single region only — Google Cloud Batch requires all zones in one region
    String mooseInferenceZones = "us-east4-a us-east4-b us-east4-c"

    # ------------------------------------------------------------------------
    # POST-PROCESSING TASK (CPU-only) — DICOM-SEG generation, compression
    # ------------------------------------------------------------------------

    String moosePostProcessDocker = "sunderlandkyl/post_process_moose:latest"

    Int moosePostProcessPreemptibleTries = 3
    Int moosePostProcessCpus = 4
    Int moosePostProcessRAM = 16

    # In IDC mode each series' raw DICOM is downloaded, used, and deleted one at a
    # time, so disk usage stays bounded to ~1 series regardless of cohort size. In
    # GCS mode (inputUri set) all series under inputUri are downloaded and sorted
    # before any per-series cleanup runs (their SeriesInstanceUID isn't known until
    # read from the file), and anything outside this run's cohort is pruned right
    # after -- but a single large inputUri cohort may still need more disk than the
    # default below.
    Int moosePostProcessDiskGB = 20
    String moosePostProcessDiskType = "HDD"

    # AMD Rome (N2D) is cheapest CPU family on Terra per Thiriveedhi et al.
    String moosePostProcessCpuFamily = "AMD Rome"

    String moosePostProcessZones = "us-east4-a us-east4-b us-east4-c"

    # ------------------------------------------------------------------------
    # OPTIONAL: copy generated DICOM-SEG (.dcm) to a GCS bucket
    # ------------------------------------------------------------------------
    # GCS prefix, e.g. gs://idc-not-a-challenge/kyle/ . When set, the per-series
    # uncompressed .dcm SEG files are uploaded there (preserving the
    # <SeriesInstanceUID>/ layout). Empty = skip upload. Authenticated by the VM
    # pet service account (ADC) -- grant it roles/storage.objectAdmin on the
    # bucket. This is NOT a secret.
    String dicomSegBucketUri = ""

    # ------------------------------------------------------------------------
    # OPTIONAL: import generated DICOM-SEG from the GCS bucket above into a
    # Healthcare API DICOM store
    # ------------------------------------------------------------------------
    # Full dicomStore resource name, e.g.
    #   projects/PROJECT/locations/LOCATION/datasets/DATASET/dicomStores/STORE
    # The dicomStore may live in a different GCP project than this workflow --
    # that's fine, the resource name fully qualifies the target. Requires
    # dicomSegBucketUri to be set too, since the import reads from that GCS
    # location. Empty = skip import. Authenticated by the VM pet service
    # account (ADC) -- grant it roles/healthcare.dicomEditor on the dataset in
    # whichever project hosts it, AND grant the Cloud Healthcare API service
    # agent in that project roles/storage.objectViewer on the source bucket
    # (the import job reads from GCS server-side). This is NOT a secret.
    String dicomStoreImportUri = ""
  }

  # ==========================================================================
  # Task 1: GPU inference
  # ==========================================================================
  call mooseInference {
    input:
      yamlListOfSeriesInstanceUIDs = yamlListOfSeriesInstanceUIDs,
      inputUri                     = inputUri,
      secretProject                = secretProject,
      mooseModels                  = mooseModels,
      accelerator                  = accelerator,
      checkpointGcsPath            = checkpointGcsPath,
      docker                       = mooseInferenceDocker,
      preemptibleTries             = mooseInferencePreemptibleTries,
      cpus                         = mooseInferenceCpus,
      ram                          = mooseInferenceRAM,
      diskGB                       = mooseInferenceDiskGB,
      diskType                     = mooseInferenceDiskType,
      gpuType                      = mooseInferenceGpuType,
      gpuCount                     = mooseInferenceGpuCount,
      zones                        = mooseInferenceZones
  }

  # ==========================================================================
  # Task 2: CPU post-processing
  # ==========================================================================
  call moosePostProcess {
    input:
      inferenceOutputArchive    = mooseInference.segmentationArchive,
      inferenceUsageMetricsCsv  = mooseInference.usageMetricsCsv,
      inferenceStatsArchive     = mooseInference.mooseStatsArchive,
      docker                    = moosePostProcessDocker,
      preemptibleTries          = moosePostProcessPreemptibleTries,
      cpus                      = moosePostProcessCpus,
      ram                       = moosePostProcessRAM,
      diskGB                    = moosePostProcessDiskGB,
      diskType                  = moosePostProcessDiskType,
      cpuFamily                 = moosePostProcessCpuFamily,
      zones                     = moosePostProcessZones,
      dicomSegBucketUri         = dicomSegBucketUri,
      dicomStoreImportUri       = dicomStoreImportUri,
      inputUri                  = inputUri,
      secretProject             = secretProject
  }

  # ==========================================================================
  # Outputs
  # ==========================================================================
  output {
    # Notebooks with logs for debugging
    File mooseInferenceNotebook   = mooseInference.outputNotebook
    File moosePostProcessNotebook = moosePostProcess.outputNotebook

    # Usage metrics (CPU/GPU/RAM over time)
    File mooseInferenceUsageMetricsCsv   = mooseInference.usageMetricsCsv
    File moosePostProcessUsageMetricsCsv = moosePostProcess.usageMetricsCsv
    File combinedUsageMetricsCsv         = moosePostProcess.combinedUsageMetricsCsv
    File? mooseRunSummary                = moosePostProcess.runSummary
    File? usageMetricsUploadErrors       = moosePostProcess.usageMetricsUploadErrors

    # Primary outputs
    File mooseSegmentations    = mooseInference.segmentationArchive
    File mooseStatsCSVs        = mooseInference.mooseStatsArchive
    File mooseDicomSegFiles    = moosePostProcess.dicomSegArchive

    # Optional error files (only produced if errors occurred)
    File? downloadErrors       = mooseInference.downloadErrors
    File? dcm2niixErrors       = mooseInference.dcm2niixErrors
    File? mooseInferenceErrors = mooseInference.inferenceErrors
    File? dicomSegErrors       = moosePostProcess.dicomSegErrors
    File? statsUploadErrors    = moosePostProcess.statsUploadErrors
  }
}


# ============================================================================
# TASK: Inference (GPU)
# Downloads DICOM, converts to NIfTI, runs moosez segmentation.
# Output: tarball of NIfTI segmentation masks + source NIfTI volumes.
# ============================================================================
task mooseInference {
  input {
    String yamlListOfSeriesInstanceUIDs
    String inputUri
    String secretProject
    String mooseModels
    String accelerator
    String checkpointGcsPath
    String docker
    Int    preemptibleTries
    Int    cpus
    Int    ram
    Int    diskGB
    String diskType
    String gpuType
    Int    gpuCount
    String zones
  }

  command <<<
    set -e

    # Pin to a specific commit for reproducibility (update SHA as needed)
    wget https://raw.githubusercontent.com/Sunderlandkyl/CloudSegmentator/moose_test/workflows/MOOSE/Notebooks/mooseInferenceNotebook.ipynb

    papermill mooseInferenceNotebook.ipynb mooseInferenceOutputNotebook.ipynb \
      -y "~{yamlListOfSeriesInstanceUIDs}" \
      -p moose_models "~{mooseModels}" \
      -p accelerator "~{accelerator}" \
      -p checkpoint_gcs "~{checkpointGcsPath}" \
      -p input_uri "~{inputUri}" \
      -p secret_project "~{secretProject}" \
      || (>&2 echo "Inference task failed" && exit 1)

    if [ ! -f moose_segmentations.tar.lz4 ]; then
      >&2 echo "Expected output archive moose_segmentations.tar.lz4 was not created"
      if [ ! -f moose_errors.txt ]; then
        echo "Inference completed without producing moose_segmentations.tar.lz4" > moose_errors.txt
      fi
      exit 1
    fi

    lz4 -d -c moose_segmentations.tar.lz4 | tar -tf - > moose_segmentations_tar_list.txt

    # Fail fast when archive contains only folders and no segmentation volumes.
    if ! grep -E '\.nii(\.gz)?$' moose_segmentations_tar_list.txt >/dev/null; then
      >&2 echo "No NIfTI segmentation files found in moose_segmentations.tar.lz4"
      if [ ! -f moose_errors.txt ]; then
        echo "No NIfTI segmentation files were generated by inference." > moose_errors.txt
      fi
      exit 1
    fi

    # Bundle the native moosez stats CSVs (volume + HU intensity per label) into
    # a separate archive so they can be surfaced as a distinct workflow output.
    grep -E '\.csv$' moose_segmentations_tar_list.txt > moose_stats_csv_list.txt || true
    if [ -s moose_stats_csv_list.txt ]; then
      mkdir -p /tmp/moose_stats_extract
      lz4 -d -c moose_segmentations.tar.lz4 | tar -xf - -C /tmp/moose_stats_extract -T moose_stats_csv_list.txt
      tar -cf - -C /tmp/moose_stats_extract . | lz4 > moose_stats.tar.lz4
    else
      >&2 echo "WARNING: No stats CSVs found in segmentation archive — moosez may not have written them"
      mkdir -p /tmp/empty_stats
      tar -cf - -C /tmp/empty_stats . | lz4 > moose_stats.tar.lz4
    fi
  >>>

  runtime {
    docker:      docker
    cpu:         cpus
    memory:      ram + " GiB"
    disks:       "local-disk " + diskGB + " " + diskType
    gpuType:     gpuType
    gpuCount:    gpuCount
    zones:       zones
    preemptible: preemptibleTries
    maxRetries:  1
  }

  output {
    File outputNotebook       = "mooseInferenceOutputNotebook.ipynb"
    File segmentationArchive  = "moose_segmentations.tar.lz4"
    File usageMetricsCsv      = "moose_inference_UsageMetrics.csv"
    File mooseStatsArchive    = "moose_stats.tar.lz4"

    File? downloadErrors      = "download_error_file.txt"
    File? dcm2niixErrors      = "dcm2niix_error_file.txt"
    File? inferenceErrors     = "moose_errors.txt"
    File? inferenceArchiveListing = "moose_segmentations_tar_list.txt"
  }
}


# ============================================================================
# TASK: Post-processing (CPU)
# Takes NIfTI segmentations from inference task, converts to DICOM-SEG format,
# compresses outputs. Runs on cheaper CPU-only VM (AMD Rome / N2D).
# ============================================================================
task moosePostProcess {
  input {
    File   inferenceOutputArchive
    File   inferenceUsageMetricsCsv
    File   inferenceStatsArchive
    String docker
    Int    preemptibleTries
    Int    cpus
    Int    ram
    Int    diskGB
    String diskType
    String cpuFamily
    String zones
    String dicomSegBucketUri
    String dicomStoreImportUri
    String inputUri
    String secretProject
  }

  command <<<
    set -o xtrace
    set -o pipefail
    set +o errexit

    # ------------------------------------------------------------------------
    # Derive a per-run identifier for the usage-metrics subfolder, so each run's
    # moose_UsageMetrics.csv lands in gs://.../_metrics/<RUN_ID>/ instead of
    # overwriting a single shared file. On Terra (Cromwell PAPIv2 / GCP Batch
    # backends) the auto-generated GCS transfer scripts placed in this task's
    # execution directory embed the full delocalization path, which contains the
    # Terra submission id and the Cromwell workflow id:
    #   gs://<bucket>/submissions/<submissionId>/<wfName>/<workflowId>/call-.../
    # Parse RUN_ID=<submissionId>_<workflowId> from there. Fall back to just the
    # bare workflow-id UUID (non-Terra Cromwell layouts), then to a
    # timestamp+uuid (local backend / standalone) so the id is always unique.
    # ------------------------------------------------------------------------
    RUN_ID=$(grep -hoE 'submissions/[0-9a-fA-F-]+/[^/]+/[0-9a-fA-F-]+/call-' ./*.sh 2>/dev/null \
      | head -n1 | awk -F/ '{print $2"_"$4}')
    if [ -z "$RUN_ID" ]; then
      RUN_ID=$(grep -hoE '/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}/call-' ./*.sh 2>/dev/null \
        | head -n1 | sed -E 's#^/([0-9a-fA-F-]+)/call-$#\1#')
    fi
    if [ -z "$RUN_ID" ]; then
      RUN_ID="run_$(date -u +%Y%m%dT%H%M%SZ)_$( (cat /proc/sys/kernel/random/uuid 2>/dev/null || echo "$RANDOM$RANDOM") | tr -d '\n' | cut -c1-8)"
    fi
    echo "Derived RUN_ID=$RUN_ID"

    wget https://raw.githubusercontent.com/Sunderlandkyl/CloudSegmentator/moose_test/workflows/MOOSE/Notebooks/moosePostProcessNotebook.ipynb
    # Curated label->SNOMED mapping (category/type/laterality modifier/region/rgb);
    # the post-process notebook resolves each moosez label name against it.
    wget https://raw.githubusercontent.com/Sunderlandkyl/CloudSegmentator/moose_test/workflows/MOOSE/resources/moose_snomed_mapping.csv

    # Normalize inference archive layout for compatibility:
    # - Current expected: <uid>/moosez-<model>-<timestamp>/segmentations/*.nii.gz
    # - Legacy/flat:      <uid>/*.nii.gz (or nested without model directories)
    python3 - <<'PY'
import re
import shutil
import subprocess
from pathlib import Path

src_archive = Path("~{inferenceOutputArchive}")
extract_root = Path("/tmp/moose_preprocess_extract")
normalized_archive = Path("moose_segmentations.normalized.tar.lz4")

_MODEL_DIR_RE = re.compile(r"^moosez-(?P<model>.+?)-\d{4}[-_]?\d{2}[-_]?\d{2}[-_T]?\d{2}[-_:]?\d{2}[-_:]?\d{2}$")

if extract_root.exists():
    shutil.rmtree(extract_root)
extract_root.mkdir(parents=True, exist_ok=True)

subprocess.run(
    ["bash", "-lc", "lz4 -d -c \"$1\" | tar -xf - -C \"$2\"", "_", str(src_archive), str(extract_root)],
    check=True,
)

top_dirs = [p for p in extract_root.iterdir() if p.is_dir()]
if len(top_dirs) == 1:
    moose_root = top_dirs[0]
else:
    moose_root = extract_root

for series_dir in [p for p in moose_root.iterdir() if p.is_dir()]:
    model_dirs = [p for p in series_dir.iterdir() if p.is_dir() and _MODEL_DIR_RE.match(p.name)]
    if model_dirs:
        continue

    seg_files = sorted(series_dir.rglob("*.nii.gz"))
    if not seg_files:
        continue

    synthetic_seg_dir = series_dir / "moosez-legacy-19700101_000000" / "segmentations"
    synthetic_seg_dir.mkdir(parents=True, exist_ok=True)

    for seg_file in seg_files:
        target = synthetic_seg_dir / seg_file.name
        if seg_file.resolve() == target.resolve():
            continue
        if target.exists():
            stem = seg_file.stem
            suffix = ''.join(seg_file.suffixes)
            target = synthetic_seg_dir / (stem + "_" + str(abs(hash(str(seg_file))) % 100000) + suffix)
        shutil.move(str(seg_file), str(target))

subprocess.run(
    [
        "bash",
        "-lc",
        "tar -cf - -C \"$1\" \"$2\" | lz4 > \"$3\"",
        "_",
        str(moose_root.parent),
        str(moose_root.name),
        str(normalized_archive),
    ],
    check=True,
)

print("Normalized archive ready: " + str(normalized_archive))
PY

    lz4 -d -c moose_segmentations.normalized.tar.lz4 | tar -tf - > moose_postprocess_input_tar_list.txt
    if ! grep -E '\.nii(\.gz)?$' moose_postprocess_input_tar_list.txt >/dev/null; then
      >&2 echo "No NIfTI files found in normalized inference archive"
      if [ ! -f dicom_seg_error_file.txt ]; then
        echo "No NIfTI segmentations found in normalized archive for post-processing." > dicom_seg_error_file.txt
      fi
      exit 1
    fi

    # The post-process notebook requires a per-series layout:
    # <root>/<SeriesInstanceUID>/.../*.nii.gz
    if ! grep -E '^[^/]+/[^/]+/.+\.nii(\.gz)?$' moose_postprocess_input_tar_list.txt >/dev/null; then
      >&2 echo "Normalized archive has NIfTI files but lacks per-series UID subdirectories"
      if [ ! -f dicom_seg_error_file.txt ]; then
        {
          echo "Post-processing requires archive layout <root>/<SeriesInstanceUID>/.../*.nii.gz"
          echo "No per-series UID subdirectories were detected in moose_segmentations.normalized.tar.lz4"
          echo
          echo "Sample archive listing:"
          head -n 200 moose_postprocess_input_tar_list.txt
        } > dicom_seg_error_file.txt
      fi
      exit 1
    fi

    if ! papermill moosePostProcessNotebook.ipynb moosePostProcessOutputNotebook.ipynb \
      -p segmentationArchivePath "moose_segmentations.normalized.tar.lz4" \
      -p dicomSegBucketUri "~{dicomSegBucketUri}" \
      -p dicomStoreImportUri "~{dicomStoreImportUri}" \
      -p inferenceUsageMetricsCsvPath "~{inferenceUsageMetricsCsv}" \
      -p statsArchivePath "~{inferenceStatsArchive}" \
      -p input_uri "~{inputUri}" \
      -p secret_project "~{secretProject}" \
      -p runId "$RUN_ID"; then
      >&2 echo "Post-process notebook failed"
      if [ -f dicom_seg_error_file.txt ]; then
        >&2 echo "----- dicom_seg_error_file.txt -----"
        cat dicom_seg_error_file.txt >&2 || true
      fi
      exit 1
    fi

    if [ ! -f moose_dicom_seg.tar.lz4 ]; then
      >&2 echo "Expected output archive moose_dicom_seg.tar.lz4 was not created"
      exit 1
    fi

    # Guard against a successful notebook run that produced only empty directories.
    if ! lz4 -d -c moose_dicom_seg.tar.lz4 | tar -tf - | grep -E '\.dcm$' >/dev/null; then
      >&2 echo "No DICOM-SEG files found in moose_dicom_seg.tar.lz4"
      >&2 echo "----- post-process input archive listing tail -----"
      tail -n 200 moose_postprocess_input_tar_list.txt >&2 || true
      if [ ! -f dicom_seg_error_file.txt ]; then
        echo "No DICOM-SEG files were generated by post-processing." > dicom_seg_error_file.txt
      fi
      >&2 echo "----- dicom_seg_error_file.txt tail -----"
      tail -n 200 dicom_seg_error_file.txt >&2 || true
      exit 1
    fi

    set -o errexit
  >>>

  runtime {
    docker:      docker
    cpu:         cpus
    cpuPlatform: cpuFamily
    memory:      ram + " GiB"
    disks:       "local-disk " + diskGB + " " + diskType
    zones:       zones
    preemptible: preemptibleTries
    maxRetries:  2
  }

  output {
    File outputNotebook     = "moosePostProcessOutputNotebook.ipynb"
    File dicomSegArchive    = "moose_dicom_seg.tar.lz4"
    File usageMetricsCsv    = "moose_postprocess_UsageMetrics.csv"
    File combinedUsageMetricsCsv = "moose_UsageMetrics.csv"
    File? runSummary        = "moose_run_summary.json"

    File? dicomSegErrors    = "dicom_seg_error_file.txt"
    File? usageMetricsUploadErrors = "metrics_bucket_error_file.txt"
    File? statsUploadErrors = "stats_bucket_error_file.txt"
    File? postProcessInputArchiveListing = "moose_postprocess_input_tar_list.txt"
  }
}
