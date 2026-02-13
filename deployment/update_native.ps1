<#
.SYNOPSIS
    Updates the LexChat Native Windows Deployment.
    Pulls latest Git changes, updates dependencies, and rebuilds Frontend.
#>

$ErrorActionPreference = "Stop"

Write-Host "=== LexChat Native Updater ===" -ForegroundColor Cyan

# Ensure we are in repo root. Script is in deployment/
Set-Location "$PSScriptRoot\.."
$RepoRoot = Get-Location

# 1. Update Code
Write-Host "Pulling latest changes from Git..."
git pull

# 2. Update Backend
Write-Host "Updating Backend..."
Set-Location "$RepoRoot\server_py"
if (Test-Path "venv") {
    .\venv\Scripts\python -m pip install -r requirements.txt
}
else {
    Write-Warning "Virtual environment not found! Run install_native.ps1 first."
}

# 3. Update Frontend
Write-Host "Updating Frontend..."
Set-Location "$RepoRoot\client"
npm install
npm run build

Write-Host "=== Update Complete! ===" -ForegroundColor Green
Write-Host "Please restart the application using 'deployment\start_native.cmd'."
Pause
