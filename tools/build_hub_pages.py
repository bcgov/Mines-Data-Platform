#!/usr/bin/env python3
"""Generate the whole Option C hub: 4 persona pages + definitions + request-a-change
+ access/data states, as PBIR pages.

Every value slot is a cardVisual bound to a measure on the Gold Inspections Semantic
Model - nothing is typed in (Romil's rule: "313 in FY26/27 must update itself").
Persona-rail and help buttons carry real PageNavigation links.
"""
import json, os, sys

ROOT = sys.argv[1]
NAV = "--no-nav" not in sys.argv          # allow generating a link-free fallback
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

# Four trust states: (label colour, fill, border)
BADGE = {
    "certified":   ("#0F6CBD", "#EFF6FC", "#B4D6F0"),
    "promoted":    ("#107C41", "#F1FAF1", "#9FD5A0"),
    "provisional": ("#8A6100", "#FFF9E6", GOLD),
    "notvalid":    (MUTED,     "#F3F2F1", "#D2D0CE"),
}

W, H = 1280, 720

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
RAIL_GEOM = [(24, 44), (76, 88), (172, 176), (356, 132), (496, 120)]

_state = {"page": None, "n": 0, "visuals": []}


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
def text(x, y, w, h, runs, align="left"):
    tr = []
    for value, size, color, bold in runs:
        style = {"fontSize": f"{size}px", "color": color}
        if bold:
            style["fontWeight"] = "bold"
        tr.append({"value": value, "textStyle": style})
    return add("textbox", x, y, w, h,
               {"objects": {"general": [{"properties": {
                   "paragraphs": [{"textRuns": tr, "horizontalTextAlignment": align}]}}]}},
               container(title=False))


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


def measure_card(x, y, w, h, measure, size=10, color=INK, align="center",
                 bold=False, bg=None, border=None, radius=4):
    props = {"fontSize": num(size), "horizontalAlignment": s(align), "color": solid(color)}
    if bold:
        props["bold"] = lit("true")
    return add("cardVisual", x, y, w, h, {
        "query": {"queryState": {"Data": {"projections": [{
            "field": {"Measure": {"Expression": {"SourceRef": {"Entity": ENTITY}},
                                  "Property": measure}},
            "queryRef": f"{ENTITY}.{measure}", "nativeQueryRef": measure}]}}},
        "objects": {
            "label": [{"properties": {"show": lit("false")}, "selector": {"id": "default"}}],
            "value": [{"properties": props, "selector": {"id": "default"}}]}},
        container(bg=bg, border=border, radius=radius))


def button(x, y, w, h, label, color=NAVY, size=10, fill=None, border=None,
           bold=True, align="center", link_to=None):
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
    return add("actionButton", x, y, w, h, {"objects": objs},
               container(border=border, radius=4), link_to=link_to)


def badge(x, y, w, h, measure, state):
    col, fill, brd = BADGE[state]
    return measure_card(x, y, w, h, measure, size=9, color=col, bold=True,
                        bg=fill, border=brd, radius=11)


# --- shared page chrome ------------------------------------------------------
def chrome(active_page, show_rail=True):
    """Backdrop, header band, logo, title, Share, persona rail."""
    rect(0, 0, W, H, fill=BODY, radius=0)
    rect(0, 0, W, 97, fill=WHITE, radius=0)
    rect(0, 96, W, 1, fill=LINE, radius=0)
    add("image", 24, 16, 116, 34, {"objects": {"general": [{"properties": {
        "imageUrl": {"expr": {"ResourcePackageItem": {
            "PackageName": "RegisteredResources", "PackageType": 1,
            "ItemName": "Logo.png"}}}}}]}}, container(title=False))
    text(152, 14, 420, 22, [("Mines Data Platform", 16, NAVY, True)])
    text(152, 33, 420, 19, [("Org app  ·  Mining & Critical Minerals", 9, MUTED, False)])
    button(1164, 16, 92, 26, "Share", color=NAVY, size=10, border=LINE)
    if not show_rail:
        return
    for (label, target), (x, w) in zip(PERSONAS, RAIL_GEOM):
        active = target == active_page
        button(x, 60, w, 30, label, color=NAVY if active else MUTED, size=10,
               bold=active, link_to=target if target and not active else None)
        if active:
            rect(x + 8, 90, w - 16, 3, fill=NAVY, radius=0)


