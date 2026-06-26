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


# 1) list data pipelines in the workspace
r = requests.get(f"{BASE}/workspaces/{WS}/dataPipelines", headers=H)
log("list dataPipelines:", r.status_code)
items = r.json().get("value", []) if r.status_code == 200 else []
for it in items:
    log("  pipeline:", it.get("displayName"), "->", it.get("id"))

target = next((it for it in items if it.get("displayName") == "pl_ingest_mds"), None)
if not target:
    log("NOTE: pl_ingest_mds is NOT a Fabric data pipeline item (likely external ADF).")
    # also dump any connections we can see
    rc = requests.get(f"{BASE}/connections", headers=H)
    log("connections list:", rc.status_code)
    if rc.status_code == 200:
        for c in rc.json().get("value", [])[:40]:
            log("  conn:", c.get("displayName"), "|", c.get("id"), "|",
                (c.get("connectionDetails") or {}).get("type"))
    sys.exit(0)

pid = target["id"]
log(f"\npl_ingest_mds id = {pid}; fetching definition...")
r = requests.post(f"{BASE}/workspaces/{WS}/dataPipelines/{pid}/getDefinition", headers=H)
log("getDefinition:", r.status_code)
data = None
if r.status_code == 200:
    data = r.json()
elif r.status_code == 202:
    op = r.headers.get("Operation-Location") or r.headers.get("Location")
    for _ in range(40):
        time.sleep(3)
        s = requests.get(op, headers=H)
        st = (s.json() or {}).get("status", "") if s.status_code == 200 else ""
        if st in ("Succeeded", "Completed"):
            res = requests.get(op + "/result", headers=H)
            data = res.json() if res.status_code == 200 else s.json()
            break
        if st in ("Failed", "Cancelled"):
            log("LRO failed:", s.text[:400]); sys.exit(1)
    else:
        log("LRO timeout"); sys.exit(1)
else:
    log("getDefinition failed:", r.text[:600]); sys.exit(1)

parts = (data or {}).get("definition", {}).get("parts", [])
log("definition parts:", [p.get("path") for p in parts])
for p in parts:
    if p["path"].endswith("pipeline-content.json"):
        content = json.loads(base64.b64decode(p["payload"]).decode("utf-8"))
        props = content.get("properties", content)
        acts = props.get("activities", [])
        log(f"\nactivities ({len(acts)}):")
        for a in acts:
            log("  -", a.get("name"), "|", a.get("type"))
        # surface connection / external references anywhere in the JSON
        raw = json.dumps(content)
        log("\nmentions externalReferences:", raw.count("externalReferences"),
            "| connection:", raw.count("connection"))
        # print a trimmed view of the first copy activity to see source query + connection
        copy = next((a for a in acts if a.get("type") == "Copy"), acts[0] if acts else None)
        if copy:
            log("\n--- first copy/activity (trimmed) ---")
            log(json.dumps(copy, indent=1)[:5000])
