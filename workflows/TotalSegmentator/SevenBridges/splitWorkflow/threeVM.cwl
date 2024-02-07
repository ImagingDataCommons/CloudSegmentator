---
class: Workflow
cwlVersion: v1.2
label: TotalSegmentatorThreeVmWorkflow
"$namespaces":
  sbg: https://sevenbridges.com
inputs:
- id: yamlListOfSeriesInstanceUIDs
  type: File
  sbg:x: 0
  sbg:y: 428
outputs:
- id: downloadDicomAndConvertUsageMetrics
  outputSource:
  - downloaddicomandconvert/downloadDicomAndConvertUsageMetrics
  type: File?
  sbg:x: 869.0360717773438
  sbg:y: 321
- id: downloadDicomAndConvertOutputJupyterNotebook
  outputSource:
  - downloaddicomandconvert/downloadDicomAndConvertOutputJupyterNotebook
  type: File?
  sbg:x: 869.0360717773438
  sbg:y: 428
- id: downloadDicomAndConvert_modality_errors
  outputSource:
  - downloaddicomandconvert/downloadDicomAndConvert_modality_errors
  type: File?
  sbg:x: 869.0360717773438
  sbg:y: 535
- id: dcm2niix_errors
  outputSource:
  - downloaddicomandconvert/dcm2niix_errors
  type: File?
  sbg:x: 869.0360717773438
  sbg:y: 642
- id: totalsegmentatorErrors
  outputSource:
  - inferencetotalsegmentator/totalsegmentatorErrors
  sbg:fileTypes: CSV
  type: File?
  sbg:x: 1352.885498046875
  sbg:y: 211.5
- id: inferenceUsageMetrics
  outputSource:
  - inferencetotalsegmentator/inferenceUsageMetrics
  sbg:fileTypes: LZ4
  type: File?
  sbg:x: 1352.885498046875
  sbg:y: 318.5
- id: inferenceOutputJupyterNotebook
  outputSource:
  - inferencetotalsegmentator/inferenceOutputJupyterNotebook
  sbg:fileTypes: IPYNB
  type: File?
  sbg:x: 1352.885498046875
  sbg:y: 425.5
- id: structuredReportsJSON
  outputSource:
  - dicomsegandradiomicssr/structuredReportsJSON
  sbg:fileTypes: LZ4
  type: File?
  sbg:x: 2162.428955078125
  sbg:y: 0
- id: structuredReportsDICOM
  outputSource:
  - dicomsegandradiomicssr/structuredReportsDICOM
  sbg:fileTypes: LZ4
  type: File?
  sbg:x: 2162.428955078125
  sbg:y: 107
- id: pyradiomicsRadiomicsFeatures
  outputSource:
  - dicomsegandradiomicssr/pyradiomicsRadiomicsFeatures
  sbg:fileTypes: LZ4
  type: File?
  sbg:x: 2162.428955078125
  sbg:y: 214
- id: dicomsegAndRadiomicsSR_UsageMetrics
  outputSource:
  - dicomsegandradiomicssr/dicomsegAndRadiomicsSR_UsageMetrics
  sbg:fileTypes: LZ4
  type: File?
  sbg:x: 2162.428955078125
  sbg:y: 321
- id: dicomsegAndRadiomicsSR_SRErrors
  outputSource:
  - dicomsegandradiomicssr/dicomsegAndRadiomicsSR_SRErrors
  sbg:fileTypes: TXT
  type: File?
  sbg:x: 2162.428955078125
  sbg:y: 428
- id: dicomsegAndRadiomicsSR_RadiomicsErrors
  outputSource:
  - dicomsegandradiomicssr/dicomsegAndRadiomicsSR_RadiomicsErrors
  sbg:fileTypes: TXT
  type: File?
  sbg:x: 2162.428955078125
  sbg:y: 535
- id: dicomsegAndRadiomicsSR_OutputJupyterNotebook
  outputSource:
  - dicomsegandradiomicssr/dicomsegAndRadiomicsSR_OutputJupyterNotebook
  sbg:fileTypes: IPYNB
  type: File?
  sbg:x: 2162.428955078125
  sbg:y: 642
- id: dicomsegAndRadiomicsSR_modality_errors
  outputSource:
  - dicomsegandradiomicssr/dicomsegAndRadiomicsSR_modality_errors
  sbg:fileTypes: TXT
  type: File?
  sbg:x: 2162.428955078125
  sbg:y: 749
- id: dicomsegAndRadiomicsSR_CompressedFiles
  outputSource:
  - dicomsegandradiomicssr/dicomsegAndRadiomicsSR_CompressedFiles
  sbg:fileTypes: LZ4
  type: File?
  sbg:x: 2162.428955078125
  sbg:y: 856
