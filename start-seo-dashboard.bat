@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_EXE="
for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "$cmd = Get-Command python,py -ErrorAction SilentlyContinue | Select-Object -First 1; if ($cmd) { $cmd.Source }"`) do set "PYTHON_EXE=%%I"

if not defined PYTHON_EXE (
  echo Python was not found in PATH.
  echo Install Python 3.11 or newer, then try again.
  pause
  exit /b 1
)

"%PYTHON_EXE%" "%~dp0apps\seo_dashboard\launch_dashboard.py" %*
if errorlevel 1 (
  echo.
  echo The SEO dashboard did not start. Check:
  echo apps\seo_dashboard\server.out.log
  echo apps\seo_dashboard\server.err.log
  pause
  exit /b 1
)

endlocal
