---
class: Workflow
cwlVersion: v1.2
label: TotalSegmentatorTwoVmWorkflow
"$namespaces":
  sbg: https://sevenbridges.com
inputs:
- id: yamlListOfSeriesInstanceUIDs
  type: File
  sbg:x: 0
  sbg:y: 374.5
outputs:
- id: totalSegmentatorErrors
  outputSource:
  - downloadDicomAndConvertAndInferenceTotalSegmentator/totalSegmentatorErrors
  sbg:fileTypes: txt
  type: File?
  sbg:x: 1048.56103515625
  sbg:y: 51.000003814697266
- id: downloadDicomAndConvertAndInferenceTotalSegmentatorUsageMetrics
  outputSource:
  - downloadDicomAndConvertAndInferenceTotalSegmentator/downloadDicomAndConvertAndInferenceTotalSegmentatorUsageMetrics
  sbg:fileTypes: lz4
  type: File?
  sbg:x: 1048.56103515625
  sbg:y: 158
- id: downloadDicomAndConvertAndInferenceTotalSegmentatorOutputJupyterNotebook
  outputSource:
  - downloadDicomAndConvertAndInferenceTotalSegmentator/downloadDicomAndConvertAndInferenceTotalSegmentatorOutputJupyterNotebook
  sbg:fileTypes: IPYNB
  type: File?
  sbg:x: 1048.56103515625
  sbg:y: 265
- id: downloadDicomAndConvertAndInferenceTotalSegmentator_modality_errors
  outputSource:
  - downloadDicomAndConvertAndInferenceTotalSegmentator/downloadDicomAndConvertAndInferenceTotalSegmentator_modality_errors
  sbg:fileTypes: TXT
  type: File?
  sbg:x: 1048.56103515625
  sbg:y: 372
- id: dcm2niixErrors
  outputSource:
  - downloadDicomAndConvertAndInferenceTotalSegmentator/dcm2niixErrors
  sbg:fileTypes: txt
  type: File?
  sbg:x: 1048.56103515625
  sbg:y: 698
- id: structuredReportsJSON
  outputSource:
  - dicomsegandradiomicssr/structuredReportsJSON
  sbg:fileTypes: LZ4
  type: File?
  sbg:x: 1858.1044921875
  sbg:y: 0
- id: structuredReportsDICOM
  outputSource:
  - dicomsegandradiomicssr/structuredReportsDICOM
  sbg:fileTypes: LZ4
  type: File?
  sbg:x: 1858.1044921875
  sbg:y: 107
- id: pyradiomicsRadiomicsFeatures
  outputSource:
  - dicomsegandradiomicssr/pyradiomicsRadiomicsFeatures
  sbg:fileTypes: LZ4
  type: File?
  sbg:x: 1858.1044921875
  sbg:y: 214
- id: dicomsegAndRadiomicsSR_UsageMetrics
  outputSource:
  - dicomsegandradiomicssr/dicomsegAndRadiomicsSR_UsageMetrics
  sbg:fileTypes: LZ4
  type: File?
  sbg:x: 1858.1044921875
  sbg:y: 321
- id: dicomsegAndRadiomicsSR_SRErrors
  outputSource:
  - dicomsegandradiomicssr/dicomsegAndRadiomicsSR_SRErrors
  sbg:fileTypes: TXT
  type: File?
  sbg:x: 1858.1044921875
  sbg:y: 428
- id: dicomsegAndRadiomicsSR_RadiomicsErrors
  outputSource:
  - dicomsegandradiomicssr/dicomsegAndRadiomicsSR_RadiomicsErrors
  sbg:fileTypes: TXT
  type: File?
  sbg:x: 1858.1044921875
  sbg:y: 535
- id: dicomsegAndRadiomicsSR_modality_errors
  outputSource:
  - dicomsegandradiomicssr/dicomsegAndRadiomicsSR_modality_errors
  sbg:fileTypes: TXT
  type: File?
  sbg:x: 1858.1044921875
  sbg:y: 642
