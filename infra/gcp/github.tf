# Identidad de CI/CD separada de las cuentas de José y David.
# Los IDs numéricos proceden de la API pública de GitHub, consultada al preparar
# esta configuración: repositorio 1413754542, propietario 209687802.
variable "enable_github_deploy" {
  description = "Habilitar explícitamente la identidad de despliegue tras revisar el plan."
  type        = bool
  default     = false
}

resource "google_project_service" "deployment" {
  for_each = var.enable_github_deploy ? toset([
    "iam.googleapis.com", "iamcredentials.googleapis.com", "sts.googleapis.com"
  ]) : toset([])
  service            = each.value
  disable_on_destroy = false
}

resource "google_service_account" "deploy" {
  count        = var.enable_github_deploy ? 1 : 0
  account_id   = "grupo7-github-deploy"
  display_name = "Grupo 7 - GitHub Actions deployment"
  depends_on   = [google_project_service.deployment]
}

resource "google_iam_workload_identity_pool" "github" {
  count                     = var.enable_github_deploy ? 1 : 0
  workload_identity_pool_id = "grupo7-github"
  display_name              = "GitHub Grupo 7"
  depends_on                = [google_project_service.deployment]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  count                              = var.enable_github_deploy ? 1 : 0
  workload_identity_pool_id          = google_iam_workload_identity_pool.github[0].workload_identity_pool_id
  workload_identity_pool_provider_id = "github-main"
  attribute_mapping = {
    "google.subject"                = "assertion.sub"
    "attribute.repository_id"       = "assertion.repository_id"
    "attribute.repository_owner_id" = "assertion.repository_owner_id"
    "attribute.ref"                 = "assertion.ref"
  }
  attribute_condition = "assertion.repository_id == '1413754542' && assertion.repository_owner_id == '209687802' && assertion.ref == 'refs/heads/main'"
  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_member" "federation" {
  count              = var.enable_github_deploy ? 1 : 0
  service_account_id = google_service_account.deploy[0].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github[0].name}/attribute.repository_id/1413754542"
}

# Administración SSH solo sobre la VM del laboratorio; no Instance Admin global.
# sudo en esta VM permite controlar contenedores y leer su configuración privada.
resource "google_compute_instance_iam_member" "deploy_oslogin" {
  count         = var.enable_github_deploy ? 1 : 0
  instance_name = google_compute_instance.lab.name
  zone          = var.zone
  role          = "roles/compute.osAdminLogin"
  member        = "serviceAccount:${google_service_account.deploy[0].email}"
}

resource "google_iap_tunnel_instance_iam_member" "deploy_tunnel" {
  count    = var.enable_github_deploy ? 1 : 0
  instance = google_compute_instance.lab.name
  zone     = var.zone
  role     = "roles/iap.tunnelResourceAccessor"
  member   = "serviceAccount:${google_service_account.deploy[0].email}"
  condition {
    title      = "ssh-only"
    expression = "destination.port == 22"
  }
}

# gcloud necesita consultar proyecto e instancia para encontrar la VM y OS Login.
# Rol de lectura mínimo; no permite crear, borrar ni encender máquinas.
resource "google_project_iam_custom_role" "deploy_lookup" {
  count       = var.enable_github_deploy ? 1 : 0
  role_id     = "grupo7DeploymentLookup"
  title       = "Grupo 7 deployment lookup"
  permissions = ["compute.projects.get", "compute.instances.get", "compute.instances.list"]
  depends_on  = [google_project_service.deployment]
}

resource "google_project_iam_member" "deploy_lookup" {
  count   = var.enable_github_deploy ? 1 : 0
  project = var.project_id
  role    = google_project_iam_custom_role.deploy_lookup[0].name
  member  = "serviceAccount:${google_service_account.deploy[0].email}"
}

output "github_workload_identity_provider" {
  value = var.enable_github_deploy ? google_iam_workload_identity_pool_provider.github[0].name : null
}

output "github_service_account" {
  value = var.enable_github_deploy ? google_service_account.deploy[0].email : null
}
