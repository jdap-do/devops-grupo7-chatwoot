variable "project_prefix" {
  description = "Prefijo exclusivo del despliegue para contenedores y volúmenes."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{0,47}$", var.project_prefix))
    error_message = "Use entre 1 y 48 caracteres: inicial minúscula, números y guiones."
  }
}

variable "network_name" {
  description = "Nombre de la red Docker existente creada por el módulo network."
  type        = string

  validation {
    condition     = length(trimspace(var.network_name)) > 0
    error_message = "network_name no puede estar vacío."
  }
}

variable "postgres_password" {
  description = "Contraseña externa del usuario PostgreSQL; se aplica al inicializar un volumen vacío."
  type        = string
  sensitive   = true

  validation {
    condition     = length(trimspace(var.postgres_password)) > 0
    error_message = "postgres_password es obligatorio y no puede estar vacío."
  }
}

variable "redis_password" {
  description = "Contraseña externa para la autenticación de Redis."
  type        = string
  sensitive   = true

  validation {
    condition     = length(trimspace(var.redis_password)) > 0
    error_message = "redis_password es obligatorio y no puede estar vacío."
  }
}

variable "postgres_image" {
  description = "Imagen PostgreSQL 16 con pgvector, fijada por digest de índice multiarquitectura."
  type        = string
  default     = "pgvector/pgvector:pg16@sha256:7b822b0aac60967beb1ea5e576b8602c94c300a157d187f385ae3e0da199b90a"
}

variable "redis_image" {
  description = "Imagen Redis 7.4, fijada por digest de índice multiarquitectura."
  type        = string
  default     = "redis:7.4-alpine@sha256:858f009f9709ce576febc734aa78b8f6d624b82571f9ddb6bda4377c833b3499"
}
