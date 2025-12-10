@echo off
echo Starting LexChat UK...

:: Start Backend in a new window
start "LexChat Backend" cmd /k "cd server && npm start"

:: Wait a moment for backend to initialize
timeout /t 3 /nobreak >nul

:: Start Frontend in a new window
start "LexChat Frontend" cmd /k "cd client && npm run dev -- --host"

echo.
echo Application started!
echo Backend: http://localhost:3000
echo Frontend: http://localhost:5173
echo.
echo Opening browser...
timeout /t 2 /nobreak >nul
start http://localhost:5173
