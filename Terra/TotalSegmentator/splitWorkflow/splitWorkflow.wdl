version 1.0
#WORKFLOW DEFINITION
workflow TotalSegmentator {
 input {
   #all the inputs entered here but not hardcoded will appear in the UI as required fields
   #And the hardcoded inputs will appear as optional to override the values entered here
   #File yamlParameters
   File seriesInstanceS5cmdUrls
   #JupyterNotebooks containing the code
   File downloadDicomAndConvertNotebook
   File inferenceTotalSegmentatorNotebook
   File itkimage2segimageNotebook
   
   #Parameters
   String dicomToNiftiConverterTool

   #Docker Images for each task
   String downloadDicomAndConvertDocker = "vamsithiriveedhi/totalsegmentator:task1_v1"
   String inferenceTotalSegmentatorDocker = "vamsithiriveedhi/totalsegmentator:cuda12.0_v1"
   String itkimage2segimageDocker = "vamsithiriveedhi/totalsegmentator:nocuda_v1"

   #Preemptible retries
   Int downloadAndConvertPreemptibleTries = 3
   Int inferenceTotalSegmentatorPreemptibleTries = 3
   Int itkimage2segimagePreemptibleTries = 3

   #Compute CPU configuration
   Int downloadAndConvertCpus = 2
   Int inferenceTotalSegmentatorCpus = 2
   Int itkimage2segimageCpus = 2

   Int downloadAndConvertRAM = 1
   Int inferenceTotalSegmentatorRAM = 8
   Int itkimage2segimageRAM = 2

   String downloadAndConvertCpuFamily = 'AMD Rome'
   #String inferenceTotalSegmentatorCpuFamily = 'Intel Skylake' Because GPUs are available only with N1 family
   String itkimage2segimageCpuFamily = 'AMD Rome'   

   String inferenceTotalSegmentatorGpuType = 'nvidia-tesla-t4'

   String downloadAndConvertZones = "us-central1-a us-central1-b us-central1-c us-central1-f us-east1-b us-east1-c us-east1-d us-east5-a us-east5-b us-east5-c us-west1-a us-west1-b us-west1-c"
   String inferenceTotalSegmentatorZones = 'us-west4-a us-west4-b asia-east1-a asia-east1-c australia-southeast1-a australia-southeast1-c asia-northeast1-a asia-northeast1-c'
   String itkimage2segimageZones = "us-central1-a us-central1-b us-central1-c us-central1-f us-east1-b us-east1-c us-east1-d us-east5-a us-east5-b us-east5-c us-west1-a us-west1-b us-west1-c"

 }
 #calling Papermill Task with the inputs
 call downloadAndConvert{
   input :
        #yamlParameters = yamlParameters,
        seriesInstanceS5cmdUrls = seriesInstanceS5cmdUrls,
        downloadDicomAndConvertNotebook = downloadDicomAndConvertNotebook,
        downloadDicomAndConvertDocker = downloadDicomAndConvertDocker,
        downloadAndConvertPreemptibleTries = downloadAndConvertPreemptibleTries,
        downloadAndConvertCpus = downloadAndConvertCpus,
        downloadAndConvertRAM = downloadAndConvertRAM,
        downloadAndConvertZones = downloadAndConvertZones,
        downloadAndConvertCpuFamily = downloadAndConvertCpuFamily
 }
 call inference{
   input :
     inferenceTotalSegmentatorNotebook= inferenceTotalSegmentatorNotebook,
     inferenceTotalSegmentatorDocker = inferenceTotalSegmentatorDocker ,
     inferenceTotalSegmentatorPreemptibleTries = inferenceTotalSegmentatorPreemptibleTries ,
     inferenceTotalSegmentatorCpus = inferenceTotalSegmentatorCpus ,
     inferenceTotalSegmentatorRAM = inferenceTotalSegmentatorRAM ,
     inferenceTotalSegmentatorZones = inferenceTotalSegmentatorZones ,

     inferenceTotalSegmentatorGpuType = inferenceTotalSegmentatorGpuType,
     #Nifti files converted in the first step are provided as input here
     NiftiFiles = downloadAndConvert.downloadDicomAndConvertNiftiFiles
 }
 call itkimage2segimage{
   input:
    #yamlParameters = yamlParameters,
    seriesInstanceS5cmdUrls = seriesInstanceS5cmdUrls,
    itkimage2segimageNotebook = itkimage2segimageNotebook,
    itkimage2segimageDocker = itkimage2segimageDocker,
    itkimage2segimagePreemptibleTries = itkimage2segimagePreemptibleTries,
    itkimage2segimageCpus = itkimage2segimageCpus,
    itkimage2segimageRAM = itkimage2segimageRAM,
    itkimage2segimageZones = itkimage2segimageZones,
    itkimage2segimageCpuFamily = itkimage2segimageCpuFamily,
    #Nifti files converted in the first step are provided as input here
    inferenceZipFile = inference.inferenceZipFile
}


 output {
  #output notebooks
   File downloadDicomAndConvertOutputNotebook = downloadAndConvert.downloadDicomAndConvertOutputJupyterNotebook
   File inferenceTotalSegmentatorOutputNotebook = inference.inferenceOutputJupyterNotebook
   File itkimage2segimageOutputNotebook = itkimage2segimage.itkimage2segimageOutputJupyterNotebook   

   File downloadDicomAndConvertUsageMetrics  = downloadAndConvert.downloadDicomAndConvertUsageMetrics
   File inferenceUsageMetrics  = inference.inferenceUsageMetrics
   File itkimage2segimageUsageMetrics  = itkimage2segimage.itkimage2segimageUsageMetrics

   File itkimage2segimageZipFile = itkimage2segimage.itkimage2segimageZipFile
   
   File dcm2niix_errors = downloadAndConvert.dcm2niix_errors
  
 }

}
#Task Definitions
task downloadAndConvert {
 input {
    #File yamlParameters
    String dicomToNiftiConverterTool
    File seriesInstanceS5cmdUrls
    File downloadDicomAndConvertNotebook 
    String downloadDicomAndConvertDocker
    Int downloadAndConvertPreemptibleTries 
    Int downloadAndConvertCpus 
    Int downloadAndConvertRAM 
    String downloadAndConvertZones 
    String downloadAndConvertCpuFamily
 }
 command {
   set -e
   papermill -p converterType ~{dicomToNiftiConverterTool} -p csvFilePath ~{seriesInstanceS5cmdUrls}  ~{downloadDicomAndConvertNotebook} downloadAndConvertOutputJupyterNotebook.ipynb 
 }
 #Run time attributes:
 runtime {
   docker: downloadDicomAndConvertDocker
   cpu: downloadAndConvertCpus
   cpuPlatform: downloadAndConvertCpuFamily
   zones: downloadAndConvertZones
   memory: downloadAndConvertRAM + " GB"
   disks: "local-disk 50 SSD"  #ToDo: Dynamically calculate disk space using the no of bytes of yaml file size. 64 characters is the max size I found in a seriesInstanceUID
   preemptible: downloadAndConvertPreemptibleTries
   maxRetries: 1
 }
  
 output {
   File downloadDicomAndConvertOutputJupyterNotebook = "downloadDicomAndConvertNotebookOutput.ipynb"
   File downloadDicomAndConvertUsageMetrics = "downloadDicomAndConvertUsageMetrics.lz4"
   File downloadDicomAndConvertNiftiFiles = "downloadDicomAndConvertNiftiFiles.tar.lz4"
   File dcm2niix_errors = "dcm2niix_errors.csv"
 }
}

