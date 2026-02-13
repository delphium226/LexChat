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

where npm >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Node.js not found. Please install Node.js 20+.
    pause
    exit /b
)

:: 2. Start Backend
echo.
echo [1/3] Starting Backend Server...
cd server_py

:: Activate venv if it exists
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    echo [WARN] Virtual environment not found. Using system python.
)

:: Run in a new separate window
start "LexChat Backend" cmd /k "python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --env-file .env.native"

:: 3. Serve Frontend
echo.
echo [2/3] Serving Frontend...
cd ..\client

if not exist dist (
    echo [INFO] Build directory not found. Building frontend...
    call npm run build
)

:: serve the 'dist' folder on port 3000
echo [INFO] Starting Frontend Server on port 3000...
start "LexChat Frontend" cmd /k "npx -y serve -s dist -l 3000"

echo.
echo ===================================================
echo   LexChat is running!
echo   Frontend: http://localhost:3000
echo   Backend:  http://localhost:8000
echo ===================================================
echo.
echo Close to exit launcher (servers will keep running).
pause
