# ==============================================================================
#  Stop JARVIS Services on Windows PowerShell
# ==============================================================================
Write-Host "Stopping JARVIS background processes..." -ForegroundColor Yellow

$procs = Get-CimInstance Win32_Process | Where-Object { 
    $_.CommandLine -like "*jarvis_launcher.py*" -or 
    $_.CommandLine -like "*agent.py*" -or 
    $_.CommandLine -like "*jarvis_bridge.py*"
}

foreach ($p in $procs) {
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    Write-Host "Stopped process ID $($p.ProcessId) ($($p.Name))" -ForegroundColor Gray
}

Write-Host "JARVIS stopped successfully." -ForegroundColor Green
