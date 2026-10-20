#requires -Version 5.1

[CmdletBinding()]
param(
  [Parameter(Mandatory)][string]$Organization,
  [Parameter(Mandatory)][string]$Workspace,
  [string]$ConfigurationDirectory = (Join-Path $PSScriptRoot '..')
)

$ErrorActionPreference = 'Stop'
if (-not $env:TF_TOKEN_app_terraform_io) {
  throw 'Cargue TF_TOKEN_app_terraform_io en el proceso local, sin pegar el token en el comando.'
}

$configurationPath = (Resolve-Path -LiteralPath $ConfigurationDirectory).Path
$localStatePath = Join-Path $configurationPath 'terraform.tfstate'
if (Test-Path -LiteralPath $localStatePath) {
  $localState = Get-Content -LiteralPath $localStatePath -Raw | ConvertFrom-Json
  if ($localState -and @($localState.resources).Count -gt 0) {
    throw 'Existe estado local con recursos. Siga primero la migración con workspace explícito y TF_WORKSPACE sin definir en docs/entrega2/estado-credenciales.md; este script selecciona un workspace remoto y no debe usarse para migrar el estado default.'
  }
}
if (-not (Test-Path -LiteralPath (Join-Path $configurationPath 'backend.tf')) -and
    -not (Test-Path -LiteralPath (Join-Path $configurationPath 'state-backend.local.tf'))) {
  throw 'La configuración seleccionada no contiene el archivo de conexión cloud del proyecto.'
}

$uri = 'https://app.terraform.io/api/v2/organizations/{0}/workspaces/{1}' -f
  [uri]::EscapeDataString($Organization), [uri]::EscapeDataString($Workspace)
$headers = @{ Authorization = "Bearer $env:TF_TOKEN_app_terraform_io" }
$response = Invoke-RestMethod -Uri $uri -Headers $headers -Method Get
$attributes = $response.data.attributes
if ($attributes.'execution-mode' -ne 'local') {
  throw 'El workspace debe configurarse en modo Local mediante el bootstrap antes de init.'
}

$binding = $attributes.description | ConvertFrom-Json
if ($binding.project -ne 'grupo7-entrega2' -or
    -not [string]::Equals($binding.host_name, [Environment]::MachineName, [StringComparison]::OrdinalIgnoreCase)) {
  throw 'El workspace no está asociado a este equipo. No inicialice el estado de otro anfitrión.'
}

$repoPath = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$configurations = @{
  'root' = Join-Path $repoPath 'terraform'
  'persistence-example' = Join-Path $repoPath 'terraform/modules/persistence/examples/standalone'
}
if (-not $configurations.ContainsKey([string]$binding.configuration) -or
    -not [string]::Equals($configurationPath, $configurations[$binding.configuration], [StringComparison]::OrdinalIgnoreCase)) {
  throw 'La configuración no corresponde a este workspace. El ejemplo y el despliegue completo usan estados separados.'
}

$endpoint = docker context inspect $binding.docker_context --format '{{.Endpoints.docker.Host}}'
if ($LASTEXITCODE -ne 0) { throw 'No se pudo consultar el endpoint Docker.' }

# Selección persistente durante esta sesión para plan/apply posteriores.
$env:TF_CLOUD_ORGANIZATION = $Organization
$env:TF_WORKSPACE = $Workspace
$env:DOCKER_HOST = $endpoint
Write-Output "Workspace verificado: $Organization/$Workspace; Local; equipo $($binding.host_name); propietario $($binding.owner)."

# Solo conexión nueva o ya migrada. No se fuerza la copia ni se hace apply.
terraform "-chdir=$configurationPath" init
if ($LASTEXITCODE -ne 0) { throw 'Falló la inicialización o migración. Conserve el estado y revise el error.' }
