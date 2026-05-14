# LexChat proxy troubleshooter
# Run from the server_py directory: .\test_proxy.ps1
#
# Sections:
#   A. System proxy settings  — WinHTTP (services), WinINET (user), .NET default
#   B. .env.native HTTPS_PROXY — what the Python backend actually uses
#   Tests 1-3 run against the .env.native proxy
#   Test  4   runs against the system proxy if one is found and differs from .env.native

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
$apiKey     = $envVars['OPENROUTER_API_KEY']

# ── Helpers ──────────────────────────────────────────────────────────────────

function Format-MaskedProxy($url) {
    return $url -replace '(:)[^:/@]+(@)', '$1***$2'
}

function New-ProxiedRequest($url, $webProxy, $authHeader) {
    $req = [System.Net.HttpWebRequest]::Create($url)
    $req.Proxy   = $webProxy
    $req.Timeout = 20000
    $req.Method  = "GET"
    if ($authHeader) { $req.Headers.Add("Authorization", $authHeader) }
    return $req
}

function New-WebProxyFromUrl($proxyUrl) {
    $uri = [System.Uri]$proxyUrl
    $p   = New-Object System.Net.WebProxy($proxyUrl, $true)
    if ($uri.UserInfo -and $uri.UserInfo -ne '') {
        $parts = $uri.UserInfo.Split(':', 2)
        $user  = [System.Uri]::UnescapeDataString($parts[0])
        $pass  = if ($parts.Length -gt 1) { [System.Uri]::UnescapeDataString($parts[1]) } else { '' }
        $p.Credentials = New-Object System.Net.NetworkCredential($user, $pass)
    }
    return $p
}

function Test-TcpPort($proxyHost, $port) {
    $tcp = New-Object System.Net.Sockets.TcpClient
    try {
        $ar     = $tcp.BeginConnect($proxyHost, $port, $null, $null)
        $waited = $ar.AsyncWaitHandle.WaitOne(5000, $false)
        if ($waited -and $tcp.Connected) {
            $tcp.EndConnect($ar)
            return $true
        }
        return $false
    } catch {
        return $false
    } finally {
        $tcp.Close()
    }
}

function Test-ProxyConnectivity($label, $proxyUrl, $withApiKey) {
    Write-Host ""
    $uri = $null
    try { $uri = [System.Uri]$proxyUrl } catch {
        Write-Host "  Cannot parse proxy URL: $_" -ForegroundColor Red
        return
    }

    # TCP
    Write-Host "  [TCP]  $($uri.Host):$($uri.Port) ..." -NoNewline
    if (Test-TcpPort $uri.Host $uri.Port) {
        Write-Host " PASS" -ForegroundColor Green
    } else {
        Write-Host " FAIL (timeout/refused)" -ForegroundColor Red
    }

    # Unauthenticated HTTP
    Write-Host "  [HTTP] GET openrouter.ai (no key) ..." -NoNewline
    try {
        $wp   = New-WebProxyFromUrl $proxyUrl
        $req  = New-ProxiedRequest "https://openrouter.ai/api/v1/models" $wp $null
        $resp = $req.GetResponse()
        $code = [int]$resp.StatusCode
        $resp.Close()
        Write-Host " PASS (HTTP $code)" -ForegroundColor Green
    } catch [System.Net.WebException] {
        if ($_.Exception.Response) {
            $code = [int]$_.Exception.Response.StatusCode
            switch ($code) {
                407 { Write-Host " FAIL (407 — proxy credentials wrong/missing)" -ForegroundColor Red }
                401 { Write-Host " PASS (401 from OpenRouter — proxy is working)" -ForegroundColor Green }
                403 { Write-Host " PASS (403 from OpenRouter — proxy is working)" -ForegroundColor Green }
                default { Write-Host " FAIL (HTTP $code)" -ForegroundColor Red }
            }
        } else {
            Write-Host " FAIL ($($_.Exception.Message))" -ForegroundColor Red
        }
    } catch {
        Write-Host " FAIL ($($_.Exception.Message))" -ForegroundColor Red
    }

    # Authenticated HTTP
    if ($withApiKey -and $apiKey) {
        Write-Host "  [HTTP] GET openrouter.ai (with API key) ..." -NoNewline
        try {
            $wp   = New-WebProxyFromUrl $proxyUrl
            $req  = New-ProxiedRequest "https://openrouter.ai/api/v1/models" $wp "Bearer $apiKey"
            $resp = $req.GetResponse()
            $code = [int]$resp.StatusCode
            $reader = New-Object System.IO.StreamReader($resp.GetResponseStream())
            $body   = $reader.ReadToEnd()
            $reader.Close(); $resp.Close()
            $n = ([regex]::Matches($body, '"id"')).Count
            Write-Host " PASS (HTTP $code, $n models)" -ForegroundColor Green
        } catch [System.Net.WebException] {
            if ($_.Exception.Response) {
                $code = [int]$_.Exception.Response.StatusCode
                Write-Host " FAIL (HTTP $code)" -ForegroundColor Red
            } else {
                Write-Host " FAIL ($($_.Exception.Message))" -ForegroundColor Red
            }
        } catch {
            Write-Host " FAIL ($($_.Exception.Message))" -ForegroundColor Red
        }
    }
}

