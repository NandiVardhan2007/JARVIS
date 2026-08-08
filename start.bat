@echo off
:: ==============================================================================
::  VISION — One-Command Windows Launcher (Backend + Bridge + Flutter Frontend)
:: ==============================================================================
title VISION - AI Assistant
cd /d "%~dp0"

echo ==============================================================
echo                VISION - AI Assistant (Windows)
echo ==============================================================

:: Check Python venv
if not exist "venv\Scripts\python.exe" (
    echo [start] Virtual environment not found. Creating venv...
    python -m venv venv
    venv\Scripts\python.exe -m pip install --upgrade pip
    venv\Scripts\python.exe -m pip install -r requirements.txt
)

:: Clear log file
if exist "VISION.log" del "VISION.log"
echo [start] Reset VISION.log - recording clean logs for this session...

:: 1. Start WebSocket Bridge in Background
echo [start] 1 of 3: Starting bridge on ws://127.0.0.1:8765 ...
start /B venv\Scripts\python.exe vision_bridge.py > vision_bridge.log 2>&1

:: 2. Launch React Frontend in Background
where npm >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [start] 2 of 3: Launching React UI frontend at http://localhost:5173 ...
    start /B cmd /c "cd /d vision_react && npm run dev"
) else (
    echo [start] 2 of 3: Node.js/npm not found on PATH. Skipping React GUI launch.
)

:: 3. Launch VISION Backend
echo [start] 3 of 3: Booting VISION backend...
echo ==============================================================
set "VISION_HUD_HIDDEN=1"
venv\Scripts\python.exe vision_launcher.py

pause
