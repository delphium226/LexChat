<#
.SYNOPSIS
    Tests all external API endpoints used by the LexChat legislation and parliament chatbots.

.DESCRIPTION
    Reads LEX_API_URL and TWFY_API_KEY from server_py/.env.
    Tests are grouped by bot: legislation bot (LEX API + National Archives) first,
    then parliament bot (TWFY + Parliament.uk APIs).
    TWFY-dependent tests are skipped (not failed) when TWFY_API_KEY is absent.
    get_hansard_debate tests chain from search_hansard results to use real gids.
    Exits 0 if all runnable tests pass, 1 if any fail.
#>

# ---------------------------------------------------------------------------
# Config -- read LEX_API_URL and TWFY_API_KEY from .env
# ---------------------------------------------------------------------------

$DefaultLexUrl = "https://lex.lab.i.ai.gov.uk"
$EnvFile       = Join-Path $PSScriptRoot ".env"

$LexBaseUrl = $DefaultLexUrl
$TwfyApiKey = ""

if (Test-Path $EnvFile) {
    foreach ($line in (Get-Content $EnvFile)) {
        if ($line -match '^\s*LEX_API_URL\s*=\s*(.+)$') {
            $LexBaseUrl = $Matches[1].Trim().TrimEnd('/')
        }
        if ($line -match '^\s*TWFY_API_KEY\s*=\s*(.+)$') {
            $TwfyApiKey = $Matches[1].Trim()
        }
    }
}

$TwfyBase          = "https://www.theyworkforyou.com/api"
$CaseLawAtomUrl    = "https://caselaw.nationalarchives.gov.uk/atom.xml"
$ParliamentMembers = "https://members-api.parliament.uk/api/Members/Search"
$ParliamentBills   = "https://bills-api.parliament.uk/api/v1/Bills"
$ScottishBills     = "https://data.parliament.scot/api/bills"

$TwfyStatus = if ($TwfyApiKey) { "[SET]" } else { "[NOT SET -- TWFY tests will be skipped]" }

Write-Host ""
Write-Host "============================================================"
Write-Host "API Connectivity Tests -- LexChat Chatbots"
Write-Host "============================================================"
Write-Host "LEX base URL   : $LexBaseUrl"
Write-Host "Case law URL   : $CaseLawAtomUrl"
Write-Host "TWFY base URL  : $TwfyBase"
Write-Host "TWFY API key   : $TwfyStatus"
Write-Host ""

# ---------------------------------------------------------------------------
# Skip SSL certificate validation (Windows PowerShell 5.1 compatible)
# ---------------------------------------------------------------------------

Add-Type @"
using System.Net;
using System.Security.Cryptography.X509Certificates;
public class TrustAllCerts : ICertificatePolicy {
    public bool CheckValidationResult(
        ServicePoint sp, X509Certificate cert, WebRequest req, int problem) { return true; }
}
"@
[System.Net.ServicePointManager]::CertificatePolicy = New-Object TrustAllCerts
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

$PassCount = 0
$FailCount = 0
$SkipCount = 0

function Test-Endpoint {
    param(
        [string]$Label,
        [string]$Url,
        [string]$Method   = "POST",
        [hashtable]$Body  = $null,
        [hashtable]$Query = $null,
        [switch]$Capture          # when set, return response body for chaining (e.g. gid extraction)
    )

    # Build display URL, masking the TWFY key value
    $displayUrl = $Url
    if ($Query) {
        $qsParts = $Query.GetEnumerator() | ForEach-Object {
            if ($_.Key -eq "key") { "key=***" } else { "$($_.Key)=$($_.Value)" }
        }
        $displayUrl = "${Url}?" + ($qsParts -join "&")
    }

    Write-Host -NoNewline "  [$Label] $Method $displayUrl ... "

    try {
        $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

        if ($Method -eq "POST") {
            $jsonBody = $Body | ConvertTo-Json -Compress
            $response = Invoke-WebRequest `
                -Uri             $Url `
                -Method          POST `
                -Body            $jsonBody `
                -ContentType     "application/json" `
                -TimeoutSec      30 `
                -UseBasicParsing `
                -ErrorAction     Stop
        } else {
            if ($Query) {
                $uriBuilder = [System.UriBuilder]$Url
                $uriBuilder.Query = ($Query.GetEnumerator() | ForEach-Object {
                    "$($_.Key)=$([Uri]::EscapeDataString($_.Value.ToString()))"
                }) -join "&"
                $Url = $uriBuilder.Uri.AbsoluteUri
            }
            $response = Invoke-WebRequest `
                -Uri             $Url `
                -Method          GET `
                -TimeoutSec      30 `
                -UseBasicParsing `
                -ErrorAction     Stop
        }

        $stopwatch.Stop()
        $ms     = $stopwatch.ElapsedMilliseconds
        $status = $response.StatusCode

        if ($status -ge 200 -and $status -lt 300) {
            Write-Host "PASS ($status, ${ms}ms)"
            $script:PassCount++
            $fullContent = $response.Content
            $preview = if ($fullContent.Length -gt 200) { $fullContent.Substring(0, 200) + "..." } else { $fullContent }
            Write-Host "         Preview: $preview"
            Write-Host ""
            if ($Capture) { return $fullContent }
        } else {
            Write-Host "FAIL (HTTP $status)"
            $script:FailCount++
            Write-Host ""
        }
    } catch {
        $stopwatch.Stop()
        Write-Host "FAIL ($_)"
        $script:FailCount++
        Write-Host ""
    }

    return $null
}

