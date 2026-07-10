@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_EXE="
for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "$cmd = Get-Command python,py -ErrorAction SilentlyContinue | Select-Object -First 1; if ($cmd) { $cmd.Source }"`) do set "PYTHON_EXE=%%I"

if not defined PYTHON_EXE (
  echo Python was not found in PATH.
  pause
  exit /b 1
)

"%PYTHON_EXE%" "%~dp0apps\seo_dashboard\stop_dashboard.py"
if errorlevel 1 (
  echo.
  echo The SEO dashboard could not be stopped cleanly.
  pause
  exit /b 1
)

endlocal
