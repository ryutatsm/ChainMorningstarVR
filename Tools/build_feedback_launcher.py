"""Build the self-contained CMD from the readable PowerShell source."""
from pathlib import Path
import argparse

ROOT=Path(__file__).resolve().parent
BOOTSTRAP=r'''@echo off
setlocal
set "CMS_FEEDBACK_SELF=%~f0"
set "CMS_FEEDBACK_NO_PAUSE=0"
if /i "%~1"=="--no-pause" set "CMS_FEEDBACK_NO_PAUSE=1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$s=[IO.File]::ReadAllText($env:CMS_FEEDBACK_SELF); $marker=[char]35+' CMS_EMBEDDED_POWERSHELL'; & ([scriptblock]::Create($s.Substring($s.LastIndexOf($marker)+$marker.Length))) -OutputDirectory $env:CMS_FEEDBACK_OUTPUT -OpenFolder:($env:CMS_FEEDBACK_NO_PAUSE -ne '1')"
set "CMS_COLLECT_EXIT=%ERRORLEVEL%"
if not "%CMS_COLLECT_EXIT%"=="0" echo Log collection failed. Please send a screenshot of the error above.
if not "%CMS_FEEDBACK_NO_PAUSE%"=="1" pause
exit /b %CMS_COLLECT_EXIT%
# CMS_EMBEDDED_POWERSHELL
'''
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    content=BOOTSTRAP+(ROOT/'Collect_CMS_Logs.ps1').read_text(encoding='utf-8-sig')
    path=ROOT/'Collect_CMS_Logs.cmd'
    if args.check:
        assert path.read_text(encoding='utf-8-sig')==content, 'CMD embedded collector differs from PS1 source'
        print('COLLECTOR_EMBEDDED_SOURCE_PASS')
    else: path.write_text(content,encoding='utf-8')
