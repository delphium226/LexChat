<#
.SYNOPSIS
    Applies a frontend update zip to the air-gapped target machine.
    Copy frontend_update.zip to the repo root on the target, then run this script.
#>

$ErrorActionPreference = "Stop"
$RepoRoot = "$PSScriptRoot\.."
$ZipPath = "$RepoRoot\frontend_update.zip"
$DistDir = "$RepoRoot\client\dist"

if (!(Test-Path $ZipPath)) {
    Write-Error "frontend_update.zip not found at $ZipPath. Copy it from the dev machine first."
    exit 1
}

Write-Host "Applying frontend update..." -ForegroundColor Cyan

if (Test-Path $DistDir) {
    Remove-Item -Recurse -Force $DistDir
}
New-Item -ItemType Directory -Force -Path $DistDir | Out-Null
Expand-Archive -Path $ZipPath -DestinationPath $DistDir -Force

Write-Host "Frontend updated successfully." -ForegroundColor Green
Write-Host "Restart the application using 'deployment\start_native.cmd' (or the offline equivalent)."
