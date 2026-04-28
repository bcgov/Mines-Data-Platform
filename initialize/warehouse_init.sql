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
-- Tracks pipeline runs, source loads, and orchestration state
-- =============================================================================

IF NOT EXISTS (
    SELECT 1 FROM sys.tables t
    JOIN sys.schemas s ON t.schema_id = s.schema_id
    WHERE s.name = 'app' AND t.name = 'pipeline_control'
)
BEGIN
    CREATE TABLE [app].[pipeline_control] (
        [control_id]          INT            NOT NULL IDENTITY(1,1),
        [pipeline_name]       NVARCHAR(200)  NOT NULL,
        [source_system]       NVARCHAR(100)  NOT NULL,
        [source_entity]       NVARCHAR(200)  NOT NULL,
        [target_schema]       NVARCHAR(50)   NOT NULL,
        [target_table]        NVARCHAR(200)  NOT NULL,
        [load_type]           NVARCHAR(20)   NOT NULL DEFAULT 'FULL',   -- FULL | INCREMENTAL | CDC
        [is_active]           BIT            NOT NULL DEFAULT 1,
        [load_frequency]      NVARCHAR(50)   NULL,                      -- e.g. DAILY, HOURLY
        [watermark_column]    NVARCHAR(200)  NULL,                      -- column used for incremental loads
        [last_watermark]      NVARCHAR(500)  NULL,                      -- last high watermark value
        [priority]            INT            NOT NULL DEFAULT 100,       -- lower = higher priority
        [dependency_on]       NVARCHAR(200)  NULL,                      -- pipeline_name this depends on
        [created_date]        DATETIME2      NOT NULL DEFAULT SYSUTCDATETIME(),
        [created_by]          NVARCHAR(200)  NOT NULL DEFAULT SYSTEM_USER,
        [modified_date]       DATETIME2      NOT NULL DEFAULT SYSUTCDATETIME(),
        [modified_by]         NVARCHAR(200)  NOT NULL DEFAULT SYSTEM_USER,
        CONSTRAINT [PK_pipeline_control] PRIMARY KEY ([control_id]),
        CONSTRAINT [UQ_pipeline_control_entity] UNIQUE ([pipeline_name], [source_entity], [target_table]),
        CONSTRAINT [CHK_pipeline_control_load_type] CHECK ([load_type] IN ('FULL', 'INCREMENTAL', 'CDC'))
    );
END;
GO

-- =============================================================================
-- APP SCHEMA: LOGGING TABLE
-- Records execution history for every pipeline run
-- =============================================================================

IF NOT EXISTS (
    SELECT 1 FROM sys.tables t
    JOIN sys.schemas s ON t.schema_id = s.schema_id
    WHERE s.name = 'app' AND t.name = 'pipeline_log'
)
BEGIN
    CREATE TABLE [app].[pipeline_log] (
        [log_id]              BIGINT         NOT NULL IDENTITY(1,1),
        [run_id]              NVARCHAR(100)  NOT NULL,                  -- Fabric activity run ID
        [pipeline_name]       NVARCHAR(200)  NOT NULL,
        [source_entity]       NVARCHAR(200)  NOT NULL,
        [target_schema]       NVARCHAR(50)   NOT NULL,
        [target_table]        NVARCHAR(200)  NOT NULL,
        [status]              NVARCHAR(20)   NOT NULL DEFAULT 'RUNNING', -- RUNNING | SUCCESS | FAILED | SKIPPED
        [rows_read]           BIGINT         NULL,
        [rows_written]        BIGINT         NULL,
        [rows_skipped]        BIGINT         NULL,
        [watermark_start]     NVARCHAR(500)  NULL,
        [watermark_end]       NVARCHAR(500)  NULL,
        [error_message]       NVARCHAR(MAX)  NULL,
        [error_code]          NVARCHAR(100)  NULL,
        [start_time]          DATETIME2      NOT NULL DEFAULT SYSUTCDATETIME(),
        [end_time]            DATETIME2      NULL,
        [duration_seconds]    AS (DATEDIFF(SECOND, [start_time], [end_time])) PERSISTED,
        [environment]         NVARCHAR(20)   NOT NULL DEFAULT 'dev',    -- dev | test | prod
        [triggered_by]        NVARCHAR(200)  NULL,                      -- user or scheduler
        [created_date]        DATETIME2      NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT [PK_pipeline_log] PRIMARY KEY ([log_id]),
        CONSTRAINT [CHK_pipeline_log_status] CHECK ([status] IN ('RUNNING', 'SUCCESS', 'FAILED', 'SKIPPED'))
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
        [environment]     NVARCHAR(20)   NOT NULL DEFAULT 'ALL',        -- ALL | dev | test | prod
        [description]     NVARCHAR(500)  NULL,
        [is_secret]       BIT            NOT NULL DEFAULT 0,            -- flag sensitive values
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
-- Captures detailed error context for debugging and alerting
-- =============================================================================

IF NOT EXISTS (
    SELECT 1 FROM sys.tables t
    JOIN sys.schemas s ON t.schema_id = s.schema_id
    WHERE s.name = 'app' AND t.name = 'error_log'
)
BEGIN
    CREATE TABLE [app].[error_log] (
        [error_id]          BIGINT         NOT NULL IDENTITY(1,1),
        [log_id]            BIGINT         NULL,                        -- FK to pipeline_log
        [run_id]            NVARCHAR(100)  NULL,
        [pipeline_name]     NVARCHAR(200)  NULL,
        [error_number]      INT            NULL,
        [error_severity]    INT            NULL,
        [error_state]       INT            NULL,
        [error_procedure]   NVARCHAR(200)  NULL,
        [error_line]        INT            NULL,
        [error_message]     NVARCHAR(MAX)  NOT NULL,
        [error_context]     NVARCHAR(MAX)  NULL,                        -- JSON context bag
        [stack_trace]       NVARCHAR(MAX)  NULL,
        [created_date]      DATETIME2      NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT [PK_error_log] PRIMARY KEY ([error_id])
    );
END;
GO

-- =============================================================================
-- APP SCHEMA: SCHEMA REGISTRY
-- Documents all schemas and their purpose — useful for governance
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
        [layer]           NVARCHAR(50)   NOT NULL,                      -- e.g. RAW | CLEANSED | CURATED | APP
        [description]     NVARCHAR(500)  NULL,
        [owner]           NVARCHAR(200)  NULL,
        [created_date]    DATETIME2      NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT [PK_schema_registry] PRIMARY KEY ([registry_id]),
        CONSTRAINT [UQ_schema_registry_name] UNIQUE ([schema_name])
    );

    -- Seed with the four schemas created above
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
