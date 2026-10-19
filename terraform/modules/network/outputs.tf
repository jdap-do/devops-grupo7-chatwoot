output "network_name" {
  description = "Nombre de la red que utilizaran compute y persistence."
  value       = docker_network.application.name
}
