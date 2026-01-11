@echo off
REM Autocoder Deployment Script (Windows)
REM ======================================
REM
REM Usage:
REM   deploy.bat start     - Start all services
REM   deploy.bat stop      - Stop all services
REM   deploy.bat restart   - Restart all services
REM   deploy.bat status    - Show service status
REM   deploy.bat logs      - Tail logs
REM

setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo ========================================
echo       Autocoder Deploy Manager
echo ========================================
echo.

REM Check for Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python not found in PATH
    exit /b 1
)

set COMMAND=%1
if "%COMMAND%"=="" set COMMAND=help

if "%COMMAND%"=="start" (
    echo Starting services...
    python deploy.py start %2 %3 %4 %5 %6 %7 %8 %9
    goto :end
)

if "%COMMAND%"=="stop" (
    echo Stopping services...
    python deploy.py stop %2 %3 %4 %5 %6 %7 %8 %9
    goto :end
)

if "%COMMAND%"=="restart" (
    echo Restarting services...
    python deploy.py restart %2 %3 %4 %5 %6 %7 %8 %9
    goto :end
)

if "%COMMAND%"=="status" (
    python deploy.py status
    goto :end
)

if "%COMMAND%"=="logs" (
    python deploy.py logs %2
    goto :end
)

if "%COMMAND%"=="help" goto :help
if "%COMMAND%"=="--help" goto :help
if "%COMMAND%"=="-h" goto :help

echo Unknown command: %COMMAND%
echo Run 'deploy.bat help' for usage
exit /b 1

:help
echo Usage: deploy.bat {start^|stop^|restart^|status^|logs} [options]
echo.
echo Commands:
echo   start [backend^|frontend]    Start services (default: all)
echo   stop [backend^|frontend]     Stop services (default: all)
echo   restart [backend^|frontend]  Restart services (default: all)
echo   status                      Show service status
echo   logs [backend^|frontend]     Tail service logs
echo.
echo Options:
echo   -b, --backend-port PORT     Set backend port
echo   -f, --frontend-port PORT    Set frontend port
echo.
echo Examples:
echo   deploy.bat start            Start all services
echo   deploy.bat start backend    Start only backend
echo   deploy.bat start -b 8080    Start with custom backend port
echo   deploy.bat status           Check service status
goto :end

:end
endlocal
