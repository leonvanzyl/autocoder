@echo off
cd /d "%~dp0"

echo.
echo ========================================
echo   Autonomous Coding Agent
echo ========================================
echo.

REM Check if Claude CLI is installed
where claude >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Claude CLI not found
    echo.
    echo Please install Claude CLI first:
    echo   https://claude.ai/download
    echo.
    echo Then run this script again.
    echo.
    pause
    exit /b 1
)

echo [OK] Claude CLI found

REM Note: Claude CLI no longer stores credentials in ~/.claude/.credentials.json
REM We can't reliably check auth status without making an API call, so we just
REM verify the CLI is installed and remind the user to login if needed
set "CLAUDE_DIR=%USERPROFILE%\.claude"
if exist "%CLAUDE_DIR%\" (
    echo [OK] Claude CLI directory found
    echo      ^(If you're not logged in, run: claude login^)
) else (
    echo [!] Claude CLI not configured
    echo.
    echo Please run 'claude login' to authenticate before continuing.
    echo.
    pause
)

:setup_venv
echo.

REM Check if venv exists, create if not
if not exist "venv\Scripts\activate.bat" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate the virtual environment
call venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt --quiet

REM Run the app
python start.py
