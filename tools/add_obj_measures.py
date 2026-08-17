# Adds the Object-model measures to fact_inspection.tmdl (additive only).
# Every figure the object page shows must resolve from the model - "313 must
# update itself" (Romil, 21 Jul). These carry the DEFINITION, the exact DATE
# WINDOW, the TRUST tag and the medallion LAYER for each KPI, so none of it is
# typed onto the page.
import io, os, re, sys

PATH = sys.argv[1]
FY = ('VAR d = TODAY () VAR fy = IF ( MONTH ( d ) >= 4, YEAR ( d ), YEAR ( d ) - 1 ) ')

M = []
def add(name, expr, desc, folder="Object"):
    M.append((name, expr, desc, folder))

# --- what each KPI counts -----------------------------------------------------
add("Obj Def Total",
    '"Every inspection ever recorded. Distinct count of inspection_id, all types, no date filter."',
    "Object page - DEFINITION line for Inspections Total.")
add("Obj Def FYTD",
    '"Inspections whose inspection_date falls in the current BC fiscal year, up to and including today. Distinct inspection_id, all types."',
    "Object page - DEFINITION line for Inspections FYTD.")
add("Obj Def Same Last FY",
    '"The same window one year earlier, so the comparison is like-for-like: 1 April of last fiscal year to this date last year."',
    "Object page - DEFINITION line for Inspections Same Time Last FY.")
add("Obj Def Last Month",
    '"Inspections in the rolling previous 30 days. Matches the Metabase ""Inspection Date Previous 30 Days"" filter - it is NOT last calendar month."',
    "Object page - DEFINITION line for Inspections Last Month.")
add("Obj Def Prev FY",
    '"Every inspection in the last completed fiscal year, 1 April to 31 March."',
    "Object page - DEFINITION line for Inspections Prev FY Total.")

# --- the exact date window each KPI uses, computed ---------------------------
add("Obj Win Total",
    'VAR a = MIN ( fact_inspection[inspection_date] ) VAR b = MAX ( fact_inspection[inspection_date] ) '
    'RETURN IF ( ISBLANK ( a ), "No inspection dates present", '
    'FORMAT ( a, "d MMMM yyyy" ) & " to " & FORMAT ( b, "d MMMM yyyy" ) & "  (all data)" )',
    "Object page - the actual date window behind Inspections Total.")
add("Obj Win FYTD",
    FY + 'RETURN FORMAT ( DATE ( fy, 4, 1 ), "d MMMM yyyy" ) & " to " & FORMAT ( d, "d MMMM yyyy" ) & "  (inclusive)"',
    "Object page - the exact date window behind Inspections FYTD. Recalculates daily.")
add("Obj Win Same Last FY",
    FY + 'RETURN FORMAT ( DATE ( fy - 1, 4, 1 ), "d MMMM yyyy" ) & " to " & FORMAT ( EDATE ( d, -12 ), "d MMMM yyyy" ) & "  (inclusive)"',
    "Object page - the exact date window behind Inspections Same Time Last FY.")
add("Obj Win Last Month",
    'VAR d = TODAY () RETURN FORMAT ( d - 30, "d MMMM yyyy" ) & " to " & FORMAT ( d - 1, "d MMMM yyyy" ) & "  (rolling 30 days)"',
    "Object page - the exact date window behind Inspections Last Month.")
add("Obj Win Prev FY",
    FY + 'RETURN FORMAT ( DATE ( fy - 1, 4, 1 ), "d MMMM yyyy" ) & " to " & FORMAT ( DATE ( fy, 3, 31 ), "d MMMM yyyy" )',
    "Object page - the exact date window behind Inspections Prev FY Total.")

# --- trust tag per KPI, derived from whether the window is actually covered ---
COVER = ('VAR mx = CALCULATE ( MAX ( fact_inspection[inspection_date] ), ALL ( fact_inspection ) ) ')
add("Obj Trust Total",
    '"Certified"',
    "Object page - trust tag for Inspections Total. All-time count needs no window coverage.")
add("Obj Trust FYTD",
    COVER + FY + 'VAR needed = d RETURN IF ( ISBLANK ( mx ), "Not validated", '
    'IF ( mx >= needed, "Certified", "Provisional" ) )',
    "Object page - trust tag for Inspections FYTD. Drops to Provisional when gold does not cover the whole window - the automated check the 21 Jul 'blue tick' discussion asked for, in its simplest form.")
add("Obj Trust Same Last FY",
    COVER + 'VAR needed = EDATE ( TODAY (), -12 ) RETURN IF ( ISBLANK ( mx ), "Not validated", '
    'IF ( mx >= needed, "Certified", "Provisional" ) )',
    "Object page - trust tag for Inspections Same Time Last FY.")
add("Obj Trust Last Month",
    COVER + 'VAR needed = TODAY () - 1 RETURN IF ( ISBLANK ( mx ), "Not validated", '
    'IF ( mx >= needed, "Certified", "Provisional" ) )',
    "Object page - trust tag for Inspections Last Month. Reads Provisional today because gold ends 7 July.")
