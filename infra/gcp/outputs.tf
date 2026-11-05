output "instance_name" {
  value = google_compute_instance.lab.name
}

output "zone" {
  value = var.zone
}

output "external_ip" {
  description = "IP efímera actual; no implica que la aplicación ya esté desplegada."
  value       = google_compute_instance.lab.network_interface[0].access_config[0].nat_ip
}

output "connect" {
  value = "gcloud compute ssh ${var.name} --project=${var.project_id} --zone=${var.zone} --tunnel-through-iap"
}
