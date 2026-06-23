import pytest

from mxfabric.paths import LakehouseRegistry, StoragePathFactory


def test_registry_register_and_get():
    reg = LakehouseRegistry()
    reg.register("bronze_lakehouse", "ws-123", "lh-456")
    assert reg.get("bronze_lakehouse") == ("ws-123", "lh-456")


def test_registry_get_missing_raises():
    reg = LakehouseRegistry()
    with pytest.raises(ValueError):
        reg.get("nope")


def test_registry_from_env(monkeypatch):
    monkeypatch.setenv(
        "FABRIC_LAKEHOUSE_MAPPING",
        '{"bronze_lakehouse": {"workspace_id": "ws-1", "lakehouse_id": "lh-1"}}',
    )
    reg = LakehouseRegistry.from_env()
    assert reg.get("bronze_lakehouse") == ("ws-1", "lh-1")


def test_registry_from_env_unset(monkeypatch):
    monkeypatch.delenv("FABRIC_LAKEHOUSE_MAPPING", raising=False)
    assert LakehouseRegistry.from_env().mapping == {}


@pytest.mark.parametrize(
    "layer,lh",
    [("bronze", "bronze_lakehouse"), ("silver", "silver_lakehouse"), ("gold", "gold_lakehouse")],
)
def test_fabric_delta_table_path(layer, lh):
    reg = LakehouseRegistry({lh: ("ws-9", f"id-{layer}")})
    f = StoragePathFactory(reg, platform="fabric")
    assert (
        f.delta_table_path(layer, "sch", "tbl")
        == f"abfss://ws-9@onelake.dfs.fabric.microsoft.com/id-{layer}/Tables/sch/tbl/"
    )


def test_fabric_raw_file_path():
    reg = LakehouseRegistry({"bronze_lakehouse": ("ws-9", "id-b")})
    f = StoragePathFactory(reg, platform="fabric")
    assert (
        f.raw_file_path("sch", "tbl", 2026, 6, 22)
        == "abfss://ws-9@onelake.dfs.fabric.microsoft.com/id-b/Files/raw/sch/tbl/year=2026/month=6/day=22/"
    )


def test_local_delta_table_path_needs_no_registry():
    f = StoragePathFactory(LakehouseRegistry(), platform="local")
    assert f.delta_table_path("silver", "sch", "tbl") == "file:///tmp/onelake/silver_lakehouse/Tables/sch/tbl/"


def test_local_raw_file_path_needs_no_registry():
    f = StoragePathFactory(LakehouseRegistry(), platform="local")
    assert (
        f.raw_file_path("sch", "tbl", 2026, 6, 22)
        == "file:///tmp/onelake/bronze_lakehouse/Files/raw/sch/tbl/year=2026/month=6/day=22/"
    )


def test_invalid_platform_raises():
    with pytest.raises(ValueError):
        StoragePathFactory(LakehouseRegistry(), platform="databricks")


def test_invalid_layer_raises():
    f = StoragePathFactory(LakehouseRegistry(), platform="local")
    with pytest.raises(ValueError):
        f.delta_table_path("platinum", "sch", "tbl")


def test_invalid_path_type_raises():
    with pytest.raises(ValueError):
        StoragePathFactory.construct_abfss_path("ws", "lh", "Bogus", "a")
