#!/usr/bin/env python3
"""A-priori per-series workload features from ``idc-index`` (no GCP auth needed).

Given SeriesInstanceUIDs, returns what is knowable about each series *before* running
anything: slice count, matrix size, voxel count, bytes, spacing, collection, body part,
manufacturer. ``voxels = instanceCount * Rows * Columns`` is the same batching metric
``workflows/MOOSE/Notebooks/Preprocessing.ipynb`` uses, so pilot features, large-run
predictions and Terra data tables are all on the same footing.

Shared by ``submission_cost.py`` (join measured cost/timing to features),
``cost_model.py`` (predict a run from a manifest) and ``make_terra_manifest.py``.

Results are cached in a local CSV so repeated invocations do not re-query DuckDB.
"""
import os
from pathlib import Path

import pandas as pd

FEATURE_COLS = [
    "SeriesInstanceUID", "collection_id", "Modality", "BodyPartExamined", "Manufacturer",
    "ManufacturerModelName", "instanceCount", "series_size_MB", "Rows", "Columns",
    "SliceThickness", "PixelSpacing_row_mm", "PixelSpacing_col_mm", "voxels", "idc_version",
]

DEFAULT_CACHE = Path(os.environ.get("CLOUDSEG_IDC_CACHE",
                                    Path.home() / ".cache" / "cloudsegmentator" / "idc_series_features.csv"))


def _query_idc(uids):
    from idc_index import IDCClient
    client = IDCClient()
    client.fetch_index("ct_index")
    version = client.get_idc_version()
    frames = []
    uids = list(dict.fromkeys(uids))
    for i in range(0, len(uids), 2000):
        chunk = uids[i:i + 2000]
        in_list = ",".join(f"'{u}'" for u in chunk)
        q = f"""
            SELECT i.SeriesInstanceUID, i.collection_id, i.Modality, i.BodyPartExamined,
                   i.Manufacturer, i.ManufacturerModelName, i.instanceCount, i.series_size_MB,
                   ct.Rows, ct.Columns, ct.SliceThickness,
                   ct.PixelSpacing_row_mm, ct.PixelSpacing_col_mm
            FROM index AS i
            LEFT JOIN ct_index AS ct USING (SeriesInstanceUID)
            WHERE i.SeriesInstanceUID IN ({in_list})
        """
        frames.append(client.sql_query(q))
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=FEATURE_COLS[:-2])
    df["Rows"] = pd.to_numeric(df["Rows"], errors="coerce").fillna(512).astype(int)
    df["Columns"] = pd.to_numeric(df["Columns"], errors="coerce").fillna(512).astype(int)
    df["instanceCount"] = pd.to_numeric(df["instanceCount"], errors="coerce").fillna(0).astype(int)
    df["voxels"] = df["instanceCount"] * df["Rows"] * df["Columns"]
    df["idc_version"] = version
    return df[FEATURE_COLS]


def series_features(uids, cache_path=DEFAULT_CACHE, refresh=False):
    """DataFrame (one row per UID found, FEATURE_COLS) for the given SeriesInstanceUIDs.
    UIDs missing from IDC (private data) are simply absent from the result."""
    uids = [u for u in dict.fromkeys(str(u).strip() for u in uids) if u]
    cache_path = Path(cache_path) if cache_path else None
    cached = pd.DataFrame(columns=FEATURE_COLS)
    if cache_path and cache_path.exists() and not refresh:
        cached = pd.read_csv(cache_path, dtype={"SeriesInstanceUID": str})
        cached = cached[[c for c in FEATURE_COLS if c in cached.columns]]
    have = set(cached["SeriesInstanceUID"]) if len(cached) else set()
    missing = [u for u in uids if u not in have]
    if missing:
        fresh = _query_idc(missing)
        parts = [d for d in (cached, fresh) if len(d)]
        cached = pd.concat(parts, ignore_index=True).drop_duplicates("SeriesInstanceUID")
        if cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cached.to_csv(cache_path, index=False)
    out = cached[cached["SeriesInstanceUID"].isin(uids)].copy()
    return out.reset_index(drop=True)


def features_by_uid(uids, **kw):
    """{uid: {feature: value}} convenience wrapper."""
    df = series_features(uids, **kw)
    return {r["SeriesInstanceUID"]: r for r in df.to_dict("records")}


if __name__ == "__main__":
    import sys
    df = series_features(sys.argv[1:])
    print(df.to_string())
