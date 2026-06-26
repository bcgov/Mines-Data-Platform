"""Deploy a single notebook item into a Fabric workspace (create-or-update) and
optionally run it as a job, waiting for the result. Auth = SPN Fabric token (FABRIC_TOKEN).

Env: WORKSPACE_ID, NOTEBOOK_NAME, NOTEBOOK_DIR, RUN ("true"/"false")."""

import base64
import os
import sys
import time

import requests

BASE = "https://api.fabric.microsoft.com/v1"
TOKEN = os.environ["FABRIC_TOKEN"]
WS = os.environ["WORKSPACE_ID"]
NAME = os.environ["NOTEBOOK_NAME"]
NB_DIR = os.environ["NOTEBOOK_DIR"]
RUN = os.environ.get("RUN", "false").lower() == "true"
H = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def b64(text):
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def poll_lro(url, tries=60, delay=5):
    for _ in range(tries):
        r = requests.get(url, headers=H)
        if r.status_code in (200, 201):
            st = (r.json() or {}).get("status", "")
            if st in ("Succeeded", "Completed"):
                return
            if st in ("Failed", "Cancelled", "Deduped"):
                log("LRO failed:", r.text)
                sys.exit(1)
        time.sleep(delay)
    log("LRO timeout:", url)
    sys.exit(1)


def wait(resp):
    if resp.status_code in (200, 201):
        return
    if resp.status_code == 202:
        loc = resp.headers.get("Operation-Location") or resp.headers.get("Location")
        if loc:
            poll_lro(loc)
        return
    log("unexpected response:", resp.status_code, resp.text)
    sys.exit(1)


def find_notebook(name):
    r = requests.get(f"{BASE}/workspaces/{WS}/notebooks", headers=H)
    r.raise_for_status()
    for it in r.json().get("value", []):
        if it.get("displayName") == name:
            return it["id"]
    return None


def deploy():
    content = open(f"{NB_DIR}/notebook-content.py", encoding="utf-8").read()
    platform = open(f"{NB_DIR}/.platform", encoding="utf-8").read()
    parts = [
        {"path": ".platform", "payload": b64(platform), "payloadType": "InlineBase64"},
        {"path": "notebook-content.py", "payload": b64(content), "payloadType": "InlineBase64"},
    ]
    nid = find_notebook(NAME)
    if nid:
        log(f"updating {NAME} ({nid})")
        wait(requests.post(f"{BASE}/workspaces/{WS}/notebooks/{nid}/updateDefinition",
                           headers=H, json={"definition": {"parts": parts}}))
    else:
        log(f"creating {NAME}")
        wait(requests.post(f"{BASE}/workspaces/{WS}/notebooks",
                           headers=H, json={"displayName": NAME, "definition": {"parts": parts}}))
        nid = find_notebook(NAME)
    log(f"{NAME} -> {nid}")
    return nid


def run_notebook(nid):
    r = requests.post(f"{BASE}/workspaces/{WS}/items/{nid}/jobs/instances?jobType=RunNotebook", headers=H)
    if r.status_code != 202:
        log("run submit failed:", r.status_code, r.text)
        sys.exit(1)
    loc = r.headers.get("Location")
    log(f"running {NAME}; polling {loc}")
    for _ in range(420):  # up to ~70 min (registry-driven silver builds many tables)
        time.sleep(10)
        st = (requests.get(loc, headers=H).json() or {}).get("status", "")
        log("  status:", st)
        if st == "Completed":
            log(f"{NAME} RUN COMPLETED")
            return
        if st in ("Failed", "Cancelled"):
            log(f"{NAME} RUN {st}")
            sys.exit(1)
    log("run timeout")
    sys.exit(1)


nid = deploy()
if RUN:
    run_notebook(nid)
log("DONE")
