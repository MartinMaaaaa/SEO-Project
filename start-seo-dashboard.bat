@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_EXE="
for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "$cmd = Get-Command python,py -ErrorAction SilentlyContinue | Select-Object -First 1; if ($cmd) { $cmd.Source }"`) do set "PYTHON_EXE=%%I"

if not defined PYTHON_EXE (
  echo Python was not found. Install Python 3.11 or newer.
  pause
  exit /b 1
)

where node >nul 2>nul
if errorlevel 1 (
  echo Node.js was not found. Install Node.js 20.19 or newer.
  pause
  exit /b 1
)

if not exist "%~dp0apps\web\node_modules\vite\bin\vite.js" (
  echo Frontend dependencies are missing.
  echo Run: cd apps\web ^&^& npm.cmd install
  pause
  exit /b 1
)

"%PYTHON_EXE%" "%~dp0apps\api\launch_stack.py" %*
if errorlevel 1 (
  echo.
  echo The separated React/FastAPI stack did not start.
  echo Check data\logs\api.err.log and data\logs\web.err.log.
  pause
  exit /b 1
)

endlocal
