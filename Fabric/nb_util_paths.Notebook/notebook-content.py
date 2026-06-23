# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": { "name": "synapse_pyspark" },
# META   "dependencies": {}
# META }

# CELL ********************

# nb_util_paths — %run this notebook to load mxfabric.paths classes into the session.
# SOURCE OF TRUTH: src/mxfabric/paths.py. Do NOT edit here; edit the module and
# re-sync (tests/test_notebook_sync.py enforces equality).

# >>> MXFABRIC:paths START
from __future__ import annotations

import json
import os
from typing import Dict, Optional, Tuple


class LakehouseRegistry:
    """Maps a logical lakehouse name to its (workspace_id, lakehouse_id) GUIDs."""

    def __init__(self, mapping: Optional[Dict[str, Tuple[str, str]]] = None) -> None:
        self.mapping: Dict[str, Tuple[str, str]] = dict(mapping) if mapping else {}

    @classmethod
    def from_env(cls) -> "LakehouseRegistry":
        """Build from env var FABRIC_LAKEHOUSE_MAPPING (JSON {name:{workspace_id,lakehouse_id}})."""
        raw = os.environ.get("FABRIC_LAKEHOUSE_MAPPING")
        if not raw:
            return cls()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return cls()
        mapping: Dict[str, Tuple[str, str]] = {}
        for name, info in parsed.items():
            mapping[name] = (info["workspace_id"], info["lakehouse_id"])
        return cls(mapping)

    def register(self, name: str, workspace_id: str, lakehouse_id: str) -> None:
        self.mapping[name] = (workspace_id, lakehouse_id)

    def get(self, name: str) -> Tuple[str, str]:
        if name not in self.mapping:
            raise ValueError(
                f"Lakehouse '{name}' not registered. Set Spark conf "
                f"'mxdata.lakehouse.{name}'='workspace_id,lakehouse_id' or env "
                f"FABRIC_LAKEHOUSE_MAPPING, or call register()."
            )
        return self.mapping[name]


class StoragePathFactory:
    """Generates OneLake (Fabric) or local file paths for the medallion layers."""

    LAYER_LAKEHOUSE: Dict[str, str] = {
        "raw": "bronze_lakehouse",
        "bronze": "bronze_lakehouse",
        "silver": "silver_lakehouse",
        "gold": "gold_lakehouse",
    }

    def __init__(self, registry: LakehouseRegistry, platform: str = "fabric") -> None:
        if platform not in ("fabric", "local"):
            raise ValueError(f"Invalid platform '{platform}'. Expected 'fabric' or 'local'.")
        self.registry = registry
        self.platform = platform

    def delta_table_path(self, layer: str, schema: str, table: str) -> str:
        if layer not in self.LAYER_LAKEHOUSE:
            raise ValueError(f"Invalid layer '{layer}'. Expected one of {list(self.LAYER_LAKEHOUSE)}.")
        lakehouse_name = self.LAYER_LAKEHOUSE[layer]
        if self.platform == "local":
            return f"file:///tmp/onelake/{lakehouse_name}/Tables/{schema}/{table}/"
        workspace_id, lakehouse_id = self.registry.get(lakehouse_name)
        return self.construct_abfss_path(workspace_id, lakehouse_id, "Tables", schema, table)

    def raw_file_path(self, schema: str, table: str, year: int, month: int, day: int) -> str:
        if self.platform == "local":
            return (
                f"file:///tmp/onelake/bronze_lakehouse/Files/raw/{schema}/{table}/"
                f"year={year}/month={month}/day={day}/"
            )
        workspace_id, lakehouse_id = self.registry.get(self.LAYER_LAKEHOUSE["raw"])
        return self.construct_abfss_path(
            workspace_id, lakehouse_id, "Files",
            "raw", schema, table, f"year={year}", f"month={month}", f"day={day}",
        )

    @staticmethod
    def construct_abfss_path(workspace_id: str, lakehouse_id: str, path_type: str, *path_parts: str) -> str:
        if path_type not in ("Files", "Tables"):
            raise ValueError(f"Invalid path_type '{path_type}'. Expected 'Files' or 'Tables'.")
        base = f"abfss://{workspace_id}@onelake.dfs.fabric.microsoft.com/{lakehouse_id}/{path_type}"
        if path_parts:
            parts = "/".join(str(p).strip("/") for p in path_parts)
            return f"{base}/{parts}/"
        return f"{base}/"
# >>> MXFABRIC:paths END

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
