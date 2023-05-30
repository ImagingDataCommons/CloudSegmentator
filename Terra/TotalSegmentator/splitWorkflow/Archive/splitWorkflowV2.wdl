version 1.0
#WORKFLOW DEFINITION
workflow TotalSegmentator {
 input {
   #all the inputs entered here but not hardcoded will appear in the UI as required fields
   #And the hardcoded inputs will appear as optional to override the values entered here
   #File yamlParameters
   File seriesInstanceS5cmdUrls
   
   #Parameters
   String dicomToNiftiConverterTool

   #Docker Images for each task
   String downloadDicomAndConvertAndInferenceTotalSegmentatorDocker = "vamsithiriveedhi/totalsegmentator:task1and2_v3"
   String itkimage2segimageDocker = "vamsithiriveedhi/totalsegmentator:task3_v2"

   #Preemptible retries

   Int downloadDicomAndConvertAndInferenceTotalSegmentatorPreemptibleTries = 3
   Int itkimage2segimagePreemptibleTries = 3

   #Compute CPU configuration
   Int downloadDicomAndConvertAndInferenceTotalSegmentatorCpus = 2
   Int itkimage2segimageCpus = 2

   Int downloadDicomAndConvertAndInferenceTotalSegmentatorRAM = 13
   Int itkimage2segimageRAM = 2

   #String downloadDicomAndConvertAndInferenceTotalSegmentatorCpuFamily = 'Intel Cascade Lake' #Because GPUs are available only with N1 family
   String itkimage2segimageCpuFamily = 'AMD Rome'   

   String downloadDicomAndConvertAndInferenceTotalSegmentatorGpuType = 'nvidia-tesla-t4'

   String downloadDicomAndConvertAndInferenceTotalSegmentatorZones = "us-central1-a us-central1-b us-central1-c us-central1-f"
   String itkimage2segimageZones = "us-central1-a us-central1-b us-central1-c us-central1-f"
 }
 #calling Papermill Task with the inputs
 call downloadDicomAndConvertAndInferenceTotalSegmentator{
   input :
     seriesInstanceS5cmdUrls = seriesInstanceS5cmdUrls,
     dicomToNiftiConverterTool = dicomToNiftiConverterTool,
     downloadDicomAndConvertAndInferenceTotalSegmentatorDocker = downloadDicomAndConvertAndInferenceTotalSegmentatorDocker ,
     downloadDicomAndConvertAndInferenceTotalSegmentatorPreemptibleTries = downloadDicomAndConvertAndInferenceTotalSegmentatorPreemptibleTries ,
     downloadDicomAndConvertAndInferenceTotalSegmentatorCpus = downloadDicomAndConvertAndInferenceTotalSegmentatorCpus ,
     downloadDicomAndConvertAndInferenceTotalSegmentatorRAM = downloadDicomAndConvertAndInferenceTotalSegmentatorRAM ,
     downloadDicomAndConvertAndInferenceTotalSegmentatorZones = downloadDicomAndConvertAndInferenceTotalSegmentatorZones ,
     downloadDicomAndConvertAndInferenceTotalSegmentatorGpuType = downloadDicomAndConvertAndInferenceTotalSegmentatorGpuType,
 }
 call itkimage2segimage{
   input:
    seriesInstanceS5cmdUrls = seriesInstanceS5cmdUrls,
    itkimage2segimageDocker = itkimage2segimageDocker,
    itkimage2segimagePreemptibleTries = itkimage2segimagePreemptibleTries,
    itkimage2segimageCpus = itkimage2segimageCpus,
    itkimage2segimageRAM = itkimage2segimageRAM,
    itkimage2segimageZones = itkimage2segimageZones,
    itkimage2segimageCpuFamily = itkimage2segimageCpuFamily,
    #Nifti files converted in the first step are provided as input here
    inferenceZipFile = downloadDicomAndConvertAndInferenceTotalSegmentator.downloadDicomAndConvertAndInferenceTotalSegmentatorZipFile
}


 output {
  #output notebooks
  
   File downloadDicomAndConvertAndInferenceTotalSegmentatorOutputNotebook = downloadDicomAndConvertAndInferenceTotalSegmentator.downloadDicomAndConvertAndInferenceTotalSegmentatorOutputJupyterNotebook
   File itkimage2segimageOutputNotebook = itkimage2segimage.itkimage2segimageOutputJupyterNotebook   


   File downloadDicomAndConvertAndInferenceTotalSegmentatorUsageMetrics= downloadDicomAndConvertAndInferenceTotalSegmentator.downloadDicomAndConvertAndInferenceTotalSegmentatorUsageMetrics
   File itkimage2segimageUsageMetrics  = itkimage2segimage.itkimage2segimageUsageMetrics

   File itkimage2segimageZipFile = itkimage2segimage.itkimage2segimageZipFile
   
   File? dcm2niixErrors = downloadDicomAndConvertAndInferenceTotalSegmentator.dcm2niixErrors
   File? totalsegmentatorErrors = downloadDicomAndConvertAndInferenceTotalSegmentator.totalsegmentatorErrors
   File? itkimage2segimageErrors = itkimage2segimage.itkimage2segimageErrors
   File inferenceMetaData = downloadDicomAndConvertAndInferenceTotalSegmentator.downloadDicomAndConvertAndInferenceTotalSegmentatorMetaData
 }

}

