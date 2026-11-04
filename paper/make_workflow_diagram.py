# /// script
# requires-python = ">=3.11"
# dependencies = ["matplotlib==3.11.2"]
# ///
"""Draw workflow-diagram, the paper's Figure 1, a generic version of the preprint's Figure 1.

    uv run paper/make_workflow_diagram.py

Writes paper/out/workflow-diagram.{pdf,svg,png} and an editable draw.io copy,
workflow-diagram.drawio. The preprint's figure drew the
TotalSegmentator workflow. This one draws the
pipeline both case studies share, following the harmonized workflow in
CloudSegmentator (workflows/harmonized): every step is shared except
segmentation, the one model-specific piece.

Style follows make_figures.py: the same ink and grid colours, and blue GPU /
orange CPU for the VM a task runs on. Green marks the model-specific step.
Positions are in millimetres, laid out top-down as depth below the top edge.

Every primitive also records a draw.io cell, at 2 px per point so draw.io font
sizes are twice the point sizes here. Stores, documents and the cloud become
native draw.io shapes, and pill, badge and store labels live inside their shape.
Edits made in draw.io do not flow back into this script.
"""

import html
import xml.etree.ElementTree as ET
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Circle, Ellipse, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle
from matplotlib.textpath import TextPath

OUT = Path(__file__).parent / "out"

INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"
GPU, CPU, MODEL = "#2a78d6", "#eb6834", "#1baf7a"
GPU_BG, CPU_BG, MODEL_BG = "#eaf1fb", "#fdefe8", "#e4f5ed"
STEP_BG, PANEL_BG = "#f4f3ef", "#fafaf8"
STORE, STORE_BG = "#b98a1e", "#fbf6ea"

FONT = ["Arial", "Helvetica", "DejaVu Sans"]
mpl.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": FONT,
    "font.size": 7, "text.color": INK,
    "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
    "savefig.dpi": 300, "savefig.pad_inches": 0,
})
PT = 25.4 / 72  # mm per point

W = 178.0  # mm, double-column width

# ---------------------------------------------------------------- layout (depth from top, mm)

# panel A
A_TITLE = 4.0
SRC_LABEL = 9.6                  # "NCI Imaging Data Commons"
SRC_TOP, SRC_H = 13.0, 9.5       # data-store cylinders: body top, height
ROW_TOP, ROW_H = 30.0, 24.0      # pipeline boxes
LEGEND = SRC_TOP + 2.6           # two rows, in the gap above the pipeline
RULE = ROW_TOP + ROW_H + 4.2

# panels B and C
BC_TITLE = RULE + 5.6
BC_SUB = BC_TITLE + 3.9
REQ_TOP, REQ_H = BC_SUB + 3.4, 16.6
EX_TOP = REQ_TOP + REQ_H + 4.0
STEP_H, STEP_GAP = 5.6, 1.8
TASK_HEAD, TASK_PAD = 4.6, 1.6
BATCH = EX_TOP + 12.0            # centre of the input-batch card
T1_TOP = BATCH + 5.6
S_TOP = [T1_TOP + TASK_HEAD + k * (STEP_H + STEP_GAP) for k in range(3)]
T1_BOT = S_TOP[2] + STEP_H + TASK_PAD
T2_TOP = T1_BOT + 6.6
S_TOP += [T2_TOP + TASK_HEAD + k * (STEP_H + STEP_GAP) for k in range(2)]
T2_BOT = S_TOP[4] + STEP_H + TASK_PAD
FORK = T2_BOT + 4.2              # where the output lines split
DOC_C = FORK + 8.0               # output document centre
REPORT = DOC_C + 7.6
EX_BOT = REPORT + 3.4
H = EX_BOT + 1.5


def Y(depth):
    return H - depth


# ---------------------------------------------------------------- draw.io cells

S = 2 / PT  # draw.io px per mm: 2 px per point
CELLS = []  # (z, kind, style, value, geometry)


def px(v):
    return f"{v * S:.2f}".rstrip("0").rstrip(".")


