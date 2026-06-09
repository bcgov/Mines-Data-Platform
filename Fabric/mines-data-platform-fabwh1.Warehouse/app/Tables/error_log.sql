CREATE TABLE [app].[error_log] (

	[error_id] bigint IDENTITY NOT NULL, 
	[log_id] bigint NULL, 
	[run_id] varchar(100) NULL, 
	[pipeline_name] varchar(200) NULL, 
	[error_number] int NULL, 
	[error_severity] int NULL, 
	[error_state] int NULL, 
	[error_procedure] varchar(200) NULL, 
	[error_line] int NULL, 
	[error_message] varchar(max) NOT NULL, 
	[error_context] varchar(max) NULL, 
	[stack_trace] varchar(max) NULL, 
	[created_date] datetime2(6) NOT NULL
);