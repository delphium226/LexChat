@echo off
REM Starts the native offline application
REM Assumes Python is installed and the frontend is pre-built in client\dist

cd /d "%~dp0\.."

echo [1/2] Starting Ollama...
tasklist /FI "IMAGENAME eq ollama.exe" 2>nul | find /I "ollama.exe" >nul
if %errorlevel% neq 0 (
    start "LexChat Ollama" /MIN cmd /k "ollama serve"
    echo    Ollama started.
) else (
    echo    Ollama already running.
)

echo [2/2] Starting FastAPI Server...
cd server_py
REM Ensure we are using .env.native
copy /Y .env.native .env
echo Launching LexChat in your default web browser...
start https://localhost/
start "LexChat Backend" cmd /k "uvicorn src.main:app --host 0.0.0.0 --port 8080"
pause
