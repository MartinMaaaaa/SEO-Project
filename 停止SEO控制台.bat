@echo off
setlocal
cd /d "%~dp0"
python "%~dp0apps\seo_dashboard\stop_dashboard.py"
echo.
echo If a window named "SEO Dashboard Server" is still open, close it manually.
pause
