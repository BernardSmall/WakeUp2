$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = Join-Path $Root "venv\Scripts\python.exe"
$Index = Join-Path $Root "frontend\dist\index.html"
$Url = "http://127.0.0.1:8000/"
$HealthUrl = "http://127.0.0.1:8000/api/health"
$LogDir = Join-Path $Root "data-local"

function Test-TcpPort {
    $Client = [Net.Sockets.TcpClient]::new()
    try {
        $Result = $Client.BeginConnect("127.0.0.1", 8000, $null, $null)
        if (-not $Result.AsyncWaitHandle.WaitOne(800)) { return $false }
        $Client.EndConnect($Result)
        return $true
    } catch {
        return $false
    } finally {
        $Client.Close()
    }
}

function Test-WakeUp2 {
    try {
        $Health = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 2
        $Home = Invoke-WebRequest -Uri $Url -TimeoutSec 2
        return $Health.status -eq "ok" -and $Health.version -eq "1.0.0" -and $Home.Content.Contains("WakeUp2")
    } catch {
        return $false
    }
}

if (-not (Test-Path $Python) -or -not (Test-Path $Index)) {
    Write-Host "WakeUp2 is not set up. Run setup-windows.bat first." -ForegroundColor Red
    exit 1
}

if (Test-TcpPort) {
    if (Test-WakeUp2) {
        Write-Host "WakeUp2 is already running at $Url."
        Start-Process $Url
        exit 0
    }
    Write-Host "Port 8000 is occupied by another application. WakeUp2 will not stop it." -ForegroundColor Red
    exit 1
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Stdout = Join-Path $LogDir "server-$Stamp.log"
$Stderr = Join-Path $LogDir "server-$Stamp-error.log"
$Server = $null
try {
    Write-Host "Starting WakeUp2 at $Url ..."
    $Server = Start-Process -FilePath $Python `
        -ArgumentList "-m uvicorn backend.main:app --host 127.0.0.1 --port 8000" `
        -WorkingDirectory $Root `
        -RedirectStandardOutput $Stdout `
        -RedirectStandardError $Stderr `
        -PassThru

    $Ready = $false
    for ($Attempt = 0; $Attempt -lt 60; $Attempt++) {
        Start-Sleep -Seconds 1
        $Server.Refresh()
        if ($Server.HasExited) { break }
        if (Test-WakeUp2) { $Ready = $true; break }
    }
    if (-not $Ready) {
        Write-Host "WakeUp2 did not become ready. Diagnostic output:" -ForegroundColor Red
        if (Test-Path $Stderr) { Get-Content $Stderr -Tail 30 }
        if (Test-Path $Stdout) { Get-Content $Stdout -Tail 30 }
        exit 1
    }

    Write-Host "WakeUp2 is ready. Opening $Url"
    Start-Process $Url
    Write-Host "Keep this window open while monitoring. Press Ctrl+C here to stop WakeUp2."
    while ($true) {
        $Server.Refresh()
        if ($Server.HasExited) {
            Write-Host "WakeUp2 stopped. See $Stderr for diagnostics."
            break
        }
        Start-Sleep -Seconds 1
    }
} finally {
    if ($Server) {
        $Server.Refresh()
        if (-not $Server.HasExited) {
            try {
                Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/monitoring/stop" -Method Post -TimeoutSec 6 | Out-Null
                $Deadline = (Get-Date).AddSeconds(5)
                do {
                    $Status = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/status" -TimeoutSec 2
                    if (-not $Status.monitoring) { break }
                    Start-Sleep -Milliseconds 200
                } while ((Get-Date) -lt $Deadline)
                if ($Status.monitoring) {
                    Write-Warning "Camera shutdown did not confirm before process cleanup."
                }
            } catch {
                Write-Warning "Could not confirm graceful camera shutdown; Windows will release resources when the server exits."
            }
            $Server.Kill()
            $Server.WaitForExit()
        }
    }
}
