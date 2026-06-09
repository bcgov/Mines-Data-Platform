CREATE TABLE [app].[schema_registry] (

	[registry_id] bigint IDENTITY NOT NULL, 
	[schema_name] varchar(50) NOT NULL, 
	[layer] varchar(50) NOT NULL, 
	[description] varchar(500) NULL, 
	[owner] varchar(200) NULL, 
	[created_date] datetime2(6) NOT NULL
);