# Datos sintéticos para comprobar políticas; no es un root Terraform desplegable.
variable "postgres_password" {
  type      = string
  sensitive = true
}

resource "docker_container" "postgres" {
  env = ["POSTGRES_PASSWORD=${var.postgres_password}"]
}

output "postgres_host" {
  value = docker_container.postgres.name
}
