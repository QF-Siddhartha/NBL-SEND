@echo off
title Helpdesk LAN - Create administrator
cd /d "%~dp0.."
if not exist venv\Scripts\python.exe (
    echo Please run scripts\install.bat first.
    pause
    exit /b 1
)
echo Create a new admin, or reset the password of an existing admin.
echo The password is hidden while you type. Use at least 12 characters.
echo.
venv\Scripts\python.exe app\app.py create-admin
pause
