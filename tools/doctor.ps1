param([switch]$Json, [switch]$RequireHermes)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Execute tools\setup.ps1 primeiro.' }
$doctorArguments = @('-m', 'ai_team.doctor')
if ($Json) { $doctorArguments += '--json' }
if ($RequireHermes) { $doctorArguments += '--require-hermes' }
& $pythonPath @doctorArguments
exit $LASTEXITCODE
