resource "azurerm_resource_group" "core" {
  name     = "rg-${var.projectNameAbbr}-core-${var.environment}-${var.locationAbbr}"
  location = var.location
  lifecycle {
    ignore_changes = [
      tags
    ]
  }
}
resource "azurerm_resource_group" "security" {
  name     = "rg-${var.projectNameAbbr}-security-${var.environment}-${var.locationAbbr}"
  location = var.location
  lifecycle {
    ignore_changes = [
      tags
    ]
  }
}
resource "azurerm_resource_group" "data" {
  name     = "rg-${var.projectNameAbbr}-data-${var.environment}-${var.locationAbbr}"
  location = var.location
  lifecycle {
    ignore_changes = [
      tags
    ]
  }
}

resource "azurerm_resource_group" "bastion_rg" {
  name     = "rg-${var.projectNameAbbr}-bstn-${var.environment}-${var.locationAbbr}"
  location = var.location
  lifecycle {
    ignore_changes = [
      tags
    ]
  }
}