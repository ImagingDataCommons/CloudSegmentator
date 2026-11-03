# /// script
# requires-python = ">=3.11"
# dependencies = ["pandas>=2.2", "idc-index==0.13.2", "idc-index-data==25.0.2"]
# ///
"""Join each case study 2 series' image geometry from IDC to its peak RAM and its
memory-related failures, to test whether geometry predicts which series run out.

    uv run paper/build_series_geometry_cs2.py

Reads paper/data/cs2_peak_memory.csv.gz and cs2_inference_failures.csv.gz (see
build_data_cs2.py). Geometry comes from idc-index (IDC v25): matrix and in-plane
spacing from ct_index, and slice spacing from volume_geometry_index, which is the
distance between slice planes and not SliceThickness. No credentials needed.

Writes paper/data/cs2_series_geometry.csv.gz, one row per series, and prints the
Spearman correlations of peak RAM with geometry and the ranks of the failed series.
"""

from pathlib import Path

import pandas as pd
from idc_index import IDCClient

DATA = Path(__file__).parent / "data"
MEMORY_CAUSES = {"killed (signal 9)": "OOM kill", "timed out (90 min cap)": "timeout",
                 "export worker killed (RAM)": "export worker killed"}
VIEWER = "https://viewer.imaging.datacommons.cancer.gov/v3/viewer/?StudyInstanceUIDs={}&initialSeriesInstanceUID={}"
RESAMPLED_MM = 1.5   # TotalSegmentator's working resolution for `total`


def main():
    peak = pd.read_csv(DATA / "cs2_peak_memory.csv.gz")
    fail = pd.read_csv(DATA / "cs2_inference_failures.csv.gz")

    idc = IDCClient()
    for name in ("ct_index", "volume_geometry_index"):
        idc.fetch_index(name)
    geo = idc.sql_query("""
        SELECT i.SeriesInstanceUID, i.collection_id, i.PatientID, i.StudyInstanceUID,
               i.SeriesDescription, i.instanceCount AS slices, i.series_size_MB,
               c.Rows, c.Columns, c.PixelSpacing_row_mm, c.PixelSpacing_col_mm, c.SliceThickness,
               g.slice_spacing_mm, g.regularly_spaced_3d_volume AS regular
        FROM index i JOIN ct_index c USING (SeriesInstanceUID)
        LEFT JOIN volume_geometry_index g USING (SeriesInstanceUID)""")
    geo = geo[geo.SeriesInstanceUID.isin(peak.SeriesInstanceUID)].copy()
    print(f"IDC {idc.get_idc_version()}: geometry for {len(geo):,} of "
          f"{peak.SeriesInstanceUID.nunique():,} series")

    # Physical extent. Without a regular slice spacing (mostly MIP reconstructions) the
    # length is left empty rather than guessed from SliceThickness.
    geo["fov_row_mm"] = geo.Rows * geo.PixelSpacing_row_mm
    geo["fov_col_mm"] = geo.Columns * geo.PixelSpacing_col_mm
    geo["length_mm"] = (geo.slices - 1) * geo.slice_spacing_mm
    geo["mvox_native"] = geo.Rows * geo.Columns * geo.slices / 1e6
    geo["mvox_1p5mm"] = geo.fov_row_mm * geo.fov_col_mm * geo.length_mm / RESAMPLED_MM**3 / 1e6
    geo["rank_1p5mm"] = geo.mvox_1p5mm.rank(ascending=False, method="min")
    geo["rank_native"] = geo.mvox_native.rank(ascending=False, method="min")

    # Peak per series and unit on the GPU VM, from units that finished.
    gpu = peak[peak.vm == "GPU"].assign(col=lambda d: d.model + ":" + d.unit)
    gpu = gpu.pivot_table(index="SeriesInstanceUID", columns="col", values="peak_gb", aggfunc="max")
    gpu.columns = ["peak_moose_gb", "peak_ts_lung_vessels_gb", "peak_ts_total_gb"]
    geo = geo.merge(gpu, left_on="SeriesInstanceUID", right_index=True, how="left")

    mem = fail[fail.cause.isin(MEMORY_CAUSES)]
    lost = (mem.assign(u=lambda d: d.model + " " + d.unit.str.replace("clin_ct_", "")
                       + " (" + d.cause.map(MEMORY_CAUSES) + ")")
            .groupby("SeriesInstanceUID").agg(memory_failures=("u", "; ".join),
                                              failed_ts=("model", lambda m: (m == "TotalSegmentator").any()),
                                              failed_moose=("model", lambda m: (m == "MOOSE").any())))
    geo = geo.merge(lost, left_on="SeriesInstanceUID", right_index=True, how="left")
    geo[["failed_ts", "failed_moose"]] = geo[["failed_ts", "failed_moose"]].fillna(False).astype(bool)
    geo["viewer_url"] = [VIEWER.format(s, r) for s, r in zip(geo.StudyInstanceUID, geo.SeriesInstanceUID)]

    geo = geo.sort_values("mvox_1p5mm", ascending=False)
    geo.round(3).to_csv(DATA / "cs2_series_geometry.csv.gz", index=False)

    # Spearman over units that finished: failed units have no peak of their own.
    print("\nSpearman rho, peak RAM of finished units against:")
    for col in ("peak_ts_total_gb", "peak_ts_lung_vessels_gb", "peak_moose_gb"):
        r = {x: geo[x].rank().corr(geo[col].rank())
             for x in ("series_size_MB", "mvox_native", "mvox_1p5mm", "length_mm")}
        print(f"  {col:26s}", "  ".join(f"{k} {v:.2f}" for k, v in r.items()))

    irregular = geo.length_mm.isna()
    print(f"\nseries without a regular slice spacing: {irregular.sum()}, "
          f"of which failed: {(irregular & (geo.failed_ts | geo.failed_moose)).sum()}")
    cols = ["rank_1p5mm", "rank_native", "PatientID", "SeriesDescription", "slices",
            "slice_spacing_mm", "fov_col_mm", "length_mm", "mvox_1p5mm", "peak_ts_total_gb",
            "peak_moose_gb", "failed_ts", "failed_moose"]
    print("\nlargest 30 series at 1.5 mm, with every memory failure:")
    show = geo[(geo.rank_1p5mm <= 30) | geo.failed_ts | geo.failed_moose]
    print(show[cols].round(1).to_string(index=False))


if __name__ == "__main__":
    main()
