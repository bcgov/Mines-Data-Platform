-- =============================================================================
-- warehouse_init.sql
-- Initializes the Fabric Warehouse with medallion schemas and app control objects
-- Idempotent: safe to run multiple times
-- =============================================================================

-- =============================================================================
-- SCHEMAS
-- =============================================================================

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'bronze')
    EXEC('CREATE SCHEMA [bronze]');
GO

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'silver')
    EXEC('CREATE SCHEMA [silver]');
GO

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'gold')
    EXEC('CREATE SCHEMA [gold]');
GO

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'app')
    EXEC('CREATE SCHEMA [app]');
GO

-- =============================================================================
-- APP SCHEMA: CONTROL TABLE
--
-- ADF pattern:
--   1. ADF Lookup activity reads active rows from this table
--   2. ForEach iterates over each row
--   3. Inside ForEach, ADF executes source_query via a Copy or Script activity,
--      substituting @{item().from_date} and @{item().to_date} at runtime
--   4. After a successful load, ADF calls UPDATE app.pipeline_control SET
--      last_watermark = @toDate, last_run_status = 'SUCCESS' WHERE control_id = @id
--
-- Source query template example stored in source_query_template:
--   SELECT * FROM dbo.Orders
--   WHERE updated_at >= '@from_date' AND updated_at < '@to_date'
--
-- ADF replaces the @from_date / @to_date tokens using pipeline expressions:
--   @replace(replace(item().source_query_template,
--     '@from_date', formatDateTime(item().from_date, 'yyyy-MM-dd HH:mm:ss')),
--     '@to_date',   formatDateTime(item().to_date,   'yyyy-MM-dd HH:mm:ss'))
-- =============================================================================

IF NOT EXISTS (
    SELECT 1 FROM sys.tables t
    JOIN sys.schemas s ON t.schema_id = s.schema_id
    WHERE s.name = 'app' AND t.name = 'pipeline_control'
)
BEGIN
    CREATE TABLE [app].[pipeline_control] (

        -- ── Identity ────────────────────────────────────────────────────────
        [control_id]              INT             NOT NULL IDENTITY(1,1),
        [pipeline_name]           NVARCHAR(200)   NOT NULL,
        [source_system]           NVARCHAR(100)   NOT NULL,
        [source_entity]           NVARCHAR(200)   NOT NULL,   -- table / endpoint / file pattern

        -- ── Target ──────────────────────────────────────────────────────────
        [target_schema]           NVARCHAR(50)    NOT NULL,
        [target_table]            NVARCHAR(200)   NOT NULL,

        -- ── ADF source query ────────────────────────────────────────────────
        -- Full query template to be executed by ADF.
        -- Use the literal tokens @from_date and @to_date as placeholders.
        -- ADF replaces them at runtime using the from_date / to_date columns.
        --
        -- Example (SQL source):
        --   SELECT id, name, updated_at
        --   FROM dbo.Customers
        --   WHERE updated_at >= '@from_date'
        --     AND updated_at <  '@to_date'
        --
        -- Example (REST source — embed as the query parameter or path):
        --   /api/v1/orders?updatedAfter=@from_date&updatedBefore=@to_date
        [source_query_template]   NVARCHAR(MAX)   NULL,

        -- ── Incremental filter window ────────────────────────────────────────
        -- ADF reads these two columns from the Lookup result and injects them
        -- into source_query_template before executing the copy activity.
        -- For FULL loads these are NULL and the template runs unfiltered.
        [from_date]               DATETIME2       NULL,       -- inclusive lower bound (@from_date)
        [to_date]                 DATETIME2       NULL,       -- exclusive upper bound (@to_date)

        -- ── Watermark tracking ───────────────────────────────────────────────
        -- After a successful run ADF writes the high-watermark back here so the
        -- next run's from_date is derived from it.
        [watermark_column]        NVARCHAR(200)   NULL,       -- source column driving the window
        [last_watermark]          NVARCHAR(500)   NULL,       -- last committed high-watermark value

        -- ── Load behaviour ───────────────────────────────────────────────────
        [load_type]               NVARCHAR(20)    NOT NULL DEFAULT 'INCREMENTAL', -- FULL | INCREMENTAL | CDC
        [is_active]               BIT             NOT NULL DEFAULT 1,
        [load_frequency]          NVARCHAR(50)    NULL,       -- DAILY | HOURLY | ON_DEMAND
        [priority]                INT             NOT NULL DEFAULT 100,           -- lower = runs first
        [dependency_on]           NVARCHAR(200)   NULL,       -- pipeline_name this must wait for

        -- ── Last run outcome (written back by ADF) ───────────────────────────
        [last_run_status]         NVARCHAR(20)    NULL,       -- SUCCESS | FAILED | SKIPPED
        [last_run_date]           DATETIME2       NULL,       -- UTC timestamp of last completed run

        -- ── Audit ────────────────────────────────────────────────────────────
        [created_date]            DATETIME2       NOT NULL DEFAULT SYSUTCDATETIME(),
        [created_by]              NVARCHAR(200)   NOT NULL DEFAULT SYSTEM_USER,
        [modified_date]           DATETIME2       NOT NULL DEFAULT SYSUTCDATETIME(),
        [modified_by]             NVARCHAR(200)   NOT NULL DEFAULT SYSTEM_USER,

        CONSTRAINT [PK_pipeline_control]       PRIMARY KEY ([control_id]),
        CONSTRAINT [UQ_pipeline_control_entity] UNIQUE ([pipeline_name], [source_entity], [target_table]),
        CONSTRAINT [CHK_pipeline_control_load_type]
            CHECK ([load_type] IN ('FULL', 'INCREMENTAL', 'CDC')),
        CONSTRAINT [CHK_pipeline_control_last_run_status]
            CHECK ([last_run_status] IS NULL OR [last_run_status] IN ('SUCCESS', 'FAILED', 'SKIPPED'))
    );