- id: dicomsegAndRadiomicsSR_CompressedFiles
  outputSource:
  - dicomsegandradiomicssr/dicomsegAndRadiomicsSR_CompressedFiles
  sbg:fileTypes: LZ4
  type: File?
  sbg:x: 1858.1044921875
  sbg:y: 749
steps:
- id: downloadDicomAndConvertAndInferenceTotalSegmentator
  in:
  - id: yamlListOfSeriesInstanceUIDs
    source: yamlListOfSeriesInstanceUIDs
  out:
  - id: downloadDicomAndConvertAndInferenceTotalSegmentatorOutputJupyterNotebook
  - id: dcm2niixErrors
  - id: totalSegmentatorErrors
  - id: downloadDicomAndConvertAndInferenceTotalSegmentatorZipFile
  - id: downloadDicomAndConvertAndInferenceTotalSegmentatorUsageMetrics
  - id: downloadDicomAndConvertAndInferenceTotalSegmentator_modality_errors
  run:
    class: CommandLineTool
    cwlVersion: v1.2
    "$namespaces":
      sbg: https://sevenbridges.com
    id: downloadDicomAndConvertAndInferenceTotalSegmentator
    baseCommand:
    - wget
    - https://raw.githubusercontent.com/ImagingDataCommons/CloudSegmentator/v1.3.0/workflows/TotalSegmentator/Notebooks/downloadDicomAndConvertAndInferenceTotalSegmentatorNotebook.ipynb
    - "&&"
    - set
    - "-e"
    - "&&"
    - papermill
    inputs:
    - id: yamlListOfSeriesInstanceUIDs
      type: File
      inputBinding:
        prefix: "-f"
        shellQuote: false
        position: 3
    outputs:
    - id: downloadDicomAndConvertAndInferenceTotalSegmentatorOutputJupyterNotebook
      type: File?
      outputBinding:
        glob: downloadDicomAndConvertAndInferenceTotalSegmentatorOutputJupyterNotebook.ipynb
      sbg:fileTypes: IPYNB
    - id: dcm2niixErrors
      type: File?
      outputBinding:
        glob: error_file.txt
      sbg:fileTypes: txt
    - id: totalSegmentatorErrors
      type: File?
      outputBinding:
        glob: totalsegmentator_errors.txt
      sbg:fileTypes: txt
    - id: downloadDicomAndConvertAndInferenceTotalSegmentatorZipFile
      type: File?
      outputBinding:
        glob: inferenceNiftiFiles.tar.lz4
      sbg:fileTypes: LZ4
    - id: downloadDicomAndConvertAndInferenceTotalSegmentatorUsageMetrics
      type: File?
      outputBinding:
        glob: inferenceUsageMetrics.lz4
      sbg:fileTypes: lz4
    - id: downloadDicomAndConvertAndInferenceTotalSegmentator_modality_errors
      type: File?
      outputBinding:
        glob: modality_error_file.txt
      sbg:fileTypes: TXT
    label: downloadDicomAndConvertAndInferenceTotalSegmentator
    arguments:
    - prefix: ''
      shellQuote: false
      position: 1
      valueFrom: downloadDicomAndConvertAndInferenceTotalSegmentatorOutputJupyterNotebook.ipynb
    - prefix: ''
      shellQuote: false
      position: 0
      valueFrom: downloadDicomAndConvertAndInferenceTotalSegmentatorNotebook.ipynb
    requirements:
    - class: ShellCommandRequirement
    - class: LoadListingRequirement
    - class: DockerRequirement
      dockerPull: "imagingdatacommons/download_convert_inference_totalseg:v1.3.0"
    - class: InlineJavascriptRequirement
    hints:
    - class: sbg:AWSInstanceType
      value: g4dn.xlarge;ebs-gp2;25
  label: downloadDicomAndConvertAndInferenceTotalSegmentator
  sbg:x: 294.9430847167969
  sbg:y: 339.5