def stroke(ec, lw, ls="-"):
    if ec == "none":
        return "strokeColor=none;"
    st = f"strokeColor={ec};strokeWidth={px(lw * PT)};"
    if ls != "-":
        st += "dashed=1;dashPattern=" + " ".join(f"{v:g}" for v in ls[1]) + ";"
    return st


def font(size, color=INK, bold=False, italic=False):
    return (f"fontFamily=Arial;fontSize={px(size * PT)};fontColor={color};"
            f"fontStyle={int(bold) + 2 * int(italic)};")


def label(s):
    return html.escape(s).replace("\n", "<br>")


def dio_vertex(z, x, top, w, h, style, value=""):
    CELLS.append((z, "v", "html=1;" + style, value, (x, top, w, h)))


def dio_edge(z, pts, style):
    CELLS.append((z, "e", "html=1;edgeStyle=none;" + style, "", pts))


def write_drawio(path):
    root = ET.Element("mxfile", host="make_workflow_diagram.py")
    model = ET.SubElement(ET.SubElement(root, "diagram", name="workflow-diagram", id="workflow-diagram"),
                          "mxGraphModel", grid="0", page="1", pageWidth=px(W), pageHeight=px(H),
                          background="#ffffff", math="0", shadow="0")
    cells = ET.SubElement(model, "root")
    ET.SubElement(cells, "mxCell", id="0")
    ET.SubElement(cells, "mxCell", id="1", parent="0")
    for n, (z, kind, style, value, geo) in enumerate(sorted(CELLS, key=lambda c: c[0]), start=2):
        if kind == "v":
            c = ET.SubElement(cells, "mxCell", id=f"c{n}", value=value, style=style, vertex="1", parent="1")
            x, top, w, h = geo
            ET.SubElement(c, "mxGeometry", x=px(x), y=px(top), width=px(w), height=px(h),
                          **{"as": "geometry"})
        else:
            c = ET.SubElement(cells, "mxCell", id=f"c{n}", style=style, edge="1", parent="1")
            g = ET.SubElement(c, "mxGeometry", relative="1", **{"as": "geometry"})
            (x0, d0), *mid, (x1, d1) = geo
            ET.SubElement(g, "mxPoint", x=px(x0), y=px(d0), **{"as": "sourcePoint"})
            ET.SubElement(g, "mxPoint", x=px(x1), y=px(d1), **{"as": "targetPoint"})
            if mid:
                arr = ET.SubElement(g, "Array", **{"as": "points"})
                for xm, dm in mid:
                    ET.SubElement(arr, "mxPoint", x=px(xm), y=px(dm))
    ET.indent(root)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


fig = plt.figure(figsize=(W / 25.4, H / 25.4))
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, W)
ax.set_ylim(0, H)
ax.set_aspect("equal")
ax.axis("off")


# ---------------------------------------------------------------- primitives

def text_width(s, size, bold=False):
    prop = FontProperties(family=FONT, weight="bold" if bold else "normal")
    return max(TextPath((0, 0), ln, size=size, prop=prop).get_extents().width
               for ln in s.split("\n")) * PT


def box(x, top, w, h, fc, ec, lw=0.7, r=1.2, ls="-", z=1, value="", style=""):
    ax.add_patch(FancyBboxPatch((x, Y(top + h)), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
                                fc=fc, ec=ec, lw=lw, ls=ls, zorder=z))
    dio_vertex(z, x, top, w, h, f"rounded=1;absoluteArcSize=1;arcSize={px(2 * r)};fillColor={fc};"
               + stroke(ec, lw, ls) + "spacing=0;" + style, value)


def text(x, d, s, size=7, color=INK, ha="center", va="center", weight="normal", style="normal",
         z=6, dio=True):
    ax.text(x, Y(d), s, fontsize=size, color=color, ha=ha, va=va, fontweight=weight,
            fontstyle=style, zorder=z, linespacing=1.1)
    if not dio or not s:
        return
    bold = weight == "bold"
    w = text_width(s, size, bold) * 1.06 + 1.0
    h = (s.count("\n") + 1) * size * PT * 1.2
    x0 = {"center": x - w / 2, "left": x, "right": x - w}[ha]
    top = {"center": d - h / 2, "top": d, "bottom": d - h}[va]
    dio_vertex(z, x0, top, w, h, f"text;strokeColor=none;fillColor=none;spacing=0;align={ha};"
               f"verticalAlign=middle;" + font(size, color, bold, style == "italic"), label(s))


