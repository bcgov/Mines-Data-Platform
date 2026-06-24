-- Centralized error log for BOTH pipeline and notebook errors.
-- [layer] discriminates the source (bronze | silver | gold | ingest); pipeline_log owns
-- run/pipeline lifecycle. [log_id]/[pipeline_name] give pipeline lineage (null on direct
-- notebook runs). [error_id] is a writer-minted GUID (Fabric Warehouse has no IDENTITY).
CREATE TABLE [app].[error_log] (

	[error_id] varchar(36) NOT NULL,
	[layer] varchar(20) NOT NULL,
	[log_id] bigint NULL,
	[pipeline_name] varchar(200) NULL,
	[run_id] varchar(100) NULL,
	[entity] varchar(200) NULL,
	[target_table] varchar(200) NULL,
	[error_message] varchar(max) NOT NULL,
	[error_code] varchar(100) NULL,
	[error_context] varchar(max) NULL,
	[stack_trace] varchar(max) NULL,
	[created_date] datetime2(6) NOT NULL
);
