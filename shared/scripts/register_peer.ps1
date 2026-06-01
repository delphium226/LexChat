<#
.SYNOPSIS
    Register a peer bot in a running bot's peer registry via the admin API.

.DESCRIPTION
    POSTs to <CallerBotUrl>/api/peers with the peer details. The caller bot must
    be running and the provided API key must belong to a valid authenticated user
    (used as the Bearer token).

.PARAMETER CallerBotUrl
    Base URL of the bot that should learn about the peer (e.g. http://localhost:8000).

.PARAMETER CallerApiKey
    JWT token (Bearer) for an admin user on the caller bot.

.PARAMETER PeerId
    Unique peer_id of the peer to register (e.g. "parliament_bot").

.PARAMETER PeerName
    Display name of the peer (e.g. "Parliament Bot").

.PARAMETER PeerBaseUrl
    Base URL of the peer bot (e.g. http://localhost:8001).

.PARAMETER PeerApiKey
    API key (JWT) the caller will use to authenticate with the peer. Optional.

.PARAMETER Description
    Natural-language description shown to the Manager LLM as the consult_peer tool description.

.EXAMPLE
    .\shared\scripts\register_peer.ps1 `
        -CallerBotUrl http://localhost:8000 `
        -CallerApiKey eyJhbGci... `
        -PeerId parliament_bot `
        -PeerName "Parliament Bot" `
        -PeerBaseUrl http://localhost:8001 `
        -PeerApiKey eyJhbGci... `
        -Description "Searches UK Parliamentary records and debates"
#>
param(
    [Parameter(Mandatory)]
    [string]$CallerBotUrl,

    [Parameter(Mandatory)]
    [string]$CallerApiKey,

    [Parameter(Mandatory)]
    [string]$PeerId,

    [Parameter(Mandatory)]
    [string]$PeerName,

    [Parameter(Mandatory)]
    [string]$PeerBaseUrl,

    [string]$PeerApiKey = '',

    [Parameter(Mandatory)]
    [string]$Description
)

$ErrorActionPreference = 'Stop'

$url = "$($CallerBotUrl.TrimEnd('/'))/api/peers"

$body = @{
    peer_id     = $PeerId
    name        = $PeerName
    base_url    = $PeerBaseUrl
    description = $Description
    enabled     = $true
}
if ($PeerApiKey) { $body.api_key = $PeerApiKey }

$headers = @{
    'Content-Type'  = 'application/json'
    'Authorization' = "Bearer $CallerApiKey"
}

Write-Host "Registering peer '$PeerId' on $CallerBotUrl ..."

$response = Invoke-RestMethod `
    -Method Post `
    -Uri $url `
    -Headers $headers `
    -Body ($body | ConvertTo-Json -Depth 5)

Write-Host "Done. Peer created:"
Write-Host "  peer_id  : $($response.peer_id)"
Write-Host "  name     : $($response.name)"
Write-Host "  base_url : $($response.base_url)"
Write-Host "  enabled  : $($response.enabled)"
Write-Host ""
Write-Host "The bot at $CallerBotUrl can now call consult_peer(peer_id='$PeerId', ...)"