def arrow(x0, d0, x1, d1, color=INK2, lw=0.8, ls="-", z=3, rad=0.0, via=()):
    """Arrow from (x0, d0) to (x1, d1); `via` adds right-angle waypoints before the head."""
    if via:
        (xs, ds) = zip((x0, d0), *via)
        ax.plot(xs, [Y(d) for d in ds], color=color, lw=lw, ls=ls, zorder=z, solid_capstyle="butt")
        dio_edge(z, [(x0, d0), *via, (x1, d1)], "endArrow=block;endFill=1;"
                 f"endSize={px(1.5 * PT)};" + stroke(color, lw, ls))
        ax.add_patch(FancyArrowPatch((via[-1][0], Y(via[-1][1])), (x1, Y(d1)),
                                     arrowstyle="-|>,head_length=1.5,head_width=0.85", mutation_scale=1,
                                     color=color, lw=lw, ls=ls, zorder=z, shrinkA=0, shrinkB=0))
        return
    ax.add_patch(FancyArrowPatch((x0, Y(d0)), (x1, Y(d1)),
                                 arrowstyle="-|>,head_length=1.5,head_width=0.85", mutation_scale=1,
                                 color=color, lw=lw, ls=ls, zorder=z, shrinkA=0, shrinkB=0,
                                 connectionstyle=f"arc3,rad={rad}"))
    # matplotlib's arc3 is a quadratic Bezier; draw.io's curved edge takes its control point
    ctrl = [((x0 + x1) / 2 + rad * (d0 - d1), (d0 + d1) / 2 + rad * (x1 - x0))] if rad else []
    dio_edge(z, [(x0, d0), *ctrl, (x1, d1)], f"endArrow=block;endFill=1;endSize={px(1.5 * PT)};"
             f"curved={int(bool(rad))};" + stroke(color, lw, ls))


def line(xs, ds, color=INK2, lw=0.8, ls="-", z=3, dio=True):
    ax.plot(xs, [Y(d) for d in ds], color=color, lw=lw, ls=ls, zorder=z, solid_capstyle="butt")
    if dio:
        dio_edge(z, list(zip(xs, ds)), "endArrow=none;" + stroke(color, lw, ls))


def circle(cx, d, r, fc, ec, lw, z, value="", style=""):
    ax.add_patch(Circle((cx, Y(d)), r, fc=fc, ec=ec, lw=lw, zorder=z))
    dio_vertex(z, cx - r, d - r, 2 * r, 2 * r, f"ellipse;fillColor={fc};" + stroke(ec, lw) + style, value)


def pill(cx, d, s, size=5.9, ec=AXIS, color=INK2, ls="-", w=None):
    w = w or text_width(s, size) + 3.0
    h = size * PT + 1.5
    box(cx - w / 2, d - h / 2, w, h, "white", ec, lw=0.5, r=h / 2, ls=ls, z=4,
        value=label(s), style=font(size, color))
    text(cx, d, s, size=size, color=color, dio=False)


def cylinder(cx, top, w, h, name):
    e = 2.2
    ax.add_patch(Rectangle((cx - w / 2, Y(top + h)), w, h, fc=STORE_BG, ec="none", zorder=2))
    line([cx - w / 2] * 2, [top, top + h], color=STORE, lw=0.7, dio=False)
    line([cx + w / 2] * 2, [top, top + h], color=STORE, lw=0.7, dio=False)
    ax.add_patch(Ellipse((cx, Y(top + h)), w, e, fc=STORE_BG, ec=STORE, lw=0.7, zorder=1.9))
    ax.add_patch(Ellipse((cx, Y(top)), w, e, fc=STORE_BG, ec=STORE, lw=0.7, zorder=2.1))
    text(cx, top + h / 2 + 0.4, name, size=6.3, weight="bold", dio=False)
    dio_vertex(2, cx - w / 2, top - e / 2, w, h + e,
               f"shape=cylinder3;boundedLbl=1;backgroundOutline=1;size={px(e / 2)};fillColor={STORE_BG};"
               + stroke(STORE, 0.7) + "spacing=0;" + font(6.3, bold=True), label(name))


