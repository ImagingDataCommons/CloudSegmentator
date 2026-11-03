# /// script
# requires-python = ">=3.11"
# dependencies = ["pandas>=2.2", "numpy", "idc-index==0.13.4", "idc-index-data==25.0.5"]
# ///
"""Count the CT, MR and PT image series in IDC that have anatomy segmented, and size
what remains for CloudSegmentator after case studies 1 (NLST) and 2 (CMB/CPTAC).

    uv run paper/build_anatomy_coverage.py              # no credentials
    uv run paper/build_anatomy_coverage.py --refresh-cs2  # re-read case study 2 from BigQuery

Whole-body anatomy is TotalSegmentator in IDC (`totalsegmentator_ct_segmentations`) or a
case study 2 output. Case study 2 is not in IDC: its source series are the
ReferencedSeriesSequence of the SEGs in idc-external-031.not_a_challenge.idc-segmentations-20261014,
cached in paper/data/cs2_output_series.csv.gz. Any other IDC SEG with an "Anatomical
Structure" segment is targeted anatomy. Everything else comes from idc-index (IDC v25).

Writes paper/data/remaining_series.csv.gz, one row per series that is segmentable and has
no whole-body anatomy, and prints the coverage counts.
"""

import subprocess
import sys
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd
from idc_index import IDCClient

DATA = Path(__file__).parent / "data"
CS2_TABLE = "idc-external-031.not_a_challenge.idc-segmentations-20261014"
TS_IDC = "totalsegmentator_ct_segmentations"
# "Tissue" is left out: it holds lesions (fdg_pet_ct_lesions) as well as normal tissue
ANATOMY = ["Anatomical Structure", "Anatomical Stucture"]
NATIVE = {"CT": "CT Image Storage", "MR": "MR Image Storage",
          "PT": "Positron Emission Tomography Image Storage"}
MIN_SLICES = 50       # as in nlstCohort.sql and nonNlstCohort.sql
RESAMPLED_MM = 1.5    # TotalSegmentator's working resolution for `total`
NLST_MAX_MVOX = 29    # largest NLST series at 1.5 mm
# Case study 2 per series: billed cost and median inference minutes
CS2_COST = {"TotalSegmentator": 0.0259, "MOOSE": 0.0317}
CS2_INFER_MIN = {"TotalSegmentator": 3.2, "MOOSE": 4.6}


def cs2_outputs(refresh):
    path = DATA / "cs2_output_series.csv.gz"
    if refresh or not path.exists():
        sql = (f"SELECT DISTINCT r.SeriesInstanceUID FROM `{CS2_TABLE}` t, "
               "UNNEST(t.ReferencedSeriesSequence) r WHERE t.Modality = 'SEG' ORDER BY 1")
        out = subprocess.run(["bq", "--project_id=idc-external-031", "query", "--use_legacy_sql=false",
                              "--format=csv", "--max_rows=100000", sql],
                             check=True, capture_output=True, text=True).stdout
        pd.read_csv(StringIO(out)).to_csv(path, index=False)
    return pd.read_csv(path)


def plane(iop):
    if not isinstance(iop, (list, np.ndarray)) or len(iop) != 6:
        return None
    normal = np.cross(np.array(iop[:3]), np.array(iop[3:]))
    return ["sagittal", "coronal", "axial"][int(np.argmax(np.abs(normal)))]


def tb(mb):
    return round(mb.sum() / 1e6, 2)


def summary(x):
    return pd.Series({
        "series": len(x), "studies": x.StudyInstanceUID.nunique(),
        "patients": (x.collection_id + "/" + x.PatientID).nunique(),
        "collections": x.collection_id.nunique(), "TB": tb(x.series_size_MB),
        "axial": (x.plane == "axial").sum(), "new_in_v25": (x.series_init_idc_version == 25).sum(),
        "targeted_anatomy": x.targeted.sum(), "CC_BY_NC": x.license_short_name.str.contains("NC").sum()})


