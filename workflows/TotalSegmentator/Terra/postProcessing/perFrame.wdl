version 1.0
#WORKFLOW DEFINITION
workflow PerFrameFunctionalGroupsSequence {
 input {
   #all the inputs entered here but not hardcoded will appear in the UI as required fields
   #And the hardcoded inputs will appear as optional to override the values entered here
   File segFilesCsv
   File jsonServiceAccountFile

   #Docker Images for each task
   String docker_PerFrameFunctionalGroupsSequence = "imagingdatacommons/per_frame_functional_group_sequence:main"

   #Preemptible retries
   Int preemptibleTries_PerFrameFunctionalGroupsSequence = 3

   #Compute CPU configuration
   Int cpus_PerFrameFunctionalGroupsSequence = 4
   Int ram_PerFrameFunctionalGroupsSequence = 16
   String cpuFamily_PerFrameFunctionalGroupsSequence = 'AMD Rome' 
   
   #Compute Zones
   String zones_PerFrameFunctionalGroupsSequence = "us-central1-a us-central1-b us-central1-c us-central1-f"

 }
 #calling Papermill Task with the inputs
 call PerFrameFunctionalGroupsSequence{
   input:
    segFilesCsv = segFilesCsv,
    jsonServiceAccountFile = jsonServiceAccountFile,
    docker_PerFrameFunctionalGroupsSequence = docker_PerFrameFunctionalGroupsSequence,
    preemptibleTries_PerFrameFunctionalGroupsSequence = preemptibleTries_PerFrameFunctionalGroupsSequence,
    cpus_PerFrameFunctionalGroupsSequence = cpus_PerFrameFunctionalGroupsSequence,
    ram_PerFrameFunctionalGroupsSequence = ram_PerFrameFunctionalGroupsSequence,
    cpuFamily_PerFrameFunctionalGroupsSequence = cpuFamily_PerFrameFunctionalGroupsSequence, 
    zones_PerFrameFunctionalGroupsSequence = zones_PerFrameFunctionalGroupsSequence
}


 output {
  #output notebooks
  
   File outputNotebook_postProcessingExtractPerframe = PerFrameFunctionalGroupsSequence.outputNotebook_postProcessingExtractPerframe
   File csvFile_PerFrameFunctionalGroupsSequence = PerFrameFunctionalGroupsSequence.csvFile_PerFrameFunctionalGroupsSequence 
 }

}
#Task Definitions
task PerFrameFunctionalGroupsSequence{
 input {
   #Just like the workflow inputs, any new inputs entered here but not hardcoded will appear in the UI as required fields
   #And the hardcoded inputs will appear as optional to override the values entered here
    File segFilesCsv 
    File jsonServiceAccountFile
    #Docker Images for task
    String docker_PerFrameFunctionalGroupsSequence
    #Preemptible retries
    Int preemptibleTries_PerFrameFunctionalGroupsSequence
    #Compute CPU configuration
    Int cpus_PerFrameFunctionalGroupsSequence
    Int ram_PerFrameFunctionalGroupsSequence
    String cpuFamily_PerFrameFunctionalGroupsSequence 
    #Compute Zones
    String zones_PerFrameFunctionalGroupsSequence
 }
 command {
   wget https://raw.githubusercontent.com/ImagingDataCommons/CloudSegmentator/main/workflows/Totalsegmentator/Notebooks/postProcessingExtractPerframe.ipynb
   
   set -o xtrace
   # For any command failures in the rest of this script, return the error.
   set -o pipefail
   set +o errexit
   
   papermill -p segFilesCsv ~{segFilesCsv} -p jsonServiceAccountFile ~{jsonServiceAccountFile}  postProcessingExtractPerframe.ipynb outputNotebook_postProcessingExtractPerframe.ipynb
   
   set -o errexit
   exit $?
 }

 #Run time attributes:
 runtime {
   docker: docker_PerFrameFunctionalGroupsSequence
   cpu: cpus_PerFrameFunctionalGroupsSequence
   cpuPlatform: cpuFamily_PerFrameFunctionalGroupsSequence
   zones: zones_PerFrameFunctionalGroupsSequence
   memory: ram_PerFrameFunctionalGroupsSequence + " GiB"
   disks: "local-disk 10 HDD" 
   preemptible: preemptibleTries_PerFrameFunctionalGroupsSequence
   maxRetries: 3
 }
 output {
   File outputNotebook_postProcessingExtractPerframe = "outputNotebook_postProcessingExtractPerframe.ipynb"
   File csvFile_PerFrameFunctionalGroupsSequence  = "perFrameFunctionalGroupSequence.csv.lz4"
   
 }
}
