---
class: Workflow
cwlVersion: v1.2
label: TotalSegmentatorThreeVmWorkflow
"$namespaces":
  sbg: https://sevenbridges.com
inputs:
- id: dicomToNiftiConverterTool
  type: string
  sbg:x: 0
  sbg:y: 428
- id: s5cmdUrls
  type: File
  sbg:x: 31.26104736328125
  sbg:y: 85.71949005126953
outputs:
- id: downloadDicomAndConvertUsageMetrics
  outputSource:
  - downloaddicomandconvert/downloadDicomAndConvertUsageMetrics
  sbg:fileTypes: LZ4
  type: File?
  sbg:x: 158.2618408203125
  sbg:y: -233.47225952148438
- id: downloadDicomAndConvertOutputJupyterNotebook
  outputSource:
  - downloaddicomandconvert/downloadDicomAndConvertOutputJupyterNotebook
  sbg:fileTypes: IPYNB
  type: File?
  sbg:x: 465.93634033203125
  sbg:y: -292.6493835449219
- id: dcm2niix_errors
  outputSource:
  - downloaddicomandconvert/dcm2niix_errors
  sbg:fileTypes: CSV
  type: File?
  sbg:x: 806.5172119140625
  sbg:y: 811.4134521484375
- id: totalsegmentatorErrors
  outputSource:
  - inferencetotalsegmentator/totalsegmentatorErrors
  sbg:fileTypes: CSV
  type: File?
  sbg:x: 1249.3201904296875
  sbg:y: -127.86664581298828
- id: inferenceUsageMetrics
  outputSource:
  - inferencetotalsegmentator/inferenceUsageMetrics
  sbg:fileTypes: LZ4
  type: File?
  sbg:x: 1033.7835693359375
  sbg:y: -290.6988525390625
- id: inferenceOutputJupyterNotebook
  outputSource:
  - inferencetotalsegmentator/inferenceOutputJupyterNotebook
  sbg:fileTypes: IPYNB
  type: File?
  sbg:x: 915.3206176757812
  sbg:y: -231.41307067871094
- id: structuredReportsJSON
  outputSource:
  - dicomsegandradiomicssr/structuredReportsJSON
  sbg:fileTypes: LZ4
  type: File?
  sbg:x: 2055.107177734375
  sbg:y: 0
- id: pyradiomicsRadiomicsFeatures
  outputSource:
  - dicomsegandradiomicssr/pyradiomicsRadiomicsFeatures
  sbg:fileTypes: LZ4
  type: File?
  sbg:x: 2055.107177734375
  sbg:y: 214
- id: dicomsegAndRadiomicsSR_SRErrors
  outputSource:
  - dicomsegandradiomicssr/dicomsegAndRadiomicsSR_SRErrors
  sbg:fileTypes: TXT
  type: File?
  sbg:x: 2055.107177734375
  sbg:y: 428
- id: dicomsegAndRadiomicsSR_RadiomicsErrors
  outputSource:
  - dicomsegandradiomicssr/dicomsegAndRadiomicsSR_RadiomicsErrors
  sbg:fileTypes: TXT
  type: File?
  sbg:x: 2055.107177734375
  sbg:y: 535
- id: dicomsegAndRadiomicsSR_OutputJupyterNotebook
  outputSource:
  - dicomsegandradiomicssr/dicomsegAndRadiomicsSR_OutputJupyterNotebook
  sbg:fileTypes: IPYNB
  type: File?
  sbg:x: 2055.107177734375
  sbg:y: 642
- id: dicomsegAndRadiomicsSR_CompressedFiles
  outputSource:
  - dicomsegandradiomicssr/dicomsegAndRadiomicsSR_CompressedFiles
  sbg:fileTypes: LZ4
  type: File?
  sbg:x: 2055.107177734375
  sbg:y: 749
- id: structuredReportsDICOM
  outputSource:
  - dicomsegandradiomicssr/structuredReportsDICOM
  sbg:fileTypes: LZ4
  type: File?
  sbg:x: 2055.107177734375
  sbg:y: 107
- id: dicomsegAndRadiomicsSR_UsageMetrics
  outputSource:
  - dicomsegandradiomicssr/dicomsegAndRadiomicsSR_UsageMetrics
  sbg:fileTypes: LZ4
  type: File?
  sbg:x: 2055.107177734375
  sbg:y: 321
