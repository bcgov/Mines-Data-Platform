provider "azurerm" {
  use_oidc = true
  features {
    key_vault {
      recover_soft_deleted_key_vaults = true
    }
    resource_group {
      prevent_deletion_if_contains_resources = false
    }
  }
}

provider "azapi" {}

provider "http" {
  # Configuration options
}

provider "azuread" {
}

# Configure the Microsoft Fabric Terraform Provider
provider "fabric" {
  # Configuration options
}

terraform {
  required_version = ">= 1.13.0"
  required_providers {
    fabric = {
      source  = "microsoft/fabric"
      version = ">= 1.6.0"
    }
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 4.44.0"
    }
  }

  backend "azurerm" {}
}
