<#
.SYNOPSIS
    Restore one LexChat database from a nightly dump. Console operation only.

.DESCRIPTION
    Full-database restore is deliberately a console operation and never a button
    in the Admin Portal: the app holds live connections to the database being
    replaced, the request performing the restore would be authenticated against
    the users table it is about to overwrite, and a restore that dies halfway
    leaves the very UI you would use to retry sitting on a half-restored
    database.

    What this script does, in order:

      1. Resolves the dump (newest verified run by default) and prints the
         manifest, including the commit SHA the dump's schema belongs to.
      2. VERIFIES the dump before touching anything - both `pg_restore --list`
         and a full read. If the dump is unusable you find out before the
         database is dropped, not after.
      3. Stops the app (but NOT PostgreSQL - the restore needs the server up).
      4. Dumps the current contents of the target first, so the restore itself
         is undoable.
      5. Terminates leftover connections, drops and recreates the database, and
         runs pg_restore.
      6. ANALYZEs, then prints exact per-table row counts, optionally alongside
         another database for comparison.

    The app is NOT restarted automatically - see the closing instructions.

.PARAMETER Database
    The database whose dump should be restored, e.g. lexchat.

.PARAMETER TargetDatabase
    Where to restore it. Defaults to -Database. Set this to restore into a
    scratch database - which is how the monthly restore drill is run:
        -Database lexchat -TargetDatabase lexchat_restore_test -NoAppStop

.PARAMETER DumpFile
    An explicit .dump file. If omitted, the newest run under -BackupRoot that
    contains <Database>.dump and did not fail is used.

.PARAMETER CompareWith
    After restoring, print row counts side by side with this database and flag
    every difference. Use the live database here during a drill.

.PARAMETER NoAppStop
    Leave the running app alone. Correct when restoring into a scratch database;
    never correct when overwriting a live one.

.PARAMETER RestoreGlobals
    Also apply globals.sql (roles). Only needed when restoring into a fresh
    PostgreSQL cluster - on an existing one the roles are already there and this
    just produces "role already exists" noise.

.EXAMPLE
    # Restore drill into a scratch database, compared against live:
    .\deployment\restore_database.ps1 -Database lexchat `
        -TargetDatabase lexchat_restore_test -CompareWith lexchat -NoAppStop

.EXAMPLE
    # The real thing, from the newest verified backup:
    .\deployment\restore_database.ps1 -Database lexchat

.EXAMPLE
    # From a specific night:
    .\deployment\restore_database.ps1 -Database lexchat `
        -DumpFile C:\LexChatBackups\2026-08-13_023000\lexchat.dump

.NOTES
    This file is deliberately ASCII-only; see the note in backup_databases.ps1.
    Full procedure: docs\deployment\BACKUP_RUNBOOK.md
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string] $Database,

    [string] $TargetDatabase = "",
    [string] $DumpFile       = "",
    [string] $BackupRoot     = "C:\LexChatBackups",
    [string] $CompareWith    = "",
    [string] $PgBin          = "",
    [string] $PgHost         = "",
    [string] $PgPort         = "",
    [string] $PgUser         = "",
    [string] $PgPassword     = "",
    [switch] $NoAppStop,
    [switch] $SkipSafetyDump,
    [switch] $RestoreGlobals,
    [switch] $Force
)

$ErrorActionPreference = "Stop"

$scriptDir = $PSScriptRoot
$repoRoot  = (Resolve-Path "$scriptDir\..").Path
if (-not $TargetDatabase) { $TargetDatabase = $Database }

function Say {
    param([string] $Message, [string] $Level = "INFO")
    switch ($Level) {
        "ERROR" { Write-Host $Message -ForegroundColor Red }
        "WARN"  { Write-Host $Message -ForegroundColor Yellow }
        "OK"    { Write-Host $Message -ForegroundColor Green }
        "HEAD"  { Write-Host ""; Write-Host $Message -ForegroundColor Cyan }
        default { Write-Host $Message }
    }
}

