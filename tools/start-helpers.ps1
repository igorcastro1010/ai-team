function Assert-AiTeamPortAvailable {
    param([Parameter(Mandatory)][ValidateRange(1,65535)][int]$Port)
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
    try { $listener.Start() }
    catch { throw "Porta $Port ocupada. Encerre a outra instancia antes de iniciar o AI TEAM." }
    finally { $listener.Stop() }
}

function Wait-AiTeamApi {
    param(
        [Parameter(Mandatory)][int]$ProcessId,
        [string]$HealthUrl = 'http://127.0.0.1:8000/health',
        [Parameter(Mandatory)][string]$ExpectedVersion,
        [ValidateRange(1,60)][int]$TimeoutSeconds = 20
    )
    $healthUri = [uri]$HealthUrl
    if (-not $healthUri.IsLoopback -or $healthUri.Scheme -ne 'http' -or $healthUri.AbsolutePath -ne '/health') {
        throw 'Diagnostico de API aceita somente /health HTTP em loopback.'
    }
    $deadline = [Diagnostics.Stopwatch]::StartNew()
    while ($deadline.Elapsed.TotalSeconds -lt $TimeoutSeconds) {
        if (-not (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)) {
            throw 'API encerrou antes de ficar pronta. Verifique a instalacao Python e .data/api.stderr.log.'
        }
        try {
            $health = Invoke-RestMethod -Uri $healthUri -Method Get -TimeoutSec 1
            if ($health.status -eq 'ok' -and $health.version -eq $ExpectedVersion) { return }
        } catch { } # Never print exception/response content; it may contain private configuration.
        Start-Sleep -Milliseconds 100
    }
    throw 'API nao ficou pronta no prazo. Painel nao iniciado; verifique .data/api.stderr.log.'
}

function Assert-AiTeamChildRunning {
    param([Parameter(Mandatory)][Diagnostics.Process]$Process, [Parameter(Mandatory)][string]$Name)
    $Process.Refresh()
    if ($Process.HasExited) { throw "$Name encerrou durante a inicializacao. Verifique os logs em .data." }
}