steps:
- id: downloaddicomandconvert
  in:
  - id: yamlListOfSeriesInstanceUIDs
    source: yamlListOfSeriesInstanceUIDs
  out:
  - id: downloadDicomAndConvertOutputJupyterNotebook
  - id: dcm2niix_errors
  - id: downloadDicomAndConvertNiftiFiles
  - id: downloadDicomAndConvertUsageMetrics
  - id: downloadDicomAndConvert_modality_errors
  run:
    class: CommandLineTool
    cwlVersion: v1.2
    "$namespaces":
      sbg: https://sevenbridges.com
    id: downloaddicomandconvert
    baseCommand:
    - wget
    - https://raw.githubusercontent.com/ImagingDataCommons/CloudSegmentator/v1.3.1/workflows/TotalSegmentator/Notebooks/downloadDicomAndConvertNotebook.ipynb
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
        position: 1
    outputs:
    - id: downloadDicomAndConvertOutputJupyterNotebook
      type: File?
      outputBinding:
        glob: downloadDicomAndConvertOutputJupyterNotebook.ipynb
    - id: dcm2niix_errors
      type: File?
      outputBinding:
        glob: dcm2niix_errors.csv
    - id: downloadDicomAndConvertNiftiFiles
      type: File?
      outputBinding:
        glob: downloadDicomAndConvertNiftiFiles.tar.lz4
    - id: downloadDicomAndConvertUsageMetrics
      type: File?
      outputBinding:
        glob: downloadDicomAndConvertUsageMetrics.lz4
    - id: downloadDicomAndConvert_modality_errors
      type: File?
      outputBinding:
        glob: modality_error_file.txt
    label: downloadDicomAndConvert
    arguments:
    - prefix: ''
      shellQuote: false
      position: 0
      valueFrom: downloadDicomAndConvertNotebook.ipynb
    - prefix: ''
      shellQuote: false
      position: 1
      valueFrom: downloadDicomAndConvertOutputJupyterNotebook.ipynb
    requirements:
    - class: ShellCommandRequirement
    - class: LoadListingRequirement
    - class: NetworkAccess
      networkAccess: true
    - class: DockerRequirement
      dockerPull: imagingdatacommons/download_convert
    - class: InlineJavascriptRequirement
    hints:
    - class: sbg:AWSInstanceType
      value: c5.large;ebs-gp2;10
  label: downloadDicomAndConvert
  hints:
  - class: sbg:AWSInstanceType
    value: c5.large;ebs-gp2;10
  sbg:x: 294.943115234375
  sbg:y: 400
- id: inferencetotalsegmentator
  in:
  - id: downloadDicomAndConvertNiftiFiles
    source: downloaddicomandconvert/downloadDicomAndConvertNiftiFiles
  out:
  - id: inferenceOutputJupyterNotebook
  - id: totalsegmentatorErrors
  - id: inferenceZipFile
  - id: inferenceUsageMetrics
  run:
    class: CommandLineTool
    cwlVersion: v1.2
    "$namespaces":
      sbg: https://sevenbridges.com
    id: inferencetotalsegmentator
    baseCommand:
    - wget
    - https://raw.githubusercontent.com/ImagingDataCommons/CloudSegmentator/v1.3.1/workflows/TotalSegmentator/Notebooks/inferenceTotalSegmentatorNotebook.ipynb
    - "&&"
    - set
    - "-e"
    - "&&"
    - papermill
    inputs:
    - id: downloadDicomAndConvertNiftiFiles
      type: File
      inputBinding:
        shellQuote: false
        position: 2
      sbg:fileTypes: LZ4
    outputs:
    - id: inferenceOutputJupyterNotebook
      type: File?
      outputBinding:
        glob: inferenceOutputJupyterNotebook.ipynb
      sbg:fileTypes: IPYNB
    - id: totalsegmentatorErrors
      type: File?
      outputBinding:
        glob: totalsegmentator_errors.txt
      sbg:fileTypes: CSV
    - id: inferenceZipFile
      type: File?
      outputBinding:
        glob: inferenceNiftiFiles.tar.lz4
      sbg:fileTypes: LZ4
    - id: inferenceUsageMetrics
      type: File?
      outputBinding:
        glob: inferenceUsageMetrics.lz4
      sbg:fileTypes: LZ4
    label: inferenceTotalSegmentator
    arguments:
    - prefix: "-p"
      shellQuote: false
      position: 1
      valueFrom: niftiFilePath
    - prefix: ''
      shellQuote: false
      position: 3
      valueFrom: inferenceTotalSegmentatorNotebook.ipynb
    - prefix: ''
      shellQuote: false
      position: 4
      valueFrom: inferenceOutputJupyterNotebook.ipynb
    requirements:
    - class: ShellCommandRequirement
    - class: LoadListingRequirement
    - class: DockerRequirement
      dockerPull: "imagingdatacommons/inference_totalseg:v1.3.1"
    - class: InlineJavascriptRequirement
    hints:
    - class: sbg:AWSInstanceType
      value: g4dn.xlarge;ebs-gp2;25
  label: inferenceTotalSegmentator
  hints:
  - class: sbg:AWSInstanceType
    value: g4dn.xlarge;ebs-gp2;25
  sbg:x: 869.0360717773438
  sbg:y: 193
- id: dicomsegandradiomicssr
  in:
  - id: downloadDicomAndConvertAndInferenceTotalSegmentatorZipFile
    source: inferencetotalsegmentator/inferenceZipFile
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
    id: dicomsegandradiomicssr
    baseCommand:
    - wget
    - https://raw.githubusercontent.com/ImagingDataCommons/CloudSegmentator/v1.3.1/workflows/TotalSegmentator/Notebooks/dicomsegAndRadiomicsSR_Notebook.ipynb
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
      dockerPull: "imagingdatacommons/dicom_seg_pyradiomics_sr:v1.3.1"
    - class: InlineJavascriptRequirement
    hints:
    - class: sbg:AWSInstanceType
      value: m5.xlarge;ebs-gp2;25
  label: dicomsegAndRadiomicsSR
  hints:
  - class: sbg:AWSInstanceType
    value: m5.xlarge;ebs-gp2;10
  sbg:x: 1352.885498046875
  sbg:y: 588.5
requirements:
- class: InlineJavascriptRequirement
- class: StepInputExpressionRequirement