function Invoke-Native {
    # See the long note in backup_databases.ps1: under ErrorActionPreference=Stop,
    # a native command's redirected stderr becomes a terminating error.
    param([string] $Exe, [string[]] $Arguments)
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & $Exe @Arguments 2>&1
        $code   = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previous
    }
    return [pscustomobject]@{ ExitCode = $code; Output = @($output | ForEach-Object { "$_" }) }
}

function Resolve-PgBin {
    param([string] $Supplied)
    if ($Supplied) {
        if (-not (Test-Path (Join-Path $Supplied "pg_restore.exe"))) {
            throw "pg_restore.exe not found in supplied -PgBin '$Supplied'."
        }
        return $Supplied
    }
    $candidates = Get-ChildItem "C:\Program Files\PostgreSQL" -Directory -ErrorAction SilentlyContinue |
        Where-Object { Test-Path (Join-Path $_.FullName "bin\pg_restore.exe") } |
        Sort-Object { [int]($_.Name -replace '\D', '0') } -Descending
    if ($candidates) { return (Join-Path $candidates[0].FullName "bin") }
    $cmd = Get-Command pg_restore.exe -ErrorAction SilentlyContinue
    if ($cmd) { return (Split-Path $cmd.Source -Parent) }
    throw "Could not locate the PostgreSQL bin directory. Pass -PgBin explicitly."
}

function Get-DatabaseSettings {
    $result = @{ PgHost = "localhost"; Port = "5432"; User = "lexuser"; Password = "" }
    foreach ($file in @("$repoRoot\server_py\.env", "$repoRoot\server_py\.env.native")) {
        if (-not (Test-Path $file)) { continue }
        $line = Select-String -Path $file -Pattern '^\s*DATABASE_URL\s*=' -ErrorAction SilentlyContinue |
                Select-Object -First 1
        if (-not $line) { continue }
        $url = ($line.Line -split '=', 2)[1].Trim().Trim('"').Trim("'")
        if ($url -match '^[a-zA-Z0-9+]+://([^:/@]+):([^@]*)@([^:/]+):(\d+)/') {
            $result.User     = [uri]::UnescapeDataString($matches[1])
            $result.Password = [uri]::UnescapeDataString($matches[2])
            $result.PgHost   = $matches[3]
            $result.Port     = $matches[4]
            break
        }
    }
    if ($PgHost)     { $result.PgHost   = $PgHost }
    if ($PgPort)     { $result.Port     = $PgPort }
    if ($PgUser)     { $result.User     = $PgUser }
    if ($PgPassword) { $result.Password = $PgPassword }
    return $result
}

function Invoke-Psql {
    param([string] $DatabaseName, [string] $Sql, [switch] $AllowFailure)
    $r = Invoke-Native $psqlExe @(
        "-U", $settings.User, "-h", $settings.PgHost, "-p", $settings.Port,
        "-d", $DatabaseName, "-A", "-t", "-v", "ON_ERROR_STOP=1", "-c", $Sql)
    if ($r.ExitCode -ne 0 -and -not $AllowFailure) {
        throw "psql failed against '$DatabaseName': $($r.Output -join '; ')"
    }
    return $r
}

function Test-DatabaseExists {
    param([string] $Name)
    $r = Invoke-Psql -DatabaseName "postgres" -Sql "SELECT 1 FROM pg_database WHERE datname = '$Name';"
    return (@($r.Output | Where-Object { $_.Trim() -eq "1" }).Count -gt 0)
}

