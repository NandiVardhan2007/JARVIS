@echo off
:: ==============================================================================
::  VISION — Standalone Virtual Air Mouse Tester
:: ==============================================================================
title VISION - Virtual Air Mouse Test
cd /d "%~dp0"

echo ==============================================================
echo        VISION - Standalone Virtual Air Mouse Test
echo ==============================================================

if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found. Please run start.bat first.
    pause
    exit /b 1
)

venv\Scripts\python.exe run_air_mouse.py

pause
