<#
.SYNOPSIS
    Tests all external API endpoints used by the LexChat legislation and parliament chatbots.

.DESCRIPTION
    Reads LEX_API_URL and TWFY_API_KEY from server_py/.env.
    Tests are grouped by bot: legislation bot (LEX API + National Archives) first,
    then parliament bot (TWFY + Parliament.uk APIs), then SP Official Report crawler.
    TWFY-dependent tests are skipped (not failed) when TWFY_API_KEY is absent.
    get_hansard_debate and get_scottish_committee_transcript tests chain from search
    results to use real IDs without hardcoding.
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
            $LexBaseUrl = $Matches[1].Split('#')[0].Trim().TrimEnd('/')
        }
        if ($line -match '^\s*TWFY_API_KEY\s*=\s*(.+)$') {
            $TwfyApiKey = $Matches[1].Split('#')[0].Trim()
        }
    }
}

$CaseLawBase       = "https://caselaw.nationalarchives.gov.uk"
$TwfyBase          = "https://www.theyworkforyou.com/api"
$ParliamentMembers = "https://members-api.parliament.uk/api/Members/Search"
$ParliamentBills   = "https://bills-api.parliament.uk/api/v1/Bills"
$ScottishBills     = "https://data.parliament.scot/api/bills"
$SpOrBase          = "https://www.parliament.scot/chamber-and-committees/official-report/search-what-was-said-in-parliament"

$TwfyStatus = if ($TwfyApiKey) { "[SET]" } else { "[NOT SET -- TWFY tests will be skipped]" }

Write-Host ""
Write-Host "============================================================"
Write-Host "API Connectivity Tests -- LexChat Chatbots"
Write-Host "============================================================"
Write-Host "LEX base URL         : $LexBaseUrl"
Write-Host "Case law base URL    : $CaseLawBase"
Write-Host "TWFY base URL        : $TwfyBase"
Write-Host "TWFY API key         : $TwfyStatus"
Write-Host "SP Official Report   : $SpOrBase"
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
$Results   = [System.Collections.Generic.List[PSCustomObject]]::new()

function Test-Endpoint {
    param(
        [string]$Label,
        [string]$Url,
        [string]$Method   = "GET",
        [hashtable]$Body  = $null,
        [hashtable]$Query = $null,
        [switch]$Capture          # when set, return response body for chaining
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

    # Preserve base URL before UriBuilder may rewrite it (needed for diagnostics)
    $BaseUrl = $Url

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
            Write-Host "PASS ($status, ${ms}ms)" -ForegroundColor Green
            $script:PassCount++
            $script:Results.Add([PSCustomObject]@{ Label = $Label; Status = "PASS"; Url = $displayUrl })
            $fullContent = $response.Content
            $preview = if ($fullContent.Length -gt 200) { $fullContent.Substring(0, 200) + "..." } else { $fullContent }
            Write-Host "         Preview: $preview"
            Write-Host ""
            if ($Capture) { return $fullContent }
        } else {
            Write-Host "FAIL (HTTP $status)" -ForegroundColor Red
            $script:FailCount++
            $script:Results.Add([PSCustomObject]@{ Label = $Label; Status = "FAIL"; Url = $displayUrl })
            Show-FailureDiagnostics -Url $BaseUrl -HttpStatus $status -ResponseBody $response.Content
        }
    } catch {
        $stopwatch.Stop()
        Write-Host "FAIL ($_)" -ForegroundColor Red
        $script:FailCount++
        $script:Results.Add([PSCustomObject]@{ Label = $Label; Status = "FAIL"; Url = $displayUrl })

        # Attempt to read response body from the caught WebException (HTTP errors thrown by Invoke-WebRequest)
        $caughtEx    = $_.Exception
        $responseBody = $null
        $httpStatus   = 0
        $webEx = $caughtEx -as [System.Net.WebException]
        if (-not $webEx) { $webEx = $caughtEx.InnerException -as [System.Net.WebException] }
        if ($webEx -and $webEx.Response) {
            $httpStatus = [int]$webEx.Response.StatusCode
            try {
                $stream  = $webEx.Response.GetResponseStream()
                $reader  = New-Object System.IO.StreamReader($stream)
                $responseBody = $reader.ReadToEnd()
            } catch {}
        }
        Show-FailureDiagnostics -Url $BaseUrl -Exception $caughtEx -ResponseBody $responseBody -HttpStatus $httpStatus
    }

    return $null
}

