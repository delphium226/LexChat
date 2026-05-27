<#
.SYNOPSIS
    Chunks OllamaSetup.exe into 50 MB parts ready for git commit.

.DESCRIPTION
    Run on the dev machine whenever a new Ollama version needs to be deployed.

    1. Place the new OllamaSetup.exe in the repo root (C:\Projects\LexChat\OllamaSetup.exe).
    2. Run this script — it writes binaries\OllamaSetup.exe.part001 ... partNNN.
    3. Update $OllamaVersion in deployment\update_ollama.ps1.
    4. git add binaries\OllamaSetup.exe.part* && git commit && git push.

.EXAMPLE
    cd C:\Projects\LexChat
    .\deployment\chunk_ollama_installer.ps1
#>

$ErrorActionPreference = "Stop"

$RepoRoot   = Split-Path $PSScriptRoot -Parent
$SrcPath    = "$RepoRoot\OllamaSetup.exe"
$OutDir     = "$RepoRoot\binaries"
$ChunkSize  = 50MB

if (-not (Test-Path $SrcPath)) {
    Write-Error "OllamaSetup.exe not found at $SrcPath. Place it there and re-run."
    exit 1
}

$sizeMB = [math]::Round((Get-Item $SrcPath).Length / 1MB, 1)
Write-Host "Source: $SrcPath ($sizeMB MB)" -ForegroundColor Cyan

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

Write-Host "Removing existing chunks..."
Get-ChildItem $OutDir -Filter "OllamaSetup.exe.part*" | Remove-Item -Force

Write-Host "Chunking into 50 MB parts..."
$fs   = [System.IO.File]::OpenRead($SrcPath)
$buf  = New-Object byte[] $ChunkSize
$part = 1

while ($fs.Position -lt $fs.Length) {
    $read = $fs.Read($buf, 0, $ChunkSize)
    $name = "$OutDir\OllamaSetup.exe.part$($part.ToString('000'))"
    $out  = [System.IO.File]::Create($name)
    $out.Write($buf, 0, $read)
    $out.Close()
    Write-Host "  $([System.IO.Path]::GetFileName($name))  ($([math]::Round($read/1MB,1)) MB)"
    $part++
}

$fs.Close()
Write-Host ""
Write-Host "$($part-1) chunks written to $OutDir" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Update `$OllamaVersion in deployment\update_ollama.ps1"
Write-Host "  2. git add binaries\OllamaSetup.exe.part*"
Write-Host "  3. git commit && git push"
Write-Host ""
Write-Host "Do NOT commit OllamaSetup.exe itself (it is ~2 GB)."