def intro_tile(title, body, pill="Hub Data As At", refresh="Hub Next Refresh"):
    rect(24, 116, 1232, 90, fill=WHITE, border=LINE)
    text(48, 128, 640, 26, [(title, 17, NAVY, True)])
    text(48, 156, 800, 42, [(body, 10, INK, False)])
    measure_card(996, 130, 236, 26, pill, size=10, color=NAVY, bold=True,
                 bg=PILL_BG, border=PILL_BG, radius=13)
    measure_card(996, 162, 236, 20, refresh, size=9, color=MUTED, align="right")


def report_cards(cards):
    """cards = [(title, chip, trust_measure, state, updated_measure, question)]"""
    n = len(cards)
    text(24, 214, 104, 20, [("Your reports", 12, INK, True)])
    text(130, 216, 300, 18, [(f"{n} items in this audience", 9, MUTED, False)])
    gap = 24
    cw = (1232 - gap * (n - 1)) // n
    cy, ch = 240, 166
    for i, (title, chip, trust_m, state, updated_m, question) in enumerate(cards):
        x = 24 + i * (cw + gap)
        rect(x, cy, cw, ch, fill=WHITE, border=LINE)
        rect(x + 20, cy + 22, 14, 14, fill=chip, radius=3)
        bw = 96 if n <= 3 else 84
        text(x + 42, cy + 16, cw - bw - 60, 26,
             [(title, 13 if n <= 3 else 12, INK, True)])
        badge(x + cw - bw - 20, cy + 18, bw, 22, trust_m, state)
        text(x + 20, cy + 50, 200, 17, [("ANSWERS", 8, FAINT, True)])
        text(x + 20, cy + 68, cw - 40, 62, [(question, 10, INK, False)])
        rect(x + 20, cy + 134, cw - 40, 1, fill=LINE, radius=0)
        measure_card(x + 20, cy + 140, cw - 130, 20, updated_m, size=9,
                     color=MUTED, align="left")
        button(x + cw - 104, cy + 138, 84, 22, "Open  →", color=NAVY, size=10)


def commentary_panel(heading, subtitle, rows, x=24, y=414, w=796, h=268):
    """rows = [(label, colour, measure)]"""
    rect(x, y, w, h, fill=WHITE, border=LINE)
    text(x + 24, y + 16, 460, 22, [(heading, 12, INK, True)])
    text(x + 24, y + 37, 520, 19, [(subtitle, 9, MUTED, False)])
    ry = y + 62
    for label, colour, m in rows:
        rect(x + 24, ry, 3, 62, fill=colour, radius=0)
        text(x + 36, ry, 320, 18, [(label, 10, INK, True)])
        measure_card(x + 36, ry + 18, w - 84, 44, m, size=10, color=INK, align="left")
        ry += 68


def contacts_panel(contacts, links, x=836, y=414, w=420, h=268):
    rect(x, y, w, h, fill=WHITE, border=LINE)
    text(x + 24, y + 16, 300, 22, [("Contacts & help", 12, INK, True)])
    cy = y + 48
    for initials, name, sub in contacts:
        oval(x + 24, cy, 30, 30, NAVY)
        text(x + 24, cy + 8, 30, 16, [(initials, 9, WHITE, True)], align="center")
        text(x + 64, cy - 1, 320, 18, [(name, 10, INK, True)])
        text(x + 64, cy + 14, 330, 19, [(sub, 9, NAVY, False)])
        cy += 44
    rect(x + 24, cy + 6, w - 48, 1, fill=LINE, radius=0)
    ly = cy + 20
    for label, sub, target in links:
        rect(x + 24, ly + 5, 12, 12, fill=NAVY, radius=2)
        button(x + 42, ly - 2, 300, 22, label, color=NAVY, size=10, align="left",
               link_to=target)
        text(x + 44, ly + 17, 340, 19, [(sub, 9, MUTED, False)])
        ly += 44


def footnote(txt):
    text(24, 684, 1232, 32, [(txt, 9, FAINT, False)])


def start_page(page_id, display_name):
    _state.update(page=page_id, n=0, visuals=[])
    _state["display"] = display_name


def finish_page(tooltip=False):
    pid, name = _state["page"], _state["display"]
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