function Skip-Test {
    param([string]$Label, [string]$Reason)
    Write-Host "  [$Label] SKIP -- $Reason"
    Write-Host ""
    $script:SkipCount++
}

# Extract the first gid from a raw TWFY getHansard JSON response body.
# The raw TWFY response is a dict with a "rows" key (or the root is an array).
function Get-TwfyGid {
    param([string]$Content)
    if (-not $Content) { return $null }
    try {
        $parsed = $Content | ConvertFrom-Json
        $rows   = if ($parsed -is [array]) { $parsed } else { $parsed.rows }
        if ($rows -and $rows.Count -gt 0) { return $rows[0].gid }
    } catch {}
    return $null
}

# ===========================================================================
# GROUP 1: LEGISLATION BOT -- LEX API + National Archives case law
# ===========================================================================

Write-Host "--- GROUP 1: LEGISLATION BOT ---"
Write-Host "    LEX API ($LexBaseUrl)"
Write-Host "    National Archives case law ($CaseLawAtomUrl)"
Write-Host ""

Write-Host "1. search_legislation -- basic search"
Test-Endpoint `
    -Label  "search_legislation" `
    -Url    "$LexBaseUrl/legislation/search" `
    -Method POST `
    -Body   @{ query = "Health and Safety at Work Act"; limit = 3; include_text = $false }

Write-Host "2. search_legislation -- with year filter"
Test-Endpoint `
    -Label  "search_legislation (year)" `
    -Url    "$LexBaseUrl/legislation/search" `
    -Method POST `
    -Body   @{ query = "Health and Safety at Work Act"; year_from = 1974; year_to = 1974; limit = 3; include_text = $false }

Write-Host "3. search_legislation_sections"
Test-Endpoint `
    -Label  "search_legislation_sections" `
    -Url    "$LexBaseUrl/legislation/section/search" `
    -Method POST `
    -Body   @{ query = "general duty of employer"; legislation_id = "ukpga/1974/37"; limit = 3 }

Write-Host "4. get_legislation_text"
Test-Endpoint `
    -Label  "get_legislation_text" `
    -Url    "$LexBaseUrl/legislation/text" `
    -Method POST `
    -Body   @{ legislation_id = "ukpga/1974/37" }

Write-Host "5. search_case_law -- basic search"
Test-Endpoint `
    -Label  "search_case_law" `
    -Url    $CaseLawAtomUrl `
    -Method GET `
    -Query  @{ query = "fair dismissal reasonable adjustment" }

Write-Host "6. search_case_law -- court filter (uksc)"
Test-Endpoint `
    -Label  "search_case_law (court=uksc)" `
    -Url    $CaseLawAtomUrl `
    -Method GET `
    -Query  @{ query = "judicial review"; court = "uksc" }

Write-Host "7. search_case_law -- date filter"
Test-Endpoint `
    -Label  "search_case_law (date filter)" `
    -Url    $CaseLawAtomUrl `
    -Method GET `
    -Query  @{ query = "employment tribunal"; date_from = "2024-01-01"; date_to = "2024-12-31" }

# ===========================================================================
# GROUP 2: PARLIAMENT BOT -- TWFY + Parliament.uk APIs
# ===========================================================================

