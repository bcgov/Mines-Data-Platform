-- =============================================================================
-- warehouse_init.sql
-- Fabric Warehouse compatible - no DEFAULT, CHECK, or UNIQUE constraints
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
--   1. Lookup activity reads active rows
--   2. ForEach iterates each row
--   3. ADF injects @from_date / @to_date into source_query_template at runtime:
--      @replace(replace(item().source_query_template,
--        '@from_date', formatDateTime(item().from_date, 'yyyy-MM-dd HH:mm:ss')),
--        '@to_date',   formatDateTime(item().to_date,   'yyyy-MM-dd HH:mm:ss'))
--   4. After success, ADF updates last_watermark, last_run_status, last_run_date
-- =============================================================================

IF NOT EXISTS (
    SELECT 1 FROM sys.tables t
    JOIN sys.schemas s ON t.schema_id = s.schema_id
    WHERE s.name = 'app' AND t.name = 'pipeline_control'
)
BEGIN
    CREATE TABLE [app].[pipeline_control] (
        [control_id]            BIGINT          IDENTITY,
        [pipeline_name]         VARCHAR(200)    NOT NULL,
        [source_system]         VARCHAR(100)    NOT NULL,
        [source_entity]         VARCHAR(200)    NOT NULL,
        [source_connection_string] VARCHAR(500) NULL,
        [key_vault_url]         VARCHAR(500)    NULL,
        [target_schema]         VARCHAR(50)     NOT NULL,
        [target_table]          VARCHAR(200)    NOT NULL,
        [source_query_template] VARCHAR(MAX)    NULL,
        [from_date]             DATETIME2(6)    NULL,
        [to_date]               DATETIME2(6)    NULL,
        [watermark_column]      VARCHAR(200)    NULL,
        [last_watermark]        VARCHAR(500)    NULL,
        [load_type]             VARCHAR(20)     NOT NULL,
        [is_active]             BIT             NOT NULL,
        [load_frequency]        VARCHAR(50)     NULL,
        [priority]              INT             NOT NULL,
        [dependency_on]         VARCHAR(200)    NULL,
        [last_run_status]       VARCHAR(20)     NULL,
        [last_run_date]         DATETIME2(6)    NULL,
        [version_number]        INT             NOT NULL,
        [row_hash]              VARCHAR(64)     NULL,
        [created_date]          DATETIME2(6)    NOT NULL,
        [created_by]            VARCHAR(200)    NOT NULL,
        [modified_date]         DATETIME2(6)    NOT NULL,
        [modified_by]           VARCHAR(200)    NOT NULL
    );
END;
GO

-- =============================================================================
-- APP SCHEMA: LOGGING TABLE
-- =============================================================================

IF NOT EXISTS (
    SELECT 1 FROM sys.tables t
    JOIN sys.schemas s ON t.schema_id = s.schema_id
    WHERE s.name = 'app' AND t.name = 'pipeline_log'
)
BEGIN
    CREATE TABLE [app].[pipeline_log] (
        [log_id]              BIGINT IDENTITY,
        [run_id]              VARCHAR(100)   NOT NULL,
        [activity_run_id]     VARCHAR(100)   NULL,
        [pipeline_name]       VARCHAR(200)   NOT NULL,
        [source_entity]       VARCHAR(200)   NOT NULL,
        [target_schema]       VARCHAR(50)    NOT NULL,
        [target_table]        VARCHAR(200)   NOT NULL,
        [status]              VARCHAR(20)    NOT NULL,
        [rows_read]           BIGINT          NULL,
        [rows_written]        BIGINT          NULL,
        [rows_skipped]        BIGINT          NULL,
        [from_date]           DATETIME2(6)       NULL,
        [to_date]             DATETIME2(6)       NULL,
        [watermark_start]     VARCHAR(500)   NULL,
        [watermark_end]       VARCHAR(500)   NULL,
        [error_message]       VARCHAR(MAX)   NULL,
        [error_code]          VARCHAR(100)   NULL,
        [start_time]          DATETIME2(6)       NOT NULL,
        [end_time]            DATETIME2(6)       NULL,
        [environment]         VARCHAR(20)    NOT NULL,
        [triggered_by]        VARCHAR(200)   NULL,
        [created_date]        DATETIME2(6)       NOT NULL
    );
END;
GO

-- =============================================================================
-- APP SCHEMA: CONFIGURATION TABLE
-- =============================================================================

