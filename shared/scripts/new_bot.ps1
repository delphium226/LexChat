<#
.SYNOPSIS
    Provision a new bot instance from the legislation_bot template.

.DESCRIPTION
    Copies bots/legislation/ to bots/<BotId>/, updates bot_config.json with the
    new identity, and appends the uvicorn start command to deployment/local/active_bots.txt.

.PARAMETER BotId
    Unique identifier for the new bot (e.g. "parliament_bot").

.PARAMETER Name
    Display name shown in the UI and bot-info endpoint (e.g. "Parliament Bot").

.PARAMETER Tagline
    Short tagline shown below the name (e.g. "UK Parliamentary Records & Debates").

.PARAMETER Port
    TCP port the new bot will listen on (e.g. 8001).

.EXAMPLE
    .\shared\scripts\new_bot.ps1 -BotId case_law_bot -Name "Case Law Bot" -Tagline "UK Court Judgments" -Port 8002
#>
param(
    [Parameter(Mandatory)]
    [string]$BotId,

    [Parameter(Mandatory)]
    [string]$Name,

    [Parameter(Mandatory)]
    [string]$Tagline,

    [Parameter(Mandatory)]
    [int]$Port
)

$ErrorActionPreference = 'Stop'

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$templateDir = Join-Path $repoRoot 'bots\legislation'
$targetDir   = Join-Path $repoRoot "bots\$BotId"
$localDir    = Join-Path $repoRoot 'deployment\local'

if (Test-Path $targetDir) {
    Write-Error "Bot directory already exists: $targetDir"
    exit 1
}

# Copy template
Write-Host "Copying template to $targetDir ..."
Copy-Item -Recurse -Force $templateDir $targetDir

# Update bot_config.json
$configPath = Join-Path $targetDir 'bot_config.json'
$config = Get-Content $configPath -Raw | ConvertFrom-Json

$config.bot_identity.bot_id    = $BotId
$config.bot_identity.name      = $Name
$config.bot_identity.tagline   = $Tagline
$config.bot_identity.logo_path = "bots/$BotId/assets/logo.png"

$config | ConvertTo-Json -Depth 10 | Set-Content $configPath -Encoding utf8

# Update .env
$envPath = Join-Path $targetDir '.env'
@"
BOT_ID=$BotId
BOT_CONFIG_PATH=bots/$BotId/bot_config.json
"@ | Set-Content $envPath -Encoding utf8

# Create local/ directory and append start command
New-Item -ItemType Directory -Force $localDir | Out-Null
$activeBotsPath = Join-Path $localDir 'active_bots.txt'
$startCmd = "# $Name (port $Port)`n" +
            "cd `"$repoRoot\server_py`" && " +
            "`$env:BOT_ID='$BotId'; " +
            "`$env:BOT_CONFIG_PATH='bots/$BotId/bot_config.json'; " +
            "`$env:DATABASE_URL='postgresql://lexuser:lexpassword@localhost:5432/${BotId}'; " +
            "uvicorn src.main:app --host 0.0.0.0 --port $Port`n"

Add-Content $activeBotsPath $startCmd

Write-Host ""
Write-Host "Bot '$BotId' created at bots\$BotId\"
Write-Host "Start command appended to deployment\local\active_bots.txt"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Create database: psql -U postgres -c `"CREATE DATABASE ${BotId};`""
Write-Host "  2. Grant access:    psql -U postgres -c `"GRANT ALL ON DATABASE ${BotId} TO lexuser;`""
Write-Host "  3. Start the bot:   see deployment\local\active_bots.txt"
Write-Host "  4. Register peers:  .\shared\scripts\register_peer.ps1 ..."