- id: dicomsegandradiomicssr
  in:
  - id: downloadDicomAndConvertAndInferenceTotalSegmentatorZipFile
    source: downloadDicomAndConvertAndInferenceTotalSegmentator/downloadDicomAndConvertAndInferenceTotalSegmentatorZipFile
  out:
  - id: dicomsegAndRadiomicsSR_OutputJupyterNotebook
  - id: dicomsegAndRadiomicsSR_CompressedFiles
  - id: pyradiomicsRadiomicsFeatures
  - id: structuredReportsDICOM
  - id: structuredReportsJSON
  - id: dicomsegAndRadiomicsSR_UsageMetrics
  - id: dicomsegAndRadiomicsSR_RadiomicsErrors
  - id: dicomsegAndRadiomicsSR_SRErrors
  - id: dicomsegAndRadiomicsSR_modality_errors
  run:
    class: CommandLineTool
    cwlVersion: v1.2
    "$namespaces":
      sbg: https://sevenbridges.com
    id: vamsikrishna14/test/dicomsegandradiomicssr/1
    baseCommand:
    - wget
    - https://raw.githubusercontent.com/ImagingDataCommons/CloudSegmentator/v1.3.0/workflows/TotalSegmentator/Notebooks/dicomsegAndRadiomicsSR_Notebook.ipynb
    - "&&"
    - set
    - "-e"
    - "&&"
    - papermill
    inputs:
    - id: downloadDicomAndConvertAndInferenceTotalSegmentatorZipFile
      type: File
      inputBinding:
        shellQuote: true
        position: 2
      sbg:fileTypes: LZ4
    outputs:
    - id: dicomsegAndRadiomicsSR_OutputJupyterNotebook
      type: File?
      outputBinding:
        glob: dicomsegAndRadiomicsSR_OutputJupyterNotebook.ipynb
      sbg:fileTypes: IPYNB
    - id: dicomsegAndRadiomicsSR_CompressedFiles
      type: File?
      outputBinding:
        glob: dicomsegAndRadiomicsSR_DICOMsegFiles.tar.lz4
      sbg:fileTypes: LZ4
    - id: pyradiomicsRadiomicsFeatures
      type: File?
      outputBinding:
        glob: pyradiomicsRadiomicsFeatures.tar.lz4
      sbg:fileTypes: LZ4
    - id: structuredReportsDICOM
      type: File?
      outputBinding:
        glob: structuredReportsDICOM.tar.lz4
      sbg:fileTypes: LZ4
    - id: structuredReportsJSON
      type: File?
      outputBinding:
        glob: structuredReportsJSON.tar.lz4
      sbg:fileTypes: LZ4
    - id: dicomsegAndRadiomicsSR_UsageMetrics
      type: File?
      outputBinding:
        glob: dicomsegAndRadiomicsSR_UsageMetrics.lz4
      sbg:fileTypes: LZ4
    - id: dicomsegAndRadiomicsSR_RadiomicsErrors
      type: File?
      outputBinding:
        glob: radiomics_error_file.txt
      sbg:fileTypes: TXT
    - id: dicomsegAndRadiomicsSR_SRErrors
      type: File?
      outputBinding:
        glob: sr_error_file.txt
      sbg:fileTypes: TXT
    - id: dicomsegAndRadiomicsSR_modality_errors
      type: File?
      outputBinding:
        glob: modality_error_file.txt
      sbg:fileTypes: TXT
    label: dicomsegAndRadiomicsSR
    arguments:
    - prefix: "-p"
      shellQuote: false
      position: 1
      valueFrom: inferenceNiftiFilePath
    - prefix: ''
      shellQuote: false
      position: 3
      valueFrom: dicomsegAndRadiomicsSR_Notebook.ipynb
    - prefix: ''
      shellQuote: false
      position: 4
      valueFrom: dicomsegAndRadiomicsSR_OutputJupyterNotebook.ipynb
    requirements:
    - class: ShellCommandRequirement
    - class: LoadListingRequirement
    - class: DockerRequirement
      dockerPull: "imagingdatacommons/dicom_seg_pyradiomics_sr:v1.3.0"
    - class: InlineJavascriptRequirement
    hints:
    - class: sbg:AWSInstanceType
      value: m5.xlarge;ebs-gp2;25
  label: dicomsegAndRadiomicsSR
  sbg:x: 1048.56103515625
  sbg:y: 535
requirements:
- class: InlineJavascriptRequirement
- class: StepInputExpressionRequirement