#Task Definitions
task downloadDicomAndConvertAndInferenceTotalSegmentator{
 input {
   #Just like the workflow inputs, any new inputs entered here but not hardcoded will appear in the UI as required fields
   #And the hardcoded inputs will appear as optional to override the values entered here
   # Command parameters
    File seriesInstanceS5cmdUrls 
    String dicomToNiftiConverterTool
    String downloadDicomAndConvertAndInferenceTotalSegmentatorDocker 
    Int downloadDicomAndConvertAndInferenceTotalSegmentatorPreemptibleTries 
    Int downloadDicomAndConvertAndInferenceTotalSegmentatorCpus 
    Int downloadDicomAndConvertAndInferenceTotalSegmentatorRAM 
    String downloadDicomAndConvertAndInferenceTotalSegmentatorZones 

    String downloadDicomAndConvertAndInferenceTotalSegmentatorGpuType 


 }

 command {
   wget https://raw.githubusercontent.com/vkt1414/Cloud-Resources-Workflows/main/Notebooks/Totalsegmentator/downloadDicomAndConvertAndInferenceTotalSegmentatorNotebook.ipynb
   set -e
   papermill -p converterType ~{dicomToNiftiConverterTool}  -p csvFilePath ~{seriesInstanceS5cmdUrls} downloadDicomAndConvertAndInferenceTotalSegmentatorNotebook.ipynb downloadDicomAndConvertAndInferenceTotalSegmentatorOutputJupyterNotebook.ipynb
 }
 #Run time attributes:
 runtime {
   docker: downloadDicomAndConvertAndInferenceTotalSegmentatorDocker 
   cpu: downloadDicomAndConvertAndInferenceTotalSegmentatorCpus 
   #cpuPlatform: downloadDicomAndConvertAndInferenceTotalSegmentatorCpuFamily 
   zones: downloadDicomAndConvertAndInferenceTotalSegmentatorZones 
   memory: downloadDicomAndConvertAndInferenceTotalSegmentatorRAM + " GiB"
   disks: "local-disk 50 SSD"  #ToDo: Dynamically calculate disk space using the no of bytes of yaml file size. 64 characters is the max size I found in a seriesInstanceUID
   preemptible: downloadDicomAndConvertAndInferenceTotalSegmentatorPreemptibleTries 
   maxRetries: 1
   gpuType: downloadDicomAndConvertAndInferenceTotalSegmentatorGpuType 
   gpuCount: 1
 }
  
 output {
   File downloadDicomAndConvertAndInferenceTotalSegmentatorOutputJupyterNotebook= "downloadDicomAndConvertAndInferenceTotalSegmentatorOutputJupyterNotebook.ipynb"
   File downloadDicomAndConvertAndInferenceTotalSegmentatorZipFile = "inferenceNiftiFiles.tar.lz4"
   File downloadDicomAndConvertAndInferenceTotalSegmentatorUsageMetrics= "inferenceUsageMetrics.lz4"
   File downloadDicomAndConvertAndInferenceTotalSegmentatorMetaData = "inferenceMetaData.tar.lz4"
   File? dcm2niixErrors = "error_file.txt"
   File? totalsegmentatorErrors = "totalsegmentator_errors.txt"
 }
}

#Task Definitions
task itkimage2segimage {
 input {
   #Just like the workflow inputs, any new inputs entered here but not hardcoded will appear in the UI as required fields
   #And the hardcoded inputs will appear as optional to override the values entered here
    File seriesInstanceS5cmdUrls 
    String itkimage2segimageDocker
    Int itkimage2segimagePreemptibleTries 
    Int itkimage2segimageCpus 
    Int itkimage2segimageRAM 
    String itkimage2segimageZones 
    String itkimage2segimageCpuFamily

    File inferenceZipFile
 }
 command {
   wget https://raw.githubusercontent.com/vkt1414/Cloud-Resources-Workflows/main/Notebooks/Totalsegmentator/itkimage2segimageNotebook.ipynb
   set -e
   papermill -p csvFilePath ~{seriesInstanceS5cmdUrls} -p inferenceNiftiFilePath ~{inferenceZipFile}  itkimage2segimageNotebook.ipynb itkimage2segimageOutputJupyterNotebook.ipynb 
 }

 #Run time attributes:
 runtime {
   docker: itkimage2segimageDocker
   cpu: itkimage2segimageCpus
   cpuPlatform: itkimage2segimageCpuFamily
   zones: itkimage2segimageZones
   memory: itkimage2segimageRAM + " GiB"
   disks: "local-disk 10 SSD"  #ToDo: Dynamically calculate disk space using the no of bytes of yaml file size. 64 characters is the max size I found in a seriesInstanceUID
   preemptible: itkimage2segimagePreemptibleTries
   maxRetries: 1
 }
 output {
   File itkimage2segimageOutputJupyterNotebook = "itkimage2segimageOutputJupyterNotebook.ipynb"
   File itkimage2segimageZipFile = "itkimage2segimageDICOMsegFiles.tar.lz4"
   File itkimage2segimageUsageMetrics = "itkimage2segimageUsageMetrics.lz4"
   File? itkimage2segimageErrors = "itkimage2segimage_error_file.txt"
 }
}
