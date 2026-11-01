@echo off
title Guardian Shield v2.0
echo ========================================================
echo   🛡️  GUARDIAN SHIELD v2.0 - SHOULDER-SURFING DEFENSE
echo ========================================================
echo.
cd /d "%~dp0"

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

REM Launch Guardian Shield desktop application
echo Starting Guardian Shield Desktop Application...
start "" pythonw main.py
echo Guardian Shield is running.
exit /b 0
