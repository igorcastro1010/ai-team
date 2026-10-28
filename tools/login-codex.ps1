$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) { throw 'Execute setup.ps1 primeiro.' }
Write-Host 'Login próprio do executor AI TEAM. Credenciais no cofre do Windows; a sessão do Desktop não será copiada.'
& .venv\Scripts\python.exe -m ai_team.codex_access login
if ($LASTEXITCODE -ne 0) { throw 'Login não concluído. O executor permanece bloqueado.' }