END;
GO

-- =============================================================================
-- APP SCHEMA: LOGGING TABLE
-- ADF writes one row per activity execution via a Script activity or
-- stored procedure call at the start and end of each pipeline run.
-- =============================================================================

IF NOT EXISTS (
    SELECT 1 FROM sys.tables t
    JOIN sys.schemas s ON t.schema_id = s.schema_id
    WHERE s.name = 'app' AND t.name = 'pipeline_log'
)
BEGIN
    CREATE TABLE [app].[pipeline_log] (
        [log_id]              BIGINT         NOT NULL IDENTITY(1,1),
        [run_id]              NVARCHAR(100)  NOT NULL,                  -- ADF pipeline run ID
        [activity_run_id]     NVARCHAR(100)  NULL,                      -- ADF activity run ID
        [pipeline_name]       NVARCHAR(200)  NOT NULL,
        [source_entity]       NVARCHAR(200)  NOT NULL,
        [target_schema]       NVARCHAR(50)   NOT NULL,
        [target_table]        NVARCHAR(200)  NOT NULL,
        [status]              NVARCHAR(20)   NOT NULL DEFAULT 'RUNNING', -- RUNNING | SUCCESS | FAILED | SKIPPED
        [rows_read]           BIGINT         NULL,
        [rows_written]        BIGINT         NULL,
        [rows_skipped]        BIGINT         NULL,
        [from_date]           DATETIME2      NULL,                       -- filter window used for this run
        [to_date]             DATETIME2      NULL,
        [watermark_start]     NVARCHAR(500)  NULL,                       -- watermark at run start
        [watermark_end]       NVARCHAR(500)  NULL,                       -- watermark at run end
        [error_message]       NVARCHAR(MAX)  NULL,
        [error_code]          NVARCHAR(100)  NULL,
        [start_time]          DATETIME2      NOT NULL DEFAULT SYSUTCDATETIME(),
        [end_time]            DATETIME2      NULL,
        [duration_seconds]    AS (DATEDIFF(SECOND, [start_time], [end_time])) PERSISTED,
        [environment]         NVARCHAR(20)   NOT NULL DEFAULT 'dev',
        [triggered_by]        NVARCHAR(200)  NULL,
        [created_date]        DATETIME2      NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT [PK_pipeline_log] PRIMARY KEY ([log_id]),
        CONSTRAINT [CHK_pipeline_log_status]
            CHECK ([status] IN ('RUNNING', 'SUCCESS', 'FAILED', 'SKIPPED'))
    );
