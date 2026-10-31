@echo off
cd /d "%~dp0"
.venv\Scripts\python src\app.py --db data\bonds.db
pause
