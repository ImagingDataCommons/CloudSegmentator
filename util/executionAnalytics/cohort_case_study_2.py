# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas>=2.2", "numpy", "pydicom>=2.4", "requests",
#                 "idc-index==0.12.5", "idc-index-data==24.2.2"]
# ///
"""Case study 2's cohort, from idc-index alone: the 3,059 CT series from CMB and CPTAC
collections in IDC v24 that pass case study 1's selection query.

    pip install idc-index==0.12.5 idc-index-data==24.2.2 pydicom requests
    python util/executionAnalytics/cohort_case_study_2.py [--out cs2_cohort_uids.txt]

The runs drew this cohort with BigQuery
(``workflows/TotalSegmentator/sqlQueries/cmbCptacCohort.sql``) and used all of it: 100
series in the pilot, 2,959 in 186 batches. This script selects the same series with
``cohort_idc_index.py`` (see its docstring for how the query's checks map onto idc-index
and DICOM headers), needs no BigQuery or credentials, and takes ~10 min (~74,000 header
reads from IDC's public bucket). idc-index-data is pinned to 24.2.2, which is IDC v24.

Writes the UIDs, one per line, sorted, and checks them against the count and SHA-256 of
the list the BigQuery query returned on 14 Oct 2026. Feed the list to
``make_terra_manifest.py full --uids-file``.
"""
import argparse
import hashlib
import sys
from pathlib import Path

from idc_index import IDCClient

sys.path.insert(0, str(Path(__file__).parent))
from cohort_idc_index import select  # noqa: E402

COLLECTIONS = ("%cmb%", "%cptac%")
IDC_VERSION = "v24"
EXPECTED_N = 3059
EXPECTED_SHA256 = "f1593f6d404cd2babdad7e77c02c1c2dd1fa9184ced83f3addd29bef09956f77"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", default="cs2_cohort_uids.txt")
    a = ap.parse_args()

    c = IDCClient()
    if c.get_idc_version() != IDC_VERSION:
        sys.exit(f"idc-index-data serves IDC {c.get_idc_version()}, need {IDC_VERSION}: "
                 "pip install idc-index==0.12.5 idc-index-data==24.2.2")
    b = select(c, COLLECTIONS)
    uids = sorted(b.loc[b.selected, "SeriesInstanceUID"])
    text = "\n".join(uids) + "\n"
    Path(a.out).write_text(text, newline="\n")
    print(f"{len(uids):,} series -> {a.out}")

    sha = hashlib.sha256(text.encode()).hexdigest()
    if len(uids) == EXPECTED_N and sha == EXPECTED_SHA256:
        print("Identical to the BigQuery cohort the case study 2 runs used")
    else:
        sys.exit(f"Differs from the BigQuery cohort ({EXPECTED_N:,} series, sha256 {EXPECTED_SHA256[:12]}...): "
                 f"got {len(uids):,}, sha256 {sha[:12]}...")


if __name__ == "__main__":
    main()
