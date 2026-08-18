#!/usr/bin/env python3
"""Build Terra data tables (TSV) for the harmonized ``Segmentator`` workflow: a designed
**pilot** and a **full** run drawn from the same IDC cohort, so a cost model fitted on the
pilot can be checked against the full run.

Cohort selection mirrors ``workflows/MOOSE/Notebooks/Preprocessing.ipynb`` (idc-index:
collection LIKE patterns, modality, ``volume_geometry_index.regularly_spaced_3d_volume``),
and the full-run batching is the same greedy voxel-target rule (one Terra entity = one
workflow = one batch of series; ``voxels = instanceCount * Rows * Columns``).

The pilot is *designed* so the per-task cost model ``a + b*nSeries + c*Mvox`` is
identifiable: series are sampled stratified over voxel quantiles (so it spans the size
distribution of the cohort) and assembled into entities of deliberately different sizes
(``--batch-sizes``); for every batch size there is one entity of small series and one of
large series before any mixed ones, so that #series and voxels do not move together.

Examples::

    # 1) pilot: ~48 series in entities of 1/3/6/10 series
    python make_terra_manifest.py pilot --collections '%cmb%' '%cptac%' \
        --n-series 48 --batch-sizes 1,3,6,10 --seed 0 --name moose_pilot

    # 2) full: 400 series (random, stratified) from the same cohort, standard batching,
    #    excluding the pilot's series
    python make_terra_manifest.py full --collections '%cmb%' '%cptac%' \
        --n-series 400 --exclude moose_pilot_series.csv --seed 0 --name moose_full

    # 3) from an explicit UID list (one per line)
    python make_terra_manifest.py full --uids-file my_uids.txt --name custom

Outputs ``<name>_terra_data_table.tsv`` (upload to Terra; root entity ``twoVM_<name>``,
set ``yamlListOfSeriesInstanceUIDs = this.SeriesInstanceUIDs``) and ``<name>_series.csv``
(the per-series features + entity assignment, for auditing / cost_model.py).
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

DEFAULT_BATCH_TARGET = 10 * 120 * 512 * 512   # voxels per batch (Preprocessing.ipynb default)


def query_cohort(collections, modalities, geometry, min_slices, max_slices):
    from idc_index import IDCClient
    client = IDCClient()
    version = client.get_idc_version()
    client.fetch_index("ct_index")
    joins, where = ["LEFT JOIN ct_index AS ct USING (SeriesInstanceUID)"], []
    if collections:
        pats = " OR ".join(f"lower(i.collection_id) LIKE '{p.lower()}'" for p in collections)
        where.append(f"({pats})")
    if modalities:
        where.append("i.Modality IN (" + ",".join(f"'{m}'" for m in modalities) + ")")
    if geometry:
        client.fetch_index("volume_geometry_index")
        joins.append("INNER JOIN volume_geometry_index AS g USING (SeriesInstanceUID)")
        where.append("g.regularly_spaced_3d_volume = TRUE")
    if min_slices:
        where.append(f"i.instanceCount >= {int(min_slices)}")
    if max_slices:
        where.append(f"i.instanceCount <= {int(max_slices)}")
    q = f"""
        SELECT i.collection_id, i.PatientID, i.StudyInstanceUID, i.SeriesInstanceUID,
               i.Modality, i.BodyPartExamined, i.Manufacturer, i.SeriesDescription,
               i.instanceCount, i.series_size_MB,
               COALESCE(ct.Rows, 512) AS Rows, COALESCE(ct.Columns, 512) AS Columns,
               ct.SliceThickness, ct.PixelSpacing_row_mm
        FROM index AS i
        {' '.join(joins)}
        {'WHERE ' + ' AND '.join(where) if where else ''}
        ORDER BY i.collection_id, i.PatientID, i.StudyInstanceUID, i.SeriesInstanceUID
    """
    df = client.sql_query(q)
    return _finish(df, version)


def _finish(df, version):
    df = df.copy()
    for c in ("instanceCount", "Rows", "Columns"):
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(512 if c != "instanceCount" else 0).astype(int)
    df["voxels"] = df["instanceCount"] * df["Rows"] * df["Columns"]
    df["idc_version"] = version
    return df.reset_index(drop=True)


def cohort_from_uids(path):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from idc_features import series_features
    uids = [ln.strip() for ln in Path(path).read_text().splitlines() if ln.strip()]
    df = series_features(uids)
    df = df.rename(columns={})
    return _finish(df, df["idc_version"].iloc[0] if len(df) else "?")


def stratified_sample(df, n, seed, key="voxels", n_strata=None):
    """Sample n rows spread evenly over quantile strata of `key` (one patient's series
    are treated independently -- fine for cost purposes)."""
    if n >= len(df):
        return df.sample(frac=1, random_state=seed).reset_index(drop=True)
    n_strata = n_strata or max(2, min(8, n // 4))
    rng = np.random.default_rng(seed)
    ranks = df[key].rank(method="first")
    strata = pd.qcut(ranks, n_strata, labels=False)
    per = np.full(n_strata, n // n_strata)
    per[: n % n_strata] += 1
    picks = []
    for s in range(n_strata):
        idx = df.index[strata == s].to_numpy()
        take = min(per[s], len(idx))
        picks.extend(rng.choice(idx, size=take, replace=False))
    return df.loc[picks].sample(frac=1, random_state=seed).reset_index(drop=True)


def greedy_batches(df, target):
    """Preprocessing.ipynb batching: accumulate series until adding the next would exceed
    `target` voxels; a single oversized series gets its own batch."""
    batches, cur, cur_v = [], [], 0
    for _, r in df.iterrows():
        v = int(r["voxels"])
        if cur and cur_v + v > target:
            batches.append(cur)
            cur, cur_v = [], 0
        cur.append(r["SeriesInstanceUID"])
        cur_v += v
    if cur:
        batches.append(cur)
    return batches


def designed_pilot_batches(df, batch_sizes, seed):
    """Assemble sampled series into entities with the requested sizes so that #series and
    voxels are NOT collinear: for every batch size the plan first makes one entity of
    *small* series (bottom third by voxels) and one of *large* series (top third), then
    mixed entities, cycling until the sample is used up."""
    rng = np.random.default_rng(seed)
    df = df.sort_values("voxels").reset_index(drop=True)
    n = len(df)
    remaining = set(df.index)
    lo = set(i for i in df.index if i < n / 3)
    hi = set(i for i in df.index if i >= 2 * n / 3)
    # (s1,lo),(s1,hi),(s2,lo),(s2,hi),... then mixed entities of each size
    plan = [p for s in batch_sizes for p in ((s, "lo"), (s, "hi"))] + [(s, "mix") for s in batch_sizes]
    batches, k = [], 0
    while remaining:
        size, kind = plan[k % len(plan)]
        pool = {"lo": lo & remaining, "hi": hi & remaining, "mix": remaining}[kind]
        if len(pool) < size:
            pool = remaining
        take = min(size, len(pool))
        pick = [int(i) for i in rng.choice(sorted(pool), size=take, replace=False)]
        remaining -= set(pick)
        batches.append([df.loc[i, "SeriesInstanceUID"] for i in pick])
        k += 1
    return batches


def write_outputs(df, batches, name, outdir):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y_%m_%d_%H_%M")
    ent_col = f"entity:twoVM_{name}_id"
    by_uid = df.set_index("SeriesInstanceUID")
    rows, assign = [], {}
    for i, uids in enumerate(batches, start=1):
        sub = by_uid.loc[uids]
        rows.append({
            ent_col: i,
            "SeriesInstanceUIDs": json.dumps({"SeriesInstanceUIDs": list(uids)}),
            "idc-version": str(sub["idc_version"].iloc[0]),
            "n_series": len(uids),
            "sum_voxels": int(sub["voxels"].sum()),
            "sum_slices": int(sub["instanceCount"].sum()),
            "sum_size_MB": round(float(sub["series_size_MB"].sum()), 1),
            "max_slices": int(sub["instanceCount"].max()),
        })
        for u in uids:
            assign[u] = i
    table = pd.DataFrame(rows)
    tsv = outdir / f"{name}_terra_data_table.tsv"
    table.to_csv(tsv, sep="\t", index=False)
    df = df.copy()
    df["entity"] = df["SeriesInstanceUID"].map(assign)
    df = df[df["entity"].notna()].sort_values(["entity", "voxels"])
    csv_path = outdir / f"{name}_series.csv"
    df.to_csv(csv_path, index=False)

    n = len(df)
    print(f"\n{name}: {len(batches)} entities, {n} series, {df['voxels'].sum() / 1e6:.0f} Mvox, "
          f"{df['instanceCount'].sum()} slices, {df['series_size_MB'].sum() / 1024:.1f} GB "
          f"(IDC {df['idc_version'].iloc[0]}, generated {stamp})")
    print(f"  series/entity: {table['n_series'].min()}-{table['n_series'].max()} "
          f"(mean {table['n_series'].mean():.1f});  Mvox/entity: {table['sum_voxels'].min() / 1e6:.0f}-"
          f"{table['sum_voxels'].max() / 1e6:.0f}")
    if len(table) > 2 and table["n_series"].std() > 0 and table["sum_voxels"].std() > 0:
        r = np.corrcoef(table["n_series"], table["sum_voxels"])[0, 1]
        print(f"  corr(n_series, sum_voxels) = {r:.2f}  (want well below 1 for the pilot)")
    q = df["voxels"].quantile([0, .1, .25, .5, .75, .9, 1]) / 1e6
    print("  series Mvox quantiles: " + ", ".join(f"p{int(k * 100)}={v:.0f}" for k, v in q.items()))
    print(f"  collections: {df['collection_id'].value_counts().to_dict()}")
    print(f"Wrote {tsv}\n      {csv_path}")
    return tsv, csv_path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["pilot", "full"])
    ap.add_argument("--name", required=True, help="output name / Terra entity type suffix (twoVM_<name>)")
    ap.add_argument("--collections", nargs="*", default=["%cmb%", "%cptac%"],
                    help="SQL LIKE patterns on collection_id (default: %%cmb%% %%cptac%%)")
    ap.add_argument("--modalities", nargs="*", default=["CT"])
    ap.add_argument("--no-geometry-filter", action="store_true",
                    help="do not require volume_geometry_index.regularly_spaced_3d_volume")
    ap.add_argument("--min-slices", type=int, default=20)
    ap.add_argument("--max-slices", type=int)
    ap.add_argument("--uids-file", help="build from an explicit SeriesInstanceUID list instead of a cohort query")
    ap.add_argument("--exclude", nargs="*", help="CSV/TSV files whose SeriesInstanceUID(s) to exclude (e.g. the pilot's *_series.csv)")
    ap.add_argument("--n-series", type=int, help="number of series to sample (pilot default 60; full default: all)")
    ap.add_argument("--batch-sizes", default="1,3,6,10", help="pilot entity sizes to cycle through")
    ap.add_argument("--batch-target", type=int, default=DEFAULT_BATCH_TARGET,
                    help="full-run voxels per batch (Preprocessing.ipynb greedy rule)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--outdir", default=".")
    args = ap.parse_args()

    if args.uids_file:
        df = cohort_from_uids(args.uids_file)
    else:
        print("Querying idc-index cohort ...", file=sys.stderr)
        df = query_cohort(args.collections, args.modalities, not args.no_geometry_filter,
                          args.min_slices, args.max_slices)
    print(f"cohort: {len(df)} series", file=sys.stderr)
    if args.exclude:
        ex = set()
        for p in args.exclude:
            t = pd.read_csv(p, sep="\t" if p.endswith(".tsv") else ",", dtype=str)
            if "SeriesInstanceUIDs" in t.columns:
                for raw in t["SeriesInstanceUIDs"]:
                    try:
                        ex.update(json.loads(raw).get("SeriesInstanceUIDs", []))
                    except Exception:
                        pass
            elif "SeriesInstanceUID" in t.columns:
                ex.update(t["SeriesInstanceUID"].astype(str))
        before = len(df)
        df = df[~df["SeriesInstanceUID"].isin(ex)].reset_index(drop=True)
        print(f"excluded {before - len(df)} series listed in {args.exclude}", file=sys.stderr)
    if df.empty:
        sys.exit("No series selected.")

    if args.mode == "pilot":
        n = args.n_series or 60
        sizes = [int(x) for x in args.batch_sizes.split(",") if x.strip()]
        sample = stratified_sample(df, n, args.seed)
        batches = designed_pilot_batches(sample, sizes, args.seed)
        write_outputs(sample, batches, args.name, args.outdir)
    else:
        sample = stratified_sample(df, args.n_series, args.seed) if args.n_series else df
        # Preprocessing.ipynb orders by collection/patient/study before batching
        sample = sample.sort_values(["collection_id", "PatientID", "StudyInstanceUID"]) \
            if "PatientID" in sample.columns else sample
        batches = greedy_batches(sample, args.batch_target)
        write_outputs(sample, batches, args.name, args.outdir)


if __name__ == "__main__":
    main()
