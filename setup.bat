@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  python -m venv .venv
)
.venv\Scripts\pip install --quiet -r requirements-dev.txt
echo setup complete - run: run.bat
pause
