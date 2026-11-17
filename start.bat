@echo off
cd /d "%~dp0"
set PY=python
if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set PY="%LocalAppData%\Programs\Python\Python312\python.exe"
for /f "tokens=4" %%i in ('ipconfig ^| findstr /c:"IPv4 Address"') do set LANIP=%%i
echo Setup page:  http://localhost:9000/setup.html
echo Overlay:     http://localhost:9000/mascot.html
echo From another computer on this network, try: http://%LANIP%:9000/mascot.html
echo Press Ctrl+C to stop.
start "" "http://localhost:9000/setup.html"
%PY% server.py 9000
pause
