# /// script
# requires-python = ">=3.11"
# dependencies = ["pandas>=2.2"]
# ///
"""Count, for each anatomical structure, the case study 2 CT series in which it was
segmented, from the SEG instances in the case study 2 DICOM store's BigQuery export.

    uv run paper/build_data_structures_cs2.py

A structure is a SNOMED CT segmented property type (CodeValue), so left and right merge
and the two model families pool where they share a code. A SEG lists only the segments
its model found in that series, so a segment in a SEG means the structure was found -
any voxels at all; there is no size threshold. Needs `bq` with read access to
idc-external-031. Writes paper/data/cs2_structures.csv.gz.
"""

import io
import subprocess
from pathlib import Path

import pandas as pd

BQ_PROJECT = "idc-external-031"
TABLE = "idc-external-031.not_a_challenge.idc-segmentations-20261014"
OUT = Path(__file__).parent / "data" / "cs2_structures.csv.gz"

# Ten first-run MOOSE SEGs have no ReferencedSeriesSequence. Their two series share a
# FrameOfReferenceUID, so the series comes from the bucket folder each file sits in
# (gs://idc-not-a-challenge/cptac_cmb_2026_10_14/, read 30 Oct 2026).
CT_A = "1.3.6.1.4.1.14519.5.2.1.22427008092060021891741993182204849096"
CT_B = "1.3.6.1.4.1.14519.5.2.1.321968755908788935912597983899264703612"
UNREFERENCED = {
    "1.2.276.0.7230010.3.1.4.296485888.2386.1792047164.240556": CT_A,  # clin_ct_digestive
    "1.2.276.0.7230010.3.1.4.296485888.2403.1792047165.244431": CT_A,  # clin_ct_lungs
    "1.2.276.0.7230010.3.1.4.296485888.2417.1792047166.256895": CT_A,  # clin_ct_muscles
    "1.2.276.0.7230010.3.1.4.296485888.2468.1792047216.419341": CT_A,  # clin_ct_ribs
    "1.2.276.0.7230010.3.1.4.296485888.2482.1792047217.517488": CT_A,  # clin_ct_vertebrae
    "1.2.276.0.7230010.3.1.4.296485888.2929.1792047528.418830": CT_B,  # clin_ct_digestive
    "1.2.276.0.7230010.3.1.4.296485888.2946.1792047529.509811": CT_B,  # clin_ct_lungs
    "1.2.276.0.7230010.3.1.4.296485888.2960.1792047530.528662": CT_B,  # clin_ct_muscles
    "1.2.276.0.7230010.3.1.4.296485888.3011.1792047578.377945": CT_B,  # clin_ct_ribs
    "1.2.276.0.7230010.3.1.4.296485888.3025.1792047579.430561": CT_B,  # clin_ct_vertebrae
}

SEGMENTS = f"""
WITH unref AS (
  SELECT * FROM UNNEST([{", ".join(f"STRUCT('{s}' AS sop, '{c}' AS ct)"
                                   for s, c in UNREFERENCED.items())}])
)
SELECT
  seg.SOPInstanceUID AS sop,
  s.SegmentNumber AS segment,
  COALESCE(r.SeriesInstanceUID, u.ct) AS ct,
  IF(STARTS_WITH(seg.SeriesDescription, 'MOOSE'), 'MOOSE', 'TotalSegmentator') AS tool,
  REGEXP_EXTRACT(seg.SeriesDescription, r'\\) (\\S+) Segmentation$') AS model,
  t.CodeValue AS code,
  t.CodeMeaning AS meaning,
  (SELECT ANY_VALUE(a.CodeMeaning) FROM UNNEST(s.AnatomicRegionSequence) a) AS region
FROM `{TABLE}` seg
LEFT JOIN UNNEST(seg.ReferencedSeriesSequence) r
LEFT JOIN unref u ON u.sop = seg.SOPInstanceUID
CROSS JOIN UNNEST(seg.SegmentSequence) s
CROSS JOIN UNNEST(s.SegmentedPropertyTypeCodeSequence) t
WHERE seg.Modality = 'SEG'
"""

STRUCTURES = f"""
WITH segs AS ({SEGMENTS})
SELECT
  code,
  ARRAY_AGG(meaning ORDER BY LENGTH(meaning), meaning LIMIT 1)[OFFSET(0)] AS meaning,
  STRING_AGG(DISTINCT region) AS region,
  STRING_AGG(DISTINCT model ORDER BY model) AS models,
  COUNT(DISTINCT ct) AS n_series,
  COUNT(DISTINCT IF(tool = 'TotalSegmentator', ct, NULL)) AS n_series_totalsegmentator,
  COUNT(DISTINCT IF(tool = 'MOOSE', ct, NULL)) AS n_series_moose,
  COUNT(*) AS n_segments
FROM segs
GROUP BY code
"""

# Every segment once, with a series: one referenced series per SEG, one type per segment.
CHECK = f"""
WITH segs AS ({SEGMENTS})
SELECT COUNT(*) AS rows_, COUNT(DISTINCT CONCAT(sop, '/', segment)) AS segments,
       COUNTIF(ct IS NULL) AS without_series, COUNT(DISTINCT sop) AS seg_instances,
       COUNT(DISTINCT ct) AS series_with_output
FROM segs
"""


def bq_csv(sql: str) -> pd.DataFrame:
    res = subprocess.run(
        ["bq", "query", f"--project_id={BQ_PROJECT}", "--use_legacy_sql=false",
         "--format=csv", "--max_rows=100000000", "--quiet", sql],
        check=True, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=1800,
    )
    return pd.read_csv(io.StringIO(res.stdout), dtype={"code": str})


def main():
    check = bq_csv(CHECK).iloc[0]
    print(check.to_string())
    assert check.rows_ == check.segments and check.without_series == 0, check

    df = bq_csv(STRUCTURES)
    # One coded concept with a region that names it better than its type does.
    df.loc[(df.meaning == "Cyst") & (df.region == "Kidney"), "meaning"] = "Kidney cyst"
    assert df.n_segments.sum() == check.segments
    df = df.drop(columns="region").sort_values("n_series", ascending=False)
    df.to_csv(OUT, index=False)
    print(f"wrote {OUT.name}: {len(df)} structures, {df.n_segments.sum():,} segments")


if __name__ == "__main__":
    main()
