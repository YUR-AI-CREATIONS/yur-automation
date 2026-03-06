@echo off
title FranklinOps — Operating System for Business
chcp 65001 >nul
echo.
echo  ============================================================
echo   FRANKLINOPS — Red Carpet Experience
echo   Documents in. Decisions out. Humans in control.
echo  ============================================================
echo.

cd /d "%~dp0.."
if not exist "src\franklinops\server.py" (
    echo [ERROR] Wrong folder. Run this from the FranklinOps folder.
    echo         Make sure you unzipped FranklinOps-Portable.zip first.
    echo.
    echo         Current folder: %CD%
    echo.
    goto :stayopen
)

REM Find Python (try python, then py launcher)
set PY=
where python >nul 2>&1
if %errorlevel% equ 0 (
    set PY=python
) else (
    where py >nul 2>&1
    if %errorlevel% equ 0 (
        set PY=py -3
    )
)

if "%PY%"=="" (
    echo [ERROR] Python not found. Please install Python 3.11+ from:
    echo         https://www.python.org/downloads/
    echo.
    echo         IMPORTANT: Check "Add Python to PATH" during installation.
    echo.
    goto :stayopen
)

echo [OK] Using: %PY%
echo.

REM Check dependencies
%PY% -c "import uvicorn" 2>nul
if errorlevel 1 (
    echo [SETUP] Installing dependencies (first run only)...
    %PY% -m pip install -r requirements-minimal.txt -q
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies.
        echo         Try running: pip install -r requirements-minimal.txt
        echo.
        goto :stayopen
    )
    echo [OK] Dependencies installed.
    echo.
)

echo [TIP] For AI chat: ollama.com ^| ollama pull llama3  (no API key)
echo.

echo [START] Launching FranklinOps...
echo.
echo   Browser opens in 3 seconds...
echo     http://127.0.0.1:8844/ui/boot
echo.
echo   Press Ctrl+C to stop.
echo  ============================================================
echo.

start /b cmd /c "timeout /t 3 /nobreak >nul && start http://127.0.0.1:8844/ui/boot"

%PY% -m uvicorn src.franklinops.server:app --host 127.0.0.1 --port 8844
if errorlevel 1 (
    echo.
    echo [ERROR] Server stopped. Check the error above.
    echo.
)

:stayopen
echo.
echo Press any key to close this window...
pause >nul
