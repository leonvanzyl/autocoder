@echo off
REM AutoCoder UI Launcher for Windows

echo.
echo ====================================
echo   AUTOCODER // WEB UI
echo   Modded by Gabi (Booplex)
echo ====================================
echo.
set UI_PORT=%AUTOCODER_UI_PORT%
if "%UI_PORT%"=="" set UI_PORT=8888
echo   Opening http://127.0.0.1:%UI_PORT%  (set AUTOCODER_OPEN_UI=0 to disable)
echo   Tip: set AUTOCODER_UI_BANNER=0 to hide this banner
echo.

REM Load .env file if it exists
if exist .env (
    for /f "tokens=1,2 delims==" %%a in ('type .env ^| findstr /v "^#" ^| findstr /v "^$"') do (
        set %%a=%%b
    )
)

REM Verify autocoder-ui exists before running
where autocoder-ui >nul 2>nul
if %errorlevel% neq 0 (
  echo.
  echo [ERROR] autocoder-ui command not found
  echo.
  echo Please install the package first:
  echo   pip install -e '.[dev]'
  echo.
  pause
  exit /b 1
)

REM Run autocoder-ui command
autocoder-ui
set EXIT_CODE=%errorlevel%
if %EXIT_CODE% neq 0 (
  echo.
  echo [ERROR] autocoder-ui exited with code %EXIT_CODE%
  echo.
  pause
  exit /b %EXIT_CODE%
)
