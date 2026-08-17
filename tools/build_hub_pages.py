#!/usr/bin/env python3
"""Generate the whole Option C hub: 4 persona pages + definitions + request-a-change
+ access/data states, as PBIR pages.

v2 - laid out against Power BI Service text metrics measured from the live report
(see metrics.py). v1 was sized against an HTML approximation, which clipped every
textbox and collapsed every small card.

Every value slot is a cardVisual bound to a measure on the Gold Inspections Semantic
Model - nothing is typed in (Romil's rule: "313 in FY26/27 must update itself").

Page-navigation links are OFF by default: Fabric's report import schema rejects the
`visualLink` property. Pass --nav to re-enable once the correct shape is confirmed.
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from metrics import (TB_LINE, TB_VPAD, TB_HPAD, CARD_LINE, CARD_VPAD,
                     tb_height, card_height, card_min_width, card_lines,
                     wrap_lines, text_width, pt_to_px, fit_size)

ROOT = sys.argv[1]
NAV = "--nav" in sys.argv
PAGES_DIR = os.path.join(ROOT, "definition", "pages")

VC = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.11.0/schema.json"
PG = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"
PM = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json"
ENTITY = "fact_inspection"

# --- BC design-system tokens -------------------------------------------------
NAVY, GOLD = "#013366", "#FCBA19"
INK, MUTED, FAINT = "#252423", "#605E5C", "#8A8886"
WHITE, LINE, BODY = "#FFFFFF", "#E1DFDD", "#F2F2F2"
PILL_BG = "#E9F1F8"
BLUE, RED, GREEN, PURPLE = "#1F4E9C", "#C8102E", "#2E8540", "#5C2D91"
ALERT = "#D83B01"

BADGE = {
    "certified":   ("#0F6CBD", "#EFF6FC", "#B4D6F0"),
    "promoted":    ("#107C41", "#F1FAF1", "#9FD5A0"),
    "provisional": ("#8A6100", "#FFF9E6", GOLD),
    "notvalid":    (MUTED,     "#F3F2F1", "#D2D0CE"),
}

# 1920x1080 - true 16:9, no letterboxing. Text metrics are fixed in CANVAS units
# (a 21px line box, ~40px of card chrome), so a larger canvas is the only lever
# that makes type relatively smaller and fits more content. It also gives the
# commentary cards the width they need: cardVisual does NOT wrap, so a long
# sentence has to fit on one line or it is ellipsised.
W, H = 1920, 1080
MARGIN = 30
CONTENT_W = W - MARGIN * 2          # 1540

# --- page registry -----------------------------------------------------------
P_EXEC = "b0000000000000000001"
P_COMP = "b0000000000000000002"
P_PERM = "b0000000000000000003"
P_AUDIT = "b0000000000000000004"
P_DEFS = "b0000000000000000005"
P_CHANGE = "b0000000000000000006"
P_STATES = "b0000000000000000007"

PERSONAS = [("All", None), ("Executive", P_EXEC), ("Compliance & Enforcement", P_COMP),
            ("Permitting & Titles", P_PERM), ("Audit & Analysis", P_AUDIT)]

# Rail geometry derived from the rendered label width (button fonts are points).
def _rail_geom():
    x, geom = MARGIN, []
    for label, _ in PERSONAS:
        w = int(text_width(label, pt_to_px(10), True) * 1.10) + 36
        geom.append((x, w))
        x += w + 10
    return geom

RAIL_GEOM = _rail_geom()

_state = {"page": None, "n": 0, "visuals": []}
_issues = []


# --- PBIR primitives ---------------------------------------------------------
def lit(v):
    return {"expr": {"Literal": {"Value": v}}}


def s(txt):
    return lit("'" + txt + "'")


def num(v):
    return lit(f"{v}D")


def solid(color):
    return {"solid": {"color": lit("'" + color + "'")}}


def container(bg=None, border=None, radius=4, title=False):
    o = {}
    if bg:
        o["background"] = [{"properties": {"show": lit("true"), "color": solid(bg)}}]
    if border:
        p = {"show": lit("true"), "color": solid(border)}
        if radius is not None:
            p["radius"] = num(radius)
        o["border"] = [{"properties": p}]
    o["title"] = [{"properties": {"show": lit("true" if title else "false")}}]
    return o


def add(vtype, x, y, w, h, visual_body, vc_objects=None, link_to=None):
    if x < 0 or y < 0 or x + w > W or y + h > H:
        _issues.append(f"{_state['page']}: {vtype} out of canvas "
                       f"({x},{y},{w},{h})")
    _state["n"] += 1
    z = _state["n"] * 100
    vid = "f" + format(_state["n"], "019x")
    body = {"visualType": vtype}
    body.update(visual_body)
    if link_to and NAV:
        body["visualLink"] = {"type": "PageNavigation", "navigationSection": link_to}
    body["drillFilterOtherVisuals"] = False
    if vc_objects:
        body["visualContainerObjects"] = vc_objects
    _state["visuals"].append({
        "$schema": VC, "name": vid,
        "position": {"x": x, "y": y, "z": z, "height": h, "width": w, "tabOrder": z},
        "visual": body})
    return vid


# --- element helpers ---------------------------------------------------------
def vcy(y, h):
    """Top for a one-line textbox whose glyph should centre on a y..y+h shape.
    The 21px line box sits TB_VPAD/2 below the box top."""
    return y + (h - TB_LINE) // 2 - TB_VPAD // 2


def text(x, y, w, runs, align="left", lines=None):
    """Auto-heights to the Service's 21px line box. Returns the height used."""
    joined = " ".join(r[0] for r in runs)
    size = max(r[1] for r in runs)
    bold = any(r[3] for r in runs)
    h = tb_height(joined, w, size, bold, lines)
    tr = []
    for value, sz, color, bd in runs:
        style = {"fontSize": f"{sz}px", "color": color}
        if bd:
            style["fontWeight"] = "bold"
        tr.append({"value": value, "textStyle": style})
    add("textbox", x, y, w, h,
        {"objects": {"general": [{"properties": {
            "paragraphs": [{"textRuns": tr, "horizontalTextAlignment": align}]}}]}},
        container(title=False))
    return h


