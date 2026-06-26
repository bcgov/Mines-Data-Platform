# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": { "name": "synapse_pyspark" },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "5e43f78b-2156-4469-980e-bffda0295fac",
# META       "default_lakehouse_name": "lh_gold",
# META       "default_lakehouse_workspace_id": "8f380f88-5ce5-48d1-9fa5-fbbfbe2685a0",
# META       "known_lakehouses": [ { "id": "5e43f78b-2156-4469-980e-bffda0295fac" } ]
# META     },
# META     "warehouse": {
# META       "default_warehouse": "dad1e7ab-adc2-bd51-408b-33e59ed9a608",
# META       "known_warehouses": [ { "id": "dad1e7ab-adc2-bd51-408b-33e59ed9a608", "type": "Datawarehouse" } ]
# META     }
# META   }
# META }

# CELL ********************

%run nb_util_gold

# METADATA ********************

# META { "language": "python", "language_group": "synapse_pyspark" }

# CELL ********************

# nb_gold_test — purposely exercises the UPDATE and SOFT-DELETE paths of build_dimension and
# build_fact by mutating the materialized stg tables directly, then asserting the gold outcome.
# Mutates real gold tables, then RESTORES them at the end (rebuild stg from silver + rebuild gold).
# Results are written to warehouse app.gold_test_log so they're readable via SQL.
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType
from delta.tables import DeltaTable
from notebookutils import mssparkutils

WAREHOUSE = "mines-data-platform-fabwh1"
SENTINEL = "GOLD_TEST_UPDATE"
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInWrite", "LEGACY")
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInRead", "LEGACY")
spark.conf.set("spark.sql.parquet.int96RebaseModeInWrite", "LEGACY")
spark.conf.set("spark.sql.parquet.int96RebaseModeInRead", "LEGACY")

results = []
def record(test, entity, passed, detail):
    results.append((test, entity, "PASS" if passed else "FAIL", str(detail)[:4000]))
    print(f"[{'PASS' if passed else 'FAIL'}] {test} ({entity}): {detail}")

TRANSFORMS = ["nb_gold_tf_dim_permit", "nb_gold_tf_fact_permit_amendment"]
def rebuild_stg():
    acts = [{"name": nb, "path": nb, "args": {}, "dependencies": []} for nb in TRANSFORMS]
    mssparkutils.notebook.runMultiple({"activities": acts, "timeoutInSeconds": 1800, "concurrency": 0})

def build_dim():
    return build_dimension("gold.dim_permit", "stg.dim_permit", 2, "Permit_SK", "permit_id", load_mode="full")
def build_ft():
    return build_fact("gold.fact_permit_amendment", "stg.fact_permit_amendment", "upsert", "full", "permit_amendment_id")

def pick_str_col(table, exclude):
    return next(c for c, t in spark.table(table).dtypes if t == "string" and c not in exclude)

# Clean baseline: stg = full snapshot of silver, gold reconciled to it.
print("=== baseline: rebuild stg + gold ===")
rebuild_stg()
print("dim:", build_dim())
print("fact:", build_ft())

# METADATA ********************

# META { "language": "python", "language_group": "synapse_pyspark" }

# CELL ********************

# ── DIMENSION test (gold.dim_permit, type2 / full) ───────────────────────────
try:
    ids = [r["permit_id"] for r in spark.table("stg.dim_permit").select("permit_id").limit(4).collect()]
    dim_upd, dim_del = ids[:2], ids[2:4]
    dim_col = pick_str_col("stg.dim_permit", {"permit_id"})
    print(f"dim test: col={dim_col} update_keys={dim_upd} delete_keys={dim_del}")

    sdt = DeltaTable.forName(spark, "stg.dim_permit")
    sdt.update(F.col("permit_id").isin(dim_upd), {dim_col: F.lit(SENTINEL)})  # change values
    sdt.delete(F.col("permit_id").isin(dim_del))                              # exclude records
    print("after mutate -> build_dimension:", build_dim())

    g = spark.table("gold.dim_permit")
    cur = g.filter(F.col("dl_iscurrent") == True)  # noqa: E712

    # UPDATE: the current SCD2 version now holds the sentinel, and an expired prior version exists
    got = [r[dim_col] for r in cur.filter(F.col("permit_id").isin(dim_upd)).select(dim_col).collect()]
    expired = g.filter(F.col("permit_id").isin(dim_upd) & (F.col("dl_iscurrent") == False)).count()  # noqa: E712
    upd_ok = len(got) == len(dim_upd) and all(v == SENTINEL for v in got) and expired >= len(dim_upd)
    record("dim_update", "gold.dim_permit", upd_ok,
           f"current values={got} (want all '{SENTINEL}'), expired prior versions={expired} (want>={len(dim_upd)})")

    # SOFT-DELETE: no current row for deleted keys; tombstone has dl_isdeleted=true & dl_iscurrent=false
    del_cur = cur.filter(F.col("permit_id").isin(dim_del)).count()
    del_tomb = g.filter(F.col("permit_id").isin(dim_del) & (F.col("dl_isdeleted") == True)
                        & (F.col("dl_iscurrent") == False)).count()  # noqa: E712
    del_ok = del_cur == 0 and del_tomb >= len(dim_del)
    record("dim_soft_delete", "gold.dim_permit", del_ok,
           f"current rows for deleted keys={del_cur} (want 0), tombstones={del_tomb} (want>={len(dim_del)})")