def badge(cx, d, n, color=INK2, r=1.6):
    circle(cx, d, r, color, "white", 0.6, 6, value=str(n), style="spacing=0;" + font(5.8, "white", True))
    text(cx, d + 0.05, str(n), size=5.8, color="white", weight="bold", z=7, dio=False)


def panel_title(x, d, letter, title, sub=None):
    text(x, d, letter, size=9, weight="bold", ha="left")
    text(x + 4.6, d, title, size=7.5, weight="bold", ha="left")
    if sub:
        text(x + 4.6, d + 3.9, sub, size=6.1, color=INK2, style="italic", ha="left")


def document(cx, d, w, h, name, sub, stack=0):
    f = 2.0
    for k in range(stack, -1, -1):
        x0, y0 = cx - w / 2 + 1.1 * k, Y(d + h / 2) + 1.1 * k
        ec = INK2 if k == 0 else AXIS
        ax.add_patch(Polygon([(x0, y0), (x0 + w, y0), (x0 + w, y0 + h - f), (x0 + w - f, y0 + h),
                              (x0, y0 + h)], closed=True, fc="white", ec=ec, lw=0.6, zorder=4 - 0.1 * k))
        value = (f'<b>{label(name)}</b><br><font style="font-size:{px(5.6 * PT)}px" color="{INK2}">'
                 f"{label(sub)}</font>") if k == 0 else ""
        dio_vertex(4 - 0.1 * k, x0, d - h / 2 - 1.1 * k, w, h,
                   f"shape=note;size={px(f)};fillColor=white;" + stroke(ec, 0.6)
                   + "spacing=0;" + font(6.1), value)
    text(cx, d - 1.2, name, size=6.1, weight="bold", dio=False)
    text(cx, d + 1.6, sub, size=5.6, color=INK2, dio=False)


def monitor(cx, d, color=MUTED):
    box(cx - 3.0, d - 2.6, 6.0, 4.0, "white", color, lw=0.8, r=0.5, z=4)
    line([cx, cx], [d + 1.4, d + 2.6], color=color)
    line([cx - 1.6, cx + 1.6], [d + 2.6, d + 2.6], color=color)


def cloud(cx, d, color=MUTED):
    for dx, dy, r in [(-2.1, 0.3, 1.4), (-0.4, -0.6, 1.9), (1.7, 0.1, 1.5)]:
        ax.add_patch(Circle((cx + dx, Y(d + dy)), r, fc="white", ec=color, lw=0.8, zorder=4))
    ax.add_patch(Rectangle((cx - 2.1, Y(d + 1.7)), 3.8, 1.5, fc="white", ec="none", zorder=4.1))
    line([cx - 2.1, cx + 1.7], [d + 1.7, d + 1.7], color=color, z=4.2, dio=False)
    dio_vertex(4, cx - 3.9, d - 2.9, 7.8, 4.8, "ellipse;shape=cloud;fillColor=white;" + stroke(color, 0.8))


# ---------------------------------------------------------------- panel A: the shared pipeline

panel_title(2.0, A_TITLE, "A", "Analysis workflow")

GAP = 8.6
STEPS = [
    # badge, title, tools, width, model-specific
    ("", "Cohort\nselection", ["idc-index"], 15.6, False),
    (1, "Data\nretrieval", ["idc-index"], 15.6, False),
    (2, "Input format\nconversion", ["dcm2niix"], 16.4, False),
    (3, "Segmentation", ["TotalSegmentator v1", "MOOSE", "TotalSegmentator v2"], 25.0, True),
    (4, "Feature\nextraction", ["pyradiomics", "Radiomics.jl"], 16.4, False),
    (5, "Output format\nconversion", ["dcmqi"], 16.4, False),
]
EDGES = ["series\nUIDs", "DICOM", "NIfTI\nvolume", "NIfTI\nlabels", "features", "DICOM"]
MID = ROW_TOP + ROW_H / 2

