<#
.SYNOPSIS
    Nightly logical backup of every LexChat PostgreSQL database.

.DESCRIPTION
    Discovers every database matching 'lexchat%' (excluding lexchat_test), takes a
    custom-format pg_dump of each, verifies each dump with `pg_restore --list`, and
    writes a manifest.json recording sizes, durations, verify results and the git
    commit SHA of the code the schema belongs to.

    Databases are ENUMERATED, never hardcoded, so a newly created federated bot is
    backed up the night it is created.

    Rows of `local_prompt_cache` are excluded (--exclude-table-data): it is pure
    cache, and it is the only table holding plaintext user queries.

    A dump that fails verification is moved aside to <name>.dump.corrupt and the
    whole run is marked FAILED. A corrupt dump must never sit in the backup
    directory looking healthy by filesize.

    Safe to run against a live system: pg_dump takes a consistent MVCC snapshot.
    There is no need to stop the app.

.PARAMETER BackupRoot
    Directory that holds all backup runs. Default C:\LexChatBackups, deliberately
    OUTSIDE the repo so no git operation can ever touch it.

.PARAMETER PgBin
    PostgreSQL bin directory. Auto-detected from C:\Program Files\PostgreSQL\* if
    not supplied (highest version wins).

.PARAMETER KeepDaily
    Number of most recent successful runs to keep.

.PARAMETER KeepWeekly
    Number of ISO weeks to keep the newest successful run of.

.PARAMETER KeepMonthly
    Number of calendar months to keep the newest successful run of.

.EXAMPLE
    .\deployment\backup_databases.ps1

.EXAMPLE
    .\deployment\backup_databases.ps1 -BackupRoot D:\Backups\LexChat -KeepDaily 30

.NOTES
    Exit code 0 = every database dumped and verified.
    Exit code 1 = at least one failure (also written to the Application event log).

    NOTE: this file is deliberately ASCII-only. Windows PowerShell 5.1 reads
    BOM-less scripts as ANSI, and a UTF-8 em dash decodes to a smart quote that
    silently terminates a string literal.
#>

[CmdletBinding()]
param(
    [string] $BackupRoot  = "C:\LexChatBackups",
    [string] $PgBin       = "",
    [string] $PgHost      = "",
    [string] $PgPort      = "",
    [string] $PgUser      = "",
    [string] $PgPassword  = "",
    [int]    $KeepDaily   = 14,
    [int]    $KeepWeekly  = 8,
    [int]    $KeepMonthly = 12,
    [switch] $SkipRetention
)

$ErrorActionPreference = "Stop"

$scriptDir = $PSScriptRoot
$repoRoot  = (Resolve-Path "$scriptDir\..").Path
$startedAt = Get-Date
$stamp     = $startedAt.ToString("yyyy-MM-dd_HHmmss")

# Excluded by design: pytest's target database, recreated from scratch on every run.
$ExcludedDatabases = @("lexchat_test")

# Pure cache, and the only table holding plaintext user queries. The schema is
# kept, the rows are not.
$ExcludeTableData = @("local_prompt_cache")

$EventSource = "LexChat Backup"

# ---------------------------------------------------------------- logging ----

$logDir  = Join-Path $BackupRoot "logs"
$logFile = Join-Path $logDir "backup.log"

function Write-Log {
    param([string] $Message, [string] $Level = "INFO")
    $line = "[{0}] [{1}] {2}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Level, $Message
    switch ($Level) {
        "ERROR" { Write-Host $line -ForegroundColor Red }
        "WARN"  { Write-Host $line -ForegroundColor Yellow }
        "OK"    { Write-Host $line -ForegroundColor Green }
        default { Write-Host $line }
    }
    try { Add-Content -Path $logFile -Value $line -Encoding UTF8 } catch { }
}

