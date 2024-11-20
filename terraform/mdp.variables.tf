// Core Project Vars
variable "projectName" {
  type        = string
  description = "The name of the project"
  default     = "Mines-Data-Platform"
}
variable "projectNameAbbr" {
  type        = string
  description = "The abbreviated name of the project"
  default     = "mdp"
}
variable "licensePlate" {
  type        = string
  description = "The license plate of the project"
  default     = "ef74b0"
}

// Core Subscription Vars
variable "subscription_id" {
  type        = string
  description = "The ID of the Azure subscription"
}
variable "tenant_id" {
  type        = string
  description = "The ID of the Azure tenant"
}

// Core Infrastructure Vars
variable "tags" {
  type        = map(string)
  description = "A map of tags to apply to resources"
  default     = {}
}

variable "environment" {
  description = "Environment for the resource."
  type        = string
  default     = "dev"
  validation {
    condition     = contains(["dev", "test", "prod"], var.environment)
    error_message = "The environment must be one of 'dev', 'test', or 'prod'."
  }
}

variable "location" {
  type        = string
  default     = "Canada Central"
  description = "The Azure region (e.g. Canada Central)"
  validation {
    condition     = contains(["Canada Central", "Canada East"], var.location)
    error_message = "The location must be one of 'Canada Central', 'Canada East'"
  }
}

variable "locationAbbr" {
  type        = string
  default     = "ca"
  description = "The abbreviated name of the Azure region (e.g. ca)"
  validation {
    condition     = contains(["ca", "ce"], var.locationAbbr)
    error_message = "The location must be one of 'ca', 'ce'"
  }
}

variable "address_space" {
  type        = list(string)
  description = "The address prefixes for the virtual network"
}

variable "subnet_names" {
  type        = list(string)
  description = "A list of names for the subnets"
}

variable "jumpbox_SKU" {
  type        = string
  description = "The SKU of the jumpbox VM"
  default     = "Standard_F2s_v2"
}