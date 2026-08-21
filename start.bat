@echo off
title VISION Autonomous AI Voice & OS System
cls

echo ===================================================
echo           VISION AI - SYSTEM LAUNCHER
echo ===================================================
echo.

:: Detect Python executable in .venv or system PATH
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
    echo [*] Using virtual environment: .venv
) else (
    set "PYTHON_EXE=python"
    echo [!] .venv not detected. Using system Python.
)

:: Parse mode from argument (default: web)
set "MODE=web"
if not "%~1"=="" set "MODE=%~1"

:: ── WEB MODE: Launch FastAPI server + open browser dashboard ──
if /i "%MODE%"=="web" (
    echo [*] Starting VISION Web Dashboard...
    echo [*] Server: http://localhost:8000
    echo [*] Opening browser automatically...
    echo.

    :: Free port 8000 if previously occupied
    for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do (
        taskkill /f /pid %%a >nul 2>&1
    )

    :: Open browser after a short delay (gives server time to boot)
    start "" cmd /c "timeout /t 3 /nobreak >nul && start http://localhost:8000"

    :: Start uvicorn web server (blocking)
    "%PYTHON_EXE%" -m uvicorn vision.gateways.web.server:app --host 127.0.0.1 --port 8000
    goto END
)

:: ── VOICE MODE: Direct microphone listening ──
if /i "%MODE%"=="voice" (
    echo [*] Launching VISION in direct Voice Mode...
    echo [*] Speak into your microphone to interact with VISION.
    echo.
    "%PYTHON_EXE%" main.py --mode voice
    goto END
)

:: ── WAKE MODE: Hands-free "Hey VISION" trigger ──
if /i "%MODE%"=="wake" (
    echo [*] Launching VISION in Wake-Word Mode...
    echo [*] Say "Hey VISION" to activate.
    echo.
    "%PYTHON_EXE%" main.py --mode wake
    goto END
)

:: ── CLI MODE: Interactive text terminal ──
if /i "%MODE%"=="cli" (
    echo [*] Launching VISION in CLI Mode...
    echo.
    "%PYTHON_EXE%" main.py --mode cli
    goto END
)

echo [!] Unknown mode: %MODE%
echo [*] Available modes: web, voice, wake, cli
echo [*] Usage: start.bat [mode]
echo.

:END
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] VISION stopped with code: %ERRORLEVEL%
    pause
)
