"""Offline checks for cost_model.py / make_terra_manifest.py / region_prices.py.

Run:  python -m pytest util/executionAnalytics/tests -q     (or python tests/test_cost_model.py)
No network, no gcloud: synthetic workflows CSVs with a known linear relation.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

import cost_model as cm            # noqa: E402
import region_prices as rp         # noqa: E402
import make_terra_manifest as mm   # noqa: E402


def synth_workflows(n=14, seed=1, region="us-east4"):
    rng = np.random.default_rng(seed)
    n_series = rng.integers(1, 12, size=n)
    mvox = n_series * rng.uniform(15, 90, size=n)
    rows = []
    for i, (ns, mv) in enumerate(zip(n_series, mvox), start=1):
        inf_min = 12 + 2.5 * ns + 0.08 * mv + rng.normal(0, 0.3)
        oc_min = 3 + 0.9 * ns + 0.01 * mv + rng.normal(0, 0.1)
        rows.append({
            "label": "synthetic", "submissionId": "s", "workflowId": f"wf{i}", "entity": str(i),
            "status": "Succeeded", "model": "moose", "radiomicsMethod": "radiomicsjl",
            "nSeries": int(ns), "sumVoxels": float(mv * 1e6), "sumSlices": int(ns * 120),
            "sumSizeMb": float(ns * 60), "region": region,
            "inference_runtimeMin": inf_min, "inference_doneRuntimeMin": inf_min,
            "inference_attempts": 1, "inference_preempted": 0, "inference_docker": "img@sha256:aaa",
            "inference_gpu": "1xnvidia-tesla-t4", "inference_machine": "custom cpu=4 mem=16 GB",
            "inference_rateHr": 0.27, "inference_cost": inf_min / 60 * 0.22,
            "outputConversion_runtimeMin": oc_min, "outputConversion_doneRuntimeMin": oc_min,
            "outputConversion_attempts": 1, "outputConversion_preempted": 0,
            "outputConversion_docker": "oc@sha256:bbb", "outputConversion_machine": "custom cpu=4 mem=16 GB",
            "outputConversion_rateHr": 0.12, "outputConversion_cost": oc_min / 60 * 0.09,
            "otherCost": 0.001, "costSource": "billing",
            "totalRuntimeMin": inf_min + oc_min,
        })
        rows[-1]["totalCost"] = rows[-1]["inference_cost"] + rows[-1]["outputConversion_cost"] + 0.001
    return pd.DataFrame(rows)


def test_fit_recovers_coefficients(tmp_path):
    wf = synth_workflows()
    p = tmp_path / "wf.csv"
    wf.to_csv(p, index=False)
    out = tmp_path / "model.json"
    cm.cmd_fit(type("A", (), {"workflows": [str(p)], "series": None, "keep_failed": False, "out": str(out)})())
    m = json.loads(out.read_text())
    a, b, c = m["tasks"]["inference"]["time"]["coef"]
    assert abs(a - 12) < 1.5 and abs(b - 2.5) < 0.3 and abs(c - 0.08) < 0.01, (a, b, c)
    assert m["tasks"]["inference"]["time"]["cols"] == ["nSeries", "Mvox"]
    assert m["config"]["inference_docker"] == "img@sha256:aaa"
    assert abs(m["tasks"]["inference"]["preempt_overhead"]) < 1e-9


def test_predict_and_evaluate_roundtrip(tmp_path):
    wf = synth_workflows()
    p = tmp_path / "wf.csv"; wf.to_csv(p, index=False)
    model = tmp_path / "model.json"
    cm.cmd_fit(type("A", (), {"workflows": [str(p)], "series": None, "keep_failed": False, "out": str(model)})())
    pred = tmp_path / "pred.csv"
    cm.cmd_predict(type("A", (), {"model": str(model), "manifest": None, "workflows": [str(p)],
                                  "rates": None, "region": None, "out": str(pred)})())
    pr = pd.read_csv(pred)
    assert abs(pr["predCost"].sum() - wf["totalCost"].sum()) / wf["totalCost"].sum() < 0.02
    assert (pr["predCostLo95"] <= pr["predCost"]).all() and (pr["predCostHi95"] >= pr["predCost"]).all()
    ev = tmp_path / "eval.csv"
    cm.cmd_evaluate(type("A", (), {"predicted": str(pred), "actual": [str(p)], "out": str(ev), "plots": None})())
    e = pd.read_csv(ev)
    assert e["inInterval"].mean() >= 0.8


def test_region_rescale(tmp_path):
    wf = synth_workflows()
    p = tmp_path / "wf.csv"; wf.to_csv(p, index=False)
    model = tmp_path / "model.json"
    cm.cmd_fit(type("A", (), {"workflows": [str(p)], "series": None, "keep_failed": False, "out": str(model)})())
    rates = {"tier": "spot", "shapes": {"inference": {"gpu": "T4"}, "outputConversion": {"gpu": None}},
             "rates": {"inference": {"us-east4": {"total_hr": 0.27}, "us-west4": {"total_hr": 0.135}},
                       "outputConversion": {"us-east4": {"total_hr": 0.12}, "us-west4": {"total_hr": 0.06}}}}
    rp_path = tmp_path / "rates.json"; rp_path.write_text(json.dumps(rates))
    p1, p2 = tmp_path / "p1.csv", tmp_path / "p2.csv"
    for reg, out in [("us-east4", p1), ("us-west4", p2)]:
        cm.cmd_predict(type("A", (), {"model": str(model), "manifest": None, "workflows": [str(p)],
                                      "rates": str(rp_path), "region": reg, "out": str(out)})())
    c1 = pd.read_csv(p1)["inference_predCost"].sum(); c2 = pd.read_csv(p2)["inference_predCost"].sum()
    assert abs(c2 / c1 - 0.5) < 1e-3  # columns are rounded to 4 dp


def test_manifest_batching_and_design():
    rng = np.random.default_rng(0)
    df = pd.DataFrame({"SeriesInstanceUID": [f"1.2.{i}" for i in range(60)],
                       "instanceCount": rng.integers(50, 700, 60), "Rows": 512, "Columns": 512,
                       "series_size_MB": 50.0, "collection_id": "x", "idc_version": "v24"})
    df["voxels"] = df["instanceCount"] * 512 * 512
    batches = mm.greedy_batches(df, 10 * 120 * 512 * 512)
    assert sum(len(b) for b in batches) == 60
    for b in batches:
        assert len(b) == 1 or df.set_index("SeriesInstanceUID").loc[b, "voxels"].sum() <= 10 * 120 * 512 * 512
    pil = mm.designed_pilot_batches(df, [1, 3, 6, 10], seed=0)
    assert sum(len(b) for b in pil) == 60
    sizes = [len(b) for b in pil]
    assert sizes[:8] == [1, 1, 3, 3, 6, 6, 10, 10]
    v = df.set_index("SeriesInstanceUID")["voxels"]
    # same size, small vs large: the "hi" entity must be much bigger than the "lo" one
    assert v.loc[pil[3]].sum() > 2 * v.loc[pil[2]].sum()


def test_rate_tables_from_fake_skus():
    def sku(desc, price, regions, usage="Preemptible", group=None):
        return {"description": desc, "serviceRegions": regions,
                "category": {"usageType": usage, "resourceGroup": group or "CPU"},
                "pricingInfo": [{"pricingExpression": {"tieredRates": [{"unitPrice": {"units": "0", "nanos": int(price * 1e9)}}]}}]}
    skus = [
        sku("Spot Preemptible Custom Instance Core running in Americas", 0.01, ["us-central1"]),
        sku("Spot Preemptible Custom Instance Ram running in Americas", 0.001, ["us-central1"]),
        sku("Nvidia Tesla T4 GPU attached to Spot Preemptible VMs running in Americas", 0.1, ["us-central1"], group="GPU"),
        sku("Spot Preemptible N2D AMD Instance Core running in Americas", 0.008, ["us-central1"]),
        sku("Spot Preemptible N2D AMD Instance Ram running in Americas", 0.0008, ["us-central1"]),
        sku("Storage PD Capacity in Americas", 0.04, ["us-central1"], usage="OnDemand"),
        sku("Balanced PD Capacity in Americas", 0.1, ["us-central1"], usage="OnDemand"),
    ]
    t = rp.rate_tables(skus, rp.DEFAULT_SHAPES)
    inf = t["inference"]["us-central1"]
    assert abs(inf["gpu_hr"] - 0.1) < 1e-9 and abs(inf["vcpu_hr"] - 0.04) < 1e-9 and abs(inf["ram_hr"] - 0.016) < 1e-9
    assert abs(inf["disk_hr"] - (50 * 0.04 + 30 * 0.1) / 730) < 1e-6
    ranked = rp.rank_regions(t, {"inference": 0.8, "outputConversion": 0.2}, data_gb_per_hour=0)
    assert ranked[0]["region"] == "us-central1"


if __name__ == "__main__":
    import tempfile
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            with tempfile.TemporaryDirectory() as d:
                fn(Path(d)) if fn.__code__.co_argcount else fn()
            print("ok", name)
