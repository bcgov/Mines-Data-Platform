#!/usr/bin/env python3
"""Inspection — object model report.

Built to the direction agreed on 21 July and confirmed on 11 August:

  * each subject is an OBJECT — Identity, Relationships, Derived Metrics,
    plus call-to-actions;
  * Inspection is built END-TO-END FIRST as the reference, then the same
    template is replicated for Notice of Work and Incident, swapping only the
    object-specific metadata (inspector_idir -> permit_type / application_status);
  * every figure resolves from the model — "313 in FY26/27 must update itself";
  * each KPI states its definition AND the exact date logic behind it;
  * each KPI carries a trust tag, and the object states where it sits in the
    bronze / silver / gold medallion.

Layout is sized from tools/metrics.py — the Power BI Service text metrics
measured from the live Service, not estimated.

    python3 tools/build_inspection_object.py "Fabric/Inspection Object Model.Report"
"""
import json, os, sys
from contextlib import contextmanager

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from metrics import (TB_LINE, TB_VPAD, TB_HPAD, tb_height, card_height,
                     card_min_width, wrap_lines, text_width, pt_to_px)

ROOT = sys.argv[1]
PAGES_DIR = os.path.join(ROOT, "definition", "pages")

VC = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.11.0/schema.json"
PG = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"
PM = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json"
ENTITY = "fact_inspection"

NAVY, GOLD = "#013366", "#FCBA19"
INK, MUTED, FAINT = "#252423", "#605E5C", "#8A8886"
WHITE, LINE, BODY = "#FFFFFF", "#E1DFDD", "#F2F2F2"
PILL_BG = "#E9F1F8"
BLUE, RED, GREEN, PURPLE = "#1F4E9C", "#C8102E", "#2E8540", "#5C2D91"
ALERT = "#D83B01"

W, H = 1920, 1080
MARGIN = 30
CONTENT_W = W - MARGIN * 2
HEADER_H = 108
PILL_H = 48

P_OBJ = "c0000000000000000001"
P_DEFS = "c0000000000000000002"

_state = {"page": None, "n": 0, "visuals": []}
_issues = []
_regions = []


@contextmanager
def region(x, y, w, h, label):
    _regions.append((x, y, w, h, label))
    try:
        yield
    finally:
        _regions.pop()


def lit(v):
    return {"expr": {"Literal": {"Value": v}}}


def s(t):
    return lit("'" + t + "'")


def num(v):
    return lit(f"{v}D")


def solid(c):
    return {"solid": {"color": lit("'" + c + "'")}}


def container(bg=None, border=None, radius=4):
    o = {}
    if bg:
        o["background"] = [{"properties": {"show": lit("true"), "color": solid(bg)}}]
    if border:
        o["border"] = [{"properties": {"show": lit("true"), "color": solid(border),
                                       "radius": num(radius)}}]
    o["title"] = [{"properties": {"show": lit("false")}}]
    return o


def add(vtype, x, y, w, h, body, vco=None):
    if x < 0 or y < 0 or x + w > W or y + h > H:
        _issues.append(f"{_state['page']}: {vtype} off canvas ({x},{y},{w},{h})")
    if _regions:
        rx, ry, rw, rh, lbl = _regions[-1]
        if x < rx or y < ry or x + w > rx + rw or y + h > ry + rh:
            _issues.append(f"{_state['page']}: {vtype} escapes {lbl} "
                           f"({x},{y},{x+w},{y+h}) vs ({rx},{ry},{rx+rw},{ry+rh})")
    _state["n"] += 1
    z = _state["n"] * 100
    vid = "f" + format(_state["n"], "019x")
    v = {"visualType": vtype}
    v.update(body)
    v["drillFilterOtherVisuals"] = False
    if vco:
        v["visualContainerObjects"] = vco
    _state["visuals"].append({"$schema": VC, "name": vid,
                              "position": {"x": x, "y": y, "z": z, "height": h,
                                           "width": w, "tabOrder": z},
                              "visual": v})
    return vid


def vcy(y, h):
    return y + (h - TB_LINE) // 2 - TB_VPAD // 2