# =============================================================================
# PAGE 1 — Executive
# =============================================================================
start_page(P_EXEC, "Start here — Executive")
chrome(P_EXEC)
intro_tile("Start here — Executive view",
           "You are viewing the Executive audience of the Mines Data Platform app. It "
           "contains the three monthly corporate reports at summary level. Operational "
           "detail sits under the Compliance & Enforcement and Permitting & Titles tabs.")
report_cards([
    ("Inspections", BLUE, "Hub Trust Inspections", "certified", "Hub Updated Inspections",
     "How many inspections have we completed this fiscal year, and how does that track "
     "against the Service Plan target?"),
    ("Incidents", RED, "Hub Trust Incidents", "provisional", "Hub Updated Incidents",
     "How many incidents have been reported this fiscal year, how many were dangerous "
     "occurrences, and how are injuries and fatalities trending?"),
    ("Notice of Work", GREEN, "Hub Trust NoW", "provisional", "Hub Updated NoW",
     "How many Notice of Work permits have been issued, split by new, amended and "
     "administrative amendments?"),
])
commentary_panel("What changed this month",
                 "Curated commentary — 1 short paragraph per report",
                 [("Inspections", BLUE, "Hub Changed Inspections"),
                  ("Incidents", RED, "Hub Changed Incidents"),
                  ("Notice of Work", GREEN, "Hub Changed NoW")])
contacts_panel(CONTACTS_STD, HELP_LINKS_STD)
footnote("Each audience tab above shows only the items made visible to that audience "
         "under Manage audiences. Executive users never see the operational detail pages.")
counts["Executive"] = finish_page()

# =============================================================================
# PAGE 2 — Compliance & Enforcement
# =============================================================================
start_page(P_COMP, "Start here — Compliance & Enforcement")
chrome(P_COMP)
intro_tile("Start here — Compliance & Enforcement",
           "You are viewing the Compliance & Enforcement audience, which also serves the "
           "GIS team. It adds inspection-planning and mine-site lookup content to the "
           "corporate inspection and incident reports. Notice of Work sits under the "
           "Permitting & Titles tab.")
report_cards([
    ("Inspections", BLUE, "Hub Trust Inspections", "certified", "Hub Updated Inspections",
     "How many inspections have we completed, by type, region and inspector — and which "
     "sites are still unvisited this year?"),
    ("Incidents", RED, "Hub Trust Incidents", "provisional", "Hub Updated Incidents",
     "What has been reported, how many were dangerous occurrences, and where are injuries "
     "and fatalities concentrated?"),
    ("Inspection planning map", PURPLE, "Hub Trust Planning Map", "provisional",
     "Hub Updated Planning Map",
     "Which sites should we visit next, given risk criteria, region and time since last "
     "inspection?"),
])
commentary_panel("What changed this month",
                 "Curated commentary — written for field and planning use",
                 [("Inspections", BLUE, "Hub Changed Inspections Ops"),
                  ("Incidents", RED, "Hub Changed Incidents"),
                  ("Inspection planning map", PURPLE, "Hub Changed Planning Map")])
contacts_panel(CONTACTS_STD, HELP_LINKS_OPS)
footnote("The GIS team is folded into this audience rather than given its own tab — their "
         "work here is inspection planning, and they consume curated data through APIs "
         "rather than through app navigation.")
counts["Compliance & Enforcement"] = finish_page()

# =============================================================================
# PAGE 3 — Permitting & Titles
# =============================================================================
start_page(P_PERM, "Start here — Permitting & Titles")
chrome(P_PERM)
intro_tile("Start here — Permitting & Titles",
           "You are viewing the Permitting & Titles audience: Notice of Work permitting, "
           "turnaround performance, and Mineral Titles. Inspection and incident reporting "
           "sits under the Compliance & Enforcement tab.")
report_cards([
    ("Notice of Work", GREEN, "Hub Trust NoW", "provisional", "Hub Updated NoW",
     "How many NoW permits have been issued, split by new, amended and amalgamated, and "
     "administrative amendments?"),
    ("Permit turnaround", BLUE, "Hub Trust Permit Turnaround", "provisional",
     "Hub Updated Permit Turnaround",
     "How long are permits taking from application to decision, and where is the backlog "
     "concentrated?"),
    ("Mineral Titles extract", PURPLE, "Hub Trust Mineral Titles", "provisional",
     "Hub Updated Mineral Titles",
     "What titles, parcels and authorisations are currently active, and how do they relate "
     "to permitted sites?"),
])
commentary_panel("What changed this month",
                 "Curated commentary — written for permitting staff",
                 [("Notice of Work", GREEN, "Hub Changed NoW Permitting"),
                  ("Administrative amendments", BLUE, "Hub Changed Admin Amendments"),
                  ("Mineral Titles extract", PURPLE, "Hub Changed Mineral Titles")])