function Get-RowCounts {
    <#
        EXACT counts, not pg_stat_user_tables.n_live_tup - that is an estimate,
        and it reads 0 for every table immediately after a restore until ANALYZE
        has run, which would make a drill comparison meaningless.
    #>
    param([string] $Name)
    $sql = @"
SELECT relname || '|' || (xpath('/row/cnt/text()', xml_count))[1]::text
FROM (
  SELECT c.relname,
         query_to_xml(format('SELECT count(*) AS cnt FROM %I.%I', n.nspname, c.relname),
                      false, true, '') AS xml_count
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE c.relkind = 'r' AND n.nspname = 'public'
) t
ORDER BY relname;
"@
    $r = Invoke-Psql -DatabaseName $Name -Sql $sql
    $counts = [ordered]@{}
    foreach ($line in $r.Output) {
        if ("$line" -match '^([^|]+)\|(\d+)$') { $counts[$matches[1]] = [long]$matches[2] }
    }
    return $counts
}

function Format-Bytes {
    param([long] $Bytes)
    if ($Bytes -ge 1GB) { return "{0:N2} GB" -f ($Bytes / 1GB) }
    if ($Bytes -ge 1MB) { return "{0:N2} MB" -f ($Bytes / 1MB) }
    if ($Bytes -ge 1KB) { return "{0:N1} KB" -f ($Bytes / 1KB) }
    return "$Bytes B"
}

# ============================================================== main =========

$pgBinDir     = Resolve-PgBin $PgBin
$pgRestoreExe = Join-Path $pgBinDir "pg_restore.exe"
$pgDumpExe    = Join-Path $pgBinDir "pg_dump.exe"
$psqlExe      = Join-Path $pgBinDir "psql.exe"

$settings = Get-DatabaseSettings
$env:PGPASSWORD = $settings.Password

try {

Say "=== LexChat database restore ===" "HEAD"
Say "PostgreSQL tools : $pgBinDir"
Say "Server           : $($settings.User)@$($settings.PgHost):$($settings.Port)"

# --- 1. Resolve the dump -----------------------------------------------------

if (-not $DumpFile) {
    if (-not (Test-Path $BackupRoot)) { throw "Backup root '$BackupRoot' does not exist. Pass -DumpFile explicitly." }

    $candidate = Get-ChildItem $BackupRoot -Directory -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -match '^\d{4}-\d{2}-\d{2}_\d{6}$' -and
            -not (Test-Path (Join-Path $_.FullName "FAILED")) -and
            (Test-Path (Join-Path $_.FullName "$Database.dump"))
        } | Sort-Object Name -Descending | Select-Object -First 1

    if (-not $candidate) {
        throw "No verified backup run under '$BackupRoot' contains $Database.dump. Runs marked FAILED are skipped by design."
    }
    $DumpFile = Join-Path $candidate.FullName "$Database.dump"
}

if (-not (Test-Path $DumpFile)) { throw "Dump file not found: $DumpFile" }
$dumpItem = Get-Item $DumpFile
$runDir   = Split-Path $DumpFile -Parent

Say "Dump             : $DumpFile"
Say "Dump size        : $(Format-Bytes $dumpItem.Length)"
Say "Dump written     : $($dumpItem.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss'))"

$manifestPath = Join-Path $runDir "manifest.json"
if (Test-Path $manifestPath) {
    try {
        $manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
        Say "Backup status    : $($manifest.status)"
        Say "Commit SHA       : $($manifest.commit_sha)"
        Say "PostgreSQL       : $($manifest.pg_version)"
        Say "Globals mode     : $($manifest.globals.mode)"
        if ($manifest.status -ne "ok") {
            Say "WARNING: this backup run was marked $($manifest.status)." "WARN"
        }
        $thisDb = $manifest.databases | Where-Object { $_.name -eq $Database }
        if ($thisDb -and $thisDb.verify -ne "ok") {
            Say "WARNING: $Database did not verify at backup time ($($thisDb.verify))." "WARN"
        }
        Say ""
        Say "Check the commit SHA above against the code now deployed. An older dump"
        Say "onto newer code is fine: startup re-applies the additive ADD COLUMN"
        Say "migrations. A NEWER dump onto older code is not - the schema will carry"
        Say "columns the running code does not know about, and may be missing none."
    } catch {
        Say "Could not parse manifest.json: $($_.Exception.Message)" "WARN"
    }
} else {
    Say "No manifest.json beside this dump - provenance unknown." "WARN"
}

