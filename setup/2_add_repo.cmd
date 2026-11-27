@echo off
chcp 65001 >nul
set /p REPO=Repository (KanimisoIT/name): 
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0sekisho-setup.ps1" -Repo "%REPO%"
pause
