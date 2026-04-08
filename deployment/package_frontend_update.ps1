<#
.SYNOPSIS
    Packages the pre-built frontend into a zip for transfer to an air-gapped machine.
    Run this on the dev machine after making frontend changes.
#>

$ErrorActionPreference = "Stop"
$RepoRoot = "$PSScriptRoot\.."
$DistDir = "$RepoRoot\client\dist"
$OutputZip = "$RepoRoot\frontend_update.zip"

if (!(Test-Path $DistDir)) {
    Write-Error "client\dist not found. Build the frontend first: npm run build"
    exit 1
}

if (Test-Path $OutputZip) {
    Remove-Item $OutputZip -Force
}

Write-Host "Packaging frontend dist..." -ForegroundColor Cyan
Compress-Archive -Path "$DistDir\*" -DestinationPath $OutputZip
Write-Host "Done. Transfer '$OutputZip' to the target machine and run 'apply_frontend_update.ps1'." -ForegroundColor Green
