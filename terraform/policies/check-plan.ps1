#requires -Version 7.2

[CmdletBinding()]
param([ValidateSet('persistence', 'root')][string]$Configuration = 'persistence')

$ErrorActionPreference = 'Stop'
$repoPath = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$image = 'openpolicyagent/conftest:v0.65.0@sha256:afa510df6d4562ebe24fb3e457da6f6d6924124140a13b51b950cc6cb1d25525'
$policyMount = "type=bind,source=$PSScriptRoot,target=/policies,readonly"
$tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$workDir = Join-Path $tempRoot "grupo7-terraform-ci-$([guid]::NewGuid().ToString('N'))"
$modulePath = Join-Path $workDir 'terraform/modules/persistence'
$examplePath = if ($Configuration -eq 'root') {
  Join-Path $workDir 'terraform'
} else {
  Join-Path $modulePath 'examples/standalone'
}
$planPath = Join-Path $workDir 'security.tfplan'
$savedEnvironment = @{}
foreach ($name in @('TF_VAR_postgres_password', 'TF_VAR_redis_password', 'TF_VAR_secret_key_base', 'TF_VAR_project_prefix', 'TF_VAR_app_port', 'TF_VAR_chatwoot_image', 'DOCKER_HOST', 'TF_DATA_DIR', 'TF_WORKSPACE')) {
  $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}

function Assert-NativeSuccess([string]$Step) {
  if ($LASTEXITCODE -ne 0) { throw "$Step failed with exit code $LASTEXITCODE" }
}

try {
  New-Item -ItemType Directory -Path $examplePath | Out-Null
  # Se copian solo código y lockfile: nunca estados, credenciales, backend root o cachés.
  foreach ($module in @('persistence', 'network', 'compute')) {
    $destination = Join-Path $workDir "terraform/modules/$module"
    New-Item -ItemType Directory -Path $destination -Force | Out-Null
    Get-ChildItem -LiteralPath (Join-Path $repoPath "terraform/modules/$module") -Filter '*.tf' |
      Copy-Item -Destination $destination
  }
  $sourceExample = if ($Configuration -eq 'root') {
    Join-Path $repoPath 'terraform'
  } else {
    Join-Path $repoPath 'terraform/modules/persistence/examples/standalone'
  }
  Get-ChildItem -LiteralPath $sourceExample -Filter '*.tf' |
    Where-Object { $_.Name -ne 'backend.tf' -and $_.Name -notlike '*.local.tf' } |
    Copy-Item -Destination $examplePath
  Copy-Item -LiteralPath (Join-Path $sourceExample '.terraform.lock.hcl') -Destination $examplePath

  $env:DOCKER_HOST = docker context inspect --format '{{.Endpoints.docker.Host}}'
  Assert-NativeSuccess 'Docker endpoint'
  $env:TF_DATA_DIR = Join-Path $workDir '.terraform'
  $env:TF_WORKSPACE = 'default'
  $env:TF_VAR_postgres_password = [Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
  $env:TF_VAR_redis_password = [Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
  $env:TF_VAR_secret_key_base = [Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(64))
  $env:TF_VAR_project_prefix = "grupo7-ci-$([guid]::NewGuid().ToString('N').Substring(0, 12))"
  $env:TF_VAR_app_port = '3010'
  $env:TF_VAR_chatwoot_image = 'ghcr.io/jdap-do/devops-grupo7-chatwoot@sha256:a07e19d2e177ca98acd3b00460e8366bc24bbc0268b0dcceb6566ed4516005e9'

  terraform "-chdir=$examplePath" init -backend=false -input=false -lockfile=readonly -no-color
  Assert-NativeSuccess 'Terraform init'
  terraform "-chdir=$examplePath" validate -no-color
  Assert-NativeSuccess 'Terraform validate'
  terraform "-chdir=$examplePath" plan -input=false -no-color "-out=$planPath"
  Assert-NativeSuccess 'Terraform plan'

  $planJson = terraform "-chdir=$examplePath" show -json $planPath
  Assert-NativeSuccess 'Terraform show'
  $plan = $planJson | ConvertFrom-Json
  if ($Configuration -eq 'persistence' -and $plan.resource_changes.Count -ne 8) {
    throw 'Expected the 8 resources of the isolated example.'
  }
  if ($Configuration -eq 'root') {
    $moduleNames = @($plan.configuration.root_module.module_calls.PSObject.Properties.Name)
    $missing = @('network', 'persistence', 'compute') | Where-Object { $_ -notin $moduleNames }
    if ($missing) {
      throw "Root pendiente de integracion: faltan modulos $($missing -join ', '). Un plan solo de red no demuestra el despliegue completo."
    }
  }
  foreach ($resource in $plan.resource_changes) {
    if (($resource.change.actions -join ',') -ne 'create') {
      throw "An empty-state plan must only create resources: $($resource.address)"
    }
  }

  $planJson | docker run --rm --network none -i --mount $policyMount $image test --parser json --policy /policies/plan -
  Assert-NativeSuccess 'Conftest plan policies'
  Write-Output "PASS: isolated $Configuration empty-state plan ($($plan.resource_changes.Count) creations) accepted; no apply or personal state used."
} finally {
  foreach ($name in $savedEnvironment.Keys) {
    [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name], 'Process')
  }
  if (Test-Path -LiteralPath $workDir) {
    $resolvedWorkDir = [IO.Path]::GetFullPath($workDir)
    $tempPrefix = $tempRoot.TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
    if (-not $resolvedWorkDir.StartsWith($tempPrefix, [StringComparison]::OrdinalIgnoreCase)) {
      throw 'Refusing to remove a verification directory outside the temporary root.'
    }
    Remove-Item -LiteralPath $resolvedWorkDir -Recurse -Force
  }
}
