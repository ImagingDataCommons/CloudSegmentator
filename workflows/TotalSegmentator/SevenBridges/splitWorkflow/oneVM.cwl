class: Workflow
cwlVersion: v1.2
label: TotalSegmentatorOneVmWorkflow
$namespaces:
  sbg: 'https://sevenbridges.com'
inputs:
  - id: s5cmdUrls
    type: File
    'sbg:x': 0
    'sbg:y': 481.5
  - id: dicomToNiftiConverterTool
    type: string
    'sbg:x': 0
    'sbg:y': 588.5
outputs:
  - id: structuredReportsDICOM
    outputSource:
      - TotalSegmentatorOneVmWorkflow/structuredReportsDICOM
    'sbg:fileTypes': LZ4
    type: File?
    'sbg:x': 888.5424194335938
    'sbg:y': 214
  - id: pyradiomicsRadiomicsFeatures
    outputSource:
      - TotalSegmentatorOneVmWorkflow/pyradiomicsRadiomicsFeatures
    'sbg:fileTypes': LZ4
    type: File?
    'sbg:x': 888.5424194335938
    'sbg:y': 321
  - id: endToEndTotalSegmentatorOutputJupyterNotebook
    outputSource:
      - TotalSegmentatorOneVmWorkflow/endToEndTotalSegmentatorOutputJupyterNotebook
    'sbg:fileTypes': IPYNB
    type: File?
    'sbg:x': 888.5424194335938
    'sbg:y': 428
  - id: endToEndTotalSegmentator_UsageMetrics
    outputSource:
      - TotalSegmentatorOneVmWorkflow/endToEndTotalSegmentator_UsageMetrics
    'sbg:fileTypes': LZ4
    type: File?
    'sbg:x': 888.5424194335938
    'sbg:y': 535
  - id: dicomSegErrors
    outputSource:
      - TotalSegmentatorOneVmWorkflow/dicomSegErrors
    type: File?
    'sbg:x': 888.5424194335938
    'sbg:y': 642
  - id: dcm2niixErrors
    outputSource:
      - TotalSegmentatorOneVmWorkflow/dcm2niixErrors
    'sbg:fileTypes': TXT
    type: File?
    'sbg:x': 888.5424194335938
    'sbg:y': 1070
  - id: dicomsegAndRadiomicsSR_CompressedFiles
    outputSource:
      - TotalSegmentatorOneVmWorkflow/dicomsegAndRadiomicsSR_CompressedFiles
    'sbg:fileTypes': LZ4
    type: File?
    'sbg:x': 888.5424194335938
    'sbg:y': 963
  - id: dicomsegAndRadiomicsSR_RadiomicsErrors
    outputSource:
      - TotalSegmentatorOneVmWorkflow/dicomsegAndRadiomicsSR_RadiomicsErrors
    'sbg:fileTypes': TXT
    type: File?
    'sbg:x': 888.5424194335938
    'sbg:y': 856
  - id: dicomsegAndRadiomicsSR_SRErrors
    outputSource:
      - TotalSegmentatorOneVmWorkflow/dicomsegAndRadiomicsSR_SRErrors
    'sbg:fileTypes': TXT
    type: File?
    'sbg:x': 888.5424194335938
    'sbg:y': 749
  - id: totalsegmentatorErrors
    outputSource:
      - TotalSegmentatorOneVmWorkflow/totalsegmentatorErrors
    type: File?
    'sbg:x': 888.5424194335938
    'sbg:y': 0
  - id: structuredReportsJSON
    outputSource:
      - TotalSegmentatorOneVmWorkflow/structuredReportsJSON
    'sbg:fileTypes': LZ4
    type: File?
    'sbg:x': 888.5424194335938
    'sbg:y': 107
