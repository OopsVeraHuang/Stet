@echo off
cd /d "%~dp0"
where python >nul 2>nul
if %errorlevel% equ 0 (
  python -X utf8 -m continuity --open
) else (
  py -3 -X utf8 -m continuity --open
)
pause