x = 2.0
xs = []
for (n, title, tools, w, special), edge in zip(STEPS, EDGES):
    ec, fc = (MODEL, MODEL_BG) if special else (AXIS, STEP_BG)
    box(x, ROW_TOP, w, ROW_H, fc, ec, lw=1.0 if special else 0.7)
    if n != "":
        badge(x + w / 2, ROW_TOP, n, color=MODEL if special else INK2)
    text(x + w / 2, ROW_TOP + (5.4 if "\n" in title else 4.3), title, size=6.6, weight="bold")
    d = ROW_TOP + (11.6 if "\n" in title else 9.4)
    for t in tools:
        pill(x + w / 2, d, t, w=w - 2.6)
        d += 3.75
    if special:
        pill(x + w / 2, d, "any other model", ec=MODEL, color=MODEL, ls=(0, (2, 1.2)), w=w - 2.6)
    xs.append((x, w))
    arrow(x + w, MID, x + w + GAP, MID)
    text(x + w + GAP / 2, MID - 3.3, edge, size=5.4, color=MUTED, style="italic")
    x += w + GAP

OUT_CX = x + 8.4
document(OUT_CX, MID - 5.3, 16.6, 8.2, "DICOM SEG", "segmentations")
document(OUT_CX, MID + 5.3, 16.6, 8.2, "DICOM SR", "features")
assert OUT_CX + 8.3 < W - 1, OUT_CX

# where the data come from and where the results go
(sel_x, sel_w), (ret_x, ret_w), (cnv_x, cnv_w) = xs[:3]
NARROW = 3.0                     # stores are this much narrower than the step below them
SRC_BOT = SRC_TOP + SRC_H + 1.1  # bottom of the lower cap
box(0.8, SRC_LABEL - 2.6, ret_x + ret_w + 0.8, SRC_BOT + 1.8 - (SRC_LABEL - 2.6), "none", STORE,
    lw=0.6, ls=(0, (3, 1.5)), r=1.6, z=0.5)
text(2.6, SRC_LABEL, "NCI Imaging Data Commons", size=6.0, color=STORE, weight="bold", ha="left")
text(ret_x + ret_w + 0.2, SRC_LABEL, "public data", size=5.6, color=INK2, style="italic", ha="right")
cylinder(sel_x + sel_w / 2, SRC_TOP, sel_w - NARROW, SRC_H, "DICOM\nmetadata")
cylinder(ret_x + ret_w / 2, SRC_TOP, ret_w - NARROW, SRC_H, "DICOM\nfiles")
PRIV_CX = cnv_x + cnv_w / 2 + 3.0
cylinder(PRIV_CX, SRC_TOP, cnv_w - NARROW, SRC_H, "Private\nbucket")
text(PRIV_CX, SRC_LABEL, "optional input", size=5.6, color=INK2, style="italic")
for cx in (sel_x + sel_w / 2, ret_x + ret_w / 2):
    arrow(cx, SRC_BOT, cx, ROW_TOP - (1.6 if cx != sel_x + sel_w / 2 else 0))
# down, then left along the gap between the IDC group and the pipeline row, then into retrieval
ELBOW = (SRC_BOT + 1.8 + ROW_TOP - 1.6) / 2
arrow(PRIV_CX, SRC_BOT, ret_x + ret_w - 3.0, ROW_TOP, ls=(0, (2.2, 1.4)), color=MUTED,
      via=[(PRIV_CX, ELBOW), (ret_x + ret_w - 3.0, ELBOW)])
text(PRIV_CX + 1.2, (SRC_BOT + ELBOW) / 2, "s5cmd", size=5.4, color=MUTED, style="italic", ha="left")

cylinder(OUT_CX, SRC_TOP, 16.6 - NARROW, SRC_H, "Results\nstore")
text(OUT_CX, SRC_LABEL, "bucket, DICOM store", size=5.6, color=INK2, style="italic")
arrow(OUT_CX, MID - 9.4, OUT_CX, SRC_BOT)

