CREATE TABLE [app].[field_registry] (

	[field_id] bigint IDENTITY NOT NULL,
	[object_id] bigint NOT NULL,
	[entity] varchar(200) NOT NULL,
	[column_name] varchar(200) NOT NULL,
	[spark_type] varchar(100) NOT NULL,
	[nullable] bit NOT NULL,
	[is_pk] bit NOT NULL,
	[include_in_load] bit NOT NULL,
	[pii_type] varchar(50) NULL,
	[ordinal] int NOT NULL,
	[created_date] datetime2(6) NOT NULL,
	[created_by] varchar(200) NOT NULL,
	[modified_date] datetime2(6) NOT NULL,
	[modified_by] varchar(200) NOT NULL
);