END;
GO

-- =============================================================================
-- APP SCHEMA: CONFIGURATION TABLE
-- Key-value store for environment and runtime configuration
-- =============================================================================

IF NOT EXISTS (
    SELECT 1 FROM sys.tables t
    JOIN sys.schemas s ON t.schema_id = s.schema_id
    WHERE s.name = 'app' AND t.name = 'config'
)
BEGIN
    CREATE TABLE [app].[config] (
        [config_id]       INT            NOT NULL IDENTITY(1,1),
        [config_key]      NVARCHAR(200)  NOT NULL,
        [config_value]    NVARCHAR(MAX)  NOT NULL,
        [config_group]    NVARCHAR(100)  NOT NULL DEFAULT 'GENERAL',
        [environment]     NVARCHAR(20)   NOT NULL DEFAULT 'ALL',
        [description]     NVARCHAR(500)  NULL,
        [is_secret]       BIT            NOT NULL DEFAULT 0,
        [is_active]       BIT            NOT NULL DEFAULT 1,
        [created_date]    DATETIME2      NOT NULL DEFAULT SYSUTCDATETIME(),
        [created_by]      NVARCHAR(200)  NOT NULL DEFAULT SYSTEM_USER,
        [modified_date]   DATETIME2      NOT NULL DEFAULT SYSUTCDATETIME(),
        [modified_by]     NVARCHAR(200)  NOT NULL DEFAULT SYSTEM_USER,
        CONSTRAINT [PK_config] PRIMARY KEY ([config_id]),
        CONSTRAINT [UQ_config_key_env] UNIQUE ([config_key], [environment])
    );
END;
GO

-- =============================================================================
-- APP SCHEMA: ERROR LOG TABLE
-- =============================================================================

IF NOT EXISTS (
    SELECT 1 FROM sys.tables t
    JOIN sys.schemas s ON t.schema_id = s.schema_id
    WHERE s.name = 'app' AND t.name = 'error_log'
)
BEGIN
    CREATE TABLE [app].[error_log] (
        [error_id]          BIGINT         NOT NULL IDENTITY(1,1),
        [log_id]            BIGINT         NULL,
        [run_id]            NVARCHAR(100)  NULL,
        [pipeline_name]     NVARCHAR(200)  NULL,
        [error_number]      INT            NULL,
        [error_severity]    INT            NULL,
        [error_state]       INT            NULL,
        [error_procedure]   NVARCHAR(200)  NULL,
        [error_line]        INT            NULL,
        [error_message]     NVARCHAR(MAX)  NOT NULL,
        [error_context]     NVARCHAR(MAX)  NULL,
        [stack_trace]       NVARCHAR(MAX)  NULL,
        [created_date]      DATETIME2      NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT [PK_error_log] PRIMARY KEY ([error_id])
    );
END;
GO

-- =============================================================================
-- APP SCHEMA: SCHEMA REGISTRY
-- =============================================================================

IF NOT EXISTS (
    SELECT 1 FROM sys.tables t
    JOIN sys.schemas s ON t.schema_id = s.schema_id
    WHERE s.name = 'app' AND t.name = 'schema_registry'
)
BEGIN
    CREATE TABLE [app].[schema_registry] (
        [registry_id]     INT            NOT NULL IDENTITY(1,1),
        [schema_name]     NVARCHAR(50)   NOT NULL,
        [layer]           NVARCHAR(50)   NOT NULL,
        [description]     NVARCHAR(500)  NULL,
        [owner]           NVARCHAR(200)  NULL,
        [created_date]    DATETIME2      NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT [PK_schema_registry] PRIMARY KEY ([registry_id]),
        CONSTRAINT [UQ_schema_registry_name] UNIQUE ([schema_name])
    );

    INSERT INTO [app].[schema_registry] ([schema_name], [layer], [description])
    VALUES
        ('bronze', 'RAW',      'Raw ingested data — no transformations applied'),
        ('silver', 'CLEANSED', 'Cleansed and conformed data — business rules applied'),
        ('gold',   'CURATED',  'Curated aggregates and star schema models for reporting'),
        ('app',    'APP',      'Application control objects — logging, config, orchestration');
