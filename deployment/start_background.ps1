<#
.SYNOPSIS
    Headless LexChat startup — called by the "LexChat Autostart" Task Scheduler task at boot.
    Launches Ollama and the uvicorn backend as background processes with output to log files.
    Do not run this manually; use start_native.cmd for interactive use instead.
#>

$repoRoot  = (Resolve-Path "$PSScriptRoot\..").Path
$logsDir   = "$PSScriptRoot\logs"
$configFile = "$PSScriptRoot\autostart_config.ps1"

if (-not (Test-Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir | Out-Null }

$startLog = "$logsDir\startup.log"
function Log($msg) { Add-Content -Path $startLog -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $msg" }

Log "--- LexChat background start ---"

# Load machine-specific paths written by install_autostart.ps1.
# $LEXCHAT_PYTHON and $LEXCHAT_OLLAMA are set in that file.
if (Test-Path $configFile) {
    . $configFile
} else {
    # Fallback: use venv python if present, else system python
    $venvPy = "$repoRoot\server_py\venv\Scripts\python.exe"
    $LEXCHAT_PYTHON = if (Test-Path $venvPy) { $venvPy } else { "python" }
    $LEXCHAT_OLLAMA = $null
}
Log "Python : $LEXCHAT_PYTHON"
Log "Ollama : $(if ($LEXCHAT_OLLAMA) { $LEXCHAT_OLLAMA } else { '(service or skip)' })"

# --- 1. PostgreSQL (should already auto-start as a Windows service) ---
# The service name is DISCOVERED, not hardcoded. This used to read
# "postgresql-x64-15" while the rest of deployment/ had moved to 18, and the
# failure was silent in the worst way: Get-Service with -ErrorAction
# SilentlyContinue returns $null for a name that does not exist, so the check
# below fell through to the else branch and logged "PostgreSQL already running"
# without ever having started it. A wildcard lookup cannot go stale on the next
# major-version upgrade.
try {
    $pg = Get-Service -Name "postgresql*" -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $pg) {
        Log "WARNING: No PostgreSQL service found (looked for 'postgresql*'). The backend will fail to connect."
    } elseif ($pg.Status -ne "Running") {
        Start-Service -Name $pg.Name
        Start-Sleep -Seconds 3
        Log "PostgreSQL started ($($pg.Name))."
    } else {
        Log "PostgreSQL already running ($($pg.Name))."
    }
} catch {
    Log "WARNING: Could not start PostgreSQL: $_"
}

# --- 2. Ollama ---
$ollamaService = Get-Service -Name "Ollama" -ErrorAction SilentlyContinue
if ($ollamaService) {
    # Ollama is installed as a Windows service — just ensure it is running.
    if ($ollamaService.Status -ne "Running") {
        try { Start-Service -Name "Ollama"; Log "Ollama service started." }
        catch { Log "WARNING: Could not start Ollama service: $_" }
    } else {
        Log "Ollama service already running."
    }
    Start-Sleep -Seconds 3
} elseif ($LEXCHAT_OLLAMA -and (Test-Path $LEXCHAT_OLLAMA)) {
    # Ollama is not a service — launch it as a background process.
    $ollamaRunning = Get-Process -Name "ollama" -ErrorAction SilentlyContinue
    if (-not $ollamaRunning) {
        $env:OLLAMA_NOHISTORY = "1"
        Start-Process -FilePath $LEXCHAT_OLLAMA `
            -ArgumentList "serve" `
            -NoNewWindow `
            -RedirectStandardOutput "$logsDir\ollama.log" `
            -RedirectStandardError  "$logsDir\ollama_err.log"
        Log "Ollama launched as background process."
        Start-Sleep -Seconds 5
    } else {
        Log "Ollama already running."
    }
} else {
    Log "WARNING: Ollama not found. Skipping."
}

# --- 3. Copy .env.native -> .env ---
$envNative = "$repoRoot\server_py\.env.native"
$envDest   = "$repoRoot\server_py\.env"
if (Test-Path $envNative) {
    Copy-Item -Path $envNative -Destination $envDest -Force
    Log ".env.native copied to .env."
} else {
    Log "WARNING: .env.native not found at $envNative"
}

# --- 4. Resolve uvicorn arguments ---
$certFile = "$PSScriptRoot\certs\lexchat.crt"
$keyFile  = "$PSScriptRoot\certs\lexchat.key"
if ((Test-Path $certFile) -and (Test-Path $keyFile)) {
    $uvicornArgs = @("-m", "uvicorn", "src.main:app", "--host", "0.0.0.0",
                     "--port", "443", "--no-access-log",
                     "--ssl-certfile", $certFile,
                     "--ssl-keyfile",  $keyFile)
    Log "SSL certs found — starting on HTTPS port 443."
} else {
    $uvicornArgs = @("-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log")
    Log "No SSL certs — starting on HTTP port 8000."
}

# --- 5. Start uvicorn backend ---
$env:PYTHONUNBUFFERED = "1"
try {
    Start-Process -FilePath $LEXCHAT_PYTHON `
        -ArgumentList $uvicornArgs `
        -WorkingDirectory "$repoRoot\server_py" `
        -NoNewWindow `
        -RedirectStandardOutput "$logsDir\backend.log" `
        -RedirectStandardError  "$logsDir\backend_err.log"
    Log "uvicorn backend launched."
} catch {
    Log "ERROR: Failed to start backend: $_"
}

Log "--- Startup complete ---"
