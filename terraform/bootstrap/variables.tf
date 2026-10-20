variable "organization" {
  description = "Nombre de la organización HCP Terraform existente del grupo."
  type        = string

  validation {
    condition     = length(trimspace(var.organization)) > 0
    error_message = "Debe indicar la organización HCP Terraform."
  }
}

variable "workspaces" {
  description = "Workspaces por anfitrión: propietario, nombre del equipo y contexto Docker autorizados."
  type = map(object({
    owner          = string
    host_name      = string
    docker_context = string
    configuration  = string
  }))

  validation {
    condition = length(var.workspaces) > 0 && alltrue([
      for name, workspace in var.workspaces :
      length(trimspace(name)) > 0 &&
      length(trimspace(workspace.owner)) > 0 &&
      length(trimspace(workspace.host_name)) > 0 &&
      length(trimspace(workspace.docker_context)) > 0 &&
      contains(["root", "persistence-example"], workspace.configuration)
    ])
    error_message = "Declare workspaces con propietario, equipo y contexto no vacíos y configuración root o persistence-example."
  }
}

variable "terraform_version" {
  description = "Versión propuesta de Terraform, pendiente de confirmar con el root de José."
  type        = string
  default     = "1.16.6"
}
