# Configure the Azure provider
terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0.2"
    }
  }

  # backend "azurerm" {
  #   resource_group_name  = "rg-mdp-unmanaged-dev-"
  #   storage_account_name = "stgtfstate"
  #   container_name       = "terraform"
  #   key                  = "terraform.tfstate"
  # }

  required_version = ">= 1.1.0"
}

provider "azurerm" {
  features {}
}