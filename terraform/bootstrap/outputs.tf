output "workspaces" {
  description = "Identificadores, URLs y asociación por anfitrión, una vez configurada la ejecución Local."
  value = {
    for name, workspace in tfe_workspace.host : name => {
      id             = workspace.id
      url            = workspace.html_url
      owner          = var.workspaces[name].owner
      host_name      = var.workspaces[name].host_name
      docker_context = var.workspaces[name].docker_context
      configuration  = var.workspaces[name].configuration
      execution_mode = tfe_workspace_settings.host[name].execution_mode
    }
  }
}
