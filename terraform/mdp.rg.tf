//TODO: Re-write this into a for-loop in tech debt remed.
resource "azurerm_resource_group" "core" {
  name     = "rg-${var.projectNameAbbr}-core-${var.environment}-${var.locationAbbr}"
  location = var.location
}
resource "azurerm_resource_group" "security" {
  name     = "rg-${var.projectNameAbbr}-security-${var.environment}-${var.locationAbbr}"
  location = var.location
}
resource "azurerm_resource_group" "data" {
  name     = "rg-${var.projectNameAbbr}-data-${var.environment}-${var.locationAbbr}"
  location = var.location
}
resource "azurerm_management_lock" "core_lock" {
  name       = "rg-core-lock"
  lock_level = "CanNotDelete"
  scope      = azurerm_resource_group.core.id
}
resource "azurerm_management_lock" "security_lock" {
  name       = "rg-sec-lock"
  lock_level = "CanNotDelete"
  scope      = azurerm_resource_group.security.id
}
resource "azurerm_management_lock" "data_lock" {
  name       = "rg-data-lock"
  lock_level = "CanNotDelete"
  scope      = azurerm_resource_group.data.id
}