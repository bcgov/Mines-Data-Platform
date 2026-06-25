-- =============================================================================
-- medallion/sql/app_registry_tables.sql
-- Fabric Warehouse-compatible DDL for the medallion app.* control/registry tables.
-- Idempotent (safe to re-run). Deployed directly to the workspace warehouse via SPN.
--
-- Fabric Warehouse T-SQL constraints respected (verified empirically 2026-06-23):
--   NO IDENTITY, NO DEFAULT, NO CHECK, NO computed columns, and NO PRIMARY KEY /
--   constraint keyword in CREATE TABLE (error 24584). Surrogate *_id columns are
--   populated by the loading notebooks (row_number()+max); keys are documented, not enforced.
-- =============================================================================

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'app')
    EXEC('CREATE SCHEMA [app]');
GO

-- ── object_registry (bronze/silver entities) ────────────────────────────────
IF NOT EXISTS (SELECT 1 FROM sys.tables t JOIN sys.schemas s ON t.schema_id=s.schema_id WHERE s.name='app' AND t.name='object_registry')
BEGIN
    CREATE TABLE [app].[object_registry] (
        [object_id]        bigint        NOT NULL,
        [source_entity]    varchar(200)  NOT NULL,
        [bronze_schema]    varchar(50)   NOT NULL,
        [bronze_table]     varchar(200)  NOT NULL,
        [silver_schema]    varchar(50)   NOT NULL,
        [silver_table]     varchar(200)  NOT NULL,
        [load_type]        varchar(20)   NOT NULL,
        [primary_key]      varchar(400)  NULL,
        [watermark_column] varchar(200)  NULL,
        [is_active]        bit           NOT NULL,
        [load_group]       int           NOT NULL,
        [priority]         int           NOT NULL,
        [dependency_on]    varchar(200)  NULL,
        [created_date]     datetime2(6)  NOT NULL,
        [created_by]       varchar(200)  NOT NULL,
        [modified_date]    datetime2(6)  NOT NULL,
        [modified_by]      varchar(200)  NOT NULL
    );
END;
GO

-- ── field_registry (column conformance) ─────────────────────────────────────
IF NOT EXISTS (SELECT 1 FROM sys.tables t JOIN sys.schemas s ON t.schema_id=s.schema_id WHERE s.name='app' AND t.name='field_registry')
BEGIN
    CREATE TABLE [app].[field_registry] (
        [field_id]        bigint        NOT NULL,
        [object_id]       bigint        NOT NULL,
        [entity]          varchar(200)  NOT NULL,
        [column_name]     varchar(200)  NOT NULL,
        [spark_type]      varchar(100)  NOT NULL,
        [nullable]        bit           NOT NULL,
        [is_pk]           bit           NOT NULL,
        [include_in_load] bit           NOT NULL,
        [pii_type]        varchar(50)   NULL,
        [ordinal]         int           NOT NULL,
        [created_date]    datetime2(6)  NOT NULL,
        [created_by]      varchar(200)  NOT NULL,
        [modified_date]   datetime2(6)  NOT NULL,
        [modified_by]     varchar(200)  NOT NULL
    );
END;
GO

-- ── transform_registry (gold dim/fact) ──────────────────────────────────────
IF NOT EXISTS (SELECT 1 FROM sys.tables t JOIN sys.schemas s ON t.schema_id=s.schema_id WHERE s.name='app' AND t.name='transform_registry')
BEGIN
    CREATE TABLE [app].[transform_registry] (
        [transform_id]   bigint        NOT NULL,
        [transform_name] varchar(200)  NOT NULL,
        [source_view]    varchar(200)  NOT NULL,
        [transform_type] varchar(20)   NOT NULL,
        [scd_type]       int           NULL,
        [surrogate_key]  varchar(200)  NULL,
        [natural_keys]   varchar(400)  NULL,
        [load_group]     int           NOT NULL,
        [load_order]     int           NOT NULL,
        [is_active]      bit           NOT NULL,
        [created_date]   datetime2(6)  NOT NULL,
        [created_by]     varchar(200)  NOT NULL,
        [modified_date]  datetime2(6)  NOT NULL,
        [modified_by]    varchar(200)  NOT NULL
    );
END;
GO

