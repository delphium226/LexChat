#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Hardens Windows Defender Firewall for the LexChat demo VM.

.DESCRIPTION
    - Allows inbound HTTP on port 80 (all sources)
    - Allows inbound RDP on port 3389 (LAN subnet only)
    - Disables all other pre-existing inbound Allow rules
    - Sets the default inbound action to Block on all profiles

    Run this from the VM console or ensure your RDP session is on the
    configured subnet before executing -- the RDP rule is created before
    anything is disabled, so an in-progress session should survive.

.NOTES
    Re-running the script is safe: existing LexChatDemo rules are removed
    and recreated, so settings stay consistent.
#>

# ── Configuration ────────────────────────────────────────────────────────────
$RDP_SUBNET = "192.168.1.0/24"   # <-- set to your LAN subnet
$RULE_PREFIX = "LexChatDemo"
# ─────────────────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "==================================================="
Write-Host "  LexChat Demo VM -- Firewall Hardening"
Write-Host "==================================================="
Write-Host ""

# Step 1: Remove any previously created LexChatDemo rules (idempotent re-run)
$existing = Get-NetFirewallRule -DisplayName "$RULE_PREFIX*" -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "[1/4] Removing existing $RULE_PREFIX rules..."
    $existing | Remove-NetFirewallRule
} else {
    Write-Host "[1/4] No existing $RULE_PREFIX rules found."
}

# Step 2: Create allow rules BEFORE disabling anything (preserves active RDP session)
Write-Host ""
Write-Host "[2/4] Creating allow rules..."

New-NetFirewallRule `
    -DisplayName "$RULE_PREFIX - HTTP (port 80)" `
    -Direction Inbound `
    -Protocol TCP `
    -LocalPort 80 `
    -Action Allow `
    -Profile Any `
    -Enabled True | Out-Null
Write-Host "   Allowed: TCP port 80 (HTTP) from any source"

New-NetFirewallRule `
    -DisplayName "$RULE_PREFIX - RDP (port 3389, LAN only)" `
    -Direction Inbound `
    -Protocol TCP `
    -LocalPort 3389 `
    -RemoteAddress $RDP_SUBNET `
    -Action Allow `
    -Profile Any `
    -Enabled True | Out-Null
Write-Host "   Allowed: TCP port 3389 (RDP) from $RDP_SUBNET"

# Step 3: Disable all other inbound Allow rules
Write-Host ""
Write-Host "[3/4] Disabling all other inbound Allow rules..."
$disabled = 0
Get-NetFirewallRule -Direction Inbound -Action Allow -Enabled True |
    Where-Object { $_.DisplayName -notlike "$RULE_PREFIX*" } |
    ForEach-Object {
        $_ | Disable-NetFirewallRule
        $disabled++
    }
Write-Host "   Disabled $disabled pre-existing inbound Allow rule(s)."

# Step 4: Set default inbound policy to Block on all profiles
Write-Host ""
Write-Host "[4/4] Setting default inbound action to Block (all profiles)..."
Set-NetFirewallProfile -Profile Domain, Private, Public -DefaultInboundAction Block
Write-Host "   Done."

Write-Host ""
Write-Host "==================================================="
Write-Host "  Hardening complete."
Write-Host "  Open inbound ports: 80 (any), 3389 ($RDP_SUBNET)"
Write-Host "==================================================="
Write-Host ""
