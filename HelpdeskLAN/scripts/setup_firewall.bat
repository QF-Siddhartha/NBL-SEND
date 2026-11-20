@echo off
title Helpdesk LAN - Firewall rule
net session >nul 2>&1
if errorlevel 1 (
    echo Please right-click this file and choose "Run as administrator".
    pause
    exit /b 1
)
echo This allows office computers to open the helpdesk on port 5000.
echo Enter your office network range. Example: if the server IP is 192.168.1.100,
echo the range is usually 192.168.1.0/24
echo.
set /p SUBNET=Office network range: 
if "%SUBNET%"=="" (
    echo No range entered. Nothing changed.
    pause
    exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "Remove-NetFirewallRule -DisplayName 'Helpdesk LAN Portal' -ErrorAction SilentlyContinue; New-NetFirewallRule -DisplayName 'Helpdesk LAN Portal' -Direction Inbound -Protocol TCP -LocalPort 5000 -RemoteAddress '%SUBNET%' -Action Allow | Out-Null; Write-Host 'Firewall rule created for %SUBNET%'"
pause
