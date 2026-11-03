param(
    [string]$PostgresContainer = 'devops-grupo7-e2-postgres',
    [string]$RedisContainer = 'devops-grupo7-e2-redis'
)
$ErrorActionPreference = 'Stop'
$target = Join-Path (Split-Path $PSScriptRoot -Parent) '.env.prober'
if (Test-Path -LiteralPath $target) {
    throw 'La configuración local ya existe. Se conserva sin sobrescribir.'
}
function Read-ContainerEnvironment([string]$ContainerName) {
    $raw = docker inspect --format '{{json .Config.Env}}' $ContainerName
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo consultar el contenedor configurado.' }
    $result = @{}
    foreach ($entry in ($raw | ConvertFrom-Json)) {
        $parts = $entry -split '=', 2
        $result[$parts[0]] = $parts[1]
    }
    return $result
}
$pgSettings = Read-ContainerEnvironment $PostgresContainer
$redisSettings = Read-ContainerEnvironment $RedisContainer
foreach ($key in @('POSTGRES_DB', 'POSTGRES_USER', 'POSTGRES_PASSWORD')) {
    if (-not $pgSettings[$key]) { throw "Falta el parámetro $key en PostgreSQL." }
}
if (-not $redisSettings['REDIS_PASSWORD']) { throw 'Falta REDIS_PASSWORD en Redis.' }
$lines = @(
    "PGHOST=$PostgresContainer",
    "PGDATABASE=$($pgSettings['POSTGRES_DB'])",
    "PGUSER=$($pgSettings['POSTGRES_USER'])",
    "PGPASSWORD=$($pgSettings['POSTGRES_PASSWORD'])",
    "REDIS_HOST=$RedisContainer",
    "REDIS_PASSWORD=$($redisSettings['REDIS_PASSWORD'])"
)
foreach ($line in $lines) {
    if ($line.Contains("`r") -or $line.Contains("`n")) { throw 'La configuración no admite valores multilínea.' }
}
[System.IO.File]::WriteAllLines($target, $lines, [System.Text.UTF8Encoding]::new($false))
Write-Output 'Configuración del prober creada localmente; no se mostraron credenciales.'
