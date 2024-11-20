resource "azurerm_private_endpoint" "adf" {
  name                = "pe-${var.projectNameAbbr}-adf-${var.environment}-${var.locationAbbr}"
  location            = var.location
  resource_group_name = azurerm_resource_group.data.name
  subnet_id           = azapi_resource.datasubnet.id

  private_service_connection {
    name                           = "psc-${var.projectNameAbbr}-adf-${var.environment}-${var.locationAbbr}"
    private_connection_resource_id = azurerm_data_factory.adf.id
    subresource_names              = ["dataFactory"]
    is_manual_connection           = false
  }
}