module "network" {
  source         = "./modules/network"
  project_prefix = var.project_prefix
}

module "persistence" {
  source            = "./modules/persistence"
  project_prefix    = var.project_prefix
  network_name      = module.network.network_name
  postgres_password = var.postgres_password
  redis_password    = var.redis_password
}

module "compute" {
  source              = "./modules/compute"
  project_prefix      = var.project_prefix
  network_name        = module.network.network_name
  chatwoot_image      = var.chatwoot_image
  app_port            = var.app_port
  secret_key_base     = var.secret_key_base
  postgres_password   = var.postgres_password
  redis_password      = var.redis_password
  postgres_host       = module.persistence.postgres_host
  postgres_port       = module.persistence.postgres_port
  postgres_database   = module.persistence.postgres_database
  postgres_username   = module.persistence.postgres_username
  redis_host          = module.persistence.redis_host
  redis_port          = module.persistence.redis_port
  storage_volume_name = module.persistence.storage_volume_name

  # Esperar las comprobaciones de salud de PostgreSQL y Redis antes de preparar Rails.
  depends_on = [module.persistence]
}
