@echo off
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0sekisho-setup.ps1" -Bootstrap
pause
