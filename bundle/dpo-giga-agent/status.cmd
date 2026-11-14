@echo off
chcp 65001 >nul
set "PSModulePath="
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0launch.ps1" -Command status %*
if errorlevel 1 (
  pause
  exit /b 1
)

