variable "project_id" {
  description = "Proyecto GCP con prueba y Compute Engine habilitados."
  type        = string
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "zone" {
  type    = string
  default = "us-central1-a"
}

variable "name" {
  description = "Prefijo exclusivo de los recursos de Entrega 4."
  type        = string
  default     = "grupo7-chatwoot"
}

variable "desired_status" {
  description = "RUNNING durante trabajo; TERMINATED significa detenida, no eliminada."
  type        = string
  default     = "RUNNING"
  validation {
    condition     = contains(["RUNNING", "TERMINATED"], var.desired_status)
    error_message = "Usar RUNNING o TERMINATED."
  }
}
