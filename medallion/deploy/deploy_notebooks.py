"""Deploy notebook items into a Fabric workspace via the Items API (create-or-update),
then run the smoke notebook as a job and wait for its result. Auth = SPN Fabric token
(passed in as FABRIC_TOKEN). GUID placeholders in the smoke notebook are injected here."""

import base64
import os
import sys
import time

import requests

BASE = "https://api.fabric.microsoft.com/v1"
TOKEN = os.environ["FABRIC_TOKEN"]
WS = os.environ["WORKSPACE_ID"]
H = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

GUIDS = {
    "<WORKSPACE_ID>": os.environ["WORKSPACE_ID"],
    "<BRONZE_LH_ID>": os.environ["BRONZE_LH_ID"],
    "<SILVER_LH_ID>": os.environ["SILVER_LH_ID"],
    "<GOLD_LH_ID>": os.environ["GOLD_LH_ID"],
}


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def b64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def poll_lro(url: str, tries: int = 60, delay: int = 5) -> None:
    for _ in range(tries):
        r = requests.get(url, headers=H)
        if r.status_code in (200, 201):
            st = (r.json() or {}).get("status", "")
            if st in ("Succeeded", "Completed"):
                return
            if st in ("Failed", "Cancelled", "Deduped"):
                log("LRO failed:", r.text)
                sys.exit(1)
        elif r.status_code == 202:
            pass
        else:
            log("LRO poll unexpected:", r.status_code, r.text)
            sys.exit(1)
        time.sleep(delay)
    log("LRO timeout:", url)
    sys.exit(1)


def wait(resp) -> None:
    if resp.status_code in (200, 201):
        return
    if resp.status_code == 202:
        loc = resp.headers.get("Operation-Location") or resp.headers.get("Location")
        if loc:
            poll_lro(loc)
        return
    log("unexpected response:", resp.status_code, resp.text)
    sys.exit(1)


def find_notebook(name: str):
    r = requests.get(f"{BASE}/workspaces/{WS}/notebooks", headers=H)
    r.raise_for_status()
    for it in r.json().get("value", []):
        if it.get("displayName") == name:
            return it["id"]
    return None


def deploy(name: str, folder: str, inject: bool = False) -> str:
    content = open(f"{folder}/notebook-content.py", encoding="utf-8").read()
    platform = open(f"{folder}/.platform", encoding="utf-8").read()
    if inject:
        for k, v in GUIDS.items():
            content = content.replace(k, v)
    parts = [
        {"path": ".platform", "payload": b64(platform), "payloadType": "InlineBase64"},
        {"path": "notebook-content.py", "payload": b64(content), "payloadType": "InlineBase64"},
    ]
    nid = find_notebook(name)
    if nid:
        log(f"updating {name} ({nid})")
        r = requests.post(
            f"{BASE}/workspaces/{WS}/notebooks/{nid}/updateDefinition",
            headers=H, json={"definition": {"parts": parts}},
        )
        wait(r)
    else:
        log(f"creating {name}")
        r = requests.post(
            f"{BASE}/workspaces/{WS}/notebooks",
            headers=H, json={"displayName": name, "definition": {"parts": parts}},
        )
        wait(r)
        nid = find_notebook(name)
    log(f"{name} -> {nid}")
    return nid


def run_notebook(nid: str, name: str) -> None:
    r = requests.post(
        f"{BASE}/workspaces/{WS}/items/{nid}/jobs/instances?jobType=RunNotebook",
        headers=H,
    )
    if r.status_code != 202:
        log("run submit failed:", r.status_code, r.text)
        sys.exit(1)
    loc = r.headers.get("Location")
    log(f"running {name}; polling {loc}")
    for _ in range(120):  # up to ~20 min
        time.sleep(10)
        jr = requests.get(loc, headers=H)
        st = (jr.json() or {}).get("status", "")
        log("  status:", st)
        if st == "Completed":
            log(f"{name} RUN COMPLETED")
            return
        if st in ("Failed", "Cancelled"):
            log(f"{name} RUN {st}:", jr.text)
            sys.exit(1)
    log("run timeout")
    sys.exit(1)


deploy("nb_util_paths", "Fabric/Notebook/utility/nb_util_paths.Notebook")
smoke_id = deploy("nb_smoke_foundation", "Fabric/Notebook/test/nb_smoke_foundation.Notebook", inject=True)
run_notebook(smoke_id, "nb_smoke_foundation")
log("DONE")
