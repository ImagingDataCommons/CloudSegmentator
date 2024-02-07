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
   String downloadDicomAndConvertDocker = "imagingdatacommons/download_convert:v1.3.0"
   String inferenceTotalSegmentatorDocker = "imagingdatacommons/inference_totalseg:v1.3.0"
   String dicomsegAndRadiomicsSR_Docker = "imagingdatacommons/dicom_seg_pyradiomics_sr:v1.3.0"

   #Preemptible retries
   Int downloadAndConvertPreemptibleTries = 3
   Int inferenceTotalSegmentatorPreemptibleTries = 3
   Int dicomsegAndRadiomicsSR_PreemptibleTries = 3

   #Compute CPU configuration
   Int downloadAndConvertCpus = 2
   Int inferenceTotalSegmentatorCpus = 2
   Int dicomsegAndRadiomicsSR_Cpus = 4

   Int downloadAndConvertRAM = 2
   Int inferenceTotalSegmentatorRAM = 13
   Int dicomsegAndRadiomicsSR_RAM = 16

   String downloadAndConvertCpuFamily = 'AMD Rome'
   #String inferenceTotalSegmentatorCpuFamily = 'Intel Cascade Lake' #Because GPUs are available only with N1 family
   #String dicomsegAndRadiomicsSR_CpuFamily = 'Intel Cascade Lake' 
   String dicomsegAndRadiomicsSR_CpuFamily = 'AMD Rome'  

   String inferenceTotalSegmentatorGpuType = 'nvidia-tesla-t4'

   String downloadAndConvertZones = "us-central1-a us-central1-b us-central1-c us-central1-f"
   String inferenceTotalSegmentatorZones = "us-central1-a us-central1-b us-central1-c us-central1-f"
   #String dicomsegAndRadiomicsSR_Zones = "us-central1-a us-central1-b us-central1-c us-central1-f us-east1-b us-east1-c us-east1-d us-east5-a us-east5-b us-east5-c us-west1-a us-west1-b us-west1-c us-west4-a us-west4-b us-west4-c"
   String dicomsegAndRadiomicsSR_Zones = "asia-northeast2-a asia-northeast2-b asia-northeast2-c europe-west4-a europe-west4-b europe-west4-c europe-north1-a europe-north1-b europe-north1-c us-central1-a us-central1-b us-central1-c us-central1-f us-east1-b us-east1-c us-east1-d us-west1-a us-west1-b us-west1-c"

 }
 #calling Papermill Task with the inputs
 call downloadAndConvert{
   input :
        #yamlParameters = yamlParameters,
        yamlListOfSeriesInstanceUIDs = yamlListOfSeriesInstanceUIDs,
        downloadDicomAndConvertDocker = downloadDicomAndConvertDocker,
        downloadAndConvertPreemptibleTries = downloadAndConvertPreemptibleTries,
        downloadAndConvertCpus = downloadAndConvertCpus,
        downloadAndConvertRAM = downloadAndConvertRAM,
        downloadAndConvertZones = downloadAndConvertZones,
        downloadAndConvertCpuFamily = downloadAndConvertCpuFamily
 }
 call inferenceTotalSegmentator{
   input :
     yamlListOfSeriesInstanceUIDs = yamlListOfSeriesInstanceUIDs,
     inferenceTotalSegmentatorDocker = inferenceTotalSegmentatorDocker ,
     inferenceTotalSegmentatorPreemptibleTries = inferenceTotalSegmentatorPreemptibleTries ,
     inferenceTotalSegmentatorCpus = inferenceTotalSegmentatorCpus ,
     inferenceTotalSegmentatorRAM = inferenceTotalSegmentatorRAM ,
     inferenceTotalSegmentatorZones = inferenceTotalSegmentatorZones ,

     inferenceTotalSegmentatorGpuType = inferenceTotalSegmentatorGpuType,
     #Nifti files converted in the first step are provided as input here
     NiftiFiles = downloadAndConvert.downloadDicomAndConvertNiftiFiles
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
    inferenceZipFile = inferenceTotalSegmentator.inferenceZipFile
}


 output {
  #output notebooks
   File downloadDicomAndConvertOutputNotebook = downloadAndConvert.downloadDicomAndConvertOutputJupyterNotebook
   File inferenceTotalSegmentatorOutputNotebook = inferenceTotalSegmentator.inferenceOutputJupyterNotebook
   File dicomsegAndRadiomicsSR_OutputNotebook = dicomsegAndRadiomicsSR.dicomsegAndRadiomicsSR_OutputJupyterNotebook   

   File downloadDicomAndConvertUsageMetrics  = downloadAndConvert.downloadDicomAndConvertUsageMetrics
   File inferenceUsageMetrics  = inferenceTotalSegmentator.inferenceUsageMetrics
   File dicomsegAndRadiomicsSR_UsageMetrics  = dicomsegAndRadiomicsSR.dicomsegAndRadiomicsSR_UsageMetrics

   File dicomsegAndRadiomicsSR_CompressedFiles = dicomsegAndRadiomicsSR.dicomsegAndRadiomicsSR_CompressedFiles

   File pyradiomicsRadiomicsFeatures = dicomsegAndRadiomicsSR.pyradiomicsRadiomicsFeatures
   File structuredReportsDICOM = dicomsegAndRadiomicsSR.structuredReportsDICOM
   File structuredReportsJSON = dicomsegAndRadiomicsSR.structuredReportsJSON
   
   File? dcm2niix_errors = downloadAndConvert.dcm2niix_errors
   File? totalsegmentatorErrors = inferenceTotalSegmentator.totalsegmentatorErrors
   File? dicomsegAndRadiomicsSR_Errors = dicomsegAndRadiomicsSR.dicomsegAndRadiomicsSR_SRErrors
   File? downloadDicomAndConvert_modality_errors = downloadAndConvert.downloadDicomAndConvert_modality_errors
   File? dicomsegAndRadiomicsSR_modality_errors = dicomsegAndRadiomicsSR.dicomsegAndRadiomicsSR_modality_errors
   File? dicomsegAndRadiomicsSR_SEGErrors = dicomsegAndRadiomicsSR.dicomsegAndRadiomicsSR_SEGErrors
 }
}
#Task Definitions
task downloadAndConvert {
 input {
    #File yamlParameters
    String yamlListOfSeriesInstanceUIDs
    String downloadDicomAndConvertDocker
    Int downloadAndConvertPreemptibleTries 
    Int downloadAndConvertCpus 
    Int downloadAndConvertRAM 
    String downloadAndConvertZones 
    String downloadAndConvertCpuFamily
 }
 command {
   wget https://raw.githubusercontent.com/ImagingDataCommons/CloudSegmentator/v1.3.0/workflows/TotalSegmentator/Notebooks/downloadDicomAndConvertNotebook.ipynb
   set -e
   papermill downloadDicomAndConvertNotebook.ipynb downloadAndConvertOutputJupyterNotebook.ipynb -y "~{yamlListOfSeriesInstanceUIDs}"
 }
 #Run time attributes:
 runtime {
   docker: downloadDicomAndConvertDocker
   cpu: downloadAndConvertCpus
   cpuPlatform: downloadAndConvertCpuFamily
   zones: downloadAndConvertZones
   memory: downloadAndConvertRAM + " GiB"
   disks: "local-disk 10 HDD"  #ToDo: Dynamically calculate disk space using the no of bytes of yaml file size. 64 characters is the max size I found in a seriesInstanceUID
   preemptible: downloadAndConvertPreemptibleTries
   maxRetries: 1
 }
  
 output {
   File downloadDicomAndConvertOutputJupyterNotebook = "downloadAndConvertOutputJupyterNotebook.ipynb"
   File downloadDicomAndConvertUsageMetrics = "downloadDicomAndConvertUsageMetrics.lz4"
   File downloadDicomAndConvertNiftiFiles = "downloadDicomAndConvertNiftiFiles.tar.lz4"
   File? dcm2niix_errors = "dcm2niix_errors.csv"
   File? downloadDicomAndConvert_modality_errors = "modality_error_file.txt"
 }
}