# ════════════════════════════════════════════════════════════════════════════
# A. SYSTEM PROXY SETTINGS
# ════════════════════════════════════════════════════════════════════════════

Write-Host ""
Write-Host "══ A. System Proxy Settings ════════════════════════════════════" -ForegroundColor Magenta

# WinHTTP (used by Windows services / SYSTEM-account processes)
Write-Host ""
Write-Host "  WinHTTP (netsh winhttp show proxy):" -ForegroundColor Cyan
$winhttp = netsh winhttp show proxy 2>&1
foreach ($line in $winhttp) {
    $t = $line.ToString().Trim()
    if ($t) { Write-Host "    $t" }
}

# WinINET / IE proxy (HKCU — current user)
Write-Host ""
Write-Host "  WinINET / IE proxy (HKCU — current user):" -ForegroundColor Cyan
$regPath = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings'
try {
    $reg = Get-ItemProperty $regPath -ErrorAction Stop
    $enabled = $reg.ProxyEnable
    $server  = $reg.ProxyServer
    $bypass  = $reg.ProxyOverride
    Write-Host "    ProxyEnable   : $enabled"
    Write-Host "    ProxyServer   : $(if ($server) { $server } else { '(not set)' })"
    Write-Host "    ProxyOverride : $(if ($bypass) { $bypass } else { '(not set)' })"

    # Derive a usable WinINET proxy URL for testing
    $winInetProxyUrl = $null
    if ($enabled -eq 1 -and $server) {
        # ProxyServer may be "host:port" or "http=host:port;https=host:port"
        if ($server -match 'https?=([^;]+)') {
            $winInetProxyUrl = "http://$($Matches[1])"
        } elseif ($server -notmatch '=') {
            $winInetProxyUrl = "http://$server"
        }
    }
} catch {
    Write-Host "    (could not read registry: $_)"
    $winInetProxyUrl = $null
}

# .NET default system proxy for openrouter.ai
Write-Host ""
Write-Host "  .NET system proxy for https://openrouter.ai:" -ForegroundColor Cyan
try {
    $sysProxy = [System.Net.WebRequest]::GetSystemWebProxy()
    $target   = [System.Uri]"https://openrouter.ai"
    if ($sysProxy.IsBypassed($target)) {
        Write-Host "    (bypassed — .NET would connect directly)"
        $dotnetProxyUrl = $null
    } else {
        $dotnetProxyUri = $sysProxy.GetProxy($target)
        Write-Host "    Proxy URI : $dotnetProxyUri"
        $dotnetProxyUrl = $dotnetProxyUri.ToString().TrimEnd('/')
        if ($dotnetProxyUrl -eq "https://openrouter.ai") { $dotnetProxyUrl = $null }  # no proxy resolved
    }
} catch {
    Write-Host "    (error reading .NET system proxy: $_)"
    $dotnetProxyUrl = $null
}

