<#
.SYNOPSIS
    Removes the "LexChat Autostart" Task Scheduler task.
    Run as Administrator to revert to manual startup via start_native.cmd.
#>

#Requires -RunAsAdministrator

$taskName = "LexChat Autostart"

$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($task) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Host "Task '$taskName' removed. LexChat will no longer start automatically at boot."
} else {
    Write-Host "Task '$taskName' not found — nothing to remove."
}
