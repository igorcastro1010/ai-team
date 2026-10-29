$ErrorActionPreference = 'Stop'
$Host.UI.RawUI.WindowTitle = 'AI TEAM - Vercel: token oculto'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
& .venv\Scripts\python.exe -m ai_team.vercel_access configure
if ($LASTEXITCODE -ne 0) { throw 'Vercel nao configurada. Nao envie o token no chat.' }
