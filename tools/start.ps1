$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Execute tools\setup.ps1 primeiro.' }
$dataPath = Join-Path $projectRoot '.data'
New-Item -ItemType Directory -Path $dataPath -Force | Out-Null
$apiProcess = Start-Process -FilePath $pythonPath -ArgumentList '-m', 'uvicorn', 'ai_team.main:app', '--host', '127.0.0.1', '--port', '8000' -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $dataPath 'api.stdout.log') -RedirectStandardError (Join-Path $dataPath 'api.stderr.log')
try {
    Set-Location -LiteralPath $projectRoot
    Write-Host 'AI TEAM: abra http://localhost:3000. Ctrl+C encerra o painel e a API iniciada por este script.'
    npm.cmd run dev
} finally {
    if (-not $apiProcess.HasExited) { Stop-Process -Id $apiProcess.Id }
}