Write-Host "--- GROUP 2: PARLIAMENT BOT ---"
Write-Host "    TheyWorkForYou API ($TwfyBase)"
Write-Host "    Parliament Members API ($ParliamentMembers)"
Write-Host "    Parliament Bills API ($ParliamentBills)"
Write-Host "    Scottish Parliament Bills ($ScottishBills)"
Write-Host ""

# --- search_hansard ---
# Capture results to chain into get_hansard_debate tests (valid gids without hardcoding)

Write-Host "8. search_hansard -- Commons debates (TWFY getHansard)"
$CommonsContent = $null
if ($TwfyApiKey) {
    $CommonsContent = Test-Endpoint `
        -Label   "search_hansard (Commons)" `
        -Url     "$TwfyBase/getHansard" `
        -Method  GET `
        -Query   @{ key = $TwfyApiKey; output = "js"; search = "housing supply planning"; num = 10 } `
        -Capture
} else {
    Skip-Test -Label "search_hansard (Commons)" -Reason "TWFY_API_KEY not set"
}

Write-Host "9. search_hansard -- Lords (TWFY getHansard?type=lords)"
$LordsContent = $null
if ($TwfyApiKey) {
    $LordsContent = Test-Endpoint `
        -Label   "search_hansard (Lords)" `
        -Url     "$TwfyBase/getHansard" `
        -Method  GET `
        -Query   @{ key = $TwfyApiKey; output = "js"; search = "criminal justice sentencing"; type = "lords"; num = 10 } `
        -Capture
} else {
    Skip-Test -Label "search_hansard (Lords)" -Reason "TWFY_API_KEY not set"
}

