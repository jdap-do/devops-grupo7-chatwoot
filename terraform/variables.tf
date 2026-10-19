variable "project_prefix" {
  description = "Prefijo del entorno final; usar sufijos personales solo en pruebas."
  type        = string
  default     = "devops-grupo7-e2"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,39}$", var.project_prefix))
    error_message = "Usar de 3 a 40 caracteres: minusculas, numeros y guiones; iniciar con letra."
  }
}
