# Copilot Dashboard — launch both servers
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "`n  🚀 Copilot Dashboard" -ForegroundColor Cyan
Write-Host "  ────────────────────"
Write-Host "  Dashboard:  http://localhost:9090"
Write-Host "  Cleanup:    http://localhost:8111`n"

$cleanup = Start-Process python "$dir\cleanup.py" -PassThru -NoNewWindow
$dashboard = Start-Process python "-m http.server 9090 --directory $dir" -PassThru -NoNewWindow

try {
    Write-Host "  Press Ctrl+C to stop both servers`n"
    Wait-Process -Id $cleanup.Id, $dashboard.Id
} finally {
    Stop-Process -Id $cleanup.Id -ErrorAction SilentlyContinue
    Stop-Process -Id $dashboard.Id -ErrorAction SilentlyContinue
    Write-Host "`n  Stopped."
}
