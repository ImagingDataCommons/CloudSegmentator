version 1.0
#WORKFLOW DEFINITION
workflow MOOSE {
 input {
   # All inputs entered here but not hardcoded will appear in the Terra UI as required fields.
   # Hardcoded inputs appear as optional overrideable defaults.

   # YAML list of SeriesInstanceUIDs to process (passed verbatim to papermill -y)
   String yamlListOfSeriesInstanceUIDs

   # Comma-separated moosez model names
   # Available: clin_ct_organs, clin_ct_ribs, clin_ct_vertebrae, clin_ct_body,
   #            clin_ct_muscles, clin_ct_cardiac, clin_ct_lungs
   String mooseModels = "clin_ct_organs,clin_ct_ribs,clin_ct_vertebrae"

   # Accelerator: 'cuda' for GPU, 'cpu' for CPU-only
   String accelerator = "cuda"

   # Docker image
   String mooseDocker = "sunderlandkyl/moose-test:latest"

   # Preemptible retries (Terra will retry on spot-instance interruption)
   Int moosePreemptibleTries = 3

   # Compute: CPU
   Int mooseCpus = 2

   # Compute: RAM (GiB)
   Int mooseRAM = 13

   # Compute: GPU model
   String mooseGpuType = "nvidia-tesla-t4"

   # Compute: eligible GCP zones that have the requested GPU
   String mooseZones = "us-east4-a us-east4-b us-east4-c"
 }

 call mooseEndToEnd {
   input:
     yamlListOfSeriesInstanceUIDs = yamlListOfSeriesInstanceUIDs,
     mooseModels                  = mooseModels,
     accelerator                  = accelerator,
     mooseDocker                  = mooseDocker,
     moosePreemptibleTries        = moosePreemptibleTries,
     mooseCpus                    = mooseCpus,
     mooseRAM                     = mooseRAM,
     mooseGpuType                 = mooseGpuType,
     mooseZones                   = mooseZones
 }

 output {
   File mooseOutputNotebook     = mooseEndToEnd.mooseOutputNotebook
   File mooseSegmentations      = mooseEndToEnd.mooseSegmentations
   File mooseUsageMetrics       = mooseEndToEnd.mooseUsageMetrics

   File? downloadErrors         = mooseEndToEnd.downloadErrors
   File? dcm2niixErrors         = mooseEndToEnd.dcm2niixErrors
   File? mooseErrors            = mooseEndToEnd.mooseErrors
 }
}


# Task Definitions
task mooseEndToEnd {
 input {
   String yamlListOfSeriesInstanceUIDs
   String mooseModels
   String accelerator
   String mooseDocker
   Int    moosePreemptibleTries
   Int    mooseCpus
   Int    mooseRAM
   String mooseGpuType
   String mooseZones
 }

 command {
   wget https://raw.githubusercontent.com/Sunderlandkyl/CloudSegmentator/moose_test/workflows/MOOSE/Notebooks/endToEndMOOSENotebook.ipynb
   set -e
   papermill endToEndMOOSENotebook.ipynb mooseOutputNotebook.ipynb \
     -y "~{yamlListOfSeriesInstanceUIDs}" \
     -p moose_models "~{mooseModels}" \
     -p accelerator "~{accelerator}" \
     || (>&2 echo "Killed" && exit 1)
 }

 runtime {
   docker:      mooseDocker
   cpu:         mooseCpus
   gpuType:     mooseGpuType
   gpuCount:    1
   zones:       mooseZones
   memory:      mooseRAM + " GiB"
   # Disk: ~500 MB per series for DICOM + NIfTI + masks; adjust for large batches
   disks:       "local-disk 50 HDD"
   preemptible: moosePreemptibleTries
   maxRetries:  1
 }

 output {
   File  mooseOutputNotebook = "mooseOutputNotebook.ipynb"
   File  mooseSegmentations  = "moose_segmentations.tar.lz4"
   File  mooseUsageMetrics   = "moose_UsageMetrics.lz4"

   File? downloadErrors      = "download_error_file.txt"
   File? dcm2niixErrors      = "error_file.txt"
   File? mooseErrors         = "moose_errors.txt"
 }
}
