@echo off
echo Stopping LexChat UK...

:: 1. Kill processes listening on ports (Backend: 3000, Frontend: 5173)
echo Checking ports...
for /f "tokens=5" %%a in ('netstat -aon ^| find ":3000" ^| find "LISTENING"') do (
    echo Killing process on port 3000 - PID: %%a
    taskkill /f /pid %%a >nul 2>&1
)

for /f "tokens=5" %%a in ('netstat -aon ^| find ":5173" ^| find "LISTENING"') do (
    echo Killing process on port 5173 - PID: %%a
    taskkill /f /pid %%a >nul 2>&1
)

:: 2. Close the specific terminal windows by title
echo Closing terminal windows...
taskkill /FI "WINDOWTITLE eq LexChat Backend" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq LexChat Frontend" /F >nul 2>&1

echo.
echo Application stopped and ports released.
echo Ready for a clean run!
timeout /t 3