IF NOT EXISTS (
    SELECT 1 FROM sys.tables t
    JOIN sys.schemas s ON t.schema_id = s.schema_id
    WHERE s.name = 'app' AND t.name = 'config'
)
BEGIN
    CREATE TABLE [app].[config] (
        [config_id]       BIGINT IDENTITY,
        [config_key]      VARCHAR(200)   NOT NULL,
        [config_value]    VARCHAR(MAX)   NOT NULL,
        [config_group]    VARCHAR(100)   NOT NULL,
        [environment]     VARCHAR(20)    NOT NULL,
        [description]     VARCHAR(500)   NULL,
        [is_secret]       BIT             NOT NULL,
        [is_active]       BIT             NOT NULL,
        [created_date]    DATETIME2(6)       NOT NULL,
        [created_by]      VARCHAR(200)   NOT NULL,
        [modified_date]   DATETIME2(6)       NOT NULL,
        [modified_by]     VARCHAR(200)   NOT NULL
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
        [error_id]        BIGINT IDENTITY,
        [log_id]          BIGINT          NULL,
        [run_id]          VARCHAR(100)   NULL,
        [pipeline_name]   VARCHAR(200)   NULL,
        [error_number]    INT             NULL,
        [error_severity]  INT             NULL,
        [error_state]     INT             NULL,
        [error_procedure] VARCHAR(200)   NULL,
        [error_line]      INT             NULL,
        [error_message]   VARCHAR(MAX)   NOT NULL,
        [error_context]   VARCHAR(MAX)   NULL,
        [stack_trace]     VARCHAR(MAX)   NULL,
        [created_date]    DATETIME2(6)       NOT NULL
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
        [registry_id]   BIGINT IDENTITY,
        [schema_name]   VARCHAR(50)    NOT NULL,
        [layer]         VARCHAR(50)    NOT NULL,
        [description]   VARCHAR(500)   NULL,
        [owner]         VARCHAR(200)   NULL,
        [created_date]  DATETIME2(6)       NOT NULL
    );
END;
GO

IF NOT EXISTS (SELECT 1 FROM [app].[schema_registry] WHERE [schema_name] = 'bronze')
    INSERT INTO [app].[schema_registry] ([schema_name], [layer], [description], [created_date])
    VALUES
        ('bronze', 'RAW',      'Raw ingested data - no transformations applied',               CAST(SYSUTCDATETIME() AS DATETIME2(6))),
        ('silver', 'CLEANSED', 'Cleansed and conformed data - business rules applied',         CAST(SYSUTCDATETIME() AS DATETIME2(6))),
        ('gold',   'CURATED',  'Curated aggregates and star schema models for reporting',      CAST(SYSUTCDATETIME() AS DATETIME2(6))),
        ('app',    'APP',      'Application control objects - logging, config, orchestration', CAST(SYSUTCDATETIME() AS DATETIME2(6)));
GO

-- =============================================================================
-- SEED CONFIGURATION VALUES
-- =============================================================================

IF NOT EXISTS (SELECT 1 FROM [app].[config] WHERE [config_key] = 'retention_days_bronze' AND [environment] = 'ALL')
    INSERT INTO [app].[config] ([config_key], [config_value], [config_group], [environment], [description], [is_secret], [is_active], [created_date], [created_by], [modified_date], [modified_by])
    VALUES ('retention_days_bronze', '90', 'RETENTION', 'ALL', 'Days to retain data in bronze layer', 0, 1, CAST(SYSUTCDATETIME() AS DATETIME2(6)), SUSER_SNAME(), CAST(SYSUTCDATETIME() AS DATETIME2(6)), SUSER_SNAME());
GO

IF NOT EXISTS (SELECT 1 FROM [app].[config] WHERE [config_key] = 'retention_days_silver' AND [environment] = 'ALL')
    INSERT INTO [app].[config] ([config_key], [config_value], [config_group], [environment], [description], [is_secret], [is_active], [created_date], [created_by], [modified_date], [modified_by])
    VALUES ('retention_days_silver', '365', 'RETENTION', 'ALL', 'Days to retain data in silver layer', 0, 1, CAST(SYSUTCDATETIME() AS DATETIME2(6)), SUSER_SNAME(), CAST(SYSUTCDATETIME() AS DATETIME2(6)), SUSER_SNAME());
GO

IF NOT EXISTS (SELECT 1 FROM [app].[config] WHERE [config_key] = 'retention_days_gold' AND [environment] = 'ALL')
    INSERT INTO [app].[config] ([config_key], [config_value], [config_group], [environment], [description], [is_secret], [is_active], [created_date], [created_by], [modified_date], [modified_by])
    VALUES ('retention_days_gold', '730', 'RETENTION', 'ALL', 'Days to retain data in gold layer', 0, 1, CAST(SYSUTCDATETIME() AS DATETIME2(6)), SUSER_SNAME(), CAST(SYSUTCDATETIME() AS DATETIME2(6)), SUSER_SNAME());
