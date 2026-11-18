@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File autostart.ps1
pause
