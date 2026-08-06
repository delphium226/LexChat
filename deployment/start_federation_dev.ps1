param(
    [string]$RepoRoot = (Split-Path $PSScriptRoot -Parent)
)

$ErrorActionPreference = 'Continue'

# Bypass system proxy for all localhost HTTP calls in this session
[System.Net.WebRequest]::DefaultWebProxy = New-Object System.Net.WebProxy

# Bot registry — one entry per federated bot. The legislation bot is the base
# deployment (no .env override); the parliament, Westminster and drafting bots
# each have their own DB, port, config and .env.
#
# Step 4 wires a FULL MESH, so adding an entry here registers the new bot as a
# peer of every existing bot and vice versa — that is how the drafting bot gets
# `consult_peer` access to the legislation bot for "what does s.7 actually say"
# without duplicating LEX tooling.
$bots = @(
    [ordered]@{
        Id       = 'legislation_bot'
        Name     = 'Legislation Bot'
        Port     = 8000
        Db       = $null   # uses the default lexchat DB
        Config   = Join-Path $RepoRoot 'bots\legislation\bot_config.json'
        EnvFile  = $null
        PeerDesc = 'Searches UK legislation, statutory instruments, and regulatory guidance'
    },
    [ordered]@{
        Id       = 'parliament_bot'
        Name     = 'Parliament Bot'
        Port     = 8001
        Db       = 'lexchat_parliament'
        Config   = Join-Path $RepoRoot 'bots\parliament\bot_config.json'
        EnvFile  = Join-Path $RepoRoot 'bots\parliament\.env'
        PeerDesc = 'Searches Scottish Parliament (Holyrood) plenary and committee proceedings, MSPs, and Scottish bills'
    },
    [ordered]@{
        Id       = 'westminster_bot'
        Name     = 'Westminster Bot'
        Port     = 8002
        Db       = 'lexchat_westminster'
        Config   = Join-Path $RepoRoot 'bots\westminster\bot_config.json'
        EnvFile  = Join-Path $RepoRoot 'bots\westminster\.env'
        PeerDesc = 'Searches UK Parliament (Westminster) Hansard debates, written statements, Members, and UK bills'
    },
    [ordered]@{
        Id       = 'drafting_bot'
        Name     = 'Drafting Bot'
        Port     = 8003
        Db       = 'lexchat_drafting'
        Config   = Join-Path $RepoRoot 'bots\drafting\bot_config.json'
        EnvFile  = Join-Path $RepoRoot 'bots\drafting\.env'
        PeerDesc = 'Answers legislative drafting-guidance questions and finds comparable enacted drafting precedent'
    }
)

# -------------------------------------------------------
# Step 1: Ensure each bot's database exists
# -------------------------------------------------------
Write-Host '[1/4] Ensuring per-bot databases exist...'

$psqlPaths = @(
    'psql',
    'C:\Program Files\PostgreSQL\18\bin\psql.exe',
    'C:\Program Files\PostgreSQL\17\bin\psql.exe',
    'C:\Program Files\PostgreSQL\16\bin\psql.exe',
    'C:\Program Files\PostgreSQL\15\bin\psql.exe'
)
$psql = $null
foreach ($p in $psqlPaths) {
    if (Get-Command $p -ErrorAction SilentlyContinue) { $psql = $p; break }
    if (Test-Path $p -ErrorAction SilentlyContinue)   { $psql = $p; break }
}

$dbNames = $bots | Where-Object { $_.Db } | ForEach-Object { $_.Db }

if (-not $psql) {
    Write-Host '   [WARN] psql not found in PATH or common install locations.'
    Write-Host "          Bots will fail if their DBs do not exist. Create manually:"
    foreach ($d in $dbNames) {
        Write-Host "          psql -U lexuser -c `"CREATE DATABASE $d;`""
    }
} else {
    $env:PGPASSWORD = 'lexpassword'
    foreach ($dbName in $dbNames) {
        $exists = & $psql -U lexuser -h localhost -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$dbName'" 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "   [WARN] Could not connect to PostgreSQL as lexuser (exit $LASTEXITCODE)."
            Write-Host '          Check that PostgreSQL is accepting connections on localhost:5432.'
            break
        } elseif ($exists -match '1') {
            Write-Host "   $dbName database already exists."
        } else {
            Write-Host "   Creating $dbName database..."
            & $psql -U lexuser -h localhost -d postgres -c "CREATE DATABASE $dbName;" 2>&1
            if ($LASTEXITCODE -ne 0) {
                Write-Host "   [WARN] Could not create $dbName automatically."
                Write-Host "          Run manually:  psql -U lexuser -c `"CREATE DATABASE $dbName;`""
            } else {
                Write-Host "   $dbName database created."
            }
        }
    }
    $env:PGPASSWORD = ''
}

# -------------------------------------------------------
# Step 2: Launch every bot in its own window
# -------------------------------------------------------
Write-Host ''
Write-Host '[2/4] Launching bots...'

$serverDir = Join-Path $RepoRoot 'server_py'

# Kill any leftover processes still holding the bot ports
foreach ($bot in $bots) {
    $line = netstat -ano | Select-String ":$($bot.Port)\s" | Select-Object -First 1
    if ($line) {
        $procId = ($line.ToString().Trim() -split '\s+')[-1]
        if ($procId -match '^\d+$') {
            Write-Host "   Stopping process on port $($bot.Port) (PID $procId)..."
            Stop-Process -Id ([int]$procId) -Force -ErrorAction SilentlyContinue
            Start-Sleep 1
        }
    }
}

