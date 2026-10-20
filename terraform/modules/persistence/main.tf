locals {
  postgres_database = "chatwoot_production"
  postgres_username = "postgres"
  postgres_port     = 5432
  redis_port        = 6379

  # Límites iniciales para laboratorio, pendientes de medición integrada.
  postgres_memory_mb = 512
  postgres_cpu_quota = 100000
  redis_memory_mb    = 256
  redis_cpu_quota    = 50000
  cpu_period         = 100000

  healthcheck_interval = "5s"
  healthcheck_timeout  = "5s"
  healthcheck_retries  = 20
  health_wait_seconds  = 180
}

resource "docker_volume" "postgres" {
  name = "${var.project_prefix}-postgres-data"
}

resource "docker_volume" "redis" {
  name = "${var.project_prefix}-redis-data"
}

resource "docker_volume" "storage" {
  name = "${var.project_prefix}-storage-data"
}

resource "docker_image" "postgres" {
  name         = var.postgres_image
  keep_locally = true
}

resource "docker_image" "redis" {
  name         = var.redis_image
  keep_locally = true
}

resource "docker_container" "postgres" {
  name              = "${var.project_prefix}-postgres"
  image             = docker_image.postgres.image_id
  restart           = "unless-stopped"
  privileged        = false
  ipc_mode          = "private"
  publish_all_ports = false
  memory            = local.postgres_memory_mb
  memory_swap       = local.postgres_memory_mb * 2
  cpu_period        = local.cpu_period
  cpu_quota         = local.postgres_cpu_quota
  wait              = true
  wait_timeout      = local.health_wait_seconds

  env = [
    "POSTGRES_DB=${local.postgres_database}",
    "POSTGRES_USER=${local.postgres_username}",
    "POSTGRES_PASSWORD=${var.postgres_password}",
  ]

  networks_advanced {
    name = var.network_name
  }

  volumes {
    volume_name    = docker_volume.postgres.name
    container_path = "/var/lib/postgresql/data"
  }

  healthcheck {
    test = [
      "CMD-SHELL",
      "PGPASSWORD=\"$POSTGRES_PASSWORD\" psql -h \"$HOSTNAME\" -U \"$POSTGRES_USER\" -d \"$POSTGRES_DB\" -v ON_ERROR_STOP=1 -c 'SELECT 1' >/dev/null",
    ]
    interval = local.healthcheck_interval
    timeout  = local.healthcheck_timeout
    retries  = local.healthcheck_retries
  }
}

resource "docker_container" "redis" {
  name              = "${var.project_prefix}-redis"
  image             = docker_image.redis.image_id
  restart           = "unless-stopped"
  privileged        = false
  ipc_mode          = "private"
  publish_all_ports = false
  memory            = local.redis_memory_mb
  memory_swap       = local.redis_memory_mb * 2
  cpu_period        = local.cpu_period
  cpu_quota         = local.redis_cpu_quota
  wait              = true
  wait_timeout      = local.health_wait_seconds

  env = ["REDIS_PASSWORD=${var.redis_password}"]
  command = [
    "sh", "-c",
    "exec redis-server --appendonly yes --requirepass \"$REDIS_PASSWORD\"",
  ]

  networks_advanced {
    name = var.network_name
  }

  volumes {
    volume_name    = docker_volume.redis.name
    container_path = "/data"
  }

  healthcheck {
    test = [
      "CMD-SHELL",
      "REDISCLI_AUTH=\"$REDIS_PASSWORD\" redis-cli ping | grep -qx PONG",
    ]
    interval = local.healthcheck_interval
    timeout  = local.healthcheck_timeout
    retries  = local.healthcheck_retries
  }
}
