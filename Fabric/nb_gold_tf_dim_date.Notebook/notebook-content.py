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

# ════════════════════════════════════════════════════════════════════════════
# nb_gold_tf_dim_date  —  Generated calendar dimension (no source DB needed)
#
# Generates a date spine from START_DATE to END_DATE and writes gold.dim_date.
# Includes BC Government fiscal year logic (FY starts April 1).
#
# Columns produced:
#   Date_SK           INT        Surrogate key YYYYMMDD (e.g. 20260701)
#   full_date         DATE       Calendar date
#   year              INT        Calendar year
#   month             INT        Calendar month (1-12)
#   month_name        STRING     e.g. "July"
#   month_short       STRING     e.g. "Jul"
#   quarter           INT        Calendar quarter (1-4)
#   day_of_month      INT        Day within month (1-31)
#   day_of_week       INT        Day of week (1=Monday ... 7=Sunday)
#   day_name          STRING     e.g. "Monday"
#   is_weekend        BOOLEAN    True for Saturday/Sunday
#   fiscal_year       INT        BC fiscal year start year (e.g. 2025 for FY2025/26)
#   fiscal_year_label STRING     e.g. "FY2025/26"
#   fiscal_month      INT        Fiscal month number (1=April ... 12=March)
#   fiscal_quarter    INT        Fiscal quarter (1=Apr-Jun ... 4=Jan-Mar)
# ════════════════════════════════════════════════════════════════════════════

from pyspark.sql import functions as F
from pyspark.sql.types import DateType

# Date range — covers all source data (MDS goes back to ~2000) plus future planning
START_DATE = "2000-01-01"
END_DATE   = "2035-12-31"

TARGET_TABLE = "gold.dim_date"

# METADATA ********************
# META { "language": "python", "language_group": "synapse_pyspark" }

# CELL ********************

# Generate date spine using sequence of days
df = spark.sql(f"""
    SELECT sequence(
        TO_DATE('{START_DATE}'),
        TO_DATE('{END_DATE}'),
        INTERVAL 1 DAY
    ) AS date_array
""").select(F.explode("date_array").alias("full_date"))

# METADATA ********************
# META { "language": "python", "language_group": "synapse_pyspark" }

# CELL ********************

# Derive all calendar and BC fiscal year columns
df = df.select(
    # Surrogate key — YYYYMMDD integer
    F.date_format("full_date", "yyyyMMdd").cast("int").alias("Date_SK"),
    F.col("full_date"),

    # Calendar columns
    F.year("full_date").alias("year"),
    F.month("full_date").alias("month"),
    F.date_format("full_date", "MMMM").alias("month_name"),
    F.date_format("full_date", "MMM").alias("month_short"),
    F.quarter("full_date").alias("quarter"),
    F.dayofmonth("full_date").alias("day_of_month"),
    # ISO day of week: 1=Monday ... 7=Sunday  (Spark default is 1=Sunday, convert)
    ((F.dayofweek("full_date") + 5) % 7 + 1).alias("day_of_week"),
    F.date_format("full_date", "EEEE").alias("day_name"),
    F.date_format("full_date", "EEE").alias("day_short"),
    F.when(F.dayofweek("full_date").isin(1, 7), True).otherwise(False).alias("is_weekend"),

    # BC fiscal year — starts April 1
    # If month >= 4 then fiscal_year = calendar year, else fiscal_year = calendar year - 1
    F.when(F.month("full_date") >= 4,
           F.year("full_date")
    ).otherwise(
           F.year("full_date") - 1
    ).alias("fiscal_year"),

    # Fiscal month: April=1, May=2, ..., March=12
    ((F.month("full_date") + 8) % 12 + 1).alias("fiscal_month"),

    # Fiscal quarter: Q1=Apr-Jun, Q2=Jul-Sep, Q3=Oct-Dec, Q4=Jan-Mar
    F.when(F.month("full_date").isin(4, 5, 6), 1)
     .when(F.month("full_date").isin(7, 8, 9), 2)
     .when(F.month("full_date").isin(10, 11, 12), 3)
     .otherwise(4).alias("fiscal_quarter"),
)

# Add fiscal year label — e.g. "FY2025/26"
df = df.withColumn(
    "fiscal_year_label",
    F.concat(
        F.lit("FY"),
        F.col("fiscal_year").cast("string"),
        F.lit("/"),
        F.lpad(((F.col("fiscal_year") + 1) % 100).cast("string"), 2, "0")
    )
)

# Add fiscal month label — e.g. "Apr 2025 (FY Q1)"
df = df.withColumn(
    "fiscal_month_label",
    F.concat(F.col("month_short"), F.lit(" "), F.col("year").cast("string"))
)

# Rolling "last 6 fiscal years" label (current FY + 5 prior; NULL otherwise) — used by the NoW
# Permitting model (dim_date.fiscal_year_last6). Used to be an ALTER/UPDATE inside
# nb_build_fact_now_permit; generated here so a dim_date rebuild never loses it.
_today = spark.sql("SELECT year(current_date()) AS y, month(current_date()) AS m").first()
CURRENT_FY = _today.y if _today.m >= 4 else _today.y - 1
df = df.withColumn("fiscal_year_last6",
                   F.when(F.col("fiscal_year").between(CURRENT_FY - 5, CURRENT_FY), F.col("fiscal_year_label")))

# Numeric sort key for fiscal_month_label (e.g. 202501 = Apr 2025, 1st month of FY2025/26). The semantic models sort
# the month axis by this column; it used to be added by hand (ALTER TABLE) in July — now scripted.
df = df.withColumn("fiscal_year_month_key", (F.col("fiscal_year") * 100 + F.col("fiscal_month")).cast("int"))

print(f"Generated {df.count()} date rows from {START_DATE} to {END_DATE}")
df.show(5)

# METADATA ********************
# META { "language": "python", "language_group": "synapse_pyspark" }

# CELL ********************

# Drop and recreate — dim_date is always fully regenerated (no incremental needed)
spark.sql(f"DROP TABLE IF EXISTS {TARGET_TABLE}")

(df.write
   .format("delta")
   .mode("overwrite")
   .option("overwriteSchema", "true")
   .saveAsTable(TARGET_TABLE))

print(f"Written {df.count()} rows to {TARGET_TABLE}")
print("Sample fiscal year check:")
spark.sql("""
    SELECT full_date, fiscal_year, fiscal_year_label, fiscal_month, fiscal_quarter
    FROM gold.dim_date
    WHERE full_date IN ('2026-04-01', '2026-06-30', '2026-07-01', '2027-03-31')
    ORDER BY full_date
""").show()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
