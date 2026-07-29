@echo off
:: ==============================================================================
::  Stop JARVIS Services on Windows
:: ==============================================================================
echo Stopping JARVIS background processes...

taskkill /FI "IMAGENAME eq python.exe" /FI "WINDOWTITLE eq *jarvis*" /F >nul 2>&1
wmic process where "commandline like '%%jarvis_launcher.py%%'" call terminate >nul 2>&1
wmic process where "commandline like '%%agent.py%%'" call terminate >nul 2>&1
wmic process where "commandline like '%%jarvis_bridge.py%%'" call terminate >nul 2>&1

echo JARVIS stopped successfully.
