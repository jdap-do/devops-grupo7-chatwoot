terraform {
  required_version = ">= 1.16.6, < 2.0.0"

  # Configurar organización y workspace nuevos antes de init, sin reutilizar el local.
  cloud {
    hostname = "app.terraform.io"
  }

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "= 7.0.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}
