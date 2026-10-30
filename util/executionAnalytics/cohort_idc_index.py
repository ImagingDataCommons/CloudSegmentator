#!/usr/bin/env python3
"""Case study 1's cohort query (``workflows/TotalSegmentator/sqlQueries/nonNlstCohort.sql``)
rebuilt on idc-index, so no BigQuery account is needed. For CMB/CPTAC on IDC v24 it selects
the same 3,059 series as ``cmbCptacCohort.sql``.

idc-index's tables do not hold everything the SQL checks, so two steps read DICOM headers
anonymously from IDC's public S3 bucket:

1. Series with a ``volume_geometry_index`` row: that row covers the SQL's per-instance checks
   except the axial test. ``obliquity_degrees`` is measured against the *nearest* axis, so
   it also passes sagittal and coronal series; the slice normal is read from one header
   instead (``|normal . z| >= 0.99``, as in the SQL). The SQL also requires identical x/y in
   ImagePositionPatient: a stack with no tilt passes when its in-plane position is
   consistent, and a tilted one (``obliquity_degrees > 0``) when it is not, because the SQL
   only compares x/y and ignores the tilt.
2. Series without a geometry row (mostly MPR/MIP reformats): every instance's header is read
   and the SQL's checks applied directly. For CMB/CPTAC this is ~530 series, ~70k headers.

Examples::

    python cohort_idc_index.py --collections '%cmb%' '%cptac%' --out cmbcptac
    python cohort_idc_index.py --collections '%cmb%' '%cptac%' --out cmbcptac \
        --compare cs1sql_uids.txt

Writes ``<out>_uids.txt`` (one SeriesInstanceUID per line, the input to
``make_terra_manifest.py full --uids-file``) and ``<out>_checks.csv`` (one row per candidate
series with each check). The result depends on the IDC version idc-index-data ships
(printed at the start).
"""
import argparse
import io
import re
import sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import pydicom
import requests
from idc_index import IDCClient
from requests.adapters import HTTPAdapter

JPEG_TS = ("1.2.840.10008.1.2.4.70", "1.2.840.10008.1.2.4.51")
GEOMETRY_CHECKS = ["single_orientation", "orthogonal_orientation", "unique_slice_positions",
                   "consistent_pixel_spacing", "consistent_image_dimensions", "uniform_slice_spacing"]

S = requests.Session()
S.mount("https://", HTTPAdapter(pool_connections=32, pool_maxsize=32))


def get(url, tries=5, **kw):
    err = None
    for _ in range(tries):
        try:
            r = S.get(url, timeout=60, **kw)
            if r.status_code < 500:
                return r
            err = f"HTTP {r.status_code}"
        except requests.RequestException as e:
            err = e
    raise RuntimeError(f"GET {url} failed after {tries} tries: {err!r}")


def keys(aws_url, limit=None):
    """Object keys of one series in IDC's public bucket (skipping the empty 'folder' key)."""
    bucket, prefix = re.match(r"s3://([^/]+)/([^*]+)", aws_url).groups()
    host = f"https://{bucket}.s3.amazonaws.com"
    out, tok = [], None
    while True:
        p = {"list-type": "2", "prefix": prefix}
        if tok:
            p["continuation-token"] = tok
        if limit:
            p["max-keys"] = str(limit + 2)
        t = get(host, params=p).text
        out += [f"{host}/{k}" for k in re.findall(r"<Key>([^<]+)</Key>", t) if not k.endswith("/")]
        m = re.search(r"<NextContinuationToken>([^<]+)</NextContinuationToken>", t)
        if not m or (limit and len(out) >= limit):
            return out[:limit] if limit else out
        tok = m.group(1)


def header(url):
    """Header of one instance, from a range GET (a larger one if the first cut it short)."""
    ds = None
    for size in (65536, 8 << 20):
        r = get(url, headers={"Range": f"bytes=0-{size - 1}"})
        try:
            ds = pydicom.dcmread(io.BytesIO(r.content), stop_before_pixels=True, force=True)
            if "ImagePositionPatient" in ds or len(r.content) < size:
                break
        except Exception:  # noqa: BLE001
            ds = None
    return ds


def normal(iop):
    a = np.array([float(v) for v in iop])
    return np.cross(a[:3], a[3:])


def slice_normal_z(aws_url):
    """|normal . z| from the first instance's ImageOrientationPatient."""
    ds = header(keys(aws_url, limit=1)[0])
    return abs(normal(ds.ImageOrientationPatient)[2])


