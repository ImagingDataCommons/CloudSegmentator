---
class: Workflow
cwlVersion: v1.2
label: TotalSegmentatorSplitWorkflowV1
"$namespaces":
  sbg: https://sevenbridges.com
inputs:
- id: dicomToNiftiConverterTool
  type: string
  sbg:x: -412.7337341308594
  sbg:y: -404.9574279785156
- id: s5cmdUrls
  type: File
  sbg:x: -367.7337341308594
  sbg:y: 194.0939483642578
outputs:
- id: downloadDicomAndConvertUsageMetrics
  outputSource:
  - downloaddicomandconvert/downloadDicomAndConvertUsageMetrics
  sbg:fileTypes: LZ4
  type: File?
  sbg:x: -71.91853332519531
  sbg:y: -392.552490234375
- id: downloadDicomAndConvertOutputJupyterNotebook
  outputSource:
  - downloaddicomandconvert/downloadDicomAndConvertOutputJupyterNotebook
  sbg:fileTypes: IPYNB
  type: File?
  sbg:x: -61.91853332519531
  sbg:y: -273.552490234375
- id: dcm2niix_errors
  outputSource:
  - downloaddicomandconvert/dcm2niix_errors
  sbg:fileTypes: CSV
  type: File?
  sbg:x: -17.918535232543945
  sbg:y: 250.28607177734375
- id: totalsegmentatorErrors
  outputSource:
  - inferencetotalsegmentatordocker/totalsegmentatorErrors
  sbg:fileTypes: CSV
  type: File?
  sbg:x: 193.26626586914062
  sbg:y: -384.07586669921875
- id: inferenceUsageMetrics
  outputSource:
  - inferencetotalsegmentatordocker/inferenceUsageMetrics
  sbg:fileTypes: LZ4
  type: File?
  sbg:x: 209.26626586914062
  sbg:y: -273.07586669921875
- id: inferenceOutputJupyterNotebook
  outputSource:
  - inferencetotalsegmentatordocker/inferenceOutputJupyterNotebook
  sbg:fileTypes: IPYNB
  type: File?
  sbg:x: 251.26626586914062
  sbg:y: 17.459945678710938
- id: inferenceMetaData
  outputSource:
  - inferencetotalsegmentatordocker/inferenceMetaData
  type: File?
  sbg:x: 269.2662658691406
  sbg:y: 149.45994567871094
- id: itkimage2segimageZipFile
  outputSource:
  - itkimage2segimage/itkimage2segimageZipFile
  sbg:fileTypes: LZ4
  type: File?
  sbg:x: 529.2662963867188
  sbg:y: -364.8226623535156
- id: itkimage2segimageUsageMetrics
  outputSource:
  - itkimage2segimage/itkimage2segimageUsageMetrics
  sbg:fileTypes: lz4
  type: File?
  sbg:x: 575.2662963867188
  sbg:y: -197.82266235351562
- id: itkimage2segimageOutputJupyterNotebook
  outputSource:
  - itkimage2segimage/itkimage2segimageOutputJupyterNotebook
  sbg:fileTypes: IPYNB
  type: File?
  sbg:x: 599.2662963867188
  sbg:y: -91.8226547241211
