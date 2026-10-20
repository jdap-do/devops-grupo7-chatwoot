# Datos del despliegue, definidos por la configuracion principal.
variable "project_prefix" {
  description = "Prefijo que identifica los contenedores de este entorno."
  type        = string
}

variable "network_name" {
  description = "Red existente, creada por el modulo network."
  type        = string
}

variable "chatwoot_image" {
  description = "Imagen publicada de Chatwoot identificada por digest."
  type        = string

  validation {
    condition     = can(regex("@sha256:[a-f0-9]{64}$", var.chatwoot_image))
    error_message = "Indicar una imagen con digest sha256 para fijar el contenido."
  }
}

variable "app_port" {
  description = "Puerto del anfitrion; Rails se publicara solo en 127.0.0.1."
  type        = number

  validation {
    condition     = var.app_port >= 1024 && var.app_port <= 65535 && floor(var.app_port) == var.app_port
    error_message = "Usar un puerto entero entre 1024 y 65535."
  }
}

# Conexiones internas recibidas del modulo persistence.
variable "postgres_host" {
  description = "Nombre DNS interno de PostgreSQL."
  type        = string
}

variable "postgres_port" {
  description = "Puerto interno de PostgreSQL."
  type        = number
}

variable "postgres_database" {
  description = "Nombre de la base de datos de Chatwoot."
  type        = string
}

variable "postgres_username" {
  description = "Usuario de PostgreSQL para Chatwoot."
  type        = string
}

variable "redis_host" {
  description = "Nombre DNS interno de Redis."
  type        = string
}

variable "redis_port" {
  description = "Puerto interno de Redis."
  type        = number
}

variable "storage_volume_name" {
  description = "Volumen de adjuntos creado por persistence; compute solo lo monta."
  type        = string
}

# Sin valores predeterminados: se proporcionan fuera del codigo.
# sensitive oculta salidas de terminal, pero no elimina valores del estado.
variable "secret_key_base" {
  description = "Clave privada de Rails, proporcionada externamente."
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.secret_key_base) >= 64
    error_message = "La clave de Rails debe tener al menos 64 caracteres."
  }
}

variable "postgres_password" {
  description = "La misma contrasena externa que recibe persistence para PostgreSQL."
  type        = string
  sensitive   = true
}

variable "redis_password" {
  description = "La misma contrasena externa que recibe persistence para Redis."
  type        = string
  sensitive   = true
}
