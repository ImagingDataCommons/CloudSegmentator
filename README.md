# Welcome to the CloudSegmentator repository. 

## This repository contains the complete source code used to develop workflows for analysis on FireCloud (Terra) or Seven Bridges Cancer Genomics Cloud.

### What is this repo about?
- There is more than 40TB of publicly available data on Imaging Data Commons (IDC) and even more on The Cancer Imaging Archive (TCIA)
- Much of this data is not annotated due to various reasons such as lack of access to Radiologists or the data may be too large to annotate all by humans
- This is where AI and deep learning models come into play to help annotate data. 
- For instance, one of the most prominent segmentation models, TotalSegmentator, can segment up to 104 body parts (v1)
- Most of the AI models leverage GPUs to perform inference quickly, which proves to be instrumental when dealing with TBs of data. 
- However, this may also mean investing in expensive GPUs or blocking the shared resources on-premises clusters
- Every research team may have their own workflow depending on the research question
- Hundreds of publicly available workflows already exist to process BigData, for example, massively parallel sequencing data
- Yet, as of writing this on 2024-01-03, not a single workflow related to radiology is on dockstore
- That's why we aim to showcase the capabilities of Terra and Seven Bridges Cancer Genomics Cloud using the TotalSegmentator segmentation model as an example to process all 3D reconstructable CT volumes on ImagingDataCommons (more than 10TB!) in a matter of few days


### Background
- FireCloud and Seven Bridges Cancer Genomics Cloud were both developed in partnership with National Cancer Institute (NCI) 
  - They are entities of Cloud Resources Division of Cancer Research Data Commons. Read more about NCI Cloud Resources [here](https://datascience.cancer.gov/data-commons/cloud-resources)
- Developed for running compute jobs on cloud computing resources for biomedical researchers
- Abstracts the inticracries of cloud platforms, meaning you do not need to be a cloud engineer with expertise to get started
- Uses open source maintained languages Workflow Description Language (WDL) and Common Workflow Language (CWL)
    - One can run these workflows not only on the cloud but on computing platform with minimal changes 
- In short, FireCloud and Seven Bridges Cancer Genomics Cloud can run reproducible and shareable workflows that can process BigData on Cloud

- And we use Dockstore as it is a place where workflows are made avaialable to public by researchers
- Users can import these workflows into a platform of their choice


<details close>
<summary><b><h2>More on FireCloud and Seven Bridges Cancer Genomics Cloud</h2></b></summary>

- FireCloud
    - is powered by Terra, a platform developed in conjunction with Microsoft, Verily and the Broad Institute
    - can run up to **3000** workflows and up to **28,800** jobs concurrently!
    - (we will refer FireCloud as Terra from this point on) 

- Seven Bridges Cancer Genomics Cloud (now Velsera) was developed by the partnership of NCI and SB
    - can run up to **80** jobs concurrently and this limit can be increased by reaching out to SB-CGC tech support
    - (we will refer Seven Bridges Cancer Genomics Cloud as SB-CGC from this point on)

</details>

## How do I get started?
- As with any new tool, there are few prerequisites and the following concepts need to be understood
- While you do not need to know everything listed here, doing so would make you understand how the workflows work

- ### Dockstore

    - [What is Dockstore](https://docs.dockstore.org/en/stable/dockstore-introduction.html) 

    - [Introduction](https://docs.dockstore.org/en/stable/getting-started/getting-started.html)

        - Getting started with docker, CWL, and WDL

    - [Optional: Video Tutorials](https://docs.dockstore.org/en/stable/videos.html) 

- ### Terra

    - [Getting Started on Terra](https://support.terra.bio/hc/en-us/categories/360005881492-Getting-Started)

        - All Overview articles except 'Interactive analysis apps: Galaxy, Jupyter notebooks and RStudio'
        - All Registration and setup articles 
        - Data Tables and Workflows Quickstart guides

- ### SB-CGC

    - [Quick start guide to SB-CGC ](https://docs.cancergenomicscloud.org/page/uncontrolled-data-quickstart-guide)

    - [More comprehensive Getting Started guide](https://docs.cancergenomicscloud.org/docs/before-you-start)

        - All articles in Get Started and Tutorials

- ## Importing workflows in to Terra

    - This sections assumes that you are now familiar with Terra, WDL and you or your team admin has access to a google cloud billing account
    - Find a WDL  workflow from our [collection on dockstore](https://dockstore.org/organizations/ImagingDataCommons/collections/CloudSegmentator)
    - For the purposes of this demo, pick [TotalSegmentatortwoVmWorkflowOnTerra:main](https://dockstore.org/workflows/github.com/ImagingDataCommons/CloudSegmentator/TotalSegmentatortwoVmWorkflowOnTerra:main)
    - Find `Launch with` on the top right and pick a plaform of choice to import the workflow
    - For the purposes of this demo, we pick Terra
    - Name the workflow or go with the default name
    - Pick or create a new workspace to import the workflow 

- ## Running workflows on Terra

    - Assuming that you were able to import the workflow in the above step, this step aims to show how to start running one on Terra
    - One of the most useful features of Terra is that it uses a data table model for launching thousands of workflows at a time
    - In addition, the data table helps data management well. It will be populated with links to the outputs generated in the workflow as they become available
    - Find a sample data table to import [here](https://github.com/ImagingDataCommons/CloudSegmentator/tree/main/workflows/TotalSegmentator/Docs/sampleManifests)
    - Find `DATA` tab in the blade and import the datatable
    - Next, find the imported workflow in `WORKFLOWS` tab
    - Choose the option `Run workflow(s) with inputs defined by data table`
    - In `Step 1` `Select root entity type`, select the data table imported above. The entity id begins with `twoVM_`
    - In `Step 2` `SELECT DATA`, select any one row for now
    - Next, under `INPUTS` tab, provide the reference for `yamlListOfSeriesInstanceUIDs` variable. It should appear as `this.SeriesInstanceUIDs`
    - All other inputs are optional, so we will leave them empty for now
    - Next, under `OUTPUTS` tab, select `Use defaults` for the `Attribute` column
    - The `RUN ANALYSIS` button should now be available, and you can click to start the workflow

- ## Importing workflows in to SB-CGC

    - This sections assumes that you are now familiar with SB-CGC, CWL and you or your team admin has access to atleast pilot funds
    - Find a CWL  workflow from our [collection on dockstore](https://dockstore.org/organizations/ImagingDataCommons/collections/CloudSegmentator)
    - For the purposes of this demo, pick [TotalSegmentatortwoVmWorkflowOnTerra:main](https://dockstore.org/workflows/github.com/ImagingDataCommons/CloudSegmentator/TotalSegmentatortwoVmWorkflowOnSB-CGC:main)
    - Find `Launch with` on the top right and pick a plaform of choice to import the workflow
    - For the purposes of this demo, we pick `CGC`
    - Pick a project to import the workflow 

- ## Running workflows on SB-CGC   

    - Assuming that you were able to import the workflow in the above step, this step aims to show how to start running one on SB-CGC
    - Find the imported workflow from the `Apps` tab 
    - Click `Run`
    - Unlike Terra, SB-CGC does not use a data table model.
    - For the purposes of this demo, [download and provide this input file](!https://raw.githubusercontent.com/ImagingDataCommons/CloudSegmentator/main/workflows/TotalSegmentator/Docs/sampleManifests/batch_1.yaml)   to `yamlListOfSeriesInstanceUIDs`
    - Click `Run` on the top right to start the workflow