- id: itkimage2segimageErrors
  outputSource:
  - itkimage2segimage/itkimage2segimageErrors
  sbg:fileTypes: txt
  type: File?
  sbg:x: 614.2662963867188
  sbg:y: 25.177339553833008
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
    id: vamsikrishna14/idc/downloaddicomandconvert/2
    baseCommand:
    - wget
    - https://raw.githubusercontent.com/vkt1414/Cloud-Resources-Workflows/main/Notebooks/Totalsegmentator/downloadDicomAndConvertNotebook.ipynb
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
      dockerPull: vamsithiriveedhi/totalsegmentator:task1_v1
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
    sbg:image_url:
    sbg:appVersion:
    - v1.2
    sbg:id: vamsikrishna14/idc/downloaddicomandconvert/2
    sbg:revision: 2
    sbg:revisionNotes: ''
    sbg:modifiedOn: 1681840727
    sbg:modifiedBy: vamsikrishna14
    sbg:createdOn: 1681833288
    sbg:createdBy: vamsikrishna14
    sbg:project: vamsikrishna14/idc
    sbg:sbgMaintained: false
    sbg:validationErrors: []
    sbg:contributors:
    - vamsikrishna14
    sbg:latestRevision: 2
    sbg:publisher: sbg
    sbg:content_hash: a06cee4ff549980ea24181509b5ff33641b37fc106922c1dc5b7c18b2a2453555
    sbg:workflowLanguage: CWL
  label: downloadDicomAndConvert
  sbg:x: -431
  sbg:y: -119
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
  - id: inferenceMetaData
  run:
    class: CommandLineTool
    cwlVersion: v1.2
    "$namespaces":
      sbg: https://sevenbridges.com
    id: vamsikrishna14/idc/inferencetotalsegmentatordocker/5
    baseCommand:
    - wget
    - https://raw.githubusercontent.com/vkt1414/Cloud-Resources-Workflows/main/Notebooks/Totalsegmentator/inferenceTotalSegmentatorNotebook.ipynb
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
    - id: inferenceMetaData
      type: File?
      outputBinding:
        glob: inferenceMetaData.tar.lz4
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
      dockerPull: vamsithiriveedhi/totalsegmentator:task2_v3
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
    sbg:image_url:
    sbg:appVersion:
    - v1.2
    sbg:id: vamsikrishna14/idc/inferencetotalsegmentatordocker/5
    sbg:revision: 5
    sbg:revisionNotes: ''
    sbg:modifiedOn: 1681859327
    sbg:modifiedBy: vamsikrishna14
    sbg:createdOn: 1681836278
    sbg:createdBy: vamsikrishna14
    sbg:project: vamsikrishna14/idc
    sbg:sbgMaintained: false
    sbg:validationErrors: []
    sbg:contributors:
    - vamsikrishna14
    sbg:latestRevision: 5
    sbg:publisher: sbg
    sbg:content_hash: a27ec6770d92b756348403ab6dcf57b0b99c286426695e30e310a91354430abb1
    sbg:workflowLanguage: CWL
  label: inferenceTotalSegmentator
  sbg:x: -28
  sbg:y: -119
