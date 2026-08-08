# ==============================================================================
#  VISION — One-Command PowerShell Launcher (Backend + Bridge + Flutter UI)
# ==============================================================================

Write-Host "==============================================================" -ForegroundColor Cyan
Write-Host "                VISION - AI Assistant (Windows)" -ForegroundColor Cyan
Write-Host "==============================================================" -ForegroundColor Cyan

Set-Location $PSScriptRoot

$venvPython = ".\venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "[start] Creating virtual environment 'venv'..." -ForegroundColor Yellow
    python -m venv venv
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -r requirements.txt
}

# Reset Log
if (Test-Path "VISION.log") {
    Remove-Item "VISION.log" -Force
}
Write-Host "[start] Reset VISION.log — recording clean logs for this session..." -ForegroundColor Green

# 1. Start WebSocket Bridge
Write-Host "[start] (1/3) Starting bridge on ws://127.0.0.1:8765 ..." -ForegroundColor Yellow
$bridgeProcess = Start-Process $venvPython -ArgumentList "vision_bridge.py" -PassThru -NoNewWindow

# 2. Launch React UI Frontend
$reactProcess = $null
if (Get-Command npm -ErrorAction SilentlyContinue) {
    Write-Host "[start] (2/3) Launching React UI Frontend (http://localhost:5173)..." -ForegroundColor Yellow
    $reactProcess = Start-Process npm -ArgumentList "run", "dev" -WorkingDirectory ".\vision_react" -PassThru -NoNewWindow
} else {
    Write-Host "[start] (2/3) Node/npm not found on PATH. Skipping React GUI." -ForegroundColor DarkYellow
}

# 3. Boot Backend
Write-Host "[start] (3/3) Booting VISION backend..." -ForegroundColor Yellow
Write-Host "==============================================================" -ForegroundColor Cyan
$env:VISION_HUD_HIDDEN = "1"

try {
    & $venvPython vision_launcher.py
} finally {
    Write-Host "`n[start] Shutting down VISION services..." -ForegroundColor Red
    if ($bridgeProcess -and -not $bridgeProcess.HasExited) {
        Stop-Process -Id $bridgeProcess.Id -Force -ErrorAction SilentlyContinue
    }
    if ($reactProcess -and -not $reactProcess.HasExited) {
        Stop-Process -Id $reactProcess.Id -Force -ErrorAction SilentlyContinue
    }
}
