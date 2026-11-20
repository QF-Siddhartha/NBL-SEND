@echo off
title Helpdesk LAN - Installation
rem Work from the main HelpdeskLAN folder (one level above this scripts folder)
cd /d "%~dp0.."
echo =====================================
echo   HELPDESK LAN INSTALLATION
echo =====================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not installed or not on PATH.
    echo Install Python 3.12 or newer from python.org and tick "Add python.exe to PATH".
    pause
    exit /b 1
)
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 (
    echo Your Python version is too old. Please install Python 3.12 or newer.
    pause
    exit /b 1
)
python --version

if not exist venv\Scripts\python.exe (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo Could not create the virtual environment.
        pause
        exit /b 1
    )
)

echo Installing packages (internet needed for this step only)...
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r app\requirements.txt
if errorlevel 1 (
    echo Installation failed. Check your internet connection and try again.
    pause
    exit /b 1
)

if not exist data mkdir data
if not exist uploads mkdir uploads
if not exist backups mkdir backups
if not exist logs mkdir logs
venv\Scripts\python.exe app\app.py init-db

echo.
echo Installation completed.
echo Next step: run scripts\create_admin.bat to create the administrator account.
pause
