variable "project_prefix" {
  description = "Prefijo que separa los recursos de este despliegue."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,39}$", var.project_prefix))
    error_message = "Usar de 3 a 40 caracteres: minusculas, numeros y guiones; iniciar con letra."
  }
}
