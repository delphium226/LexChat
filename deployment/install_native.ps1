<#
.SYNOPSIS
    Installs prerequisites for LexChat Native Windows Deployment.
    Installs Python, Node.js, PostgreSQL, and Ollama.
    Sets up Python venv, builds Frontend, creates Database, and pulls AI Models.
#>

$ErrorActionPreference = "Stop"

# Check Administrator Privileges
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Warning "This script requires Administrator privileges!"
    Write-Warning "Please right-click and select 'Run as Administrator'."
    exit
}

Write-Host "=== LexChat Native Installer ===" -ForegroundColor Cyan

# 1. Install Chocolatey
if (-not (Get-Command "choco" -ErrorAction SilentlyContinue)) {
    Write-Host "Installing Chocolatey..."
    Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
    $RunEnvUpdate = $true
}

# Reload Path if choco was just installed
if ($RunEnvUpdate) {
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
}

# 2. Install Core Dependencies
Write-Host "Installing Python 3.11..."
choco install python --version=3.11.9 -y

Write-Host "Installing Node.js (LTS)..."
choco install nodejs-lts -y

Write-Host "Installing PostgreSQL 15..."
# Note: This installs Postgres. Password set via params if supported, otherwise manual.
# Using 'lexpassword' as default for automated setup.
choco install postgresql15 -y --params '/Password:lexpassword'

Write-Host "Installing Ollama..."
$OllamaInstaller = "$env:TEMP\OllamaSetup.exe"
Invoke-WebRequest -Uri "https://ollama.com/download/OllamaSetup.exe" -OutFile $OllamaInstaller
Start-Process -FilePath $OllamaInstaller -ArgumentList "/silent" -Wait

# 3. Reload Path to ensure python/node/ollama are visible
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

# 4. Configure PostgreSQL (Create DB and User)
Write-Host "Configuring Database..."
# Wait for service to start
Start-Sleep -Seconds 10
$PG_PASSWORD = "lexpassword"
$env:PGPASSWORD = $PG_PASSWORD

# Create User 'lexuser' if not exists
# We use psql from the install. typically in "C:\Program Files\PostgreSQL\15\bin"
# But it should be in PATH after install. If not, we might fail here without a reboot/refresh.
# We try to proceed.

# Helper to check if tool is available
if (-not (Get-Command "psql" -ErrorAction SilentlyContinue)) {
    Write-Warning "psql not found in PATH. You may need to restart the shell or add PostgreSQL bin to PATH manually."
    Write-Warning "Skipping DB creation automation. Please create 'lexuser' and 'lexchat' DB manually."
}
else {
    $UserCheck = psql -U postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='lexuser'"
    if ($UserCheck -ne '1') {
        Write-Host "Creating 'lexuser'..."
        psql -U postgres -c "CREATE USER lexuser WITH PASSWORD 'lexpassword';"
        psql -U postgres -c "ALTER USER lexuser WITH SUPERUSER;"
    }

    # Create DB 'lexchat' if not exists
    $DbCheck = psql -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname='lexchat'"
    if ($DbCheck -ne '1') {
        Write-Host "Creating 'lexchat' database..."
        psql -U postgres -c "CREATE DATABASE lexchat OWNER lexuser;"
    }
}
$env:PGPASSWORD = $null # Clear password

# 5. Configure Ollama (Pull Model)
Write-Host "Pulling AI Model (mistral-large)..."
# Start Ollama in background just in case
if (Get-Command "ollama" -ErrorAction SilentlyContinue) {
    try {
        Start-Process -FilePath "ollama" -ArgumentList "serve" -PassThru -NoNewWindow
        Start-Sleep -Seconds 5
        ollama pull mistral-large
    }
    catch {
        Write-Warning "Failed to auto-pull model. Run 'ollama pull mistral-large' manually."
    }
}
else {
    Write-Warning "Ollama not found in PATH. Please restart shell and run 'ollama pull mistral-large manualy'."
}

# 6. App Setup
# Assume script is run from deployment/ folder, so repo root is ..
$RepoRoot = Resolve-Path "$PSScriptRoot\.."
Write-Host "Setting up Application at $RepoRoot..."

# Backend
Write-Host "Setting up Backend (venv)..."
Set-Location "$RepoRoot\server_py"
python -m venv venv
.\venv\Scripts\python -m pip install -r requirements.txt

# Create .env.native
if (-not (Test-Path ".env.native")) {
    Write-Host "Creating default .env.native..."
    $EnvContent = @"
PORT=8000
DATABASE_URL=postgresql://lexuser:lexpassword@localhost:5432/lexchat
JWT_SECRET=native_windows_secret
OLLAMA_BASE_URL=http://localhost:11434
LEX_API_URL=https://lex-api.victoriousdesert-f8e685e0.uksouth.azurecontainerapps.io
"@
    Set-Content -Path ".env.native" -Value $EnvContent
}

# Frontend
Write-Host "Building Frontend..."
Set-Location "$RepoRoot\client"
npm install
npm run build

Write-Host "=== Installation Complete! ===" -ForegroundColor Green
Write-Host "Run 'deployment\start_native.cmd' to launch the app."
Pause
