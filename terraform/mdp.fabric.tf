# It's recommended to use `lifecycle` with `postcondition` block to handle the state of the capacity.
data "fabric_capacity" "example" {
  id = var.capacity_id

  lifecycle {
    postcondition {
      condition     = self.state == "Active"
      error_message = "Fabric Capacity is not in Active state. Please check the Fabric Capacity status."
    }
  }
}

data "fabric_workspace" "non-prod" {
  display_name = var.non_prod_workspace_display_name
}

# TODO: Prod is NOT ready yet.
# data "fabric_workspace" "prod" {
#   display_name = var.prod_workspace_display_name
# }