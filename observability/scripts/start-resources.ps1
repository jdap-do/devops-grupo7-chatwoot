param([string]$Prefix = 'devops-grupo7-e2', [string]$PythonExecutable = 'python')
$ErrorActionPreference = 'Stop'
$directory = Join-Path (Split-Path $PSScriptRoot -Parent) '.runtime'
New-Item -ItemType Directory -Path $directory -Force | Out-Null
$pidFile = Join-Path $directory 'collector.pid'
if (Test-Path -LiteralPath $pidFile) {
    $previousId = [int](Get-Content -LiteralPath $pidFile)
    if (Get-Process -Id $previousId -ErrorAction SilentlyContinue) {
        throw 'Existe un proceso con el PID registrado. Revisarlo antes de iniciar otro colector.'
    }
}
$executable = (Get-Command $PythonExecutable -ErrorAction Stop).Source
$script = Join-Path $PSScriptRoot 'collect-resources.py'
$arguments = @('-u', ('"' + $script + '"'), '--prefix', $Prefix)
$process = Start-Process -FilePath $executable -ArgumentList $arguments -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $directory 'collector.log') `
    -RedirectStandardError (Join-Path $directory 'collector-error.log')
[System.IO.File]::WriteAllText($pidFile, [string]$process.Id)
Write-Output "Colector de memoria iniciado. PID: $($process.Id). Registros en .runtime/."
