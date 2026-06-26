"""Print a Fabric job instance (incl. failureReason). Env: WORKSPACE_ID, ITEM_ID, INSTANCE_ID."""
import json
import os
import sys

import requests

BASE = "https://api.fabric.microsoft.com/v1"
H = {"Authorization": f"Bearer {os.environ['FABRIC_TOKEN']}"}
r = requests.get(f"{BASE}/workspaces/{os.environ['WORKSPACE_ID']}/items/"
                 f"{os.environ['ITEM_ID']}/jobs/instances/{os.environ['INSTANCE_ID']}", headers=H)
print(json.dumps(r.json(), indent=1)[:6000], file=sys.stderr)
