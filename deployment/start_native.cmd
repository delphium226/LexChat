@echo off
SETLOCAL EnableDelayedExpansion

TITLE LexChat Native Launcher

echo ===================================================
echo   LexChat Native Windows Launcher
echo ===================================================

:: Ensure we are in repo root. Script is in deployment/
cd /d "%~dp0\.."

:: 1. Check Prerequisites
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.11+ and add to PATH.
    pause
    exit /b
)

:: where npm >nul 2>nul
:: if %errorlevel% neq 0 (
::     echo [ERROR] Node.js not found. Please install Node.js 20+.
::     pause
::     exit /b
:: )

:: 2. Start Ollama
echo.
echo [1/3] Starting Ollama...
where ollama >nul 2>nul
if %errorlevel% neq 0 (
    echo [WARN] Ollama not found in PATH. Skipping.
) else (
    tasklist /FI "IMAGENAME eq ollama.exe" 2>nul | find /I "ollama.exe" >nul
    if %errorlevel% neq 0 (
        start "LexChat Ollama" /MIN cmd /k "ollama serve"
        echo    Ollama started.
    ) else (
        echo    Ollama already running.
    )
)

:: 3. Start Backend
echo.
echo [2/3] Starting Backend Server...
cd server_py

:: Activate venv if it exists
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    echo [WARN] Virtual environment not found. Using system python.
)

:: Run in a new separate window
:: Expects organizational certificates in deployment/certs relative to root
set CERT_PATH=..\deployment\certs\lexchat.crt
set KEY_PATH=..\deployment\certs\lexchat.key
start "LexChat Backend" cmd /k "python -m uvicorn src.main:app --host 0.0.0.0 --port 443 --ssl-keyfile !KEY_PATH! --ssl-certfile !CERT_PATH! --env-file .env.native"

:: 4. Build Frontend (if missing)
echo.
echo [3/3] Checking Frontend...
cd ..\client

if not exist dist (
    echo [INFO] Build directory not found. Building frontend...
    call npm run build
) else (
    echo [INFO] Frontend build found. Served natively by Backend on port 443.
)

echo.
echo ===================================================
echo   LexChat is running natively!
echo   Application: https://localhost (Port 443)
echo ===================================================
echo.
echo Close to exit launcher (servers will keep running).
pause
