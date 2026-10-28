$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw 'Instale uv (https://docs.astral.sh/uv/) e tente novamente.'
}
uv venv --python 3.12 .venv
if ($LASTEXITCODE -ne 0) { throw 'Falha ao criar ambiente Python.' }
uv pip sync --python .venv\Scripts\python.exe services\api\requirements.lock
if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar dependências Python.' }
uv pip install --python .venv\Scripts\python.exe --no-deps -e services/api
if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar API.' }
npm.cmd ci
if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar painel.' }
& .venv\Scripts\python.exe -m ai_team.cli create-owner --username admin
if ($LASTEXITCODE -ne 0) { throw 'Falha ao cadastrar proprietário. Confira a mensagem acima.' }
Write-Host 'Instalação concluída. Execute .\tools\start.ps1'
