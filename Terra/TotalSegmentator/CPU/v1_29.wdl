version 1.0
#WORKFLOW DEFINITION
workflow TotalSegmentator {
 input {
   #all the inputs entered here but not hardcoded will appear in the UI as required fields
   #And the hardcoded inputs will appear as optional to override the values entered here
   File yaml_parameters
   File total_segmentator_jupyter_notebook
   String total_segmentator_nocuda_docker = "vamsithiriveedhi/totalsegmentator:nocuda"
   Int preemptible_tries = 3
   #Int machine_mem_size = 13
   #Int vcpus = 2
 }


 #calling Papermill Task with the inputs
 call Papermill{
   input:
	 yaml_parameters = yaml_parameters,
     total_segmentator_jupyter_notebook = total_segmentator_jupyter_notebook,
     docker_image = total_segmentator_nocuda_docker,
     preemptible_tries = preemptible_tries,
     #machine_mem_size = machine_mem_size,
     #vcpus = vcpus
 }
 #only DICOMSEG object and CT DICOM files in a zipfile and
 #Papermill command's output jupyter notebook are extracted as output
 output {
   File outputJupyterNotebook = Papermill.outputJupyterNotebook
   Array[File] outputZipFile = Papermill.outputZipFile
  
 }
}


#Task Definitions
task Papermill {
 input {
   #Just like the workflow inputs, any new inputs entered here but not hardcoded will appear in the UI as required fields
   #And the hardcoded inputs will appear as optional to override the values entered here
   # Command parameters
   File yaml_parameters
   File total_segmentator_jupyter_notebook



   # Runtime parameters
   #Int machine_mem_size
   #Int vcpus
   String docker_image
   Int preemptible_tries
 }


 command {
   set -e
   papermill -f ~{yaml_parameters}  ~{total_segmentator_jupyter_notebook} output.ipynb || (>&2 echo "Killed" && exit 1)
 }


 #Run time attributes:
 runtime {
   docker: docker_image
   #cpu: vcpus
   cpuPlatform: "AMD Milan"
   zones: "us-central1-a us-central1-b us-central1-c us-central1-f us-east1-b us-east1-c us-east1-d us-east5-a us-east5-b us-east5-c us-west1-a us-west1-b us-west1-c"
   #memory: machine_mem_size + " GB"
   disks: "local-disk 50 SSD"
   preemptible: preemptible_tries
   maxRetries: 1
 }
  
 output {
   File outputJupyterNotebook = "output.ipynb"
   Array[File] outputZipFile = glob("*.zip")
 }
}