def rect(x, y, w, h, fill=None, border=None, radius=4):
    return add("shape", x, y, w, h,
               {"objects": {"shape": [{"properties": {"tileShape": s("rectangle")}}],
                            "fill": [{"properties": {"show": lit("false")}}],
                            "outline": [{"properties": {"show": lit("false")}}]}},
               container(bg=fill, border=border, radius=radius))


def oval(x, y, w, h, fill):
    return add("shape", x, y, w, h,
               {"objects": {"shape": [{"properties": {"tileShape": s("oval")}}],
                            "fill": [{"properties": {"show": lit("true"),
                                                     "fillColor": solid(fill)}}],
                            "outline": [{"properties": {"show": lit("false")}}]}},
               container(title=False))


def measure_card(x, y, w, measure, size=10, color=INK, align="center", bold=False,
                 bg=None, border=None, radius=4, lines=1, sample=None):
    """Always ONE line - cardVisual does not word-wrap, it ellipsises. The point
    size is stepped down if the measure's widest real value would not fit, and
    an issue is recorded if even the smallest size overflows."""
    lines = 1
    h = card_height(lines)
    pill = bool(bg or border)
    sample = sample or SAMPLES.get(measure)
    if sample:
        fitted = fit_size(sample, w, pill, bold, tuple(
            n for n in (size, size - 1, size - 2) if n >= 8))
        if card_min_width(sample, fitted, pill, bold) > w:
            _issues.append(f"{_state['page']}: card '{measure}' w={w} needs "
                           f"{card_min_width(sample, fitted, pill, bold)} at {fitted}pt")
        size = fitted
    props = {"fontSize": num(size), "horizontalAlignment": s(align), "color": solid(color)}
    if bold:
        props["bold"] = lit("true")
    add("cardVisual", x, y, w, h, {
        "query": {"queryState": {"Data": {"projections": [{
            "field": {"Measure": {"Expression": {"SourceRef": {"Entity": ENTITY}},
                                  "Property": measure}},
            "queryRef": f"{ENTITY}.{measure}", "nativeQueryRef": measure}]}}},
        "objects": {
            "label": [{"properties": {"show": lit("false")}, "selector": {"id": "default"}}],
            "value": [{"properties": props, "selector": {"id": "default"}}]}},
        container(bg=bg, border=border, radius=radius))
    return h


def button(x, y, w, h, label, color=NAVY, size=10, fill=None, border=None,
           bold=True, align="center", link_to=None):
    need = text_width(label, pt_to_px(size), bold) + 24
    if need > w:
        _issues.append(f"{_state['page']}: button {label!r} w={w} needs {int(need)}")
    objs = {
        "icon": [{"properties": {"shapeType": s("blank")}, "selector": {"id": "default"}},
                 {"properties": {"show": lit("false")}}],
        "text": [{"properties": {
            "show": lit("true"), "text": s(label), "fontColor": solid(color),
            "fontSize": num(size), "bold": lit("true" if bold else "false"),
            "horizontalAlignment": s(align)}, "selector": {"id": "default"}}],
        "outline": [{"properties": {"show": lit("false")}}],
    }
    if fill:
        objs["fill"] = [{"properties": {"show": lit("true")}},
                        {"properties": {"fillColor": solid(fill)},
                         "selector": {"id": "default"}}]
    else:
        objs["fill"] = [{"properties": {"show": lit("false")}}]
    add("actionButton", x, y, w, h, {"objects": objs},
        container(border=border, radius=4), link_to=link_to)
    return h