contacts_panel(CONTACTS_STD, HELP_LINKS_OPS)
footnote("Notice of Work counts exclude administrative amendments in the headline measure, "
         "but include them as a separate series — a definition worth stating on the landing "
         "page, not buried in the report.")
counts["Permitting & Titles"] = finish_page()

# =============================================================================
# PAGE 4 — Audit & Analysis
# =============================================================================
start_page(P_AUDIT, "Start here — Audit & Analysis")
chrome(P_AUDIT)
intro_tile("Start here — Audit & Analysis",
           "You are viewing the Audit & Analysis audience: all three corporate reports, "
           "plus saved time-window presets, exports with context, and the definition and "
           "lineage panel. Every figure here can be traced to source without writing a query.")
report_cards([
    ("Inspections", BLUE, "Hub Trust Inspections", "certified", "Hub Updated Inspections",
     "Inspection counts by type, region and period, with export."),
    ("Incidents", RED, "Hub Trust Incidents", "provisional", "Hub Updated Incidents",
     "Incidents, dangerous occurrences, injuries and fatalities by period."),
    ("Notice of Work", GREEN, "Hub Trust NoW", "provisional", "Hub Updated NoW",
     "Permits issued by type and period, amendments separated."),
    ("Dictionary & lineage", PURPLE, "Hub Trust Dictionary", "provisional",
     "Hub Updated Dictionary",
     "Where each measure comes from, how it is calculated, and when it was last validated."),
])
commentary_panel("Saved audit windows",
                 "Shared filter presets — the recurring windows this team asks for",
                 [("Current fiscal year to date", BLUE, "Hub Window FYTD"),
                  ("Same period last fiscal year", RED, "Hub Window Same Last FY"),
                  ("Rolling 5 fiscal years", GREEN, "Hub Window Rolling 5")])
contacts_panel([("R", "Rebecca", "MDS — definitions & semantics owner"),
                ("SA", "Sarah Alloisio", "Senior Auditor, Mine Audits Unit")],
               [("How data is certified",
                 "Validation and approval before publication", P_DEFS),
                ("Report a data issue",
                 "Flag a count that disagrees with source", P_CHANGE)])
footnote("Survey evidence: \"trusted / certified data\" ranked #1 capability and respondents "
         "wanted source, definition, last refresh and drill-through together rather than any "
         "single trust signal — hence the dictionary tile and the export-with-context link.")
counts["Audit & Analysis"] = finish_page()

# =============================================================================
# PAGE 5 — How to read these reports (definitions, sources, trust badges)
# =============================================================================
start_page(P_DEFS, "How to read these reports")
chrome("")
intro_tile("How to read these reports",
           "One page for every definition, so meanings are not scattered across reports. "
           "Each figure states what it counts, where it comes from, when it last refreshed "
           "and who validated it. Report a disagreement through Request a change.")

# --- trust badge legend
rect(24, 214, 1232, 132, fill=WHITE, border=LINE)
text(48, 226, 500, 22, [("Trust badges — four states", 12, INK, True)])
text(48, 247, 700, 19,
     [("Shown on every report card and, once the validation layer lands, on every KPI.", 9,
       MUTED, False)])
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
for i, (m, state, desc) in enumerate(BADGE_DOC):
    bx = 48 + i * 300
    badge(bx, 274, 96, 22, m, state)
    text(bx, 300, 280, 42, [(desc, 9, INK, False)])

# --- anatomy of a definition
rect(24, 358, 604, 324, fill=WHITE, border=LINE)
text(48, 370, 500, 22, [("Anatomy of a definition", 12, INK, True)])
text(48, 391, 560, 19,
     [("What every KPI states — the bundle, not a single signal.", 9, MUTED, False)])
ANATOMY = [("DEFINITION", "Hub Def Inspections FYTD"),
           ("SOURCE", "Hub Def Source"),
           ("LAST REFRESH", "Hub Def Last Refresh"),
           ("VALIDATED BY", "Hub Def Validated By")]