GO

IF NOT EXISTS (SELECT 1 FROM [app].[config] WHERE [config_key] = 'max_retry_attempts' AND [environment] = 'ALL')
    INSERT INTO [app].[config] ([config_key], [config_value], [config_group], [environment], [description], [is_secret], [is_active], [created_date], [created_by], [modified_date], [modified_by])
    VALUES ('max_retry_attempts', '3', 'ORCHESTRATION', 'ALL', 'Maximum pipeline retry attempts on failure', 0, 1, CAST(SYSUTCDATETIME() AS DATETIME2(6)), SUSER_SNAME(), CAST(SYSUTCDATETIME() AS DATETIME2(6)), SUSER_SNAME());
GO

IF NOT EXISTS (SELECT 1 FROM [app].[config] WHERE [config_key] = 'alert_on_failure' AND [environment] = 'ALL')
    INSERT INTO [app].[config] ([config_key], [config_value], [config_group], [environment], [description], [is_secret], [is_active], [created_date], [created_by], [modified_date], [modified_by])
    VALUES ('alert_on_failure', 'true', 'ALERTING', 'ALL', 'Send alert notification on pipeline failure', 0, 1, CAST(SYSUTCDATETIME() AS DATETIME2(6)), SUSER_SNAME(), CAST(SYSUTCDATETIME() AS DATETIME2(6)), SUSER_SNAME());
GO

-- =============================================================================
-- SEED EXAMPLE CONTROL TABLE ROW
-- =============================================================================

