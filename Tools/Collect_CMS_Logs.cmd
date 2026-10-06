@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Collect_CMS_Logs.ps1" -OutputDirectory "%~dp0"
pause
