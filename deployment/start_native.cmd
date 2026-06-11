@echo off
SETLOCAL EnableDelayedExpansion

:: Parse arguments
set USE_NGINX=0
for %%A in (%*) do if /I "%%A"=="--nginx" set USE_NGINX=1

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

:: 2. Start PostgreSQL
echo.
echo [1/4] Starting PostgreSQL...
sc query postgresql-x64-18 | find "RUNNING" >nul
if %errorlevel% neq 0 (
    net start postgresql-x64-18
    echo    PostgreSQL started.
) else (
    echo    PostgreSQL already running.
)

:: 3. Start Ollama
echo.
echo [2/4] Starting Ollama...
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

:: 4. Start Backend
echo.
echo [3/4] Starting Backend Server...
cd server_py

:: Use .env.native as the active config
copy /Y .env.native .env >nul

:: Activate venv if it exists
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    echo [WARN] Virtual environment not found. Using system python.
)

:: Use SSL if certs are present, otherwise run on HTTP port 8000.
:: --nginx bypasses SSL: uvicorn runs on port 8000 internally; nginx is the public face on port 80.
set CERT_PATH=..\deployment\certs\lexchat.crt
set KEY_PATH=..\deployment\certs\lexchat.key
set USE_SSL=0
if !USE_NGINX!==0 if exist !CERT_PATH! if exist !KEY_PATH! set USE_SSL=1

if !USE_NGINX!==1 goto :mode_nginx
if !USE_SSL!==1 goto :mode_ssl

:mode_http
set SSL_ARGS=--port 8000
set APP_URL=http://localhost:8000
echo    No SSL certificates found. Running on HTTP port 8000.
goto :mode_done

:mode_nginx
set SSL_ARGS=--port 8000
set APP_URL=http://localhost
echo    Nginx mode: uvicorn on HTTP port 8000 ^(internal only^).
goto :mode_done

:mode_ssl
set SSL_ARGS=--port 443 --ssl-keyfile !KEY_PATH! --ssl-certfile !CERT_PATH!
set APP_URL=https://localhost
echo    SSL certificates found. Running on HTTPS port 443.

:mode_done

set BOT_CONFIG_PATH=%~dp0..\bots\legislation\bot_config.json
start "LexChat Backend" cmd /k "python -m uvicorn src.main:app --host 0.0.0.0 !SSL_ARGS!"

:: 3b. Start Nginx (only in --nginx mode)
if !USE_NGINX!==1 (
    echo.
    echo [3b] Starting Nginx (reverse proxy)...
    set "NGINX_EXE="
    for /f "delims=" %%i in ('where nginx 2^>nul') do if not defined NGINX_EXE set "NGINX_EXE=%%i"
    if not defined NGINX_EXE if exist "C:\nginx\nginx.exe" set "NGINX_EXE=C:\nginx\nginx.exe"
    if not defined NGINX_EXE if exist "C:\Program Files\nginx\nginx.exe" set "NGINX_EXE=C:\Program Files\nginx\nginx.exe"

    if not defined NGINX_EXE (
        echo [ERROR] nginx.exe not found in PATH or common install locations.
        echo         Install nginx for Windows from nginx.org, then either add to PATH
        echo         or install to C:\nginx or C:\Program Files\nginx
        pause
        exit /b 1
    )

    for %%i in ("!NGINX_EXE!") do set "NGINX_DIR=%%~dpi"
    set "NGINX_DIR=!NGINX_DIR:~0,-1!"
    set "NGINX_CONF=%~dp0nginx\lexchat.conf"

    start "LexChat Nginx" /MIN "!NGINX_EXE!" -p "!NGINX_DIR!" -c "!NGINX_CONF!"
    echo    Nginx started.
    echo    Traffic flow: external port 80 --^> uvicorn port 8000
)

:: 5. Check Frontend
echo.
echo [4/4] Checking Frontend...
cd ..\client

if not exist dist (
    echo [INFO] Build directory not found. Building frontend...
    call npm run build
) else (
    echo [INFO] Frontend build found. Served by backend on !APP_URL!.
)

echo.
echo ===================================================
echo   LexChat is running natively!
echo   Application: !APP_URL!
echo ===================================================
echo.
start !APP_URL!
echo Close to exit launcher (servers will keep running).
pause
