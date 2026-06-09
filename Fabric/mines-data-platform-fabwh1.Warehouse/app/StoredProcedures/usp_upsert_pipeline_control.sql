CREATE PROCEDURE [app].[usp_upsert_pipeline_control]
    @pipeline_name VARCHAR(200),
    @source_system VARCHAR(100),
    @source_entity VARCHAR(200),
    @source_connection_string VARCHAR(500) = NULL,
    @key_vault_url VARCHAR(500) = NULL,
    @target_schema VARCHAR(50),
    @target_table VARCHAR(200),
    @source_query_template VARCHAR(MAX) = NULL,
    @from_date DATETIME2(6) = NULL,
    @to_date DATETIME2(6) = NULL,
    @watermark_column VARCHAR(200) = NULL,
    @last_watermark VARCHAR(500) = NULL,
    @load_type VARCHAR(20) = 'INCREMENTAL',
    @load_frequency VARCHAR(50) = NULL,
    @priority INT = 100,
    @dependency_on VARCHAR(200) = NULL
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @new_hash VARCHAR(64);

    SET @new_hash = CONVERT(VARCHAR(64), HASHBYTES('SHA2_256',
        CONCAT(
            ISNULL(@source_system, ''), '|',
            ISNULL(@source_entity, ''), '|',
            ISNULL(@source_connection_string, ''), '|',
            ISNULL(@target_schema, ''), '|',
            ISNULL(@target_table, ''), '|',
            ISNULL(@source_query_template, ''), '|',
            ISNULL(@load_type, ''), '|',
            ISNULL(@watermark_column, '')
        )
    ), 2);

    IF EXISTS (
        SELECT 1
        FROM [app].[pipeline_control]
        WHERE [source_system] = @source_system
          AND [source_entity] = @source_entity
          AND [target_schema] = @target_schema
          AND [target_table] = @target_table
          AND [row_hash] = @new_hash
          AND [is_active] = 1
    )
    BEGIN
        PRINT 'No changes detected - active record with identical hash already exists. Skipping.';
        RETURN;
    END;

    DECLARE @next_version INT;

    SELECT @next_version = ISNULL(MAX([version_number]), 0) + 1
    FROM [app].[pipeline_control]
    WHERE [source_system] = @source_system
      AND [source_entity] = @source_entity
      AND [target_schema] = @target_schema
      AND [target_table] = @target_table;

    UPDATE [app].[pipeline_control]
    SET
        [is_active] = 0,
        [modified_date] = CAST(SYSUTCDATETIME() AS DATETIME2(6)),
        [modified_by] = SUSER_SNAME()
    WHERE [source_system] = @source_system
      AND [source_entity] = @source_entity
      AND [target_schema] = @target_schema
      AND [target_table] = @target_table
      AND [is_active] = 1;

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
        1,
        @load_frequency,
        @priority,
        @dependency_on,
        NULL,
        NULL,
        @next_version,
        @new_hash,
        CAST(SYSUTCDATETIME() AS DATETIME2(6)),
        SUSER_SNAME(),
        CAST(SYSUTCDATETIME() AS DATETIME2(6)),
        SUSER_SNAME()
    );

    PRINT CONCAT('Inserted pipeline_control record: ', @pipeline_name, ' v', CAST(@next_version AS VARCHAR(10)), ' | hash: ', @new_hash);
END;