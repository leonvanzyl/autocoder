@echo off
REM Autonomous Coder UI Launcher for Windows
REM This script launches the web UI for the autonomous coding agent.

echo.
echo ====================================
echo   Autonomous Coder UI
echo ====================================
echo.

REM Check if Python is available
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERROR: Python not found in PATH
    echo Please install Python from https://python.org
    pause
    exit /b 1
)

REM Run the Python launcher
python "%~dp0start_ui.py" %*

pause