-- ── dq_rule (data-quality rules) ─────────────────────────────────────────────
IF NOT EXISTS (SELECT 1 FROM sys.tables t JOIN sys.schemas s ON t.schema_id=s.schema_id WHERE s.name='app' AND t.name='dq_rule')
BEGIN
    CREATE TABLE [app].[dq_rule] (
        [rule_id]       bigint        NOT NULL,
        [entity]        varchar(200)  NOT NULL,
        [column_name]   varchar(200)  NULL,
        [rule_type]     varchar(50)   NOT NULL,
        [params]        varchar(max)  NULL,
        [severity]      varchar(20)   NOT NULL,
        [is_active]     bit           NOT NULL,
        [created_date]  datetime2(6)  NOT NULL,
        [created_by]    varchar(200)  NOT NULL,
        [modified_date] datetime2(6)  NOT NULL,
        [modified_by]   varchar(200)  NOT NULL
    );
END;
GO

-- ── dq_result (DQ run log) ───────────────────────────────────────────────────
IF NOT EXISTS (SELECT 1 FROM sys.tables t JOIN sys.schemas s ON t.schema_id=s.schema_id WHERE s.name='app' AND t.name='dq_result')
BEGIN
    CREATE TABLE [app].[dq_result] (
        [result_id]      bigint        NOT NULL,
        [run_id]         varchar(100)  NOT NULL,
        [entity]         varchar(200)  NOT NULL,
        [rule_name]      varchar(200)  NOT NULL,
        [rows_evaluated] bigint        NOT NULL,
        [rows_failed]    bigint        NOT NULL,
        [status]         varchar(20)   NOT NULL,
        [run_ts]         datetime2(6)  NOT NULL
    );
END;
GO

-- ── unified error log (all layers via the [layer] column) ────────────────────
-- Supersedes the per-phase error_log_* tables. pipeline_log owns run/pipeline
-- logging; app.error_log owns errors for bronze | silver | gold | ingest.
DROP TABLE IF EXISTS [app].[error_log_bronze];
GO
DROP TABLE IF EXISTS [app].[error_log_silver];
GO
DROP TABLE IF EXISTS [app].[error_log_gold];
GO

-- Centralized error log for BOTH pipeline and notebook errors.
-- error_id is a GUID (varchar) so ADF (newid()) and notebooks (uuid4) can each mint it
-- without IDENTITY (unsupported by Fabric Warehouse).
-- The error_number/severity/state/procedure/line columns are the SQL Server TRY/CATCH
-- error fields (ERROR_NUMBER() etc.); unused by the medallion notebooks but retained for
-- other (stored-proc / SQL-based) processes that write into this shared table.
--
-- Migration is layered so existing error rows are preserved where possible:
--  1) DROP only the truly-incompatible pre-unification shape (no [error_code] / had IDENTITY).
--  2) For the current unified shape (has [error_code], missing the SQL TRY/CATCH cols), ADD
--     them in place via ALTER — non-destructive.
--  3) CREATE the full latest shape if the table is absent (fresh deploy or post-drop).
-- All three are idempotent.

-- 1) drop the pre-unification shape (no error_code → had IDENTITY/ADF-only columns, incompatible)
IF EXISTS (SELECT 1 FROM sys.tables t JOIN sys.schemas s ON t.schema_id=s.schema_id WHERE s.name='app' AND t.name='error_log')
   AND NOT EXISTS (
       SELECT 1 FROM sys.columns c
       JOIN sys.tables t  ON c.object_id = t.object_id
       JOIN sys.schemas s ON t.schema_id = s.schema_id
       WHERE s.name='app' AND t.name='error_log' AND c.name='error_code'
   )
BEGIN
    DROP TABLE [app].[error_log];
END;
GO

-- 2) additive: bring the current unified shape up to date without losing rows
IF EXISTS (SELECT 1 FROM sys.tables t JOIN sys.schemas s ON t.schema_id=s.schema_id WHERE s.name='app' AND t.name='error_log')
   AND EXISTS (
       SELECT 1 FROM sys.columns c JOIN sys.tables t ON c.object_id=t.object_id
       JOIN sys.schemas s ON t.schema_id=s.schema_id
       WHERE s.name='app' AND t.name='error_log' AND c.name='error_code'
   )
   AND NOT EXISTS (
       SELECT 1 FROM sys.columns c JOIN sys.tables t ON c.object_id=t.object_id
       JOIN sys.schemas s ON t.schema_id=s.schema_id
       WHERE s.name='app' AND t.name='error_log' AND c.name='error_line'
   )
BEGIN
    ALTER TABLE [app].[error_log] ADD
        [error_number]    int          NULL,
        [error_severity]  int          NULL,
        [error_state]     int          NULL,
        [error_procedure] varchar(200) NULL,
        [error_line]      int          NULL;
