@echo off
rem Backs up the database and uploads into the backups folder (keeps the newest 30).
rem To back up to another drive or NAS, uncomment and edit the next line:
rem set HELPDESK_BACKUP_DIR=D:\HelpdeskBackups
cd /d "%~dp0.."
if not exist logs mkdir logs
venv\Scripts\python.exe app\app.py backup >> logs\backup.log 2>&1
if errorlevel 1 (
    echo %date% %time% BACKUP FAILED >> logs\backup.log
    exit /b 1
)
exit /b 0
