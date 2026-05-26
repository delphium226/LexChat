<#
.SYNOPSIS
    Ensures Ollama starts automatically at boot, independently of LexChat.

.DESCRIPTION
    Run once as Administrator after git pull on the target server.

    If Ollama is already installed as a Windows service (the Ollama installer
    creates one), this script just sets that service to Automatic start.

    Otherwise it registers a "Ollama Autostart" Task Scheduler task that runs
    "ollama serve" as SYSTEM at every boot — the same pattern used by
    install_autostart.ps1 for the LexChat backend.

    Either way, start_background.ps1 will find Ollama already running when the
    LexChat task fires, so the 5-second boot-time wait is avoided.

.EXAMPLE
    # In an elevated PowerShell session:
    cd C:\Projects\LexChat
    .\deployment\install_ollama_autostart.ps1
#>

#Requires -RunAsAdministrator

$taskName = "Ollama Autostart"

Write-Host ""
Write-Host "=== Ollama Autostart Installer ==="
Write-Host ""

# --- Check for an existing Ollama Windows service first ---
$svc = Get-Service -Name "Ollama" -ErrorAction SilentlyContinue
if ($svc) {
    Write-Host "Ollama Windows service found. Setting startup type to Automatic..."
    Set-Service -Name "Ollama" -StartupType Automatic
    if ($svc.Status -ne "Running") {
        Start-Service -Name "Ollama"
        Write-Host "Ollama service started."
    } else {
        Write-Host "Ollama service already running."
    }
    Write-Host ""
    Write-Host "Done. Ollama will start automatically via the Windows service on every boot."
    Write-Host "No Task Scheduler task needed."
    exit 0
}

# --- Ollama is not a service — find the executable ---
$ollamaExe = $null

$ollamaCmd = Get-Command ollama -ErrorAction SilentlyContinue
if ($ollamaCmd) {
    $ollamaExe = $ollamaCmd.Source
} else {
    # Scan user profile directories for a per-user Ollama install
    $userDirs = Get-ChildItem "C:\Users" -Directory -ErrorAction SilentlyContinue
    foreach ($dir in $userDirs) {
        $candidate = "$($dir.FullName)\AppData\Local\Programs\Ollama\ollama.exe"
        if (Test-Path $candidate) {
            $ollamaExe = $candidate
            break
        }
    }
}

if (-not $ollamaExe) {
    Write-Error "Ollama executable not found in PATH or user profiles. Install Ollama and re-run."
    exit 1
}

Write-Host "Ollama found at: $ollamaExe"

# --- Register Task Scheduler task ---
$action = New-ScheduledTaskAction -Execute $ollamaExe -Argument "serve"

$trigger = New-ScheduledTaskTrigger -AtStartup

# ExecutionTimeLimit of zero = no limit (ollama serve is a long-running process).
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -ExecutionTimeLimit ([TimeSpan]::Zero)

$principal = New-ScheduledTaskPrincipal `
    -UserId    "SYSTEM" `
    -LogonType ServiceAccount `
    -RunLevel  Highest

$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Host "Removed existing '$taskName' task."
}

Register-ScheduledTask `
    -TaskName   $taskName `
    -Action     $action `
    -Trigger    $trigger `
    -Settings   $settings `
    -Principal  $principal `
    -Description "Starts Ollama (ollama serve) at system boot without requiring a login." `
    | Out-Null

Write-Host ""
Write-Host "Task '$taskName' registered successfully."
Write-Host "Ollama will start automatically on every boot."
Write-Host ""
Write-Host "To start immediately without rebooting:"
Write-Host "  Start-ScheduledTask -TaskName '$taskName'"
Write-Host ""
