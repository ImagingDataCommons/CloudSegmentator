---
class: Workflow
cwlVersion: v1.2
label: TotalSegmentatorTwoVmWorkflow
"$namespaces":
  sbg: https://sevenbridges.com
inputs:
- id: s5cmdUrls
  type: File
  sbg:x: 0
  sbg:y: 321
- id: dicomToNiftiConverterTool
  type: string
  sbg:x: 0
  sbg:y: 428
outputs:
- id: totalSegmentatorErrors
  outputSource:
  - example/totalSegmentatorErrors
  sbg:fileTypes: txt
  type: File?
  sbg:x: 966.80322265625
  sbg:y: 111.5
- id: downloadDicomAndConvertAndInferenceTotalSegmentatorUsageMetrics
  outputSource:
  - example/downloadDicomAndConvertAndInferenceTotalSegmentatorUsageMetrics
  sbg:fileTypes: lz4
  type: File?
  sbg:x: 966.80322265625
  sbg:y: 218.5
- id: downloadDicomAndConvertAndInferenceTotalSegmentatorOutputJupyterNotebook
  outputSource:
  - example/downloadDicomAndConvertAndInferenceTotalSegmentatorOutputJupyterNotebook
  sbg:fileTypes: IPYNB
  type: File?
  sbg:x: 966.80322265625
  sbg:y: 325.5
- id: dcm2niixErrors
  outputSource:
  - example/dcm2niixErrors
  sbg:fileTypes: txt
  type: File?
  sbg:x: 966.80322265625
  sbg:y: 637.5
- id: structuredReportsJSON
  outputSource:
  - dicomsegandradiomicssr/structuredReportsJSON
  sbg:fileTypes: LZ4
  type: File?
  sbg:x: 1747.1385498046875
  sbg:y: 0
- id: structuredReportsDICOM
  outputSource:
  - dicomsegandradiomicssr/structuredReportsDICOM
  sbg:fileTypes: LZ4
  type: File?
  sbg:x: 1747.1385498046875
  sbg:y: 107
- id: dicomsegAndRadiomicsSR_UsageMetrics
  outputSource:
  - dicomsegandradiomicssr/dicomsegAndRadiomicsSR_UsageMetrics
  sbg:fileTypes: LZ4
  type: File?
  sbg:x: 1747.1385498046875
  sbg:y: 321
- id: dicomsegAndRadiomicsSR_SRErrors
  outputSource:
  - dicomsegandradiomicssr/dicomsegAndRadiomicsSR_SRErrors
  sbg:fileTypes: TXT
  type: File?
  sbg:x: 1747.1385498046875
  sbg:y: 428
- id: dicomsegAndRadiomicsSR_RadiomicsErrors
  outputSource:
  - dicomsegandradiomicssr/dicomsegAndRadiomicsSR_RadiomicsErrors
  sbg:fileTypes: TXT
  type: File?
  sbg:x: 1747.1385498046875
  sbg:y: 535
- id: dicomsegAndRadiomicsSR_CompressedFiles
  outputSource:
  - dicomsegandradiomicssr/dicomsegAndRadiomicsSR_CompressedFiles
  sbg:fileTypes: LZ4
  type: File?
  sbg:x: 1747.1385498046875
  sbg:y: 749
- id: dicomsegAndRadiomicsSR_OutputJupyterNotebook
  outputSource:
  - dicomsegandradiomicssr/dicomsegAndRadiomicsSR_OutputJupyterNotebook
  sbg:fileTypes: IPYNB
  type: File?
  sbg:x: 1747.1385498046875
  sbg:y: 642
- id: pyradiomicsRadiomicsFeatures
  outputSource:
  - dicomsegandradiomicssr/pyradiomicsRadiomicsFeatures
  sbg:fileTypes: LZ4
  type: File?
  sbg:x: 1747.1385498046875
  sbg:y: 214
