@echo off
title Helpdesk LAN - Server (close this window to stop)
cd /d "%~dp0.."
set PORT=5000

if not exist venv\Scripts\waitress-serve.exe (
    echo Please run scripts\install.bat first.
    pause
    exit /b 1
)
if not exist data mkdir data
if not exist uploads mkdir uploads

set PYTHONUNBUFFERED=1
set HTTPS_ONLY=0

echo Helpdesk is starting on port %PORT% ...
echo Employees open:  http://THIS-SERVER-IP:%PORT%
echo Admin panel:     http://THIS-SERVER-IP:%PORT%/admin
echo.
echo Keep this window open. Closing it stops the helpdesk.
echo (For permanent use, run scripts\install_service.bat instead.)
echo.
rem The server must run from inside the app folder so it can find app.py
cd app
..\venv\Scripts\waitress-serve.exe --listen=0.0.0.0:%PORT% --threads=8 app:app
pause
