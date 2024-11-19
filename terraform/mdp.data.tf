data "azurerm_virtual_network" "vnet" {
  name                = "${var.licensePlate}-${var.environment}-vwan-spoke"
  resource_group_name = "${var.licensePlate}-${var.environment}-networking"
}