# Write a small temp .cmd per bot — avoids all ArgumentList quote-escaping issues.
# The bot's .env is loaded FIRST, then BOT_ID and BOT_CONFIG_PATH are overridden
# with absolute values so the relative path inside the .env cannot win
# (uvicorn's CWD is server_py/, not the repo root).
foreach ($bot in $bots) {
    $envExtra = ''
    if ($bot.EnvFile -and (Test-Path $bot.EnvFile)) {
        Get-Content $bot.EnvFile | Where-Object { $_ -match '^[A-Z_]+=.' } | ForEach-Object {
            $k, $v = $_ -split '=', 2
            $envExtra += "set $($k.Trim())=$($v.Trim())`r`n"
        }
    }
    $script = "@echo off`r`ncd /d `"$serverDir`"`r`n$($envExtra)set BOT_ID=$($bot.Id)`r`nset BOT_CONFIG_PATH=$($bot.Config)`r`npython -m uvicorn src.main:app --host 0.0.0.0 --port $($bot.Port) --no-access-log --reload`r`n"
    $file = "$env:TEMP\run_$($bot.Id).cmd"
    [System.IO.File]::WriteAllText($file, $script, [System.Text.Encoding]::ASCII)
    Start-Process cmd.exe -ArgumentList @('/k', $file) -WindowStyle Normal
    Write-Host "   $($bot.Name) launching on port $($bot.Port)..."
}

# -------------------------------------------------------
# Step 3: Wait for every bot to respond
# -------------------------------------------------------
Write-Host ''
Write-Host '[3/4] Waiting for bots to be ready...'

function Wait-Bot([int]$Port, [string]$Name) {
    Write-Host "   Waiting for $Name..." -NoNewline
    for ($i = 0; $i -lt 30; $i++) {
        $up = Test-NetConnection -ComputerName localhost -Port $Port `
            -InformationLevel Quiet -WarningAction SilentlyContinue -ErrorAction SilentlyContinue
        if ($up) {
            Write-Host ' ready.'
            return $true
        }
        Write-Host '.' -NoNewline
        Start-Sleep 2
    }
    Write-Host ' TIMEOUT (60s).'
    return $false
}

$allUp = $true
foreach ($bot in $bots) {
    if (-not (Wait-Bot $bot.Port $bot.Name)) { $allUp = $false }
}

if (-not $allUp) {
    Write-Host ''
    Write-Host '[ERROR] One or more bots did not start in time. Check the bot windows for errors.'
    Write-Host '        Peer registration skipped — register manually via Admin Portal > Federation.'
    exit 1
}

# -------------------------------------------------------
# Step 4: Register peers (every bot knows every other bot)
# -------------------------------------------------------
Write-Host ''
Write-Host '[4/4] Wiring federation...'

function Get-AdminToken([string]$BaseUrl) {
    $body = '{"username":"admin","password":"admin"}'
    $r = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/auth/login" `
        -ContentType 'application/json' -Body $body
    return $r.token
}

# Federation peer credentials must not expire, or the bots need periodic
# re-wiring. Exchange the (short-lived) admin login token for a non-expiring
# federation token and store THAT as the peer api_key.
function Get-FederationToken([string]$BaseUrl, [string]$AdminToken) {
    $headers = @{ Authorization = "Bearer $AdminToken" }
    $r = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/auth/federation-token" `
        -Headers $headers -ContentType 'application/json'
    return $r.token
}

function Register-Peer([string]$CallerUrl, [string]$Token,
                        [string]$PeerId, [string]$PeerName,
                        [string]$PeerUrl, [string]$PeerToken,
                        [string]$Description) {
    $headers = @{ Authorization = "Bearer $Token" }
    $body = [ordered]@{
        peer_id     = $PeerId
        name        = $PeerName
        base_url    = $PeerUrl
        api_key     = $PeerToken
        description = $Description
        enabled     = $true
    } | ConvertTo-Json
    try {
        $null = Invoke-RestMethod -Method Post -Uri "$CallerUrl/api/peers" `
            -Headers $headers -ContentType 'application/json' -Body $body
        Write-Host "   Registered '$PeerName' on $CallerUrl"
    } catch {
        $status = $_.Exception.Response.StatusCode.value__
        if ($status -eq 409) {
            Write-Host "   '$PeerName' already registered on $CallerUrl (skipped)"
        } else {
            Write-Host "   [WARN] Could not register '$PeerName': $($_.Exception.Message)"
        }
    }
}

Write-Host '   Fetching admin tokens and minting non-expiring federation tokens...'
foreach ($bot in $bots) {
    $url = "http://localhost:$($bot.Port)"
    $bot.Url = $url
    $adminToken = Get-AdminToken $url
    $bot.AdminToken = $adminToken
    $bot.FedToken = Get-FederationToken $url $adminToken
}

# Full mesh: register every other bot as a peer on each bot.
foreach ($caller in $bots) {
    foreach ($peer in $bots) {
        if ($caller.Id -eq $peer.Id) { continue }
        Register-Peer $caller.Url $caller.AdminToken `
            $peer.Id $peer.Name `
            $peer.Url $peer.FedToken `
            $peer.PeerDesc
    }
}

Write-Host ''
Write-Host '   Federation wired. All bots are peered and ready:'
foreach ($bot in $bots) {
    Write-Host "     $($bot.Name.PadRight(18)) $($bot.Url)"
}
