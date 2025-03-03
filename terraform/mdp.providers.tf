provider "azurerm" {
  features {
    key_vault {
      recover_soft_deleted_key_vaults = true
    }
  }
}

provider "azapi" {}

provider "http" {
  # Configuration options
}