except Exception as e:
    import traceback
    record("dim_test", "gold.dim_permit", False, f"EXCEPTION: {e}\n{traceback.format_exc()}")

# METADATA ********************

# META { "language": "python", "language_group": "synapse_pyspark" }

# CELL ********************

# ── FACT test (gold.fact_permit_amendment, upsert / full) ────────────────────
try:
    fids = [r["permit_amendment_id"] for r in
            spark.table("stg.fact_permit_amendment").select("permit_amendment_id").limit(4).collect()]
    fact_upd, fact_del = fids[:2], fids[2:4]
    fact_col = pick_str_col("stg.fact_permit_amendment", {"permit_amendment_id", "permit_id", "Permit_SK"})
    print(f"fact test: col={fact_col} update_keys={fact_upd} delete_keys={fact_del}")

    sft = DeltaTable.forName(spark, "stg.fact_permit_amendment")
    sft.update(F.col("permit_amendment_id").isin(fact_upd), {fact_col: F.lit(SENTINEL)})  # change values
    sft.delete(F.col("permit_amendment_id").isin(fact_del))                               # exclude records
    print("after mutate -> build_fact:", build_ft())

    gf = spark.table("gold.fact_permit_amendment")

    # UPDATE: upsert updates the row in place to the sentinel, still live (dl_isdeleted=false)
    upd_rows = gf.filter(F.col("permit_amendment_id").isin(fact_upd))
    gotf = [r[fact_col] for r in upd_rows.select(fact_col).collect()]
    live = upd_rows.filter(F.col("dl_isdeleted") == False).count()  # noqa: E712
    fupd_ok = len(gotf) == len(fact_upd) and all(v == SENTINEL for v in gotf) and live == len(fact_upd)
    record("fact_update", "gold.fact_permit_amendment", fupd_ok,
           f"values={gotf} (want all '{SENTINEL}'), live rows={live} (want {len(fact_upd)})")

    # SOFT-DELETE: keys absent from the full source are flagged dl_isdeleted=true (row retained)
    fdel_tomb = gf.filter(F.col("permit_amendment_id").isin(fact_del) & (F.col("dl_isdeleted") == True)).count()  # noqa: E712
    fdel_live = gf.filter(F.col("permit_amendment_id").isin(fact_del) & (F.col("dl_isdeleted") == False)).count()  # noqa: E712
    fdel_ok = fdel_tomb >= len(fact_del) and fdel_live == 0
    record("fact_soft_delete", "gold.fact_permit_amendment", fdel_ok,
           f"tombstones={fdel_tomb} (want>={len(fact_del)}), still-live deleted={fdel_live} (want 0)")
except Exception as e:
    import traceback
    record("fact_test", "gold.fact_permit_amendment", False, f"EXCEPTION: {e}\n{traceback.format_exc()}")

# METADATA ********************

# META { "language": "python", "language_group": "synapse_pyspark" }

# CELL ********************

# ── RESTORE gold to a clean state (rebuild stg from silver, reconcile gold) ───
try:
    print("=== restore ===")
    rebuild_stg()
    print("dim:", build_dim())
    print("fact:", build_ft())
    # sanity: previously-deleted keys are live again
    try:
        dl = spark.table("gold.dim_permit").filter(
            F.col("permit_id").isin(dim_del) & (F.col("dl_iscurrent") == True)).count()  # noqa: E712,F821
        record("restore_dim", "gold.dim_permit", dl >= len(dim_del), f"deleted dim keys live again={dl}")  # noqa: F821
    except Exception:
        pass
    try:
        fl = spark.table("gold.fact_permit_amendment").filter(
            F.col("permit_amendment_id").isin(fact_del) & (F.col("dl_isdeleted") == False)).count()  # noqa: E712,F821
        record("restore_fact", "gold.fact_permit_amendment", fl >= len(fact_del), f"deleted fact keys live again={fl}")  # noqa: F821
    except Exception:
        pass
except Exception as e:
    import traceback
    record("restore", "gold", False, f"EXCEPTION: {e}\n{traceback.format_exc()}")

# METADATA ********************

# META { "language": "python", "language_group": "synapse_pyspark" }

# CELL ********************

# Persist results to the warehouse for SQL verification.
sch = StructType([
    StructField("test_name", StringType()), StructField("entity", StringType()),
    StructField("status", StringType()), StructField("detail", StringType()),
])
from com.microsoft.spark.fabric import Constants  # noqa: F401
(spark.createDataFrame(results, sch).withColumn("run_ts", F.current_timestamp())
    .write.mode("overwrite").option("overwriteSchema", "true").synapsesql(f"{WAREHOUSE}.app.gold_test_log"))

passed = sum(1 for r in results if r[2] == "PASS")
print(f"\nGOLD TEST DONE | pass={passed} fail={len(results)-passed}")
for r in results:
    print(" ", r[2], r[0], "-", r[3][:160])

# METADATA ********************

# META { "language": "python", "language_group": "synapse_pyspark" }
