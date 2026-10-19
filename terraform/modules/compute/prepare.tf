# Contenedor temporal: preparar la base y esperar a que termine.
# El modulo compute se conectara despues de persistence en la configuracion principal.
resource "docker_container" "prepare" {
  name       = "${var.project_prefix}-prepare"
  image      = docker_image.chatwoot.image_id
  entrypoint = ["bundle", "exec", "rails"]
  command    = ["db:chatwoot_prepare"]
  env        = local.app_environment

  # No debe permanecer ejecutandose ni reiniciarse tras terminar.
  attach         = true
  must_run       = false
  restart        = "no"
  rm             = false
  remove_volumes = false

  networks_advanced {
    name = var.network_name
  }

  volumes {
    volume_name    = var.storage_volume_name
    container_path = "/app/storage"
  }

  timeouts {
    create = "5m"
  }

  # Esperar al proceso no basta: una preparacion fallida debe detener apply.
  lifecycle {
    postcondition {
      condition     = self.exit_code == 0
      error_message = "La preparacion de Chatwoot termino con error. Revisar los logs del contenedor prepare."
    }
  }
}
