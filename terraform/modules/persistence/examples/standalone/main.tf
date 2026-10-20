terraform {
  required_version = ">= 1.16.6, < 2.0.0"

  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "= 4.6.0"
    }
  }
}

# El endpoint se suministra externamente mediante DOCKER_HOST.
provider "docker" {}

variable "project_prefix" {
  description = "Prefijo exclusivo de esta prueba, distinto al del despliegue final."
  type        = string
  default     = "grupo7-david-persistence-test"
}

variable "postgres_password" {
  description = "Contraseña de laboratorio proporcionada mediante TF_VAR_postgres_password."
  type        = string
  sensitive   = true
}

variable "redis_password" {
  description = "Contraseña de laboratorio proporcionada mediante TF_VAR_redis_password."
  type        = string
  sensitive   = true
}

resource "docker_network" "test" {
  name     = "${var.project_prefix}-network"
  internal = true
}

module "persistence" {
  source = "../.."

  project_prefix    = var.project_prefix
  network_name      = docker_network.test.name
  postgres_password = var.postgres_password
  redis_password    = var.redis_password
}

output "connection" {
  description = "Parámetros sin contraseñas para inspeccionar esta prueba aislada."
  value = {
    postgres_host       = module.persistence.postgres_host
    postgres_port       = module.persistence.postgres_port
    postgres_database   = module.persistence.postgres_database
    postgres_username   = module.persistence.postgres_username
    redis_host          = module.persistence.redis_host
    redis_port          = module.persistence.redis_port
    storage_volume_name = module.persistence.storage_volume_name
  }
}
