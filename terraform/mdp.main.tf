# Configure the Azure provider
terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0.2"
    }
    azapi = {
       source = "Azure/azapi"
    }
    random = {
      source  = "hashicorp/random"
      version = "~>3.0"
    }
  }

  backend "azurerm" {}

  required_version = ">= 1.1.0"
}

provider "azurerm" {
  features {}
}

provider "azapi" {}