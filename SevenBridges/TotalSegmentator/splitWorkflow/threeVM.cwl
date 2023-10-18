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
  - inferencetotalsegmentatordocker/totalsegmentatorErrors
  sbg:fileTypes: CSV
  type: File?
  sbg:x: 1249.3201904296875
  sbg:y: -127.86664581298828
- id: inferenceUsageMetrics
  outputSource:
  - inferencetotalsegmentatordocker/inferenceUsageMetrics
  sbg:fileTypes: LZ4
  type: File?
  sbg:x: 1033.7835693359375
  sbg:y: -290.6988525390625
- id: inferenceOutputJupyterNotebook
  outputSource:
  - inferencetotalsegmentatordocker/inferenceOutputJupyterNotebook
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
    id: vamsikrishna14/idc/downloaddicomandconvert/3
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
    sbg:projectName: IDC
    sbg:revisionsInfo:
    - sbg:revision: 0
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1681833288
      sbg:revisionNotes: Copy of vamsikrishna14/idc/itkimage2segimage/9
    - sbg:revision: 1
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1681834267
      sbg:revisionNotes: ''
    - sbg:revision: 2
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1681840727
      sbg:revisionNotes: ''
    - sbg:revision: 3
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1695396114
      sbg:revisionNotes: ''
    sbg:image_url:
    sbg:appVersion:
    - v1.2
    sbg:id: vamsikrishna14/idc/downloaddicomandconvert/3
    sbg:revision: 3
    sbg:revisionNotes: ''
    sbg:modifiedOn: 1695396114
    sbg:modifiedBy: vamsikrishna14
    sbg:createdOn: 1681833288
    sbg:createdBy: vamsikrishna14
    sbg:project: vamsikrishna14/idc
    sbg:sbgMaintained: false
    sbg:validationErrors: []
    sbg:contributors:
    - vamsikrishna14
    sbg:latestRevision: 3
    sbg:publisher: sbg
    sbg:content_hash: a2fff83cdce6f5974ed918b5730d473ca7bbe4c51fc8899051f9f8ed2542055e5
    sbg:workflowLanguage: CWL
  label: downloadDicomAndConvert
  sbg:x: 259.817138671875
  sbg:y: 353.5
- id: inferencetotalsegmentatordocker
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
    id: vamsikrishna14/idc/inferencetotalsegmentatordocker/7
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
    sbg:projectName: IDC
    sbg:revisionsInfo:
    - sbg:revision: 0
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1681836278
      sbg:revisionNotes: Copy of vamsikrishna14/idc/downloaddicomandconvert/1
    - sbg:revision: 1
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1681836986
      sbg:revisionNotes: ''
    - sbg:revision: 2
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1681839774
      sbg:revisionNotes: ''
    - sbg:revision: 3
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1681841312
      sbg:revisionNotes: ''
    - sbg:revision: 4
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1681843996
      sbg:revisionNotes: ''
    - sbg:revision: 5
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1681859327
      sbg:revisionNotes: ''
    - sbg:revision: 6
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1685297796
      sbg:revisionNotes: removed metadata as required outputs
    - sbg:revision: 7
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1695396371
      sbg:revisionNotes: ''
    sbg:image_url:
    sbg:appVersion:
    - v1.2
    sbg:id: vamsikrishna14/idc/inferencetotalsegmentatordocker/7
    sbg:revision: 7
    sbg:revisionNotes: ''
    sbg:modifiedOn: 1695396371
    sbg:modifiedBy: vamsikrishna14
    sbg:createdOn: 1681836278
    sbg:createdBy: vamsikrishna14
    sbg:project: vamsikrishna14/idc
    sbg:sbgMaintained: false
    sbg:validationErrors: []
    sbg:contributors:
    - vamsikrishna14
    sbg:latestRevision: 7
    sbg:publisher: sbg
    sbg:content_hash: ab851c5f011008d0250dffee373ec54ae770f1b34b524501f01b040d8d9ee68a0
    sbg:workflowLanguage: CWL
  label: inferenceTotalSegmentator
  sbg:x: 795.6659545898438
  sbg:y: 193
