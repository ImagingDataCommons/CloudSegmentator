version 1.0
#WORKFLOW DEFINITION
workflow TotalSegmentator {
 input {
   #all the inputs entered here but not hardcoded will appear in the UI as required fields
   #And the hardcoded inputs will appear as optional to override the values entered here
   #File yamlParameters
   
   #Parameters
   String yamlListOfSeriesInstanceUIDs

   #Docker Images for each task
   String downloadDicomAndConvertAndInferenceTotalSegmentatorDocker = "imagingdatacommons/download_convert_inference_totalseg:main"
   String dicomsegAndRadiomicsSR_Docker = "imagingdatacommons/dicom_seg_pyradiomics_sr:main"

   #Preemptible retries

   Int downloadDicomAndConvertAndInferenceTotalSegmentatorPreemptibleTries = 3
   Int dicomsegAndRadiomicsSR_PreemptibleTries = 3

   #Compute CPU configuration
   Int downloadDicomAndConvertAndInferenceTotalSegmentatorCpus = 2
   Int dicomsegAndRadiomicsSR_Cpus = 4

   Int downloadDicomAndConvertAndInferenceTotalSegmentatorRAM = 13
   Int dicomsegAndRadiomicsSR_RAM = 16

   #String downloadDicomAndConvertAndInferenceTotalSegmentatorCpuFamily = 'Intel Cascade Lake' #Because GPUs are available only with N1 family
   #String dicomsegAndRadiomicsSR_CpuFamily = 'Intel Cascade Lake'   
   String dicomsegAndRadiomicsSR_CpuFamily = 'AMD Rome' 
   
   String downloadDicomAndConvertAndInferenceTotalSegmentatorGpuType = 'nvidia-tesla-t4'

   String downloadDicomAndConvertAndInferenceTotalSegmentatorZones = "us-west4-a us-west4-b us-east4-a us-east4-b us-east4-c europe-west2-a europe-west2-b asia-northeast1-a asia-northeast1-c asia-southeast1-a asia-southeast1-b asia-southeast1-c europe-west4-a europe-west4-b europe-west4-c"
   String dicomsegAndRadiomicsSR_Zones = "asia-northeast2-a asia-northeast2-b asia-northeast2-c europe-west4-a europe-west4-b europe-west4-c europe-north1-a europe-north1-b europe-north1-c us-central1-a us-central1-b us-central1-c us-central1-f us-east1-b us-east1-c us-east1-d us-west1-a us-west1-b us-west1-c"

 }
 #calling Papermill Task with the inputs
 call downloadDicomAndConvertAndInferenceTotalSegmentator{
   input :
     yamlListOfSeriesInstanceUIDs = yamlListOfSeriesInstanceUIDs,
     downloadDicomAndConvertAndInferenceTotalSegmentatorDocker = downloadDicomAndConvertAndInferenceTotalSegmentatorDocker ,
     downloadDicomAndConvertAndInferenceTotalSegmentatorPreemptibleTries = downloadDicomAndConvertAndInferenceTotalSegmentatorPreemptibleTries ,
     downloadDicomAndConvertAndInferenceTotalSegmentatorCpus = downloadDicomAndConvertAndInferenceTotalSegmentatorCpus ,
     downloadDicomAndConvertAndInferenceTotalSegmentatorRAM = downloadDicomAndConvertAndInferenceTotalSegmentatorRAM ,
     downloadDicomAndConvertAndInferenceTotalSegmentatorZones = downloadDicomAndConvertAndInferenceTotalSegmentatorZones ,
     downloadDicomAndConvertAndInferenceTotalSegmentatorGpuType = downloadDicomAndConvertAndInferenceTotalSegmentatorGpuType,
 }
 call dicomsegAndRadiomicsSR{
   input:
    dicomsegAndRadiomicsSR_Docker = dicomsegAndRadiomicsSR_Docker,
    dicomsegAndRadiomicsSR_PreemptibleTries = dicomsegAndRadiomicsSR_PreemptibleTries,
    dicomsegAndRadiomicsSR_Cpus = dicomsegAndRadiomicsSR_Cpus,
    dicomsegAndRadiomicsSR_RAM = dicomsegAndRadiomicsSR_RAM,
    dicomsegAndRadiomicsSR_Zones = dicomsegAndRadiomicsSR_Zones,
    dicomsegAndRadiomicsSR_CpuFamily = dicomsegAndRadiomicsSR_CpuFamily,
    #Nifti files converted in the first step are provided as input here
    inferenceZipFile = downloadDicomAndConvertAndInferenceTotalSegmentator.downloadDicomAndConvertAndInferenceTotalSegmentatorZipFile
}

 output {
  #output notebooks
  
   File downloadDicomAndConvertAndInferenceTotalSegmentatorOutputNotebook = downloadDicomAndConvertAndInferenceTotalSegmentator.downloadDicomAndConvertAndInferenceTotalSegmentatorOutputJupyterNotebook
   File dicomsegAndRadiomicsSR_OutputNotebook = dicomsegAndRadiomicsSR.dicomsegAndRadiomicsSR_OutputJupyterNotebook   

   File downloadDicomAndConvertAndInferenceTotalSegmentatorUsageMetrics= downloadDicomAndConvertAndInferenceTotalSegmentator.downloadDicomAndConvertAndInferenceTotalSegmentatorUsageMetrics
   File dicomsegAndRadiomicsSR_UsageMetrics  = dicomsegAndRadiomicsSR.dicomsegAndRadiomicsSR_UsageMetrics

   File dicomsegAndRadiomicsSR_CompressedFiles = dicomsegAndRadiomicsSR.dicomsegAndRadiomicsSR_CompressedFiles
   
   File pyradiomicsRadiomicsFeatures = dicomsegAndRadiomicsSR.pyradiomicsRadiomicsFeatures
   File structuredReportsDICOM = dicomsegAndRadiomicsSR.structuredReportsDICOM
   File structuredReportsJSON = dicomsegAndRadiomicsSR.structuredReportsJSON
   
   File? dcm2niixErrors = downloadDicomAndConvertAndInferenceTotalSegmentator.dcm2niixErrors
   File? totalsegmentatorErrors = downloadDicomAndConvertAndInferenceTotalSegmentator.totalsegmentatorErrors
   File? dicomsegAndRadiomicsSR_Errors = dicomsegAndRadiomicsSR.dicomsegAndRadiomicsSR_SRErrors
   File? downloadDicomAndConvertAndInferenceTotalSegmentator_modality_errors = downloadDicomAndConvertAndInferenceTotalSegmentator.downloadDicomAndConvertAndInferenceTotalSegmentator_modality_errors
   File? dicomsegAndRadiomicsSR_modality_errors = dicomsegAndRadiomicsSR.dicomsegAndRadiomicsSR_modality_errors
 }
}

