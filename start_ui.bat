@echo off
cd /d "%~dp0"
REM AutoForge UI Launcher for Windows
REM This script launches the web UI for the autonomous coding agent.

echo.
echo ====================================
echo   AutoForge UI
echo ====================================
echo.

REM Kill any existing processes on port 8888
echo Cleaning up old processes...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8888" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)

REM Check if Python is available
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERROR: Python not found in PATH
    echo Please install Python from https://python.org
    pause
    exit /b 1
)

REM Check if venv exists with correct activation script
if not exist "venv\Scripts\activate.bat" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate the virtual environment
call venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt --quiet

REM Ensure playwright-cli is available for browser automation
where playwright-cli >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Installing playwright-cli for browser automation...
    call npm install -g @playwright/cli >nul 2>&1
    if %ERRORLEVEL% neq 0 (
        echo Note: Could not install playwright-cli. Install manually: npm install -g @playwright/cli
    )
)

REM Run the Python launcher
python "%~dp0start_ui.py" %*
