@echo off
rem Start Jot. Double-click this file and leave the window open while you use it.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo First run: setting things up ^(one time, about a minute^)...
  where py >nul 2>nul && (py -3 -m venv .venv) || (python -m venv .venv)
  if not exist ".venv\Scripts\python.exe" (
    echo Could not find Python 3. Install it from https://www.python.org/downloads/ ^(tick "Add python.exe to PATH"^) and run this again.
    pause
    exit /b 1
  )
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)
".venv\Scripts\python.exe" app.py
pause
