{
  "class": "CommandLineTool",
  "cwlVersion": "v1.2",
  "$namespaces": {
    "sbg": "https://sevenbridges.com"
  },
  "baseCommand": [
    "wget",
    "https://raw.githubusercontent.com/vkt1414/Cloud-Resources-Workflows/main/Notebooks/Totalsegmentator/itkimage2segimageNotebook.ipynb",
    "&&",
    "set",
    "-e",
    "&&",
    "papermill"
  ],
  "inputs": [
    {
      "id": "dicomToNiftiConverterTool",
      "type": "string",
      "inputBinding": {
        "shellQuote": false,
        "position": 2
      }
    },
    {
      "id": "s5cmdUrls",
      "type": "File",
      "inputBinding": {
        "shellQuote": false,
        "position": 3
      }
    },
    {
      "id": "downloadDicomAndConvertAndInferenceTotalSegmentatorZipFile",
      "type": "File?"
    }
  ],
  "outputs": [
    {
      "id": "itkimage2segimageOutputJupyterNotebook",
      "type": "File?",
      "outputBinding": {
        "glob": "itkimage2segimageOutputJupyterNotebook.ipynb"
      },
      "sbg:fileTypes": "IPYNB"
    },
    {
      "id": "itkimage2segimageErrors",
      "type": "File?",
      "outputBinding": {
        "glob": "itkimage2segimage_error_file.txt"
      },
      "sbg:fileTypes": "txt"
    },
    {
      "id": "itkimage2segimageZipFile",
      "type": "File?",
      "outputBinding": {
        "glob": "itkimage2segimageZipFile.tar.lz4"
      },
      "sbg:fileTypes": "LZ4"
    },
    {
      "id": "itkimage2segimageUsageMetrics",
      "type": "File?",
      "outputBinding": {
        "glob": "itkimage2segimageUsageMetrics.lz4"
      },
      "sbg:fileTypes": "lz4"
    }
  ],
  "label": "itkimage2segimage",
  "arguments": [
    {
      "prefix": "-p",
      "shellQuote": false,
      "position": 2,
      "valueFrom": "converterType"
    },
    {
      "prefix": "-p",
      "shellQuote": false,
      "position": 3,
      "valueFrom": "csvFilePath"
    },
    {
      "prefix": "",
      "shellQuote": false,
      "position": 5,
      "valueFrom": "itkimage2segimageNotebook.ipynb"
    },
    {
      "prefix": "",
      "shellQuote": false,
      "position": 6,
      "valueFrom": "itkimage2segimageOutputJupyterNotebook.ipynb"
    }
  ],
  "requirements": [
    {
      "class": "ShellCommandRequirement"
    },
    {
      "class": "LoadListingRequirement"
    },
    {
      "class": "DockerRequirement",
      "dockerPull": "vamsithiriveedhi/totalsegmentator:task3_v2"
    },
    {
      "class": "InlineJavascriptRequirement"
    }
  ],
  "hints": [
    {
      "class": "sbg:AWSInstanceType",
      "value": "c5.large;ebs-gp2;10"
    }
  ],
  "sbg:projectName": "IDC",
  "sbg:revisionsInfo": [
    {
      "sbg:revision": 0,
      "sbg:modifiedBy": "vamsikrishna14",
      "sbg:modifiedOn": 1681762996,
      "sbg:revisionNotes": "Copy of vamsikrishna14/idc/example/16"
    },
    {
      "sbg:revision": 1,
      "sbg:modifiedBy": "vamsikrishna14",
      "sbg:modifiedOn": 1681763373,
      "sbg:revisionNotes": ""
    },
    {
      "sbg:revision": 2,
      "sbg:modifiedBy": "vamsikrishna14",
      "sbg:modifiedOn": 1681763535,
      "sbg:revisionNotes": ""
    },
    {
      "sbg:revision": 3,
      "sbg:modifiedBy": "vamsikrishna14",
      "sbg:modifiedOn": 1681763659,
      "sbg:revisionNotes": ""
    },
    {
      "sbg:revision": 4,
      "sbg:modifiedBy": "vamsikrishna14",
      "sbg:modifiedOn": 1681766623,
      "sbg:revisionNotes": ""
    },
    {
      "sbg:revision": 5,
      "sbg:modifiedBy": "vamsikrishna14",
      "sbg:modifiedOn": 1681769793,
      "sbg:revisionNotes": ""
    }
  ],
  "sbg:image_url": null,
  "sbg:appVersion": [
    "v1.2"
  ],
  "id": "https://cgc-api.sbgenomics.com/v2/apps/vamsikrishna14/idc/itkimage2segimage/5/raw/",
  "sbg:id": "vamsikrishna14/idc/itkimage2segimage/5",
  "sbg:revision": 5,
  "sbg:revisionNotes": "",
  "sbg:modifiedOn": 1681769793,
  "sbg:modifiedBy": "vamsikrishna14",
  "sbg:createdOn": 1681762996,
  "sbg:createdBy": "vamsikrishna14",
  "sbg:project": "vamsikrishna14/idc",
  "sbg:sbgMaintained": false,
  "sbg:validationErrors": [],
  "sbg:contributors": [
    "vamsikrishna14"
  ],
  "sbg:latestRevision": 5,
  "sbg:publisher": "sbg",
  "sbg:content_hash": "a86b07d445be62791fa65348bdadf74762645d405dd5d1f7cda894759f0355ec9",
  "sbg:workflowLanguage": "CWL"
}