ay = 414
for label, m in ANATOMY:
    text(48, ay, 200, 17, [(label, 8, FAINT, True)])
    measure_card(48, ay + 16, 556, 38, m, size=10, color=INK, align="left")
    rect(48, ay + 55, 556, 1, fill=LINE, radius=0)
    ay += 61
text(48, ay + 2, 560, 19,
     [("Worked example: the Inspections FYTD headline on the Executive view.", 9,
       MUTED, False)])

# --- fiscal calendar + counting rules
rect(652, 358, 604, 324, fill=WHITE, border=LINE)
text(676, 370, 500, 22, [("Counting rules and the fiscal calendar", 12, INK, True)])
text(676, 391, 560, 19,
     [("The date logic behind every headline figure.", 9, MUTED, False)])
RULES = [("Fiscal year", "Hub Rule Fiscal Year"),
         ("Inspections", "Hub Rule Inspections"),
         ("Notice of Work", "Hub Rule NoW"),
         ("Service Plan target", "Hub Rule Target")]
ry = 414
for label, m in RULES:
    text(676, ry, 240, 19, [(label, 10, INK, True)])
    measure_card(676, ry + 18, 556, 40, m, size=9, color=INK, align="left")
    ry += 62
footnote("Definitions are maintained here as the single source of truth. Power BI cannot "
         "auto-sync this page into per-visual tooltips, so any change made here is also "
         "applied to the report tooltips as part of the same change request.")
counts["How to read"] = finish_page()

# =============================================================================
# PAGE 6 — Request a change
# =============================================================================
start_page(P_CHANGE, "Request a change")
chrome("")
intro_tile("Request a change",
           "Something look wrong, missing, or defined differently from how your team uses "
           "it? Raise it here. Requests are logged against the report and the named owner, "
           "so nothing depends on remembering who to email.")

rect(24, 214, 796, 300, fill=WHITE, border=LINE)
text(48, 230, 500, 22, [("What happens when you submit", 12, INK, True)])
STEPS = [("1", "You describe the issue",
          "Report, figure, and what you expected instead. The current filter context and "
          "\"data as at\" date are attached automatically."),
         ("2", "A ticket is raised",
          "The button writes a work item through Power Automate — no separate form to find "
          "and no email that gets lost."),
         ("3", "The section owner reviews it",
          "The named owner on the report card is accountable for the answer, not a shared "
          "inbox."),
         ("4", "The outcome is published",
          "If a definition changes, it changes on How to read these reports and in the "
          "report tooltip at the same time.")]
sy = 260
for n, title, desc in STEPS:
    oval(48, sy, 22, 22, NAVY)
    text(48, sy + 4, 22, 16, [(n, 9, WHITE, True)], align="center")
    text(80, sy - 1, 500, 18, [(title, 10, INK, True)])
    text(80, sy + 16, 716, 36, [(desc, 9, MUTED, False)])
    sy += 60

rect(836, 214, 420, 300, fill=WHITE, border=LINE)
text(860, 230, 300, 22, [("Raise it now", 12, INK, True)])
text(860, 251, 380, 38,
     [("Takes about a minute. You will get the ticket reference back on screen.", 9,
       MUTED, False)])
button(860, 296, 372, 40, "Submit a change request", color=WHITE, size=11,
       fill=NAVY, border=NAVY)
text(860, 344, 380, 19, [("Opens the Power Automate flow in this report.", 9, MUTED, False)])
rect(860, 376, 372, 1, fill=LINE, radius=0)
text(860, 390, 380, 19, [("Prefer to ask a person first?", 10, INK, True)])
cy = 414
for initials, name, sub in CONTACTS_STD:
    oval(860, cy, 30, 30, NAVY)
    text(860, cy + 8, 30, 16, [(initials, 9, WHITE, True)], align="center")
    text(900, cy - 1, 320, 18, [(name, 10, INK, True)])
    text(900, cy + 14, 330, 19, [(sub, 9, NAVY, False)])
    cy += 44

rect(24, 530, 1232, 148, fill=WHITE, border=LINE)
text(48, 544, 500, 22, [("Request states", 12, INK, True)])
text(48, 565, 700, 19,
     [("The three states the button shows, so a submitted request never looks like nothing "
       "happened.", 9, MUTED, False)])
