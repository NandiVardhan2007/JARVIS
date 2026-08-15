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

:: Default to voice mode if no argument passed
set "MODE=voice"
if not "%~1"=="" set "MODE=%~1"

echo [*] Starting VISION in mode: %MODE%
echo [*] Tip: Run 'start.bat cli' for Text mode, or 'start.bat web' for Web mode.
echo.

"%PYTHON_EXE%" main.py --mode %MODE%

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] VISION stopped with an error code: %ERRORLEVEL%
    pause
)
