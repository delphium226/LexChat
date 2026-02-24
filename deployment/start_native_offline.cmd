@echo off
REM Starts the native offline application
REM Assumes Python is installed and the frontend is pre-built in client\dist

cd ..\server_py
echo Starting FastAPI Server...
REM Ensure we are using .env.native
copy /Y .env.native .env
uvicorn src.main:app --host 0.0.0.0 --port 8080
pause
