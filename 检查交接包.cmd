@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (set "PROTO_PY=python") else (set "PROTO_PY=py -3")
%PROTO_PY% -X utf8 -m unittest discover -s tests -v
if errorlevel 1 goto failed
%PROTO_PY% -X utf8 tools/package.py verify
if errorlevel 1 goto failed
echo Offline checks passed.
pause
exit /b 0
:failed
echo Check failed. Please keep the error above for review.
pause
exit /b 1