def main():
    cs2 = cs2_outputs("--refresh-cs2" in sys.argv)
    idc = IDCClient()
    for name in ("seg_index", "rtstruct_index", "volume_geometry_index", "ct_index", "mr_index",
                 "pt_index", "collections_index"):
        idc.fetch_index(name)
    idc._duckdb_conn.register("cs2", cs2)
    d = idc.sql_query(f"""
        WITH anat AS (
          SELECT s.segmented_SeriesInstanceUID AS SeriesInstanceUID,
                 bool_or(COALESCE(i.analysis_result_id, '') = '{TS_IDC}') AS ts_idc,
                 bool_or(COALESCE(i.analysis_result_id, '') <> '{TS_IDC}') AS targeted
          FROM seg_index s JOIN index i USING (SeriesInstanceUID)
          WHERE s.segmented_SeriesInstanceUID IS NOT NULL
            AND list_has_any(s.SegmentedPropertyCategory_CodeMeanings, {ANATOMY})
          GROUP BY 1)
        SELECT i.collection_id, i.PatientID, i.StudyInstanceUID, i.SeriesInstanceUID, i.Modality,
               i.sop_class_name, i.instanceCount, i.series_size_MB, i.series_init_idc_version,
               i.license_short_name, i.BodyPartExamined, i.TransferSyntaxUID,
               CASE WHEN i.collection_id = 'nlst' THEN 'NLST'
                    WHEN i.collection_id LIKE '%cmb%' OR i.collection_id LIKE '%cptac%' THEN 'CMB/CPTAC'
                    ELSE 'other' END AS grp,
               COALESCE(a.ts_idc, false) AS ts_idc, COALESCE(a.targeted, false) AS targeted,
               cs2.SeriesInstanceUID IS NOT NULL AS cs2,
               COALESCE(g.regularly_spaced_3d_volume, false) AS regular, g.SeriesInstanceUID IS NOT NULL AS in_geometry,
               g.ImageOrientationPatient AS iop, g.obliquity_degrees, g.slice_spacing_mm,
               COALESCE(list_contains(c.ImageType, 'LOCALIZER'), false) AS localizer,
               COALESCE(c.Rows, m.Rows, p.Rows) AS rows, COALESCE(c.Columns, m.Columns, p.Columns) AS cols,
               COALESCE(c.PixelSpacing_row_mm, m.PixelSpacing_row_mm, p.PixelSpacing_row_mm) AS ps_row,
               COALESCE(c.PixelSpacing_col_mm, m.PixelSpacing_col_mm, p.PixelSpacing_col_mm) AS ps_col,
               col.species, CAST(col.cancer_types AS VARCHAR) || ' ' || CAST(col.tumor_locations AS VARCHAR) AS col_desc
        FROM index i
        LEFT JOIN anat a USING (SeriesInstanceUID) LEFT JOIN cs2 USING (SeriesInstanceUID)
        LEFT JOIN volume_geometry_index g USING (SeriesInstanceUID)
        LEFT JOIN ct_index c USING (SeriesInstanceUID) LEFT JOIN mr_index m USING (SeriesInstanceUID)
        LEFT JOIN pt_index p USING (SeriesInstanceUID)
        LEFT JOIN collections_index col USING (collection_id)
        WHERE i.Modality IN ('CT', 'MR', 'PT') AND i.analysis_result_id IS NULL""")
    print(f"IDC {idc.get_idc_version()}: {len(d):,} CT/MR/PT image series, {tb(d.series_size_MB)} TB; "
          f"case study 2 outputs matched {d.cs2.sum():,} of {len(cs2):,}")

    rt_organ = idc.sql_query("""SELECT DISTINCT referenced_SeriesInstanceUID FROM rtstruct_index
                                WHERE list_contains(RTROIInterpretedTypes, 'ORGAN')""")
    d["rt_organ"] = d.SeriesInstanceUID.isin(rt_organ.referenced_SeriesInstanceUID)
    d["wholebody"] = d.ts_idc | d.cs2
    d["coverage"] = np.select([d.wholebody, d.targeted], ["whole-body", "targeted only"], "none")
    d["plane"] = d.iop.map(plane)
    d["native"] = d.sop_class_name == d.Modality.map(NATIVE)
    d["eligible"] = d.native & ~d.localizer & d.regular & (d.instanceCount >= MIN_SLICES)
    # species is not enough: phantom_fda, among others, is recorded as Human
    d["non_patient"] = (d.species.fillna("") != "Human") | d.col_desc.str.contains("Phantom")
    d["mvox_native"] = d.rows * d.cols * d.instanceCount / 1e6
    d["mvox_1p5mm"] = (d.rows * d.ps_row * d.cols * d.ps_col * (d.instanceCount - 1) * d.slice_spacing_mm
                       / RESAMPLED_MM**3 / 1e6)

    print("\n== Coverage")
    cov = d.groupby(["Modality", "coverage"]).agg(series=("SeriesInstanceUID", "size"), TB=("series_size_MB", tb))
    cov["pct"] = (100 * cov.series / cov.groupby(level=0).series.transform("sum")).round(1)
    print(cov.to_string())
    print(d.groupby("coverage").agg(series=("SeriesInstanceUID", "size"), TB=("series_size_MB", tb)).to_string())
    print(d.groupby(["grp", "Modality", "coverage"]).size().to_string())
    print("No anatomy SEG but an RTSTRUCT with an ORGAN ROI:",
          d[(d.coverage == "none") & d.rt_organ].groupby("Modality").size().to_dict())

    print("\n== Rule against the case-study cohorts (whole-body series passing it)")
    print(d[d.wholebody].groupby("grp").agg(series=("eligible", "size"), eligible=("eligible", "sum")).to_string())

    print("\n== Why series without whole-body anatomy are not segmentable")
    rest = d[~d.wholebody & ~d.eligible]
    why = np.select([~rest.native, rest.localizer, ~rest.in_geometry, ~rest.regular],
                    ["secondary capture or raw data", "localizer", "not in volume_geometry_index",
                     "not a regular 3D volume"], f"fewer than {MIN_SLICES} slices")
    print(rest.assign(why=why).groupby(["Modality", "why"]).agg(
        series=("SeriesInstanceUID", "size"), TB=("series_size_MB", tb)).to_string())

    todo = d[~d.wholebody & d.eligible]
    print(f"\n== Phantom and animal series left out: {(todo.non_patient).sum():,}")
    labelled_human = d[d.non_patient & (d.species == "Human")].collection_id.unique()
    print(f"non-patient collections recorded as Human: {len(labelled_human)}", sorted(labelled_human))
    print(todo[todo.non_patient].groupby(["Modality", "collection_id"]).size()
          .sort_values(ascending=False).head(12).to_string())
    todo = todo[~todo.non_patient]

    print("\n== Remaining")
    print(todo.groupby(["Modality", "grp"]).apply(summary).to_string())
    print(todo.groupby("Modality").apply(summary).to_string())
    patient_mr = d[~d.wholebody & ~d.non_patient & d.native & d.regular & (d.Modality == "MR")]
    print(f"MR with at least 20 slices: {(patient_mr.instanceCount >= 20).sum():,}")
    elig = d[d.eligible & ~d.non_patient]
    print("Segmentable patient series that have whole-body anatomy:")
    print(elig.groupby("Modality").agg(segmentable=("wholebody", "size"), done=("wholebody", "sum"))
          .assign(pct=lambda t: (100 * t.done / t.segmentable).round(1)).to_string())

    nlst = todo[todo.grp == "NLST"]
    jpeg = nlst.TransferSyntaxUID.str.contains(r"1\.2\.840\.10008\.1\.2\.4\.(?:51|70)\b")
    print(f"NLST: {len(nlst)} left, {jpeg.sum()} of them JPEG-compressed")

    print("\n== CMB/CPTAC CT outside the case study 2 outputs")
    cc = todo[(todo.grp == "CMB/CPTAC") & (todo.Modality == "CT")]
    axial, new = cc.plane == "axial", cc.series_init_idc_version == 25
    runs = set()
    for name in ("cs2_peak_memory", "cs2_inference_failures"):
        runs |= set(pd.read_csv(DATA / f"{name}.csv.gz").SeriesInstanceUID)
    old_axial = cc[axial & ~new]
    no_output = old_axial.SeriesInstanceUID.isin(runs - set(cs2.SeriesInstanceUID))
    tilt = old_axial[~no_output].obliquity_degrees
    print(f"axial, new in v25 {(axial & new).sum()}; sagittal or coronal {(~axial).sum()} "
          f"({(~axial & new).sum()} new in v25); axial from before v25 {len(old_axial)}, of them "
          f"{no_output.sum()} run series with no output; of the other {len(tilt)}, "
          f"{(tilt >= 0.1).sum()} tilted {tilt[tilt >= 0.1].min():.2f}-{tilt.max():.2f} degrees")

    def top(x):
        t = x.groupby("collection_id").agg(series=("SeriesInstanceUID", "size"), patients=("PatientID", "nunique"))
        return t.sort_values("series", ascending=False).head(12).to_string()
    ct, mr, pt = (todo[todo.Modality == m] for m in ("CT", "MR", "PT"))
    print("\n== CT by collection\n" + top(ct))
    print("\n== MR by collection\n" + top(mr))
    body = mr.BodyPartExamined.fillna("(none)").str.upper().value_counts(normalize=True).head(4)
    print("MR BodyPartExamined:", (100 * body).round(1).to_dict())
    print("MR CC BY-NC by collection:", mr[mr.license_short_name.str.contains("NC")].collection_id.value_counts().to_dict())
    print("\n== PT by collection\n" + top(pt))

    print("\n== CT size and cost")
    geo = pd.read_csv(DATA / "cs2_series_geometry.csv.gz")
    failed_at = geo[geo.memory_failures.fillna("").str.contains("TotalSegmentator total")].mvox_1p5mm.min()
    print(f"mean native Mvox {ct.mvox_native.mean():.1f} (case study 2 cohort {geo.mvox_native.mean():.1f}); "
          f"above {NLST_MAX_MVOX} Mvox at 1.5 mm {(ct.mvox_1p5mm > NLST_MAX_MVOX).sum():,}; "
          f"at or above {failed_at:.1f} (smallest where case study 2 `total` failed) {(ct.mvox_1p5mm >= failed_at).sum():,}")
    for model in CS2_COST:
        print(f"{model}: ${len(ct) * CS2_COST[model]:,.0f}, "
              f"{len(ct) * CS2_INFER_MIN[model] / 60:,.0f} GPU-hours of median inference")

    print("\n== PET studies")
    studies = pt.StudyInstanceUID.drop_duplicates()
    done = set(d[(d.Modality == "CT") & d.wholebody].StudyInstanceUID)
    print(f"{len(studies):,} studies; with a remaining segmentable CT {studies.isin(set(ct.StudyInstanceUID)).sum():,}; "
          f"with a CT already done {studies.isin(done).sum():,}")

    cols = ["collection_id", "PatientID", "StudyInstanceUID", "SeriesInstanceUID", "Modality", "plane",
            "instanceCount", "series_size_MB", "mvox_1p5mm", "series_init_idc_version", "license_short_name",
            "targeted"]
    todo[cols].round({"series_size_MB": 2, "mvox_1p5mm": 2}).sort_values(cols[:4]).to_csv(
        DATA / "remaining_series.csv.gz", index=False)
    print(f"\nwrote {len(todo):,} rows to {DATA / 'remaining_series.csv.gz'}")


if __name__ == "__main__":
    main()
