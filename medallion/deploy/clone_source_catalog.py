"""Clone the team's Metadata_Extractor pipeline into a NEW pipeline 'pl_extract_source_catalog'
that lands the FULL source column catalog (not just PK columns) to bronze Files/raw/mds_source_catalog.
Originals (Metadata_Extractor, pl_ingest_mds) are left untouched; the same source Postgres
connection is reused by GUID. Optionally runs the new pipeline (RUN=true).
Auth = SPN Fabric token (FABRIC_TOKEN). Env: WORKSPACE_ID, RUN.
"""
import base64
import json
import os
import re
import sys
import time

import requests

BASE = "https://api.fabric.microsoft.com/v1"
TOKEN = os.environ["FABRIC_TOKEN"]
WS = os.environ["WORKSPACE_ID"]
RUN = os.environ.get("RUN", "false").lower() == "true"
NEW_NAME = "pl_extract_source_catalog"
NEW_FILE = "mds_source_catalog"
H = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def b64(s):
    return base64.b64encode(s.encode("utf-8")).decode("ascii")


def find_pipeline(name):
    r = requests.get(f"{BASE}/workspaces/{WS}/dataPipelines", headers=H)
    r.raise_for_status()
    return next((it for it in r.json().get("value", []) if it.get("displayName") == name), None)


def get_parts(pid):
    r = requests.post(f"{BASE}/workspaces/{WS}/dataPipelines/{pid}/getDefinition", headers=H)
    if r.status_code == 202:
        op = r.headers.get("Operation-Location") or r.headers.get("Location")
        for _ in range(40):
            time.sleep(3)
            s = requests.get(op, headers=H)
            if (s.json() or {}).get("status") in ("Succeeded", "Completed"):
                r = requests.get(op + "/result", headers=H)
                break
    r.raise_for_status()
    return {p["path"]: p["payload"] for p in r.json()["definition"]["parts"]}


src = find_pipeline("Metadata_Extractor")
if not src:
    log("Metadata_Extractor not found"); sys.exit(1)
parts = get_parts(src["id"])
content = json.loads(base64.b64decode(parts["pipeline-content.json"]).decode("utf-8"))

# 1) modify the Copy activity: drop the PK-only filter, repoint the sink file name
acts = content.get("properties", content).get("activities", [])
copy = next(a for a in acts if a.get("type") == "Copy")
q = copy["typeProperties"]["source"]["query"]
q2 = re.sub(r"\s*WHERE\s+is_primary_key\s*=\s*'YES'", "", q, flags=re.IGNORECASE)
copy["typeProperties"]["source"]["query"] = q2
log("PK filter removed:", q2 != q)
loc = copy["typeProperties"]["sink"]["datasetSettings"]["typeProperties"]["location"]
log("sink file:", loc.get("fileName"), "->", NEW_FILE)
loc["fileName"] = NEW_FILE

# 2) new .platform (rename); keep the source connection GUID untouched
platform = json.loads(base64.b64decode(parts[".platform"]).decode("utf-8"))
platform["metadata"]["displayName"] = NEW_NAME

new_parts = [
    {"path": ".platform", "payload": b64(json.dumps(platform)), "payloadType": "InlineBase64"},
    {"path": "pipeline-content.json", "payload": b64(json.dumps(content)), "payloadType": "InlineBase64"},
]

# 3) create-or-update the new pipeline
existing = find_pipeline(NEW_NAME)
if existing:
    pid = existing["id"]
    log(f"updating {NEW_NAME} ({pid})")
    r = requests.post(f"{BASE}/workspaces/{WS}/dataPipelines/{pid}/updateDefinition",
                      headers=H, json={"definition": {"parts": new_parts}})
else:
    log(f"creating {NEW_NAME}")
    r = requests.post(f"{BASE}/workspaces/{WS}/dataPipelines",
                      headers=H, json={"displayName": NEW_NAME, "definition": {"parts": new_parts}})
if r.status_code in (200, 201, 202):
    if r.status_code == 202:
        op = r.headers.get("Operation-Location") or r.headers.get("Location")
        for _ in range(40):
            time.sleep(3)
            if (requests.get(op, headers=H).json() or {}).get("status") in ("Succeeded", "Completed"):
                break
    pid = (find_pipeline(NEW_NAME) or {}).get("id")
    log(f"{NEW_NAME} -> {pid}")
else:
    log("create/update failed:", r.status_code, r.text[:600]); sys.exit(1)

# 4) optionally run it
if RUN and pid:
    log("running pipeline...")
    rr = requests.post(f"{BASE}/workspaces/{WS}/items/{pid}/jobs/instances?jobType=Pipeline", headers=H)
    if rr.status_code != 202:
        log("run submit failed:", rr.status_code, rr.text[:600]); sys.exit(1)
    loc = rr.headers.get("Location")
    for _ in range(120):
        time.sleep(10)
        st = (requests.get(loc, headers=H).json() or {})
        s = st.get("status", "")
        log("  status:", s)
        if s == "Completed":
            log("PIPELINE RUN COMPLETED"); break
        if s in ("Failed", "Cancelled", "Deduped"):
            log("PIPELINE RUN", s, "-", json.dumps(st.get("failureReason") or st)[:800]); sys.exit(1)
    else:
        log("run poll timeout"); sys.exit(1)
log("DONE")