# The widest string each measure actually returns, read back from the live model.
# cardVisual does not wrap, so every one of these has to fit on ONE line.
SAMPLES = {
    "Hub Data As At": "Data as at 30 September 2026",
    "Hub Next Refresh": "Next refresh: 30 September 2026",
    "Hub Updated Inspections": "Source extract stale",
    "Hub Updated Incidents": "Not yet published",
    "Hub Updated NoW": "Source extract stale",
    "Hub Updated Planning Map": "Source extract stale",
    "Hub Updated Permit Turnaround": "Source extract stale",
    "Hub Updated Mineral Titles": "Source extract stale",
    "Hub Updated Dictionary": "Source extract stale",
    "Hub Trust Inspections": "Not validated",
    "Hub Trust Incidents": "Not validated",
    "Hub Trust NoW": "Not validated",
    "Hub Trust Planning Map": "Not validated",
    "Hub Trust Permit Turnaround": "Not validated",
    "Hub Trust Mineral Titles": "Not validated",
    "Hub Trust Dictionary": "Not validated",
    "Hub Badge Certified": "Certified",
    "Hub Badge Promoted": "Promoted",
    "Hub Badge Provisional": "Provisional",
    "Hub Badge Not Validated": "Not validated",
    "Hub Changed Inspections":
        "511 completed FYTD, down from 747 at the same point last year. July "
        "contributed 17. FY2025/26 finished at 1,519, below the 1,600 Service Plan "
        "target.",
    "Hub Changed Inspections Ops":
        "511 completed so far this fiscal year against 747 at the same point last "
        "year. July contributed 17 - plan coverage accordingly.",
    "Hub Changed Incidents":
        "Report not yet built. Commentary lands with the Incidents build - no figures "
        "are shown until they can be validated.",
    "Hub Changed NoW":
        "Permitting logic is built and matches the corporate report, but the "
        "now_application source extract has not landed since April 2025. Figures "
        "publish once the extract is refreshed.",
    "Hub Changed NoW Permitting":
        "Permitting logic matches the corporate report. The now_application extract "
        "is behind, so counts are withheld rather than shown provisionally.",
    "Hub Changed Planning Map":
        "Risk criteria are not yet agreed, so the tile is visible and labelled rather "
        "than hidden - the openness matters more than the polish here.",
    "Hub Changed Admin Amendments":
        "Administrative amendments are tracked as a separate series and excluded from "
        "the headline permit count.",
    "Hub Changed Mineral Titles":
        "Mineral Titles extract is stale pending the refreshed feed; no counts are "
        "published until it lands.",
    "Hub Window FYTD": "1 April 2026 to 30 September 2026",
    "Hub Window Same Last FY": "1 April 2025 to 30 September 2025",
    "Hub Window Rolling 5": "1 April 2021 to 31 March 2026",
    "Hub Def Inspections FYTD":
        "Distinct count of inspection_id where inspection_date falls in the current "
        "BC fiscal year to today.",
    "Hub Def Source": "lh_gold.fact_inspection, built from CORE and NRIS.",
    "Hub Def Last Refresh": "Gold data last landed 30 September 2026.",
    "Hub Def Validated By": "Mines Digital Services - certified 30 September 2026.",
    "Hub Rule Fiscal Year":
        "FY runs 1 April to 31 March. FY2026/27 began 1 April 2026.",
    "Hub Rule Inspections":
        "Counted on inspection_date, distinct inspection_id, all types included.",
    "Hub Rule NoW":
        "Counted on issue date; administrative amendments held separately.",
    "Hub Rule Target": "Service Plan target is 1,600 inspections per fiscal year.",
    "Hub Access Note":
        "Access is granted per audience by the app owner - not per report.",
    "Hub Stale Warning":
        "Gold data last landed 30 September 2026 and the next scheduled refresh was "
        "1 October 2026. Figures below are 41 days old.",
}

# Widest string each measure family can return, for width checks.
S_BADGE = "Not validated"
S_ASAT = "Data as at 30 September 2026"
S_REFRESH = "Next refresh: 30 September 2026"
S_UPDATED = "Source extract stale"

BADGE_W = card_min_width(S_BADGE, 9, pill=True, bold=True) + 8
PILL_W = card_min_width(S_ASAT, 10, pill=True, bold=True) + 8
REFRESH_W = card_min_width(S_REFRESH, 9, pill=False) + 8


def badge(x, y, measure, state, w=None):
    col, fill, brd = BADGE[state]
    return measure_card(x, y, w or BADGE_W, measure, size=9, color=col, bold=True,
                        bg=fill, border=brd, radius=card_height(1) // 2,
                        sample=S_BADGE)


# --- shared page chrome ------------------------------------------------------
HEADER_H = 124


def chrome(active_page, show_rail=True):
    rect(0, 0, W, H, fill=BODY, radius=0)
    rect(0, 0, W, HEADER_H - 2, fill=WHITE, radius=0)
    rect(0, HEADER_H - 2, W, 1, fill=LINE, radius=0)
    add("image", 28, 22, 145, 42, {"objects": {"general": [{"properties": {
        "imageUrl": {"expr": {"ResourcePackageItem": {
            "PackageName": "RegisteredResources", "PackageType": 1,
            "ItemName": "Logo.png"}}}}}]}}, container(title=False))
    text(190, 18, 520, [("Mines Data Platform", 17, NAVY, True)])
    text(190, 50, 520, [("Org app  ·  Mining & Critical Minerals", 9, MUTED, False)])
    button(W - 148, 26, 118, 32, "Share", color=NAVY, size=10, border=LINE)
    if not show_rail:
        return
    for (label, target), (x, w) in zip(PERSONAS, RAIL_GEOM):
        active = target == active_page
        button(x, 86, w, 30, label, color=NAVY if active else MUTED, size=10,
               bold=active, link_to=target if target and not active else None)
        if active:
            rect(x + 8, 117, w - 16, 3, fill=NAVY, radius=0)


INTRO_Y = HEADER_H + 16          # 140


def intro_tile(title, body, pill="Hub Data As At", refresh="Hub Next Refresh"):
    body_w = min(1240, W - PILL_W - MARGIN - 90)
    th = tb_height(title, 800, 17, True)
    bh = tb_height(body, body_w, 10)
    tile_h = 14 + th + 2 + bh + 14
    rect(MARGIN, INTRO_Y, CONTENT_W, tile_h, fill=WHITE, border=LINE)
    text(MARGIN + 26, INTRO_Y + 14, 800, [(title, 17, NAVY, True)])
    text(MARGIN + 26, INTRO_Y + 14 + th + 2, body_w, [(body, 10, INK, False)])
    px = W - MARGIN - 26 - PILL_W
    measure_card(px, INTRO_Y + 14, PILL_W, pill, size=10, color=NAVY, bold=True,
                 bg=PILL_BG, border=PILL_BG, radius=card_height(1) // 2,
                 sample=S_ASAT)
    measure_card(px + PILL_W - REFRESH_W, INTRO_Y + 14 + card_height(1) + 6,
                 REFRESH_W, refresh, size=9, color=MUTED, align="right",
                 sample=S_REFRESH)
    return INTRO_Y + tile_h


CARDS_TOP = 316


