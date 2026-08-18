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
#   inferenceDocker        - per-model image, FROM imagingdatacommons/segmentator-base
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

    # Per-model GPU inference image (derived FROM segmentator-base).
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

    # ------------------------------------------------------------------------
    # OPTIONAL: checkpoint/resume on preemption (inference task)
    # ------------------------------------------------------------------------
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
    String outputConversionDocker = "imagingdatacommons/output_conversion:main"
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
      secretProject             = secretProject
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

    # ---- Fetch shared convert notebook (nb1) and model inference notebook (nb2)
    wget -O convertNotebook.ipynb   "${RAW}/~{convertNotebookPath}"
    wget -O inferenceNotebook.ipynb "${RAW}/~{inferenceNotebookPath}"

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

    # Fail fast when archive has no NIfTI segmentation volumes.
    lz4 -d -c segmentations.tar.lz4 | tar -tf - > segmentations_tar_list.txt
    if ! grep -E '\.nii(\.gz)?$' segmentations_tar_list.txt >/dev/null; then
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
# Runs on the cheaper CPU-only segmentator-base image (AMD Rome / N2D).
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

    wget -O outputConversionNotebook.ipynb "${RAW}/~{outputConversionNotebookPath}"

    # Radiomics.jl driver script — only used when radiomicsMethod=radiomicsjl (the
    # Julia runtime + Radiomics.jl live in the output_conversion image). Fetched
    # alongside the notebook so the extraction logic can be iterated without an
    # image rebuild; errexit is off here, so a miss just leaves the notebook to
    # record a clear "driver not found" radiomics error.
    wget -O radiomics_jl_extract.jl "${RAW}/workflows/common/Notebooks/radiomics_jl_extract.jl"

    # snomedMappingPath may be empty when the model bundles its own SNOMED table
    # into the segmentation archive (e.g. MOOSE ships moosez's
    # moose_snomed_mapping.csv); nb3 then reads the bundled copy instead.
    if [ -n "~{snomedMappingPath}" ]; then
      wget -O snomed_mapping.csv "${RAW}/~{snomedMappingPath}"
    fi

    if ! papermill outputConversionNotebook.ipynb outputConversionOutputNotebook.ipynb \
      -p segmentationArchivePath "~{segmentationArchive}" \
      -p snomedMappingPath "snomed_mapping.csv" \
      -p modelName "~{modelName}" \
      -p runRadiomics ~{runRadiomics} \
      -p runStructuredReport ~{runStructuredReport} \
      -p radiomicsMethod "~{radiomicsMethod}" \
      -p dicomSegBucketUri "~{dicomSegBucketUri}" \
      -p dicomStoreImportUri "~{dicomStoreImportUri}" \
      -p inferenceUsageMetricsCsvPath "~{inferenceUsageMetricsCsv}"       -p convertUsageMetricsCsvPath "~{default='' convertUsageMetricsCsv}" \
      -p input_uri "~{inputUri}" \
      -p secret_project "~{secretProject}" \
      -p runId "$RUN_ID"; then
      >&2 echo "Output-conversion notebook failed"
      [ -f dicom_seg_error_file.txt ] && { >&2 echo "----- dicom_seg_error_file.txt -----"; cat dicom_seg_error_file.txt >&2; }
      exit 1
    fi

    if [ ! -f dicom_seg.tar.lz4 ]; then
      >&2 echo "Expected output archive dicom_seg.tar.lz4 was not created"
      exit 1
    fi
    if ! lz4 -d -c dicom_seg.tar.lz4 | tar -tf - | grep -E '\.dcm$' >/dev/null; then
      >&2 echo "No DICOM-SEG files found in dicom_seg.tar.lz4"
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
    File dicomSegArchive         = "dicom_seg.tar.lz4"
    File usageMetricsCsv         = "output_conversion_UsageMetrics.csv"
    File combinedUsageMetricsCsv = "combined_UsageMetrics.csv"
    File? runSummary             = "run_summary.json"

    File? radiomicsArchive = "radiomics.tar.lz4"
    File? srDicomArchive   = "structured_reports_dicom.tar.lz4"
    File? srJsonArchive    = "structured_reports_json.tar.lz4"

    File? dicomSegErrors  = "dicom_seg_error_file.txt"
    File? radiomicsErrors = "radiomics_error_file.txt"
  }
}
