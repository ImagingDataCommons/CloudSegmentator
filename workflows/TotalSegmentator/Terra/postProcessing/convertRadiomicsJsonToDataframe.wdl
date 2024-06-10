version 1.0
#WORKFLOW DEFINITION
workflow radiomicsJsonConversion {
 input {
   #all the inputs entered here but not hardcoded will appear in the UI as required fields
   #And the hardcoded inputs will appear as optional to override the values entered here
   Array[File] rawJsonRadiomicsFiles

   #Docker Images for each task
   String docker_radiomicsJsonToDataFrame = "imagingdatacommons/convert_radiomics_features_json_to_df:feat-convert-raw-radiomics-to-dataframe"

   #Preemptible retries
   Int preemptibleTries_radiomicsJsonToDataFrame= 3

   #Compute CPU configuration
   Int cpus_radiomicsJsonToDataFrame = 4
   Int ram_radiomicsJsonToDataFrame = 16
   String cpuFamily_radiomicsJsonToDataFrame = 'AMD Rome' 
   
   #Compute Zones
   String zones_radiomicsJsonToDataFrame = "us-central1-a us-central1-b us-central1-c us-central1-f"

 }
 #calling Papermill Task with the inputs
 call radiomicsJsonToDataFrame{
   input:
    rawJsonRadiomicsFiles = rawJsonRadiomicsFiles,
    docker_radiomicsJsonToDataFrame = docker_radiomicsJsonToDataFrame,
    preemptibleTries_radiomicsJsonToDataFrame = preemptibleTries_radiomicsJsonToDataFrame,
    cpus_radiomicsJsonToDataFrame = cpus_radiomicsJsonToDataFrame,
    ram_radiomicsJsonToDataFrame = ram_radiomicsJsonToDataFrame,
    cpuFamily_radiomicsJsonToDataFrame = cpuFamily_radiomicsJsonToDataFrame, 
    zones_radiomicsJsonToDataFrame = zones_radiomicsJsonToDataFrame
}

 output {
  #output notebooks
  
   File outputNotebook_radiomicsJsonToDataFrame = radiomicsJsonToDataFrame.outputNotebook_radiomicsJsonToDataFrame
   File parquet_radiomicsJsonToDataFrame = radiomicsJsonToDataFrame.parquet_radiomicsJsonToDataFrame 
   File? conversion_Errors = radiomicsJsonToDataFrame.conversion_Errors
}
}
#Task Definitions
task radiomicsJsonToDataFrame{
 input {
   #Just like the workflow inputs, any new inputs entered here but not hardcoded will appear in the UI as required fields
   #And the hardcoded inputs will appear as optional to override the values entered here
    Array[File] rawJsonRadiomicsFiles
    #Docker Images for task
    String docker_radiomicsJsonToDataFrame
    #Preemptible retries
    Int preemptibleTries_radiomicsJsonToDataFrame
    #Compute CPU configuration
    Int cpus_radiomicsJsonToDataFrame
    Int ram_radiomicsJsonToDataFrame
    String cpuFamily_radiomicsJsonToDataFrame 
    #Compute Zones
    String zones_radiomicsJsonToDataFrame
 }
 command {
   wget https://raw.githubusercontent.com/vkt1414/CloudSegmentator/feat-convert-raw-radiomics-to-dataframe/workflows/TotalSegmentator/Notebooks/postProcessingRadiomicsJsonToDataFrame.ipynb
   
   set -o xtrace
   # For any command failures in the rest of this script, return the error.
   set -o pipefail
   set +o errexit
   
   papermill postProcessingRadiomicsJsonToDataFrame.ipynb outputNotebook_postProcessingRadiomicsJsonToDataFrame.ipynb -p rawJsonRadiomicsFiles ~{sep="," rawJsonRadiomicsFiles}
   
   set -o errexit
   exit $?
 }

 #Run time attributes:
 runtime {
   docker: docker_radiomicsJsonToDataFrame
   cpu: cpus_radiomicsJsonToDataFrame
   cpuPlatform: cpuFamily_radiomicsJsonToDataFrame
   zones: zones_radiomicsJsonToDataFrame
   memory: ram_radiomicsJsonToDataFrame + " GiB"
   disks: "local-disk 10 HDD" 
   preemptible: preemptibleTries_radiomicsJsonToDataFrame
   maxRetries: 1
 }
 output {
   File outputNotebook_radiomicsJsonToDataFrame = "outputNotebook_postProcessingRadiomicsJsonToDataFrame.ipynb"
   File parquet_radiomicsJsonToDataFrame  = "raw_radiomics.parquet"
   File? conversion_Errors = "error_file.txt"
 }
}
