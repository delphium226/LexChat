<#
.SYNOPSIS
    One-time setup: registers the nightly LexChat database backup as a Task
    Scheduler task running as SYSTEM.

.DESCRIPTION
    Run this once as Administrator on the target server after git pull. It:

      1. Creates the backup directory and locks its ACL down to SYSTEM and the
         local Administrators group only. Dumps contain app_settings (the
         OpenRouter API key) and peer_bots.api_key, so the directory must be no
         more readable than the PostgreSQL data directory itself.
      2. Registers the "LexChat Backup" Application event log source, so that a
         failed nightly run can raise an event even though the run itself has no
         admin rights.
      3. Registers a daily "LexChat Database Backup" task that runs
         backup_databases.ps1 as SYSTEM, with no login required.

    Follows the same idiom as install_autostart.ps1.

.PARAMETER BackupRoot
    Where backups are written. Default C:\LexChatBackups.

.PARAMETER At
    Time of day to run, 24h. Default 02:30 - after the parliament crawler's
    daily delta and well outside working hours.

.EXAMPLE
    # In an elevated PowerShell session:
    cd C:\Projects\LexChat
    .\deployment\install_backup_task.ps1

.EXAMPLE
    .\deployment\install_backup_task.ps1 -BackupRoot D:\Backups\LexChat -At 01:00 -RunNow

.NOTES
    This file is deliberately ASCII-only; see the note in backup_databases.ps1.
#>

#Requires -RunAsAdministrator

[CmdletBinding()]
param(
    [string] $BackupRoot  = "C:\LexChatBackups",
    [string] $At          = "02:30",
    [string] $TaskName    = "LexChat Database Backup",
    [string] $PgBin       = "",
    [int]    $KeepDaily   = 14,
    [int]    $KeepWeekly  = 8,
    [int]    $KeepMonthly = 12,
    [switch] $RunNow
)

$ErrorActionPreference = "Stop"

$scriptDir    = $PSScriptRoot
$backupScript = Join-Path $scriptDir "backup_databases.ps1"
$EventSource  = "LexChat Backup"

Write-Host ""
Write-Host "=== LexChat Database Backup Installer ==="
Write-Host ""

if (-not (Test-Path $backupScript)) {
    Write-Error "backup_databases.ps1 not found at $backupScript"
    exit 1
}

# --- 1. Backup directory ------------------------------------------------------

if (-not (Test-Path $BackupRoot)) {
    New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null
    Write-Host "Created backup directory: $BackupRoot"
} else {
    Write-Host "Backup directory      : $BackupRoot  (already exists)"
}

# --- 2. Lock down the ACL -----------------------------------------------------
# Well-known SIDs rather than names, so this works on a non-English server.

try {
    $systemSid = New-Object System.Security.Principal.SecurityIdentifier("S-1-5-18")      # LOCAL SYSTEM
    $adminsSid = New-Object System.Security.Principal.SecurityIdentifier("S-1-5-32-544")  # BUILTIN\Administrators

    $acl = Get-Acl $BackupRoot
    # $true  = protect from inheritance
    # $false = do not copy the inherited rules down as explicit ones
    $acl.SetAccessRuleProtection($true, $false)
    foreach ($rule in @($acl.Access)) { [void]$acl.RemoveAccessRule($rule) }

    foreach ($sid in @($systemSid, $adminsSid)) {
        $acl.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule(
            $sid, "FullControl", "ContainerInherit,ObjectInherit", "None", "Allow")))
    }
    $acl.SetOwner($adminsSid)
    Set-Acl -Path $BackupRoot -AclObject $acl

    Write-Host "ACL                   : SYSTEM + Administrators only (inheritance disabled)"
} catch {
    Write-Warning "Could not tighten the ACL on $BackupRoot : $($_.Exception.Message)"
    Write-Warning "Set it by hand. Dumps contain the OpenRouter and federation API keys."
}

# --- 3. Event log source ------------------------------------------------------
# Registered here, where we have admin rights, so that the unprivileged nightly
# run can write a failure event without needing them.

try {
    if ([System.Diagnostics.EventLog]::SourceExists($EventSource)) {
        Write-Host "Event log source      : '$EventSource' already registered"
    } else {
        New-EventLog -LogName Application -Source $EventSource
        Write-Host "Event log source      : '$EventSource' registered in the Application log"
    }
} catch {
    Write-Warning "Could not register the event log source: $($_.Exception.Message)"
}

# --- 4. Register the scheduled task ------------------------------------------

$argList = @(
    "-NonInteractive", "-NoProfile", "-ExecutionPolicy", "Bypass",
    "-File", "`"$backupScript`"",
    "-BackupRoot", "`"$BackupRoot`"",
    "-KeepDaily", $KeepDaily,
    "-KeepWeekly", $KeepWeekly,
    "-KeepMonthly", $KeepMonthly
)
if ($PgBin) { $argList += @("-PgBin", "`"$PgBin`"") }

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument ($argList -join " ")

$trigger = New-ScheduledTaskTrigger -Daily -At $At

# StartWhenAvailable   : run a missed backup once the box comes back up.
# ExecutionTimeLimit   : the whole run takes well under a minute at current size;
#                        2h is a generous ceiling that still guarantees the task
#                        cannot hang forever holding a snapshot open.
# MultipleInstances    : never let a slow run overlap the next night's.
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -ExecutionTimeLimit ([TimeSpan]::FromHours(2)) `
    -MultipleInstances IgnoreNew `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

$principal = New-ScheduledTaskPrincipal `
    -UserId   "SYSTEM" `
    -LogonType ServiceAccount `
    -RunLevel Highest

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed existing '$TaskName' task."
}

Register-ScheduledTask `
    -TaskName   $TaskName `
    -Action     $action `
    -Trigger    $trigger `
    -Settings   $settings `
    -Principal  $principal `
    -Description "Nightly pg_dump of every lexchat% database, with verification, manifest and GFS retention. See docs/deployment/BACKUP_RUNBOOK.md." `
    | Out-Null

Write-Host "Scheduled task        : '$TaskName' registered, daily at $At as SYSTEM"

# --- 5. Optionally run it now -------------------------------------------------

if ($RunNow) {
    Write-Host ""
    Write-Host "Running the first backup now..."
    Start-ScheduledTask -TaskName $TaskName
    Start-Sleep -Seconds 5
    Write-Host "Started. Watch it with:"
    Write-Host "  Get-Content '$BackupRoot\logs\backup.log' -Wait"
}

Write-Host ""
Write-Host "Done."
Write-Host ""
Write-Host "Verify the regime is healthy:"
Write-Host "  Get-ScheduledTaskInfo -TaskName '$TaskName' | Select-Object LastRunTime, LastTaskResult, NextRunTime"
Write-Host "    LastTaskResult 0 = the backup succeeded."
Write-Host ""
Write-Host "  Get-Content '$BackupRoot\logs\backup.log' -Tail 30"
Write-Host "  Get-ChildItem '$BackupRoot' -Directory | Sort-Object Name -Descending | Select-Object -First 5"
Write-Host ""
Write-Host "Run it on demand:"
Write-Host "  Start-ScheduledTask -TaskName '$TaskName'"
Write-Host ""
Write-Host "Restore procedure: docs\deployment\BACKUP_RUNBOOK.md"
Write-Host ""
