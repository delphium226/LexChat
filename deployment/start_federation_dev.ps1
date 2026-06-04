param(
    [string]$RepoRoot = (Split-Path $PSScriptRoot -Parent)
)

$ErrorActionPreference = 'Continue'

# Bypass system proxy for all localhost HTTP calls in this session
[System.Net.WebRequest]::DefaultWebProxy = New-Object System.Net.WebProxy

# -------------------------------------------------------
# Step 1: Ensure parliament_bot database exists
# -------------------------------------------------------
Write-Host '[3/4] Ensuring parliament_bot database exists...'

# Parliament bot DB name: must match DATABASE_URL in bots/parliament/.env
$parDbName = 'lexchat_parliament'

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

if (-not $psql) {
    Write-Host '   [WARN] psql not found in PATH or common install locations.'
    Write-Host "          Parliament Bot will fail if $parDbName DB does not exist."
    Write-Host "          Create it manually:  psql -U lexuser -c `"CREATE DATABASE $parDbName;`""
} else {
    $env:PGPASSWORD = 'lexpassword'
    $exists = & $psql -U lexuser -h localhost -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$parDbName'" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "   [WARN] Could not connect to PostgreSQL as lexuser (exit $LASTEXITCODE)."
        Write-Host '          Check that PostgreSQL is accepting connections on localhost:5432.'
    } elseif ($exists -match '1') {
        Write-Host "   $parDbName database already exists."
    } else {
        Write-Host "   Creating $parDbName database..."
        & $psql -U lexuser -h localhost -d postgres -c "CREATE DATABASE $parDbName;" 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Host "   [WARN] Could not create $parDbName database automatically."
            Write-Host "          Run manually:  psql -U lexuser -c `"CREATE DATABASE $parDbName;`""
        } else {
            Write-Host "   $parDbName database created."
        }
    }
    $env:PGPASSWORD = ''
}

# -------------------------------------------------------
# Step 2: Launch both bots in separate windows
# -------------------------------------------------------
Write-Host ''
Write-Host '[4/4] Launching bots and wiring federation...'

$serverDir      = Join-Path $RepoRoot 'server_py'
$legConfigPath  = Join-Path $RepoRoot 'bots\legislation\bot_config.json'
$parConfigPath  = Join-Path $RepoRoot 'bots\parliament\bot_config.json'

# Kill any leftover processes still holding ports 8000/8001
foreach ($port in 8000, 8001) {
    $line = netstat -ano | Select-String ":$port\s" | Select-Object -First 1
    if ($line) {
        $procId = ($line.ToString().Trim() -split '\s+')[-1]
        if ($procId -match '^\d+$') {
            Write-Host "   Stopping process on port $port (PID $procId)..."
            Stop-Process -Id ([int]$procId) -Force -ErrorAction SilentlyContinue
            Start-Sleep 1
        }
    }
}

# Write a small temp .cmd for each bot — avoids all ArgumentList quote-escaping issues.
# BOT_CONFIG_PATH must be absolute because uvicorn CWD is server_py/.

$legScript = "@echo off`r`ncd /d `"$serverDir`"`r`nset BOT_ID=legislation_bot`r`nset BOT_CONFIG_PATH=$legConfigPath`r`npython -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload`r`n"
$legFile = "$env:TEMP\run_legislation_bot.cmd"
[System.IO.File]::WriteAllText($legFile, $legScript, [System.Text.Encoding]::ASCII)
Start-Process cmd.exe -ArgumentList @('/k', $legFile) -WindowStyle Normal

# Load extra env vars from bots/parliament/.env so TWFY_API_KEY, RESEARCH_MODE, etc. are set
$parEnvExtra = ''
$parEnvFile = Join-Path $RepoRoot 'bots\parliament\.env'
if (Test-Path $parEnvFile) {
    Get-Content $parEnvFile | Where-Object { $_ -match '^[A-Z_]+=.' } | ForEach-Object {
        $k, $v = $_ -split '=', 2
        $parEnvExtra += "set $($k.Trim())=$($v.Trim())`r`n"
    }
}

# Load .env first, then override BOT_ID and BOT_CONFIG_PATH with absolute values so
# the relative path in bots/parliament/.env does not win.
$parScript = "@echo off`r`ncd /d `"$serverDir`"`r`n$($parEnvExtra)set BOT_ID=parliament_bot`r`nset BOT_CONFIG_PATH=$parConfigPath`r`npython -m uvicorn src.main:app --host 0.0.0.0 --port 8001 --reload`r`n"
$parFile = "$env:TEMP\run_parliament_bot.cmd"
[System.IO.File]::WriteAllText($parFile, $parScript, [System.Text.Encoding]::ASCII)
Start-Process cmd.exe -ArgumentList @('/k', $parFile) -WindowStyle Normal

Write-Host '   Both bots launching...'

# -------------------------------------------------------
# Step 3: Wait for both bots to respond
# -------------------------------------------------------
Write-Host ''
Write-Host '   Waiting for bots to be ready...'

function Wait-Bot([string]$Url, [string]$Name) {
    $port = ([System.Uri]$Url).Port
    Write-Host "   Waiting for $Name..." -NoNewline
    for ($i = 0; $i -lt 30; $i++) {
        $up = Test-NetConnection -ComputerName localhost -Port $port `
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

$ErrorActionPreference = 'Continue'
$b1 = Wait-Bot 'http://localhost:8000' 'Legislation Bot'
$b2 = Wait-Bot 'http://localhost:8001' 'Parliament Bot'

if (-not $b1 -or -not $b2) {
    Write-Host ''
    Write-Host '[ERROR] One or both bots did not start in time. Check the bot windows for errors.'
    Write-Host '        Peer registration skipped — register manually via Admin Portal > Federation.'
    exit 1
}

# -------------------------------------------------------
# Step 4: Register peers
# -------------------------------------------------------
function Get-AdminToken([string]$BaseUrl) {
    $body = '{"username":"admin","password":"admin"}'
    $r = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/auth/login" `
        -ContentType 'application/json' -Body $body
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

Write-Host '   Fetching admin tokens...'
$t1 = Get-AdminToken 'http://localhost:8000'
$t2 = Get-AdminToken 'http://localhost:8001'

Register-Peer 'http://localhost:8000' $t1 `
    'parliament_bot' 'Parliament Bot' `
    'http://localhost:8001' $t2 `
    'Searches UK Parliamentary records, Hansard debates, and committee proceedings'

Register-Peer 'http://localhost:8001' $t2 `
    'legislation_bot' 'Legislation Bot' `
    'http://localhost:8000' $t1 `
    'Searches UK legislation, statutory instruments, and regulatory guidance'

Write-Host ''
Write-Host '   Federation wired. Both bots are peered and ready.'