steps:
  - id: TotalSegmentatorOneVmWorkflow
    in:
      - id: s5cmdUrls
        source: s5cmdUrls
      - id: dicomToNiftiConverterTool
        source: dicomToNiftiConverterTool
        valueFrom: '"dcm2niix"'
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
    run:
      class: CommandLineTool
      cwlVersion: v1.2
      $namespaces:
        sbg: 'https://sevenbridges.com'
      id: _total_segmentator_one_vm_workflow
      baseCommand:
        - wget
        - https://raw.githubusercontent.com/ImagingDataCommons/Cloud-Resources-Workflows/main/Notebooks/Totalsegmentator/endToEndTotalSegmentatorNotebook.ipynb
        - '&&'
        - set
        - '-e'
        - '&&'
        - papermill
      inputs:
        - id: s5cmdUrls
          type: File?
          inputBinding:
            shellQuote: false
            position: 3
        - id: converterType
          type: string?
          inputBinding:
            shellQuote: true
            position: 2
      outputs:
        - id: endToEndTotalSegmentatorOutputJupyterNotebook
          type: File?
          outputBinding:
            glob: endToEndTotalSegmentatorOutputJupyterNotebook.ipynb
          'sbg:fileTypes': IPYNB
        - id: dicomsegAndRadiomicsSR_CompressedFiles
          type: File?
          outputBinding:
            glob: dicomsegAndRadiomicsSR_DICOMsegFiles.tar.lz4
          'sbg:fileTypes': LZ4
        - id: pyradiomicsRadiomicsFeatures
          type: File?
          outputBinding:
            glob: pyradiomicsRadiomicsFeatures.tar.lz4
          'sbg:fileTypes': LZ4
        - id: structuredReportsDICOM
          type: File?
          outputBinding:
            glob: structuredReportsDICOM.tar.lz4
          'sbg:fileTypes': LZ4
        - id: structuredReportsJSON
          type: File?
          outputBinding:
            glob: structuredReportsJSON.tar.lz4
          'sbg:fileTypes': LZ4
        - id: endToEndTotalSegmentator_UsageMetrics
          type: File?
          outputBinding:
            glob: endToEndTotalSegmentator_UsageMetrics.lz4
          'sbg:fileTypes': LZ4
        - id: dicomsegAndRadiomicsSR_RadiomicsErrors
          type: File?
          outputBinding:
            glob: radiomics_error_file.txt
          'sbg:fileTypes': TXT
        - id: dicomsegAndRadiomicsSR_SRErrors
          type: File?
          outputBinding:
            glob: sr_error_file.txt
          'sbg:fileTypes': TXT
        - id: dcm2niixErrors
          type: File?
          outputBinding:
            glob: error_file.txt
          'sbg:fileTypes': TXT
        - id: totalsegmentatorErrors
          type: File?
          outputBinding:
            glob: totalsegmentator_errors.txt
        - id: dicomSegErrors
          type: File?
          outputBinding:
            glob: itkimage2segimage_error_file.txt
      label: TotalSegmentatorEndtoEnd
      arguments:
        - prefix: '-p'
          shellQuote: false
          position: 2
          valueFrom: converterType
        - prefix: '-p'
          shellQuote: false
          position: 3
          valueFrom: csvFilePath
        - prefix: ''
          shellQuote: false
          position: 5
          valueFrom: endToEndTotalSegmentatorNotebook.ipynb
        - prefix: ''
          shellQuote: false
          position: 6
          valueFrom: endToEndTotalSegmentatorOutputJupyterNotebook.ipynb
      requirements:
        - class: ShellCommandRequirement
        - class: LoadListingRequirement
        - class: DockerRequirement
          dockerPull: imagingdatacommons/download_convert_inference_totalseg_radiomics
        - class: InlineJavascriptRequirement
      hints:
        - class: 'sbg:AWSInstanceType'
          value: g4dn.xlarge;ebs-gp2;25
      'sbg:x': 259.817138671875
      'sbg:y': 346.5
    label: TotalSegmentatorEndtoEnd
    'sbg:x': 259.817138671875
    'sbg:y': 465
requirements:
  - class: InlineJavascriptRequirement
  - class: StepInputExpressionRequirement