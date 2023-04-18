---
class: Workflow
cwlVersion: v1.2
label: TotalSegmentator
"$namespaces":
  sbg: https://sevenbridges.com
inputs:
- id: s5cmdUrls
  type: File
  sbg:x: -431.01019287109375
  sbg:y: -496.17388916015625
- id: dicomToNiftiConverterTool
  type: string
  sbg:x: -427.57568359375
  sbg:y: -6.724541187286377
outputs:
- id: totalSegmentatorErrors
  outputSource:
  - example/totalSegmentatorErrors
  sbg:fileTypes: txt
  type: File?
  sbg:x: 208.97361755371094
  sbg:y: -807.8592529296875
- id: downloadDicomAndConvertAndInferenceTotalSegmentatorUsageMetrics
  outputSource:
  - example/downloadDicomAndConvertAndInferenceTotalSegmentatorUsageMetrics
  sbg:fileTypes: lz4
  type: File?
  sbg:x: 210.5350341796875
  sbg:y: -682.17529296875
- id: downloadDicomAndConvertAndInferenceTotalSegmentatorOutputJupyterNotebook
  outputSource:
  - example/downloadDicomAndConvertAndInferenceTotalSegmentatorOutputJupyterNotebook
  sbg:fileTypes: IPYNB
  type: File?
  sbg:x: 212.30093383789062
  sbg:y: -539.1367797851562
- id: downloadDicomAndConvertAndInferenceTotalSegmentatorMetaData
  outputSource:
  - example/downloadDicomAndConvertAndInferenceTotalSegmentatorMetaData
  sbg:fileTypes: lz4
  type: File?
  sbg:x: 279.4054260253906
  sbg:y: 96.58999633789062
- id: dcm2niixErrors
  outputSource:
  - example/dcm2niixErrors
  sbg:fileTypes: txt
  type: File?
  sbg:x: 282.937255859375
  sbg:y: 278.59442138671875
- id: itkimage2segimageZipFile
  outputSource:
  - itkimage2segimage/itkimage2segimageZipFile
  sbg:fileTypes: LZ4
  type: File?
  sbg:x: 682.0303344726562
  sbg:y: -467.511474609375
- id: itkimage2segimageUsageMetrics
  outputSource:
  - itkimage2segimage/itkimage2segimageUsageMetrics
  sbg:fileTypes: lz4
  type: File?
  sbg:x: 673.081298828125
  sbg:y: -324.3268737792969
- id: itkimage2segimageOutputJupyterNotebook
  outputSource:
  - itkimage2segimage/itkimage2segimageOutputJupyterNotebook
  sbg:fileTypes: IPYNB
  type: File?
  sbg:x: 676.660888671875
  sbg:y: -204.4097900390625
- id: itkimage2segimageErrors
  outputSource:
  - itkimage2segimage/itkimage2segimageErrors
  sbg:fileTypes: txt
  type: File?
  sbg:x: 655.1832275390625
  sbg:y: -41.537330627441406
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
  - id: downloadDicomAndConvertAndInferenceTotalSegmentatorMetaData
  run:
    class: CommandLineTool
    cwlVersion: v1.2
    "$namespaces":
      sbg: https://sevenbridges.com
    id: vamsikrishna14/idc/example/17
    baseCommand:
    - wget
    - https://raw.githubusercontent.com/vkt1414/Cloud-Resources-Workflows/main/Notebooks/Totalsegmentator/downloadDicomAndConvertAndInferenceTotalSegmentatorNotebook.ipynb
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
    - id: downloadDicomAndConvertAndInferenceTotalSegmentatorMetaData
      type: File?
      outputBinding:
        glob: inferenceMetaData.tar.lz4
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
      dockerPull: vamsithiriveedhi/totalsegmentator:task1and2_v3
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
    sbg:image_url:
    sbg:appVersion:
    - v1.2
    sbg:id: vamsikrishna14/idc/example/17
    sbg:revision: 17
    sbg:revisionNotes: ''
    sbg:modifiedOn: 1681766694
    sbg:modifiedBy: vamsikrishna14
    sbg:createdOn: 1674046555
    sbg:createdBy: vamsikrishna14
    sbg:project: vamsikrishna14/idc
    sbg:sbgMaintained: false
    sbg:validationErrors: []
    sbg:contributors:
    - vamsikrishna14
    sbg:latestRevision: 17
    sbg:publisher: sbg
    sbg:content_hash: afe232a3b88463eec73ac6159116772bf9dc898a23d8548c2d9963f1a474ce65d
    sbg:workflowLanguage: CWL
  label: downloadDicomAndConvertAndInferenceTotalSegmentator
  sbg:x: -322.2542419433594
  sbg:y: -254.9150390625
