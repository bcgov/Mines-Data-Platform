CREATE TABLE [app].[dq_result] (

	[result_id] bigint IDENTITY NOT NULL,
	[run_id] varchar(100) NOT NULL,
	[entity] varchar(200) NOT NULL,
	[rule_name] varchar(200) NOT NULL,
	[rows_evaluated] bigint NOT NULL,
	[rows_failed] bigint NOT NULL,
	[status] varchar(20) NOT NULL,
	[run_ts] datetime2(6) NOT NULL
);
