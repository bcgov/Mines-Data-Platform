// Azurerm data factory that is used for the platform 
resource "azurerm_data_factory" "data" {
  name                   = "adf-${var.projectNameAbbr}-${var.environment}-${var.locationAbbr}"
  resource_group_name    = azurerm_resource_group.data.name
  public_network_enabled = false
  identity {
    type = "SystemAssigned"
  }
  location = var.location
  tags     = var.tags
}