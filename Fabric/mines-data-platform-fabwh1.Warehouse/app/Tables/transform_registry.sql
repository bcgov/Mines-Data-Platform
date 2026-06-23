CREATE TABLE [app].[transform_registry] (

	[transform_id] bigint IDENTITY NOT NULL,
	[transform_name] varchar(200) NOT NULL,
	[source_view] varchar(200) NOT NULL,
	[transform_type] varchar(20) NOT NULL,
	[scd_type] int NULL,
	[surrogate_key] varchar(200) NULL,
	[natural_keys] varchar(400) NULL,
	[load_group] int NOT NULL,
	[load_order] int NOT NULL,
	[is_active] bit NOT NULL,
	[created_date] datetime2(6) NOT NULL,
	[created_by] varchar(200) NOT NULL,
	[modified_date] datetime2(6) NOT NULL,
	[modified_by] varchar(200) NOT NULL
);
