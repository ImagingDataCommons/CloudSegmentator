# Example case for a segmentation figure

One CT series from the case study 2 cohort, with all 12 segmentations produced by the runs and
their SR measurement objects. Downloaded 30 Oct 2026 for preparing a figure. The DICOM files are
git-ignored (~0.5 GB); this README and the scripts that make [the figure](#the-figure) are committed.

## The case

| | |
|---|---|
| Collection | `cptac_stad` (CPTAC-STAD, stomach adenocarcinoma), CC BY 4.0 |
| Patient | C3L-08169 |
| StudyInstanceUID | `1.3.6.1.4.1.14519.5.2.1.2099.3754.796339422254487721250055856078` |
| SeriesInstanceUID | `1.3.6.1.4.1.14519.5.2.1.2099.3754.960969117456598186449044876912` |
| Series | "Arterial Body 1.0 CE 1.0 thorax CE": contrast-enhanced chest/abdomen/pelvis, arterial phase, 1.0 mm slices, 982 slices, 518 MB |
| Viewer | [IDC viewer (CT only)](https://viewer.imaging.datacommons.cancer.gov/v3/viewer/?StudyInstanceUIDs=1.3.6.1.4.1.14519.5.2.1.2099.3754.796339422254487721250055856078&initialSeriesInstanceUID=1.3.6.1.4.1.14519.5.2.1.2099.3754.960969117456598186449044876912) |

**Why this one.** The candidates were the series that have all 12 SEGs, ranked by total
segment count in `idc-external-031.not_a_challenge.idc_segmentations`. The series ranked higher
were mostly low-dose PET/CT attenuation-correction scans of 3–3.75 mm, which look poor in print.
This is the highest-ranked series that is diagnostic, contrast-enhanced and thin-slice (238
segments). IDC itself holds no other segmentations of it (`seg_index`, v25).

## Files

- `ct/`: the CT series from IDC, files named by CRDC instance UUID
- `seg_sr/`: from `gs://idc-not-a-challenge/cptac_cmb_2026_10_14/<SeriesInstanceUID>/`; `<model>_0.dcm` is
  the SEG, `<model>_0_sr.dcm` the SR

| Model | Segments |
|---|---|
| `total` (TotalSegmentator) | 115 |
| `lung_vessels` (TotalSegmentator) | 4 |
| `clin_ct_body` (MOOSE) | 4 |
| `clin_ct_body_composition` (MOOSE) | 3 |
| `clin_ct_cardiac` (MOOSE) | 13 |
| `clin_ct_digestive` (MOOSE) | 4 |
| `clin_ct_lungs` (MOOSE) | 5 |
| `clin_ct_muscles` (MOOSE) | 10 |
| `clin_ct_organs` (MOOSE) | 19 |
| `clin_ct_peripheral_bones` (MOOSE) | 9 |
| `clin_ct_ribs` (MOOSE) | 25 |
| `clin_ct_vertebrae` (MOOSE) | 27 |

In `lung_vessels`, segments 1 and 2 are both labelled and coded "Trachea and bronchus" (SCT
110726009). Segment 1 is TotalSegmentator's `lung_airways`; segment 2 is `lung_airways_wall`, the
airway wall. Label them that way in a legend; the two are distinguishable in the SEG only by
display colour.

This affects the whole run, not just this case: in BigQuery, all 2,880 `lung_vessels` SEGs that
contain both airway segments carry the duplicate (2,938 SEGs in all; the rest lack one or both).
The cause is `workflows/models/totalseg/resources/snomed_mapping.csv`, which
has coded both classes this way since `45bb2b9` (1 Sep 2026). The not-a-challenge repo had
already recoded the wall as FMA 86618 "Wall of tracheobronchial tree" (`6ec7b1d`, 28 May 2026),
but that fix had not reached CloudSegmentator when this was checked on 30 Oct 2026;
[#78](https://github.com/ImagingDataCommons/CloudSegmentator/pull/78) brings it over.

## Re-download

```
S=1.3.6.1.4.1.14519.5.2.1.2099.3754.960969117456598186449044876912
gcloud storage cp "gs://idc-not-a-challenge/cptac_cmb_2026_10_14/$S/*" paper/example-case/seg_sr/
idc download $S --download-dir paper/example-case/ct --dir-template ""
```

`gsutil -m cp` stalled when this was made; use `gcloud storage cp`.

## The figure

`../out/cs2-sample-result.png` (2919 × 678 px): a coronal CT slice and all 12 segmentations as
unsmoothed 3D surfaces, side by side, each labelled with its model and grouped by tool. Made
30 Oct 2026. Its keyword is `cs2-sample-result`, the case study 2 counterpart of
`sample-result`.

`../out/cs2-sample-result_two-rows.png` (2919 × 2476 px) is the same scene in two rows: the CT,
TotalSegmentator and the first three MOOSE models above, the other seven MOOSE models below.
Each model has about twice the pixels of the one-row version, and the labels are larger (40 px
against 26), so it suits a full-width figure better. It is the version in the manuscript, as
the bottom-left panel of Figure 8, which is why `file` is set to `cs2-sample-result_two-rows`
in [`figures.csv`](../figures.csv).

| File | Role |
|---|---|
| `slicer_scene.py` | Runs inside 3D Slicer: loads the CT and SEGs, builds the surfaces and the CT plane, lays out the rows, captures the 3D view |
| `make_figure.py` | Drives `slicer_scene.py` step by step through the Slicer MCP server, then labels the captures |
| `annotate.py` | Crops each capture, draws the labels and stacks the rows; needs no Slicer |
| `../out/cs2-sample-result_raw.{png,json}` | The unlabelled capture of the one-row figure and where each model sits in it, for relabelling without Slicer |
| `../out/cs2-sample-result_two-rows_raw{1,2}.{png,json}` | The same for each row of the two-row figure |

### Rebuilding it

1. Start 3D Slicer. The figure was made with 5.11.0-2026-05-02 (preview), whose DICOM SEG
   loader is built in and calls dcmqi `segimage2itkimage --mergeSegments`.
2. In Slicer's Python console, start the MCP server from
   [slicer-skill](https://github.com/pieper/slicer-skill) (`6e73a3a` was used), then allow
   access when Slicer asks:
   ```python
   exec(open("/path/to/slicer-skill/slicer-mcp-server.py").read())
   ```
3. Run, pointing at wherever `ct/` and `seg_sr/` are (default: this directory), with
   `--layout two-rows` for the two-row figure:
   ```
   uv run paper/example-case/make_figure.py --case-dir ~/Downloads/example-case
   ```

Each step finds the nodes the previous ones made, so a step can be rerun on its own, and models
already loaded are not loaded again; with everything loaded, a run takes under a minute. The
pixel size of a capture is that of the 3D view, so it depends on the size of Slicer's window,
on a 13-inch MacBook Pro with the module panel hidden during the capture: 2974 × 976 device
pixels for the one-row figure, 2974 × 1252 for the two-row one. The view size also changes the
background a little, because the gradient spans the view: the one-row figure rebuilt in the
taller view has the same geometry but background pixels up to 11 levels different.

Measured on that machine (2020, Intel i5, 32 GB): converting `total` (17,215 frames) takes
3.3 min and peaks at 1.9 GB in dcmqi; the other 11 SEGs together load in about 3.5 min; the
unsmoothed surfaces of `total` take 108 s. Slicer peaked at 7.3 GB. The scene holds 238 segments
and about 26 million triangles.

### Settings

| Setting | Value | Why |
|---|---|---|
| Surface smoothing | 0 | Show the voxel output as the models produced it |
| CT slice | Coronal, y = −10 mm (RAS; slice j = 265), W 400 / L 40, cropped left–right to the `clin_ct_body` outline ± 10 mm | Of five levels compared (y = 20, 0, −10, −20, −35 mm), the one with heart, liver, spleen, stomach, both kidneys, spine, pelvis and femoral heads in one plane |
| Rotation | 30° about the S–I axis (patient right towards the viewer), then 25° tipping the top towards the viewer, about one centre, (−1, 14, −1074) mm, for every model and the CT plane | `clin_ct_body_composition` is a thin axial slab and only an edge from the front; a shared centre keeps anatomy roughly level across models |
| Layout | Models shifted along R–L, 40 mm apart; camera anterior and orthographic | Rotating the camera instead would let each model's depth push it into its neighbours |
| Two rows | Split after `clin_ct_cardiac`, keeping the one-row order; second row 40 mm inferior to the first; each row captured on its own, the other hidden, at one scale for both | This split makes the rows the same width (2422 and 2416 mm); capturing both rows in one view would give each model about half the pixels |
| Background | Slicer's default 3D gradient | |

How it is done, where that is not obvious:

- The CT is a plane model textured with the slice, not a slice view shown in 3D, whose size and
  resolution follow the layout.
- The capture scale factor does not work in Slicer
  ([forum, 2023](https://discourse.slicer.org/t/29341)), and the offscreen-rendering workaround
  there can crash Slicer, so the only way to more pixels is a larger 3D view. SlicerMorph's
  HiResScreenCapture module is the alternative; it was not tried.
- Labels are positioned from where Slicer's camera puts each model. MOOSE models are labelled
  without their `clin_ct_` prefix, which the bracket gives.
- Loading goes through a temporary DICOM database, leaving Slicer's own database untouched.

## Citation

- National Cancer Institute Clinical Proteomic Tumor Analysis Consortium (CPTAC). *The Clinical
  Proteomic Tumor Analysis Consortium Stomach Adenocarcinoma Collection (CPTAC-STAD)* (Version 1)
  [Dataset]. The Cancer Imaging Archive. https://doi.org/10.7937/JW9A-8K71
- The IDC paper: Fedorov et al., *RadioGraphics* 43(12), 2023. https://doi.org/10.1148/rg.230180
