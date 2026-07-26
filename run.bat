@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo   ITR Tally - one-click launcher
echo ============================================
echo.

where git >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Git is not installed or not on PATH.
    echo Install it from https://git-scm.com/download/win then run this file again.
    echo.
    pause
    exit /b 1
)

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python is not installed or not on PATH.
    echo Install it from https://www.python.org/downloads/
    echo IMPORTANT: on the install screen, check "Add python.exe to PATH".
    echo Then run this file again.
    echo.
    pause
    exit /b 1
)

if exist ".git" (
    echo Checking for updates...
    git pull
    if errorlevel 1 (
        echo [WARNING] Could not pull the latest changes - continuing with the code already on disk.
    )
) else (
    echo [WARNING] This folder is not a git checkout - skipping update check.
)

echo.
if not exist ".venv" (
    echo First-time setup: creating a virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Could not create the virtual environment.
        pause
        exit /b 1
    )
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] Could not activate the virtual environment.
    pause
    exit /b 1
)

echo Installing/updating required packages...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install required packages. Check your internet connection and try again.
    pause
    exit /b 1
)

echo.
echo Starting ITR Tally...
echo Your browser will open automatically at http://127.0.0.1:5050
echo Keep this window open while you use the app.
echo Close this window, or press Ctrl+C, to stop ITR Tally.
echo.

start "" /min cmd /c "ping -n 4 127.0.0.1 >nul & explorer http://127.0.0.1:5050"

python app.py

echo.
echo ITR Tally has stopped.
pause
