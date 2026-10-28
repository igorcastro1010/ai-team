$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
& .venv\Scripts\python.exe -m ai_team.github_setup
if ($LASTEXITCODE -ne 0) { throw 'GitHub App não configurada. Nenhum segredo deve ser enviado no chat.' }
