param([string]$RailsContainer = 'devops-grupo7-e2-rails', [string]$UserEmail = 'admin@example.com')
$ErrorActionPreference = 'Stop'
if ($UserEmail -notmatch '^[a-zA-Z0-9@._+\-]+$') { throw 'Formato de correo no admitido.' }
$directory = Join-Path (Split-Path $PSScriptRoot -Parent) '.runtime'
New-Item -ItemType Directory -Path $directory -Force | Out-Null
$target = Join-Path $directory 'chatwoot-client.json'
if (Test-Path -LiteralPath $target) { throw 'Ya existe la configuración del cliente; no se sobrescribe.' }
# Reads an existing token and test identifiers; never creates users or rotates tokens.
$ruby = "u=User.find_by!(email: '$UserEmail'); a=u.accounts.first!; c=a.conversations.first!; puts '__CLIENT__'+{token:u.access_token.token,account_id:a.id,conversation_id:c.display_id}.to_json"
$output = docker exec $RailsContainer bundle exec rails runner $ruby
if ($LASTEXITCODE -ne 0) { throw 'No se pudo leer el usuario, token y conversación existentes.' }
$line = @($output | Where-Object { $_.StartsWith('__CLIENT__') })
if ($line.Count -ne 1) { throw 'Respuesta de configuración inesperada.' }
$json = $line[0].Substring(10)
$parsed = $json | ConvertFrom-Json
if (-not $parsed.token -or -not $parsed.account_id -or -not $parsed.conversation_id) { throw 'Faltan datos del cliente.' }
[System.IO.File]::WriteAllText($target, $json, [System.Text.UTF8Encoding]::new($false))
Write-Output 'Cliente autenticado configurado localmente. No se muestran ni versionan tokens.'
