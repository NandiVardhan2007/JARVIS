@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ==============================================================
echo                 JARVIS - AI Assistant
echo ==============================================================
echo.
echo Initializing JARVIS for the first time...
echo This will set up an isolated environment for JARVIS to run.
echo.

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in your system PATH.
    echo Please install Python 3.10 or 3.11 from python.org and check "Add to PATH".
    pause
    exit /b
)

:: Create Virtual Environment if it doesn't exist
if not exist "venv" (
    echo [1/3] Creating an isolated virtual environment...
    python -m venv venv
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b
    )
)

:: Activate the environment
call venv\Scripts\activate.bat

:: Check if requirements are installed by checking for livekit
python -c "import livekit" >nul 2>&1
if %errorlevel% neq 0 (
    echo [2/3] Downloading required AI models and dependencies...
    echo This may take a few minutes depending on your internet connection.
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to install dependencies. Check your internet connection.
        pause
        exit /b
    )
) else (
    echo [2/3] Dependencies already installed!
)

echo.
echo [3/3] Booting JARVIS...
echo ==============================================================
:: Launch JARVIS dynamically via Watchdog
python watchdog.py

pause
