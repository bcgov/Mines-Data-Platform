//TODO: Re-write this into a for-loop in tech debt remed.

resource "azurerm_resource_group" "core" {
  name     = "rg-${var.projectNameAbbr}-core-${var.environment}-${var.locationAbbr}"
  location = var.location
}

resource "azurerm_resource_group" "security" {
  name     = "rg-${var.projectNameAbbr}-sec-${var.environment}-${var.locationAbbr}"
  location = var.location
}

resource "azurerm_resource_group" "data" {
  name     = "rg-${var.projectNameAbbr}-data-${var.environment}-${var.locationAbbr}"
  location = var.location
}