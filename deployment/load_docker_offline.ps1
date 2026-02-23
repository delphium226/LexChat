<#
.SYNOPSIS
    Loads pre-downloaded Docker image archives into the local Docker daemon.
    
.DESCRIPTION
    This script is intended for offline deployments. It reads all .tar files
    located in the \binaries\raw\docker directory and uses 'docker load' 
    to import them into Docker Desktop or Docker Engine.

    Once loaded, the application can be started normally via docker-compose.
#>

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path "$PSScriptRoot\.."
$DockerDir = "$RepoRoot\binaries\raw\docker"

Write-Host "=== LexChat Offline Docker Importer ===" -ForegroundColor Cyan

# Check for Docker
if (-not (Get-Command "docker" -ErrorAction SilentlyContinue)) {
    Write-Warning "Docker command not found! Please ensure Docker Desktop is installed and running."
    exit 1
}

if (-not (Test-Path $DockerDir)) {
    Write-Warning "Offline docker directory not found relative to script: $DockerDir"
    Write-Warning "Have you run 'reconstruct_binaries.ps1' yet?"
    exit 1
}

$TarFiles = Get-ChildItem -Path $DockerDir -Filter "*.tar"

if ($TarFiles.Count -eq 0) {
    Write-Warning "No .tar Docker images found in $DockerDir"
    exit 1
}

Write-Host "Found $($TarFiles.Count) Docker images to load offline." -ForegroundColor Yellow

foreach ($file in $TarFiles) {
    Write-Host "Loading image: $($file.Name)..." -ForegroundColor Cyan
    # Use AsByteStream to bypass raw SMB read bottlenecks on Windows Hyper-V
    if ($PSVersionTable.PSVersion.Major -ge 7) {
        Get-Content -Path $file.FullName -AsByteStream -ReadCount 0 | docker load
    }
    else {
        Get-Content -Path $file.FullName -Encoding Byte -ReadCount 0 | docker load
    }
}

Write-Host "=== All Images Successfully Loaded! ===" -ForegroundColor Green
Write-Host "You can now start the application tightly offline by running:"
Write-Host "docker-compose up -d  <-- (Starts the application)"