# legend
for k, (fc, ec, lab) in enumerate([(STEP_BG, AXIS, "the same for every model"),
                                   (MODEL_BG, MODEL, "model-specific: the only step that changes between models")]):
    box(84.0, LEGEND + 4.6 * k - 1.4, 4.2, 2.8, fc, ec, lw=0.7, r=0.6)
    text(89.6, LEGEND + 4.6 * k, lab, size=6.0, color=INK2, ha="left")
line([1.0, W - 1.0], [RULE] * 2, color=GRID, lw=0.6)


# ---------------------------------------------------------------- panels B and C

STEP_NAMES = ["Data retrieval", "Input format conversion", "Segmentation", "Feature extraction",
              "Output format conversion"]
SW = 36.0  # step box width


def steps(cx):
    for i, top in enumerate(S_TOP):
        special = i == 2
        box(cx - SW / 2, top, SW, STEP_H, MODEL_BG if special else "white", MODEL if special else AXIS,
            lw=0.9 if special else 0.6, r=0.9, z=5)
        badge(cx - SW / 2 + 3.0, top + STEP_H / 2, i + 1, color=MODEL if special else INK2, r=1.5)
        text(cx + 1.6, top + STEP_H / 2, STEP_NAMES[i], size=6.2)


def requirements(x0, w, kind, tools, cols):
    box(x0, REQ_TOP, w, REQ_H, PANEL_BG, AXIS, lw=0.7, r=1.6)
    text(x0 + 2.2, REQ_TOP + 3.0, "Requirements", size=6.5, weight="bold", ha="left")
    text(x0 + w - 2.2, REQ_TOP + 3.0, kind, size=6.1, color=INK2, style="italic", ha="right")
    pw = (w - 4.4 - 2.0 * (cols - 1)) / cols
    for k, t in enumerate(tools):
        r, c = divmod(k, cols)
        pill(x0 + 2.2 + pw / 2 + c * (pw + 2.0), REQ_TOP + 8.6 + r * 4.4, t, w=pw)


def execution(x0, w, sub):
    box(x0, EX_TOP, w, EX_BOT - EX_TOP, PANEL_BG, AXIS, lw=0.7, r=1.6)
    text(x0 + 2.2, EX_TOP + 3.0, "Execution", size=6.5, weight="bold", ha="left")
    text(x0 + 2.2, EX_TOP + 6.2, sub, size=6.0, color=INK2, ha="left")


def checkpoints(x, ds, note):
    end = FORK - 1.0
    line([x, x], [ds[0], end - 1.4], color=MUTED, lw=0.7, z=4)
    arrow(x, end - 1.6, x, end, color=MUTED, lw=0.7)
    for d in ds:
        circle(x, d, 1.5, "white", INK2, 0.8, 5)
    text(x, end + 1.4, note, size=5.5, color=MUTED, style="italic", va="top")


def outputs(cx, stack):
    line([cx, cx], [S_TOP[4] + STEP_H if not stack else T2_BOT, FORK])
    line([cx - 9.5, cx + 9.5], [FORK, FORK])
    for dx, label, sub in [(-9.5, "Output 1", "DICOM SEG"), (9.5, "Output 2", "DICOM SR")]:
        arrow(cx + dx, FORK, cx + dx, DOC_C - 4.1 - 1.1 * stack)
        document(cx + dx, DOC_C, 16.6, 8.2, label, sub, stack=stack)


# ---- B
BX, BW = 2.0, 78.0
B_CX = BX + BW / 2
panel_title(BX, BC_TITLE, "B", "Traditional pipeline", "one pre-configured machine runs every step")
requirements(BX, BW, "platform-specific",
             ["data access clients", "dcm2niix", "model + framework", "GPU driver, CUDA",
              "radiomics library", "dcmqi"], cols=3)
execution(BX, BW, "a workstation or a single VM")
monitor(BX + BW - 6.0, EX_TOP + 4.0)
pill(B_CX, BATCH, "input: list of series", size=6.0, w=28.0)
arrow(B_CX, BATCH + 2.0, B_CX, S_TOP[0])
steps(B_CX)
for i in range(4):
    arrow(B_CX, S_TOP[i] + STEP_H, B_CX, S_TOP[i + 1])
outputs(B_CX, stack=0)

