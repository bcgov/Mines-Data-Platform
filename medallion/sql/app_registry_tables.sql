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

-- ── per-phase error logs (bronze / silver / gold) ────────────────────────────
IF NOT EXISTS (SELECT 1 FROM sys.tables t JOIN sys.schemas s ON t.schema_id=s.schema_id WHERE s.name='app' AND t.name='error_log_bronze')
BEGIN
    CREATE TABLE [app].[error_log_bronze] (
        [error_id]      bigint        NOT NULL,
        [run_id]        varchar(100)  NULL,
        [entity]        varchar(200)  NULL,
        [target_table]  varchar(200)  NULL,
        [error_message] varchar(max)  NOT NULL,
        [error_context] varchar(max)  NULL,
        [stack_trace]   varchar(max)  NULL,
        [created_date]  datetime2(6)  NOT NULL
    );
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.tables t JOIN sys.schemas s ON t.schema_id=s.schema_id WHERE s.name='app' AND t.name='error_log_silver')
BEGIN
    CREATE TABLE [app].[error_log_silver] (
        [error_id]      bigint        NOT NULL,
        [run_id]        varchar(100)  NULL,
        [entity]        varchar(200)  NULL,
        [target_table]  varchar(200)  NULL,
        [error_message] varchar(max)  NOT NULL,
        [error_context] varchar(max)  NULL,
        [stack_trace]   varchar(max)  NULL,
        [created_date]  datetime2(6)  NOT NULL
    );
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.tables t JOIN sys.schemas s ON t.schema_id=s.schema_id WHERE s.name='app' AND t.name='error_log_gold')
BEGIN
    CREATE TABLE [app].[error_log_gold] (
        [error_id]      bigint        NOT NULL,
        [run_id]        varchar(100)  NULL,
        [entity]        varchar(200)  NULL,
        [target_table]  varchar(200)  NULL,
        [error_message] varchar(max)  NOT NULL,
        [error_context] varchar(max)  NULL,
        [stack_trace]   varchar(max)  NULL,
        [created_date]  datetime2(6)  NOT NULL
    );
END;
GO

-- ── verify ───────────────────────────────────────────────────────────────────
SELECT t.name AS table_name
FROM sys.tables t JOIN sys.schemas s ON t.schema_id=s.schema_id
WHERE s.name='app' AND t.name IN
    ('object_registry','field_registry','transform_registry','dq_rule','dq_result',
     'error_log_bronze','error_log_silver','error_log_gold')
ORDER BY t.name;
GO
