$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Execute tools\setup.ps1 primeiro.' }
$dataPath = Join-Path $projectRoot '.data'
New-Item -ItemType Directory -Path $dataPath -Force | Out-Null
$apiProcess = Start-Process -FilePath $pythonPath -ArgumentList '-m', 'uvicorn', 'ai_team.main:app', '--host', '127.0.0.1', '--port', '8000' -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $dataPath 'api.stdout.log') -RedirectStandardError (Join-Path $dataPath 'api.stderr.log')
$workerProcess = $null
$schedulerProcess = $null
try {
    $workerProcess = Start-Process -FilePath $pythonPath -ArgumentList '-m', 'ai_team.worker' -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $dataPath 'worker.stdout.log') -RedirectStandardError (Join-Path $dataPath 'worker.stderr.log')
    $schedulerProcess = Start-Process -FilePath $pythonPath -ArgumentList '-m', 'ai_team.scheduler' -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $dataPath 'scheduler.stdout.log') -RedirectStandardError (Join-Path $dataPath 'scheduler.stderr.log')
    Set-Location -LiteralPath $projectRoot
    Write-Host 'AI TEAM: abra http://localhost:3000. Ctrl+C encerra painel, API, worker e scheduler deste script.'
    npm.cmd run dev
} finally {
    if ($schedulerProcess -and -not $schedulerProcess.HasExited) { Stop-Process -Id $schedulerProcess.Id }
    if (-not $apiProcess.HasExited) { Stop-Process -Id $apiProcess.Id }
    if ($workerProcess -and -not $workerProcess.HasExited) {
        & "$env:SystemRoot\System32\taskkill.exe" /PID $workerProcess.Id /T /F | Out-Null
    }
}