# ════════════════════════════════════════════════════════════════════════════
# B. .env.native HTTPS_PROXY
# ════════════════════════════════════════════════════════════════════════════

Write-Host ""
Write-Host "══ B. .env.native HTTPS_PROXY ══════════════════════════════════" -ForegroundColor Magenta
Write-Host ""

if (-not $httpsProxy) {
    Write-Host "  HTTPS_PROXY not set in .env.native" -ForegroundColor Red
    Write-Host "  Add:  HTTPS_PROXY=http://user:pass@proxyhost:port" -ForegroundColor DarkGray
} else {
    $displayProxy = Format-MaskedProxy $httpsProxy
    Write-Host "  HTTPS_PROXY : $displayProxy" -ForegroundColor Cyan
    Write-Host "  API key     : $(if ($apiKey) { $apiKey.Substring(0, [Math]::Min(12, $apiKey.Length)) + '...' } else { '(not set)' })" -ForegroundColor Cyan

    Write-Host ""
    Write-Host "[TEST 1/2/3] Testing .env.native proxy" -ForegroundColor Yellow
    Test-ProxyConnectivity ".env.native" $httpsProxy $true
}

# ════════════════════════════════════════════════════════════════════════════
# TEST 4 — system proxy (if different from .env.native)
# ════════════════════════════════════════════════════════════════════════════

# Collect candidate system proxy URLs (WinINET, .NET)
$systemProxyUrls = @()
if ($winInetProxyUrl)  { $systemProxyUrls += $winInetProxyUrl }
if ($dotnetProxyUrl -and $dotnetProxyUrl -notin $systemProxyUrls) { $systemProxyUrls += $dotnetProxyUrl }

foreach ($sysUrl in $systemProxyUrls) {
    $normSys = $sysUrl.TrimEnd('/')
    $normEnv = if ($httpsProxy) { $httpsProxy.TrimEnd('/') } else { '' }
    if ($normSys -ne $normEnv) {
        Write-Host ""
        Write-Host "[TEST 4] Testing system proxy: $(Format-MaskedProxy $sysUrl)" -ForegroundColor Yellow
        Write-Host "         (uses default Windows credentials — no username/password injected)" -ForegroundColor DarkGray
        # Use default credentials for system proxy
        $wp = New-Object System.Net.WebProxy($sysUrl, $true)
        $wp.UseDefaultCredentials = $true

        Write-Host ""
        Write-Host "  [TCP]  ..." -NoNewline
        $u = [System.Uri]$sysUrl
        if (Test-TcpPort $u.Host $u.Port) {
            Write-Host " PASS" -ForegroundColor Green
        } else {
            Write-Host " FAIL (timeout/refused)" -ForegroundColor Red
        }

        Write-Host "  [HTTP] GET openrouter.ai (no key) ..." -NoNewline
        try {
            $req  = New-ProxiedRequest "https://openrouter.ai/api/v1/models" $wp $null
            $resp = $req.GetResponse()
            $code = [int]$resp.StatusCode
            $resp.Close()
            Write-Host " PASS (HTTP $code)" -ForegroundColor Green
        } catch [System.Net.WebException] {
            if ($_.Exception.Response) {
                $code = [int]$_.Exception.Response.StatusCode
                switch ($code) {
                    407 { Write-Host " FAIL (407 — system proxy needs explicit credentials)" -ForegroundColor Red }
                    401 { Write-Host " PASS (401 from OpenRouter — system proxy is working)" -ForegroundColor Green }
                    403 { Write-Host " PASS (403 from OpenRouter — system proxy is working)" -ForegroundColor Green }
                    default { Write-Host " FAIL (HTTP $code)" -ForegroundColor Red }
                }
            } else {
                Write-Host " FAIL ($($_.Exception.Message))" -ForegroundColor Red
            }
        } catch {
            Write-Host " FAIL ($($_.Exception.Message))" -ForegroundColor Red
        }
    }
}

Write-Host ""
