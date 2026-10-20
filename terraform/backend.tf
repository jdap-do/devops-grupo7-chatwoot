terraform {
  # TF_CLOUD_ORGANIZATION y TF_WORKSPACE se proporcionan en el proceso local.
  # El workspace debe existir y tener execution_mode = local antes de init.
  cloud {
    hostname = "app.terraform.io"
  }
}