Write-Host "10. search_hansard -- Written answers (TWFY getHansard?type=wrans)"
$WransContent = $null
if ($TwfyApiKey) {
    $WransContent = Test-Endpoint `
        -Label   "search_hansard (Wrans)" `
        -Url     "$TwfyBase/getHansard" `
        -Method  GET `
        -Query   @{ key = $TwfyApiKey; output = "js"; search = "NHS waiting times"; type = "wrans"; num = 10 } `
        -Capture
} else {
    Skip-Test -Label "search_hansard (Wrans)" -Reason "TWFY_API_KEY not set"
}

# --- get_hansard_debate (chains gids from the search_hansard calls above) ---

Write-Host "11. get_hansard_debate -- Commons (TWFY getDebates)"
$CommonsGid = Get-TwfyGid -Content $CommonsContent
if ($CommonsGid) {
    Test-Endpoint `
        -Label  "get_hansard_debate (Commons)" `
        -Url    "$TwfyBase/getDebates" `
        -Method GET `
        -Query  @{ key = $TwfyApiKey; output = "js"; id = $CommonsGid }
} elseif (-not $TwfyApiKey) {
    Skip-Test -Label "get_hansard_debate (Commons)" -Reason "TWFY_API_KEY not set"
} else {
    Skip-Test -Label "get_hansard_debate (Commons)" -Reason "no gid returned by search_hansard (Commons)"
}

Write-Host "12. get_hansard_debate -- Lords (TWFY getLords)"
$LordsGid = Get-TwfyGid -Content $LordsContent
if ($LordsGid) {
    Test-Endpoint `
        -Label  "get_hansard_debate (Lords)" `
        -Url    "$TwfyBase/getLords" `
        -Method GET `
        -Query  @{ key = $TwfyApiKey; output = "js"; id = $LordsGid }
} elseif (-not $TwfyApiKey) {
    Skip-Test -Label "get_hansard_debate (Lords)" -Reason "TWFY_API_KEY not set"
} else {
    Skip-Test -Label "get_hansard_debate (Lords)" -Reason "no gid returned by search_hansard (Lords)"
}

Write-Host "13. get_hansard_debate -- Written answers (TWFY getWrans)"
$WransGid = Get-TwfyGid -Content $WransContent
if ($WransGid) {
    Test-Endpoint `
        -Label  "get_hansard_debate (Wrans)" `
        -Url    "$TwfyBase/getWrans" `
        -Method GET `
        -Query  @{ key = $TwfyApiKey; output = "js"; id = $WransGid }
} elseif (-not $TwfyApiKey) {
    Skip-Test -Label "get_hansard_debate (Wrans)" -Reason "TWFY_API_KEY not set"
} else {
    Skip-Test -Label "get_hansard_debate (Wrans)" -Reason "no gid returned by search_hansard (Wrans)"
}

# --- get_member_info ---

Write-Host "14. get_member_info -- Commons (Parliament Members API)"
Test-Endpoint `
    -Label  "get_member_info (Commons)" `
    -Url    $ParliamentMembers `
    -Method GET `
    -Query  @{ Name = "Keir Starmer"; House = 1; IsCurrentMember = "false"; Skip = 0; Take = 3 }

Write-Host "15. get_member_info -- Lords (Parliament Members API, House=2)"
Test-Endpoint `
    -Label  "get_member_info (Lords)" `
    -Url    $ParliamentMembers `
    -Method GET `
    -Query  @{ Name = "Baroness Hale"; House = 2; IsCurrentMember = "false"; Skip = 0; Take = 3 }

Write-Host "16. get_member_info -- Scotland MSP (TWFY getMSPInfo)"
if ($TwfyApiKey) {
    Test-Endpoint `
        -Label  "get_member_info (Scotland)" `
        -Url    "$TwfyBase/getMSPInfo" `
        -Method GET `
        -Query  @{ key = $TwfyApiKey; output = "js"; search = "John Swinney" }
} else {
    Skip-Test -Label "get_member_info (Scotland)" -Reason "TWFY_API_KEY not set"
}

# --- search_bills ---

Write-Host "17. search_bills -- UK Westminster (Parliament Bills API)"
Test-Endpoint `
    -Label  "search_bills (UK)" `
    -Url    $ParliamentBills `
    -Method GET `
    -Query  @{ SearchTerm = "Renters Rights"; SortOrder = "DateUpdatedDescending"; Take = 5; Skip = 0 }

Write-Host "18. search_bills -- Scotland (data.parliament.scot -- no search param, filtered client-side)"
Test-Endpoint `
    -Label  "search_bills (Scotland)" `
    -Url    $ScottishBills `
    -Method GET

# --- search_scottish_parliament ---

Write-Host "19. search_scottish_parliament -- debates (TWFY getHansard?type=sp)"
$SpContent = $null
if ($TwfyApiKey) {
    $SpContent = Test-Endpoint `
        -Label   "search_scottish_parliament" `
        -Url     "$TwfyBase/getHansard" `
        -Method  GET `
        -Query   @{ key = $TwfyApiKey; output = "js"; search = "education Scotland curriculum"; type = "sp"; num = 10 } `
        -Capture
} else {
    Skip-Test -Label "search_scottish_parliament" -Reason "TWFY_API_KEY not set"
}

Write-Host "20. search_scottish_parliament -- written answers (TWFY getHansard?type=spwrans)"
if ($TwfyApiKey) {
    Test-Endpoint `
        -Label  "search_scottish_parliament (wrans)" `
        -Url    "$TwfyBase/getHansard" `
        -Method GET `
        -Query  @{ key = $TwfyApiKey; output = "js"; search = "health board Scotland"; type = "spwrans"; num = 10 }
} else {
    Skip-Test -Label "search_scottish_parliament (wrans)" -Reason "TWFY_API_KEY not set"
}

Write-Host "21. get_hansard_debate -- Scottish Parliament (TWFY getSP)"
$SpGid = Get-TwfyGid -Content $SpContent
if ($SpGid) {
    Test-Endpoint `
        -Label  "get_hansard_debate (SP)" `
        -Url    "$TwfyBase/getSP" `
        -Method GET `
        -Query  @{ key = $TwfyApiKey; output = "js"; id = $SpGid }
} elseif (-not $TwfyApiKey) {
    Skip-Test -Label "get_hansard_debate (SP)" -Reason "TWFY_API_KEY not set"
} else {
    Skip-Test -Label "get_hansard_debate (SP)" -Reason "no gid returned by search_scottish_parliament"
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

$Total = $PassCount + $FailCount + $SkipCount
Write-Host "============================================================"
Write-Host "Results: $PassCount passed, $FailCount failed, $SkipCount skipped (of $Total tests)"

if ($FailCount -gt 0) {
    Write-Host "FAIL -- $FailCount endpoint(s) did not respond as expected." -ForegroundColor Red
    exit 1
} else {
    Write-Host "PASS -- all runnable endpoints healthy." -ForegroundColor Green
    exit 0
}