function Skip-Test {
    param([string]$Label, [string]$Reason)
    Write-Host "  [$Label] SKIP -- $Reason" -ForegroundColor Yellow
    Write-Host ""
    $script:SkipCount++
    $script:Results.Add([PSCustomObject]@{ Label = $Label; Status = "SKIP"; Url = "" })
}

# ---------------------------------------------------------------------------
# Failure diagnostics
# ---------------------------------------------------------------------------

function Show-FailureDiagnostics {
    param(
        [string]$Url,
        [System.Exception]$Exception   = $null,
        [string]$ResponseBody          = $null,
        [int]$HttpStatus               = 0
    )

    Write-Host "         --- Diagnostics ---"

    # 1. Classify the failure and give a targeted hint
    if ($HttpStatus -gt 0) {
        switch ($HttpStatus) {
            400 { Write-Host "         [HTTP $HttpStatus] Bad request -- check request body/parameters." }
            401 { Write-Host "         [HTTP $HttpStatus] Unauthorized -- API key missing or invalid." }
            403 { Write-Host "         [HTTP $HttpStatus] Forbidden -- API key rejected or IP not whitelisted." }
            404 { Write-Host "         [HTTP $HttpStatus] Not found -- URL path may be wrong." }
            429 { Write-Host "         [HTTP $HttpStatus] Rate limited -- too many requests, try again later." }
            default {
                if ($HttpStatus -ge 500) {
                    Write-Host "         [HTTP $HttpStatus] Server error -- the remote service returned an error."
                } else {
                    Write-Host "         [HTTP $HttpStatus] Unexpected status code."
                }
            }
        }
    }

    if ($Exception) {
        $exMsg   = $Exception.Message
        $innerEx = $Exception.InnerException
        $innerMsg = if ($innerEx) { $innerEx.Message } else { "" }
        $combined = "$exMsg $innerMsg".ToLower()

        Write-Host "         [Error] $exMsg"
        if ($innerMsg) { Write-Host "         [Cause] $innerMsg" }

        if ($combined -match "name.*resolut|could not resolve|no such host|getaddress") {
            Write-Host "         [Hint] DNS resolution failed -- '$Url' hostname not resolvable. Check DNS or proxy settings."
        } elseif ($combined -match "actively refused|connection refused|no connection could be made") {
            Write-Host "         [Hint] Connection refused -- host reachable but port closed. Check firewall or service status."
        } elseif ($combined -match "timed out|a connection attempt failed|operation timed out") {
            Write-Host "         [Hint] Connection timed out -- host unreachable or traffic silently dropped by firewall."
        } elseif ($combined -match "ssl|tls|certificate|handshake|trust") {
            Write-Host "         [Hint] TLS/SSL error -- certificate not trusted or TLS version mismatch."
        } elseif ($combined -match "proxy|407") {
            Write-Host "         [Hint] Proxy authentication required -- configure proxy credentials."
        }
    }

    # 2. Show server response body (often contains a useful error message)
    if ($ResponseBody) {
        $preview = if ($ResponseBody.Length -gt 400) { $ResponseBody.Substring(0, 400) + "..." } else { $ResponseBody }
        Write-Host "         [Response body] $preview"
    }

    # 3. DNS resolution check
    try {
        $uri      = [System.Uri]$Url
        $hostname = $uri.Host
        $port     = if ($uri.Port -gt 0) { $uri.Port } elseif ($uri.Scheme -eq "https") { 443 } else { 80 }

        Write-Host -NoNewline "         [DNS] Resolving '$hostname' ... "
        try {
            $addrs = [System.Net.Dns]::GetHostAddresses($hostname)
            $ips   = ($addrs | ForEach-Object { $_.IPAddressToString }) -join ", "
            Write-Host "OK  ($ips)"
        } catch {
            Write-Host "FAILED  ($_)"
        }

        # 4. TCP port connectivity check
        Write-Host -NoNewline "         [TCP] Connecting to ${hostname}:${port} ... "
        try {
            $tcp = New-Object System.Net.Sockets.TcpClient
            $ar  = $tcp.BeginConnect($hostname, $port, $null, $null)
            $ok  = $ar.AsyncWaitHandle.WaitOne(5000, $false)
            if ($ok -and $tcp.Connected) {
                $tcp.EndConnect($ar)
                Write-Host "OK  (port open)"
            } else {
                Write-Host "FAILED  (no response within 5 s -- firewall may be dropping packets)"
            }
            $tcp.Close()
        } catch {
            Write-Host "FAILED  ($_)"
        }
    } catch {
        Write-Host "         [Diag] Could not parse URL for diagnostics: $Url"
    }

    Write-Host "         -------------------"
    Write-Host ""
}

