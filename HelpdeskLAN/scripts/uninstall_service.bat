@echo off
title Helpdesk LAN - Remove Windows service
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
net session >nul 2>&1
if errorlevel 1 (
    echo Please right-click this file and choose "Run as administrator".
    pause
    exit /b 1
)
set NSSM=nssm
if exist "%ROOT%\nssm.exe" set "NSSM=%ROOT%\nssm.exe"
if exist "%ROOT%\scripts\nssm.exe" set "NSSM=%ROOT%\scripts\nssm.exe"
"%NSSM%" stop HelpdeskLAN
"%NSSM%" remove HelpdeskLAN confirm
echo Service removed. Your data in the data and uploads folders is untouched.
pause
