# /// script
# requires-python = ">=3.11"
# dependencies = ["pandas>=2.2"]
# ///
"""Count, for each structure segmented in IDC or in case study 2, the series it was
segmented in before case study 2 (every SEG in IDC v25 on a CT, MR or PET series), and
the case study 2 CT series that add to it.

    uv run paper/build_data_structures_idc.py

A structure is a segmented property type, as in build_data_structures_cs2.py, whose
case study 2 query this reuses: left and right merge, and a segment means the structure
was found. Legacy SNOMED RT codes join their SNOMED CT counterparts (SAME_AS). A series
is counted once per structure whatever the number of SEGs on it, so a case study 2
series adds to a structure only if no SEG in IDC already has it there. Needs `bq` with
read access to idc-external-031. Writes paper/data/idc_structures.csv.gz, one row per
structure, and idc_structures_totals.csv.gz, series with any segment.
"""

from pathlib import Path

from build_data_structures_cs2 import SEGMENTS, bq_csv

IDC = "bigquery-public-data.idc_v25"
DATA = Path(__file__).parent / "data"

# Codes for one concept, to a single key: legacy SNOMED RT codes to the SNOMED CT concept
# of the same meaning, the "MRSC" Breast of ACRIN 6698 and others to SNOMED CT's, and
# M-8FFFF, which QIBA uses for "Neoplasm" and no code system defines, to Neoplasm. Case
# study 2 codes gluteus maximus as 206007 (structure of) and TotalSegmentator in IDC as
# 181674001 (entire); the other muscles agree.
SAME_AS = {
    "SRT:T-32000": "SCT:80891009",   # Heart
    "SRT:T-71000": "SCT:64033007",   # Kidney
    "SRT:T-9200B": "SCT:41216001",   # Prostate
    "SRT:T-D05E4": "SCT:279706003",  # Peripheral zone of prostate
    "SRT:T-D820B": "SCT:40983000",   # Upper arm
    "SRT:T-D0050": "SCT:85756007",   # Tissue
    "SRT:G-A460": "SCT:17621005",    # Normal
    "SRT:M-01100": "SCT:52988006",   # Lesion
    "SRT:M-03000": "SCT:4147007",    # Mass
    "SRT:M-03010": "SCT:27925004",   # Nodule
    "SRT:M-80003": "SCT:86049000",   # Neoplasm, primary
    "SRT:M-8FFFF": "SCT:108369006",  # Neoplasm
    "MRSC:B-1000": "SCT:76752008",   # Breast
    "SCT:181674001": "SCT:206007",   # Gluteus maximus muscle
}
# Not a structure: the BAMF PET and kidney models label the rest of the image.
NOT_A_STRUCTURE = ["DCM:125040"]  # Background

