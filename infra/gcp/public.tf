variable "enable_public_web" {
  description = "Abrir HTTP/HTTPS para Caddy una vez preparada la autenticacion y el DNS."
  type        = bool
  default     = false
}

resource "google_compute_firewall" "public_web" {
  count         = var.enable_public_web ? 1 : 0
  name          = "${var.name}-public-web"
  network       = google_compute_network.lab.name
  source_ranges = ["0.0.0.0/0"]
  target_tags   = [var.name]
  allow {
    protocol = "tcp"
    ports    = ["80", "443"]
  }
}
