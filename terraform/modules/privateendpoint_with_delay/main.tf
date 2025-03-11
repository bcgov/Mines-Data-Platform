resource "azurerm_private_endpoint" "this" {
  name                = var.endpoint_name
  location            = var.location
  resource_group_name = var.resource_group_name
  subnet_id           = var.subnet_id

  private_service_connection {
    name                           = var.connection_name
    private_connection_resource_id = var.resource_id
    is_manual_connection           = false
    subresource_names              = var.subresource_names
  }
}

resource "time_sleep" "wait_for_dns" {
  depends_on      = [azurerm_private_endpoint.this]
  create_duration = "60s"
}