$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
if (-not (Get-Command graphify -ErrorAction SilentlyContinue)) { throw 'Graphify opcional não instalado.' }
# Apenas AST: não consome API de LLM, não instala hooks, não escreve fora deste projeto.
graphify . --code-only
if ($LASTEXITCODE -ne 0) { throw 'Graphify não conseguiu extrair o projeto.' }