# Extract the first gid from a raw TWFY getHansard JSON response body.
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

# Extract the first case law judgment URL from a National Archives Atom XML response.
# Atom <id> elements inside <entry> blocks hold the canonical case URL
# (e.g. https://caselaw.nationalarchives.gov.uk/uksc/2024/1).
function Get-CaseLawUrl {
    param([string]$Content)
    if (-not $Content) { return $null }
    $allMatches = [regex]::Matches($Content, '<id>(https://caselaw\.nationalarchives\.gov\.uk/[^<]+)</id>')
    foreach ($m in $allMatches) {
        $url = $m.Groups[1].Value.Trim()
        # Skip the feed-level <id> which points at atom.xml itself
        if ($url -notmatch 'atom\.xml') {
            return $url
        }
    }
    return $null
}

# Extract the first committee meeting (slug + meetingId) from the SP OR listing page HTML.
# Excludes plenary meetings (meeting-of-parliament-* slugs).
function Get-SpMeeting {
    param([string]$Content)
    if (-not $Content) { return $null }
    $pattern = 'href="[^"]*official-report/search-what-was-said-in-parliament/([^"?/\s]+)\?meeting=(\d+)"'
    $allMatches = [regex]::Matches($Content, $pattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    foreach ($m in $allMatches) {
        $slug      = $m.Groups[1].Value
        $meetingId = $m.Groups[2].Value
        if ($slug -notmatch 'meeting-of-parliament') {
            return @{ Slug = $slug; MeetingId = $meetingId }
        }
    }
    return $null
}

# Extract the first iob_id from a SP meeting detail page HTML.
function Get-SpIobId {
    param([string]$Content, [string]$MeetingId)
    if (-not $Content -or -not $MeetingId) { return $null }
    $escapedId = [regex]::Escape($MeetingId)
    $m = [regex]::Match($Content, "meeting=$escapedId(?:&amp;|&)iob=(\d+)", [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    if ($m.Success) { return $m.Groups[1].Value }
    return $null
}

# ===========================================================================
# GROUP 1: LEGISLATION BOT -- LEX API + National Archives case law
# ===========================================================================

Write-Host "--- GROUP 1: LEGISLATION BOT ---"
Write-Host "    LEX API ($LexBaseUrl)"
Write-Host "    National Archives case law ($CaseLawBase)"
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

Write-Host "5. search_case_law -- basic search (captures result for test 8)"
$AtomContent = Test-Endpoint `
    -Label   "search_case_law" `
    -Url     "$CaseLawBase/atom.xml" `
    -Method  GET `
    -Query   @{ query = "fair dismissal reasonable adjustment" } `
    -Capture

Write-Host "6. search_case_law -- court filter (uksc)"
Test-Endpoint `
    -Label  "search_case_law (court=uksc)" `
    -Url    "$CaseLawBase/atom.xml" `
    -Method GET `
    -Query  @{ query = "judicial review"; court = "uksc" }

Write-Host "7. search_case_law -- date filter"
Test-Endpoint `
    -Label  "search_case_law (date filter)" `
    -Url    "$CaseLawBase/atom.xml" `
    -Method GET `
    -Query  @{ query = "employment tribunal"; date_from = "2024-01-01"; date_to = "2024-12-31" }

Write-Host "8. get_case_law_text -- fetch full judgment via /data.xml (chained from test 5)"
$CaseLawUrl = Get-CaseLawUrl -Content $AtomContent
if ($CaseLawUrl) {
    $DataXmlUrl = $CaseLawUrl.TrimEnd('/') + "/data.xml"
    Test-Endpoint `
        -Label  "get_case_law_text" `
        -Url    $DataXmlUrl `
        -Method GET
} else {
    Skip-Test -Label "get_case_law_text" -Reason "no case URL returned by search_case_law (test 5)"
}

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

Write-Host "9. search_hansard -- Commons debates (TWFY getHansard)"
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

Write-Host "10. search_hansard -- Lords (TWFY getHansard?type=lords)"
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

Write-Host "11. search_hansard -- Written answers (TWFY getHansard?type=wrans)"
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

Write-Host "12. get_hansard_debate -- Commons (TWFY getDebates)"
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

Write-Host "13. get_hansard_debate -- Lords (TWFY getLords)"
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

Write-Host "14. get_hansard_debate -- Written answers (TWFY getWrans)"
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

Write-Host "15. get_member_info -- Commons (Parliament Members API)"
Test-Endpoint `
    -Label  "get_member_info (Commons)" `
    -Url    $ParliamentMembers `
    -Method GET `
    -Query  @{ Name = "Keir Starmer"; House = 1; IsCurrentMember = "false"; Skip = 0; Take = 3 }

Write-Host "16. get_member_info -- Lords (Parliament Members API, House=2)"
Test-Endpoint `
    -Label  "get_member_info (Lords)" `
    -Url    $ParliamentMembers `
    -Method GET `
    -Query  @{ Name = "Baroness Hale"; House = 2; IsCurrentMember = "false"; Skip = 0; Take = 3 }

Write-Host "17. get_member_info -- Scotland MSP (TWFY getMSPInfo)"
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

Write-Host "18. search_bills -- UK Westminster (Parliament Bills API)"
Test-Endpoint `
    -Label  "search_bills (UK)" `
    -Url    $ParliamentBills `
    -Method GET `
    -Query  @{ SearchTerm = "Renters Rights"; SortOrder = "DateUpdatedDescending"; Take = 5; Skip = 0 }

Write-Host "19. search_bills -- Scotland (data.parliament.scot -- no search param, filtered client-side)"
Test-Endpoint `
    -Label  "search_bills (Scotland)" `
    -Url    $ScottishBills `
    -Method GET

# --- search_scottish_parliament ---

Write-Host "20. search_scottish_parliament -- debates (TWFY getHansard)"
$SpContent = $null
if ($TwfyApiKey) {
    $SpContent = Test-Endpoint `
        -Label   "search_scottish_parliament" `
        -Url     "$TwfyBase/getHansard" `
        -Method  GET `
        -Query   @{ key = $TwfyApiKey; output = "js"; search = "education Scotland curriculum"; num = 20 } `
        -Capture
} else {
    Skip-Test -Label "search_scottish_parliament" -Reason "TWFY_API_KEY not set"
}

Write-Host "21. search_scottish_parliament -- written answers (TWFY getHansard?type=spwrans)"
if ($TwfyApiKey) {
    Test-Endpoint `
        -Label  "search_scottish_parliament (wrans)" `
        -Url    "$TwfyBase/getHansard" `
        -Method GET `
        -Query  @{ key = $TwfyApiKey; output = "js"; search = "health board Scotland"; type = "spwrans"; num = 10 }
} else {
    Skip-Test -Label "search_scottish_parliament (wrans)" -Reason "TWFY_API_KEY not set"
}

Write-Host "22. get_hansard_debate -- Scottish Parliament (TWFY getSP)"
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

# ===========================================================================
# GROUP 3: SP OFFICIAL REPORT CRAWLER
# Verifies the three URL patterns used by parliament_crawler.py:
#   (1) listing page  -- GET $SpOrBase?showCommittee=true
#   (2) meeting page  -- GET $SpOrBase/{slug}?meeting={id}
#   (3) transcript    -- GET $SpOrBase/{slug}?meeting={id}&iob={iob_id}
# Tests 24 and 25 chain from the listing page result; both skip if no meeting
# is found (e.g. parliament in recess) rather than failing.
# ===========================================================================

Write-Host "--- GROUP 3: SP OFFICIAL REPORT CRAWLER ---"
Write-Host "    Scottish Parliament Official Report ($SpOrBase)"
Write-Host ""

Write-Host "23. SP Official Report -- listing page (committee filter)"
$SpListingContent = Test-Endpoint `
    -Label   "SP listing page" `
    -Url     $SpOrBase `
    -Method  GET `
    -Query   @{ showCommittee = "true" } `
    -Capture

Write-Host "24. SP Official Report -- meeting detail page (chained from test 23)"
$SpMeeting = Get-SpMeeting -Content $SpListingContent
if ($SpMeeting) {
    $MeetingUrl = "$SpOrBase/$($SpMeeting.Slug)?meeting=$($SpMeeting.MeetingId)"
    $SpMeetingContent = Test-Endpoint `
        -Label   "SP meeting detail" `
        -Url     $MeetingUrl `
        -Method  GET `
        -Capture
} else {
    $SpMeetingContent = $null
    Skip-Test -Label "SP meeting detail" -Reason "no committee meeting found in listing page (parliament may be in recess)"
}

Write-Host "25. SP Official Report -- transcript page (chained from test 24)"
$SpMeetingId = if ($SpMeeting) { $SpMeeting.MeetingId } else { "" }
$SpIobId = Get-SpIobId -Content $SpMeetingContent -MeetingId $SpMeetingId
if ($SpMeeting -and $SpIobId) {
    $TranscriptUrl = "$SpOrBase/$($SpMeeting.Slug)?meeting=$($SpMeeting.MeetingId)&iob=$SpIobId"
    Test-Endpoint `
        -Label  "SP transcript" `
        -Url    $TranscriptUrl `
        -Method GET
} elseif (-not $SpMeeting) {
    Skip-Test -Label "SP transcript" -Reason "no meeting found in listing page (skipped by test 24)"
} else {
    Skip-Test -Label "SP transcript" -Reason "no iob_id found in meeting page"
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

$Total = $PassCount + $FailCount + $SkipCount
Write-Host "============================================================"
Write-Host "SUMMARY"
Write-Host "============================================================"
foreach ($r in $Results) {
    $urlSuffix = if ($r.Url) { "  $($r.Url)" } else { "" }
    switch ($r.Status) {
        "PASS" { Write-Host ("  [PASS] " + $r.Label + $urlSuffix) -ForegroundColor Green  }
        "FAIL" { Write-Host ("  [FAIL] " + $r.Label + $urlSuffix) -ForegroundColor Red    }
        "SKIP" { Write-Host ("  [SKIP] " + $r.Label + $urlSuffix) -ForegroundColor Yellow }
    }
}
Write-Host ""
Write-Host "$PassCount passed  |  $FailCount failed  |  $SkipCount skipped  (of $Total tests)"

if ($FailCount -gt 0) {
    Write-Host "OVERALL: FAIL -- $FailCount endpoint(s) did not respond as expected." -ForegroundColor Red
    exit 1
} else {
    Write-Host "OVERALL: PASS -- all runnable endpoints healthy." -ForegroundColor Green
    exit 0
}