def report_cards(cards, top=None):
    n = len(cards)
    y0 = top if top is not None else CARDS_TOP
    lh = text(MARGIN, y0 - 42, 150, [("Your reports", 12, INK, True)])
    text(MARGIN + 150, y0 - 42, 340,
         [(f"{n} items in this audience", 9, MUTED, False)])
    gap = 26
    cw = (CONTENT_W - gap * (n - 1)) // n
    pad = 24
    title_size = 13 if n <= 3 else 12
    title_w = cw - pad - 26 - BADGE_W - 16
    q_w = cw - pad * 2
    q_lines = max(wrap_lines(c[5], q_w - TB_HPAD, 10) for c in cards)
    t_lines = max(wrap_lines(c[0], title_w - TB_HPAD, title_size, True) for c in cards)
    th = TB_LINE * t_lines + TB_VPAD
    qh = TB_LINE * q_lines + TB_VPAD
    ch = (pad - 6) + max(th, card_height(1)) + 6 + TB_LINE + TB_VPAD + 4 + qh \
         + 14 + 1 + 12 + card_height(1) + pad - 6
    for i, (title, chip, trust_m, state, updated_m, question) in enumerate(cards):
        x = MARGIN + i * (cw + gap)
        rect(x, y0, cw, ch, fill=WHITE, border=LINE)
        cy = y0 + pad - 6
        rect(x + pad, cy + 8, 16, 16, fill=chip, radius=3)
        text(x + pad + 26, cy, title_w, [(title, title_size, INK, True)])
        badge(x + cw - pad - BADGE_W, cy, trust_m, state)
        cy += max(th, card_height(1)) + 6
        cy += text(x + pad, cy, 240, [("ANSWERS", 8, FAINT, True)]) + 4
        text(x + pad, cy, q_w, [(question, 10, INK, False)], lines=q_lines)
        cy += qh + 14
        rect(x + pad, cy, cw - pad * 2, 1, fill=LINE, radius=0)
        cy += 12
        measure_card(x + pad, cy, cw - pad * 2 - 150, updated_m, size=9,
                     color=MUTED, align="left", sample=S_UPDATED)
        button(x + cw - pad - 132, cy + 6, 132, 32, "Open  →", color=NAVY, size=10)
    return y0 + ch


PANEL_GAP = 26
COMM_W = 1440
CONT_W = CONTENT_W - COMM_W - PANEL_GAP
CONT_X = MARGIN + COMM_W + PANEL_GAP


def commentary_panel(heading, subtitle, rows, y, h):
    x, w = MARGIN, COMM_W
    rect(x, y, w, h, fill=WHITE, border=LINE)
    cy = y + 14
    cy += text(x + 24, cy, 620, [(heading, 12, INK, True)])
    cy += text(x + 24, cy, 760, [(subtitle, 9, MUTED, False)]) + 4
    # cardVisual does not wrap, so the label sits ABOVE and the card gets the
    # panel's full width - the widest commentary sentence needs ~1260px.
    rowh = TB_LINE + TB_VPAD + card_height(1)
    for label, colour, m in rows:
        rect(x + 24, cy, 4, rowh, fill=colour, radius=0)
        text(x + 24 + 14, cy, w - 24 - 14 - 24, [(label, 10, INK, True)],
             lines=1)
        measure_card(x + 24 + 14, cy + TB_LINE + TB_VPAD, w - 24 - 14 - 24, m,
                     size=10, color=INK, align="left")
        cy += rowh + 12
    return y + h


def contacts_panel(contacts, links, y, h):
    x, w = CONT_X, CONT_W
    rect(x, y, w, h, fill=WHITE, border=LINE)
    cy = y + 14
    cy += text(x + 24, cy, 340, [("Contacts & help", 12, INK, True)]) + 6
    for initials, name, sub in contacts:
        oval(x + 24, cy + 2, 34, 34, NAVY)
        text(x + 24, vcy(cy + 2, 34), 34, [(initials, 9, WHITE, True)],
             align="center")
        text(x + 70, cy, w - 94, [(name, 10, INK, True)])
        text(x + 70, cy + 26, w - 94, [(sub, 9, NAVY, False)], lines=1)
        cy += 62
    rect(x + 24, cy + 2, w - 48, 1, fill=LINE, radius=0)
    cy += 14
    for label, sub, target in links:
        rect(x + 24, cy + 9, 14, 14, fill=NAVY, radius=2)
        button(x + 46, cy, w - 94, 30, label, color=NAVY, size=10, align="left",
               link_to=target)
        text(x + 48, cy + 28, w - 96, [(sub, 9, MUTED, False)], lines=1)
        cy += 66
    return y + h


def footnote(txt, y=None):
    fy = y if y is not None else H - 44
    text(MARGIN, fy, CONTENT_W, [(txt, 9, FAINT, False)], lines=1)


PANELS_Y = 580
PANELS_H = H - 44 - 12 - PANELS_Y      # leaves the footnote clear


def start_page(page_id, display_name):
    _state.update(page=display_name, n=0, visuals=[])
    _state["pid"] = page_id
    _state["display"] = display_name


def finish_page():
    pid, name = _state["pid"], _state["display"]
    d = os.path.join(PAGES_DIR, pid)
    os.makedirs(os.path.join(d, "visuals"), exist_ok=True)
    page = {"$schema": PG, "name": pid, "displayName": name,
            "displayOption": "FitToPage", "height": H, "width": W,
            "objects": {"background": [{"properties": {
                "color": solid(BODY), "transparency": num(0)}}]}}
    with open(os.path.join(d, "page.json"), "w", encoding="utf-8") as f:
        json.dump(page, f, indent=2)
    for v in _state["visuals"]:
        vd = os.path.join(d, "visuals", v["name"])
        os.makedirs(vd, exist_ok=True)
        with open(os.path.join(vd, "visual.json"), "w", encoding="utf-8") as f:
            json.dump(v, f, indent=2)
    return len(_state["visuals"])


