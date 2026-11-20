@echo off
title Helpdesk LAN - Install Windows service
rem ROOT = the main HelpdeskLAN folder (one level above this scripts folder)
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
cd /d "%ROOT%"
set SERVICE=HelpdeskLAN
set PORT=5000

net session >nul 2>&1
if errorlevel 1 (
    echo Please right-click this file and choose "Run as administrator".
    pause
    exit /b 1
)
if not exist "%ROOT%\venv\Scripts\waitress-serve.exe" (
    echo Please run scripts\install.bat first.
    pause
    exit /b 1
)

rem nssm.exe can be in the HelpdeskLAN folder, the scripts folder, or on PATH
set NSSM=nssm
if exist "%ROOT%\nssm.exe" set "NSSM=%ROOT%\nssm.exe"
if exist "%ROOT%\scripts\nssm.exe" set "NSSM=%ROOT%\scripts\nssm.exe"
"%NSSM%" version >nul 2>&1
if errorlevel 1 (
    echo NSSM was not found.
    echo Download it from https://nssm.cc/download, and copy win64\nssm.exe
    echo into this folder: %ROOT%
    pause
    exit /b 1
)

if not exist logs mkdir logs
"%NSSM%" stop %SERVICE% >nul 2>&1
"%NSSM%" remove %SERVICE% confirm >nul 2>&1

"%NSSM%" install %SERVICE% "%ROOT%\venv\Scripts\waitress-serve.exe" --listen=0.0.0.0:%PORT% --threads=8 app:app
"%NSSM%" set %SERVICE% AppDirectory "%ROOT%\app"
"%NSSM%" set %SERVICE% DisplayName "Helpdesk LAN"
"%NSSM%" set %SERVICE% Description "Office IT helpdesk web application (port %PORT%)"
"%NSSM%" set %SERVICE% Start SERVICE_AUTO_START
"%NSSM%" set %SERVICE% AppEnvironmentExtra PYTHONUNBUFFERED=1 HTTPS_ONLY=0
"%NSSM%" set %SERVICE% AppStdout "%ROOT%\logs\service.log"
"%NSSM%" set %SERVICE% AppStderr "%ROOT%\logs\service.log"
"%NSSM%" set %SERVICE% AppRotateFiles 1
"%NSSM%" set %SERVICE% AppRotateBytes 5000000
"%NSSM%" start %SERVICE%

echo.
"%NSSM%" status %SERVICE%
echo.
echo The helpdesk now runs in the background and starts automatically with Windows.
echo Do not also run start_server.bat (both use port %PORT%).
pause
