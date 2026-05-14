# LexChat proxy troubleshooter
# Run from the server_py directory: .\test_proxy.ps1
# Reads HTTPS_PROXY and OPENROUTER_API_KEY from .env.native, then runs three tests:
#   1. TCP reachability of the proxy host
#   2. Unauthenticated HTTPS request to openrouter.ai through the proxy
#   3. Authenticated request using the stored API key

$envFile = Join-Path $PSScriptRoot ".env.native"
if (-not (Test-Path $envFile)) {
    Write-Host "[FAIL] .env.native not found at $envFile" -ForegroundColor Red
    exit 1
}

# Parse key=value pairs from .env.native
$envVars = @{}
foreach ($line in Get-Content $envFile) {
    if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
        $envVars[$Matches[1]] = $Matches[2].Trim()
    }
}

$httpsProxy = $envVars['HTTPS_PROXY']
if (-not $httpsProxy) {
    Write-Host "[FAIL] HTTPS_PROXY not set in .env.native" -ForegroundColor Red
    exit 1
}

$apiKey = $envVars['OPENROUTER_API_KEY']

# Show proxy URL with password masked
$displayProxy = $httpsProxy -replace '(:)[^:/@]+(@)', '$1***$2'
Write-Host ""
Write-Host "HTTPS_PROXY : $displayProxy" -ForegroundColor Cyan
Write-Host "API key     : $(if ($apiKey) { $apiKey.Substring(0, [Math]::Min(12, $apiKey.Length)) + '...' } else { '(not set)' })" -ForegroundColor Cyan
Write-Host ""

# ── Helpers ─────────────────────────────────────────────────────────────────

function New-ProxiedRequest($url, $proxy, $proxyUri, $authHeader) {
    $req = [System.Net.HttpWebRequest]::Create($url)
    $req.Proxy  = $proxy
    $req.Timeout = 20000
    $req.Method  = "GET"
    if ($authHeader) { $req.Headers.Add("Authorization", $authHeader) }
    return $req
}

function Build-Proxy($proxyUrl, $proxyUri) {
    $p = New-Object System.Net.WebProxy($proxyUrl, $true)
    if ($proxyUri.UserInfo -and $proxyUri.UserInfo -ne '') {
        $parts = $proxyUri.UserInfo.Split(':', 2)
        $user  = [System.Uri]::UnescapeDataString($parts[0])
        $pass  = if ($parts.Length -gt 1) { [System.Uri]::UnescapeDataString($parts[1]) } else { '' }
        $p.Credentials = New-Object System.Net.NetworkCredential($user, $pass)
    }
    return $p
}

# ── Parse proxy URI ──────────────────────────────────────────────────────────

try {
    $proxyUri = [System.Uri]$httpsProxy
} catch {
    Write-Host "[FAIL] Could not parse HTTPS_PROXY as a URI: $_" -ForegroundColor Red
    exit 1
}

# ── Test 1: TCP to proxy ─────────────────────────────────────────────────────

Write-Host "[TEST 1] TCP connection to proxy $($proxyUri.Host):$($proxyUri.Port)" -ForegroundColor Yellow
$tcp = Test-NetConnection -ComputerName $proxyUri.Host -Port $proxyUri.Port -WarningAction SilentlyContinue -InformationLevel Quiet
if ($tcp.TcpTestSucceeded) {
    Write-Host "  PASS - proxy is reachable" -ForegroundColor Green
} else {
    Write-Host "  FAIL - cannot reach proxy host/port; check HTTPS_PROXY value" -ForegroundColor Red
    exit 1
}

# ── Test 2: Unauthenticated request through proxy ────────────────────────────

Write-Host ""
Write-Host "[TEST 2] GET https://openrouter.ai/api/v1/models (no API key)" -ForegroundColor Yellow
try {
    $proxy = Build-Proxy $httpsProxy $proxyUri
    $req   = New-ProxiedRequest "https://openrouter.ai/api/v1/models" $proxy $proxyUri $null
    $resp  = $req.GetResponse()
    $code  = [int]$resp.StatusCode
    $resp.Close()
    Write-Host "  PASS - HTTP $code (proxy is routing to openrouter.ai)" -ForegroundColor Green
} catch [System.Net.WebException] {
    if ($_.Exception.Response) {
        $code = [int]$_.Exception.Response.StatusCode
        switch ($code) {
            407 { Write-Host "  FAIL - 407 Proxy Authentication Required; credentials in HTTPS_PROXY are wrong or missing" -ForegroundColor Red }
            401 { Write-Host "  PASS (expected) - 401 Unauthorized from openrouter.ai (proxy is working, just no API key supplied)" -ForegroundColor Green }
            403 { Write-Host "  PASS (expected) - 403 Forbidden from openrouter.ai (proxy is working)" -ForegroundColor Green }
            default { Write-Host "  FAIL - HTTP $code : $($_.Exception.Message)" -ForegroundColor Red }
        }
    } else {
        Write-Host "  FAIL - $($_.Exception.Message)" -ForegroundColor Red
    }
} catch {
    Write-Host "  FAIL - $($_.Exception.Message)" -ForegroundColor Red
}

# ── Test 3: Authenticated request with API key ───────────────────────────────

Write-Host ""
if (-not $apiKey) {
    Write-Host "[TEST 3] Skipped - OPENROUTER_API_KEY not set in .env.native" -ForegroundColor DarkGray
} else {
    Write-Host "[TEST 3] GET https://openrouter.ai/api/v1/models (with API key)" -ForegroundColor Yellow
    try {
        $proxy = Build-Proxy $httpsProxy $proxyUri
        $req   = New-ProxiedRequest "https://openrouter.ai/api/v1/models" $proxy $proxyUri "Bearer $apiKey"
        $resp  = $req.GetResponse()
        $code  = [int]$resp.StatusCode

        $reader  = New-Object System.IO.StreamReader($resp.GetResponseStream())
        $body    = $reader.ReadToEnd()
        $reader.Close(); $resp.Close()

        $modelCount = ([regex]::Matches($body, '"id"')).Count
        Write-Host "  PASS - HTTP $code, received $modelCount model entries" -ForegroundColor Green
    } catch [System.Net.WebException] {
        if ($_.Exception.Response) {
            $code = [int]$_.Exception.Response.StatusCode
            Write-Host "  FAIL - HTTP $code : $($_.Exception.Message)" -ForegroundColor Red
        } else {
            Write-Host "  FAIL - $($_.Exception.Message)" -ForegroundColor Red
        }
    } catch {
        Write-Host "  FAIL - $($_.Exception.Message)" -ForegroundColor Red
    }
}

Write-Host ""