END;
GO

-- 3) fresh deploy / post-drop: create the full latest shape
IF NOT EXISTS (SELECT 1 FROM sys.tables t JOIN sys.schemas s ON t.schema_id=s.schema_id WHERE s.name='app' AND t.name='error_log')
BEGIN
    CREATE TABLE [app].[error_log] (
        [error_id]         varchar(36)   NOT NULL,   -- GUID (writer-minted)
        [layer]            varchar(20)   NOT NULL,   -- bronze | silver | gold | ingest
        [log_id]           bigint        NULL,       -- pipeline_log.log_id when triggered by a pipeline (else null)
        [pipeline_name]    varchar(200)  NULL,       -- triggering pipeline name (else null for direct runs)
        [run_id]           varchar(100)  NULL,       -- notebook run id / pipeline RunId
        [entity]           varchar(200)  NULL,
        [target_table]     varchar(200)  NULL,
        [error_message]    varchar(max)  NOT NULL,
        [error_code]       varchar(100)  NULL,       -- ADF error code (null for notebook errors)
        [error_context]    varchar(max)  NULL,
        [stack_trace]      varchar(max)  NULL,
        [created_date]     datetime2(6)  NOT NULL,
        -- SQL Server TRY/CATCH fields for other (stored-proc / SQL-based) writers; trailing
        -- so a fresh CREATE matches the additive-ALTER physical order above.
        [error_number]     int           NULL,       -- ERROR_NUMBER()
        [error_severity]   int           NULL,       -- ERROR_SEVERITY()
        [error_state]      int           NULL,       -- ERROR_STATE()
        [error_procedure]  varchar(200)  NULL,       -- ERROR_PROCEDURE()
        [error_line]       int           NULL        -- ERROR_LINE()
    );
END;
GO

-- ── gold build config: split into gold_build (per-object metadata) + gold_dependency (DAG) ─
-- Supersedes the single app.gold_build_dag. gold_build = one row per gold object (what/how
-- to build); gold_dependency = the DAG edges (build order). Drop the old combined table.
DROP TABLE IF EXISTS [app].[gold_build_dag];
GO

-- gold_build: metadata for each gold table. table_type replaces the old scd_type/fact_type
-- pair with a single enum the builder dispatches on:
--   type1_incremental_dimension : SCD1, partial source — no delete detection
--   type1_full_dimension        : SCD1, complete snapshot — source-absent keys soft-deleted (dl_isdeleted=true)
--   type2_incremental_dimension : SCD2 (history), partial source — no delete detection
--   type2_full_dimension        : SCD2 (history), complete snapshot — source-absent keys soft-expired (dl_isdeleted=true)
--   append_only_fact : insert source rows whose business_keys are new (never update/delete)
--   upsert_fact      : merge on business_keys (update matched + insert new)
--   reload_fact      : full drop+rebuild from source each run (rows absent from source vanish)
-- Only the *_full dimensions check deletes — an incremental source is never complete.
IF NOT EXISTS (SELECT 1 FROM sys.tables t JOIN sys.schemas s ON t.schema_id=s.schema_id WHERE s.name='app' AND t.name='gold_build')
BEGIN
    CREATE TABLE [app].[gold_build] (
        [node_name]               varchar(100)  NOT NULL,   -- unique node id + join key to gold_dependency, e.g. 'dim_permit'
        [gold_object]             varchar(200)  NOT NULL,   -- target table, e.g. 'gold.dim_permit'
        [object_type]             varchar(10)   NOT NULL,   -- DIM | FACT (coarse; reporting)
        [transform_notebook]      varchar(200)  NOT NULL,   -- notebook that materializes the stg table
        [source_table]            varchar(200)  NOT NULL,   -- materialized stg table it produces, e.g. 'stg.dim_permit'
        [table_type]              varchar(30)   NOT NULL,   -- type1_dimension|type2_dimension|append_only_fact|upsert_fact|reload_fact
        [surrogate_key]           varchar(100)  NULL,       -- DIM surrogate, e.g. 'Permit_SK'
        [business_keys]           varchar(400)  NULL,       -- natural/business keys (comma-separated column names)
        [non_historized_columns]  varchar(max)  NULL,       -- DIM SCD2: excluded from change detection (comma list)
        [watermark_column]        varchar(200)  NULL,       -- FACT: optional source-window column for append/upsert
        [last_n_days]             int           NULL,       -- FACT: optional source-window size (days)
        [is_active]               bit           NOT NULL,   -- only active nodes are built
        [created_date]            datetime2(6)  NOT NULL,
        [created_by]              varchar(200)  NOT NULL,
        [modified_date]           datetime2(6)  NOT NULL,
        [modified_by]             varchar(200)  NOT NULL
    );