STATES = [("Ready", "certified", "Default state. The button is live and the flow is reachable."),
          ("Sent", "promoted", "Confirmation with a ticket reference, shown in place."),
          ("Unavailable", "notvalid",
           "Tenant settings block the Power Automate visual — falls back to the named "
           "owner's email.")]
for i, (label, state, desc) in enumerate(STATES):
    bx = 48 + i * 400
    col, fill, brd = BADGE[state]
    rect(bx, 594, 96, 22, fill=fill, border=brd, radius=11)
    text(bx, 599, 96, 17, [(label, 9, col, True)], align="center")
    text(bx, 622, 370, 42, [(desc, 9, INK, False)])
footnote("The Power Automate visual is subject to a tenant setting we have not yet "
         "confirmed — the fallback path is designed for, not bolted on later.")
counts["Request a change"] = finish_page()

# =============================================================================
# PAGE 7 — Access and data states
# =============================================================================
start_page(P_STATES, "Access & data states")
chrome("")
intro_tile("Access & data states",
           "The two screens users hit that are not the happy path. Both are designed rather "
           "than left to the platform default, because both are moments where trust is won "
           "or lost.")

text(24, 216, 700, 18,
     [("STATE 1 — user has no audience membership", 9, ALERT, True)])
rect(24, 238, 1232, 214, fill=WHITE, border=LINE)
rect(608, 252, 64, 34, fill=PILL_BG, radius=6)
rect(630, 261, 20, 16, fill=NAVY, radius=3)
text(24, 294, 1232, 26, [("You don't have access to this app yet", 16, INK, True)],
     align="center")
text(190, 324, 900, 44,
     [("Mines Data Platform is organised into four audiences — Executive, Compliance & "
       "Enforcement, Permitting & Titles, and Audit & Analysis. Your account is not yet a "
       "member of any of them, so there is nothing to display.", 10, MUTED, False)],
     align="center")
button(468, 376, 160, 34, "Request access", color=WHITE, size=10, fill=NAVY, border=NAVY)
button(652, 376, 160, 34, "Who should I ask?", color=NAVY, size=10, border=LINE)
measure_card(24, 418, 1232, 20, "Hub Access Note", size=9, color=FAINT, align="center")

text(24, 462, 700, 18, [("STATE 2 — report has not refreshed on schedule", 9, ALERT, True)])
rect(24, 484, 1232, 190, fill=WHITE, border=LINE)
rect(24, 484, 4, 190, fill=ALERT, radius=0)
text(52, 496, 600, 24, [("Start here — Executive view", 14, NAVY, True)])
measure_card(52, 520, 900, 40, "Hub Stale Warning", size=10, color=INK, align="left")
rect(1000, 494, 232, 26, fill="#FDF3F0", border=ALERT, radius=13)
measure_card(1000, 499, 232, 18, "Hub Data As At", size=9, color=ALERT, align="center")
for i, (label, chip) in enumerate([("Inspections", BLUE), ("Incidents", RED),
                                   ("Notice of Work", GREEN)]):
    x = 52 + i * 396
    rect(x, 570, 372, 88, fill="#FAFAFA", border=LINE)
    rect(x + 20, 590, 12, 12, fill=chip, radius=3)
    text(x + 40, 584, 240, 22, [(label, 11, MUTED, True)])
    rect(x + 20, 614, 150, 22, fill="#FDF3F0", border=ALERT, radius=11)
    measure_card(x + 20, 617, 150, 18, "Hub Data As At", size=8, color=ALERT,
                 align="center")
    text(x + 182, 616, 180, 19, [("Not current", 9, MUTED, False)])
footnote("Survey evidence: outdated data / unclear refresh scored 2.6 of 4 for severity, and "
         "4 of 6 operational respondents verify figures by hand. Never show a stale number "
         "without saying it is stale — and never hide the tile.")
counts["Access & data states"] = finish_page()

# --- pages.json --------------------------------------------------------------
order = [P_EXEC, P_COMP, P_PERM, P_AUDIT, P_DEFS, P_CHANGE, P_STATES]
with open(os.path.join(PAGES_DIR, "pages.json"), "w", encoding="utf-8") as f:
    json.dump({"$schema": PM, "pageOrder": order, "activePageName": P_EXEC}, f, indent=2)

print(f"navigation links: {'ON' if NAV else 'OFF'}")
for k, v in counts.items():
    print(f"  {k:<26} {v:>3} visuals")
print("total visuals:", sum(counts.values()))
