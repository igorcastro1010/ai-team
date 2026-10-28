$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
& .venv\Scripts\python.exe -m pytest services/api/tests -q
if ($LASTEXITCODE -ne 0) { throw 'Testes da API falharam.' }
& .venv\Scripts\python.exe -m ruff check services/api
if ($LASTEXITCODE -ne 0) { throw 'Lint Python falhou.' }
npm.cmd run lint
if ($LASTEXITCODE -ne 0) { throw 'Lint do painel falhou.' }
npm.cmd run typecheck
if ($LASTEXITCODE -ne 0) { throw 'Typecheck falhou.' }
npm.cmd run build
if ($LASTEXITCODE -ne 0) { throw 'Build falhou.' }
npm.cmd run test:e2e
if ($LASTEXITCODE -ne 0) { throw 'E2E falhou.' }
