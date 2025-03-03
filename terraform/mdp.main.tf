# Configure the Azure provider
terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.21.1"
    }
    azapi = {
      source = "Azure/azapi"
    }
    random = {
      source  = "hashicorp/random"
      version = "~>3.0"
    }
    http = {
      source  = "hashicorp/http"
      version = "3.4.5"
    }
  }

  backend "azurerm" {
    resource_group_name  = "rg-mdp-unmanaged-test-ca"
    storage_account_name = "stgmdptfstateca"
    container_name       = "tfstate"
    key                  = "terraform.tfstate"
    use_azuread_auth     = true

  }

  required_version = ">= 1.1.0"
}