- id: dicomsegandradiomicssr
  in:
  - id: s5cmdUrls
    source: s5cmdUrls
  - id: downloadDicomAndConvertAndInferenceTotalSegmentatorZipFile
    source: inferencetotalsegmentatordocker/inferenceZipFile
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
    id: vamsikrishna14/idc/dicomsegandradiomicssr/2
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
    sbg:projectName: IDC
    sbg:revisionsInfo:
    - sbg:revision: 0
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1685298038
      sbg:revisionNotes: Copy of vamsikrishna14/idc/itkimage2segimage/9
    - sbg:revision: 1
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1685298787
      sbg:revisionNotes: updated task3
    - sbg:revision: 2
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1695396190
      sbg:revisionNotes: ''
    sbg:image_url:
    sbg:appVersion:
    - v1.2
    sbg:id: vamsikrishna14/idc/dicomsegandradiomicssr/2
    sbg:revision: 2
    sbg:revisionNotes: ''
    sbg:modifiedOn: 1695396190
    sbg:modifiedBy: vamsikrishna14
    sbg:createdOn: 1685298038
    sbg:createdBy: vamsikrishna14
    sbg:project: vamsikrishna14/idc
    sbg:sbgMaintained: false
    sbg:validationErrors: []
    sbg:contributors:
    - vamsikrishna14
    sbg:latestRevision: 2
    sbg:publisher: sbg
    sbg:content_hash: a32120ab84bdb935639d78709618996d0108b5048e4eb87e3e5beeb31cb0dae64
    sbg:workflowLanguage: CWL
  label: dicomsegAndRadiomicsSR
  sbg:x: 1274.7718505859375
  sbg:y: 535
requirements:
- class: InlineJavascriptRequirement
- class: StepInputExpressionRequirement
sbg:projectName: IDC
sbg:revisionsInfo:
- sbg:revision: 0
  sbg:modifiedBy: vamsikrishna14
  sbg:modifiedOn: 1685299575
  sbg:revisionNotes: Copy of vamsikrishna14/idc/totalsegmentatortwovmworkflow/3
- sbg:revision: 1
  sbg:modifiedBy: vamsikrishna14
  sbg:modifiedOn: 1685299685
  sbg:revisionNotes: ''
- sbg:revision: 2
  sbg:modifiedBy: vamsikrishna14
  sbg:modifiedOn: 1685301381
  sbg:revisionNotes: ''
- sbg:revision: 3
  sbg:modifiedBy: vamsikrishna14
  sbg:modifiedOn: 1685301607
  sbg:revisionNotes: ''
- sbg:revision: 4
  sbg:modifiedBy: vamsikrishna14
  sbg:modifiedOn: 1685301628
  sbg:revisionNotes: ''
- sbg:revision: 5
  sbg:modifiedBy: vamsikrishna14
  sbg:modifiedOn: 1695396679
  sbg:revisionNotes: ''
sbg:image_url: https://cgc.sbgenomics.com/ns/brood/images/vamsikrishna14/idc/totalsegmentatorthreevmworkflow/5.png
sbg:appVersion:
- v1.2
id: https://cgc-api.sbgenomics.com/v2/apps/vamsikrishna14/idc/totalsegmentatorthreevmworkflow/5/raw/
sbg:id: vamsikrishna14/idc/totalsegmentatorthreevmworkflow/5
sbg:revision: 5
sbg:revisionNotes: ''
sbg:modifiedOn: 1695396679
sbg:modifiedBy: vamsikrishna14
sbg:createdOn: 1685299575
sbg:createdBy: vamsikrishna14
sbg:project: vamsikrishna14/idc
sbg:sbgMaintained: false
sbg:validationErrors: []
sbg:contributors:
- vamsikrishna14
sbg:latestRevision: 5
sbg:publisher: sbg
sbg:content_hash: a9e9ea5f19f18761b3dbcb4babc86e58ae5011bc602f60c1988548307cb9a8be9
sbg:workflowLanguage: CWL
