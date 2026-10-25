@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  .venv\Scripts\python.exe -X utf8 -m continuity --open
  goto done
)
where python >nul 2>nul
if %errorlevel% equ 0 (
  python -X utf8 -m continuity --open
) else (
  py -3 -X utf8 -m continuity --open
)
:done
pause
