CREATE TABLE [app].[dq_rule] (

	[rule_id] bigint IDENTITY NOT NULL,
	[entity] varchar(200) NOT NULL,
	[column_name] varchar(200) NULL,
	[rule_type] varchar(50) NOT NULL,
	[params] varchar(max) NULL,
	[severity] varchar(20) NOT NULL,
	[is_active] bit NOT NULL,
	[created_date] datetime2(6) NOT NULL,
	[created_by] varchar(200) NOT NULL,
	[modified_date] datetime2(6) NOT NULL,
	[modified_by] varchar(200) NOT NULL
);
