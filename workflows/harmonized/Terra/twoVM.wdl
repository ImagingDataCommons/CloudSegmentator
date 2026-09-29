version 1.0

# ============================================================================
# Harmonized Segmentator twoVM Workflow
# ----------------------------------------------------------------------------
# A single, model-agnostic workflow. Only the *inference* notebook + docker
# image are model-specific; input conversion and output conversion are shared.
#
#   Task 1 (GPU): nb1 convert (DICOM -> NIfTI)  +  nb2 inference (model-specific)
#   Task 2 (CPU): nb3 output conversion (NIfTI seg -> DICOM-SEG + radiomics + SR)
#
# Select a model purely by inputs (no WDL edits):
#   inferenceDocker        - per-model image, FROM imagingdatacommons/cloudsegmentator-base
#   inferenceNotebookPath  - repo path to the model's nb2 inference notebook
#   snomedMappingPath      - repo path to the model's unified SNOMED mapping CSV
#   inferenceParamsYaml    - generic papermill params passthrough for model knobs
#
# See workflows/models/<model>/inputs.<model>.json for ready-made presets.
#
# Contracts between steps (both tar.lz4 archives passed as WDL File):
#   Boundary A (nb1 -> nb2): converted_nifti.tar.lz4
#       <SeriesInstanceUID>/<SeriesInstanceUID>.nii.gz  (+ convert_manifest.json)
#   Boundary B (nb2 -> nb3): segmentations.tar.lz4
#       <SeriesInstanceUID>/<model>/segmentations/*.nii.gz  (+ label_map.json per model dir)
#
# Based on the twoVM pattern from Thiriveedhi et al. 2024 (CloudSegmentator),
# generalized from workflows/MOOSE/Terra/splitWorkflow/twoVM.wdl.
# ============================================================================

