<#
.SYNOPSIS
    Updates the LexChat application.
    Pulls latest changes from Git and rebuilds Docker containers.
#>

$ErrorActionPreference = "Stop"

Write-Host "Updating LexChat..." -ForegroundColor Cyan

# Ensure we are in the repo root (assuming script is in /deployment folder, so go up one level)
$ScriptPath = $PSScriptRoot
$RepoRoot = Split-Path -Parent $ScriptPath
Set-Location $RepoRoot

Write-Host "Pulling latest changes from Git..."
git pull

Write-Host "Rebuilding containers..."
.\rebuild_docker.ps1

Write-Host "Update Complete!" -ForegroundColor Green
