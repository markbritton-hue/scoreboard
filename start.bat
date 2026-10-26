@echo off
cd /d "%~dp0"
where python >nul 2>nul
if %errorlevel%==0 (set PY=python) else (set PY=py)
echo Setup page:  http://localhost:8000/setup.html
echo Overlay:     http://localhost:8000/mascot.html
echo Press Ctrl+C to stop.
start "" "http://localhost:8000/setup.html"
%PY% -m http.server 8000
pause