workflow Segmentator {
  input {
    # ------------------------------------------------------------------------
    # INPUT SOURCE: IDC series list (default) OR a private GCS bucket
    # (GCS mode requires the one-time s5cmd HMAC / Secret Manager setup described
    #  in workflows/harmonized/Docs/README.md)
    # ------------------------------------------------------------------------
    String yamlListOfSeriesInstanceUIDs = ""
    String inputUri = ""
    String secretProject = ""

    # ------------------------------------------------------------------------
    # MODEL SELECTION (the only per-model surface — see inputs.<model>.json)
    # ------------------------------------------------------------------------
    # Short model identifier, embedded in the Boundary-B layout (<uid>/<model>/...)
    String modelName = ""

    # Per-model GPU inference image (derived FROM cloudsegmentator-base).
    String inferenceDocker

    # Repo path to the model's nb2 inference notebook (fetched from gitRepo/gitBranch).
    String inferenceNotebookPath

    # Repo path to the model's unified SNOMED mapping CSV
    # (schema: model,label_name,label_id, + SegmentedProperty*/AnatomicRegion*/RGB).
    # Leave empty when the model bundles its own SNOMED table into the
    # segmentation archive (e.g. MOOSE ships moosez's moose_snomed_mapping.csv);
    # nb3 then prefers the bundled copy.
    String snomedMappingPath = ""

    # Generic papermill parameters passthrough for model-specific knobs, e.g.
    #   "moose_models: clin_ct_organs,clin_ct_ribs\naccelerator: cuda"
    # Written to a params.yaml and passed to nb2 via `papermill -f`. Empty = none.
    String inferenceParamsYaml = ""

    # ------------------------------------------------------------------------
    # SOURCE OF NOTEBOOKS + RESOURCES (override for dev branches / forks)
    # ------------------------------------------------------------------------
    String gitRepo   = "ImagingDataCommons/CloudSegmentator"
    String gitBranch = "main"

    # Fixed shared notebooks (rarely overridden).
    String convertNotebookPath          = "workflows/common/Notebooks/convertNotebook.ipynb"
    String outputConversionNotebookPath = "workflows/common/Notebooks/outputConversionNotebook.ipynb"

    # ------------------------------------------------------------------------
    # HARMONIZED OUTPUT TOGGLES (nb3)
    # ------------------------------------------------------------------------
    Boolean runRadiomics = true
    Boolean runStructuredReport = true

    # Radiomics engine to use when runRadiomics is true. One method per run;
    # run the workflow twice to compare engines. Valid values:
    #   "pyradiomics" (default) - AIM-Harvard pyradiomics (Python)
    #   "radiomicsjl"           - JuliaHealth Radiomics.jl (Julia)
    String radiomicsMethod = "pyradiomics"

    # Radiomics feature classes to compute, comma-separated, applied to whichever
    # engine radiomicsMethod selects (engine-neutral pyradiomics-style names):
    #   firstorder, shape, glcm, glrlm, glszm, ngtdm, gldm   or   "all"
    # Texture classes (glcm/glrlm/glszm/ngtdm/gldm) are considerably more
    # expensive than firstorder+shape; unknown names are warned about and ignored.
    String radiomicsFeatureClasses = "firstorder,shape"

    # Julia threads for the Radiomics.jl worker (radiomicsMethod=radiomicsjl only).
    # 0 = auto (all vCPUs). Radiomics.jl parallelises across the labels of a seg
    # file. Requires Radiomics.jl >= 2.0.0 (output_conversion image): earlier
    # releases had a multi-label data race with >1 thread, which is why this was
    # pinned to 1 before Sep 2026.
    Int outputConversionJuliaThreads = 0

    # Skip radiomics for any label whose ROI exceeds this many Mvoxels (SEG is still
    # written). Radiomics cost scales with ROI size; whole-body masks (MOOSE clin_ct_body,
    # 10-60 Mvox) took ~20 min/series in the Aug-2026 pilot vs < 1 min for any organ.
    # Organs/lungs/liver are < ~3 Mvox, so 5 separates anatomy from "everything". <= 0 disables.
    Float radiomicsMaxRoiMvox = 5.0

    # ------------------------------------------------------------------------
    # OPTIONAL: checkpoint/resume on preemption (inference task)
    # GCS prefix (e.g. the workspace bucket: gs://fc-<id>/segmentator_ckpt). nb1 bundles
    # the converted NIfTIs there once, nb2 saves each finished (series, model) output;
    # a preempted VM's retry restores both and skips the done work; the run's prefix
    # is deleted on success. Namespaced by the Cromwell workflow id. Empty = disabled.
    # (Aug-2026 pilot: ~40 % of GPU VM-minutes were lost to preemption retries on a bad day.)
    String checkpointGcsPath = ""

    # ------------------------------------------------------------------------
    # OPTIONAL: deliver generated DICOM-SEG to GCS and/or a Healthcare DICOM store
    # ------------------------------------------------------------------------
    String dicomSegBucketUri   = ""
    String dicomStoreImportUri = ""

    # ------------------------------------------------------------------------
    # INFERENCE TASK (GPU) compute shape
    # ------------------------------------------------------------------------
    Int    inferencePreemptibleTries = 3
    Int    inferenceCpus   = 4
    Int    inferenceRAM    = 16
    Int    inferenceDiskGB = 50
    String inferenceDiskType = "HDD"
    String inferenceGpuType  = "nvidia-tesla-t4"
    Int    inferenceGpuCount = 1
    # Single region only — Google Cloud Batch requires all zones in one region.
    String inferenceZones = "us-east4-a us-east4-b us-east4-c"

    # ------------------------------------------------------------------------
    # OUTPUT-CONVERSION TASK (CPU-only) compute shape
    # ------------------------------------------------------------------------
    String outputConversionDocker = "imagingdatacommons/cloudsegmentator-output-conversion:main"
    Int    outputConversionPreemptibleTries = 3
    Int    outputConversionCpus   = 4
    Int    outputConversionRAM    = 16
    Int    outputConversionDiskGB = 20
    String outputConversionDiskType = "HDD"
    # AMD Rome (N2D) is cheapest CPU family on Terra per Thiriveedhi et al.
    String outputConversionCpuFamily = "AMD Rome"
    String outputConversionZones = "us-east4-a us-east4-b us-east4-c"
  }

  # ==========================================================================
  # Task 1: GPU — convert (nb1) then inference (nb2)
  # ==========================================================================
  call inference {
    input:
      yamlListOfSeriesInstanceUIDs = yamlListOfSeriesInstanceUIDs,
      inputUri                     = inputUri,
      secretProject                = secretProject,
      modelName                    = modelName,
      gitRepo                      = gitRepo,
      gitBranch                    = gitBranch,
      convertNotebookPath          = convertNotebookPath,
      inferenceNotebookPath        = inferenceNotebookPath,
      inferenceParamsYaml          = inferenceParamsYaml,
      checkpointGcsPath            = checkpointGcsPath,
      docker                       = inferenceDocker,
      preemptibleTries             = inferencePreemptibleTries,
      cpus                         = inferenceCpus,
      ram                          = inferenceRAM,
      diskGB                       = inferenceDiskGB,
      diskType                     = inferenceDiskType,
      gpuType                      = inferenceGpuType,
      gpuCount                     = inferenceGpuCount,
      zones                        = inferenceZones
  }

  # ==========================================================================
  # Task 2: CPU — output conversion (nb3): SEG + radiomics + SR
  # ==========================================================================
  call outputConversion {
    input:
      segmentationArchive       = inference.segmentationArchive,
      inferenceUsageMetricsCsv  = inference.usageMetricsCsv,
      convertUsageMetricsCsv    = inference.convertUsageMetricsCsv,
      modelName                 = modelName,
      gitRepo                   = gitRepo,
      gitBranch                 = gitBranch,
      outputConversionNotebookPath = outputConversionNotebookPath,
      snomedMappingPath         = snomedMappingPath,
      runRadiomics              = runRadiomics,
      runStructuredReport       = runStructuredReport,
      radiomicsMethod           = radiomicsMethod,
      radiomicsFeatureClasses   = radiomicsFeatureClasses,
      juliaThreads              = outputConversionJuliaThreads,
      maxRoiMvox                = radiomicsMaxRoiMvox,
      docker                    = outputConversionDocker,
      preemptibleTries          = outputConversionPreemptibleTries,
      cpus                      = outputConversionCpus,
      ram                       = outputConversionRAM,
      diskGB                    = outputConversionDiskGB,
      diskType                  = outputConversionDiskType,
      cpuFamily                 = outputConversionCpuFamily,
      zones                     = outputConversionZones,
      dicomSegBucketUri         = dicomSegBucketUri,
      dicomStoreImportUri       = dicomStoreImportUri,
      inputUri                  = inputUri,
      secretProject             = secretProject,
      checkpointGcsPath         = checkpointGcsPath
  }

  output {
    # Executed notebooks (logs) for debugging
    File convertNotebook          = inference.convertOutputNotebook
    File inferenceNotebook        = inference.inferenceOutputNotebook
    File outputConversionNotebook = outputConversion.outputNotebook

    # Usage metrics
    File inferenceUsageMetricsCsv        = inference.usageMetricsCsv
    File? convertUsageMetricsCsv         = inference.convertUsageMetricsCsv
    File outputConversionUsageMetricsCsv = outputConversion.usageMetricsCsv
    File combinedUsageMetricsCsv         = outputConversion.combinedUsageMetricsCsv
    File? runSummary                     = outputConversion.runSummary

    # Primary artifacts (uniform across all models)
    File segmentations = inference.segmentationArchive
    File dicomSegFiles = outputConversion.dicomSegArchive
    File? radiomicsFeatures      = outputConversion.radiomicsArchive
    File? structuredReportsDicom = outputConversion.srDicomArchive
    File? structuredReportsJson  = outputConversion.srJsonArchive

    # Optional error files (only produced on failure)
    File? downloadErrors        = inference.downloadErrors
    File? dcm2niixErrors        = inference.dcm2niixErrors
    File? inferenceErrors       = inference.inferenceErrors
    File? dicomSegErrors        = outputConversion.dicomSegErrors
    File? radiomicsErrors       = outputConversion.radiomicsErrors
    File? srErrors              = outputConversion.srErrors
  }
}


