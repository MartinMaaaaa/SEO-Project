@echo off
setlocal
cd /d "%~dp0"

echo Starting SEO dashboard...
start "SEO Dashboard Server" /D "%~dp0" cmd /k "python -u apps\seo_dashboard\server.py 8766"
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:8766"
