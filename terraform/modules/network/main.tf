# Docker asigna una subred disponible; no se fijan direcciones del computador.
# Los modulos de aplicacion y datos recibiran el nombre de esta red.
resource "docker_network" "application" {
  name   = "${var.project_prefix}-network"
  driver = "bridge"

  labels {
    label = "unal.group"
    value = "7"
  }

  labels {
    label = "unal.delivery"
    value = "2"
  }
}