- id: itkimage2segimage
  in:
  - id: dicomToNiftiConverterTool
    source: dicomToNiftiConverterTool
  - id: s5cmdUrls
    source: s5cmdUrls
  - id: downloadDicomAndConvertAndInferenceTotalSegmentatorZipFile
    source: example/downloadDicomAndConvertAndInferenceTotalSegmentatorZipFile
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
    id: vamsikrishna14/idc/itkimage2segimage/5
    baseCommand:
    - wget
    - https://raw.githubusercontent.com/vkt1414/Cloud-Resources-Workflows/main/Notebooks/Totalsegmentator/itkimage2segimageNotebook.ipynb
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
    - id: downloadDicomAndConvertAndInferenceTotalSegmentatorZipFile
      type: File?
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
      valueFrom: converterType
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
    sbg:image_url:
    sbg:appVersion:
    - v1.2
    sbg:id: vamsikrishna14/idc/itkimage2segimage/5
    sbg:revision: 5
    sbg:revisionNotes: ''
    sbg:modifiedOn: 1681769793
    sbg:modifiedBy: vamsikrishna14
    sbg:createdOn: 1681762996
    sbg:createdBy: vamsikrishna14
    sbg:project: vamsikrishna14/idc
    sbg:sbgMaintained: false
    sbg:validationErrors: []
    sbg:contributors:
    - vamsikrishna14
    sbg:latestRevision: 5
    sbg:publisher: sbg
    sbg:content_hash: a86b07d445be62791fa65348bdadf74762645d405dd5d1f7cda894759f0355ec9
    sbg:workflowLanguage: CWL
  label: itkimage2segimage
  sbg:x: 522.7245483398438
  sbg:y: -250.3060760498047
requirements:
- class: InlineJavascriptRequirement
- class: StepInputExpressionRequirement
sbg:projectName: IDC
sbg:revisionsInfo:
- sbg:revision: 0
  sbg:modifiedBy: vamsikrishna14
  sbg:modifiedOn: 1681763732
  sbg:revisionNotes:
- sbg:revision: 1
  sbg:modifiedBy: vamsikrishna14
  sbg:modifiedOn: 1681764004
  sbg:revisionNotes: ''
- sbg:revision: 2
  sbg:modifiedBy: vamsikrishna14
  sbg:modifiedOn: 1681764068
  sbg:revisionNotes: ''
- sbg:revision: 3
  sbg:modifiedBy: vamsikrishna14
  sbg:modifiedOn: 1681764099
  sbg:revisionNotes: ''
- sbg:revision: 4
  sbg:modifiedBy: vamsikrishna14
  sbg:modifiedOn: 1681764131
  sbg:revisionNotes: ''
- sbg:revision: 5
  sbg:modifiedBy: vamsikrishna14
  sbg:modifiedOn: 1681764163
  sbg:revisionNotes: ''
- sbg:revision: 6
  sbg:modifiedBy: vamsikrishna14
  sbg:modifiedOn: 1681764295
  sbg:revisionNotes: ''
- sbg:revision: 7
  sbg:modifiedBy: vamsikrishna14
  sbg:modifiedOn: 1681764490
  sbg:revisionNotes: ''
- sbg:revision: 8
  sbg:modifiedBy: vamsikrishna14
  sbg:modifiedOn: 1681765950
  sbg:revisionNotes: ''
- sbg:revision: 9
  sbg:modifiedBy: vamsikrishna14
  sbg:modifiedOn: 1681767051
  sbg:revisionNotes: ''
- sbg:revision: 10
  sbg:modifiedBy: vamsikrishna14
  sbg:modifiedOn: 1681769890
  sbg:revisionNotes: ''
sbg:image_url: https://cgc.sbgenomics.com/ns/brood/images/vamsikrishna14/idc/totalsegmentator/10.png
sbg:appVersion:
- v1.2
id: https://cgc-api.sbgenomics.com/v2/apps/vamsikrishna14/idc/totalsegmentator/10/raw/
sbg:id: vamsikrishna14/idc/totalsegmentator/10
sbg:revision: 10
sbg:revisionNotes: ''
sbg:modifiedOn: 1681769890
sbg:modifiedBy: vamsikrishna14
sbg:createdOn: 1681763732
sbg:createdBy: vamsikrishna14
sbg:project: vamsikrishna14/idc
sbg:sbgMaintained: false
sbg:validationErrors: []
sbg:contributors:
- vamsikrishna14
sbg:latestRevision: 10
sbg:publisher: sbg
sbg:content_hash: a8c49a98c4e9b783ebe5f8ce835aff66d47783403420af9ac469dc9ab99ff9e82
sbg:workflowLanguage: CWL
