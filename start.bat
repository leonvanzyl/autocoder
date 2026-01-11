@echo off
cd /d "%~dp0"

echo.
echo ========================================
echo   Autonomous Coding Agent
echo ========================================
echo.

REM Check if Opencode Python SDK is available
python -c "import opencode_ai" >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Opencode Python SDK not found
    echo.
    echo Please install the SDK first:
    echo   pip install --pre opencode-ai
    echo.
    echo Then run this script again.
    echo.
    pause
    exit /b 1
)

echo [OK] Opencode SDK available

REM Note: Opencode uses API keys or other auth mechanisms. Ensure OPENCODE_API_KEY is set.
if defined OPENCODE_API_KEY (
    echo [OK] OPENCODE_API_KEY found in environment
) else (
    echo [!] Opencode API key not configured
    echo.
    echo Please set OPENCODE_API_KEY per https://opencode.ai/docs
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
