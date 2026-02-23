<#
.SYNOPSIS
    Reconstructs the offline_dependencies.zip from its chunks and extracts it.

.DESCRIPTION
    This script finds all part files in the \binaries directory, combines them
    in the correct order to re-create offline_dependencies.zip, and then extracts
    the contents back into the \binaries\raw directory for deployment use.
#>

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path "$PSScriptRoot\.."
$BinariesDir = "$RepoRoot\binaries"
$RawDir = "$BinariesDir\raw"
$ZipPath = "$BinariesDir\offline_dependencies.zip"

Write-Host "Reconstructing offline_dependencies.zip from chunks..." -ForegroundColor Cyan

# Check if part files exist
$PartFiles = Get-ChildItem -Path $BinariesDir -Filter "offline_dependencies.zip.part*" | Sort-Object { [int]($_.Name -replace '.*\.part', '') }

if ($PartFiles.Count -eq 0) {
    Write-Host "No part files (offline_dependencies.zip.part*) found in $BinariesDir!" -ForegroundColor Red
    exit 1
}

Write-Host "Found $($PartFiles.Count) part files. Combining..."

# Use copy /b to safely and quickly combine binary files on Windows
$FileList = ($PartFiles.FullName | ForEach-Object { '"{0}"' -f $_ }) -join "+"
$CmdStr = "cmd.exe /c copy /b $FileList `"$ZipPath`""

# Execute the combined command
Invoke-Expression $CmdStr | Out-Null

if (Test-Path $ZipPath) {
    Write-Host "Successfully reconstructed: $ZipPath" -ForegroundColor Green
    $ZipSize = (Get-Item $ZipPath).Length / 1MB
    Write-Host "Total Size: $([math]::Round($ZipSize, 2)) MB" -ForegroundColor Yellow
}
else {
    Write-Host "Failed to reconstruct the zip file!" -ForegroundColor Red
    exit 1
}

Write-Host "Extracting $ZipPath into $RawDir..." -ForegroundColor Cyan
if (Test-Path $RawDir) {
    Write-Host "Cleaning up old raw directory..."
    Remove-Item -Path $RawDir -Recurse -Force
}

# Use tar.exe to extract since PowerShell 5.1 Expand-Archive struggles with large files
Set-Location $BinariesDir
tar.exe -x -f offline_dependencies.zip

Write-Host "Extraction complete!" -ForegroundColor Green
Write-Host "You can now run install_native.ps1 or the docker setup." -ForegroundColor Green
