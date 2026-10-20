# El proveedor obtiene su autenticación de TFE_TOKEN, no de variables Terraform.
provider "tfe" {
  hostname = "app.terraform.io"
}

resource "tfe_workspace" "host" {
  for_each = var.workspaces

  name              = each.key
  organization      = var.organization
  terraform_version = var.terraform_version
  auto_apply        = false
  force_delete      = false
  description = jsonencode({
    project        = "grupo7-entrega2"
    owner          = each.value.owner
    host_name      = each.value.host_name
    docker_context = each.value.docker_context
    configuration  = each.value.configuration
  })

  lifecycle {
    prevent_destroy = true
  }
}

resource "tfe_workspace_settings" "host" {
  for_each = var.workspaces

  workspace_id              = tfe_workspace.host[each.key].id
  execution_mode            = "local"
  global_remote_state       = false
  remote_state_consumer_ids = []
}
