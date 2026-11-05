# Esta raíz crea únicamente infraestructura GCP. No cambia terraform/ ni su estado.
resource "google_project_service" "required" {
  for_each           = toset(["compute.googleapis.com", "iap.googleapis.com", "oslogin.googleapis.com"])
  service            = each.value
  disable_on_destroy = false
}

resource "google_compute_network" "lab" {
  name                    = "${var.name}-network"
  auto_create_subnetworks = false
  depends_on              = [google_project_service.required]
}

resource "google_compute_subnetwork" "lab" {
  name          = "${var.name}-subnet"
  ip_cidr_range = "10.77.0.0/24"
  network       = google_compute_network.lab.id
}

# SSH solo mediante IAP; no se abre el puerto 22 a toda Internet.
resource "google_compute_firewall" "iap_ssh" {
  name          = "${var.name}-iap-ssh"
  network       = google_compute_network.lab.name
  source_ranges = ["35.235.240.0/20"]
  target_tags   = [var.name]
  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
}

# Disco separado del sistema operativo y protegido frente a destroy accidental.
resource "google_compute_disk" "data" {
  name = "${var.name}-data"
  type = "pd-balanced"
  size = 60
  lifecycle {
    prevent_destroy = true
  }
  depends_on = [google_project_service.required]
}

resource "google_compute_instance" "lab" {
  name                      = var.name
  machine_type              = "e2-standard-2"
  desired_status            = var.desired_status
  allow_stopping_for_update = true
  deletion_protection       = true
  tags                      = [var.name]
  labels = {
    project     = "devops-grupo7"
    environment = "lab"
    delivery    = "4"
  }

  boot_disk {
    initialize_params {
      image = "ubuntu-os-cloud/ubuntu-2404-lts-amd64"
      size  = 20
      type  = "pd-balanced"
    }
  }

  attached_disk {
    source      = google_compute_disk.data.id
    device_name = "chatwoot-data"
    mode        = "READ_WRITE"
  }

  network_interface {
    subnetwork = google_compute_subnetwork.lab.id
    # IP efímera: permite descargar paquetes/imágenes sin contratar Cloud NAT.
    # Puede cambiar al detener/encender; no usarla como URL definitiva todavía.
    access_config {}
  }

  metadata = {
    enable-oslogin         = "TRUE"
    block-project-ssh-keys = "TRUE"
    startup-script         = file("${path.module}/startup.sh")
  }

  # Sin cuenta de servicio adjunta: la aplicación no necesita acceso a APIs GCP.
  shielded_instance_config {
    enable_secure_boot          = true
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }

  depends_on = [google_project_service.required]
}