def instance_checks(aws_url):
    """The SQL's per-instance checks, applied to every instance's header."""
    with ThreadPoolExecutor(8) as ex:
        H = [h for h in ex.map(header, keys(aws_url)) if h is not None]
    s = lambda ds, t: "/".join(str(v) for v in ds[t].value) if t in ds and ds[t].value is not None else None  # noqa: E731
    d = pd.DataFrame([dict(
        ts=str(ds.file_meta.get("TransferSyntaxUID", "")) if hasattr(ds, "file_meta") else "",
        localizer="LOCALIZER" in [str(v) for v in (ds.get("ImageType") or [])],
        iop=s(ds, "ImageOrientationPatient"), ps=s(ds, "PixelSpacing"),
        ipp=[str(v) for v in ds.ImagePositionPatient] if ds.get("ImagePositionPatient") else None,
        rows=ds.get("Rows"), cols=ds.get("Columns")) for ds in H])
    if d.empty or d.localizer.any() or d.ts.isin(JPEG_TS).any():
        return False
    d = d[d.ipp.notna()]
    if len(d) < 50:
        return False
    z = np.sort(d.ipp.map(lambda p: float(p[2])).values)
    steps = np.unique(np.diff(z))
    dot = max(normal(v.split("/"))[2] for v in d.iop.dropna())
    return bool(d.iop.nunique() == 1 and d.ps.nunique() == 1 and len(d) == len(np.unique(z))
                and d.ipp.map(lambda p: p[0] + "/" + p[1]).nunique() == 1
                and d.rows.nunique() == 1 and d.cols.nunique() == 1
                and 0.99 <= abs(dot) <= 1.01 and len(steps) and steps.max() - steps.min() < 0.01)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--collections", nargs="+", required=True, help="collection_id LIKE patterns")
    ap.add_argument("--out", required=True, help="output prefix")
    ap.add_argument("--compare", help="UID list (e.g. from the BigQuery query) to compare against")
    ap.add_argument("--workers", type=int, default=16)
    a = ap.parse_args()

    b = select(IDCClient(), a.collections, a.workers)
    uids = sorted(b.loc[b.selected, "SeriesInstanceUID"])
    with open(f"{a.out}_uids.txt", "w") as f:
        f.write("\n".join(uids) + "\n")
    b.drop(columns=["series_aws_url"]).to_csv(f"{a.out}_checks.csv", index=False)
    print(f"selected {len(uids)} series -> {a.out}_uids.txt", file=sys.stderr)

    if a.compare:
        ref = set(open(a.compare).read().split())
        print(f"compare with {a.compare} ({len(ref)}): both {len(ref & set(uids))}, "
              f"only here {len(set(uids) - ref)}, only there {len(ref - set(uids))}", file=sys.stderr)


def select(c, collections, workers=16):
    """One row per CT series in the collections, with each check and ``selected``."""
    for t in ("ct_index", "volume_geometry_index"):
        c.fetch_index(t)
    pats = " OR ".join(f"lower(i.collection_id) LIKE '{p.lower()}'" for p in collections)
    b = c.sql_query(f"""
        SELECT i.SeriesInstanceUID, i.collection_id, i.SeriesDescription, i.instanceCount,
               i.TransferSyntaxUID, i.series_aws_url, ct.ImageType,
               g.SeriesInstanceUID IS NOT NULL AS has_geometry, g.obliquity_degrees,
               g.consistent_in_plane_row, g.consistent_in_plane_col,
               {", ".join("g." + k for k in GEOMETRY_CHECKS)}
        FROM index i
        LEFT JOIN ct_index ct USING (SeriesInstanceUID)
        LEFT JOIN volume_geometry_index g USING (SeriesInstanceUID)
        WHERE i.Modality = 'CT' AND ({pats})
    """)
    print(f"IDC {c.get_idc_version()}: {len(b)} CT series in {collections}", file=sys.stderr)

    b["basic"] = (~b.ImageType.astype(str).str.contains("LOCALIZER")
                  & ~b.TransferSyntaxUID.isin(JPEG_TS) & (b.instanceCount >= 50))
    flag = lambda col: b[col].fillna(False).astype(bool)  # noqa: E731
    inplane = flag("consistent_in_plane_row") & flag("consistent_in_plane_col")
    straight = ((b.obliquity_degrees == 0) & inplane) | ((b.obliquity_degrees > 0) & ~inplane)
    b["geometry"] = b.has_geometry & pd.concat([flag(k) for k in GEOMETRY_CHECKS], axis=1).all(axis=1) & straight

    # Step 1: axial test from one header, for series that pass everything else.
    todo = b[b.basic & b.geometry]
    print(f"step 1: slice normal of {len(todo)} series (one header each)", file=sys.stderr)
    with ThreadPoolExecutor(workers) as ex:
        nz = dict(zip(todo.SeriesInstanceUID, ex.map(slice_normal_z, todo.series_aws_url)))
    b["normal_z"] = b.SeriesInstanceUID.map(nz)
    b["axial"] = b.normal_z.between(0.99, 1.01)

    # Step 2: every header, for series with no geometry row.
    todo = b[b.basic & ~b.has_geometry]
    print(f"step 2: per-instance checks on {len(todo)} series ({int(todo.instanceCount.sum())} headers)",
          file=sys.stderr)
    with ThreadPoolExecutor(max(1, workers // 4)) as ex:
        ok = dict(zip(todo.SeriesInstanceUID, ex.map(instance_checks, todo.series_aws_url)))
    b["instances"] = b.SeriesInstanceUID.map(ok)

    b["selected"] = b.basic & ((b.geometry & b.axial) | b.instances.eq(True))
    return b


if __name__ == "__main__":
    main()