function Write-FailureEvent {
    param([string] $Message)
    # Fail-soft: the event source may not be registered (install_backup_task.ps1
    # registers it, and that needs admin). Never let logging kill the run.
    try {
        if (-not [System.Diagnostics.EventLog]::SourceExists($EventSource)) {
            New-EventLog -LogName Application -Source $EventSource -ErrorAction Stop
        }
        Write-EventLog -LogName Application -Source $EventSource -EntryType Error `
            -EventId 1001 -Message $Message -ErrorAction Stop
    } catch {
        Write-Log "Could not write to the Application event log: $($_.Exception.Message)" "WARN"
    }
}

# ------------------------------------------------------- resolve pg tools ----

function Resolve-PgBin {
    param([string] $Supplied)

    if ($Supplied) {
        if (-not (Test-Path (Join-Path $Supplied "pg_dump.exe"))) {
            throw "pg_dump.exe not found in supplied -PgBin '$Supplied'."
        }
        return $Supplied
    }

    $candidates = Get-ChildItem "C:\Program Files\PostgreSQL" -Directory -ErrorAction SilentlyContinue |
        Where-Object { Test-Path (Join-Path $_.FullName "bin\pg_dump.exe") } |
        Sort-Object { [int]($_.Name -replace '\D', '0') } -Descending

    if ($candidates) { return (Join-Path $candidates[0].FullName "bin") }

    $cmd = Get-Command pg_dump.exe -ErrorAction SilentlyContinue
    if ($cmd) { return (Split-Path $cmd.Source -Parent) }

    throw "Could not locate the PostgreSQL bin directory. Pass -PgBin explicitly."
}

# --------------------------------------------------- resolve credentials -----

function Get-DatabaseSettings {
    <#
        Credentials come from server_py/.env (falling back to .env.native) so that
        this script holds no password of its own and cannot drift from the app's
        connection settings. Explicit parameters override.
    #>
    $result = @{ PgHost = "localhost"; Port = "5432"; User = "lexuser"; Password = "" }

    $envFiles = @("$repoRoot\server_py\.env", "$repoRoot\server_py\.env.native")
    foreach ($file in $envFiles) {
        if (-not (Test-Path $file)) { continue }
        $line = Select-String -Path $file -Pattern '^\s*DATABASE_URL\s*=' -ErrorAction SilentlyContinue |
                Select-Object -First 1
        if (-not $line) { continue }

        $url = ($line.Line -split '=', 2)[1].Trim().Trim('"').Trim("'")
        # postgresql[+driver]://user:password@host:port/dbname
        if ($url -match '^[a-zA-Z0-9+]+://([^:/@]+):([^@]*)@([^:/]+):(\d+)/') {
            $result.User     = [uri]::UnescapeDataString($matches[1])
            $result.Password = [uri]::UnescapeDataString($matches[2])
            $result.PgHost   = $matches[3]
            $result.Port     = $matches[4]
            Write-Log "Connection settings read from $file"
            break
        } else {
            Write-Log "DATABASE_URL in $file did not parse; falling back to defaults." "WARN"
        }
    }

    if ($PgHost)     { $result.PgHost   = $PgHost }
    if ($PgPort)     { $result.Port     = $PgPort }
    if ($PgUser)     { $result.User     = $PgUser }
    if ($PgPassword) { $result.Password = $PgPassword }

    return $result
}

# ------------------------------------------------------------- git SHA -------

function Get-CommitSha {
    <#
        The single most useful field in the manifest at 2am: which code this
        dump's schema belongs to. Restoring an old dump onto newer code is fine
        (startup re-applies the additive ADD COLUMN migrations); the reverse is
        not. Read .git directly if git.exe is absent, because the scheduled task
        runs as SYSTEM, whose PATH may not include git.
    #>
    try {
        $git = Get-Command git.exe -ErrorAction SilentlyContinue
        if ($git) {
            $sha = & $git.Source -C $repoRoot rev-parse HEAD 2>$null
            if ($LASTEXITCODE -eq 0 -and $sha) { return "$sha".Trim() }
        }

        $headFile = Join-Path $repoRoot ".git\HEAD"
        if (Test-Path $headFile) {
            $head = (Get-Content $headFile -Raw).Trim()
            if ($head -match '^ref:\s*(.+)$') {
                $ref     = $matches[1].Trim()
                $refPath = Join-Path $repoRoot (".git\" + $ref.Replace('/', '\'))
                if (Test-Path $refPath) { return (Get-Content $refPath -Raw).Trim() }
                $packed = Join-Path $repoRoot ".git\packed-refs"
                if (Test-Path $packed) {
                    $match = Select-String -Path $packed -Pattern ([regex]::Escape($ref)) |
                             Select-Object -First 1
                    if ($match) { return ($match.Line -split '\s+')[0] }
                }
            } else {
                return $head   # detached HEAD
            }
        }
    } catch { }
    return $null
}

# ---------------------------------------------------------------- helpers ----

function Invoke-Native {
    <#
        Run a native executable and return its exit code plus combined output.

        Windows PowerShell 5.1 wraps a native command's stderr lines in
        ErrorRecords when they are redirected with 2>&1, and under
        $ErrorActionPreference = "Stop" that turns any tool that merely writes a
        warning to stderr into a terminating error. pg_dumpall's permission
        failure is exactly that case, and it would abort the run before the
        --no-role-passwords fallback could be tried. Drop to Continue for the
        duration of the call and inspect the exit code ourselves.
    #>
    param([string] $Exe, [string[]] $Arguments)

    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & $Exe @Arguments 2>&1
        $code   = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previous
    }
    return [pscustomobject]@{
        ExitCode = $code
        Output   = @($output | ForEach-Object { "$_" })
    }
}

function Invoke-Psql {
    param([string] $Database, [string] $Sql)
    $r = Invoke-Native $psqlExe @(
        "-U", $settings.User, "-h", $settings.PgHost, "-p", $settings.Port,
        "-d", $Database, "-A", "-t", "-v", "ON_ERROR_STOP=1", "-c", $Sql)
    if ($r.ExitCode -ne 0) { throw "psql failed: $($r.Output -join '; ')" }
    return ($r.Output | Where-Object { $_ -ne "" })
}

function Format-Bytes {
    param([long] $Bytes)
    if ($Bytes -ge 1GB) { return "{0:N2} GB" -f ($Bytes / 1GB) }
    if ($Bytes -ge 1MB) { return "{0:N2} MB" -f ($Bytes / 1MB) }
    if ($Bytes -ge 1KB) { return "{0:N1} KB" -f ($Bytes / 1KB) }
    return "$Bytes B"
}

# ============================================================== main =========

$runDir      = $null
$pgVersion   = $null
$globalsMode = "not-run"
$failures    = New-Object System.Collections.ArrayList
$dbResults   = New-Object System.Collections.ArrayList

try {
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }

    Write-Log "=== LexChat database backup starting ==="

    $pgBinDir     = Resolve-PgBin $PgBin
    $pgDumpExe    = Join-Path $pgBinDir "pg_dump.exe"
    $pgDumpAllExe = Join-Path $pgBinDir "pg_dumpall.exe"
    $pgRestoreExe = Join-Path $pgBinDir "pg_restore.exe"
    $psqlExe      = Join-Path $pgBinDir "psql.exe"
    Write-Log "PostgreSQL tools: $pgBinDir"

    $settings = Get-DatabaseSettings
    $env:PGPASSWORD = $settings.Password
    Write-Log "Server: $($settings.User)@$($settings.PgHost):$($settings.Port)"

    $pgVersion = (Invoke-Psql -Database "postgres" -Sql "SHOW server_version;") -join ""
    Write-Log "Server version: $pgVersion"

    # --- Enumerate, do not hardcode ------------------------------------------
    $excludeList = ($ExcludedDatabases | ForEach-Object { "'$_'" }) -join ", "
    $enumerateSql = @"
SELECT datname FROM pg_database
WHERE datname LIKE 'lexchat%'
  AND datname NOT IN ($excludeList)
  AND datallowconn
  AND NOT datistemplate
ORDER BY datname;
"@
    $databases = @(Invoke-Psql -Database "postgres" -Sql $enumerateSql | ForEach-Object { "$_".Trim() })

    if ($databases.Count -eq 0) {
        throw ("No databases matching 'lexchat%' were found. Treating this as a failure: " +
               "an empty target list is far more likely to be a connection or permission " +
               "problem than a genuinely empty server.")
    }
    Write-Log "Databases to back up ($($databases.Count)): $($databases -join ', ')"

    # --- Create the run directory --------------------------------------------
    $runDir = Join-Path $BackupRoot $stamp
    New-Item -ItemType Directory -Path $runDir -Force | Out-Null
    Write-Log "Run directory: $runDir"

    # --- Globals -------------------------------------------------------------
    # A dump carries no roles. Without them a restore into a fresh cluster fails
    # on ownership. pg_dumpall needs superuser rights to read pg_authid for the
    # password hashes, and lexuser is NOT a superuser on this deployment, so fall
    # back to --no-role-passwords (role definitions without passwords) and record
    # which variant we got. The runbook tells the operator to set the password by
    # hand in the fallback case.
    $globalsFile = Join-Path $runDir "globals.sql"
    $globalsMode = "full"
    $globalsOk   = $false

    $connArgs = @("-U", $settings.User, "-h", $settings.PgHost, "-p", $settings.Port)

    $r = Invoke-Native $pgDumpAllExe ($connArgs + @("--globals-only", "-f", $globalsFile))
    if ($r.ExitCode -eq 0) {
        $globalsOk = $true
    } else {
        Write-Log "pg_dumpall --globals-only failed (not a superuser?); retrying without role passwords." "WARN"
        $globalsMode = "no-role-passwords"
        $r = Invoke-Native $pgDumpAllExe ($connArgs + @("--globals-only", "--no-role-passwords", "-f", $globalsFile))
        if ($r.ExitCode -eq 0) {
            $globalsOk = $true
            Write-Log ("Globals dumped WITHOUT role passwords. A restore into a fresh cluster " +
                       "will need the lexuser password set by hand - see BACKUP_RUNBOOK.md.") "WARN"
        } else {
            $globalsMode = "failed"
            [void]$failures.Add("globals: $($r.Output -join '; ')")
            Write-Log "Globals dump failed: $($r.Output -join '; ')" "ERROR"
        }
    }
    if ($globalsOk) {
        Write-Log "Globals: $(Format-Bytes (Get-Item $globalsFile).Length) ($globalsMode)" "OK"
    }

    # --- Per-database dump + verify ------------------------------------------
    $excludeArgs = @()
    foreach ($table in $ExcludeTableData) { $excludeArgs += "--exclude-table-data=$table" }

    foreach ($db in $databases) {
        $dbStart  = Get-Date
        $dumpFile = Join-Path $runDir "$db.dump"
        $entry = [ordered]@{
            name        = $db
            file        = "$db.dump"
            bytes       = 0
            verify      = "not-run"
            toc_entries = 0
            verify_s    = 0
            duration_s  = 0
            error       = $null
        }

        Write-Log "Dumping $db ..."
        $r = Invoke-Native $pgDumpExe ($connArgs + @("-d", $db, "-Fc") + $excludeArgs + @("-f", $dumpFile))
        $dumpExit = $r.ExitCode

        if ($dumpExit -ne 0) {
            $entry.verify = "dump-failed"
            $entry.error  = ($r.Output -join '; ').Trim()
            [void]$failures.Add("$db : pg_dump exited $dumpExit - $($entry.error)")
            Write-Log "pg_dump FAILED for $db : $($entry.error)" "ERROR"
            if (Test-Path $dumpFile) {
                Move-Item $dumpFile "$dumpFile.corrupt" -Force
                Write-Log "Partial dump moved to $db.dump.corrupt" "WARN"
            }
            $entry.duration_s = [math]::Round(((Get-Date) - $dbStart).TotalSeconds, 2)
            [void]$dbResults.Add($entry)
            continue
        }

        $entry.bytes = (Get-Item $dumpFile).Length

        # --- Verify. This is the whole point of the phase. --------------------
        # TWO stages, and the second is the one that matters.
        #
        # Stage 1, `pg_restore --list`, reads only the table of contents. In a
        # custom-format archive the TOC precedes the data, so --list is NOT a
        # check on the data blocks: a dump truncated to half its length by a
        # mid-dump reboot still lists every TOC entry and exits 0. Measured on
        # this deployment - a 50%-truncated lexchat.dump listed all 172 entries
        # and passed. --list therefore catches only a missing or header-corrupt
        # archive, and is kept for the TOC count it gives the manifest.
        #
        # Stage 2, `pg_restore -f NUL`, converts the whole archive to SQL and
        # throws the output away, which forces every data block to be read and
        # decompressed. That is what actually catches truncation ("could not
        # read from input file: end of file"). It costs about 1.7s for the
        # 157 MB parliament dump, so it runs on every database every night.
        $verifyStart = Get-Date

        $listResult = Invoke-Native $pgRestoreExe @("--list", $dumpFile)
        $tocCount   = @($listResult.Output | Where-Object { $_ -match '^\d+;' }).Count
        $verifyError = $null

        if ($listResult.ExitCode -ne 0) {
            $verifyError = "pg_restore --list: " + ($listResult.Output -join '; ').Trim()
        } elseif ($tocCount -eq 0) {
            $verifyError = "pg_restore --list succeeded but the archive contains no TOC entries."
        } else {
            $deepResult = Invoke-Native $pgRestoreExe @("-f", "NUL", $dumpFile)
            if ($deepResult.ExitCode -ne 0) {
                $verifyError = "pg_restore -f NUL (full read): " + ($deepResult.Output -join '; ').Trim()
            }
        }

        $entry.toc_entries = $tocCount
        $entry.verify_s    = [math]::Round(((Get-Date) - $verifyStart).TotalSeconds, 2)

        if ($verifyError) {
            $entry.verify = "FAILED"
            $entry.error  = $verifyError
            [void]$failures.Add("$db : verify FAILED - $verifyError")
            Write-Log "VERIFY FAILED for $db : $verifyError" "ERROR"
            Move-Item $dumpFile "$dumpFile.corrupt" -Force
            Write-Log "Unverifiable dump moved to $db.dump.corrupt so it can never be mistaken for a good backup." "WARN"
        } else {
            $entry.verify = "ok"
            Write-Log "$db : $(Format-Bytes $entry.bytes), $tocCount TOC entries, fully read in $($entry.verify_s)s, verified" "OK"
        }

        $entry.duration_s = [math]::Round(((Get-Date) - $dbStart).TotalSeconds, 2)
        # Cast to PSCustomObject (order is preserved): an OrderedDictionary has no
        # properties for Measure-Object to sum over.
        [void]$dbResults.Add([pscustomobject]$entry)
    }

} catch {
    $msg = $_.Exception.Message
    [void]$failures.Add("run aborted: $msg")
    Write-Log "Backup run aborted: $msg" "ERROR"
} finally {
    if ($env:PGPASSWORD) { Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue }
}

# --- Manifest ----------------------------------------------------------------

$finishedAt = Get-Date
if ($failures.Count -eq 0) { $status = "ok" } else { $status = "FAILED" }

if ($runDir -and (Test-Path $runDir)) {
    # Summed by hand: Measure-Object throws on an empty collection, and an aborted
    # run must still produce a manifest.
    $totalBytes = [long]0
    foreach ($d in $dbResults) { $totalBytes += [long]$d.bytes }

    $manifest = [ordered]@{
        status              = $status
        started_at          = $startedAt.ToString("o")
        finished_at         = $finishedAt.ToString("o")
        duration_s          = [math]::Round(($finishedAt - $startedAt).TotalSeconds, 2)
        commit_sha          = Get-CommitSha
        pg_version          = $pgVersion
        host                = $env:COMPUTERNAME
        backup_root         = $BackupRoot
        globals             = @{ file = "globals.sql"; mode = $globalsMode }
        excluded_table_data = $ExcludeTableData
        excluded_databases  = $ExcludedDatabases
        databases           = @($dbResults)
        errors              = @($failures)
        total_bytes         = $totalBytes
    }

    $json = $manifest | ConvertTo-Json -Depth 6
    # Written without a BOM: the Phase 4-6 backend will read these with Python's
    # json module, which does not tolerate one under plain utf-8.
    [System.IO.File]::WriteAllText(
        (Join-Path $runDir "manifest.json"),
        $json,
        (New-Object System.Text.UTF8Encoding($false)))

    # A marker file, so retention and any future restore picker can tell a bad
    # run from a good one without parsing JSON.
    if ($status -ne "ok") {
        Set-Content -Path (Join-Path $runDir "FAILED") `
                    -Value ($failures -join "`r`n") -Encoding UTF8
    }
    Write-Log "Manifest written to $runDir\manifest.json"
}

