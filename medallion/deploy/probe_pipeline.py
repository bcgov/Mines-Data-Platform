"""Feasibility probe: is pl_ingest_mds a Fabric Data pipeline we can read/clone, and what
source connection does it use? Lists workspace data pipelines and dumps the definition of
pl_ingest_mds (connection refs + copy-activity shape) so we can design a metadata-copy clone.
Read-only. Auth = SPN Fabric token (FABRIC_TOKEN). Env: WORKSPACE_ID."""
import base64
import json
import os
import sys
import time

import requests

BASE = "https://api.fabric.microsoft.com/v1"
TOKEN = os.environ["FABRIC_TOKEN"]
WS = os.environ["WORKSPACE_ID"]
H = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def get_def(pid):
    r = requests.post(f"{BASE}/workspaces/{WS}/dataPipelines/{pid}/getDefinition", headers=H)
    if r.status_code == 200:
        data = r.json()
    elif r.status_code == 202:
        op = r.headers.get("Operation-Location") or r.headers.get("Location")
        data = None
        for _ in range(40):
            time.sleep(3)
            s = requests.get(op, headers=H)
            st = (s.json() or {}).get("status", "") if s.status_code == 200 else ""
            if st in ("Succeeded", "Completed"):
                res = requests.get(op + "/result", headers=H)
                data = res.json() if res.status_code == 200 else s.json()
                break
            if st in ("Failed", "Cancelled"):
                log("LRO failed:", s.text[:400]); return None
    else:
        log("getDefinition failed:", r.status_code, r.text[:400]); return None
    for p in (data or {}).get("definition", {}).get("parts", []):
        if p["path"].endswith("pipeline-content.json"):
            return json.loads(base64.b64decode(p["payload"]).decode("utf-8"))
    return None


def walk_conns(node, out):
    if isinstance(node, dict):
        if "connection" in node and isinstance(node["connection"], str):
            out.add(node["connection"])
        for v in node.values():
            walk_conns(v, out)
    elif isinstance(node, list):
        for v in node:
            walk_conns(v, out)


# connections map (GUID -> name/type)
rc = requests.get(f"{BASE}/connections", headers=H)
log("connections list:", rc.status_code)
conns = {}
if rc.status_code == 200:
    for c in rc.json().get("value", []):
        conns[c.get("id")] = (c.get("displayName"), (c.get("connectionDetails") or {}).get("type"))
        log("  conn:", c.get("id"), "|", c.get("displayName"), "|",
            (c.get("connectionDetails") or {}).get("type"))

# pipelines
r = requests.get(f"{BASE}/workspaces/{WS}/dataPipelines", headers=H)
items = r.json().get("value", []) if r.status_code == 200 else []
by_name = {it.get("displayName"): it.get("id") for it in items}
log("\npipelines:", list(by_name))

# 1) Metadata_Extractor — dump full content (likely small + exactly relevant)
if "Metadata_Extractor" in by_name:
    c = get_def(by_name["Metadata_Extractor"])
    if c:
        log("\n================ Metadata_Extractor (full) ================")
        log(json.dumps(c)[:12000])

# 2) pl_ingest_mds — all activities (incl. nested) + every connection GUID used
if "pl_ingest_mds" in by_name:
    c = get_def(by_name["pl_ingest_mds"])
    if c:
        props = c.get("properties", c)

        def walk_acts(acts, depth=0):
            for a in acts or []:
                log("   " * depth + "- " + str(a.get("name")) + " | " + str(a.get("type")))
                tp = a.get("typeProperties", {})
                walk_acts(tp.get("activities"), depth + 1)  # ForEach/If inner activities
        log("\n================ pl_ingest_mds activities ================")
        walk_acts(props.get("activities"))
        used = set(); walk_conns(c, used)
        log("\nconnection GUIDs used by pl_ingest_mds:")
        for g in used:
            log("  ", g, "->", conns.get(g, "(unknown)"))
