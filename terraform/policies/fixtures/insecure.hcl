# Caso deliberadamente inseguro, con un marcador que no es una contraseña real.
variable "postgres_password" {
  default = "NOT_A_REAL_SECRET"
}

resource "docker_container" "postgres" {
  env = ["POSTGRES_PASSWORD=NOT_A_REAL_SECRET"]
}

output "postgres_password" {
  value = var.postgres_password
}
