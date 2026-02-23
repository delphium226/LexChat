<#
.SYNOPSIS
    Builds the LexChat application images locally and exports them for offline transfer.

.DESCRIPTION
    This script is intended to be run on an ONLINE machine. It uses docker-compose
    to build the 'lexchat-backend' and 'lexchat-frontend' images, which bakes all
    the npm and pip dependencies straight into the image. It then exports the
    fully compiled images into the \binaries\raw\docker\ folder so they can be
    zipped up and transferred to the air-gapped server.
#>

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path "$PSScriptRoot\.."
$DockerDir = "$RepoRoot\binaries\raw\docker"

Write-Host "=== LexChat Offline Image Builder ===" -ForegroundColor Cyan

# Check for Docker
if (-not (Get-Command "docker-compose" -ErrorAction SilentlyContinue)) {
    Write-Warning "docker-compose command not found! Please ensure Docker Desktop is installed and running."
    exit 1
}

# Ensure the output directory exists
if (-not (Test-Path $DockerDir)) {
    New-Item -Path $DockerDir -ItemType Directory -Force | Out-Null
}

Write-Host "Building application images from source..." -ForegroundColor Yellow
Set-Location $RepoRoot

# We run docker-compose build to let it use the Dockerfiles and build the images.
# We explicitly tag them so we can save them later.
# docker-compose build normally tags them as `<foldername>_<servicename>`
# Let's run a standard build first.
docker-compose build

Write-Host "Exporting backend application image to .tar..." -ForegroundColor Cyan
# The default tag name is usually the lowercase folder name + service name
# Let's find the exact dynamic name or just explicitly tag and save.
$BackendImageId = docker images -q "lexchat-backend"
if (-not $BackendImageId) {
    $BackendImageId = docker images -q "*lexchat*backend*" 
}

if ($BackendImageId) {
    docker save -o "$DockerDir\lexchat-backend.tar" $BackendImageId[0]
    Write-Host "Saved lexchat-backend.tar!" -ForegroundColor Green
}
else {
    Write-Warning "Could not locate the compiled backend image to export."
}

Write-Host "Exporting frontend application image to .tar..." -ForegroundColor Cyan
$FrontendImageId = docker images -q "lexchat-frontend"
if (-not $FrontendImageId) {
    $FrontendImageId = docker images -q "*lexchat*frontend*"
}

if ($FrontendImageId) {
    docker save -o "$DockerDir\lexchat-frontend.tar" $FrontendImageId[0]
    Write-Host "Saved lexchat-frontend.tar!" -ForegroundColor Green
}
else {
    Write-Warning "Could not locate the compiled frontend image to export."
}

Write-Host "=== Offline Build Process Complete ===" -ForegroundColor Green
Write-Host "You can now run 'compress_and_chunk.ps1' to zip these new images up!" -ForegroundColor Yellow