# --- 2. Verify the dump BEFORE touching the database -------------------------

Say "Verifying the dump before anything is dropped..." "HEAD"

$listResult = Invoke-Native $pgRestoreExe @("--list", $DumpFile)
$tocCount   = @($listResult.Output | Where-Object { $_ -match '^\d+;' }).Count
if ($listResult.ExitCode -ne 0 -or $tocCount -eq 0) {
    Say "ABORTING: pg_restore --list failed on this dump." "ERROR"
    $listResult.Output | ForEach-Object { Say "  $_" "ERROR" }
    exit 1
}

# --list reads only the table of contents, which sits ahead of the data, so it
# passes on a dump truncated halfway through. The full read is what catches that.
$deepResult = Invoke-Native $pgRestoreExe @("-f", "NUL", $DumpFile)
if ($deepResult.ExitCode -ne 0) {
    Say "ABORTING: the dump is corrupt - it lists correctly but cannot be read in full." "ERROR"
    $deepResult.Output | ForEach-Object { Say "  $_" "ERROR" }
    Say "Use an older run. Nothing has been changed." "ERROR"
    exit 1
}
Say "Dump verified: $tocCount TOC entries, archive fully readable." "OK"

# --- 3. Confirm --------------------------------------------------------------

$targetExists = Test-DatabaseExists $TargetDatabase

Say "About to restore" "HEAD"
Say "  from : $DumpFile"
Say "  into : $TargetDatabase  $(if ($targetExists) { '(EXISTS - will be DROPPED and recreated)' } else { '(does not exist - will be created)' })"
if ($targetExists) {
    $existingCounts = Get-RowCounts $TargetDatabase
    $existingTotal  = 0
    foreach ($v in $existingCounts.Values) { $existingTotal += $v }
    Say "  $TargetDatabase currently holds $existingTotal row(s) across $($existingCounts.Count) table(s). All of it will be replaced."
}

if (-not $Force) {
    Say ""
    $answer = Read-Host "Type the target database name ($TargetDatabase) to proceed, anything else to abort"
    if ($answer -ne $TargetDatabase) {
        Say "Aborted. Nothing has been changed." "WARN"
        exit 1
    }
}

# --- 4. Stop the app (NOT PostgreSQL) ----------------------------------------
# Note that stop_native.cmd is the wrong tool here: its last step stops the
# PostgreSQL service, and the restore needs the server running.

if ($NoAppStop) {
    Say "Leaving the running app alone (-NoAppStop)." "HEAD"
    if ($TargetDatabase -eq $Database) {
        Say "You are overwriting '$TargetDatabase' with the app still connected to it. This is only safe if the app is already stopped." "WARN"
    }
} else {
    Say "Stopping the app (PostgreSQL stays up)..." "HEAD"

    # Stop the autostart task first, or it may bring uvicorn straight back.
    $autoTask = Get-ScheduledTask -TaskName "LexChat Autostart" -ErrorAction SilentlyContinue
    if ($autoTask) {
        try {
            Stop-ScheduledTask -TaskName "LexChat Autostart" -ErrorAction SilentlyContinue
            Say "  Stopped the 'LexChat Autostart' task."
        } catch { }
    }

    Get-Process nginx -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine -match 'uvicorn' } |
        ForEach-Object {
            Say "  Stopping uvicorn (PID $($_.ProcessId))."
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
    Start-Sleep -Seconds 3
    Say "  App stopped."
}

# PostgreSQL itself must be up.
$pgService = Get-Service -Name "postgresql*" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($pgService -and $pgService.Status -ne "Running") {
    Say "Starting the PostgreSQL service ($($pgService.Name))..."
    Start-Service -Name $pgService.Name
    Start-Sleep -Seconds 5
}

# --- 5. Safety dump ----------------------------------------------------------
# Cheap insurance that makes the restore itself undoable.

