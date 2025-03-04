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
# variable "SUBSCRIPTION_ID" {
#   type        = string
#   description = "The ID of the Azure subscription"
# }

variable "tenant_id" {
  type        = string
  description = "The ID of the Azure tenant"
  default     = "6fdb5200-3d0d-4a8a-b036-d3685e359adc"
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
  default     = "test"
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
    error_message = "The location must be one of 'Canada Central', 'Canada East'."
  }
}

variable "locationAbbr" {
  type        = string
  default     = "ca"
  description = "The abbreviated name of the Azure region (e.g. ca)"
  validation {
    condition     = contains(["ca", "ce"], var.locationAbbr)
    error_message = "The location must be one of 'ca', 'ce'."
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


#### BASTION ####
variable "bastion_host_name" {
  description = "(Required) The name of the Bastion Host"
  type        = string
  default = "bstn-mdp"
}

variable "bastion_sku" {
  description = "(Optional) Accepted values are Developer, Basic, Standard and Premium."
  type        = string
  default     = "Basic"

  validation {
    condition     = var.bastion_sku != "Developer"
    error_message = "Developer SKU is not currently available in Canada"
  }
}

variable "copy_paste_enabled" {
  description = "(Optional) Is Copy/Paste feature enabled for the Bastion Host. Defaults to true."
  type        = bool
  default     = true
}

variable "file_copy_enabled" {
  description = "(Optional) Is File Copy feature enabled for the Bastion Host. Defaults to false."
  type        = bool
  default     = null

  validation {
    condition = (
      (var.file_copy_enabled == null || var.file_copy_enabled == false) ||
      (var.file_copy_enabled == true && var.bastion_sku == "Standard" || var.bastion_sku == "Premium")
    )
    error_message = "file_copy_enabled is only supported when sku is Standard or Premium"
  }
}

variable "ip_connect_enabled" {
  description = "(Optional) Is IP Connect feature enabled for the Bastion Host. Defaults to false."
  type        = bool
  default     = null

  validation {
    condition = (
      (var.ip_connect_enabled == null || var.ip_connect_enabled == false) ||
      (var.ip_connect_enabled == true && var.bastion_sku == "Standard" || var.bastion_sku == "Premium")
    )
    error_message = "ip_connect_enabled is only supported when sku is Standard or Premium"
  }
}

variable "kerberos_enabled" {
  description = "(Optional) Is Kerberos feature enabled for the Bastion Host. Defaults to false."
  type        = bool
  default     = null

  validation {
    condition = (
      (var.kerberos_enabled == null || var.kerberos_enabled == false) ||
      (var.kerberos_enabled == true && var.bastion_sku == "Standard" || var.bastion_sku == "Premium")
    )
    error_message = "kerberos_enabled is only supported when sku is Standard or Premium"
  }
}

variable "scale_units" {
  description = "(Optional) The number of scale units for the Bastion Host. Defaults to 2."
  type        = number
  default     = 2

  validation {
    condition = (
      (
        var.scale_units >= 2 &&
        var.bastion_sku == "Standard" || var.bastion_sku == "Premium"
      ) ||
      (
        var.scale_units <= 2 &&
        var.bastion_sku == "Basic"
      )
    )
    error_message = "scale_units is only supported when sku is Standard or Premium"
  }

  validation {
    condition = (
      var.scale_units >= 2 &&
      var.scale_units <= 50
    )
    error_message = "scale_units must be between 2 and 50"
  }
}

variable "shareable_link_enabled" {
  description = "(Optional) Is Shareable Link feature enabled for the Bastion Host. Defaults to false."
  type        = bool
  default     = null

  validation {
    condition = (
      (var.shareable_link_enabled == null || var.shareable_link_enabled == false) ||
      (var.shareable_link_enabled == true && var.bastion_sku == "Standard" || var.bastion_sku == "Premium")
    )
    error_message = "shareable_link_enabled is only supported when sku is Standard or Premium"
  }
}

variable "tunneling_enabled" {
  description = "(Optional) Enable tunneling through the Bastion Host"
  type        = bool
  default     = null

  validation {
    condition = (
      (var.tunneling_enabled == null || var.tunneling_enabled == false) ||
      (var.tunneling_enabled == true && var.bastion_sku == "Standard" || var.bastion_sku == "Premium")
    )
    error_message = "tunneling_enabled is only supported when sku is Standard or Premium"
  }
}

variable "session_recording_enabled" {
  description = "(Optional) Enable session recording for the Bastion Host"
  type        = bool
  default     = null

  validation {
    condition = (
      (var.session_recording_enabled == null || var.session_recording_enabled == false) ||
      (var.session_recording_enabled == true && var.bastion_sku == "Premium")
    )
    error_message = "session_recording_enabled is only supported when sku is Premium."
  }
}

variable "virtual_network_name" {
  description = "Name of the existing virtual network"
  type        = string
}

variable "virtual_network_resource_group" {
  description = "Name of the resource group containing the virtual network"
  type        = string
}

variable "bastionSubnetAddressPrefix" {
  description = "Address prefix for the bastion subnet. Must be at least w.x.y.z/26"
  type        = string

  validation {
    condition     = can(regex("^(\\d{1,3}\\.){3}\\d{1,3}/(\\d{1,2})$", var.bastionSubnetAddressPrefix)) && tonumber(split("/", var.bastionSubnetAddressPrefix)[1]) <= 26
    error_message = "bastionSubnetAddressPrefix must be in the form w.x.y.z/26 or larger (e.g., /25, /24, etc.)"
  }
}
