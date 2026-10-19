# Esta primera fase conecta solo la red.
# Compute y persistence se incorporaran cuando esten implementados.
module "network" {
  source         = "./modules/network"
  project_prefix = var.project_prefix
}
