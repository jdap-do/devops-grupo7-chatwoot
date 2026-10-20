output "postgres_host" {
  description = "Nombre DNS interno de PostgreSQL; depende de su creación saludable."
  value       = docker_container.postgres.name
}

output "postgres_port" {
  description = "Puerto interno PostgreSQL, sin publicación al anfitrión."
  value       = local.postgres_port
}

output "postgres_database" {
  description = "Base inicial de Chatwoot."
  value       = local.postgres_database
}

output "postgres_username" {
  description = "Usuario PostgreSQL del laboratorio."
  value       = local.postgres_username
}

output "redis_host" {
  description = "Nombre DNS interno de Redis; depende de su creación saludable."
  value       = docker_container.redis.name
}

output "redis_port" {
  description = "Puerto interno Redis, sin publicación al anfitrión."
  value       = local.redis_port
}

output "storage_volume_name" {
  description = "Volumen de adjuntos que compute debe montar en /app/storage."
  value       = docker_volume.storage.name
}
