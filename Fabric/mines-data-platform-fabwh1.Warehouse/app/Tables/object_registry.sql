CREATE TABLE [app].[object_registry] (

	[object_id] bigint IDENTITY NOT NULL,
	[source_entity] varchar(200) NOT NULL,
	[bronze_schema] varchar(50) NOT NULL,
	[bronze_table] varchar(200) NOT NULL,
	[silver_schema] varchar(50) NOT NULL,
	[silver_table] varchar(200) NOT NULL,
	[load_type] varchar(20) NOT NULL,
	[primary_key] varchar(400) NULL,
	[watermark_column] varchar(200) NULL,
	[is_active] bit NOT NULL,
	[load_group] int NOT NULL,
	[priority] int NOT NULL,
	[dependency_on] varchar(200) NULL,
	[created_date] datetime2(6) NOT NULL,
	[created_by] varchar(200) NOT NULL,
	[modified_date] datetime2(6) NOT NULL,
	[modified_by] varchar(200) NOT NULL
);