# Every segment in IDC outside phantom collections, with the series it is on. The
# collection metadata names the phantoms (CT4Harmonization-Multicentric as "Liver
# Phantom"). Outside them, 1,030 SEGs in eight collections have no
# segmented_SeriesInstanceUID (read 30 Oct 2026); they are placed by frame of reference,
# each frame counting as one series. A frame of reference that no CT, MR or PET series in
# IDC has, or that series of two of them share (PET-CT), places nothing: 2 SEGs.
IDC_ALL = f"""
WITH
seg_instances AS (
  SELECT DISTINCT SOPInstanceUID, collection_id, analysis_result_id
  FROM `{IDC}.dicom_all`
  WHERE Modality = 'SEG' AND collection_id NOT IN (
    SELECT collection_id FROM `{IDC}.original_collections_metadata`
    WHERE REGEXP_CONTAINS(LOWER(CONCAT(CancerTypes, ' ', TumorLocations)), 'phantom'))
),
series AS (SELECT DISTINCT SeriesInstanceUID, Modality FROM `{IDC}.dicom_all`),
frames AS (
  SELECT FrameOfReferenceUID, ANY_VALUE(Modality) AS Modality
  FROM (SELECT DISTINCT FrameOfReferenceUID, Modality FROM `{IDC}.dicom_all`
        WHERE Modality IN ('CT', 'MR', 'PT') AND FrameOfReferenceUID IS NOT NULL)
  GROUP BY 1 HAVING COUNT(*) = 1
),
same_as AS (
  SELECT * FROM UNNEST([{", ".join(f"STRUCT('{a}' AS code, '{b}' AS key)"
                                   for a, b in SAME_AS.items())}])
),
segs AS (
  SELECT
    s.SOPInstanceUID AS sop,
    s.SegmentNumber AS segment,
    COALESCE(r.SeriesInstanceUID, CONCAT('FoR:', f.FrameOfReferenceUID)) AS series,
    COALESCE(r.Modality, f.Modality) AS modality,
    s.segmented_SeriesInstanceUID IS NULL AS by_frame,
    CONCAT(s.SegmentedPropertyType.CodingSchemeDesignator, ':',
           s.SegmentedPropertyType.CodeValue) AS code,
    s.SegmentedPropertyType.CodeMeaning AS meaning,
    s.AnatomicRegion.CodeMeaning AS region,
    COALESCE(i.analysis_result_id, i.collection_id) AS source,
    IFNULL(i.analysis_result_id = 'totalsegmentator_ct_segmentations', FALSE) AS cs1
  FROM `{IDC}.segmentations` s
  JOIN seg_instances i USING (SOPInstanceUID)
  LEFT JOIN series r ON r.SeriesInstanceUID = s.segmented_SeriesInstanceUID
  LEFT JOIN frames f
    ON f.FrameOfReferenceUID = s.FrameOfReferenceUID AND s.segmented_SeriesInstanceUID IS NULL
)
SELECT segs.*, COALESCE(m.key, code) AS key
FROM segs LEFT JOIN same_as m USING (code)
"""

# Then on CT, MR and PET only, which leaves out slide microscopy; and structures only.
IDC_SEGMENTS = f"""
SELECT * FROM ({IDC_ALL})
WHERE modality IN ('CT', 'MR', 'PT') AND code NOT IN ({", ".join(f"'{c}'" for c in NOT_A_STRUCTURE)})
"""

# Each (structure, series) once, flagged by where it was segmented. Case study 2 is CT.
PAIRS = f"""
idc AS ({IDC_SEGMENTS}),
cs2 AS (SELECT * EXCEPT (code), CONCAT('SCT:', code) AS code, CONCAT('SCT:', code) AS key
        FROM ({SEGMENTS})),
pairs AS (
  SELECT key, series, IFNULL(modality, 'CT') AS modality, IFNULL(in_idc, FALSE) AS in_idc,
         IFNULL(cs1, FALSE) AS cs1, IFNULL(in_cs2, FALSE) AS in_cs2
  FROM (SELECT key, series, ANY_VALUE(modality) AS modality, TRUE AS in_idc,
               LOGICAL_OR(cs1) AS cs1
        FROM idc GROUP BY 1, 2)
  FULL JOIN (SELECT DISTINCT key, ct AS series, TRUE AS in_cs2 FROM cs2) USING (key, series)
)
"""