if ($targetExists -and -not $SkipSafetyDump) {
    Say "Dumping the current contents of $TargetDatabase first..." "HEAD"
    $preDir = Join-Path $BackupRoot "pre-restore"
    if (-not (Test-Path $preDir)) { New-Item -ItemType Directory -Path $preDir -Force | Out-Null }
    $safetyFile = Join-Path $preDir ("{0}_{1}.dump" -f $TargetDatabase, (Get-Date -Format "yyyy-MM-dd_HHmmss"))

    $r = Invoke-Native $pgDumpExe @(
        "-U", $settings.User, "-h", $settings.PgHost, "-p", $settings.Port,
        "-d", $TargetDatabase, "-Fc", "-f", $safetyFile)
    if ($r.ExitCode -ne 0) {
        Say "ABORTING: could not dump the current contents, so the restore would not be undoable." "ERROR"
        $r.Output | ForEach-Object { Say "  $_" "ERROR" }
        Say "Re-run with -SkipSafetyDump if you accept that, and are certain." "ERROR"
        exit 1
    }
    Say "Safety dump: $safetyFile ($(Format-Bytes (Get-Item $safetyFile).Length))" "OK"
    Say "To undo this restore, run this script again with -DumpFile `"$safetyFile`""
}

# --- 6. Drop, recreate, restore ----------------------------------------------

Say "Restoring..." "HEAD"

if ($targetExists) {
    # Drop the database, not just its tables: pg_restore into a database that
    # still holds objects produces a blizzard of "already exists" errors that
    # hide the real ones.
    Invoke-Psql -DatabaseName "postgres" -Sql @"
SELECT pg_terminate_backend(pid) FROM pg_stat_activity
WHERE datname = '$TargetDatabase' AND pid <> pg_backend_pid();
"@ | Out-Null
    Say "  Terminated remaining connections to $TargetDatabase."

    Invoke-Psql -DatabaseName "postgres" -Sql "DROP DATABASE IF EXISTS `"$TargetDatabase`";" | Out-Null
    Say "  Dropped $TargetDatabase."
}

Invoke-Psql -DatabaseName "postgres" -Sql "CREATE DATABASE `"$TargetDatabase`" OWNER `"$($settings.User)`";" | Out-Null
Say "  Created $TargetDatabase (owner $($settings.User))."

if ($RestoreGlobals) {
    $globalsFile = Join-Path $runDir "globals.sql"
    if (Test-Path $globalsFile) {
        $r = Invoke-Native $psqlExe @(
            "-U", $settings.User, "-h", $settings.PgHost, "-p", $settings.Port,
            "-d", "postgres", "-f", $globalsFile)
        if ($r.ExitCode -ne 0) {
            Say "  Globals produced errors (usually just 'role already exists' - harmless on an existing cluster):" "WARN"
            $r.Output | Select-Object -First 10 | ForEach-Object { Say "    $_" "WARN" }
        } else {
            Say "  Globals applied."
        }
    } else {
        Say "  -RestoreGlobals given but no globals.sql beside the dump." "WARN"
    }
}

$restoreStart = Get-Date
$r = Invoke-Native $pgRestoreExe @(
    "-U", $settings.User, "-h", $settings.PgHost, "-p", $settings.Port,
    "-d", $TargetDatabase, "--no-owner", "--no-privileges", $DumpFile)
$restoreSeconds = [math]::Round(((Get-Date) - $restoreStart).TotalSeconds, 1)

$errorLines = @($r.Output | Where-Object { $_ -match 'error:' })
if ($r.ExitCode -ne 0 -or $errorLines.Count -gt 0) {
    Say "pg_restore reported $($errorLines.Count) error(s), exit code $($r.ExitCode):" "ERROR"
    $errorLines | Select-Object -First 20 | ForEach-Object { Say "  $_" "ERROR" }
    if ($errorLines.Count -gt 20) { Say "  ... and $($errorLines.Count - 20) more." "ERROR" }
    Say ""
    Say "The database is in an unknown state. Do NOT start the app against it until" "ERROR"
    Say "you have read the errors above. See docs\deployment\BACKUP_RUNBOOK.md." "ERROR"
    $restoreFailed = $true
} else {
    Say "Restored in ${restoreSeconds}s with no errors." "OK"
    $restoreFailed = $false
}