steps:
- id: example
  in:
  - id: dicomToNiftiConverterTool
    source: dicomToNiftiConverterTool
    valueFrom: '"dcm2niix"'
  - id: s5cmdUrls
    source: s5cmdUrls
  out:
  - id: downloadDicomAndConvertAndInferenceTotalSegmentatorOutputJupyterNotebook
  - id: dcm2niixErrors
  - id: totalSegmentatorErrors
  - id: downloadDicomAndConvertAndInferenceTotalSegmentatorZipFile
  - id: downloadDicomAndConvertAndInferenceTotalSegmentatorUsageMetrics
  run:
    class: CommandLineTool
    cwlVersion: v1.2
    "$namespaces":
      sbg: https://sevenbridges.com
    id: vamsikrishna14/idc/example/19
    baseCommand:
    - wget
    - https://raw.githubusercontent.com/ImagingDataCommons/Cloud-Resources-Workflows/main/Notebooks/Totalsegmentator/downloadDicomAndConvertAndInferenceTotalSegmentatorNotebook.ipynb
    - "&&"
    - set
    - "-e"
    - "&&"
    - papermill
    inputs:
    - id: dicomToNiftiConverterTool
      type: string
      inputBinding:
        shellQuote: false
        position: 2
    - id: s5cmdUrls
      type: File
      inputBinding:
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
    label: downloadDicomAndConvertAndInferenceTotalSegmentator
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
      valueFrom: downloadDicomAndConvertAndInferenceTotalSegmentatorOutputJupyterNotebook.ipynb
    - prefix: ''
      shellQuote: false
      position: 0
      valueFrom: downloadDicomAndConvertAndInferenceTotalSegmentatorNotebook.ipynb
    requirements:
    - class: ShellCommandRequirement
    - class: LoadListingRequirement
    - class: DockerRequirement
      dockerPull: imagingdatacommons/download_convert_inference_totalseg
    - class: InlineJavascriptRequirement
    hints:
    - class: sbg:AWSInstanceType
      value: g4dn.xlarge;ebs-gp2;25
    sbg:projectName: IDC
    sbg:revisionsInfo:
    - sbg:revision: 0
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1674046555
      sbg:revisionNotes:
    - sbg:revision: 1
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1674062962
      sbg:revisionNotes: ''
    - sbg:revision: 2
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1674754210
      sbg:revisionNotes: ''
    - sbg:revision: 3
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1681303367
      sbg:revisionNotes: ''
    - sbg:revision: 4
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1681303509
      sbg:revisionNotes: ''
    - sbg:revision: 5
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1681304253
      sbg:revisionNotes: ''
    - sbg:revision: 6
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1681305368
      sbg:revisionNotes: ''
    - sbg:revision: 7
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1681305775
      sbg:revisionNotes: ''
    - sbg:revision: 8
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1681665737
      sbg:revisionNotes: ''
    - sbg:revision: 9
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1681666866
      sbg:revisionNotes: ''
    - sbg:revision: 10
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1681677923
      sbg:revisionNotes: ''
    - sbg:revision: 11
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1681748107
      sbg:revisionNotes: ''
    - sbg:revision: 12
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1681755192
      sbg:revisionNotes: ''
    - sbg:revision: 13
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1681758193
      sbg:revisionNotes: ''
    - sbg:revision: 14
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1681758689
      sbg:revisionNotes: ''
    - sbg:revision: 15
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1681759160
      sbg:revisionNotes: ''
    - sbg:revision: 16
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1681762956
      sbg:revisionNotes: ''
    - sbg:revision: 17
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1681766694
      sbg:revisionNotes: ''
    - sbg:revision: 18
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1685297484
      sbg:revisionNotes: removed metadata as we no longer capture png files
    - sbg:revision: 19
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1695396244
      sbg:revisionNotes: ''
    sbg:image_url:
    sbg:appVersion:
    - v1.2
    sbg:id: vamsikrishna14/idc/example/19
    sbg:revision: 19
    sbg:revisionNotes: ''
    sbg:modifiedOn: 1695396244
    sbg:modifiedBy: vamsikrishna14
    sbg:createdOn: 1674046555
    sbg:createdBy: vamsikrishna14
    sbg:project: vamsikrishna14/idc
    sbg:sbgMaintained: false
    sbg:validationErrors: []
    sbg:contributors:
    - vamsikrishna14
    sbg:latestRevision: 19
    sbg:publisher: sbg
    sbg:content_hash: affc3b50184ebba59c7e99fd080393efffc6b6a933334e251bd69cc94e9af2307
    sbg:workflowLanguage: CWL
  label: downloadDicomAndConvertAndInferenceTotalSegmentator
  sbg:x: 259.817138671875
  sbg:y: 346.5
- id: dicomsegandradiomicssr
  in:
  - id: s5cmdUrls
    source: s5cmdUrls
  - id: downloadDicomAndConvertAndInferenceTotalSegmentatorZipFile
    source: example/downloadDicomAndConvertAndInferenceTotalSegmentatorZipFile
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
  sbg:x: 966.80322265625
  sbg:y: 481.5
requirements:
- class: InlineJavascriptRequirement
- class: StepInputExpressionRequirement
sbg:projectName: IDC
sbg:revisionsInfo:
- sbg:revision: 0
  sbg:modifiedBy: vamsikrishna14
  sbg:modifiedOn: 1685298940
  sbg:revisionNotes: Copy of vamsikrishna14/idc/totalsegmentatorsplitworkflowv1/1
- sbg:revision: 1
  sbg:modifiedBy: vamsikrishna14
  sbg:modifiedOn: 1685299066
  sbg:revisionNotes: ''
- sbg:revision: 2
  sbg:modifiedBy: vamsikrishna14
  sbg:modifiedOn: 1685299241
  sbg:revisionNotes: ''
- sbg:revision: 3
  sbg:modifiedBy: vamsikrishna14
  sbg:modifiedOn: 1685299500
  sbg:revisionNotes: ''
- sbg:revision: 4
  sbg:modifiedBy: vamsikrishna14
  sbg:modifiedOn: 1685301237
  sbg:revisionNotes: ''
- sbg:revision: 5
  sbg:modifiedBy: vamsikrishna14
  sbg:modifiedOn: 1695396447
  sbg:revisionNotes: ''
sbg:image_url: https://cgc.sbgenomics.com/ns/brood/images/vamsikrishna14/idc/totalsegmentatortwovmworkflow/5.png
sbg:appVersion:
- v1.2
id: https://cgc-api.sbgenomics.com/v2/apps/vamsikrishna14/idc/totalsegmentatortwovmworkflow/5/raw/
sbg:id: vamsikrishna14/idc/totalsegmentatortwovmworkflow/5
sbg:revision: 5
sbg:revisionNotes: ''
sbg:modifiedOn: 1695396447
sbg:modifiedBy: vamsikrishna14
sbg:createdOn: 1685298940
sbg:createdBy: vamsikrishna14
sbg:project: vamsikrishna14/idc
sbg:sbgMaintained: false
sbg:validationErrors: []
sbg:contributors:
- vamsikrishna14
sbg:latestRevision: 5
sbg:publisher: sbg
sbg:content_hash: a1b26965f8c6bee5d3d74583373e5bf6c031d759013fbaa383a60cb32911088ab
sbg:workflowLanguage: CWL
