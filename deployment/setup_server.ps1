<#
.SYNOPSIS
    Bootstraps a Windows Server 2022 instance for LexChat.
    Installs Chocolatey, Git, Docker Desktop, and clones the repository.

.DESCRIPTION
    This script requires Administrator privileges.
    It will:
    1. Install Chocolatey.
    2. Install Git and Docker Desktop.
    3. Clone the LexChat repository.
    4. Start the application using rebuild_docker.ps1.

.PARAMETER RepoUrl
    The URL of the Git repository to clone. Defaults to prompt if not provided.

.EXAMPLE
    .\setup_server.ps1 -RepoUrl "https://github.com/delphium226/LexChat.git"
#>

param(
    [string]$RepoUrl
)

# 1. Check for Administrator Privileges
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Warning "This script requires Administrator privileges!"
    Write-Warning "Please right-click PowerShell and select 'Run as Administrator'."
    exit
}

$ErrorActionPreference = "Stop"

# 2. Install Chocolatey
if (-not (Get-Command "choco" -ErrorAction SilentlyContinue)) {
    Write-Host "Installing Chocolatey..." -ForegroundColor Cyan
    Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
    
    # Reload environment variables so 'choco' is available immediately
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
}
else {
    Write-Host "Chocolatey is already installed." -ForegroundColor Green
}

# 3. Install Dependencies (Git, Docker Desktop)
Write-Host "Checking for Git..." -ForegroundColor Cyan
if (-not (Get-Command "git" -ErrorAction SilentlyContinue)) {
    Write-Host "Installing Git..."
    choco install git -y --params "/GitAndUnixToolsOnPath"
    # Refreshenv equivalent (simple path reload often not enough for git, but we try)
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
}
else {
    Write-Host "Git is already installed." -ForegroundColor Green
}

Write-Host "Checking for Docker..." -ForegroundColor Cyan
if (-not (Get-Command "docker" -ErrorAction SilentlyContinue)) {
    Write-Host "Installing Docker Desktop..."
    choco install docker-desktop -y
    
    Write-Warning "Docker Desktop has been installed."
    Write-Warning "YOU MUST REBOOT THE SERVER NOW TO COMPLETE DOCKER INSTALLATION."
    Write-Warning "After reboot, log in again and run this script again to continue."
    
    $reboot = Read-Host "Do you want to reboot now? (y/n)"
    if ($reboot -eq 'y') {
        Restart-Computer
    }
    exit
}
else {
    Write-Host "Docker is already installed." -ForegroundColor Green
}

# 4. Clone Repository
$RepoPath = Join-Path $HOME "Documents\LexChat"

if (-not (Test-Path $RepoPath)) {
    if ([string]::IsNullOrWhiteSpace($RepoUrl)) {
        $RepoUrl = Read-Host "Please enter the Git Repository URL (e.g., https://github.com/user/repo.git)"
    }
    
    if ([string]::IsNullOrWhiteSpace($RepoUrl)) {
        Write-Error "Repository URL is required to proceed."
        exit
    }

    Write-Host "Cloning repository to $RepoPath..." -ForegroundColor Cyan
    git clone $RepoUrl $RepoPath
}
else {
    Write-Host "Repository already exists at $RepoPath. Skipping clone." -ForegroundColor Green
}

# 5. Build and Run
Set-Location $RepoPath
Write-Host "Starting deployment at $RepoPath..." -ForegroundColor Cyan

# Check if rebuild_docker.ps1 exists
if (Test-Path "rebuild_docker.ps1") {
    .\rebuild_docker.ps1
}
else {
    Write-Error "rebuild_docker.ps1 not found in repository root!"
}

Write-Host "Setup Complete!" -ForegroundColor Green
