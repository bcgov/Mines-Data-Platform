"""Organize our notebooks into Fabric WORKSPACE folders to mirror the repo layout:
  Notebook/                (nb_bronze_load, nb_silver_build, nb_gold_orchestrator)
  Notebook/stageQuery/     (nb_gold_tf_dim_permit, nb_gold_tf_fact_permit_amendment)
  Notebook/utility/        (nb_util_gold, nb_util_paths)
  Notebook/test/           (nb_gold_test, nb_smoke_foundation)
Team-owned notebooks (nb_bronze_master, Nb_Silver_Master) are left at the workspace root.
Idempotent. Auth = SPN Fabric token (FABRIC_TOKEN). Env: WORKSPACE_ID.
"""
import os
import sys
import time

import requests

BASE = "https://api.fabric.microsoft.com/v1"
TOKEN = os.environ["FABRIC_TOKEN"]
WS = os.environ["WORKSPACE_ID"]
H = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

LAYOUT = {
    "_root":      ["nb_bronze_load", "nb_silver_registry", "nb_silver_build", "nb_gold_orchestrator"],
    "stageQuery": ["nb_gold_tf_dim_permit", "nb_gold_tf_fact_permit_amendment",
                   "nb_gold_tf_dim_party", "nb_gold_tf_dim_municipality",
                   "nb_gold_tf_dim_amendment_enriched", "nb_gold_tf_fact_amendment_activity"],
    "utility":    ["nb_util_gold", "nb_util_paths"],
    "test":       ["nb_gold_test", "nb_smoke_foundation"],
}


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def get(url):
    r = requests.get(url, headers=H)
    r.raise_for_status()
    return r.json()


def list_folders():
    return get(f"{BASE}/workspaces/{WS}/folders").get("value", [])


def list_items():
    return get(f"{BASE}/workspaces/{WS}/items").get("value", [])


def find_folder(name, parent_id):
    for f in list_folders():
        if f["displayName"] == name and (f.get("parentFolderId") or None) == (parent_id or None):
            return f["id"]
    return None


def ensure_folder(name, parent_id=None):
    fid = find_folder(name, parent_id)
    if fid:
        log(f"folder exists: {name} ({fid})")
        return fid
    body = {"displayName": name}
    if parent_id:
        body["parentFolderId"] = parent_id
    r = requests.post(f"{BASE}/workspaces/{WS}/folders", headers=H, json=body)
    if r.status_code in (200, 201):
        fid = r.json()["id"]
        log(f"created folder: {name} ({fid})")
        return fid
    if r.status_code == 202:  # async — re-list until it appears
        for _ in range(12):
            time.sleep(3)
            fid = find_folder(name, parent_id)
            if fid:
                log(f"created folder (async): {name} ({fid})")
                return fid
    log(f"create folder {name} failed: {r.status_code} {r.text}")
    sys.exit(1)


def move_item(item_id, target_folder_id):
    return requests.post(f"{BASE}/workspaces/{WS}/items/{item_id}/move", headers=H,
                         json={"targetFolderId": target_folder_id})


# 1) folders (Notebook + subfolders)
root = ensure_folder("Notebook")
sub = {name: ensure_folder(name, root) for name in ("stageQuery", "utility", "test")}

# 2) target folder per notebook
target = {nb: root for nb in LAYOUT["_root"]}
for name in ("stageQuery", "utility", "test"):
    for nb in LAYOUT[name]:
        target[nb] = sub[name]

# 3) move each notebook into its folder (idempotent)
items = {it["displayName"]: it for it in list_items() if it.get("type") == "Notebook"}
for nb, fid in target.items():
    it = items.get(nb)
    if not it:
        log(f"WARN notebook not found in workspace: {nb}")
        continue
    if (it.get("folderId") or None) == fid:
        log(f"already placed: {nb}")
        continue
    r = move_item(it["id"], fid)
    if r.status_code not in (200, 201, 202):
        log(f"move {nb} failed: {r.status_code} {r.text}")
        sys.exit(1)
    log(f"moved: {nb} -> {fid}")

# 4) verify — print the resulting layout
time.sleep(3)
fname = {f["id"]: f["displayName"] for f in list_folders()}
fparent = {f["id"]: f.get("parentFolderId") for f in list_folders()}


def path_of(folder_id):
    if not folder_id:
        return "(root)"
    parent = fparent.get(folder_id)
    pre = (path_of(parent) + "/") if parent else ""
    return pre + fname.get(folder_id, "?")


log("=== final workspace notebook layout ===")
for it in sorted(list_items(), key=lambda x: x.get("displayName", "")):
    if it.get("type") == "Notebook":
        log(f"  {path_of(it.get('folderId'))}/{it['displayName']}")