#Task Definitions
task inference {
 input {
   #Just like the workflow inputs, any new inputs entered here but not hardcoded will appear in the UI as required fields
   #And the hardcoded inputs will appear as optional to override the values entered here
   # Command parameters
    File inferenceTotalSegmentatorNotebook 
    String inferenceTotalSegmentatorDocker 
    Int inferenceTotalSegmentatorPreemptibleTries 
    Int inferenceTotalSegmentatorCpus 
    Int inferenceTotalSegmentatorRAM 
    String inferenceTotalSegmentatorZones 

    String inferenceTotalSegmentatorGpuType

    File NiftiFiles 

 }

 command {
   set -e
   papermill ~{inferenceTotalSegmentatorNotebook} inferenceOutputJupyterNotebook.ipynb
 }
 #Run time attributes:
 runtime {
   docker: inferenceTotalSegmentatorDocker
   cpu: inferenceTotalSegmentatorCpus
   #cpuPlatform: downloadAndConvertCpuFamily
   zones: inferenceTotalSegmentatorZones
   memory: inferenceTotalSegmentatorRAM + " GB"
   disks: "local-disk 50 SSD"  #ToDo: Dynamically calculate disk space using the no of bytes of yaml file size. 64 characters is the max size I found in a seriesInstanceUID
   preemptible: inferenceTotalSegmentatorPreemptibleTries
   maxRetries: 2
   gpuType: inferenceTotalSegmentatorGpuType
   gpuCount: 1
 }
  
 output {
   File inferenceOutputJupyterNotebook = "inferenceOutputJupyterNotebook.ipynb"
   File inferenceZipFile = "inferenceNiftiFiles.tar.lz4"
   File inferenceUsageMetrics = "inferenceUsageMetrics.lz4"
   #File inferenceMetaData = "inferencemetaData.zip"
 }
}

#Task Definitions
task itkimage2segimage {
 input {
   #Just like the workflow inputs, any new inputs entered here but not hardcoded will appear in the UI as required fields
   #And the hardcoded inputs will appear as optional to override the values entered here
    #File yamlParameters
    File seriesInstanceS5cmdUrls
    File itkimage2segimageNotebook 
    String itkimage2segimageDocker
    Int itkimage2segimagePreemptibleTries 
    Int itkimage2segimageCpus 
    Int itkimage2segimageRAM 
    String itkimage2segimageZones 
    String itkimage2segimageCpuFamily

    File inferenceZipFile
 }
 command {
   set -e
   papermill -p csvFilePath ~{seriesInstanceS5cmdUrls} ~{itkimage2segimageNotebook} itkimage2segimageOutputJupyterNotebook.ipynb || (>&2 echo "Killed" && exit 1)
 }

 #Run time attributes:
 runtime {
   docker: itkimage2segimageDocker
   cpu: itkimage2segimageCpus
   cpuPlatform: itkimage2segimageCpuFamily
   zones: itkimage2segimageZones
   memory: itkimage2segimageRAM + " GB"
   disks: "local-disk 50 SSD"  #ToDo: Dynamically calculate disk space using the no of bytes of yaml file size. 64 characters is the max size I found in a seriesInstanceUID
   preemptible: itkimage2segimagePreemptibleTries
   maxRetries: 1
 }
 output {
   File itkimage2segimageOutputJupyterNotebook = "itkimage2segimageOutputJupyterNotebook.ipynb"
   File itkimage2segimageZipFile = "itkimage2segimageDICOMsegFiles.tar.lz4"
   File itkimage2segimageUsageMetrics = "itkimage2segimageUsageMetrics.lz4"
 }
}
