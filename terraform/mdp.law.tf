resource "azurerm_log_analytics_workspace" "law" {
  name                = "law-${var.projectNameAbbr}-${var.environment}-${var.locationAbbr}"
  resource_group_name = azurerm_resource_group.data.name
  location            = azurerm_resource_group.data.location
  sku                 = "PerGB2018"
  retention_in_days   = 30
}