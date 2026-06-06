@echo off
echo Stopping JARVIS...
taskkill /F /FI "WINDOWTITLE eq JARVIS - Agent" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq JARVIS - Token Server" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq JARVIS - Telegram Bot" >nul 2>&1
echo Done.
pause
