@echo off
echo Starting LexChat UK (Production Mode)...

:: Build Frontend
echo Building Frontend...
cd client
call npm run build
if %errorlevel% neq 0 (
    echo Frontend build failed!
    pause
    exit /b %errorlevel%
)
cd ..

:: Start Backend
echo Starting Server...
start "LexChat Server" cmd /k "cd server && npm start"

:: Wait for init
timeout /t 5 /nobreak >nul

:: Open browser
echo Application started at http://localhost:3000
echo (Access via port 80 on mobile if firewall forwarding is configured)
echo.
echo Opening local browser...
start http://localhost:3000
