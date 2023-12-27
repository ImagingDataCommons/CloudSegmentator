---
class: CommandLineTool
cwlVersion: v1.2
"$namespaces":
  sbg: https://sevenbridges.com
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
id: https://cgc-api.sbgenomics.com/v2/apps/vamsikrishna14/idc/example/17/raw/
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
