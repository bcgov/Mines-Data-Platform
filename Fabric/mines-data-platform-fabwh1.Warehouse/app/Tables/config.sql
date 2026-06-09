CREATE TABLE [app].[config] (

	[config_id] bigint IDENTITY NOT NULL, 
	[config_key] varchar(200) NOT NULL, 
	[config_value] varchar(max) NOT NULL, 
	[config_group] varchar(100) NOT NULL, 
	[environment] varchar(20) NOT NULL, 
	[description] varchar(500) NULL, 
	[is_secret] bit NOT NULL, 
	[is_active] bit NOT NULL, 
	[created_date] datetime2(6) NOT NULL, 
	[created_by] varchar(200) NOT NULL, 
	[modified_date] datetime2(6) NOT NULL, 
	[modified_by] varchar(200) NOT NULL
);