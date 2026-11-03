# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow>=10"]
# ///
"""Crop the captured 3D view to the row and label each model below it, with brackets per tool.

    uv run paper/example-case/annotate.py <raw.png> <raw.json> [<raw.png> <raw.json> ...] <out.png>

raw.json is what slicer_scene.capture() returns: each model's horizontal extent and the row's
vertical extent, as fractions of the captured image. Several pairs, one per row of a multi-row
layout, are labelled one row at a time and stacked top to bottom. Needs no Slicer, so labels can
be restyled from the raw captures.
"""

import json
import sys

from PIL import Image, ImageDraw, ImageFont

FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"
LABELS = {"CT": "CT (coronal)", "total": "total", "lung_vessels": "lung_vessels"}
GROUPS = [
    ("TotalSegmentator", ["total", "lung_vessels"]),
    ("MOOSE (clin_ct_*)", [m for m in [
        "clin_ct_body", "clin_ct_body_composition", "clin_ct_cardiac", "clin_ct_digestive", "clin_ct_lungs",
        "clin_ct_muscles", "clin_ct_organs", "clin_ct_peripheral_bones", "clin_ct_ribs", "clin_ct_vertebrae"]]),
]
TEXT = (34, 34, 34)
RULE = (110, 110, 110)


def main(rows, outPath, fontPx=26, marginPx=16, rowGapPx=None):
    """Label each row and stack the rows; `rows` is a list of (raw.png, raw.json) pairs, top row first."""
    infos = [json.load(open(capturePath)) for _, capturePath in rows]
    if len({tuple(info["size_px"]) for info in infos}) > 1:
        raise SystemExit("rows were captured at different view sizes, so their scales differ")
    # capture() centres each row in the view at a shared scale, so one horizontal crop lines the rows up
    x0 = min(info["slots"][0]["x0"] for info in infos)
    x1 = max(info["slots"][-1]["x1"] for info in infos)
    panels = [labelRow(Image.open(rawPath).convert("RGB"), info, x0, x1, fontPx, marginPx)
              for (rawPath, _), info in zip(rows, infos)]
    rowGapPx = fontPx if rowGapPx is None else rowGapPx
    out = Image.new("RGB", (panels[0].width, sum(p.height for p in panels) + rowGapPx * (len(panels) - 1)), "white")
    y = 0
    for panel in panels:
        out.paste(panel, (0, y))
        y += panel.height + rowGapPx
    out.save(outPath)
    print(outPath, out.size)


def labelRow(image, info, x0, x1, fontPx, marginPx):
    width, height = image.size
    slots = info["slots"]
    # Clamped, because a row that fills the view height leaves less than marginPx above and below it
    left = max(0, int(x0 * width) - marginPx)
    right = min(width, int(x1 * width) + marginPx)
    top = max(0, int(info["rowTop"] * height) - marginPx)
    bottom = min(height, int(info["rowBottom"] * height) + marginPx)
    row = image.crop((left, top, right, bottom))

    font = ImageFont.truetype(FONT, fontPx)
    groupFont = ImageFont.truetype(FONT, int(fontPx * 1.1))
    lineHeight = int(fontPx * 1.25)
    labelBand = 2 * lineHeight + marginPx  # room for a wrapped label
    groupBand = int(fontPx * 2.6)
    out = Image.new("RGB", (row.width, row.height + labelBand + groupBand), "white")
    out.paste(row, (0, 0))
    draw = ImageDraw.Draw(out)

    def px(fraction):
        return fraction * width - left

    centres = {}
    gap = (slots[1]["x0"] - slots[0]["x1"]) * width
    for slot in slots:
        x0, x1 = px(slot["x0"]), px(slot["x1"])
        centres[slot["model"]] = (x0, x1)
        text = LABELS.get(slot["model"], slot["model"].removeprefix("clin_ct_"))
        lines = [text]
        if draw.textlength(text, font=font) > (x1 - x0) + gap and "_" in text:
            head, tail = text.split("_", 1)
            lines = [head + "_", tail]
        for n, line in enumerate(lines):
            draw.text(((x0 + x1) / 2, row.height + marginPx / 2 + n * lineHeight), line,
                      font=font, fill=TEXT, anchor="ma")

    ruleY = row.height + labelBand + int(fontPx * 0.4)
    tick = int(fontPx * 0.35)
    for name, models in GROUPS:
        models = [m for m in models if m in centres]  # a group can span rows; bracket this row's part
        if not models:
            continue
        x0 = min(centres[m][0] for m in models)
        x1 = max(centres[m][1] for m in models)
        draw.line([(x0, ruleY - tick), (x0, ruleY), (x1, ruleY), (x1, ruleY - tick)], fill=RULE, width=max(2, round(fontPx / 13)))
        draw.text(((x0 + x1) / 2, ruleY + int(fontPx * 0.35)), name, font=groupFont, fill=TEXT, anchor="ma")
    return out


if __name__ == "__main__":
    if len(sys.argv) < 4 or len(sys.argv) % 2:
        raise SystemExit(__doc__)
    main(list(zip(sys.argv[1:-1:2], sys.argv[2:-1:2])), sys.argv[-1])
