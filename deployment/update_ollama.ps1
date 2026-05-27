<#
.SYNOPSIS
    Updates Ollama to a specific version and restores cloud model manifests.

.DESCRIPTION
    Run as Administrator on the target server after git pull.

    Steps:
      1. Stops Ollama (service or process).
      2. Installs OllamaSetup.exe — either downloaded automatically or supplied manually.
      3. Copies cloud model manifests and blobs from deployment\ollama_models\ into
         the Ollama models directory (%USERPROFILE%\.ollama\models or %OLLAMA_MODELS%).
      4. Restarts Ollama.

    INSTALLER DOWNLOAD
    The script tries these URLs in order:
      1. https://ollama.com/download/OllamaSetup.exe  (likely accessible if ollama.ai is whitelisted)
      2. https://github.com/ollama/ollama/releases/download/<version>/OllamaSetup.exe

    If neither URL is reachable, place OllamaSetup.exe manually in the repo root
    (C:\Projects\LexChat\OllamaSetup.exe) before running this script — it will be
    used automatically and deleted afterwards. Do NOT commit it (it is ~2 GB).

    MODEL MANIFESTS
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

$OllamaVersion   = "v0.24.0"
$DownloadUrls    = @(
    "https://ollama.com/download/OllamaSetup.exe",
    "https://github.com/ollama/ollama/releases/download/$OllamaVersion/OllamaSetup.exe"
)
$InstallerPath   = "$env:TEMP\OllamaSetup.exe"
$RepoRoot        = Split-Path $PSScriptRoot -Parent
$ManualInstaller = "$RepoRoot\OllamaSetup.exe"
$ModelsSrc       = "$RepoRoot\deployment\ollama_models"

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
# 2. Locate or download installer
# ---------------------------------------------------------------------------
Write-Host "[2/4] Locating OllamaSetup.exe..."

$installerReady = $false

# Check for manually placed installer first
if (Test-Path $ManualInstaller) {
    Write-Host "      Using manually placed installer at $ManualInstaller"
    $InstallerPath = $ManualInstaller
    $installerReady = $true
}

# Try each download URL in turn
if (-not $installerReady) {
    foreach ($url in $DownloadUrls) {
        Write-Host "      Trying: $url"
        try {
            Invoke-WebRequest -Uri $url -OutFile $InstallerPath -UseBasicParsing -TimeoutSec 30
            Write-Host "      Downloaded successfully."
            $installerReady = $true
            break
        } catch {
            Write-Host "      Failed: $_"
        }
    }
}

if (-not $installerReady) {
    Write-Host ""
    Write-Host "ERROR: Could not obtain OllamaSetup.exe." -ForegroundColor Red
    Write-Host ""
    Write-Host "To install manually:" -ForegroundColor Yellow
    Write-Host "  1. Download OllamaSetup.exe ($OllamaVersion) on a machine with internet access:"
    Write-Host "     https://github.com/ollama/ollama/releases/download/$OllamaVersion/OllamaSetup.exe"
    Write-Host "  2. Copy it to: $RepoRoot\OllamaSetup.exe"
    Write-Host "  3. Re-run this script."
    Write-Host ""
    Write-Host "The script will continue to restore model manifests without updating Ollama."
    Write-Host ""
} else {
    Write-Host "      Installing (silent)..."
    $result = Start-Process -FilePath $InstallerPath -ArgumentList "/VERYSILENT", "/NORESTART" -PassThru -Wait
    if ($result.ExitCode -ne 0) {
        Write-Warning "Installer exited with code $($result.ExitCode) — check if Ollama updated correctly."
    } else {
        Write-Host "      Ollama $OllamaVersion installed."
    }
    # Clean up temp download (not the manually placed one)
    if ($InstallerPath -eq "$env:TEMP\OllamaSetup.exe") {
        Remove-Item $InstallerPath -ErrorAction SilentlyContinue
    }
}

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
        $ollamaExe = (Get-Command ollama -ErrorAction SilentlyContinue)
        $ollamaExePath = if ($ollamaExe) { $ollamaExe.Source } else { $null }
        if (-not $ollamaExePath) {
            $ollamaExePath = Get-ChildItem "C:\Users" -Recurse -Filter "ollama.exe" -ErrorAction SilentlyContinue |
                             Select-Object -First 1 -ExpandProperty FullName
        }
        if ($ollamaExePath) {
            Start-Process -FilePath $ollamaExePath -ArgumentList "serve" -WindowStyle Hidden
            Write-Host "      ollama serve started in background."
        } else {
            Write-Warning "Could not find ollama.exe — start Ollama manually."
        }
    }
}

Write-Host ""
Write-Host "=== Done ===" -ForegroundColor Green
if ($installerReady) {
    Write-Host "Ollama $OllamaVersion installed and cloud model manifests restored."
} else {
    Write-Host "Cloud model manifests restored. Ollama binary was NOT updated (no installer available)."
}
Write-Host "Restart LexChat: deployment\stop_native.cmd then deployment\start_native.cmd"
Write-Host ""