#Task Definitions
task inferenceTotalSegmentator {
 input {
   #Just like the workflow inputs, any new inputs entered here but not hardcoded will appear in the UI as required fields
   #And the hardcoded inputs will appear as optional to override the values entered here
   # Command parameters
    String yamlListOfSeriesInstanceUIDs
    String inferenceTotalSegmentatorDocker 
    Int inferenceTotalSegmentatorPreemptibleTries 
    Int inferenceTotalSegmentatorCpus 
    Int inferenceTotalSegmentatorRAM 
    String inferenceTotalSegmentatorZones 

    String inferenceTotalSegmentatorGpuType

    File NiftiFiles 

 }

 command {
   wget https://raw.githubusercontent.com/ImagingDataCommons/CloudSegmentator/v1.3.0/workflows/TotalSegmentator/Notebooks/inferenceTotalSegmentatorNotebook.ipynb
   set -e
   papermill -p niftiFilePath ~{NiftiFiles} inferenceTotalSegmentatorNotebook.ipynb inferenceOutputJupyterNotebook.ipynb
 }
 #Run time attributes:
 runtime {
   docker: inferenceTotalSegmentatorDocker
   cpu: inferenceTotalSegmentatorCpus
   #cpuPlatform: downloadAndConvertCpuFamily
   zones: inferenceTotalSegmentatorZones
   memory: inferenceTotalSegmentatorRAM + " GiB"
   disks: "local-disk 10 HDD"  #ToDo: Dynamically calculate disk space using the no of bytes of yaml file size. 64 characters is the max size I found in a seriesInstanceUID
   preemptible: inferenceTotalSegmentatorPreemptibleTries
   maxRetries: 1
   gpuType: inferenceTotalSegmentatorGpuType
   gpuCount: 1
 }
  
 output {
   File inferenceOutputJupyterNotebook = "inferenceOutputJupyterNotebook.ipynb"
   File inferenceZipFile = "inferenceNiftiFiles.tar.lz4"
   File inferenceUsageMetrics = "inferenceUsageMetrics.lz4"
   #File inferenceMetaData = "inferenceMetaData.tar.lz4"
   File? totalsegmentatorErrors = "totalsegmentator_errors.txt"
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
   wget https://raw.githubusercontent.com/ImagingDataCommons/CloudSegmentator/v1.3.0/workflows/TotalSegmentator/Notebooks/dicomsegAndRadiomicsSR_Notebook.ipynb
   set -e
   papermill -p inferenceNiftiFilePath ~{inferenceZipFile}  dicomsegAndRadiomicsSR_Notebook.ipynb dicomsegAndRadiomicsSR_OutputJupyterNotebook.ipynb || (>&2 echo "Killed" && exit 1)
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
   File? dicomsegAndRadiomicsSR_SEGErrors = "itkimage2segimage_error_file.txt"
 }
}