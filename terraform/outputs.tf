output "network_name" {
  description = "Nombre de la red declarada para la aplicacion y sus datos."
  value       = module.network.network_name
}

output "app_url" {
  description = "Direccion local del panel de Chatwoot."
  value       = module.compute.app_url
}
