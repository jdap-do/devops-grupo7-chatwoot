$ErrorActionPreference = 'Stop'
$directory = Join-Path (Split-Path $PSScriptRoot -Parent) '.runtime'
New-Item -ItemType Directory -Path $directory -Force | Out-Null
$target = Join-Path $directory 'grafana-admin-password.txt'
if (Test-Path -LiteralPath $target) {
    Write-Output 'Se conserva la contraseña local existente. No se cambia el usuario de Grafana.'
    exit 0
}
$bytes = [byte[]]::new(24)
$generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
try { $generator.GetBytes($bytes) } finally { $generator.Dispose() }
$password = [Convert]::ToBase64String($bytes)
[System.IO.File]::WriteAllText($target, $password, [System.Text.UTF8Encoding]::new($false))
Write-Output 'Contraseña inicial creada en .runtime/grafana-admin-password.txt (excluida de Git).'