# ---- C
CX0, CW = 86.0, 63.0
C_CX = CX0 + 37.0
panel_title(CX0, BC_TITLE, "C", "Workflow-manager implementation",
            "a workflow manager runs containerized tasks")
requirements(CX0, CW, "platform-independent",
             ["workflow manager (WDL)", "container images", "pipeline code (notebooks)"], cols=2)
execution(CX0, CW, "cloud VMs, provisioned per task")
cloud(CX0 + CW - 6.0, EX_TOP + 4.0)

for k in (2, 1, 0):
    box(C_CX - 14.0 + 1.1 * k, BATCH - 2.0 - 1.1 * k, 28.0, 4.0, "white", INK2 if k == 0 else AXIS,
        lw=0.6, r=2.0, z=4.5 - 0.1 * k)
text(C_CX, BATCH, "input: one batch of series", size=6.0, color=INK2)
arrow(C_CX, BATCH + 2.0, C_CX, T1_TOP)


def task(top, bot, label, vm, ec, fc):
    x0, w = C_CX - SW / 2 - 2.6, SW + 5.2
    for k in (2, 1):  # parallel copies of the task
        box(x0 + 1.0 * k, top + 1.0 * k, w, bot - top, "white", ec, lw=0.4, r=1.4, z=2 - 0.1 * k)
    box(x0, top, w, bot - top, fc, ec, lw=0.9, r=1.4, z=2.2)
    text(x0 + 2.0, top + 2.4, label, size=6.2, weight="bold", ha="left", color=ec)
    text(x0 + w - 2.0, top + 2.4, vm, size=5.8, ha="right", color=ec)


task(T1_TOP, T1_BOT, "Task 1 container", "GPU VM, preemptible", GPU, GPU_BG)
task(T2_TOP, T2_BOT, "Task 2 container", "CPU VM, preemptible", CPU, CPU_BG)
steps(C_CX)
for i in (0, 1, 3):
    arrow(C_CX, S_TOP[i] + STEP_H, C_CX, S_TOP[i + 1])
line([C_CX, C_CX], [S_TOP[2] + STEP_H, T1_BOT + 2.0])
arrow(C_CX, T1_BOT + 2.0, C_CX, T2_TOP)
text(C_CX + 1.4, T1_BOT + 4.0, "NIfTI labels", size=5.4, color=MUTED, style="italic", ha="left")
line([C_CX, C_CX], [S_TOP[4] + STEP_H, T2_BOT])
outputs(C_CX, stack=2)
text(C_CX + 3.0, REPORT, "plus an execution report: logs, cost, usage", size=5.8, color=INK2,
     style="italic")
checkpoints(CX0 + 9.0, [BATCH, T1_TOP + 2.4, T2_TOP + 2.4],
            "re-entry at\neach task\nboundary;\npreempted\ntasks retried")

# what the workflow manager adds
AX = CX0 + CW + 3.4
for d, head, body in [
    (REQ_TOP + REQ_H / 2, "Portability", "one definition runs\non any platform\nwith the manager"),
    (S_TOP[1] + STEP_H / 2, "Scalability", "thousands of\nbatches run\nin parallel"),
    ((S_TOP[3] + S_TOP[4] + STEP_H) / 2, "Automatic\nresource\nmanagement",
     "VMs allocated per\ntask and released\nwhen it ends"),
]:
    arrow(AX + 1.8, d, AX - 2.0, d, color=MUTED, lw=0.7)
    nh = head.count("\n") + 1
    text(AX + 2.8, d - 1.3, head, size=6.3, weight="bold", ha="left", va="top")
    text(AX + 2.8, d - 1.3 + 2.75 * nh + 0.5, body, size=5.7, color=INK2, ha="left", va="top")

OUT.mkdir(exist_ok=True)
for ext in ("pdf", "svg", "png"):
    fig.savefig(OUT / f"workflow-diagram.{ext}")
write_drawio(OUT / "workflow-diagram.drawio")
print(f"{W:.0f} x {H:.0f} mm ->", *(OUT / f"workflow-diagram.{e}" for e in ("pdf", "svg", "png", "drawio")))