add("Obj Trust Prev FY",
    COVER + FY + 'VAR needed = DATE ( fy, 3, 31 ) RETURN IF ( ISBLANK ( mx ), "Not validated", '
    'IF ( mx >= needed, "Certified", "Provisional" ) )',
    "Object page - trust tag for Inspections Prev FY Total.")

# --- coverage / medallion / identity ------------------------------------------
add("Obj Coverage Note",
    COVER + FY + 'VAR fyStart = DATE ( fy, 4, 1 ) VAR d = TODAY () '
    'RETURN IF ( ISBLANK ( mx ), "No inspection data is present in gold.", '
    'IF ( mx >= d, "Gold covers the full fiscal year to date - every window on this page is complete.", '
    '"Gold ends " & FORMAT ( mx, "d MMMM yyyy" ) & ", so windows running past that date are incomplete. '
    'Figures are shown and labelled rather than hidden." ) )',
    "Object page - plain-language statement of what the data does and does not cover.")
add("Obj Layer",
    '"Gold  ·  lh_gold.fact_inspection  ·  built from CORE and NRIS via the bronze and silver layers"',
    "Object page - where this object sits in the bronze / silver / gold medallion, per the 5 Aug ask.")
add("Obj Record Count",
    'VAR n = DISTINCTCOUNT ( fact_inspection[inspection_id] ) VAR m = DISTINCTCOUNT ( fact_inspection[mine_guid] ) '
    'VAR t = DISTINCTCOUNT ( fact_inspection[inspection_type_id] ) '
    'RETURN FORMAT ( n, "#,0" ) & " inspections  ·  " & FORMAT ( m, "#,0" ) & " mines  ·  " & FORMAT ( t, "#,0" ) & " inspection types"',
    "Object page - the object's shape in one line, straight from the data.")
add("Obj Rel Mine",
    'VAR m = DISTINCTCOUNT ( fact_inspection[mine_guid] ) RETURN "Mine  —  " & FORMAT ( m, "#,0" ) & " related mines  ·  via mine_guid"',
    "Object page - RELATIONSHIP line, Inspection to Mine.")
add("Obj Rel Type",
    'VAR t = DISTINCTCOUNT ( fact_inspection[inspection_type_id] ) RETURN "Inspection Type  —  " & FORMAT ( t, "#,0" ) & " types  ·  via inspection_type_id"',
    "Object page - RELATIONSHIP line, Inspection to Inspection Type.")
add("Obj Rel Date",
    'VAR a = MIN ( fact_inspection[inspection_date] ) VAR b = MAX ( fact_inspection[inspection_date] ) '
    'RETURN IF ( ISBLANK ( a ), "Date  —  no dates present", "Date  —  " & FORMAT ( a, "MMM yyyy" ) & " to " '
    '& FORMAT ( b, "MMM yyyy" ) & "  ·  via inspection_date_key" )',
    "Object page - RELATIONSHIP line, Inspection to Date.")
add("Obj Identity Note",
    'VAR ins = DISTINCTCOUNT ( fact_inspection[inspector_idir] ) '
    'RETURN "Keyed on inspection_id  ·  " & FORMAT ( ins, "#,0" ) & " distinct inspectors recorded in inspector_idir"',
    "Object page - IDENTITY line. inspector_idir is the field Inspection carries that Notice of Work does not.")

# --- formatted value lines: a card must never render "(blank)" ---------------
# The 5 Aug rule was "never show an empty card - show the number, tag the trust
# level, say where it sits". So the value is formatted here and falls back to an
# em dash, with the trust tag and the coverage note carrying the explanation.
for nm, base in [("Total", "Inspections Total"), ("FYTD", "Inspections FYTD"),
                 ("Same Last FY", "Inspections Same Time Last FY"),
                 ("Last Month", "Inspections Last Month"),
                 ("Prev FY", "Inspections Prev FY Total")]:
    add(f"Obj Val {nm}",
        f'VAR v = [{base}] RETURN IF ( ISBLANK ( v ), "—", FORMAT ( v, "#,0" ) )',
        f"Object page - display value for {base}. Falls back to an em dash rather "
        f"than rendering (blank), per the 5 Aug 'never show an empty card' rule.")

# ------------------------------------------------------------------ emit TMDL
lines = []
for i, (name, expr, desc, folder) in enumerate(M):
    lines.append(f"\t/// {desc}")
    lines.append(f"\tmeasure '{name}' = {expr}")
    lines.append(f"\t\tdisplayFolder: {folder}")
    lines.append(f"\t\tlineageTag: 0b1e{i:04d}-0000-4000-8000-00000000{i:04d}")
    lines.append("")
block = "\r\n".join(lines) + "\r\n"

raw = io.open(PATH, "r", encoding="utf-8", newline="").read()
if "Obj Def FYTD" in raw:
    print("already present - no change"); sys.exit(0)
marker = raw.find("\r\n\tcolumn ")
if marker < 0:
    print("ERROR: no column block found"); sys.exit(1)
out = raw[:marker + 2] + block + raw[marker + 2:]
io.open(PATH, "w", encoding="utf-8", newline="").write(out)
print(f"inserted {len(M)} measures")
