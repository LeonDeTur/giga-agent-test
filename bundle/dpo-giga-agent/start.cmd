@echo off
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0launch.ps1" -Command start %*
if errorlevel 1 (
  pause
  exit /b 1
)

