@echo off
cd /d "%~dp0"
if "%1"=="--import" (
  if not exist data\bonds.db if exist "v5.5_40L_Project_Tracker.xlsm" (
    .venv\Scripts\python src\app.py --import "v5.5_40L_Project_Tracker.xlsm" --db data\bonds.db
  ) else (
    echo import skipped: data\bonds.db already exists
  )
)
.venv\Scripts\python src\app.py --db data\bonds.db
pause