def text(x, y, w, runs, align="left", lines=None):
    joined = " ".join(r[0] for r in runs)
    size = max(r[1] for r in runs)
    bold = any(r[3] for r in runs)
    h = tb_height(joined, w, size, bold, lines)
    tr = [{"value": v, "textStyle": dict({"fontSize": f"{sz}px", "color": c},
                                         **({"fontWeight": "bold"} if b else {}))}
          for v, sz, c, b in runs]
    add("textbox", x, y, w, h,
        {"objects": {"general": [{"properties": {
            "paragraphs": [{"textRuns": tr, "horizontalTextAlignment": align}]}}]}},
        container())
    return h


def rect(x, y, w, h, fill=None, border=None, radius=4):
    return add("shape", x, y, w, h,
               {"objects": {"shape": [{"properties": {"tileShape": s("rectangle")}}],
                            "fill": [{"properties": {"show": lit("false")}}],
                            "outline": [{"properties": {"show": lit("false")}}]}},
               container(bg=fill, border=border, radius=radius))


def card(x, y, w, measure, size=10, color=INK, align="left", bold=False, h=None):
    box_h = h if h is not None else card_height(size)
    props = {"fontSize": num(size), "horizontalAlignment": s(align),
             "color": solid(color)}
    if bold:
        props["bold"] = lit("true")
    add("cardVisual", x, y, w, box_h, {
        "query": {"queryState": {"Data": {"projections": [{
            "field": {"Measure": {"Expression": {"SourceRef": {"Entity": ENTITY}},
                                  "Property": measure}},
            "queryRef": f"{ENTITY}.{measure}", "nativeQueryRef": measure}]}}},
        "objects": {"label": [{"properties": {"show": lit("false")},
                               "selector": {"id": "default"}}],
                    "value": [{"properties": props, "selector": {"id": "default"}}]}},
        container())
    return box_h


