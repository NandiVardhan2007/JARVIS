@echo off
:: ==============================================================================
::  JARVIS — One-Command Windows Launcher (Backend + Bridge + Flutter Frontend)
:: ==============================================================================
title JARVIS - AI Assistant
cd /d "%~dp0"

echo ==============================================================
echo                JARVIS - AI Assistant (Windows)
echo ==============================================================

:: Check Python venv
if not exist "venv\Scripts\python.exe" (
    echo [start] Virtual environment not found. Creating venv...
    python -m venv venv
    venv\Scripts\python.exe -m pip install --upgrade pip
    venv\Scripts\python.exe -m pip install -r requirements.txt
)

:: Clear log file
if exist "JARVIS.log" del "JARVIS.log"
echo [start] Reset JARVIS.log — recording clean logs for this session...

:: 1. Start WebSocket Bridge in Background
echo [start] (1/3) Starting bridge on ws://127.0.0.1:8765 ...
start /B venv\Scripts\python.exe jarvis_bridge.py > jarvis_bridge.log 2>&1

:: 2. Launch Flutter Frontend in Background
where flutter >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [start] (2/3) Launching Flutter face frontend...
    start /B cmd /c "cd /d jarvis_face && flutter run -d windows"
) else (
    echo [start] (2/3) Flutter CLI not found on PATH. Skipping Flutter GUI launch.
)

:: 3. Launch JARVIS Backend
echo [start] (3/3) Booting JARVIS backend...
echo ==============================================================
set "JARVIS_HUD_HIDDEN=1"
venv\Scripts\python.exe jarvis_launcher.py

pause
