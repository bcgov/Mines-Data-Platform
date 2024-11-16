# resource "azurerm_storage_account" "core" {
#   name                     = "st${var.projectNameAbbr}core${var.environment}"
#   resource_group_name      = azurerm_resource_group.core.name
#   location                 = var.location
#   account_tier             = "Standard"
#   account_replication_type = "LRS"
# }

# resource "azurerm_storage_account" "data" {
#   name                     = "st${var.projectNameAbbr}data${var.environment}"
#   resource_group_name      = azurerm_resource_group.data.name
#   location                 = var.location
#   account_tier             = "Standard"
#   account_replication_type = "LRS"
# }