# Servidor web: acceso local al panel y al widget.
resource "docker_container" "rails" {
  name       = "${var.project_prefix}-rails"
  image      = docker_image.chatwoot.image_id
  entrypoint = ["bundle", "exec", "rails"]
  command    = ["s", "-p", "3000", "-b", "0.0.0.0"]
  ipc_mode   = "private"
  env        = local.app_environment
  restart    = "unless-stopped"

  networks_advanced {
    name = var.network_name
  }

  ports {
    internal = 3000
    external = var.app_port
    ip       = "127.0.0.1"
  }

  volumes {
    volume_name    = var.storage_volume_name
    container_path = "/app/storage"
  }

  remove_volumes = false

  # El postcondition de prepare bloquea este recurso si la tarea falla.
  depends_on = [docker_container.prepare]
}

# Trabajador de colas: no sirve el panel ni publica puertos.
resource "docker_container" "sidekiq" {
  name       = "${var.project_prefix}-sidekiq"
  image      = docker_image.chatwoot.image_id
  entrypoint = ["bundle", "exec", "sidekiq"]
  command    = ["-C", "config/sidekiq.yml"]
  ipc_mode   = "private"
  env        = local.app_environment
  restart    = "unless-stopped"

  networks_advanced {
    name = var.network_name
  }

  volumes {
    volume_name    = var.storage_volume_name
    container_path = "/app/storage"
  }

  remove_volumes = false

  depends_on = [docker_container.prepare]
}
