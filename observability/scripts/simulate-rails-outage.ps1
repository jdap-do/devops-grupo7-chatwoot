param(
    [string]$RailsContainer = 'devops-grupo7-e2-rails',
    [string]$GatewayUrl = 'http://127.0.0.1:3011/',
    [string]$PrometheusUrl = 'http://127.0.0.1:9090',
    [string]$ClientFile = (Join-Path (Split-Path $PSScriptRoot -Parent) '.runtime/chatwoot-client.json'),
    [ValidateRange(1,360)][int]$OutageSeconds = 360,
    [switch]$Execute
)
$ErrorActionPreference = 'Stop'
$raw = docker inspect --format '{{.Id}} {{.State.Running}}' $RailsContainer
if ($LASTEXITCODE -ne 0) { throw 'No se pudo identificar Rails.' }
$parts = $raw -split ' '
if ($parts[1] -ne 'true') { throw 'Rails debe estar activo antes de la prueba.' }
$containerId = $parts[0]
$client = Get-Content -LiteralPath $ClientFile -Raw | ConvertFrom-Json
$readUrl = $GatewayUrl.TrimEnd('/') + '/api/v1/accounts/' + $client.account_id + '/conversations'
$response = Invoke-WebRequest -Uri $readUrl -Headers @{api_access_token=$client.token} -TimeoutSec 10 -UseBasicParsing
if ($response.StatusCode -ne 200) { throw 'El gateway no devuelve 200 antes de la prueba.' }
$rules = Invoke-RestMethod -Uri ($PrometheusUrl.TrimEnd('/') + '/api/v1/rules') -TimeoutSec 10
$names = @($rules.data.groups | ForEach-Object { $_.rules } | ForEach-Object { $_.name })
$alertReady = $names -contains 'ChatwootAvailabilityBudgetBurn'
Write-Output "Rails activo y gateway HTTP 200. Alerta integrada: $alertReady"
if (-not $Execute) {
    Write-Output 'SOLO COMPROBACIÓN: no se detuvo ningún contenedor.'
    Write-Output 'La ejecución requiere alerta integrada, tráfico nominal previo y observación en Grafana.'
    return
}
if (-not $alertReady) { throw 'No se ejecuta el incidente: falta la alerta de disponibilidad acordada.' }
$query = [uri]::EscapeDataString('unal_chatwoot:http_telemetry_valid:ratio')
$telemetry = Invoke-RestMethod -Uri ($PrometheusUrl.TrimEnd('/') + '/api/v1/query?query=' + $query) -TimeoutSec 10
if ($telemetry.data.result.Count -ne 1 -or $telemetry.data.result[0].value[1] -ne '1') {
    throw 'No se ejecuta el incidente: la nueva medición HTTP no está validada por las reglas.'
}
$alerts = Invoke-RestMethod -Uri ($PrometheusUrl.TrimEnd('/') + '/api/v1/alerts') -TimeoutSec 10
if (@($alerts.data.alerts | Where-Object { $_.state -eq 'firing' }).Count -gt 0) {
    throw 'No se ejecuta el incidente mientras existan alertas activas.'
}
Write-Output 'Requiere generador de tráfico activo. No se modifican bases ni volúmenes.'
try {
    docker stop --time 10 $containerId | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo detener Rails; se intentará restaurarlo.' }
    Write-Output "Rails detenido durante un máximo de $OutageSeconds segundos."
    for ($elapsed = 0; $elapsed -lt $OutageSeconds; $elapsed += 10) {
        Start-Sleep -Seconds ([Math]::Min(10, $OutageSeconds - $elapsed))
    }
}
finally {
    docker start $containerId | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Restauración fallida. Iniciar manualmente: docker start $RailsContainer" }
    Write-Output 'Se solicitó el arranque del mismo contenedor Rails. Verificar HTTP y flujo funcional.'
}