HELP_LINKS_STD = [("How to read these reports",
                   "Definitions, sources and the fiscal calendar", P_DEFS),
                  ("Request a change",
                   "Submit a data or report change request", P_CHANGE)]
HELP_LINKS_OPS = [("Definitions & data sources",
                   "Inspection types, CORE and NRIS lineage", P_DEFS),
                  ("Report a data issue",
                   "Flag a count that disagrees with source", P_CHANGE)]
CONTACTS_STD = [("RG", "Rajneesh Gulati", "Rajneesh.1.Gulati@gov.bc.ca"),
                ("NN", "Nhung Nguyen", "Nhung.Nguyen@gov.bc.ca")]

counts = {}


def persona_page(pid, display, title, body, cards, comm_head, comm_sub, comm_rows,
                 contacts, links, note):
    start_page(pid, display)
    chrome(pid)
    intro_tile(title, body)
    report_cards(cards)
    commentary_panel(comm_head, comm_sub, comm_rows, PANELS_Y, PANELS_H)
    contacts_panel(contacts, links, PANELS_Y, PANELS_H)
    footnote(note)
    counts[display] = finish_page()


def kv_panel(x, y, w, h, heading, sub, rows, label_w=160, size=10, color=INK):
    """Heading + optional sub, then label-left / measure-right rows."""
    rect(x, y, w, h, fill=WHITE, border=LINE)
    cy = y + 14
    cy += text(x + 24, cy, w - 48, [(heading, 12, INK, True)])
    if sub:
        cy += text(x + 24, cy, w - 48, [(sub, 9, MUTED, False)], lines=1)
    cy += 6
    rowh = TB_LINE + TB_VPAD + card_height(1)
    avail = (y + h - 14) - cy
    pitch = max(rowh + 6, avail // len(rows))
    for label, m in rows:
        text(x + 24, cy, w - 48, [(label, 8, FAINT, True)], lines=1)
        measure_card(x + 24, cy + TB_LINE + TB_VPAD, w - 48, m, size=size,
                     color=color, align="left")
        cy += pitch
    return y + h


# =============================================================================
# PAGES 1-4 - the persona pages
# =============================================================================
persona_page(
    P_EXEC, "Start here — Executive", "Start here — Executive view",
    "You are viewing the Executive audience of the Mines Data Platform app. It contains "
    "the three monthly corporate reports at summary level. Operational detail sits under "
    "the Compliance & Enforcement and Permitting & Titles tabs.",
    [("Inspections", BLUE, "Hub Trust Inspections", "certified", "Hub Updated Inspections",
      "How many inspections have we completed this fiscal year, and how does that track "
      "against the Service Plan target?"),
     ("Incidents", RED, "Hub Trust Incidents", "provisional", "Hub Updated Incidents",
      "How many incidents have been reported this fiscal year, how many were dangerous "
      "occurrences, and how are injuries and fatalities trending?"),
     ("Notice of Work", GREEN, "Hub Trust NoW", "provisional", "Hub Updated NoW",
      "How many Notice of Work permits have been issued, split by new, amended and "
      "administrative amendments?")],
    "What changed this month", "Curated commentary — one short paragraph per report",
    [("Inspections", BLUE, "Hub Changed Inspections"),
     ("Incidents", RED, "Hub Changed Incidents"),
     ("Notice of Work", GREEN, "Hub Changed NoW")],
    CONTACTS_STD, HELP_LINKS_STD,
    "Each audience tab above shows only the items made visible to that audience under "
    "Manage audiences. Executive users never see the operational detail pages.")

persona_page(
    P_COMP, "Start here — Compliance & Enforcement", "Start here — Compliance & Enforcement",
    "You are viewing the Compliance & Enforcement audience, which also serves the GIS "
    "team. It adds inspection-planning and mine-site lookup content to the corporate "
    "inspection and incident reports. Notice of Work sits under Permitting & Titles.",
    [("Inspections", BLUE, "Hub Trust Inspections", "certified", "Hub Updated Inspections",
      "How many inspections have we completed, by type, region and inspector — and which "
      "sites are still unvisited this year?"),
     ("Incidents", RED, "Hub Trust Incidents", "provisional", "Hub Updated Incidents",
      "What has been reported, how many were dangerous occurrences, and where are injuries "
      "and fatalities concentrated?"),
     ("Inspection planning map", PURPLE, "Hub Trust Planning Map", "provisional",
      "Hub Updated Planning Map",
      "Which sites should we visit next, given risk criteria, region and time since last "
      "inspection?")],
    "What changed this month", "Curated commentary — written for field and planning use",
    [("Inspections", BLUE, "Hub Changed Inspections Ops"),
     ("Incidents", RED, "Hub Changed Incidents"),
     ("Inspection planning map", PURPLE, "Hub Changed Planning Map")],
    CONTACTS_STD, HELP_LINKS_OPS,
    "The GIS team is folded into this audience rather than given its own tab — their work "
    "here is inspection planning, and they consume curated data through APIs.")

persona_page(
    P_PERM, "Start here — Permitting & Titles", "Start here — Permitting & Titles",
    "You are viewing the Permitting & Titles audience: Notice of Work permitting, "
    "turnaround performance, and Mineral Titles. Inspection and incident reporting sits "
    "under the Compliance & Enforcement tab.",
    [("Notice of Work", GREEN, "Hub Trust NoW", "provisional", "Hub Updated NoW",
      "How many NoW permits have been issued, split by new, amended and amalgamated, and "
      "administrative amendments?"),
     ("Permit turnaround", BLUE, "Hub Trust Permit Turnaround", "provisional",
      "Hub Updated Permit Turnaround",
      "How long are permits taking from application to decision, and where is the backlog "
      "concentrated?"),
     ("Mineral Titles extract", PURPLE, "Hub Trust Mineral Titles", "provisional",
      "Hub Updated Mineral Titles",
      "What titles, parcels and authorisations are currently active, and how do they "
      "relate to permitted sites?")],
    "What changed this month", "Curated commentary — written for permitting staff",
    [("Notice of Work", GREEN, "Hub Changed NoW Permitting"),
     ("Administrative amendments", BLUE, "Hub Changed Admin Amendments"),
     ("Mineral Titles extract", PURPLE, "Hub Changed Mineral Titles")],
    CONTACTS_STD, HELP_LINKS_OPS,
    "Notice of Work counts exclude administrative amendments in the headline measure, but "
    "include them as a separate series — a definition worth stating on the landing page.")

persona_page(
    P_AUDIT, "Start here — Audit & Analysis", "Start here — Audit & Analysis",
    "You are viewing the Audit & Analysis audience: all three corporate reports, plus "
    "saved time-window presets, exports with context, and the definition and lineage "
    "panel. Every figure here can be traced to source without writing a query.",
    [("Inspections", BLUE, "Hub Trust Inspections", "certified", "Hub Updated Inspections",
      "Inspection counts by type, region and period, with export."),
     ("Incidents", RED, "Hub Trust Incidents", "provisional", "Hub Updated Incidents",
      "Incidents, dangerous occurrences, injuries and fatalities by period."),
     ("Notice of Work", GREEN, "Hub Trust NoW", "provisional", "Hub Updated NoW",
      "Permits issued by type and period, amendments separated."),
     ("Dictionary & lineage", PURPLE, "Hub Trust Dictionary", "provisional",
      "Hub Updated Dictionary",
      "Where each measure comes from, how it is calculated, and when it was validated.")],
    "Saved audit windows", "Shared filter presets — the recurring windows this team asks for",
    [("Current fiscal year to date", BLUE, "Hub Window FYTD"),
     ("Same period last fiscal year", RED, "Hub Window Same Last FY"),
     ("Rolling 5 fiscal years", GREEN, "Hub Window Rolling 5")],
    [("R", "Rebecca", "MDS — definitions & semantics owner"),
     ("SA", "Sarah Alloisio", "Senior Auditor, Mine Audits Unit")],
    [("How data is certified", "Validation and approval before publication", P_DEFS),
     ("Report a data issue", "Flag a count that disagrees with source", P_CHANGE)],
    "Survey evidence: \"trusted / certified data\" ranked #1 capability, and respondents "
    "wanted source, definition, last refresh and drill-through together.")

# =============================================================================
# PAGE 5 - How to read these reports
# =============================================================================
start_page(P_DEFS, "How to read these reports")
chrome("")
y = intro_tile("How to read these reports",
               "One page for every definition, so meanings are not scattered across "
               "reports. Each figure states what it counts, where it comes from, when it "
               "last refreshed and who validated it. Report a disagreement through "
               "Request a change.")

# trust badge legend
LEG_Y = y + 16
BADGE_DOC = [
    ("Hub Badge Certified", "certified",
     "Validated and approved by MDS. Used on the corporate reports and every measure "
     "derived from them."),
    ("Hub Badge Promoted", "promoted",
     "The owner recommends it, but it has not been through certification. For reports "
     "awaiting MDS sign-off."),
    ("Hub Badge Provisional", "provisional",
     "Definition not yet agreed, or the source is behind. Visible and labelled — never "
     "hidden."),
    ("Hub Badge Not Validated", "notvalid",
     "Ad-hoc or user-built content. Distinct grey styling so it is never mistaken for a "
     "governed figure."),
]
col_w = CONTENT_W // 4
desc_lines = max(wrap_lines(d, col_w - 34 - TB_HPAD, 9) for _, _, d in BADGE_DOC)
LEG_H = 14 + 33 + 33 + 8 + card_height(1) + 6 + (TB_LINE * desc_lines + TB_VPAD) + 14
rect(MARGIN, LEG_Y, CONTENT_W, LEG_H, fill=WHITE, border=LINE)
ly = LEG_Y + 14
ly += text(MARGIN + 24, ly, 600, [("Trust badges — four states", 12, INK, True)])
ly += text(MARGIN + 24, ly, 900,
           [("Shown on every report card and, once the validation layer lands, on every "
             "KPI.", 9, MUTED, False)], lines=1) + 8
for i, (m, state, desc) in enumerate(BADGE_DOC):
    bx = MARGIN + 24 + i * col_w
    badge(bx, ly, m, state)
    text(bx, ly + card_height(1) + 6, col_w - 34, [(desc, 9, INK, False)],
         lines=desc_lines)

# anatomy of a definition + counting rules
BOT_Y = LEG_Y + LEG_H + 16
BOT_H = (H - 44 - 12) - BOT_Y
DEFS_L_W = 1100
DEFS_R_X = MARGIN + DEFS_L_W + PANEL_GAP
DEFS_R_W = CONTENT_W - DEFS_L_W - PANEL_GAP
kv_panel(MARGIN, BOT_Y, DEFS_L_W, BOT_H, "Anatomy of a definition",
         "What every KPI states — the bundle, not a single signal.",
         [("DEFINITION", "Hub Def Inspections FYTD"),
          ("SOURCE", "Hub Def Source"),
          ("LAST REFRESH", "Hub Def Last Refresh"),
          ("VALIDATED BY", "Hub Def Validated By")], label_w=140)
kv_panel(DEFS_R_X, BOT_Y, DEFS_R_W, BOT_H, "Counting rules and the fiscal calendar",
         "The date logic behind every headline figure.",
         [("FISCAL YEAR", "Hub Rule Fiscal Year"),
          ("INSPECTIONS", "Hub Rule Inspections"),
          ("NOTICE OF WORK", "Hub Rule NoW"),
          ("SERVICE PLAN", "Hub Rule Target")], label_w=132, size=9)
footnote("Definitions are maintained here as the single source of truth. Power BI cannot "
         "auto-sync this page into per-visual tooltips, so any change made here is applied "
         "to the report tooltips as part of the same change request.")
counts["How to read"] = finish_page()

# =============================================================================
# PAGE 6 - Request a change
# =============================================================================
start_page(P_CHANGE, "Request a change")
chrome("")
y = intro_tile("Request a change",
               "Something look wrong, missing, or defined differently from how your team "
               "uses it? Raise it here. Requests are logged against the report and the "
               "named owner, so nothing depends on remembering who to email.")

STEPS = [("1", "You describe the issue",
          "Report, figure, and what you expected instead. The current filter context and "
          "\"data as at\" date are attached automatically."),
         ("2", "A ticket is raised",
          "The button writes a work item through Power Automate — no separate form to find "
          "and no email that gets lost."),
         ("3", "The section owner reviews it",
          "The named owner on the report card is accountable for the answer, rather than a "
          "shared inbox."),
         ("4", "The outcome is published",
          "If a definition changes, it changes on How to read these reports and in the "
          "report tooltip at the same time.")]
TOP_Y = y + 16
step_w = COMM_W - 48 - 46
step_lines = max(wrap_lines(d, step_w - TB_HPAD, 9) for _, _, d in STEPS)
step_h = 33 + (TB_LINE * step_lines + TB_VPAD) + 12
TOP_H = 14 + 33 + 8 + step_h * len(STEPS) + 6
rect(MARGIN, TOP_Y, COMM_W, TOP_H, fill=WHITE, border=LINE)
sy = TOP_Y + 14
sy += text(MARGIN + 24, sy, 600, [("What happens when you submit", 12, INK, True)]) + 8
for n, title, desc in STEPS:
    oval(MARGIN + 24, sy + 4, 26, 26, NAVY)
    text(MARGIN + 24, vcy(sy + 4, 26), 26, [(n, 9, WHITE, True)],
         align="center")
    text(MARGIN + 70, sy, 600, [(title, 10, INK, True)], lines=1)
    text(MARGIN + 70, sy + 30, step_w, [(desc, 9, MUTED, False)], lines=step_lines)
    sy += step_h

rect(CONT_X, TOP_Y, CONT_W, TOP_H, fill=WHITE, border=LINE)
ry = TOP_Y + 14
ry += text(CONT_X + 24, ry, CONT_W - 48, [("Raise it now", 12, INK, True)])
ry += text(CONT_X + 24, ry, CONT_W - 48,
           [("Takes about a minute. You will get the ticket reference back on screen.",
             9, MUTED, False)]) + 10
button(CONT_X + 24, ry, CONT_W - 48, 44, "Submit a change request", color=WHITE,
       size=11, fill=NAVY, border=NAVY)
ry += 44 + 6
ry += text(CONT_X + 24, ry, CONT_W - 48,
           [("Opens the Power Automate flow in this report.", 9, MUTED, False)],
           lines=1) + 8
rect(CONT_X + 24, ry, CONT_W - 48, 1, fill=LINE, radius=0)
ry += 12
ry += text(CONT_X + 24, ry, CONT_W - 48,
           [("Prefer to ask a person first?", 10, INK, True)]) + 4
for initials, name, sub in CONTACTS_STD:
    oval(CONT_X + 24, ry + 2, 34, 34, NAVY)
    text(CONT_X + 24, vcy(ry + 2, 34), 34, [(initials, 9, WHITE, True)],
         align="center")
    text(CONT_X + 70, ry, CONT_W - 94, [(name, 10, INK, True)], lines=1)
    text(CONT_X + 70, ry + 26, CONT_W - 94, [(sub, 9, NAVY, False)], lines=1)
    ry += 62

STATES = [("Ready", "certified",
           "Default state. The button is live and the flow is reachable."),
          ("Sent", "promoted",
           "Confirmation with a ticket reference, shown in place."),
          ("Unavailable", "notvalid",
           "Tenant settings block the Power Automate visual — falls back to the named "
           "owner's email.")]
ST_Y = TOP_Y + TOP_H + 16
st_col = CONTENT_W // 3
st_lines = max(wrap_lines(d, st_col - 34 - TB_HPAD, 9) for _, _, d in STATES)
ST_H = 14 + 33 + 33 + 8 + card_height(1) + 6 + (TB_LINE * st_lines + TB_VPAD) + 14
rect(MARGIN, ST_Y, CONTENT_W, ST_H, fill=WHITE, border=LINE)
sy = ST_Y + 14
sy += text(MARGIN + 24, sy, 600, [("Request states", 12, INK, True)])
sy += text(MARGIN + 24, sy, 1000,
           [("The three states the button shows, so a submitted request never looks like "
             "nothing happened.", 9, MUTED, False)], lines=1) + 8
for i, (label, state, desc) in enumerate(STATES):
    bx = MARGIN + 24 + i * st_col
    col, fill_c, brd = BADGE[state]
    rect(bx, sy, BADGE_W, card_height(1), fill=fill_c, border=brd,
         radius=card_height(1) // 2)
    text(bx, vcy(sy, card_height(1)), BADGE_W, [(label, 9, col, True)],
         align="center", lines=1)
    text(bx, sy + card_height(1) + 6, st_col - 34, [(desc, 9, INK, False)],
         lines=st_lines)
footnote("The Power Automate visual is subject to a tenant setting we have not yet "
         "confirmed — the fallback path is designed for, not bolted on later.",
         y=ST_Y + ST_H + 10)
counts["Request a change"] = finish_page()

# =============================================================================
# PAGE 7 - Access and data states
# =============================================================================
start_page(P_STATES, "Access & data states")
chrome("")
y = intro_tile("Access & data states",
               "The two screens users hit that are not the happy path. Both are designed "
               "rather than left to the platform default, because both are moments where "
               "trust is won or lost.")

y += 16
y += text(MARGIN, y, 800,
          [("STATE 1 — user has no audience membership", 9, ALERT, True)], lines=1)
S1_H = 14 + 40 + 10 + 33 + 6 + 54 + 14 + 36 + 12 + card_height(1) + 14
rect(MARGIN, y, CONTENT_W, S1_H, fill=WHITE, border=LINE)
ay = y + 14
rect(W // 2 - 34, ay, 68, 38, fill=PILL_BG, radius=6)
rect(W // 2 - 12, ay + 11, 24, 16, fill=NAVY, radius=3)
ay += 40 + 10
ay += text(MARGIN, ay, CONTENT_W,
           [("You don't have access to this app yet", 16, INK, True)],
           align="center", lines=1) + 6
ay += text(MARGIN + 220, ay, CONTENT_W - 440,
           [("Mines Data Platform is organised into four audiences — Executive, "
             "Compliance & Enforcement, Permitting & Titles, and Audit & Analysis. Your "
             "account is not yet a member of any of them, so there is nothing to display.",
             10, MUTED, False)], align="center", lines=2) + 14
button(W // 2 - 190, ay, 180, 36, "Request access", color=WHITE, size=10, fill=NAVY,
       border=NAVY)
button(W // 2 + 10, ay, 180, 36, "Who should I ask?", color=NAVY, size=10, border=LINE)
ay += 36 + 12
measure_card(MARGIN, ay, CONTENT_W, "Hub Access Note", size=9, color=FAINT,
             align="center")
y += S1_H + 16

y += text(MARGIN, y, 800,
          [("STATE 2 — report has not refreshed on schedule", 9, ALERT, True)], lines=1)
S2_H = (H - 44 - 12) - y
rect(MARGIN, y, CONTENT_W, S2_H, fill=WHITE, border=LINE)
rect(MARGIN, y, 5, S2_H, fill=ALERT, radius=0)
sy = y + 16
sy += text(MARGIN + 28, sy, 700, [("Start here — Executive view", 14, NAVY, True)])
STALE_PILL_W = card_min_width(S_ASAT, 9, pill=True, bold=True) + 8
rect(W - MARGIN - 24 - STALE_PILL_W, y + 16, STALE_PILL_W, card_height(1),
     fill="#FDF3F0", border=ALERT, radius=card_height(1) // 2)
measure_card(W - MARGIN - 24 - STALE_PILL_W, y + 16, STALE_PILL_W, "Hub Data As At",
             size=9, color=ALERT, align="center", sample=S_ASAT)
measure_card(MARGIN + 28, sy, CONTENT_W - 80, "Hub Stale Warning",
             size=10, color=INK, align="left")
sy += card_height(1) + 18
mini_w = (CONTENT_W - 56 - 40) // 3
mini_h = (y + S2_H - 16) - sy
for i, (label, chip) in enumerate([("Inspections", BLUE), ("Incidents", RED),
                                   ("Notice of Work", GREEN)]):
    mx = MARGIN + 28 + i * (mini_w + 20)
    rect(mx, sy, mini_w, mini_h, fill="#FAFAFA", border=LINE)
    rect(mx + 20, sy + 22, 14, 14, fill=chip, radius=3)
    text(mx + 42, sy + 14, mini_w - 70, [(label, 11, MUTED, True)], lines=1)
    measure_card(mx + 20, sy + 54, mini_w - 40, "Hub Data As At", size=9, color=ALERT,
                 align="center", bg="#FDF3F0", border=ALERT,
                 radius=card_height(1) // 2, sample=S_ASAT)
    text(mx + 20, sy + 54 + card_height(1) + 6, mini_w - 40,
         [("Not current — verify against source before quoting.", 9, MUTED, False)],
         lines=1)
footnote("Survey evidence: outdated data / unclear refresh scored 2.6 of 4 for severity, "
         "and 4 of 6 operational respondents verify figures by hand. Never show a stale "
         "number without saying it is stale — and never hide the tile.")
counts["Access & data states"] = finish_page()

# --- pages.json --------------------------------------------------------------
order = [P_EXEC, P_COMP, P_PERM, P_AUDIT, P_DEFS, P_CHANGE, P_STATES]
with open(os.path.join(PAGES_DIR, "pages.json"), "w", encoding="utf-8") as f:
    json.dump({"$schema": PM, "pageOrder": order, "activePageName": P_EXEC}, f, indent=2)

print(f"canvas {W}x{H}   navigation links: {'ON' if NAV else 'OFF'}")
for k, v in counts.items():
    print(f"  {k:<30} {v:>3} visuals")
print("total visuals:", sum(counts.values()))
if _issues:
    print(f"\n!! {len(_issues)} layout issues")
    for i in _issues:
        print("   ", i)
else:
    print("\nlayout clean: nothing clipped, nothing off-canvas")