def pill(x, y, w, measure, size=9, color=INK, fill=None, border=None, ph=PILL_H):
    ch = card_height(size)
    rect(x, y + (ch - ph) // 2, w, ph, fill=fill, border=border, radius=ph // 2)
    card(x, y, w, measure, size=size, color=color, align="center", bold=True)
    return ch


def button(x, y, w, h, label, color=NAVY, size=10, fill=None, border=None, bold=True):
    if text_width(label, pt_to_px(size), bold) + 26 > w:
        _issues.append(f"{_state['page']}: button {label!r} too narrow ({w})")
    objs = {"icon": [{"properties": {"shapeType": s("blank")},
                      "selector": {"id": "default"}},
                     {"properties": {"show": lit("false")}}],
            "text": [{"properties": {"show": lit("true"), "text": s(label),
                                     "fontColor": solid(color), "fontSize": num(size),
                                     "bold": lit("true" if bold else "false"),
                                     "horizontalAlignment": s("center")},
                      "selector": {"id": "default"}}],
            "outline": [{"properties": {"show": lit("false")}}]}
    if fill:
        objs["fill"] = [{"properties": {"show": lit("true")}},
                        {"properties": {"fillColor": solid(fill)},
                         "selector": {"id": "default"}}]
    else:
        objs["fill"] = [{"properties": {"show": lit("false")}}]
    add("actionButton", x, y, w, h, {"objects": objs}, container(border=border))


def start(pid, name):
    _state.update(page=name, n=0, visuals=[], pid=pid, display=name)


def finish():
    d = os.path.join(PAGES_DIR, _state["pid"])
    os.makedirs(os.path.join(d, "visuals"), exist_ok=True)
    with open(os.path.join(d, "page.json"), "w", encoding="utf-8") as f:
        json.dump({"$schema": PG, "name": _state["pid"],
                   "displayName": _state["display"], "displayOption": "FitToPage",
                   "height": H, "width": W,
                   "objects": {"background": [{"properties": {
                       "color": solid(BODY), "transparency": num(0)}}]}}, f, indent=2)
    for v in _state["visuals"]:
        vd = os.path.join(d, "visuals", v["name"])
        os.makedirs(vd, exist_ok=True)
        with open(os.path.join(vd, "visual.json"), "w", encoding="utf-8") as f:
            json.dump(v, f, indent=2)
    return len(_state["visuals"])


def chrome(subtitle):
    rect(0, 0, W, H, fill=BODY, radius=0)
    rect(0, 0, W, HEADER_H - 2, fill=WHITE, radius=0)
    rect(0, HEADER_H - 2, W, 1, fill=LINE, radius=0)
    add("image", 28, 22, 145, 42, {"objects": {"general": [{"properties": {
        "imageUrl": {"expr": {"ResourcePackageItem": {
            "PackageName": "RegisteredResources", "PackageType": 1,
            "ItemName": "Logo.png"}}}}}]}}, container())
    text(190, 18, 700, [("Mines Data Platform", 17, NAVY, True)])
    text(190, 50, 700, [(subtitle, 9, MUTED, False)], lines=1)
    ASAT_W = card_min_width("Data as at 30 September 2026", 10, bold=True) + 28
    pill(W - MARGIN - ASAT_W, 24, ASAT_W, "Hub Data As At", size=10, color=NAVY,
         fill=PILL_BG, border=PILL_BG)


# The five KPIs the object exposes. Each carries its own definition, its own
# date window and its own trust tag — all measure-bound.
KPIS = [
    ("Inspections to date", "Obj Val Total", "Obj Def Total", "Obj Win Total",
     "Obj Trust Total", BLUE),
    ("This fiscal year to date", "Obj Val FYTD", "Obj Def FYTD", "Obj Win FYTD",
     "Obj Trust FYTD", BLUE),
    ("Same point last year", "Obj Val Same Last FY", "Obj Def Same Last FY",
     "Obj Win Same Last FY", "Obj Trust Same Last FY", PURPLE),
    ("Rolling 30 days", "Obj Val Last Month", "Obj Def Last Month",
     "Obj Win Last Month", "Obj Trust Last Month", GOLD),
    ("Last completed fiscal year", "Obj Val Prev FY", "Obj Def Prev FY",
     "Obj Win Prev FY", "Obj Trust Prev FY", GREEN),
]

# =============================================================================
# PAGE 1 — Inspection, the object
# =============================================================================
start(P_OBJ, "Inspection — the object")
chrome("Object model  ·  built end-to-end as the reference, then replicated to "
       "Notice of Work and Incident")

y = HEADER_H + 16
TILE_H = 10 + 33 + card_height(10) + 10
rect(MARGIN, y, CONTENT_W, TILE_H, fill=WHITE, border=LINE)
with region(MARGIN, y, CONTENT_W, TILE_H, "object tile"):
    cy = y + 10
    rect(MARGIN + 26, cy + 6, 18, 18, fill=BLUE, radius=3)
    cy += text(MARGIN + 52, cy, 700, [("Inspection", 17, NAVY, True)])
    card(MARGIN + 26, cy, CONTENT_W - 52, "Obj Record Count", size=10, color=INK)
y += TILE_H + 14

# --- three columns: identity | relationships | call to actions ---------------
GAP = 24
COL_W = (CONTENT_W - GAP * 2) // 3
COL_H = 310
IDENTITY_CORE = ["inspection_id  —  key", "external_id", "inspection_date",
                 "completed_date", "inspection_status_id"]
IDENTITY_META = ["inspector_idir", "business_area", "assessment_sub_type",
                 "inspection_reason_id", "inspection_auth_type"]

for i, title in enumerate(["IDENTITY", "RELATIONSHIPS", "CALL TO ACTIONS"]):
    x = MARGIN + i * (COL_W + GAP)
    rect(x, y, COL_W, COL_H, fill=WHITE, border=LINE)
    with region(x, y, COL_W, COL_H, f"{title} panel"):
        cy = y + 16
        cy += text(x + 22, cy, COL_W - 44, [(title, 8, FAINT, True)], lines=1) + 2

        if i == 0:
            card(x + 22, cy, COL_W - 44, "Obj Identity Note", size=9, color=MUTED)
            cy += card_height(9) + 6
            half = (COL_W - 44 - 16) // 2
            for j, (grp, fields) in enumerate([("CORE", IDENTITY_CORE),
                                               ("METADATA — Inspection only",
                                                IDENTITY_META)]):
                gx = x + 22 + j * (half + 16)
                gy = cy
                gy += text(gx, gy, half, [(grp, 8, FAINT, True)], lines=1) - 4
                for f in fields:
                    col = NAVY if f == "inspector_idir" else INK
                    gy += text(gx, gy, half, [(f, 9, col, f == "inspector_idir")],
                               lines=1) - 6

        elif i == 1:
            cy += 2
            for m, colour in [("Obj Rel Mine", BLUE), ("Obj Rel Type", PURPLE),
                              ("Obj Rel Date", GREEN)]:
                rect(x + 22, cy, 4, card_height(9), fill=colour, radius=0)
                card(x + 34, cy, COL_W - 60, m, size=9, color=INK)
                cy += card_height(9) + 4

        else:
            cy += text(x + 22, cy, COL_W - 44,
                       [("Actions on the object, not on a chart.", 9, MUTED, False)],
                       lines=1) + 6
            for label, primary in [("Open the Inspections report", True),
                                   ("View all definitions", False),
                                   ("Export with context", False),
                                   ("Request a change", False)]:
                button(x + 22, cy, COL_W - 44, 40, label,
                       color=WHITE if primary else NAVY, size=10,
                       fill=NAVY if primary else None,
                       border=NAVY if primary else LINE)
                cy += 48
y += COL_H + 14

# --- derived metrics ---------------------------------------------------------
DM_H = (H - 44 - 12) - y
rect(MARGIN, y, CONTENT_W, DM_H, fill=WHITE, border=LINE)
with region(MARGIN, y, CONTENT_W, DM_H, "derived metrics panel"):
    cy = y + 12
    cy += text(MARGIN + 22, cy, 600, [("DERIVED METRICS", 8, FAINT, True)], lines=1) - 4
    cy += text(MARGIN + 22, cy, 900,
               [("Every figure states what it counts and the exact dates behind it",
                 12, INK, True)], lines=1) + 6

    kw = (CONTENT_W - 44 - 16 * 4) // 5
    TRUST_W = card_min_width("Not validated", 9, bold=True) + 28
    for i, (label, val_m, def_m, win_m, trust_m, colour) in enumerate(KPIS):
        kx = MARGIN + 22 + i * (kw + 16)
        kh = (y + DM_H - 12) - cy
        rect(kx, cy, kw, kh, fill="#FAFAFA", border=LINE)
        with region(kx, cy, kw, kh, f"KPI {label!r}"):
            ky = cy + 12
            rect(kx + 16, ky, 40, 3, fill=colour, radius=0)
            ky += 9
            ky += text(kx + 16, ky, kw - 32, [(label, 10, MUTED, True)], lines=1)
            card(kx + 16, ky, kw - 32, val_m, size=13, color=NAVY, bold=True)
            ky += card_height(13) + 4
            pill(kx + 16, ky, TRUST_W, trust_m, size=9, color=NAVY,
                 fill=PILL_BG, border="#B4D6F0")
            ky += card_height(9) + 6
            card(kx + 16, ky, kw - 32, win_m, size=9, color=MUTED)

text(MARGIN, H - 44, CONTENT_W,
     [("Inspection is the reference object. Notice of Work and Incident reuse this "
       "frame unchanged — only the identity metadata differs (inspector_idir becomes "
       "permit_type and application_status).", 9, FAINT, False)], lines=1)
n1 = finish()

# =============================================================================
# PAGE 2 — definitions
# =============================================================================
start(P_DEFS, "Inspection — definitions")
chrome("Every KPI: what it counts, the exact date logic, its trust state and where "
       "the data sits")

y = HEADER_H + 16
INTRO_H = 12 + 33 + 33 + card_height(9) + 12
rect(MARGIN, y, CONTENT_W, INTRO_H, fill=WHITE, border=LINE)
with region(MARGIN, y, CONTENT_W, INTRO_H, "defs intro"):
    cy = y + 12
    cy += text(MARGIN + 26, cy, 900, [("Definitions — Inspection", 17, NAVY, True)])
    cy += text(MARGIN + 26, cy, CONTENT_W - 60,
               [("Each KPI can use a different date filter, so the window is stated "
                 "explicitly next to every figure. These lines are measures — change "
                 "the definition once in the model and it changes everywhere.",
                 10, INK, False)], lines=1)
    card(MARGIN + 26, cy, CONTENT_W - 60, "Obj Coverage Note", size=9, color=MUTED)
y += INTRO_H + 14

HDR = ["KPI", "WHAT IT COUNTS", "DATE WINDOW", "TRUST"]
COLS = [300, 640, 560, 240]
row_h = card_height(9) + 8
TBL_H = 12 + 29 + len(KPIS) * row_h + 12
rect(MARGIN, y, CONTENT_W, TBL_H, fill=WHITE, border=LINE)
with region(MARGIN, y, CONTENT_W, TBL_H, "definitions table"):
    cy = y + 12
    cx = MARGIN + 22
    for i, hcol in enumerate(HDR):
        text(cx, cy, COLS[i] - 12, [(hcol, 8, FAINT, True)], lines=1)
        cx += COLS[i]
    cy += 29
    for label, val_m, def_m, win_m, trust_m, colour in KPIS:
        rect(MARGIN + 22, cy, CONTENT_W - 44, 1, fill=LINE, radius=0)
        cx = MARGIN + 22
        rect(cx, cy + 6, 4, card_height(9), fill=colour, radius=0)
        text(cx + 14, vcy(cy + 6, card_height(9)), COLS[0] - 40,
             [(label, 10, INK, True)], lines=1)
        cx += COLS[0]
        card(cx, cy + 6, COLS[1] - 20, def_m, size=9, color=INK)
        cx += COLS[1]
        card(cx, cy + 6, COLS[2] - 20, win_m, size=9, color=MUTED)
        cx += COLS[2]
        card(cx, cy + 6, COLS[3] - 20, trust_m, size=9, color=NAVY, bold=True)
        cy += row_h
y += TBL_H + 16

PROV = [("SOURCE", "Hub Def Source"), ("LAST REFRESH", "Hub Def Last Refresh"),
        ("VALIDATED BY", "Hub Def Validated By"), ("MEDALLION LAYER", "Obj Layer")]
PROV_H = (H - 44 - 12) - y
rect(MARGIN, y, CONTENT_W, PROV_H, fill=WHITE, border=LINE)
with region(MARGIN, y, CONTENT_W, PROV_H, "provenance panel"):
    cy = y + 14
    cy += text(MARGIN + 22, cy, 700, [("Where these figures come from", 12, INK, True)],
               lines=1) + 4
    qw = (CONTENT_W - 44 - 20 * 3) // 4
    for k, (label, m) in enumerate(PROV):
        px = MARGIN + 22 + k * (qw + 20)
        py = cy + text(px, cy, qw, [(label, 8, FAINT, True)], lines=1) - 4
        card(px, py, qw, m, size=9, color=INK)

text(MARGIN, H - 44, CONTENT_W,
     [("Power BI cannot auto-sync a central definitions library into per-visual "
       "tooltips, so the same measures feed this page and the hover tooltips — one "
       "edit, both places.", 9, FAINT, False)], lines=1)
n2 = finish()

with open(os.path.join(PAGES_DIR, "pages.json"), "w", encoding="utf-8") as f:
    json.dump({"$schema": PM, "pageOrder": [P_OBJ, P_DEFS],
               "activePageName": P_OBJ}, f, indent=2)

print(f"canvas {W}x{H}")
print(f"  Inspection — the object      {n1:>3} visuals")
print(f"  Inspection — definitions     {n2:>3} visuals")
if _issues:
    print(f"\n!! {len(_issues)} layout issues")
    for i in _issues:
        print("   ", i)
else:
    print("\nlayout clean: nothing clipped, nothing escapes its panel")
