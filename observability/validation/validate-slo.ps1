[CmdletBinding()]
param(
    [string]$PromtoolPath = 'promtool'
)

$ErrorActionPreference = 'Stop'
$promtoolCommand = (Get-Command -Name $PromtoolPath -ErrorAction Stop).Source
$versionOutput = & $promtoolCommand --version 2>&1
if ($LASTEXITCODE -ne 0) {
    throw 'No fue posible obtener la version de promtool.'
}
if (($versionOutput -join "`n") -notmatch '(?m)^promtool, version 3\.13\.5\b') {
    throw 'Estas validaciones requieren promtool 3.13.5, la version fijada para las pruebas.'
}

Push-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
try {
    & $promtoolCommand check rules 'prometheus/rules/slo-recording.yml'
    if ($LASTEXITCODE -ne 0) {
        throw 'La configuracion de recording rules no es valida.'
    }

    & $promtoolCommand test rules 'prometheus/tests/slo.test.yml'
    if ($LASTEXITCODE -ne 0) {
        throw 'Las pruebas de SLO no finalizaron correctamente.'
    }
}
finally {
    Pop-Location
}