# The restore leaves no statistics behind, so the first queries against the
# restored database would plan badly.
Invoke-Psql -DatabaseName $TargetDatabase -Sql "ANALYZE;" -AllowFailure | Out-Null
Say "ANALYZE complete."

# --- 7. Row counts -----------------------------------------------------------

Say "Row counts in $TargetDatabase" "HEAD"
$restored = Get-RowCounts $TargetDatabase

if ($CompareWith) {
    if (-not (Test-DatabaseExists $CompareWith)) { throw "-CompareWith database '$CompareWith' does not exist." }
    $reference = Get-RowCounts $CompareWith

    $allTables = @($reference.Keys) + @($restored.Keys) | Sort-Object -Unique
    $rows = foreach ($t in $allTables) {
        $refCount = if ($reference.Contains($t)) { $reference[$t] } else { $null }
        $newCount = if ($restored.Contains($t))  { $restored[$t]  } else { $null }

        # local_prompt_cache rows are excluded from every dump by design, so an
        # empty table here is the correct outcome, not a discrepancy.
        if ($t -eq "local_prompt_cache") {
            $note = "excluded by design"
        } elseif ($refCount -eq $newCount) {
            $note = "match"
        } else {
            $note = "*** DIFFERS ***"
        }

        [pscustomobject][ordered]@{
            Table        = $t
            $CompareWith = $refCount
            Restored     = $newCount
            Result       = $note
        }
    }
    $rows | Format-Table -AutoSize | Out-String -Width 200 | Write-Host

    $mismatches = @($rows | Where-Object { $_.Result -eq "*** DIFFERS ***" })
    if ($mismatches.Count -eq 0) {
        Say "Every table matches $CompareWith (local_prompt_cache excluded by design)." "OK"
    } else {
        Say "$($mismatches.Count) table(s) differ from $CompareWith." "WARN"
        Say "If the source database has taken writes since the dump was taken, differences in"
        Say "chats / messages / request_timings / activity_log are expected. Differences in"
        Say "users, app_settings or peer_bots are not, and are worth investigating."
    }
} else {
    $total = 0
    $rows = foreach ($t in $restored.Keys) {
        $total += $restored[$t]
        [pscustomobject]@{ Table = $t; Rows = $restored[$t] }
    }
    $rows | Format-Table -AutoSize | Out-String -Width 200 | Write-Host
    Say "$total row(s) across $($restored.Count) table(s)."
}

# --- 8. What to do next ------------------------------------------------------

Say "Next steps" "HEAD"
if ($restoreFailed) {
    Say "The restore reported errors. Do not start the app until they are understood." "ERROR"
} elseif ($NoAppStop) {
    Say "Nothing was stopped, so nothing needs restarting."
    if ($TargetDatabase -ne $Database) {
        Say "This was a restore into a scratch database. When you are finished with it:"
        Say "  psql -U $($settings.User) -h $($settings.PgHost) -d postgres -c 'DROP DATABASE $TargetDatabase;'"
    }
} else {
    Say "1. Start the app:  .\deployment\start_native.cmd"
    Say "     (or, if the autostart task is installed: Start-ScheduledTask -TaskName 'LexChat Autostart')"
    Say "   Startup re-applies the additive ADD COLUMN migrations, which is what makes"
    Say "   an older dump safe against newer code."
    Say "2. Smoke test: log in, open a chat, confirm the Admin Portal loads."
    Say "3. Check the backend log for schema errors:"
    Say "     Get-Content .\deployment\logs\backend.log -Tail 50"
}
Say ""

} finally {
    if ($env:PGPASSWORD) { Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue }
}

if ($restoreFailed) { exit 1 }
exit 0
