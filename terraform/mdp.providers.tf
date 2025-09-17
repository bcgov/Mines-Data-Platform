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