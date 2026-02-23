$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path "$PSScriptRoot\.."
$BinariesDir = "$RepoRoot\binaries"
$RawDir = "$BinariesDir\raw"
$ZipPath = "$BinariesDir\offline_dependencies.zip"

Write-Host "Checking for existing part files to clean up..." -ForegroundColor Cyan
Get-ChildItem -Path $BinariesDir -Filter "offline_dependencies.zip.part*" | Remove-Item -Force

Write-Host "Compressing $RawDir into $ZipPath using tar.exe (this avoids the 2GB PS5.1 limit)..." -ForegroundColor Cyan
if (Test-Path $ZipPath) {
    Remove-Item -Path $ZipPath -Force
}

Set-Location $BinariesDir
# Use built-in Windows tar to create zip, bypassing PS 5.1 Compress-Archive limitations
tar.exe -a -c -f offline_dependencies.zip raw

Write-Host "Compression complete!" -ForegroundColor Green
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
    # Using 000 padding so we don't hit the part1, part10, part2 string sorting issue which corrupts reassembly!
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

# Delete the large original zip so it isn't accidentally committed
Remove-Item -Path $ZipPath -Force
