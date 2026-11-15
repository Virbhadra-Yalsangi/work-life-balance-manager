@echo off
cd /d "%~dp0"
if not exist .venv (py -m venv .venv)
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
if not exist .env copy .env.example .env
echo.
echo Setup complete. Run run_app.bat to start the dashboard.
pause