# ============================================================================
# TASK: Inference (GPU) — nb1 convert + nb2 inference on one VM
# Output: Boundary-B segmentation archive for the output-conversion task.
# ============================================================================
task inference {
  input {
    String yamlListOfSeriesInstanceUIDs
    String inputUri
    String secretProject
    String modelName
    String gitRepo
    String gitBranch
    String convertNotebookPath
    String inferenceNotebookPath
    String inferenceParamsYaml
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
    RAW="https://raw.githubusercontent.com/~{gitRepo}/~{gitBranch}"

    # ---- Fetch shared convert notebook (nb1), model inference notebook (nb2) and the
    #      checkpoint helper module both notebooks import (no-op unless checkpointGcsPath).
    wget -O convertNotebook.ipynb   "${RAW}/~{convertNotebookPath}"
    wget -O inferenceNotebook.ipynb "${RAW}/~{inferenceNotebookPath}"
    wget -O segmentator_checkpoint.py "${RAW}/workflows/common/Notebooks/segmentator_checkpoint.py"

    # ---- Checkpoint namespace = this workflow's Cromwell id, derived from the
    #      auto-generated transfer scripts (same trick as the outputConversion task).
    #      Stable across preemption retries of this call, unique per workflow, so a
    #      retried VM resumes its own state and never another submission's.
    RUN_ID=$(grep -hoE 'submissions/[0-9a-fA-F-]+/[^/]+/[0-9a-fA-F-]+/call-' ./*.sh 2>/dev/null \
      | head -n1 | awk -F/ '{print $2"_"$4}')
    if [ -z "$RUN_ID" ]; then
      # Fallback: hash of the inputs (still stable across retries of the same inputs).
      RUN_ID="inputs_$(printf '%s|%s|%s' "~{yamlListOfSeriesInstanceUIDs}" "~{modelName}" "~{inferenceParamsYaml}" | md5sum | cut -c1-16)"
    fi
    echo "Derived RUN_ID=$RUN_ID (checkpointGcsPath='~{checkpointGcsPath}')"

    # Model-specific papermill params (optional). Guarantee a valid non-empty
    # YAML doc so `papermill -f` never chokes on an empty file.
    cat > inference_params.yaml <<'YAML'
~{inferenceParamsYaml}
YAML
    [ -s inference_params.yaml ] || echo "{}" > inference_params.yaml

    # ---- Step 1: convert (nb1) -> converted_nifti.tar.lz4 (Boundary A)
    # --log-output streams each cell's print()s into this task's stdout/stderr
    # log so per-series failures are visible without digging through the
    # execution bucket for the output notebook.
    papermill --log-output convertNotebook.ipynb convertOutputNotebook.ipynb \
      -y "~{yamlListOfSeriesInstanceUIDs}" \
      -p input_uri "~{inputUri}" \
      -p secret_project "~{secretProject}" \
      -p checkpoint_gcs "~{checkpointGcsPath}" \
      -p run_id "$RUN_ID" \
      || {
        >&2 echo "Convert task failed"
        [ -f download_error_file.txt ] && { >&2 echo "----- download_error_file.txt -----"; cat download_error_file.txt >&2; }
        [ -f dcm2niix_error_file.txt ] && { >&2 echo "----- dcm2niix_error_file.txt -----"; cat dcm2niix_error_file.txt >&2; }
        exit 1
      }

    if [ ! -f converted_nifti.tar.lz4 ]; then
      >&2 echo "Expected Boundary-A archive converted_nifti.tar.lz4 was not created"
      exit 1
    fi

    # ---- Step 2: inference (nb2) -> segmentations.tar.lz4 (Boundary B)
    papermill --log-output inferenceNotebook.ipynb inferenceOutputNotebook.ipynb \
      -f inference_params.yaml \
      -p converted_nifti_path "converted_nifti.tar.lz4" \
      -p model_name "~{modelName}" \
      -p accelerator "cuda" \
      -p checkpoint_gcs "~{checkpointGcsPath}" \
      -p run_id "$RUN_ID" \
      || {
        >&2 echo "Inference task failed"
        [ -f inference_errors.txt ] && { >&2 echo "----- inference_errors.txt -----"; cat inference_errors.txt >&2; }
        exit 1
      }

    if [ ! -f segmentations.tar.lz4 ]; then
      >&2 echo "Expected Boundary-B archive segmentations.tar.lz4 was not created"
      if [ -f inference_errors.txt ]; then
        >&2 echo "----- inference_errors.txt -----"; cat inference_errors.txt >&2
      else
        echo "Inference completed without producing segmentations.tar.lz4" > inference_errors.txt
      fi
      exit 1
    fi

    # Fail fast when archive has no NIfTI segmentation volumes. Only files under a
    # <model>/segmentations/ dir count: <uid>/reference.nii.gz is the input CT.
    lz4 -d -c segmentations.tar.lz4 | tar -tf - > segmentations_tar_list.txt
    if ! grep -E '/segmentations/[^/]+\.nii(\.gz)?$' segmentations_tar_list.txt >/dev/null; then
      >&2 echo "No NIfTI segmentation files found in segmentations.tar.lz4"
      if [ ! -f inference_errors.txt ]; then
        echo "No NIfTI segmentation files were generated by inference." > inference_errors.txt
      fi
      exit 1
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
    File convertOutputNotebook   = "convertOutputNotebook.ipynb"
    File inferenceOutputNotebook = "inferenceOutputNotebook.ipynb"
    File segmentationArchive     = "segmentations.tar.lz4"
    File usageMetricsCsv         = "inference_UsageMetrics.csv"
    # nb1 per-series download / dcm2niix timings (same VM as nb2); folded into the
    # combined usage metrics by nb3 and used by util/executionAnalytics for profiling.
    File? convertUsageMetricsCsv = "convert_UsageMetrics.csv"

    File? downloadErrors  = "download_error_file.txt"
    File? dcm2niixErrors  = "dcm2niix_error_file.txt"
    File? inferenceErrors = "inference_errors.txt"
    File? segmentationArchiveListing = "segmentations_tar_list.txt"
  }
}


# ============================================================================
# TASK: Output conversion (CPU) — nb3
# Boundary-B segmentation archive -> DICOM-SEG (+ pyradiomics + DICOM SR).
# Runs on the cheaper CPU-only cloudsegmentator-base image (AMD Rome / N2D).
# ============================================================================
task outputConversion {
  input {
    File    segmentationArchive
    File    inferenceUsageMetricsCsv
    File?   convertUsageMetricsCsv
    String  modelName
    String  gitRepo
    String  gitBranch
    String  outputConversionNotebookPath
    String  snomedMappingPath
    Boolean runRadiomics
    Boolean runStructuredReport
    String  radiomicsMethod
    String  radiomicsFeatureClasses
    Int     juliaThreads
    Float   maxRoiMvox
    String  docker
    Int     preemptibleTries
    Int     cpus
    Int     ram
    Int     diskGB
    String  diskType
    String  cpuFamily
    String  zones
    String  dicomSegBucketUri
    String  dicomStoreImportUri
    String  inputUri
    String  secretProject
    String  checkpointGcsPath
  }

  command <<<
    set -o xtrace
    set -o pipefail
    set +o errexit

    RAW="https://raw.githubusercontent.com/~{gitRepo}/~{gitBranch}"

    # ---- Derive a per-run id so each run's metrics land in _metrics/<RUN_ID>/
    #      instead of overwriting a shared file (Terra/Cromwell delocalization
    #      paths are embedded in the auto-generated transfer scripts).
    RUN_ID=$(grep -hoE 'submissions/[0-9a-fA-F-]+/[^/]+/[0-9a-fA-F-]+/call-' ./*.sh 2>/dev/null \
      | head -n1 | awk -F/ '{print $2"_"$4}')
    if [ -z "$RUN_ID" ]; then
      RUN_ID="run_$(date -u +%Y%m%dT%H%M%SZ)_$( (cat /proc/sys/kernel/random/uuid 2>/dev/null || echo "$RANDOM$RANDOM") | tr -d '\n' | cut -c1-8)"
    fi
    echo "Derived RUN_ID=$RUN_ID"

    # fetch <dest> <repo path> [optional]: wget -O leaves a 0-byte file on a 404,
    # which the notebook would take for a real (empty) file, so a failed download
    # is removed. A required file fails the task; an optional one is left missing
    # for nb3 to report.
    fetch() {
      if wget -O "$1" "${RAW}/$2"; then return 0; fi
      rm -f "$1"
      if [ "${3:-}" = optional ]; then
        >&2 echo "WARNING: could not fetch ${RAW}/$2 (optional)"
        return 0
      fi
      >&2 echo "ERROR: could not fetch ${RAW}/$2"
      exit 1
    }

    fetch outputConversionNotebook.ipynb "~{outputConversionNotebookPath}"

    # Radiomics.jl driver script — only used when radiomicsMethod=radiomicsjl (the
    # Julia runtime + Radiomics.jl live in the output_conversion image). Fetched
    # alongside the notebook so the extraction logic can be iterated without an
    # image rebuild; a miss leaves the notebook to record a clear "driver not
    # found" radiomics error.
    fetch radiomics_jl_extract.jl "workflows/common/Notebooks/radiomics_jl_extract.jl" optional
    # Checkpoint helper (per-series SEG + radiomics resume; no-op unless checkpointGcsPath).
    fetch segmentator_checkpoint.py "workflows/common/Notebooks/segmentator_checkpoint.py"

    # snomedMappingPath may be empty when the model bundles its own SNOMED table
    # into the segmentation archive (e.g. MOOSE ships moosez's
    # moose_snomed_mapping.csv); nb3 then reads the bundled copy instead.
    if [ -n "~{snomedMappingPath}" ]; then
      fetch snomed_mapping.csv "~{snomedMappingPath}"
    fi

    # Feature -> DICOM quantity/units code mapping (IBSI + UCUM) for the TID1500
    # SR writer. A miss just disables SR (recorded in sr_error_file.txt).
    fetch radiomicsFeaturesMaps.csv "workflows/common/resources/radiomicsFeaturesMaps.csv" optional

    if ! papermill outputConversionNotebook.ipynb outputConversionOutputNotebook.ipynb \
      -p segmentationArchivePath "~{segmentationArchive}" \
      -p snomedMappingPath "snomed_mapping.csv" \
      -p modelName "~{modelName}" \
      -p runRadiomics ~{runRadiomics} \
      -p runStructuredReport ~{runStructuredReport} \
      -p radiomicsMethod "~{radiomicsMethod}" \
      -p radiomicsFeatureClasses "~{radiomicsFeatureClasses}" \
      -p radiomicsFeatureCodesPath "radiomicsFeaturesMaps.csv" \
      -p radiomicsJlThreads ~{juliaThreads} \
      -p radiomicsMaxRoiMvox ~{maxRoiMvox} \
      -p dicomSegBucketUri "~{dicomSegBucketUri}" \
      -p dicomStoreImportUri "~{dicomStoreImportUri}" \
      -p inferenceUsageMetricsCsvPath "~{inferenceUsageMetricsCsv}"       -p convertUsageMetricsCsvPath "~{default='' convertUsageMetricsCsv}" \
      -p input_uri "~{inputUri}" \
      -p secret_project "~{secretProject}" \
      -p runId "$RUN_ID" \
      -p checkpointGcs "~{checkpointGcsPath}"; then
      >&2 echo "Output-conversion notebook failed"
      [ -f dicom_seg_error_file.txt ] && { >&2 echo "----- dicom_seg_error_file.txt -----"; cat dicom_seg_error_file.txt >&2; }
      exit 1
    fi

    if [ ! -f dicom_seg.tar ]; then
      >&2 echo "Expected output archive dicom_seg.tar was not created"
      exit 1
    fi
    if ! tar -tf dicom_seg.tar | grep -E '\.dcm$' >/dev/null; then
      >&2 echo "No DICOM-SEG files found in dicom_seg.tar"
      if [ ! -f dicom_seg_error_file.txt ]; then
        echo "No DICOM-SEG files were generated by output conversion." > dicom_seg_error_file.txt
      fi
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
    File outputNotebook          = "outputConversionOutputNotebook.ipynb"
    File dicomSegArchive         = "dicom_seg.tar"
    File usageMetricsCsv         = "output_conversion_UsageMetrics.csv"
    File combinedUsageMetricsCsv = "combined_UsageMetrics.csv"
    File? runSummary             = "run_summary.json"

    File? radiomicsArchive = "radiomics.tar"
    File? srDicomArchive   = "structured_reports_dicom.tar"
    File? srJsonArchive    = "structured_reports_json.tar"

    File? dicomSegErrors  = "dicom_seg_error_file.txt"
    File? radiomicsErrors = "radiomics_error_file.txt"
    File? srErrors        = "sr_error_file.txt"
  }
}
