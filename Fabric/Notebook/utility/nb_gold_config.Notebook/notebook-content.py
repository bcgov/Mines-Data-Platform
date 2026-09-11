# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "896cd6b0-6cd0-47e5-8438-f50dde9564b8",
# META       "default_lakehouse_name": "mcm_mdp_lh1_dev",
# META       "default_lakehouse_workspace_id": "475a3e70-610e-49ae-be54-dd2c31167535",
# META       "known_lakehouses": [
# META         {
# META           "id": "896cd6b0-6cd0-47e5-8438-f50dde9564b8"
# META         }
# META       ]
# META     }
# META   }
# META }

# CELL ********************

# nb_gold_config — the Gold build plan, kept IN GIT (scripted, same in DEV / TEST / PROD).
# nb_gold_orchestrator runs `%run nb_gold_config`, then:
#   1) runs STANDALONE_NOTEBOOKS (self-contained builders: calendar, lookups, NoW facts)
#   2) runs GOLD_BUILD as a dependency DAG (GOLD_DEPENDENCY), level by level
# Replaces the hand-inserted rows in the old warehouse app.gold_build / app.gold_dependency
# (sources: BC (1)/Notebooks/gold_build_register_*.sql + medallion seed for dim_party).
# The orchestrator also writes this plan to the warehouse (app.gold_build / app.gold_dependency)
# on every run, for visibility only.

# Self-contained builders — write gold.* directly, depend only on silver. Run first, in parallel.
STANDALONE_NOTEBOOKS = [
    "nb_gold_tf_dim_date",            # gold.dim_date (generated calendar, BC fiscal year)
    "nb_gold_dim_inspection_type",    # gold.dim_inspection_type
    "nb_build_fact_now_permit",       # gold.fact_now_permit       (NoW Permitting report)
    "nb_build_fact_now_application",  # gold.fact_now_application  (NoW Received report)
]


def _node(node_name, table_type, load_strategy, surrogate_key=None, business_keys=None,
          non_historized_columns=None, watermark_column=None, last_n_days=None, is_active=True):
    return {
        "node_name": node_name,
        "gold_object": f"gold.{node_name}",
        "object_type": "DIM" if "dimension" in table_type else "FACT",
        "transform_notebook": f"nb_gold_tf_{node_name}",
        "source_table": f"stg.{node_name}",
        "table_type": table_type,          # type1_dimension | type2_dimension | append_fact | upsert_fact | reload_fact
        "load_strategy": load_strategy,    # incremental | full (full = source is a complete snapshot)
        "surrogate_key": surrogate_key,
        "business_keys": business_keys,
        "non_historized_columns": non_historized_columns,
        "watermark_column": watermark_column,
        "last_n_days": last_n_days,
        "is_active": is_active,
    }


GOLD_BUILD = [
    _node("dim_mine", "type2_dimension", "full", "Mine_SK", "mine_guid",
          "latitude,longitude,geom,mine_timezone,number_of_contractors,number_of_mine_employees"),
    _node("dim_party", "type2_dimension", "full", "Party_SK", "party_guid"),
    _node("dim_incident_category", "type1_dimension", "full", "Incident_Category_SK", "mine_incident_category_code"),
    _node("fact_inspection", "upsert_fact", "incremental", business_keys="inspection_id"),
    _node("fact_mine_incident", "upsert_fact", "incremental", business_keys="mine_incident_id"),
    _node("bridge_incident_category", "reload_fact", "full",
          business_keys="mine_incident_id,mine_incident_category_code"),
]

# DAG edges: node -> parent nodes (must finish first). Roots are omitted.
GOLD_DEPENDENCY = {
    "fact_inspection": "dim_mine",
    "fact_mine_incident": "dim_mine,dim_party",   # also reads gold.dim_date (standalone, runs first)
    "bridge_incident_category": "dim_incident_category",
}
print(f"nb_gold_config | standalone={len(STANDALONE_NOTEBOOKS)} dag_nodes={len(GOLD_BUILD)}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
