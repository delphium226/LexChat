<#
.SYNOPSIS
    Updates Ollama to a specific version and restores cloud model manifests.

.DESCRIPTION
    Run as Administrator on the target server after git pull.

    1. Stops Ollama (service or process).
    2. Downloads OllamaSetup.exe from GitHub and installs it silently.
    3. Copies cloud model manifests and blobs from deployment\ollama_models\ into
       the Ollama models directory (%USERPROFILE%\.ollama\models or %OLLAMA_MODELS%).
    4. Restarts Ollama.

    Cloud models have no local weights — manifests are a few hundred bytes each.
    The full set is committed to deployment\ollama_models\ so git pull keeps them
    current without any separate file transfer.

    To update to a newer Ollama version in future:
      1. Update $OllamaVersion below.
      2. Pull models on the dev machine: ollama pull <model>
      3. Re-copy deployment\ollama_models\ from ~/.ollama/models/ on the dev machine.
      4. Commit and push.

.EXAMPLE
    # In an elevated PowerShell session on the target server:
    cd C:\Projects\LexChat
    .\deployment\update_ollama.ps1
#>

#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"

$OllamaVersion  = "v0.24.0"
$InstallerUrl   = "https://github.com/ollama/ollama/releases/download/$OllamaVersion/OllamaSetup.exe"
$InstallerPath  = "$env:TEMP\OllamaSetup.exe"
$RepoRoot       = Split-Path $PSScriptRoot -Parent
$ModelsSrc      = "$RepoRoot\deployment\ollama_models"

Write-Host ""
Write-Host "=== Ollama Updater ($OllamaVersion) ===" -ForegroundColor Cyan
Write-Host ""

# ---------------------------------------------------------------------------
# 1. Stop Ollama
# ---------------------------------------------------------------------------
Write-Host "[1/4] Stopping Ollama..."

$svc = Get-Service -Name "Ollama" -ErrorAction SilentlyContinue
if ($svc -and $svc.Status -eq "Running") {
    Stop-Service -Name "Ollama" -Force
    Write-Host "      Stopped Ollama service."
} else {
    $proc = Get-Process -Name "ollama" -ErrorAction SilentlyContinue
    if ($proc) {
        $proc | Stop-Process -Force
        Write-Host "      Killed ollama process."
    } else {
        Write-Host "      Ollama not running."
    }
}
Start-Sleep -Seconds 2

# ---------------------------------------------------------------------------
# 2. Download and install
# ---------------------------------------------------------------------------
Write-Host "[2/4] Downloading OllamaSetup.exe $OllamaVersion..."
Invoke-WebRequest -Uri $InstallerUrl -OutFile $InstallerPath -UseBasicParsing
Write-Host "      Downloaded to $InstallerPath"

Write-Host "      Installing (silent)..."
$proc = Start-Process -FilePath $InstallerPath -ArgumentList "/VERYSILENT", "/NORESTART" -PassThru -Wait
if ($proc.ExitCode -ne 0) {
    Write-Warning "Installer exited with code $($proc.ExitCode) — check if Ollama updated correctly."
} else {
    Write-Host "      Ollama $OllamaVersion installed."
}
Remove-Item $InstallerPath -ErrorAction SilentlyContinue

# ---------------------------------------------------------------------------
# 3. Restore model manifests and blobs
# ---------------------------------------------------------------------------
Write-Host "[3/4] Restoring model manifests..."

$modelsDest = if ($env:OLLAMA_MODELS) { $env:OLLAMA_MODELS } else { "$env:USERPROFILE\.ollama\models" }
Write-Host "      Target: $modelsDest"

if (-not (Test-Path $ModelsSrc)) {
    Write-Error "deployment\ollama_models\ not found at $ModelsSrc. Run git pull first."
    exit 1
}

New-Item -ItemType Directory -Force -Path $modelsDest | Out-Null
Copy-Item -Path "$ModelsSrc\*" -Destination $modelsDest -Recurse -Force
Write-Host "      Model files restored."

# ---------------------------------------------------------------------------
# 4. Start Ollama
# ---------------------------------------------------------------------------
Write-Host "[4/4] Starting Ollama..."

$svc = Get-Service -Name "Ollama" -ErrorAction SilentlyContinue
if ($svc) {
    Start-Service -Name "Ollama"
    Write-Host "      Ollama service started."
} else {
    $task = Get-ScheduledTask -TaskName "Ollama Autostart" -ErrorAction SilentlyContinue
    if ($task) {
        Start-ScheduledTask -TaskName "Ollama Autostart"
        Write-Host "      Ollama Autostart task triggered."
    } else {
        # Find executable and start directly
        $ollamaExe = (Get-Command ollama -ErrorAction SilentlyContinue)?.Source
        if (-not $ollamaExe) {
            $ollamaExe = Get-ChildItem "C:\Users" -Recurse -Filter "ollama.exe" -ErrorAction SilentlyContinue |
                         Select-Object -First 1 -ExpandProperty FullName
        }
        if ($ollamaExe) {
            Start-Process -FilePath $ollamaExe -ArgumentList "serve" -WindowStyle Hidden
            Write-Host "      ollama serve started in background."
        } else {
            Write-Warning "Could not find ollama.exe — start Ollama manually."
        }
    }
}

Write-Host ""
Write-Host "=== Done ===" -ForegroundColor Green
Write-Host "Ollama $OllamaVersion is installed and cloud model manifests are restored."
Write-Host "Restart LexChat: deployment\stop_native.cmd then deployment\start_native.cmd"
Write-Host ""
