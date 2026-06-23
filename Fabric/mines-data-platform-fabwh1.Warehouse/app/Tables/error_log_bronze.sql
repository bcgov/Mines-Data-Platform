CREATE TABLE [app].[error_log_bronze] (

	[error_id] bigint IDENTITY NOT NULL,
	[run_id] varchar(100) NULL,
	[entity] varchar(200) NULL,
	[target_table] varchar(200) NULL,
	[error_message] varchar(max) NOT NULL,
	[error_context] varchar(max) NULL,
	[stack_trace] varchar(max) NULL,
	[created_date] datetime2(6) NOT NULL
);
