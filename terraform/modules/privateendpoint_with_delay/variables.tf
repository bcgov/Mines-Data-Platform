variable "endpoint_name" {
  type        = string
  description = "The name of the private endpoint."
}

variable "location" {
  type        = string
  description = "The location of the private endpoint."
}

variable "resource_group_name" {
  type        = string
  description = "The name of the resource group in which to create the private endpoint."
}

variable "subnet_id" {
  type        = string
  description = "The ID of the subnet to which to attach the private endpoint."
}

variable "connection_name" {
  type        = string
  description = "The name of the private service connection."
}

variable "resource_id" {
  type        = string
  description = "The ID of the resource to which to connect."
}

variable "subresource_names" {
  type        = list(string)
  description = "A list of subresources to which to connect."
}
