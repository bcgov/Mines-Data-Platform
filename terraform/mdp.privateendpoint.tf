module "private_endpoint_adf" {
  source              = "./modules/privateendpoint_with_delay"
  endpoint_name       = "pe-${var.projectNameAbbr}-adf-${var.environment}-${var.locationAbbr}"
  location            = var.location
  resource_group_name = azurerm_resource_group.data.name
  subnet_id           = data.azurerm_subnet.privatesubnet.id
  connection_name     = "psc-${var.projectNameAbbr}-adf-${var.environment}-${var.locationAbbr}"
  resource_id         = azurerm_data_factory.adf.id
  subresource_names   = ["dataFactory"]
  depends_on          = [azurerm_data_factory.adf]
}

module "private_endpoint_kv" {
  source              = "./modules/privateendpoint_with_delay"
  endpoint_name       = "pe-${var.projectNameAbbr}-vault-${var.environment}-${var.locationAbbr}"
  location            = azurerm_resource_group.security.location
  resource_group_name = azurerm_resource_group.security.name
  subnet_id           = data.azurerm_subnet.privatesubnet.id
  connection_name     = "psc-${var.projectNameAbbr}-vault-${var.environment}-${var.locationAbbr}"
  resource_id         = azurerm_key_vault.kv.id
  subresource_names   = ["vault"]
  depends_on          = [azurerm_key_vault.kv]
}

module "private_endpoint_corestorage" {
  source              = "./modules/privateendpoint_with_delay"
  endpoint_name       = "pe-${var.projectNameAbbr}-stgcore-${var.environment}-${var.locationAbbr}"
  location            = var.location
  resource_group_name = azurerm_resource_group.data.name
  subnet_id           = data.azurerm_subnet.privatesubnet.id
  connection_name     = "psc-${var.projectNameAbbr}-stgcore-${var.environment}-${var.locationAbbr}"
  resource_id         = azurerm_storage_account.core.id
  subresource_names   = ["blob"]
  depends_on          = [azurerm_storage_account.core]
}

module "private_endpoint_datastorage" {
  source              = "./modules/privateendpoint_with_delay"
  endpoint_name       = "pe-${var.projectNameAbbr}-stgdata-${var.environment}-${var.locationAbbr}"
  location            = var.location
  resource_group_name = azurerm_resource_group.data.name
  subnet_id           = data.azurerm_subnet.privatesubnet.id
  connection_name     = "psc-${var.projectNameAbbr}-stgdata-${var.environment}-${var.locationAbbr}"
  resource_id         = azurerm_storage_account.data.id
  subresource_names   = ["blob"]
  depends_on          = [azurerm_storage_account.data]
}
