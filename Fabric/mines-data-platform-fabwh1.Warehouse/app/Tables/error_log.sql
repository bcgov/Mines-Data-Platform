-- Unified error log for all processing layers (bronze | silver | gold | ingest).
-- [layer] discriminates the source; pipeline_log owns run/pipeline logging.
-- Fabric Warehouse-safe (no IDENTITY / constraints); error_id populated by the writer.
CREATE TABLE [app].[error_log] (

	[error_id] bigint NOT NULL,
	[layer] varchar(20) NOT NULL,
	[run_id] varchar(100) NULL,
	[entity] varchar(200) NULL,
	[target_table] varchar(200) NULL,
	[error_message] varchar(max) NOT NULL,
	[error_context] varchar(max) NULL,
	[stack_trace] varchar(max) NULL,
	[created_date] datetime2(6) NOT NULL
);
