<#
.SYNOPSIS
    Queries Windows Defender Firewall to check if inbound connections are allowed for Ports 80 and 443.
#>

Write-Host "==============================================="
Write-Host " Inspecting Windows Defender Firewall Rules"
Write-Host "==============================================="
Write-Host ""

function Check-PortInboundRule {
    param([int]$Port)
    
    # Get all active TCP Port filters matching this port
    Write-Host "Checking inbound TCP rules for Port $Port..."
    $filters = Get-NetFirewallPortFilter -ErrorAction SilentlyContinue | Where-Object { 
        $_.LocalPort -eq $Port -or $_.LocalPort -match "(^|-)$Port(-|$)" 
    } | Where-Object { $_.Protocol -eq 'TCP' }

    if ($null -eq $filters -or @($filters).Count -eq 0) {
        Write-Host " [X] No specific firewall rules found for Port $Port." -ForegroundColor Red
        return
    }

    # Find which filters correspond to an Enabled, Allow, Inbound Rule
    $allowedRules = @()
    foreach ($filter in $filters) {
        $rule = Get-NetFirewallRule -Name $filter.InstanceID -ErrorAction SilentlyContinue | `
                Where-Object { $_.Direction -eq 'Inbound' -and $_.Action -eq 'Allow' -and $_.Enabled -eq 'True' }
        if ($rule) {
            $allowedRules += $rule
        }
    }

    if ($allowedRules.Count -gt 0) {
        Write-Host " [V] Port $Port is currently OPEN. Allowed by the following rules:" -ForegroundColor Green
        foreach ($rule in $allowedRules) {
            Write-Host "     - $($rule.DisplayName) (Profile: $($rule.Profile))" -ForegroundColor DarkGreen
        }
    } else {
        Write-Host " [X] Port $Port has rules, but none are active/allowed inbound rules." -ForegroundColor Red
    }
}

Check-PortInboundRule -Port 80
Write-Host ""
Check-PortInboundRule -Port 443
Write-Host ""

Write-Host "Note: If no rules are found, Windows blocks inbound ports by default." -ForegroundColor Yellow
Pause
