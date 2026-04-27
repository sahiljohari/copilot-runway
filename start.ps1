# Copilot Dashboard — launch both servers
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Ensure Python can print emojis on Windows (avoids cp1252 UnicodeEncodeError)
$env:PYTHONIOENCODING = "utf-8"

# Verify Python is available
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "`n  ❌ Python is not installed or not in PATH." -ForegroundColor Red
    exit 1
}

# Kill any stale processes on the required ports
foreach ($port in @(9090, 8111)) {
    $pids = netstat -ano | Select-String ":$port\s.*LISTENING" |
        ForEach-Object { ($_ -split '\s+')[-1] } | Select-Object -Unique
    foreach ($procId in $pids) {
        if ($procId -and $procId -ne '0') {
            Write-Host "  ⚠ Killing stale process $procId on port $port" -ForegroundColor Yellow
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        }
    }
}

Write-Host "`n  🚀 Copilot Dashboard" -ForegroundColor Cyan
Write-Host "  ────────────────────"
Write-Host "  Dashboard:  http://localhost:9090"
Write-Host "  Cleanup:    http://localhost:8111`n"

$cleanup = Start-Process python "$dir\cleanup.py" -PassThru -NoNewWindow
$dashboard = Start-Process python "-m http.server 9090 --directory $dir" -PassThru -NoNewWindow

# Wait briefly and verify both servers started
Start-Sleep -Seconds 2
if ($dashboard.HasExited) {
    Write-Host "  ❌ Dashboard server failed to start." -ForegroundColor Red
    Stop-Process -Id $cleanup.Id -ErrorAction SilentlyContinue
    exit 1
}
if ($cleanup.HasExited) {
    Write-Host "  ❌ Cleanup server failed to start." -ForegroundColor Red
    Stop-Process -Id $dashboard.Id -ErrorAction SilentlyContinue
    exit 1
}

try {
    Write-Host "  Press Ctrl+C to stop both servers`n"
    Wait-Process -Id $cleanup.Id, $dashboard.Id
} finally {
    Stop-Process -Id $cleanup.Id -ErrorAction SilentlyContinue
    Stop-Process -Id $dashboard.Id -ErrorAction SilentlyContinue
    Write-Host "`n  Stopped."
}
