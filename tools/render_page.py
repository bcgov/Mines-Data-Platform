#!/usr/bin/env python3
"""Offline preview of a PBIR page: reads the generated JSON back and draws it as
HTML, so layout can be checked without a push/deploy cycle.

  python3 tools/render_page.py "<report>.Report" <pageId> [out.html] [--links]

--links outlines every actionButton hit target and prints where it navigates.
"""
import json, os, sys, html

ROOT, PID = sys.argv[1], sys.argv[2]
OUT = sys.argv[3] if len(sys.argv) > 3 and not sys.argv[3].startswith("--") \
    else "/tmp/preview.html"
SHOW_LINKS = "--links" in sys.argv
PD = os.path.join(ROOT, "definition", "pages", PID)
page = json.load(open(os.path.join(PD, "page.json"), encoding="utf-8"))


def val(x):
    if isinstance(x, dict):
        if "expr" in x and "Literal" in x["expr"]:
            v = x["expr"]["Literal"]["Value"]
            return v.strip("'").rstrip("D")
        if "solid" in x:
            return val(x["solid"]["color"])
        if "color" in x:
            return val(x["color"])
    return x


def prop(objs, name, key):
    for e in (objs or {}).get(name, []):
        if key in e.get("properties", {}):
            return val(e["properties"][key])
    return None


items = []
vdir = os.path.join(PD, "visuals")
for vid in sorted(os.listdir(vdir)):
    v = json.load(open(os.path.join(vdir, vid, "visual.json"), encoding="utf-8"))
    items.append(v)
items.sort(key=lambda v: v["position"]["z"])

body = []
for v in items:
    p, vis = v["position"], v["visual"]
    vt, o = vis["visualType"], vis.get("objects", {})
    vco = vis.get("visualContainerObjects", {})
    bg = prop(vco, "background", "color")
    bd = prop(vco, "border", "color")
    rad = prop(vco, "border", "radius") or 0
    st = (f"left:{p['x']}px;top:{p['y']}px;width:{p['width']}px;"
          f"height:{p['height']}px;z-index:{p['z']};")
    if bg:
        st += f"background:{bg};"
    if bd:
        st += f"border:1px solid {bd};border-radius:{float(rad)}px;"
    inner = ""
    if vt == "textbox":
        para = o["general"][0]["properties"]["paragraphs"][0]
        align = para.get("horizontalTextAlignment", "left")
        runs = ""
        for r in para["textRuns"]:
            ts = r["textStyle"]
            runs += (f"<span style=\"font-size:{ts['fontSize']};color:{ts['color']};"
                     f"font-weight:{ts.get('fontWeight','normal')}\">"
                     f"{html.escape(r['value'])}</span>")
        inner = (f"<div style='padding:5px 4px;text-align:{align};"
                 f"line-height:21px'>{runs}</div>")
    elif vt == "cardVisual":
        m = vis["query"]["queryState"]["Data"]["projections"][0]["nativeQueryRef"]
        col = prop(o, "value", "fontColor") or "#252423"
        size = prop(o, "value", "fontSize") or "10"
        al = prop(o, "value", "horizontalAlignment") or "center"
        bold = prop(o, "value", "bold")
        px = round(float(size) * 4 / 3)
        inner = (f"<div style='padding:13px 20px;text-align:{al};color:{col};"
                 f"font-size:{px}px;font-weight:{'bold' if bold else 'normal'};"
                 f"line-height:18px;white-space:nowrap;overflow:hidden;"
                 f"text-overflow:ellipsis' title='{m}'>[{html.escape(m)}]</div>")
    elif vt == "image":
        st += "background:#013366;border-radius:3px;"
        inner = ("<div style='color:#fff;font-size:11px;padding:14px 10px'>"
                 "BC logo</div>")
    elif vt == "shape":
        pass
    elif vt == "actionButton":
        tgt = prop(vco, "visualLink", "navigationSection") or \
              prop(vco, "visualLink", "webUrl")
        if SHOW_LINKS and tgt:
            st += "outline:1px dashed #C8102E;"
            inner = (f"<div style='font-size:9px;color:#C8102E;padding:1px 3px'>"
                     f"&#8594;{html.escape(str(tgt))[-14:]}</div>")
    body.append(f"<div class='v' style=\"{st}\">{inner}</div>")

doc = f"""<!doctype html><meta charset="utf-8"><title>{html.escape(page['displayName'])}</title>
<style>body{{margin:0;background:#555;font-family:'Segoe UI',system-ui,sans-serif}}
.page{{position:relative;width:{page['width']}px;height:{page['height']}px;
background:#F2F2F2;margin:16px auto;box-shadow:0 2px 18px #0006;overflow:hidden}}
.v{{position:absolute;box-sizing:border-box;overflow:hidden}}</style>
<div class="page">{''.join(body)}</div>"""
open(OUT, "w", encoding="utf-8").write(doc)
print("wrote", OUT, len(items), "visuals")
