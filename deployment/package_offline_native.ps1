# requires admin privileges
# This script downloads all the standalone installers, python wheels, and pre-builds the frontend.

$ErrorActionPreference = "Stop"

# Auto-elevate to Administrator explicitly
if (-Not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Warning "Administrator permissions are required to prepare the deployment packaging. Prompting for elevation..."
    Start-Process powershell.exe "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit
}

$BINARIES_DIR = "..\binaries\raw"
$INSTALLERS_DIR = "$BINARIES_DIR\installers"
$WHEELS_DIR = "$BINARIES_DIR\python_wheels"
$OLLAMA_MODELS_DIR = "$BINARIES_DIR\ollama_models"

# 1. Clean up old binaries
Write-Host "Cleaning up old binaries..."
if (Test-Path $BINARIES_DIR) {
    Remove-Item -Recurse -Force $BINARIES_DIR
}
New-Item -ItemType Directory -Force -Path $INSTALLERS_DIR | Out-Null
New-Item -ItemType Directory -Force -Path $WHEELS_DIR | Out-Null
New-Item -ItemType Directory -Force -Path $OLLAMA_MODELS_DIR | Out-Null

# 2. Download Installers
Write-Host "Downloading standalone installers (this may take a while)..."
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$PYTHON_URL = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
$POSTGRES_URL = "https://get.enterprisedb.com/postgresql/postgresql-15.7-1-windows-x64.exe"
$OLLAMA_URL = "https://ollama.com/download/OllamaSetup.exe"

Write-Host "Downloading Python..."
curl.exe -L -o "$INSTALLERS_DIR\python-3.11.9-amd64.exe" $PYTHON_URL
Write-Host "Downloading PostgreSQL..."
curl.exe -L -o "$INSTALLERS_DIR\postgresql-15.7-1-windows-x64.exe" $POSTGRES_URL
Write-Host "Downloading Ollama..."
curl.exe -L -o "$INSTALLERS_DIR\OllamaSetup.exe" $OLLAMA_URL

# 3. Download Python Wheels
Write-Host "Downloading Python wheels for offline installation (Python 3.11 win_amd64)..."
# We must explicitly force Python 3.11 cp311 win_amd64 wheels to match our standalone installer!
pip download --platform win_amd64 --python-version 3.11 --implementation cp --only-binary=:all: -r ..\server_py\requirements.txt -d $WHEELS_DIR

# 4. Pre-build Frontend
Write-Host "Pre-building the React frontend locally..."
$env:Path = "$env:USERPROFILE\node_portable\node-v20.15.1-win-x64;" + $env:Path
Push-Location ..\client
npm install
npm run build
Pop-Location
# The build output is already in client\dist, which we will copy during the deployment phase.

# 5. Export Ollama Models (Assumes Ollama is installed and running locally)
Write-Host "Exporting Ollama models according to config.py..."
$CONFIG_PATH = "..\server_py\src\config.py"
if (Test-Path $CONFIG_PATH) {
    # Extract model names from MODEL_LIST using regex
    $configContent = Get-Content $CONFIG_PATH -Raw
    $models = [regex]::Matches($configContent, '"name":\s*"([^"]+)"') | ForEach-Object { $_.Groups[1].Value }
    
    foreach ($model in $models) {
        Write-Host "Pulling model: $model"
        ollama pull $model
    }
} else {
    Write-Warning "Could not find config.py to determine models to pull."
}
# Determine the correct Ollama models path
$OLLAMA_SOURCE_DIR = $env:OLLAMA_MODELS
if (-not $OLLAMA_SOURCE_DIR) {
    $OLLAMA_SOURCE_DIR = "$env:USERPROFILE\.ollama\models"
}

if (Test-Path $OLLAMA_SOURCE_DIR) {
    Write-Host "Copying models from $OLLAMA_SOURCE_DIR..."
    Copy-Item -Path "$OLLAMA_SOURCE_DIR\*" -Destination $OLLAMA_MODELS_DIR -Recurse -Force
} else {
    Write-Warning "Could not find local Ollama models directory at $OLLAMA_SOURCE_DIR"
}

Write-Host "Offline packaging complete. The 'binaries\raw' folder is ready to be chunked."
