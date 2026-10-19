# Descargar la imagen publicada, sin volver a construir Chatwoot.
# keep_locally conserva la imagen al retirar este recurso de Terraform.
resource "docker_image" "chatwoot" {
  name         = var.chatwoot_image
  keep_locally = true
}

# Configuracion comun para prepare, Rails y Sidekiq.
# Los secretos llegan desde entradas sensibles, nunca como valores escritos aqui.
locals {
  app_url = "http://localhost:${var.app_port}"

  app_environment = [
    "RAILS_ENV=production",
    "NODE_ENV=production",
    "INSTALLATION_ENV=docker",
    "FRONTEND_URL=${local.app_url}",
    "FORCE_SSL=false",
    "ENABLE_ACCOUNT_SIGNUP=false",
    "ACTIVE_STORAGE_SERVICE=local",
    "RAILS_LOG_TO_STDOUT=true",
    "SECRET_KEY_BASE=${var.secret_key_base}",
    "POSTGRES_HOST=${var.postgres_host}",
    "POSTGRES_PORT=${var.postgres_port}",
    "POSTGRES_DATABASE=${var.postgres_database}",
    "POSTGRES_USERNAME=${var.postgres_username}",
    "POSTGRES_PASSWORD=${var.postgres_password}",
    "REDIS_URL=redis://${var.redis_host}:${var.redis_port}",
    "REDIS_PASSWORD=${var.redis_password}",
  ]
}
