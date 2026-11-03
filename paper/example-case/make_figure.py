# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow>=10"]
# ///
"""Rebuild the example-case figure in a running 3D Slicer, through the Slicer MCP server.

    uv run paper/example-case/make_figure.py [--case-dir DIR] [--layout row|two-rows]

DIR holds ct/ and seg_sr/ (default: this directory; README.md says how to download them).
Slicer must be running with the MCP server started and access allowed; see README.md.
Writes out/cs2-sample-result{.png,_raw.png,_raw.json} for the one-row layout, and
out/cs2-sample-result_two-rows{.png,_raw1.png,_raw1.json,_raw2.png,_raw2.json} for two rows. From an
empty scene this takes about 8 minutes on a 2020 13-inch MacBook Pro, with Slicer peaking at
about 7.3 GB; with everything loaded, under a minute.
"""

import argparse
import json
import pathlib
import urllib.error
import urllib.request

import annotate

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE.parent / "out"

# The settings of the committed figures; README.md says why
SMOOTHING = 0.0
CORONAL = {"y": -10.0, "window": 400, "level": 40, "marginMm": 10.0}
ARRANGE = {"gapMm": 40.0, "azimuth": 30.0, "elevation": 25.0, "rotateCT": True, "background": "slicer"}
MODELS = [
    "total", "lung_vessels",
    "clin_ct_body", "clin_ct_body_composition", "clin_ct_cardiac", "clin_ct_digestive",
    "clin_ct_lungs", "clin_ct_muscles", "clin_ct_organs", "clin_ct_peripheral_bones",
    "clin_ct_ribs", "clin_ct_vertebrae",
]
LAYOUTS = {
    "row": {"name": "cs2-sample-result", "rows": None, "fontPx": 26},
    # Split where the two rows come out the same width
    "two-rows": {"name": "cs2-sample-result_two-rows", "fontPx": 40,
                 "rows": [["CT"] + MODELS[:5], MODELS[5:]]},
}


def slicer(url, function, *args, **kwargs):
    """Call slicer_scene.<function>(*args, **kwargs) inside Slicer and return its JSON result."""
    code = (
        "import json, runpy\n"
        f"ns = runpy.run_path({str(HERE / 'slicer_scene.py')!r})\n"
        f"args, kwargs = json.loads({json.dumps([args, kwargs])!r})\n"
        f"__result = ns[{function!r}](*args, **kwargs)\n"
    )
    request = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
               "params": {"name": "execute_python", "arguments": {"code": code}}}
    with urllib.request.urlopen(urllib.request.Request(
            url, data=json.dumps(request).encode(), headers={"Content-Type": "application/json"}),
            timeout=900) as response:
        reply = json.load(response)
    if "error" in reply:
        raise SystemExit(f"Slicer MCP server: {reply['error']}")
    text = "\n".join(c.get("text", "") for c in reply["result"]["content"])
    if reply["result"].get("isError") or text.startswith("Error:"):
        raise SystemExit(f"{function} failed in Slicer:\n{text}")
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--case-dir", type=pathlib.Path, default=HERE)
    parser.add_argument("--url", default="http://localhost:2026/mcp", help="Slicer MCP server")
    parser.add_argument("--layout", choices=LAYOUTS, default="row")
    options = parser.parse_args()
    layout = LAYOUTS[options.layout]
    caseDir = options.case_dir.expanduser().resolve()
    for sub in ("ct", "seg_sr"):
        if not (caseDir / sub).is_dir():
            raise SystemExit(f"{caseDir / sub} not found; see README.md to download the case")
    try:
        slicer(options.url, "_defaultOrder")
    except urllib.error.URLError as error:
        raise SystemExit(f"No Slicer MCP server at {options.url} ({error.reason}); see README.md")

    print(slicer(options.url, "loadCT", str(caseDir / "ct")))
    for model in MODELS:
        print(slicer(options.url, "loadSeg", model, str(caseDir / "seg_sr"), smoothing=SMOOTHING))
    print(slicer(options.url, "addCoronalCT", **CORONAL))
    print(slicer(options.url, "arrange", **ARRANGE, rows=layout["rows"]))

    # Rows are captured one at a time, each filling the view at a scale shared by all of them
    OUT.mkdir(exist_ok=True)
    name, rows = layout["name"], layout["rows"] or [None]
    captures = []
    for n, row in enumerate(rows, 1):
        suffix = str(n) if len(rows) > 1 else ""
        raw, positions = OUT / f"{name}_raw{suffix}.png", OUT / f"{name}_raw{suffix}.json"
        positions.write_text(slicer(options.url, "capture", str(raw), models=row, sizeFrom=layout["rows"]) + "\n")
        captures.append((raw, positions))
    annotate.main(captures, OUT / f"{name}.png", fontPx=layout["fontPx"])


if __name__ == "__main__":
    main()
