variable "project_prefix" {
  description = "Prefijo del entorno final; usar sufijos personales solo en pruebas."
  type        = string
  default     = "devops-grupo7-e2"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,39}$", var.project_prefix))
    error_message = "Usar de 3 a 40 caracteres: minusculas, numeros y guiones; iniciar con letra."
  }
}

variable "chatwoot_image" {
  description = "Imagen publicada en la entrega 1, fijada por digest."
  type        = string
  default     = "ghcr.io/jdap-do/devops-grupo7-chatwoot@sha256:a07e19d2e177ca98acd3b00460e8366bc24bbc0268b0dcceb6566ed4516005e9"

  validation {
    condition     = can(regex("@sha256:[a-f0-9]{64}$", var.chatwoot_image))
    error_message = "Indicar una imagen identificada por digest sha256."
  }
}

variable "app_port" {
  description = "Puerto local del panel de Chatwoot."
  type        = number
  default     = 3010

  validation {
    condition     = var.app_port >= 1024 && var.app_port <= 65535 && floor(var.app_port) == var.app_port
    error_message = "Usar un puerto entero entre 1024 y 65535."
  }
}

variable "secret_key_base" {
  description = "Clave privada de Rails, proporcionada fuera del codigo."
  type        = string
  sensitive   = true
  nullable    = false

  validation {
    condition     = length(var.secret_key_base) >= 64
    error_message = "La clave de Rails debe tener al menos 64 caracteres."
  }
}

variable "postgres_password" {
  description = "Contrasena externa compartida por los modulos de datos y computo."
  type        = string
  sensitive   = true
  nullable    = false

  validation {
    condition     = length(trimspace(var.postgres_password)) > 0
    error_message = "La contrasena de PostgreSQL no puede estar vacia."
  }
}

variable "redis_password" {
  description = "Contrasena externa compartida por los modulos de datos y computo."
  type        = string
  sensitive   = true
  nullable    = false

  validation {
    condition     = length(trimspace(var.redis_password)) > 0
    error_message = "La contrasena de Redis no puede estar vacia."
  }
}
