# TotalSegmentator workflows (older)

These workflows run TotalSegmentator 1.5.6 on IDC CT series, and convert the results to DICOM
SEG, pyradiomics features and DICOM SR. Release
[v1.2.0](https://github.com/ImagingDataCommons/CloudSegmentator/releases/tag/v1.2.0) of these
workflows produced the [TotalSegmentator-CT-Segmentations](https://doi.org/10.5281/zenodo.8347011)
results for 126,088 NLST series in 2023–24. For new runs, use the
[harmonized workflow](../../harmonized/Docs/README.md).

## Configurations

The work is split across one, two or three VMs. The NLST run used twoVM.

| Configuration | Dockstore workflow | What runs where |
|---|---|---|
| oneVM | `TotalSegmentatorOneVmWorkflowOnTerra` | everything on one GPU VM |
| twoVM | `TotalSegmentatortwoVmWorkflowOnTerra` | download, convert and inference on a GPU VM; SEG, radiomics and SR on a CPU VM ([diagram](architectureDiagrams/twoVM.png)) |
| threeVM | `TotalSegmentatorthreeVmWorkflowOnTerra` | download and convert, inference, and SEG/radiomics/SR on separate VMs ([diagram](architectureDiagrams/threeVM.png)) |

Which notebook and image each configuration uses is listed in
[Notebooks/README.md](../Notebooks/README.md) and [Dockerfiles/README.md](../Dockerfiles/README.md).
Two post-processing workflows prepare the results for BigQuery:
`perFrameFunctionalGroupSequenceExtractionOnTerra` extracts the per-frame functional groups of
each SEG to CSV, and `convertRadiomicsJsonToDataframeOnTerra` turns the radiomics JSON into a
table. The cohort queries are in [`sqlQueries/`](../sqlQueries).

CWL versions of the three configurations, for Seven Bridges CGC, are in
[`SevenBridges/`](../SevenBridges). They were not used or tested in the 2026 run; the
instructions for them are in the
[v1.2.0 README](https://github.com/ImagingDataCommons/CloudSegmentator/tree/v1.2.0#readme).

## Running on Terra

The steps are those in the root README's [Running on Terra](../../../README.md#running-on-terra),
with these differences:

- Import [`TotalSegmentatortwoVmWorkflowOnTerra`](https://dockstore.org/workflows/github.com/ImagingDataCommons/CloudSegmentator/TotalSegmentatortwoVmWorkflowOnTerra:main).
  To reproduce the NLST run, choose version `v1.2.0`.
- Use the [sample data table](sampleManifests/terra_data_table_manifest_2024_01_09_20_38.tsv);
  its root entity type begins with `twoVM_`.
- There is no preset. Set `yamlListOfSeriesInstanceUIDs` to `this.SeriesInstanceUIDs` and leave
  the other inputs empty.
