@echo off
title Helpdesk LAN - Schedule daily backup
cd /d "%~dp0.."
net session >nul 2>&1
if errorlevel 1 (
    echo Please right-click this file and choose "Run as administrator".
    pause
    exit /b 1
)
if not exist logs mkdir logs
schtasks /Create /F /SC DAILY /ST 23:00 /RU SYSTEM /TN "HelpdeskLAN Backup" /TR "\"%~dp0backup.bat\""
if errorlevel 1 (
    echo Could not create the scheduled task.
    pause
    exit /b 1
)
echo.
echo Daily backup scheduled at 23:00. Running a first backup now...
call "%~dp0backup.bat"
if errorlevel 1 (echo First backup FAILED - see logs\backup.log) else (echo First backup done - see the backups folder.)
pause
