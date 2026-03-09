@echo off
setlocal enabledelayedexpansion

title FranklinOps

echo.
echo   =============================================================
echo   FranklinOps - Universal Business Automation OS
echo   =============================================================
echo.

REM Get the directory where this script lives
set ROOT=%~dp0
cd /d "%ROOT%"

REM Create data directory
if not exist "data\franklinops" mkdir "data\franklinops"

REM Check for Python
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   ERROR: Python not found
    echo.
    echo   SOLUTION: Download from https://www.python.org/downloads/
    echo   IMPORTANT: During install, CHECK "Add Python to PATH"
    echo   Then restart this script.
    echo.
    pause
    exit /b 1
)

REM Kill old process on port 8844
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8844 ^| findstr LISTENING') do (
    taskkill /PID %%a /F >nul 2>&1
)

REM Install dependencies silently
echo   Installing dependencies...
python -m pip install -q fastapi uvicorn python-dotenv requests 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo   Retrying pip install...
    python -m pip install fastapi uvicorn python-dotenv requests
    if %ERRORLEVEL% NEQ 0 (
        echo   ERROR: Pip install failed
        echo   Try: python -m pip install --upgrade pip
        pause
        exit /b 1
    )
)

REM Start server
echo.
echo   Starting FranklinOps...
echo   Browser opening in 3 seconds to: http://localhost:8844/ui
echo.
timeout /t 3 /nobreak

REM Open browser
start http://127.0.0.1:8844/ui

REM Run server
python -m uvicorn src.franklinops.server_clean:app --host 127.0.0.1 --port 8844
