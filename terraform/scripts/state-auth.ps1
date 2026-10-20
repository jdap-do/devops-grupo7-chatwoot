#requires -Version 5.1

[CmdletBinding()]
param([switch]$SaveForCurrentUser)

$ErrorActionPreference = 'Stop'
if ($SaveForCurrentUser -and [Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
  throw 'El guardado con DPAPI solo se admite en Windows. Use el token únicamente en el proceso en otros sistemas.'
}

$secureToken = Read-Host 'Token de usuario HCP Terraform (no se mostrará)' -AsSecureString
if ($secureToken.Length -eq 0) { throw 'El token no puede estar vacío.' }
$tokenValue = [System.Net.NetworkCredential]::new('', $secureToken).Password
if ($tokenValue -match '\s' -or @($tokenValue.ToCharArray() | Where-Object { [char]::IsControl($_) }).Count -gt 0) {
  throw 'El token contiene espacios o caracteres de control. Copie solo su valor y péguelo con clic derecho o Shift+Insert en el prompt oculto.'
}
$env:TF_TOKEN_app_terraform_io = $tokenValue
$env:TFE_TOKEN = $env:TF_TOKEN_app_terraform_io

try {
  Invoke-RestMethod -Uri 'https://app.terraform.io/api/v2/account/details' -Method Get -Headers @{
    Authorization = "Bearer $tokenValue"
    Accept        = 'application/vnd.api+json'
  } | Out-Null
} catch {
  Remove-Item Env:TF_TOKEN_app_terraform_io, Env:TFE_TOKEN -ErrorAction SilentlyContinue
  if ($_.Exception.Response -and [int]$_.Exception.Response.StatusCode -eq 401) {
    throw 'HCP Terraform no autorizó este token. Genere un token de usuario en app.terraform.io/app/settings/tokens y repita. No se guardó el nuevo valor.'
  }
  throw
}

if ($SaveForCurrentUser) {
  $tokenPath = Join-Path $PSScriptRoot '../.hcp-token.local'
  $secureToken | Export-Clixml -LiteralPath $tokenPath
  Write-Output 'Token guardado cifrado con DPAPI para el usuario/equipo actuales, excluido de Git.'
}
Write-Output 'Autenticación cargada en las variables del proceso actual para Terraform CLI y el provider tfe.'