- id: itkimage2segimage
  in:
  - id: s5cmdUrls
    source: s5cmdUrls
  - id: downloadDicomAndConvertAndInferenceTotalSegmentatorZipFile
    source: inferencetotalsegmentatordocker/inferenceZipFile
  out:
  - id: itkimage2segimageOutputJupyterNotebook
  - id: itkimage2segimageErrors
  - id: itkimage2segimageZipFile
  - id: itkimage2segimageUsageMetrics
  run:
    class: CommandLineTool
    cwlVersion: v1.2
    "$namespaces":
      sbg: https://sevenbridges.com
    id: vamsikrishna14/idc/itkimage2segimage/9
    baseCommand:
    - wget
    - https://raw.githubusercontent.com/vkt1414/Cloud-Resources-Workflows/main/Notebooks/Totalsegmentator/itkimage2segimageNotebook.ipynb
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
    - id: itkimage2segimageOutputJupyterNotebook
      type: File?
      outputBinding:
        glob: itkimage2segimageOutputJupyterNotebook.ipynb
      sbg:fileTypes: IPYNB
    - id: itkimage2segimageErrors
      type: File?
      outputBinding:
        glob: itkimage2segimage_error_file.txt
      sbg:fileTypes: txt
    - id: itkimage2segimageZipFile
      type: File?
      outputBinding:
        glob: itkimage2segimageZipFile.tar.lz4
      sbg:fileTypes: LZ4
    - id: itkimage2segimageUsageMetrics
      type: File?
      outputBinding:
        glob: itkimage2segimageUsageMetrics.lz4
      sbg:fileTypes: lz4
    label: itkimage2segimage
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
      valueFrom: itkimage2segimageNotebook.ipynb
    - prefix: ''
      shellQuote: false
      position: 6
      valueFrom: itkimage2segimageOutputJupyterNotebook.ipynb
    requirements:
    - class: ShellCommandRequirement
    - class: LoadListingRequirement
    - class: DockerRequirement
      dockerPull: vamsithiriveedhi/totalsegmentator:task3_v2
    - class: InlineJavascriptRequirement
    hints:
    - class: sbg:AWSInstanceType
      value: c5.large;ebs-gp2;10
    sbg:projectName: IDC
    sbg:revisionsInfo:
    - sbg:revision: 0
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1681762996
      sbg:revisionNotes: Copy of vamsikrishna14/idc/example/16
    - sbg:revision: 1
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1681763373
      sbg:revisionNotes: ''
    - sbg:revision: 2
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1681763535
      sbg:revisionNotes: ''
    - sbg:revision: 3
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1681763659
      sbg:revisionNotes: ''
    - sbg:revision: 4
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1681766623
      sbg:revisionNotes: ''
    - sbg:revision: 5
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1681769793
      sbg:revisionNotes: ''
    - sbg:revision: 6
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1681827369
      sbg:revisionNotes: ''
    - sbg:revision: 7
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1681828769
      sbg:revisionNotes: ''
    - sbg:revision: 8
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1681828857
      sbg:revisionNotes: ''
    - sbg:revision: 9
      sbg:modifiedBy: vamsikrishna14
      sbg:modifiedOn: 1681828891
      sbg:revisionNotes: ''
    sbg:image_url:
    sbg:appVersion:
    - v1.2
    sbg:id: vamsikrishna14/idc/itkimage2segimage/9
    sbg:revision: 9
    sbg:revisionNotes: ''
    sbg:modifiedOn: 1681828891
    sbg:modifiedBy: vamsikrishna14
    sbg:createdOn: 1681762996
    sbg:createdBy: vamsikrishna14
    sbg:project: vamsikrishna14/idc
    sbg:sbgMaintained: false
    sbg:validationErrors: []
    sbg:contributors:
    - vamsikrishna14
    sbg:latestRevision: 9
    sbg:publisher: sbg
    sbg:content_hash: a44ec989dd68ff0a415a5e1b1fb88dec30eadf81a7f5e820f84f07eb8c7c8dcc7
    sbg:workflowLanguage: CWL
  label: itkimage2segimage
  sbg:x: 367
  sbg:y: -133
requirements:
- class: InlineJavascriptRequirement
- class: StepInputExpressionRequirement
sbg:projectName: IDC
sbg:revisionsInfo:
- sbg:revision: 0
  sbg:modifiedBy: vamsikrishna14
  sbg:modifiedOn: 1681860040
  sbg:revisionNotes:
- sbg:revision: 1
  sbg:modifiedBy: vamsikrishna14
  sbg:modifiedOn: 1681860198
  sbg:revisionNotes: ''
sbg:image_url: https://cgc.sbgenomics.com/ns/brood/images/vamsikrishna14/idc/totalsegmentatorsplitworkflowv1/1.png
sbg:appVersion:
- v1.2
id: https://cgc-api.sbgenomics.com/v2/apps/vamsikrishna14/idc/totalsegmentatorsplitworkflowv1/1/raw/
sbg:id: vamsikrishna14/idc/totalsegmentatorsplitworkflowv1/1
sbg:revision: 1
sbg:revisionNotes: ''
sbg:modifiedOn: 1681860198
sbg:modifiedBy: vamsikrishna14
sbg:createdOn: 1681860040
sbg:createdBy: vamsikrishna14
sbg:project: vamsikrishna14/idc
sbg:sbgMaintained: false
sbg:validationErrors: []
sbg:contributors:
- vamsikrishna14
sbg:latestRevision: 1
sbg:publisher: sbg
sbg:content_hash: aa7e97b49bea2caf65db47a910b3fe4d8ba9f8f35d310828a1deaab7b36afd1ff
sbg:workflowLanguage: CWL