#Task Definitions
task downloadDicomAndConvertAndInferenceTotalSegmentator{
 input {
   #Just like the workflow inputs, any new inputs entered here but not hardcoded will appear in the UI as required fields
   #And the hardcoded inputs will appear as optional to override the values entered here
   # Command parameters
    String yamlListOfSeriesInstanceUIDs
    String downloadDicomAndConvertAndInferenceTotalSegmentatorDocker 
    Int downloadDicomAndConvertAndInferenceTotalSegmentatorPreemptibleTries 
    Int downloadDicomAndConvertAndInferenceTotalSegmentatorCpus 
    Int downloadDicomAndConvertAndInferenceTotalSegmentatorRAM 
    String downloadDicomAndConvertAndInferenceTotalSegmentatorZones 
    String downloadDicomAndConvertAndInferenceTotalSegmentatorGpuType 
 }

 command {
   wget https://raw.githubusercontent.com/ImagingDataCommons/CloudSegmentator/main/workflows/TotalSegmentator/Notebooks/downloadDicomAndConvertAndInferenceTotalSegmentatorNotebook.ipynb
   set -e
   papermill downloadDicomAndConvertAndInferenceTotalSegmentatorNotebook.ipynb downloadDicomAndConvertAndInferenceTotalSegmentatorOutputJupyterNotebook.ipynb -y "~{yamlListOfSeriesInstanceUIDs}"
 }
 #Run time attributes:
 runtime {
   docker: downloadDicomAndConvertAndInferenceTotalSegmentatorDocker 
   cpu: downloadDicomAndConvertAndInferenceTotalSegmentatorCpus 
   #cpuPlatform: downloadDicomAndConvertAndInferenceTotalSegmentatorCpuFamily 
   zones: downloadDicomAndConvertAndInferenceTotalSegmentatorZones 
   memory: downloadDicomAndConvertAndInferenceTotalSegmentatorRAM + " GiB"
   disks: "local-disk 10 HDD"  #ToDo: Dynamically calculate disk space using the no of bytes of yaml file size. 64 characters is the max size I found in a seriesInstanceUID
   preemptible: downloadDicomAndConvertAndInferenceTotalSegmentatorPreemptibleTries 
   maxRetries: 1
   gpuType: downloadDicomAndConvertAndInferenceTotalSegmentatorGpuType 
   gpuCount: 1
 }
  
 output {
   File downloadDicomAndConvertAndInferenceTotalSegmentatorOutputJupyterNotebook= "downloadDicomAndConvertAndInferenceTotalSegmentatorOutputJupyterNotebook.ipynb"
   File downloadDicomAndConvertAndInferenceTotalSegmentatorZipFile = "inferenceNiftiFiles.tar.lz4"
   File downloadDicomAndConvertAndInferenceTotalSegmentatorUsageMetrics= "inferenceUsageMetrics.lz4"
   #File downloadDicomAndConvertAndInferenceTotalSegmentatorMetaData = "inferenceMetaData.tar.lz4"
   File? dcm2niixErrors = "error_file.txt"
   File? totalsegmentatorErrors = "totalsegmentator_errors.txt"
   File? downloadDicomAndConvertAndInferenceTotalSegmentator_modality_errors = "modality_error_file.txt"
 }
}

