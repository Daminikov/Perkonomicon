@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "PY="
where python >nul 2>nul && set "PY=python"
if not defined PY (where py >nul 2>nul && set "PY=py -3")
if not defined PY (
  echo.
  echo Python 3 not found in PATH. Install Python or add it to PATH, then run this file again.
  echo.
  pause
  exit /b 1
)

echo.
echo   Skyrim perk database: starting local server...
echo   (to stop: close this window or press Ctrl+C)
echo.

%PY% app.py

echo.
echo Server stopped.
pause
