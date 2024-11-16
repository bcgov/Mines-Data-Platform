data "azurerm_virtual_network" "vnet" {
  name                = "${var.licensePlate}-${var.environment}-vwan-spoke"
  resource_group_name = "${var.licensePlate}-${var.environment}-networking"
}

output "vnet_id" {
  value = data.azurerm_virtual_network.vnet.id
}

output "vnet_name" {
  value = data.azurerm_virtual_network.vnet.name
}