@echo off
SETLOCAL EnableDelayedExpansion

TITLE LexChat Federation Dev Launcher

echo ===================================================
echo   LexChat Federation Dev Launcher
echo   Legislation Bot : http://localhost:8000
echo   Parliament Bot  : http://localhost:8001
echo ===================================================

:: Ensure we are in repo root (script lives in deployment/)
cd /d "%~dp0\.."

:: Check Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Install Python 3.11+ and add to PATH.
    pause
    exit /b 1
)

:: -------------------------------------------------------
:: 1. Start PostgreSQL
:: -------------------------------------------------------
echo.
echo [1/4] Starting PostgreSQL...
sc query postgresql-x64-18 | find "RUNNING" >nul 2>nul
if %errorlevel% equ 0 goto pg_already_running

net start postgresql-x64-18
if %errorlevel% neq 0 goto pg_failed
echo    PostgreSQL started.
goto pg_done

:pg_already_running
echo    PostgreSQL already running.
goto pg_done

:pg_failed
echo [ERROR] Could not start the postgresql-x64-18 service.
echo         Try starting it via Services manually, then re-run.
pause
exit /b 1

:pg_done

:: -------------------------------------------------------
:: 2. Start Ollama (optional)
:: -------------------------------------------------------
echo.
echo [2/4] Starting Ollama...
where ollama >nul 2>nul
if %errorlevel% neq 0 (
    echo    [WARN] Ollama not found. Skipping.
    goto ollama_done
)
tasklist /FI "IMAGENAME eq ollama.exe" 2>nul | find /I "ollama.exe" >nul
if %errorlevel% equ 0 (
    echo    Ollama already running.
    goto ollama_done
)
start "Ollama" /MIN cmd /k "ollama serve"
echo    Ollama started.

:ollama_done

:: -------------------------------------------------------
:: 3-4. Hand off to PowerShell for DB setup, bot launch,
::      and federation peer registration
:: -------------------------------------------------------
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_federation_dev.ps1" -RepoRoot "%cd%"
if %errorlevel% neq 0 (
    pause
    exit /b 1
)

echo.
echo ===================================================
echo   Federation dev environment running:
echo     Legislation Bot : http://localhost:8000
echo     Parliament Bot  : http://localhost:8001
echo ===================================================
echo.
start http://localhost:8000
echo Close this window when done (bot windows will stay open).
pause
