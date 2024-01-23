---
class: Workflow
cwlVersion: v1.2
label: TotalSegmentatorEndtoEnd
inputs:
- id: yamlListOfSeriesInstanceUIDs
  sbg:fileTypes: YAML
  type: File
  sbg:x: 0
  sbg:y: 588.5
outputs:
- id: totalsegmentatorErrors
  outputSource:
  - totalsegmentatorend_to_end/totalsegmentatorErrors
  type: File?
  sbg:x: 971.2205200195312
  sbg:y: 0
- id: structuredReportsJSON
  outputSource:
  - totalsegmentatorend_to_end/structuredReportsJSON
  sbg:fileTypes: LZ4
  type: File?
  sbg:x: 971.2205200195312
  sbg:y: 107
- id: structuredReportsDICOM
  outputSource:
  - totalsegmentatorend_to_end/structuredReportsDICOM
  sbg:fileTypes: LZ4
  type: File?
  sbg:x: 971.2205200195312
  sbg:y: 214
- id: pyradiomicsRadiomicsFeatures
  outputSource:
  - totalsegmentatorend_to_end/pyradiomicsRadiomicsFeatures
  sbg:fileTypes: LZ4
  type: File?
  sbg:x: 971.2205200195312
  sbg:y: 321
- id: modality_errors
  outputSource:
  - totalsegmentatorend_to_end/modality_errors
  sbg:fileTypes: TXT
  type: File?
  sbg:x: 971.2205200195312
  sbg:y: 428
- id: endToEndTotalSegmentatorOutputJupyterNotebook
  outputSource:
  - totalsegmentatorend_to_end/endToEndTotalSegmentatorOutputJupyterNotebook
  sbg:fileTypes: IPYNB
  type: File?
  sbg:x: 971.2205200195312
  sbg:y: 535
- id: endToEndTotalSegmentator_UsageMetrics
  outputSource:
  - totalsegmentatorend_to_end/endToEndTotalSegmentator_UsageMetrics
  sbg:fileTypes: LZ4
  type: File?
  sbg:x: 971.2205200195312
  sbg:y: 642
- id: dcm2niixErrors
  outputSource:
  - totalsegmentatorend_to_end/dcm2niixErrors
  sbg:fileTypes: TXT
  type: File?
  sbg:x: 971.2205200195312
  sbg:y: 1177
- id: dicomsegAndRadiomicsSR_CompressedFiles
  outputSource:
  - totalsegmentatorend_to_end/dicomsegAndRadiomicsSR_CompressedFiles
  sbg:fileTypes: LZ4
  type: File?
  sbg:x: 971.2205200195312
  sbg:y: 1070
- id: dicomsegAndRadiomicsSR_RadiomicsErrors
  outputSource:
  - totalsegmentatorend_to_end/dicomsegAndRadiomicsSR_RadiomicsErrors
  sbg:fileTypes: TXT
  type: File?
  sbg:x: 971.2205200195312
  sbg:y: 963
- id: dicomsegAndRadiomicsSR_SRErrors
  outputSource:
  - totalsegmentatorend_to_end/dicomsegAndRadiomicsSR_SRErrors
  sbg:fileTypes: TXT
  type: File?
  sbg:x: 971.2205200195312
  sbg:y: 856
- id: dicomSegErrors
  outputSource:
  - totalsegmentatorend_to_end/dicomSegErrors
  type: File?
  sbg:x: 971.2205200195312
  sbg:y: 749
steps:
- id: totalsegmentatorend_to_end
  in:
  - id: yamlListOfSeriesInstanceUIDs
    source: yamlListOfSeriesInstanceUIDs
  out:
  - id: endToEndTotalSegmentatorOutputJupyterNotebook
  - id: dicomsegAndRadiomicsSR_CompressedFiles
  - id: pyradiomicsRadiomicsFeatures
  - id: structuredReportsDICOM
  - id: structuredReportsJSON
  - id: endToEndTotalSegmentator_UsageMetrics
  - id: dicomsegAndRadiomicsSR_RadiomicsErrors
  - id: dicomsegAndRadiomicsSR_SRErrors
  - id: dcm2niixErrors
  - id: totalsegmentatorErrors
  - id: dicomSegErrors
  - id: modality_errors
  run:
    class: CommandLineTool
    cwlVersion: v1.2
    "$namespaces":
      sbg: https://sevenbridges.com
    id: TotalSegmentatorOneVmWorkflow
    baseCommand:
    - wget
    - https://raw.githubusercontent.com/ImagingDataCommons/CloudSegmentator/v1.1.0/workflows/TotalSegmentator/Notebooks/endToEndTotalSegmentatorNotebook.ipynb
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
      sbg:fileTypes: YAML
    outputs:
    - id: endToEndTotalSegmentatorOutputJupyterNotebook
      type: File?
      outputBinding:
        glob: endToEndTotalSegmentatorOutputJupyterNotebook.ipynb
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
    - id: endToEndTotalSegmentator_UsageMetrics
      type: File?
      outputBinding:
        glob: endToEndTotalSegmentator_UsageMetrics.lz4
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
    - id: dcm2niixErrors
      type: File?
      outputBinding:
        glob: error_file.txt
      sbg:fileTypes: TXT
    - id: totalsegmentatorErrors
      type: File?
      outputBinding:
        glob: totalsegmentator_errors.txt
    - id: dicomSegErrors
      type: File?
      outputBinding:
        glob: itkimage2segimage_error_file.txt
    - id: modality_errors
      type: File?
      outputBinding:
        glob: modality_error_file.txt
      sbg:fileTypes: TXT
    label: TotalSegmentatorOneVmWorkflow
    arguments:
    - prefix: ''
      shellQuote: false
      position: 1
      valueFrom: endToEndTotalSegmentatorNotebook.ipynb
    - prefix: ''
      shellQuote: false
      position: 2
      valueFrom: endToEndTotalSegmentatorOutputJupyterNotebook.ipynb
    requirements:
    - class: ShellCommandRequirement
    - class: LoadListingRequirement
    - class: DockerRequirement
      dockerPull: "imagingdatacommons/download_convert_inference_totalseg_dicom_seg_pyradiomics_sr:v1.1.0"
    - class: InlineJavascriptRequirement
    hints:
    - class: sbg:AWSInstanceType
      value: g4dn.xlarge;ebs-gp2;25
  label: TotalSegmentatorOneVmWorkflow
  hints:
  - class: sbg:AWSInstanceType
    value: g4dn.xlarge;ebs-gp2;25
  sbg:x: 294.943115234375
  sbg:y: 511.5
requirements:
- class: InlineJavascriptRequirement
- class: StepInputExpressionRequirement