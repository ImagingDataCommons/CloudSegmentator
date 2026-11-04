# /// script
# requires-python = ">=3.11"
# ///
"""Check figures.csv, which maps figure keywords to figure numbers, and number the figures.

The manuscript cites figures by keyword - "Figure [stage-times]", "Figure [workflow-diagram]B"
- and the scripts here name each figure's files, and the function that draws it, by the same
keyword. Figures can then be added, dropped or reordered without renumbering anything.
Numbers are assigned once, when the order is final, in the `number` column of figures.csv.
Keywords that are panels of one figure share its number.

    uv run paper/number_figures.py                               # check figures.csv against out/
    uv run paper/number_figures.py --manuscript TEXT             # also check what TEXT cites
    uv run paper/number_figures.py --manuscript TEXT --assign    # number by first citation
    uv run paper/number_figures.py --export DIR                  # copy as DIR/figure-<N>.<ext>

TEXT is the manuscript as plain text or Markdown with tracked changes accepted; a deleted
citation still counts. Citations by keyword and by number are both checked against
figures.csv. --assign numbers the figures cited by keyword 1, 2, ... in order of first
citation, clears the number of every figure not cited, and keeps numbers that are not plain
integers (S1, S2, ... for supplementary figures). It refuses a TEXT that already cites figures
by number; set the numbers by hand then. `file` names the output to use when it is not the
keyword itself, as for the two-row layout of cs2-sample-result. A figure with no `script` is
not drawn here and has to be supplied separately, as do the panels of a shared number, which
are exported one file per keyword.
"""

import argparse
import csv
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
MAP, OUT = HERE / "figures.csv", HERE / "out"
FIELDS = ["keyword", "number", "file", "script", "title"]
FORMATS = (".pdf", ".svg", ".png")
KEYWORD = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
# A keyword in brackets, escaped as pandoc writes it or not
BRACKETED = re.compile(r"\\?\[(" + KEYWORD.pattern + r")\\?\]")
CITED = re.compile(r"Fig(?:ure)?s?\.?\s*" + BRACKETED.pattern)
# A citation by number, panel letter ignored: "Figure 1B" cites Figure 1
NUMBERED = re.compile(r"Fig(?:ure)?s?\.?\s*(S?\d+)")


def load():
    with MAP.open(newline="") as f:
        rows = list(csv.DictReader(f))
    errors = []
    if rows and list(rows[0]) != FIELDS:
        errors.append(f"{MAP.name}: columns should be {','.join(FIELDS)}")
    for kw in {r["keyword"] for r in rows if [s["keyword"] for s in rows].count(r["keyword"]) > 1}:
        errors.append(f"{kw}: listed twice")
    for r in rows:
        if not KEYWORD.fullmatch(r["keyword"]):
            errors.append(f"{r['keyword']!r}: a keyword is lowercase words joined by hyphens")
    return rows, errors


def shared_numbers(rows):
    """Numbers given to more than one keyword: figures made of panels drawn separately."""
    counts = Counter(r["number"] for r in rows if r["number"])
    return {n for n, c in counts.items() if c > 1}


def outputs(row):
    return sorted(OUT.glob((row["file"] or row["keyword"]) + ".*"), key=lambda p: p.suffix)


def check_outputs(rows, errors, warnings):
    if not OUT.is_dir():
        warnings.append("no out/ yet; run the figure scripts to check their outputs")
        return
    for r in rows:
        if r["script"] and not any(p.suffix in FORMATS for p in outputs(r)):
            (errors if r["number"] else warnings).append(
                f"{r['keyword']}: no {r['file'] or r['keyword']}.pdf/.svg/.png in out/; run {r['script']}")
    # Every output is <keyword>.<ext> or <keyword>_<variant>.<ext>
    keywords = {r["keyword"] for r in rows}
    for kw in sorted({p.name.split(".")[0].split("_")[0] for p in OUT.iterdir()} - keywords):
        warnings.append(f"out/{kw}*: not a keyword in {MAP.name}")


def check_manuscript(rows, text, errors, warnings):
    """Return the keywords in order of first citation."""
    keywords = {r["keyword"] for r in rows}
    first = {}
    for m in BRACKETED.finditer(text):
        if m.group(1) in keywords:
            first.setdefault(m.group(1), m.start())
    for kw in sorted({m.group(1) for m in CITED.finditer(text)} - keywords):
        errors.append(f"{kw}: cited as a figure but not in {MAP.name}")
    numbers = {m.group(1) for m in NUMBERED.finditer(text)}
    for n in sorted(numbers - {r["number"] for r in rows}, key=lambda n: n.zfill(3)):
        errors.append(f"Figure {n}: cited, but no keyword in {MAP.name} has that number")
    for r in rows:
        if r["number"] and r["keyword"] not in first and r["number"] not in numbers:
            warnings.append(f"{r['keyword']}: numbered {r['number']} but not cited")
        if not r["number"] and r["keyword"] in first:
            warnings.append(f"{r['keyword']}: cited but not numbered yet")
    return sorted(first, key=first.get)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manuscript", type=Path, help="manuscript text, tracked changes accepted")
    ap.add_argument("--assign", action="store_true", help="write numbers in order of first citation")
    ap.add_argument("--export", type=Path, metavar="DIR", help="copy the numbered figures to DIR")
    args = ap.parse_args()
    if args.assign and not args.manuscript:
        ap.error("--assign needs --manuscript")

    rows, errors = load()
    warnings = []
    if args.manuscript:
        text = args.manuscript.read_text()
        order = check_manuscript(rows, text, errors, warnings)
        if args.assign and NUMBERED.search(text):
            errors.append(f"--assign: {args.manuscript.name} already cites figures by number; "
                          f"set them in {MAP.name} by hand")
        if args.assign and not errors:
            for r in rows:
                if r["keyword"] in order:
                    r["number"] = str(order.index(r["keyword"]) + 1)
                elif r["number"].isdigit():
                    r["number"] = ""
            with MAP.open("w", newline="") as f:
                writer = csv.DictWriter(f, FIELDS, lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
            warnings = []
            check_manuscript(rows, text, [], warnings)
            print(f"numbered {len(order)} figures in {MAP.name}")
    check_outputs(rows, errors, warnings)

    for r in sorted(rows, key=lambda r: (not r["number"], r["number"].zfill(3))):
        files = ", ".join(p.name for p in outputs(r) if p.suffix in FORMATS) or "-"
        print(f"{r['number'] or '-':>4}  {r['keyword']:<20} {r['script'] or 'not drawn here':<28} {files}")
    for w in warnings:
        print("warning:", w)
    for e in errors:
        print("error:", e)
    if errors:
        sys.exit(1)

    if args.export:
        args.export.mkdir(parents=True, exist_ok=True)
        shared = shared_numbers(rows)
        for r in rows:
            if not r["number"]:
                continue
            name = f"figure-{r['number']}"
            if r["number"] in shared:
                name += f"_{r['keyword']}"
            if not r["script"]:
                print(f"Figure {r['number']} ({r['keyword']}) is not drawn here; supply it separately")
            for p in outputs(r):
                if p.suffix in FORMATS:
                    shutil.copy2(p, args.export / f"{name}{p.suffix}")
        for n in sorted(shared, key=lambda n: n.zfill(3)):
            print(f"Figure {n} has panels from several keywords, exported one file each; combine them")
        print("exported to", args.export)


if __name__ == "__main__":
    main()
