@echo off
TITLE LexChat Stop

echo ===================================================
echo   LexChat - Stopping Services
echo ===================================================

:: 1. Stop Nginx (if running in --nginx mode; safe no-op otherwise)
echo.
echo [1/4] Stopping Nginx (if running)...
taskkill /IM nginx.exe /T /F >nul 2>nul
echo    Done.

:: 2. Stop the FastAPI/uvicorn backend (runs in a window titled "LexChat Backend")
echo.
echo [2/4] Stopping Backend (uvicorn)...
taskkill /FI "WINDOWTITLE eq LexChat Backend" /T /F >nul 2>nul
:: Also catch any stray uvicorn/python processes on port 443
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":443 " ^| findstr "LISTENING"') do (
    taskkill /PID %%a /T /F >nul 2>nul
)
echo    Done.

:: 3. Stop Ollama
echo.
echo [3/4] Stopping Ollama...
taskkill /IM ollama.exe /T /F >nul 2>nul
echo    Done.

:: 4. Stop PostgreSQL Windows service
echo.
echo [4/4] Stopping PostgreSQL service...
net stop postgresql-x64-18 >nul 2>nul
if %errorlevel% equ 0 (
    echo    Done.
) else (
    echo    [INFO] PostgreSQL service not running or not found.
)

echo.
echo ===================================================
echo   LexChat stopped.
echo ===================================================
pause