IF NOT EXISTS (SELECT 1 FROM [app].[pipeline_control] WHERE [pipeline_name] = 'pl_ingest_orders')
    INSERT INTO [app].[pipeline_control] (
        [pipeline_name], [source_system], [source_entity],
        [source_connection_string], [key_vault_url],
        [target_schema], [target_table], [load_type],
        [watermark_column], [from_date], [to_date],
        [is_active], [priority], [version_number], [row_hash],
        [created_date], [created_by], [modified_date], [modified_by],
        [source_query_template]
    )
    VALUES (
        'pl_ingest_orders', 'SourceDB', 'dbo.Orders',
        'Server=tcp:source-server.database.windows.net,1433;Database=SourceDB', NULL,
        'bronze', 'orders', 'INCREMENTAL',
        'updated_at', '2024-01-01 00:00:00', CAST(SYSUTCDATETIME() AS DATETIME2(6)),
        1, 100, 1,
        CONVERT(VARCHAR(64), HASHBYTES('SHA2_256',
            CONCAT('SourceDB','|','dbo.Orders','|',
                   'Server=tcp:source-server.database.windows.net,1433;Database=SourceDB',
                   '|','bronze','|','orders')), 2),
        CAST(SYSUTCDATETIME() AS DATETIME2(6)), SUSER_SNAME(),
        CAST(SYSUTCDATETIME() AS DATETIME2(6)), SUSER_SNAME(),
        'SELECT order_id, customer_id, order_date, total_amount, updated_at
FROM dbo.Orders
WHERE updated_at >= ''@from_date''
  AND updated_at <  ''@to_date'''
    );
GO
-- =============================================================================
-- STORED PROCEDURE: usp_upsert_pipeline_control
--
-- Purpose: Insert or version a pipeline control record.
--   - Computes SHA2_256 hash over source_system, source_entity,
--     source_connection_string, target_schema, target_table
--   - If an identical hash already exists and is active -> no-op (duplicate)
--   - If same source+target mapping exists with a different hash ->
--     mark existing rows inactive, insert new row with version_number + 1
--   - If no existing mapping -> insert as version 1
--
-- Parameters match pipeline_control columns except auto-managed fields:
--   control_id, is_active, version_number, row_hash,
--   created_date, created_by, modified_date, modified_by
-- =============================================================================

IF EXISTS (
    SELECT 1 FROM sys.procedures p
    JOIN sys.schemas s ON p.schema_id = s.schema_id
    WHERE s.name = 'app' AND p.name = 'usp_upsert_pipeline_control'
)
    DROP PROCEDURE [app].[usp_upsert_pipeline_control];
GO

CREATE PROCEDURE [app].[usp_upsert_pipeline_control]
    @pipeline_name          VARCHAR(200),
    @source_system          VARCHAR(100),
    @source_entity          VARCHAR(200),
    @source_connection_string VARCHAR(500) = NULL,
    @key_vault_url          VARCHAR(500)  = NULL,
    @target_schema          VARCHAR(50),
    @target_table           VARCHAR(200),
    @source_query_template  VARCHAR(MAX)  = NULL,
    @from_date              DATETIME2(6)  = NULL,
    @to_date                DATETIME2(6)  = NULL,
    @watermark_column       VARCHAR(200)  = NULL,
    @last_watermark         VARCHAR(500)  = NULL,
    @load_type              VARCHAR(20)   = 'INCREMENTAL',
    @load_frequency         VARCHAR(50)   = NULL,
    @priority               INT           = 100,
    @dependency_on          VARCHAR(200)  = NULL
AS
BEGIN
    SET NOCOUNT ON;

    -- ── 1. Compute hash over source-to-target identity fields ────────────────
    DECLARE @new_hash VARCHAR(64);
    SET @new_hash = CONVERT(VARCHAR(64), HASHBYTES('SHA2_256',
        CONCAT(
            ISNULL(@source_system,              ''),   '|',
            ISNULL(@source_entity,              ''),   '|',
            ISNULL(@source_connection_string,   ''),   '|',
            ISNULL(@target_schema,              ''),   '|',
            ISNULL(@target_table,               ''),   '|',
            ISNULL(@source_query_template,      ''),   '|',
            ISNULL(@load_type,                  ''),   '|',
            ISNULL(@watermark_column,           '')
        )
    ), 2);

    -- ── 2. Check for exact duplicate (same hash, already active) ────────────
    IF EXISTS (
        SELECT 1 FROM [app].[pipeline_control]
        WHERE [source_system]   = @source_system
          AND [source_entity]   = @source_entity
          AND [target_schema]   = @target_schema
          AND [target_table]    = @target_table
          AND [row_hash]        = @new_hash
          AND [is_active]       = 1
    )
    BEGIN
        PRINT 'No changes detected — active record with identical hash already exists. Skipping.';
        RETURN;
    END

    -- ── 3. Get current max version for this source-to-target mapping ─────────
    DECLARE @next_version INT;
    SELECT @next_version = ISNULL(MAX([version_number]), 0) + 1
    FROM [app].[pipeline_control]
    WHERE [source_system] = @source_system
      AND [source_entity] = @source_entity
      AND [target_schema] = @target_schema
      AND [target_table]  = @target_table;

    -- ── 4. Mark all existing active records for this mapping as inactive ─────
    UPDATE [app].[pipeline_control]
    SET
        [is_active]     = 0,
        [modified_date] = CAST(SYSUTCDATETIME() AS DATETIME2(6)),
        [modified_by]   = SUSER_SNAME()
    WHERE [source_system] = @source_system
      AND [source_entity] = @source_entity
      AND [target_schema] = @target_schema
      AND [target_table]  = @target_table
      AND [is_active]     = 1;

    -- ── 5. Insert new active version ─────────────────────────────────────────
    INSERT INTO [app].[pipeline_control] (
        [pipeline_name],
        [source_system],
        [source_entity],
        [source_connection_string],
        [key_vault_url],
        [target_schema],
        [target_table],
        [source_query_template],
        [from_date],
        [to_date],
        [watermark_column],
        [last_watermark],
        [load_type],
        [is_active],
        [load_frequency],
        [priority],
        [dependency_on],
        [last_run_status],
        [last_run_date],
        [version_number],
        [row_hash],
        [created_date],
        [created_by],
        [modified_date],
        [modified_by]
    )
    VALUES (
        @pipeline_name,
        @source_system,
        @source_entity,
        @source_connection_string,
        @key_vault_url,
        @target_schema,
        @target_table,
        @source_query_template,
        @from_date,
        @to_date,
        @watermark_column,
        @last_watermark,
        @load_type,
        1,                                              -- is_active = true
        @load_frequency,
        @priority,
        @dependency_on,
        NULL,                                           -- last_run_status
        NULL,                                           -- last_run_date
        @next_version,
        @new_hash,
        CAST(SYSUTCDATETIME() AS DATETIME2(6)),
        SUSER_SNAME(),
        CAST(SYSUTCDATETIME() AS DATETIME2(6)),
        SUSER_SNAME()
    );

    PRINT CONCAT('Inserted pipeline_control record: ', @pipeline_name,
                 ' v', CAST(@next_version AS VARCHAR(10)),
                 ' | hash: ', @new_hash);
END;
GO

-- =============================================================================
-- DONE
-- =============================================================================

SELECT
    s.name        AS schema_name,
    COUNT(t.name) AS table_count
FROM sys.schemas s
LEFT JOIN sys.tables t ON t.schema_id = s.schema_id
WHERE s.name IN ('bronze', 'silver', 'gold', 'app')
GROUP BY s.name
ORDER BY s.name;