@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [1/2] Creating Python environment...
  py -3 -m venv .venv
  if errorlevel 1 (
    echo Python 3.11 or later is required. Download it from https://www.python.org/downloads/
    pause
    exit /b 1
  )
)
echo [2/2] Installing or checking packages...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
echo Opening Mirae AI Studio at http://127.0.0.1:8000
start "" http://127.0.0.1:8000
".venv\Scripts\python.exe" -m uvicorn app:app --host 127.0.0.1 --port 8000
pause
