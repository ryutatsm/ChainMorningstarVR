@echo off
setlocal
rem The PowerShell script already defaults to its own directory.
rem A quoted %%~dp0 ends in a backslash and can corrupt a native argument.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Collect_CMS_Logs.ps1"
set "CMS_COLLECT_EXIT=%ERRORLEVEL%"
if not "%CMS_COLLECT_EXIT%"=="0" echo Log collection failed. Please send a screenshot of the error above.
if /i not "%~1"=="--no-pause" pause
exit /b %CMS_COLLECT_EXIT%
