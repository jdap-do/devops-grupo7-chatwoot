$ErrorActionPreference = 'Stop'
$repoPath = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$image = 'openpolicyagent/conftest:v0.65.0@sha256:afa510df6d4562ebe24fb3e457da6f6d6924124140a13b51b950cc6cb1d25525'
$mount = "type=bind,source=$repoPath,target=/project,readonly"

function Invoke-Conftest {
  param(
    [string[]]$Arguments,
    [int]$ExpectedExit = 0,
    [string]$RequiredCode
  )

  $result = & docker run --rm --network none --mount $mount $image @Arguments
  $actualExit = $LASTEXITCODE
  $result | Write-Output
  if ($actualExit -ne $ExpectedExit) {
    throw "Conftest: expected exit $ExpectedExit; got $actualExit."
  }
  if ($RequiredCode -and ($result -join "`n") -notmatch [regex]::Escape($RequiredCode)) {
    throw "The rejected fixture must report $RequiredCode."
  }
}

foreach ($kind in @('plan', 'source')) {
  Invoke-Conftest -Arguments @('verify', '--policy', "/project/terraform/policies/$kind")
}

$files = @(Get-ChildItem -LiteralPath (Join-Path $repoPath 'terraform') -Filter '*.tf' -Recurse |
  Where-Object { $_.FullName -notmatch '[/\\]\.terraform[/\\]' } |
  ForEach-Object { '/project/' + $_.FullName.Substring($repoPath.Length + 1).Replace('\', '/') })
if ($files.Count -eq 0) { throw 'No Terraform source files found.' }
Invoke-Conftest -Arguments (@('test', '--parser', 'hcl2', '--policy', '/project/terraform/policies/source') + $files)

foreach ($kind in @('plan', 'source')) {
  $extension = if ($kind -eq 'plan') { 'plan.json' } else { 'hcl' }
  $parser = if ($kind -eq 'plan') { 'json' } else { 'hcl2' }
  $requiredCode = if ($kind -eq 'plan') { 'P003:' } else { 'S001:' }
  $arguments = @('test', '--parser', $parser, '--policy', "/project/terraform/policies/$kind")
  Invoke-Conftest -Arguments ($arguments + "/project/terraform/policies/fixtures/secure.$extension")
  Write-Output "Expected rejection: insecure $kind fixture"
  Invoke-Conftest -Arguments ($arguments + "/project/terraform/policies/fixtures/insecure.$extension") -ExpectedExit 1 -RequiredCode $requiredCode
}

Write-Output 'PASS: policy suites, current HCL and accepted/rejected fixtures.'
# El último fixture debe fallar; no propagar ese código esperado al runner pwsh.
exit 0
