<#
.SYNOPSIS
    Tests LEX API endpoints used by LexChat.

.DESCRIPTION
    Reads LEX_API_URL from server_py/.env (falls back to the config.py default).
    Tests all three LEX API endpoints and the National Archives case law endpoint.
    Exits with code 0 if all pass, 1 if any fail.
#>

# ---------------------------------------------------------------------------
# Config — read LEX_API_URL from .env, fall back to config.py default
# ---------------------------------------------------------------------------

$DefaultLexUrl = "https://lex.lab.i.ai.gov.uk"
$EnvFile = Join-Path $PSScriptRoot ".env"

$LexBaseUrl = $DefaultLexUrl
if (Test-Path $EnvFile) {
    $line = Select-String -Path $EnvFile -Pattern '^\s*LEX_API_URL\s*=' | Select-Object -First 1
    if ($line) {
        $LexBaseUrl = ($line.Line -split '=', 2)[1].Trim().TrimEnd('/')
    }
}

$CaseLawUrl = "https://caselaw.nationalarchives.gov.uk/atom.xml"

Write-Host ""
Write-Host "LEX API Endpoint Tests"
Write-Host "======================"
Write-Host "LEX base URL : $LexBaseUrl"
Write-Host "Case law URL : $CaseLawUrl"
Write-Host ""

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

$PassCount = 0
$FailCount = 0

function Test-Endpoint {
    param(
        [string]$Label,
        [string]$Url,
        [string]$Method = "POST",
        [hashtable]$Body = $null,
        [hashtable]$Query = $null
    )

    $displayUrl = $Url
    if ($Query) {
        $qs = ($Query.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" }) -join "&"
        $displayUrl = "${Url}?${qs}"
    }

    Write-Host -NoNewline "  [$Label] $Method $displayUrl ... "

    try {
        $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

        if ($Method -eq "POST") {
            $jsonBody = $Body | ConvertTo-Json -Compress
            $response = Invoke-WebRequest `
                -Uri $Url `
                -Method POST `
                -Body $jsonBody `
                -ContentType "application/json" `
                -TimeoutSec 30 `
                -SkipCertificateCheck `
                -ErrorAction Stop
        } else {
            # Build URI with query params
            if ($Query) {
                $uriBuilder = [System.UriBuilder]$Url
                $uriBuilder.Query = ($Query.GetEnumerator() | ForEach-Object { "$($_.Key)=$([Uri]::EscapeDataString($_.Value))" }) -join "&"
                $Url = $uriBuilder.Uri.AbsoluteUri
            }
            $response = Invoke-WebRequest `
                -Uri $Url `
                -Method GET `
                -TimeoutSec 30 `
                -SkipCertificateCheck `
                -ErrorAction Stop
        }

        $stopwatch.Stop()
        $ms = $stopwatch.ElapsedMilliseconds

        $status = $response.StatusCode
        if ($status -ge 200 -and $status -lt 300) {
            Write-Host "PASS ($status, ${ms}ms)"
            $script:PassCount++

            # Show a short content preview
            $content = $response.Content
            if ($content.Length -gt 200) { $content = $content.Substring(0, 200) + "..." }
            Write-Host "         Preview: $content"
        } else {
            Write-Host "FAIL (HTTP $status)"
            $script:FailCount++
        }
    } catch {
        $stopwatch.Stop()
        Write-Host "FAIL ($_)"
        $script:FailCount++
    }

    Write-Host ""
}

# ---------------------------------------------------------------------------
# LEX API — legislation/search
# ---------------------------------------------------------------------------

Write-Host "1. search_legislation  [POST $LexBaseUrl/legislation/search]"
Test-Endpoint `
    -Label "legislation search" `
    -Url "$LexBaseUrl/legislation/search" `
    -Method "POST" `
    -Body @{
        query       = "Health and Safety at Work Act"
        year_from   = 1974
        year_to     = 1974
        limit       = 3
        include_text = $false
    }

# ---------------------------------------------------------------------------
# LEX API — legislation/section/search
# ---------------------------------------------------------------------------

Write-Host "2. search_legislation_sections  [POST $LexBaseUrl/legislation/section/search]"
Test-Endpoint `
    -Label "section search" `
    -Url "$LexBaseUrl/legislation/section/search" `
    -Method "POST" `
    -Body @{
        query          = "general duty of employer"
        legislation_id = "ukpga/1974/37"
        limit          = 3
    }

# ---------------------------------------------------------------------------
# LEX API — legislation/text
# ---------------------------------------------------------------------------

Write-Host "3. get_legislation_text  [POST $LexBaseUrl/legislation/text]"
Test-Endpoint `
    -Label "legislation text" `
    -Url "$LexBaseUrl/legislation/text" `
    -Method "POST" `
    -Body @{
        legislation_id = "ukpga/1974/37"
    }

# ---------------------------------------------------------------------------
# National Archives — case law Atom feed
# ---------------------------------------------------------------------------

Write-Host "4. search_case_law  [GET $CaseLawUrl]"
Test-Endpoint `
    -Label "case law atom" `
    -Url $CaseLawUrl `
    -Method "GET" `
    -Query @{
        query = "fair dismissal reasonable adjustment"
    }

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

$Total = $PassCount + $FailCount
Write-Host "======================"
Write-Host "Results: $PassCount/$Total passed"

if ($FailCount -gt 0) {
    Write-Host "FAIL — $FailCount endpoint(s) did not respond as expected." -ForegroundColor Red
    exit 1
} else {
    Write-Host "PASS — all endpoints healthy." -ForegroundColor Green
    exit 0
}
