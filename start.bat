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

:: Default directly to Voice mode (Mic listening -> STT -> LLM -> Tools -> Cartesia TTS)
set "MODE=voice"
if not "%~1"=="" set "MODE=%~1"

echo [*] Launching VISION in direct Voice Mode...
echo [*] Speak into your microphone to interact with VISION.
echo.

"%PYTHON_EXE%" main.py --mode %MODE%


:END
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] VISION stopped with code: %ERRORLEVEL%
    pause
)