steps:
- id: downloaddicomandconvert
  in:
  - id: s5cmdUrls
    source: s5cmdUrls
  - id: dicomToNiftiConverterTool
    source: dicomToNiftiConverterTool
  out:
  - id: downloadDicomAndConvertOutputJupyterNotebook
  - id: dcm2niix_errors
  - id: downloadDicomAndConvertNiftiFiles
  - id: downloadDicomAndConvertUsageMetrics
  run:
    class: CommandLineTool
    cwlVersion: v1.2
    "$namespaces":
      sbg: https://sevenbridges.com
    id: downloaddicomandconvert
    baseCommand:
    - wget
    - https://raw.githubusercontent.com/ImagingDataCommons/Cloud-Resources-Workflows/main/Notebooks/Totalsegmentator/downloadDicomAndConvertNotebook.ipynb
    - "&&"
    - set
    - "-e"
    - "&&"
    - papermill
    inputs:
    - id: s5cmdUrls
      type: File
      inputBinding:
        shellQuote: false
        position: 3
    - id: dicomToNiftiConverterTool
      type: string
      inputBinding:
        shellQuote: true
        position: 2
    outputs:
    - id: downloadDicomAndConvertOutputJupyterNotebook
      type: File?
      outputBinding:
        glob: downloadDicomAndConvertOutputJupyterNotebook.ipynb
      sbg:fileTypes: IPYNB
    - id: dcm2niix_errors
      type: File?
      outputBinding:
        glob: dcm2niix_errors.csv
      sbg:fileTypes: CSV
    - id: downloadDicomAndConvertNiftiFiles
      type: File?
      outputBinding:
        glob: downloadDicomAndConvertNiftiFiles.tar.lz4
      sbg:fileTypes: LZ4
    - id: downloadDicomAndConvertUsageMetrics
      type: File?
      outputBinding:
        glob: downloadDicomAndConvertUsageMetrics.lz4
      sbg:fileTypes: LZ4
    label: downloadDicomAndConvert
    arguments:
    - prefix: "-p"
      shellQuote: false
      position: 2
      valueFrom: converterType
    - prefix: "-p"
      shellQuote: false
      position: 3
      valueFrom: csvFilePath
    - prefix: ''
      shellQuote: false
      position: 5
      valueFrom: downloadDicomAndConvertNotebook.ipynb
    - prefix: ''
      shellQuote: false
      position: 6
      valueFrom: downloadDicomAndConvertOutputJupyterNotebook.ipynb
    requirements:
    - class: ShellCommandRequirement
    - class: LoadListingRequirement
    - class: DockerRequirement
      dockerPull: imagingdatacommons/download_convert
    - class: InlineJavascriptRequirement
    hints:
    - class: sbg:AWSInstanceType
      value: c5.large;ebs-gp2;10
  label: downloadDicomAndConvert
  sbg:x: 259.817138671875
  sbg:y: 353.5
- id: inferencetotalsegmentator
  in:
  - id: downloadDicomAndConvertNiftiFiles
    source: downloaddicomandconvert/downloadDicomAndConvertNiftiFiles
  - id: dicomToNiftiConverterTool
    source: dicomToNiftiConverterTool
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
    - https://raw.githubusercontent.com/ImagingDataCommons/Cloud-Resources-Workflows/main/Notebooks/Totalsegmentator/inferenceTotalSegmentatorNotebook.ipynb
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
        position: 3
      sbg:fileTypes: LZ4
    - id: dicomToNiftiConverterTool
      type: string
      inputBinding:
        shellQuote: true
        position: 2
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
      position: 2
      valueFrom: converterType
    - prefix: "-p"
      shellQuote: false
      position: 3
      valueFrom: niftiFilePath
    - prefix: ''
      shellQuote: false
      position: 5
      valueFrom: inferenceTotalSegmentatorNotebook.ipynb
    - prefix: ''
      shellQuote: false
      position: 6
      valueFrom: inferenceOutputJupyterNotebook.ipynb
    requirements:
    - class: ShellCommandRequirement
    - class: LoadListingRequirement
    - class: DockerRequirement
      dockerPull: imagingdatacommons/inference_totalseg
    - class: InlineJavascriptRequirement
    hints:
    - class: sbg:AWSInstanceType
      value: g4dn.xlarge;ebs-gp2;25
  label: inferenceTotalSegmentator
  sbg:x: 795.6659545898438
  sbg:y: 193
- id: dicomsegandradiomicssr
  in:
  - id: s5cmdUrls
    source: s5cmdUrls
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
  run:
    class: CommandLineTool
    cwlVersion: v1.2
    "$namespaces":
      sbg: https://sevenbridges.com
    id: dicomsegandradiomicssr
    baseCommand:
    - wget
    - https://raw.githubusercontent.com/ImagingDataCommons/Cloud-Resources-Workflows/main/Notebooks/Totalsegmentator/dicomsegAndRadiomicsSR_Notebook.ipynb
    - "&&"
    - set
    - "-e"
    - "&&"
    - papermill
    inputs:
    - id: s5cmdUrls
      type: File
      inputBinding:
        shellQuote: false
        position: 3
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
    label: dicomsegAndRadiomicsSR
    arguments:
    - prefix: "-p"
      shellQuote: false
      position: 2
      valueFrom: inferenceNiftiFilePath
    - prefix: "-p"
      shellQuote: false
      position: 3
      valueFrom: csvFilePath
    - prefix: ''
      shellQuote: false
      position: 5
      valueFrom: dicomsegAndRadiomicsSR_Notebook.ipynb
    - prefix: ''
      shellQuote: false
      position: 6
      valueFrom: dicomsegAndRadiomicsSR_OutputJupyterNotebook.ipynb
    requirements:
    - class: ShellCommandRequirement
    - class: LoadListingRequirement
    - class: DockerRequirement
      dockerPull: imagingdatacommons/radiomics
    - class: InlineJavascriptRequirement
    hints:
    - class: sbg:AWSInstanceType
      value: m5.xlarge;ebs-gp2;25
  label: dicomsegAndRadiomicsSR
  sbg:x: 1274.7718505859375
  sbg:y: 535
requirements:
- class: InlineJavascriptRequirement
- class: StepInputExpressionRequirement