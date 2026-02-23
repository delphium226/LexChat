<#
.SYNOPSIS
    Downloads all external dependencies required for offline deployment.
    This includes Python packages, Node packages, native installers, and Docker images.

.DESCRIPTION
    The downloaded dependencies are saved into the "binaries\raw" folder and then
    compressed into "binaries\offline_dependencies.zip".
#>

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path "$PSScriptRoot\.."
$BinariesDir = "$RepoRoot\binaries"
$RawDir = "$BinariesDir\raw"

Write-Host "Creating directories in $BinariesDir..." -ForegroundColor Cyan
New-Item -Path "$RawDir\docker" -ItemType Directory -Force | Out-Null


Write-Host "Downloading Docker Images..." -ForegroundColor Cyan
$DockerImages = @(
    "postgres:15",
    "ollama/ollama",
    "python:3.11-slim",
    "node:20-slim",
    "nginx:alpine"
)

foreach ($image in $DockerImages) {
    Write-Host "Pulling $image..."
    docker pull $image
    $safeName = $image.Replace(":", "_").Replace("/", "_")
    Write-Host "Saving $image to docker\$safeName.tar..."
    docker save -o "$RawDir\docker\$safeName.tar" $image
}

Write-Host "Zipping everything up... This may take several minutes." -ForegroundColor Cyan
# Set-Location back to root so we don't hold the client directory
Set-Location $RepoRoot

$ZipPath = "$BinariesDir\offline_dependencies.zip"
if (Test-Path $ZipPath) {
    Remove-Item -Path $ZipPath -Force
}

Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($RawDir, $ZipPath, [System.IO.Compression.CompressionLevel]::Optimal, $false)

Write-Host "Done! The zip file is located at $ZipPath" -ForegroundColor Green
$ZipSize = (Get-Item $ZipPath).Length / 1MB
Write-Host "Total Zip Size: $([math]::Round($ZipSize, 2)) MB" -ForegroundColor Yellow

# Split the zip file into 50MB chunks
Write-Host "Splitting zip file into 50MB chunks for GitHub..." -ForegroundColor Cyan
$ChunkSize = 50MB
$FileStream = [System.IO.File]::OpenRead($ZipPath)
$Buffer = New-Object byte[] $ChunkSize
$PartNumber = 1

while ($FileStream.Position -lt $FileStream.Length) {
    $BytesRead = $FileStream.Read($Buffer, 0, $ChunkSize)
    $PartNumberPadded = $PartNumber.ToString("000")
    $PartFileName = "$ZipPath.part$PartNumberPadded"
    $PartFileStream = [System.IO.File]::Create($PartFileName)
    $PartFileStream.Write($Buffer, 0, $BytesRead)
    $PartFileStream.Close()
    
    Write-Host "Created $PartFileName"
    $PartNumber++
}

$FileStream.Close()
Write-Host "Split complete. You can now commit the .part* files." -ForegroundColor Green
Write-Host "To reassemble, run: Get-Content .\offline_dependencies.zip.part* -Encoding Byte -ReadCount 0 | Set-Content .\offline_dependencies.zip -Encoding Byte" -ForegroundColor Yellow

# Optional: Delete the large original zip so it isn't accidentally committed
Remove-Item -Path $ZipPath -Force
