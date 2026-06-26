"""Delete a Fabric notebook workspace item by displayName. Auth = SPN Fabric token.
Env: WORKSPACE_ID, ITEM_NAME."""
import os
import sys

import requests

BASE = "https://api.fabric.microsoft.com/v1"
H = {"Authorization": f"Bearer {os.environ['FABRIC_TOKEN']}"}
WS = os.environ["WORKSPACE_ID"]
NAME = os.environ["ITEM_NAME"]


def log(*a):
    print(*a, file=sys.stderr, flush=True)


r = requests.get(f"{BASE}/workspaces/{WS}/notebooks", headers=H)
r.raise_for_status()
nid = next((it["id"] for it in r.json().get("value", []) if it.get("displayName") == NAME), None)
if not nid:
    log(f"{NAME}: not found (already deleted?)")
    sys.exit(0)
d = requests.delete(f"{BASE}/workspaces/{WS}/notebooks/{nid}", headers=H)
log(f"delete {NAME} ({nid}): HTTP {d.status_code} {d.text[:300]}")
sys.exit(0 if d.status_code in (200, 202) else 1)