# --- Retention (GFS) ---------------------------------------------------------
# Selection over one flat list of runs - no promotion, no copying, no hard links.
# Keep: the last N runs, plus the newest run of each of the last N ISO weeks,
# plus the newest run of each of the last N calendar months. Failed runs never
# occupy a weekly or monthly slot (a broken backup must not displace a good one)
# but are kept for 14 days so they can be investigated.

if (-not $SkipRetention -and (Test-Path $BackupRoot)) {
    try {
        $runs = Get-ChildItem $BackupRoot -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match '^\d{4}-\d{2}-\d{2}_\d{6}$' } |
            ForEach-Object {
                [pscustomobject]@{
                    Dir    = $_
                    Date   = [datetime]::ParseExact($_.Name, "yyyy-MM-dd_HHmmss", $null)
                    Failed = (Test-Path (Join-Path $_.FullName "FAILED"))
                }
            } | Sort-Object Date -Descending

        $good = @($runs | Where-Object { -not $_.Failed })
        $keep = New-Object System.Collections.Generic.HashSet[string]

        foreach ($r in ($good | Select-Object -First $KeepDaily)) { [void]$keep.Add($r.Dir.Name) }

        $cal = [System.Globalization.CultureInfo]::InvariantCulture.Calendar
        $weekly = $good | Group-Object {
            "{0}-W{1:D2}" -f $_.Date.Year, $cal.GetWeekOfYear(
                $_.Date,
                [System.Globalization.CalendarWeekRule]::FirstFourDayWeek,
                [DayOfWeek]::Monday)
        } | Sort-Object Name -Descending | Select-Object -First $KeepWeekly
        foreach ($g in $weekly) {
            [void]$keep.Add((($g.Group | Sort-Object Date -Descending)[0]).Dir.Name)
        }

        $monthly = $good | Group-Object { $_.Date.ToString("yyyy-MM") } |
            Sort-Object Name -Descending | Select-Object -First $KeepMonthly
        foreach ($g in $monthly) {
            [void]$keep.Add((($g.Group | Sort-Object Date -Descending)[0]).Dir.Name)
        }

        # Failed runs: keep for 14 days for investigation, then drop.
        $failedCutoff = (Get-Date).AddDays(-14)
        foreach ($r in ($runs | Where-Object { $_.Failed -and $_.Date -ge $failedCutoff })) {
            [void]$keep.Add($r.Dir.Name)
        }

        $toDelete = @($runs | Where-Object { -not $keep.Contains($_.Dir.Name) })
        foreach ($r in $toDelete) {
            Remove-Item $r.Dir.FullName -Recurse -Force
            Write-Log "Retention: removed $($r.Dir.Name)"
        }
        Write-Log "Retention: $($keep.Count) run(s) kept, $($toDelete.Count) removed (daily=$KeepDaily weekly=$KeepWeekly monthly=$KeepMonthly)."
    } catch {
        # Retention is housekeeping. A failure here must not mark an otherwise
        # good backup as failed.
        Write-Log "Retention pass failed (the backups themselves are unaffected): $($_.Exception.Message)" "WARN"
    }
}

# --- Outcome -----------------------------------------------------------------

if ($status -eq "ok") { $finalLevel = "OK" } else { $finalLevel = "ERROR" }
Write-Log "=== Backup finished: $status in $([math]::Round(($finishedAt - $startedAt).TotalSeconds, 1))s ===" $finalLevel

if ($failures.Count -gt 0) {
    $summary = "LexChat database backup FAILED on $env:COMPUTERNAME.`r`n`r`n" +
               "Run: $runDir`r`n`r`n" + ($failures -join "`r`n")
    Write-FailureEvent $summary
    Write-Host ""
    Write-Host "BACKUP FAILED:" -ForegroundColor Red
    foreach ($f in $failures) { Write-Host "  - $f" -ForegroundColor Red }
    exit 1
}

exit 0
