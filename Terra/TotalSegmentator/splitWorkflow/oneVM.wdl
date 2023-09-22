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
   String totalSegmentatorDocker = "imagingdatacommons/download_convert_inference_totalseg_radiomics" 

   #Preemptible retries
   Int totalSegmentatorPreemptibleTries = 3

   #Compute CPU configuration
   Int totalSegmentatorCpus = 2
   
   #Compute RAM configuration
   Int totalSegmentatorRAM = 13

   #String downloadDicomAndConvertAndInferenceTotalSegmentatorCpuFamily = 'Intel Cascade Lake' #Because GPUs are available only with N1 family
   #String dicomsegAndRadiomicsSR_CpuFamily = 'Intel Cascade Lake'   
   
   #Compute GPU model
   String totalSegmentatorGpuType = 'nvidia-tesla-t4'
   
   #Compute Datacenter Zones
   String totalSegmentatorZones = "us-west4-a us-west4-b europe-west2-a europe-west2-b asia-east1-a asia-east1-c australia-southeast1-a australia-southeast1-c asia-northeast1-a asia-northeast1-c"
   
 }
 #calling totalSegmentatorEndtoEnd Task with the inputs

 call totalSegmentatorEndToEnd{
   input:
    seriesInstanceS5cmdUrls = seriesInstanceS5cmdUrls,
    dicomToNiftiConverterTool = dicomToNiftiConverterTool,
    totalSegmentatorDocker = totalSegmentatorDocker,
    totalSegmentatorPreemptibleTries = totalSegmentatorPreemptibleTries,
    totalSegmentatorCpus = totalSegmentatorCpus,
    totalSegmentatorRAM = totalSegmentatorRAM,
    totalSegmentatorGpuType = totalSegmentatorGpuType,
    totalSegmentatorZones = totalSegmentatorZones
}


 output {
  #output notebooks
  
   File endToEndTotalSegmentatorOutputJupyterNotebook = totalSegmentatorEndToEnd.endToEndTotalSegmentatorOutputJupyterNotebook
   File dicomsegAndRadiomicsSR_CompressedFiles = totalSegmentatorEndToEnd.dicomsegAndRadiomicsSR_CompressedFiles
   File pyradiomicsRadiomicsFeatures = totalSegmentatorEndToEnd.pyradiomicsRadiomicsFeatures
   File structuredReportsDICOM = totalSegmentatorEndToEnd.structuredReportsDICOM
   File structuredReportsJSON = totalSegmentatorEndToEnd.structuredReportsJSON
   File endToEndTotalSegmentator_UsageMetrics = totalSegmentatorEndToEnd.endToEndTotalSegmentator_UsageMetrics


   File? dcm2niixErrors = totalSegmentatorEndToEnd.dcm2niixErrors
   File? totalsegmentatorErrors = totalSegmentatorEndToEnd.totalsegmentatorErrors
   File? dicomSegErrors = totalSegmentatorEndToEnd.dicomSegErrors
   File? dicomsegAndRadiomicsSR_RadiomicsErrors = totalSegmentatorEndToEnd.dicomsegAndRadiomicsSR_RadiomicsErrors
   File? dicomsegAndRadiomicsSR_SRErrors = totalSegmentatorEndToEnd.dicomsegAndRadiomicsSR_SRErrors
 }

}

#Task Definitions
task totalSegmentatorEndToEnd{
 input {
   #Just like the workflow inputs, any new inputs entered here but not hardcoded will appear in the UI as required fields
   #And the hardcoded inputs will appear as optional to override the values entered here
    File seriesInstanceS5cmdUrls
    String dicomToNiftiConverterTool 
    String totalSegmentatorDocker
    Int totalSegmentatorPreemptibleTries 
    Int totalSegmentatorCpus 
    Int totalSegmentatorRAM 
    String totalSegmentatorGpuType 
    String totalSegmentatorZones

 }
 command {
   wget https://raw.githubusercontent.com/ImagingDataCommons/Cloud-Resources-Workflows/main/Notebooks/Totalsegmentator/endToEndTotalSegmentatorNotebook.ipynb
   set -e
   papermill -p csvFilePath ~{seriesInstanceS5cmdUrls} -p converterType ~{dicomToNiftiConverterTool}  endToEndTotalSegmentatorNotebook.ipynb endToEndTotalSegmentatorOutputJupyterNotebook.ipynb || (>&2 echo "Killed" && exit 1)
 }

 #Run time attributes:
 runtime {
   docker: totalSegmentatorDocker
   cpu: totalSegmentatorCpus
   #cpuPlatform: dicomsegAndRadiomicsSR_CpuFamily
   gpuType: totalSegmentatorGpuType 
   gpuCount: 1
   zones: totalSegmentatorZones
   memory: totalSegmentatorRAM + " GiB"
   disks: "local-disk 10 HDD"  #ToDo: Dynamically calculate disk space using the no of bytes of yaml file size. 64 characters is the max size I found in a seriesInstanceUID
   preemptible: totalSegmentatorPreemptibleTries
   maxRetries: 3
 }
 output {
   File endToEndTotalSegmentatorOutputJupyterNotebook = "endToEndTotalSegmentatorOutputJupyterNotebook.ipynb"
   File dicomsegAndRadiomicsSR_CompressedFiles = "dicomsegAndRadiomicsSR_DICOMsegFiles.tar.lz4"
   File pyradiomicsRadiomicsFeatures = "pyradiomicsRadiomicsFeatures.tar.lz4"
   File structuredReportsDICOM = "structuredReportsDICOM.tar.lz4"
   File structuredReportsJSON = "structuredReportsJSON.tar.lz4"
   File endToEndTotalSegmentator_UsageMetrics = "endToEndTotalSegmentator_UsageMetrics.lz4"


   File? dcm2niixErrors = 'error_file.txt'
   File? totalsegmentatorErrors = "totalsegmentator_errors.txt"
   File? dicomSegErrors = "itkimage2segimage_error_file.txt"  
   File? dicomsegAndRadiomicsSR_RadiomicsErrors = "radiomics_error_file.txt" 
   File? dicomsegAndRadiomicsSR_SRErrors = "sr_error_file.txt"
   
 }
}