END;
GO

-- =============================================================================
-- SEED DEFAULT CONFIGURATION VALUES
-- =============================================================================

IF NOT EXISTS (SELECT 1 FROM [app].[config] WHERE [config_key] = 'retention_days_bronze' AND [environment] = 'ALL')
    INSERT INTO [app].[config] ([config_key], [config_value], [config_group], [environment], [description])
    VALUES ('retention_days_bronze', '90', 'RETENTION', 'ALL', 'Days to retain data in bronze layer');

IF NOT EXISTS (SELECT 1 FROM [app].[config] WHERE [config_key] = 'retention_days_silver' AND [environment] = 'ALL')
    INSERT INTO [app].[config] ([config_key], [config_value], [config_group], [environment], [description])
    VALUES ('retention_days_silver', '365', 'RETENTION', 'ALL', 'Days to retain data in silver layer');

IF NOT EXISTS (SELECT 1 FROM [app].[config] WHERE [config_key] = 'retention_days_gold' AND [environment] = 'ALL')
    INSERT INTO [app].[config] ([config_key], [config_value], [config_group], [environment], [description])
    VALUES ('retention_days_gold', '730', 'RETENTION', 'ALL', 'Days to retain data in gold layer');

IF NOT EXISTS (SELECT 1 FROM [app].[config] WHERE [config_key] = 'max_retry_attempts' AND [environment] = 'ALL')
    INSERT INTO [app].[config] ([config_key], [config_value], [config_group], [environment], [description])
    VALUES ('max_retry_attempts', '3', 'ORCHESTRATION', 'ALL', 'Maximum pipeline retry attempts on failure');

IF NOT EXISTS (SELECT 1 FROM [app].[config] WHERE [config_key] = 'alert_on_failure' AND [environment] = 'ALL')
    INSERT INTO [app].[config] ([config_key], [config_value], [config_group], [environment], [description])
    VALUES ('alert_on_failure', 'true', 'ALERTING', 'ALL', 'Send alert notification on pipeline failure');
GO

-- =============================================================================
-- SEED EXAMPLE CONTROL TABLE ROWS
-- Shows the ADF query template pattern with @from_date / @to_date tokens
-- =============================================================================

IF NOT EXISTS (SELECT 1 FROM [app].[pipeline_control] WHERE [pipeline_name] = 'pl_ingest_orders')
    INSERT INTO [app].[pipeline_control] (
        [pipeline_name], [source_system], [source_entity],
        [target_schema], [target_table],
        [load_type], [watermark_column],
        [from_date], [to_date],
        [source_query_template]
    )
    VALUES (
        'pl_ingest_orders',
        'SourceDB',
        'dbo.Orders',
        'bronze',
        'orders',
        'INCREMENTAL',
        'updated_at',
        '2024-01-01 00:00:00',
        SYSUTCDATETIME(),
        'SELECT order_id, customer_id, order_date, total_amount, updated_at
FROM dbo.Orders
WHERE updated_at >= ''@from_date''
  AND updated_at <  ''@to_date'''
    );
GO

-- =============================================================================
-- DONE
-- =============================================================================

SELECT
    s.name          AS schema_name,
    COUNT(t.name)   AS table_count
FROM sys.schemas s
LEFT JOIN sys.tables t ON t.schema_id = s.schema_id
WHERE s.name IN ('bronze', 'silver', 'gold', 'app')
GROUP BY s.name
ORDER BY s.name;