[CmdletBinding()]
param(
    [switch]$SkipSystemInstall
)

# requires admin privileges
# This script installs the pre-packaged standalone dependencies and application on an air-gapped machine

$ErrorActionPreference = "Stop"

# Auto-elevate to Administrator explicitly so that the standalone EXE installers can run
if (-Not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Warning "Administrator permissions are required to run the Postgres and Python installers. Prompting for elevation..."
    $argList = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    if ($SkipSystemInstall) {
        $argList += " -SkipSystemInstall"
    }
    Start-Process powershell.exe $argList -Verb RunAs
    exit
}

$BINARIES_DIR = "..\binaries\raw"
$INSTALLERS_DIR = "$BINARIES_DIR\installers"
$WHEELS_DIR = "$BINARIES_DIR\python_wheels"
$OLLAMA_MODELS_DIR = "$BINARIES_DIR\ollama_models"

if (!(Test-Path $BINARIES_DIR)) {
    Write-Error "Binaries directory not found. Please ensure the chunks have been reconstructed into $BINARIES_DIR."
    exit 1
}

# 1. Install System Dependencies
if (-not $SkipSystemInstall) {
    Write-Host "Installing Python silently..."
    Start-Process -FilePath "$INSTALLERS_DIR\python-3.11.9-amd64.exe" -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1" -Wait -NoNewWindow

    Write-Host "Installing PostgreSQL silently (Superuser: postgres, Password: lexpassword)..."
    Start-Process -FilePath "$INSTALLERS_DIR\postgresql-15.7-1-windows-x64.exe" -ArgumentList "--mode unattended --superpassword lexpassword --serverport 5432" -Wait -NoNewWindow
    # Reload path just in case Postgres modified it, and add common pg path
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User") + ";C:\Program Files\PostgreSQL\15\bin"
    Write-Host "Initializing lexchat database..."
    $env:PGPASSWORD="lexpassword"
    `"C:\Program Files\PostgreSQL\15\bin\psql.exe`" -U postgres -c `"CREATE DATABASE lexchat;`"

    Write-Host "Installing Ollama silently..."
    Start-Process -FilePath "$INSTALLERS_DIR\OllamaSetup.exe" -ArgumentList "/S" -Wait -NoNewWindow
} else {
    Write-Host "Skipping system dependencies installation (-SkipSystemInstall flag provided)."
}

# 2. Install Python Dependencies Offline
Write-Host "Installing Python dependencies from local wheels..."
# Need to reload path to ensure pip from new Python install is available
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
python -m pip install --no-index --find-links=$WHEELS_DIR -r ..\server_py\requirements.txt

# 3. Restore AI Models
Write-Host "Restoring Ollama Models..."
$OLLAMA_TARGET_DIR = $env:OLLAMA_MODELS
if (-not $OLLAMA_TARGET_DIR) {
    $OLLAMA_TARGET_DIR = "$env:USERPROFILE\.ollama\models"
}

if (!(Test-Path $OLLAMA_TARGET_DIR)) {
    New-Item -ItemType Directory -Force -Path $OLLAMA_TARGET_DIR | Out-Null
}
Write-Host "Copying models to $OLLAMA_TARGET_DIR..."
Copy-Item -Path "$OLLAMA_MODELS_DIR\*" -Destination $OLLAMA_TARGET_DIR -Recurse -Force

# 4. Extract Frontend
Write-Host "Extracting pre-built frontend..."
$FRONTEND_TARGET_DIR = "..\client\dist"
if (Test-Path $FRONTEND_TARGET_DIR) {
    Remove-Item -Recurse -Force $FRONTEND_TARGET_DIR
}
New-Item -ItemType Directory -Force -Path $FRONTEND_TARGET_DIR | Out-Null
$FRONTEND_SRC_DIR = "$BINARIES_DIR\frontend_dist"
if (Test-Path $FRONTEND_SRC_DIR) {
    Copy-Item -Path "$FRONTEND_SRC_DIR\*" -Destination $FRONTEND_TARGET_DIR -Recurse -Force
} else {
    Write-Warning "No frontend_dist found in the offline package."
}

# 5. Configure FastAPI to serve the frontend
Write-Host "Please ensure your .env.native file is configured and you have added code to server_py/src/main.py to serve the client/dist folder as static files."
# 6. Configure Windows Firewall
Write-Host "Configuring Windows Firewall to allow port 443 for remote access..."
New-NetFirewallRule -DisplayName "LexChat HTTPS (Port 443)" -Direction Inbound -LocalPort 443 -Protocol TCP -Action Allow -ErrorAction SilentlyContinue | Out-Null

Write-Host "Offline Installation Complete. You can start the server using deployment\start_native_offline.cmd"