END;
GO

-- gold_dependency: the DAG. One row per node; depends_on is a comma-separated list of parent
-- node_names (null/empty = root). A node depending on 4 tables lists all 4 here.
IF NOT EXISTS (SELECT 1 FROM sys.tables t JOIN sys.schemas s ON t.schema_id=s.schema_id WHERE s.name='app' AND t.name='gold_dependency')
BEGIN
    CREATE TABLE [app].[gold_dependency] (
        [node_name]      varchar(100)  NOT NULL,   -- child node (FK-style ref to gold_build.node_name)
        [depends_on]     varchar(400)  NULL,       -- parent node_names (comma-separated); null = root
        [created_date]   datetime2(6)  NOT NULL,
        [created_by]     varchar(200)  NOT NULL,
        [modified_date]  datetime2(6)  NOT NULL,
        [modified_by]    varchar(200)  NOT NULL
    );
END;
GO

-- seed v1: dim_permit (SCD2) -> fact_permit_amendment (reload; depends on dim_permit)
IF NOT EXISTS (SELECT 1 FROM [app].[gold_build] WHERE node_name='dim_permit')
    INSERT INTO [app].[gold_build]
        (node_name, gold_object, object_type, transform_notebook, source_table, table_type,
         surrogate_key, business_keys, non_historized_columns, watermark_column, last_n_days,
         is_active, created_date, created_by, modified_date, modified_by)
    VALUES
        ('dim_permit','gold.dim_permit','DIM','nb_gold_tf_dim_permit','stg.dim_permit','type2_full_dimension',
         'Permit_SK','permit_id',NULL,NULL,NULL,1,SYSUTCDATETIME(),'system',SYSUTCDATETIME(),'system');
GO
IF NOT EXISTS (SELECT 1 FROM [app].[gold_build] WHERE node_name='fact_permit_amendment')
    INSERT INTO [app].[gold_build]
        (node_name, gold_object, object_type, transform_notebook, source_table, table_type,
         surrogate_key, business_keys, non_historized_columns, watermark_column, last_n_days,
         is_active, created_date, created_by, modified_date, modified_by)
    VALUES
        ('fact_permit_amendment','gold.fact_permit_amendment','FACT','nb_gold_tf_fact_permit_amendment','stg.fact_permit_amendment','reload_fact',
         NULL,'permit_amendment_id',NULL,NULL,NULL,1,SYSUTCDATETIME(),'system',SYSUTCDATETIME(),'system');
GO

IF NOT EXISTS (SELECT 1 FROM [app].[gold_dependency] WHERE node_name='dim_permit')
    INSERT INTO [app].[gold_dependency] (node_name, depends_on, created_date, created_by, modified_date, modified_by)
    VALUES ('dim_permit', NULL, SYSUTCDATETIME(),'system',SYSUTCDATETIME(),'system');
GO
IF NOT EXISTS (SELECT 1 FROM [app].[gold_dependency] WHERE node_name='fact_permit_amendment')
    INSERT INTO [app].[gold_dependency] (node_name, depends_on, created_date, created_by, modified_date, modified_by)
    VALUES ('fact_permit_amendment', 'dim_permit', SYSUTCDATETIME(),'system',SYSUTCDATETIME(),'system');
GO

-- Migrate the pre-split table_type values to the 4-way dimension enum. dim_permit's stg source
-- is a full snapshot (transform overwrites fully from silver), so type2_full is correct + lets
-- delete handling apply. Idempotent: only touches rows still on an old value.
UPDATE [app].[gold_build] SET table_type='type2_full_dimension', modified_date=SYSUTCDATETIME(), modified_by='system'
 WHERE table_type='type2_dimension';
GO
UPDATE [app].[gold_build] SET table_type='type1_full_dimension', modified_date=SYSUTCDATETIME(), modified_by='system'
 WHERE table_type='type1_dimension';
GO

-- ── verify ───────────────────────────────────────────────────────────────────
SELECT t.name AS table_name
FROM sys.tables t JOIN sys.schemas s ON t.schema_id=s.schema_id
WHERE s.name='app' AND t.name IN
    ('object_registry','field_registry','transform_registry','dq_rule','dq_result','error_log','gold_build','gold_dependency')
ORDER BY t.name;
GO
