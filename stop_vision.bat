@echo off
:: ==============================================================================
::  Stop VISION Services on Windows
:: ==============================================================================
echo Stopping VISION background processes...

taskkill /FI "IMAGENAME eq python.exe" /FI "WINDOWTITLE eq *vision*" /F >nul 2>&1
wmic process where "commandline like '%%vision_launcher.py%%'" call terminate >nul 2>&1
wmic process where "commandline like '%%agent.py%%'" call terminate >nul 2>&1
wmic process where "commandline like '%%vision_bridge.py%%'" call terminate >nul 2>&1

echo VISION stopped successfully.