STRUCTURES = f"""
WITH {PAIRS},
counts AS (
  SELECT key,
    COUNTIF(in_idc) AS n_series_idc,
    COUNTIF(in_idc AND modality = 'CT') AS n_series_idc_ct,
    COUNTIF(in_idc AND modality = 'MR') AS n_series_idc_mr,
    COUNTIF(in_idc AND modality = 'PT') AS n_series_idc_pt,
    COUNTIF(cs1) AS n_series_cs1,
    COUNTIF(in_cs2) AS n_series_cs2,
    COUNTIF(in_cs2 AND NOT in_idc) AS n_series_cs2_new,
    COUNT(*) AS n_series
  FROM pairs GROUP BY key
),
seg_rows AS (
  SELECT key, meaning, region, code, CAST(NULL AS STRING) AS source, 0 AS pref FROM cs2
  UNION ALL
  SELECT key, meaning, region, code, source, 1 FROM idc
),
-- Case study 2's name where it has one, chosen as build_data_structures_cs2.py does; else
-- the commonest in IDC, as a few SEGs carry a wrong one (Neoplasm as "lung", Nodule as
-- "Mass").
names AS (
  SELECT key,
    ARRAY_AGG(meaning ORDER BY pref, IF(pref = 0, LENGTH(meaning), -n), meaning
              LIMIT 1)[OFFSET(0)] AS meaning
  FROM (SELECT key, meaning, pref, COUNT(*) AS n FROM seg_rows GROUP BY 1, 2, 3)
  GROUP BY key
),
labels AS (
  SELECT key,
    STRING_AGG(DISTINCT code ORDER BY code) AS codes,
    STRING_AGG(DISTINCT region ORDER BY region) AS region,
    STRING_AGG(DISTINCT source ORDER BY source) AS idc_sources,
    COUNTIF(pref = 1) AS n_segments_idc,
    COUNTIF(pref = 0) AS n_segments_cs2
  FROM seg_rows GROUP BY key
)
SELECT * FROM names JOIN labels USING (key) JOIN counts USING (key)
"""

# Series with any segment, per modality: before case study 2, after, and what it adds.
TOTALS = f"""
WITH {PAIRS},
segments AS (
  SELECT modality, COUNT(DISTINCT sop) AS n_seg_instances_idc, COUNT(*) AS n_segments_idc,
         COUNT(DISTINCT source) AS n_sources_idc
  FROM idc GROUP BY 1
)
SELECT modality,
  COUNT(DISTINCT IF(in_idc, series, NULL)) AS n_series_idc,
  COUNT(DISTINCT IF(in_cs2, series, NULL)) AS n_series_cs2,
  COUNT(DISTINCT series) AS n_series,
  ANY_VALUE(segments).* EXCEPT (modality)
FROM pairs LEFT JOIN segments USING (modality)
GROUP BY modality
"""

# Every segment once; what is left out, and how much rests on frames of reference.
CHECK = f"""
SELECT
  CASE WHEN modality IN ('CT', 'MR', 'PT') THEN modality
       WHEN modality IS NULL THEN 'unplaced' ELSE 'other' END AS modality,
  by_frame, COUNT(*) AS rows_, COUNT(DISTINCT CONCAT(sop, '/', segment)) AS segments,
  COUNT(DISTINCT sop) AS seg_instances, COUNT(DISTINCT series) AS series,
  STRING_AGG(DISTINCT source ORDER BY source LIMIT 6) AS sources
FROM ({IDC_ALL})
GROUP BY 1, 2 ORDER BY 1, 2
"""


def main():
    check = bq_csv(CHECK)
    print(check.to_string())
    assert (check.rows_ == check.segments).all(), check

    df = bq_csv(STRUCTURES)
    # As in build_data_structures_cs2.py; every cyst in IDC is a kidney cyst too (BAMF).
    df.loc[df.key == "SCT:367643001", "meaning"] = "Kidney cyst"
    names = df.meaning.str.lower()
    assert not names.duplicated().any(), df[names.duplicated(keep=False)]
    df = df.sort_values("n_series", ascending=False)
    df.to_csv(DATA / "idc_structures.csv.gz", index=False)
    print(f"wrote idc_structures.csv.gz: {len(df)} structures, {df.n_series_idc.sum():,} "
          f"structure-series in IDC, {df.n_series_cs2_new.sum():,} added by case study 2")

    totals = bq_csv(TOTALS)
    print(totals.to_string())
    totals.to_csv(DATA / "idc_structures_totals.csv.gz", index=False)


if __name__ == "__main__":
    main()