#Task Definitions
task dicomsegAndRadiomicsSR{
 input {
   #Just like the workflow inputs, any new inputs entered here but not hardcoded will appear in the UI as required fields
   #And the hardcoded inputs will appear as optional to override the values entered here
    String dicomsegAndRadiomicsSR_Docker
    Int dicomsegAndRadiomicsSR_PreemptibleTries 
    Int dicomsegAndRadiomicsSR_Cpus 
    Int dicomsegAndRadiomicsSR_RAM 
    String dicomsegAndRadiomicsSR_Zones 
    String dicomsegAndRadiomicsSR_CpuFamily

    File inferenceZipFile
 }
 command {
   wget https://raw.githubusercontent.com/ImagingDataCommons/CloudSegmentator/main/workflows/TotalSegmentator/Notebooks/dicomsegAndRadiomicsSR_Notebook.ipynb
   
   set -o xtrace
   # For any command failures in the rest of this script, return the error.
   set -o pipefail
   set +o errexit
   
   papermill  -p inferenceNiftiFilePath ~{inferenceZipFile}  dicomsegAndRadiomicsSR_Notebook.ipynb dicomsegAndRadiomicsSR_OutputJupyterNotebook.ipynb
   
   set -o errexit
   exit $?
 }

 #Run time attributes:
 runtime {
   docker: dicomsegAndRadiomicsSR_Docker
   cpu: dicomsegAndRadiomicsSR_Cpus
   cpuPlatform: dicomsegAndRadiomicsSR_CpuFamily
   zones: dicomsegAndRadiomicsSR_Zones
   memory: dicomsegAndRadiomicsSR_RAM + " GiB"
   disks: "local-disk 10 HDD"  #ToDo: Dynamically calculate disk space using the no of bytes of yaml file size. 64 characters is the max size I found in a seriesInstanceUID
   preemptible: dicomsegAndRadiomicsSR_PreemptibleTries
   maxRetries: 1
 }
 output {
   File dicomsegAndRadiomicsSR_OutputJupyterNotebook = "dicomsegAndRadiomicsSR_OutputJupyterNotebook.ipynb"
   File dicomsegAndRadiomicsSR_CompressedFiles = "dicomsegAndRadiomicsSR_DICOMsegFiles.tar.lz4"
   File pyradiomicsRadiomicsFeatures = "pyradiomicsRadiomicsFeatures.tar.lz4"
   File structuredReportsDICOM = "structuredReportsDICOM.tar.lz4"
   File structuredReportsJSON = "structuredReportsJSON.tar.lz4"
   File dicomsegAndRadiomicsSR_UsageMetrics = "dicomsegAndRadiomicsSR_UsageMetrics.lz4"
   File? dicomsegAndRadiomicsSR_RadiomicsErrors = "radiomics_error_file.txt"
   File? dicomsegAndRadiomicsSR_SRErrors = "sr_error_file.txt"  
   File? dicomsegAndRadiomicsSR_modality_errors = "modality_error_file.txt" 
 }
}