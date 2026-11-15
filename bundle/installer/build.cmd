@echo off
setlocal DisableDelayedExpansion
set "ISCC="
for %%I in (ISCC.exe) do set "ISCC=%%~$PATH:I"
if defined ISCC goto compile
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if defined ISCC goto compile
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if defined ISCC goto compile
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if defined ISCC goto compile
echo ERROR: ISCC.exe not found. Install Inno Setup 6 or add its directory to PATH.
exit /b 1

:compile
if defined DPO_SIGN_CMD goto signed_compile
"%ISCC%" "%~dp0dpo-giga-agent.iss"
if errorlevel 1 exit /b %errorlevel%
echo Output: unsigned.
goto checksum

:signed_compile
"%ISCC%" /DSIGN "/Sdposign=%DPO_SIGN_CMD%" "%~dp0dpo-giga-agent.iss"
if errorlevel 1 exit /b %errorlevel%
echo Output: signed.

:checksum
set "PSModulePath="
set "DPO_SETUP_EXE=%~dp0..\dist\dpo-giga-agent-setup.exe"
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -Command "try { $ErrorActionPreference = 'Stop'; $stream = [IO.File]::OpenRead($env:DPO_SETUP_EXE); $sha = [Security.Cryptography.SHA256]::Create(); try { $hash = [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() } finally { $stream.Dispose(); $sha.Dispose() }; [IO.File]::WriteAllText($env:DPO_SETUP_EXE + '.sha256', $hash + '  dpo-giga-agent-setup.exe' + [char]10, [Text.Encoding]::ASCII); Write-Output $hash; exit 0 } catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 }"
exit /b %errorlevel%
