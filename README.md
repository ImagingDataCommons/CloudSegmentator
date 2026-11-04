# CloudSegmentator

CloudSegmentator runs AI segmentation models on images from the
[NCI Imaging Data Commons](https://imaging.datacommons.cancer.gov/) (IDC) on cloud VMs, and
converts the results to standard DICOM that can be shared back through IDC:

- **Segmentations** of anatomy, as DICOM Segmentation (SEG) objects with each structure coded
  in SNOMED CT.
- **Radiomics features** of each segmented structure, as JSON and as DICOM Structured Reports
  (TID 1500).

The models are [TotalSegmentator](https://github.com/wasserth/TotalSegmentator) and
[MOOSE](https://github.com/ENHANCE-PET/MOOSE). The workflows are written in WDL, run on
[Terra](https://terra.bio), and are published on
[Dockstore](https://dockstore.org/organizations/ImagingDataCommons/collections/CloudSegmentator).
They read public IDC data directly, or DICOM from a private Google Cloud Storage bucket.

## Results

| When | Models and workflow | Images | Results |
|---|---|---|---|
| 2023–24 | TotalSegmentator; older workflow, release [v1.2.0](https://github.com/ImagingDataCommons/CloudSegmentator/releases/tag/v1.2.0) | 126,088 CT series from NLST | In IDC as [TotalSegmentator-CT-Segmentations](https://doi.org/10.5281/zenodo.8347011) |
| Oct 2026 | TotalSegmentator and MOOSE; harmonized workflow | 3,059 CT series from CMB and CPTAC | On [Zenodo](https://doi.org/10.5281/zenodo.23825858), pending ingestion into IDC |

## Which workflow to use

For new runs, use the **harmonized workflow**. One WDL runs every supported model, and only the
inference step is model-specific, so adding a model takes one notebook and one Docker image.

| Dockstore workflows | Models | Status | Docs |
|---|---|---|---|
| `SegmentatorTwoVmWorkflowOnTerra` | TotalSegmentator 2.18.0 (`total`, `lung_vessels`); MOOSE (10 `clin_ct_*` models) | Current. Validated on Terra in Sep 2026; used for the 2026 run | [Harmonized](workflows/harmonized/Docs/README.md) |
| `TotalSegmentator*VmWorkflowOnTerra` | TotalSegmentator 1.5.6 | Older; used for the NLST run | [TotalSegmentator](workflows/TotalSegmentator/Docs/README.md) |
| `Moose*VmWorkflowOnTerra` | MOOSE | Older; replaced by the harmonized workflow | [MOOSE](workflows/MOOSE/Docs/README.md) |

The older workflows stay in the repository and on Dockstore so that past runs can be reproduced.
Open issues with the harmonized workflow, such as its untested import into a DICOM store, are
listed under [Known gaps](workflows/harmonized/Docs/README.md#known-gaps).

## How the harmonized workflow works

Each workflow instance processes one batch of series on two VMs. Every step is a Jupyter
notebook, run by papermill inside a Docker image.

```
GPU VM (preemptible)                         CPU VM
  convert     DICOM → NIfTI (dcm2niix)         output conversion
  inference   NIfTI → label maps        ──▶      NIfTI → DICOM SEG (dcmqi)
              (one notebook and one              radiomics (pyradiomics or Radiomics.jl)
               image per model)                  DICOM SR (TID 1500)
                                                 optional upload to GCS and a DICOM store
```

Finished work is checkpointed to a bucket, so a preempted VM resumes where it stopped. Each run
records per-step timings, peak memory and errors per series, which
[`util/executionAnalytics`](util/executionAnalytics/README.md) uses to measure what a run cost
and to predict the cost of the next one.

## Running on Terra

You need a Terra account and a Google Cloud billing project. If Terra or Dockstore is new to you,
start with [Terra's guides](https://support.terra.bio/hc/en-us/categories/360005881492-Getting-Started)
and [Dockstore's](https://docs.dockstore.org/en/stable/getting-started/getting-started.html).

1. Open [`SegmentatorTwoVmWorkflowOnTerra`](https://dockstore.org/workflows/github.com/ImagingDataCommons/CloudSegmentator/SegmentatorTwoVmWorkflowOnTerra:main)
   on Dockstore, choose **Launch with → Terra**, and pick a workspace.
2. Under **Data**, upload a data table with one row per batch and a `SeriesInstanceUIDs` column
   listing the IDC series in that batch.
   [`make_terra_manifest.py`](util/executionAnalytics/make_terra_manifest.py) builds one from
   an IDC cohort; [here is a sample](workflows/TotalSegmentator/Docs/sampleManifests/terra_data_table_manifest_2024_01_09_20_38.tsv).
3. Under **Workflows**, open the workflow, choose **Run workflow(s) with inputs defined by data
   table**, and select the table and the rows to run.
4. Under **Inputs**, upload the preset for a model ([MOOSE](workflows/models/moose/inputs.moose.json),
   [TotalSegmentator](workflows/models/totalseg/inputs.totalseg.json),
   [TotalSegmentator lung vessels](workflows/models/totalseg/inputs.totalseg_lung_vessels.json))
   and set `yamlListOfSeriesInstanceUIDs` to `this.SeriesInstanceUIDs`. Under **Outputs**,
   choose **Use defaults**, so the outputs are linked from the data table.
5. Click **Run analysis**.

To submit and monitor many batches from the command line, use [`util/terraOps`](util/terraOps),
described in [operations.md](workflows/harmonized/Docs/operations.md).

## Repository contents

| Path | Contents |
|---|---|
| [`workflows/harmonized/`](workflows/harmonized) | The harmonized workflow's WDL, and its docs: [overview and inputs](workflows/harmonized/Docs/README.md), [operations](workflows/harmonized/Docs/operations.md), [development](workflows/harmonized/Docs/development.md) |
| [`workflows/common/`](workflows/common) | Its shared notebooks (convert, output conversion), the base and output-conversion Dockerfiles, and the codes for radiomics features |
| [`workflows/models/`](workflows/models) | Per model: the inference notebook, Dockerfile, input presets and SNOMED overrides |
| [`workflows/TotalSegmentator/`](workflows/TotalSegmentator), [`workflows/MOOSE/`](workflows/MOOSE) | The older per-model workflows: WDL, notebooks, Dockerfiles, cohort queries |
| [`util/terraOps/`](util/terraOps) | Command-line tools to upload data tables, submit batches, watch them and check their outputs |
| [`util/executionAnalytics/`](util/executionAnalytics) | Measure what a Terra run cost; fit a cost model on a pilot and predict a larger run |
| `util/pricingOptimization/`, `util/downloadBenchmarking/`, `util/Monitoring/` | One-off notebooks and queries: GPU prices by region, download speed, GPU quota use |
| [`paper/`](paper) | Scripts and data behind the figures of the 2026 paper; every figure can be redrawn without credentials |
| [`.github/workflows/`](.github/workflows) | CI that builds the Docker images and pushes them to Docker Hub (`imagingdatacommons/cloudsegmentator-*` for the harmonized workflow) |
| [`AGENTS.md`](AGENTS.md), [`.claude/skills/`](.claude/skills) | Notes and procedures for coding agents |

## Citation

> Thiriveedhi VK, Krishnaswamy D, Clunie D, Pieper S, Kikinis R, Fedorov A. Cloud-based
> large-scale curation of medical imaging data using AI segmentation. *Research Square* (2024).
> https://doi.org/10.21203/rs.3.rs-4351526/v1

Release v1.2.0 is archived on Zenodo: https://doi.org/10.5281/zenodo.10712896. A paper covering
both runs is in preparation.

## License

Apache 2.0; see [LICENSE](LICENSE).
