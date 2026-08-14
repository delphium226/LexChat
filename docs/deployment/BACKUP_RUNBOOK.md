# Backup & Restore Runbook

**Written for someone doing this at 2am.** Start at [Something is broken](#something-is-broken)
and follow it down. The reference material is below that.

Plan and rationale: `docs/BACKUP_RESTORE_PLAN.md`. This document is the procedure.

---

## The 30-second version

```powershell
# 1. Is there a good backup?
Get-ChildItem C:\LexChatBackups -Directory | Sort-Object Name -Descending | Select-Object -First 3

# 2. Restore the newest verified one (asks you to type the database name):
cd C:\Projects\LexChat
.\deployment\restore_database.ps1 -Database lexchat

# 3. Start the app back up:
.\deployment\start_native.cmd
```

The restore script verifies the dump **before** it drops anything, and dumps the
current contents first, so step 2 is reversible.

---

## Something is broken

### "Somebody hit the Danger Zone / cleared data they should not have"

**Do not restore the whole database.** A full restore also rolls back everything
that happened since last night, including other people's chats. What you have
lost is scope-shaped, and there is a scope-shaped tool for it.

**Admin Portal -> Developer -> Restore from backup.** No console needed.

1. Pick the backup to restore from (defaults to the most recent verified one).
2. Tick the same boxes that were ticked in the Danger Zone.
3. Press **Check what would change**. This loads the dump into a staging
   database and reports, line by line, exactly what it would put back - it is
   the real restore with the writes withheld, not an estimate.
4. Read it, type `RESTORE`, press the button.

It is **additive**: it only fills in what is missing and never overwrites
anything that survived, so it is safe to run twice and safe to run when you are
not sure. It dumps the current contents to `C:\LexChatBackups\pre-restore\`
first, so it can itself be undone, and it writes a row to the activity log.

**Reading the preflight.** Three things surprise people:

- **"Cached summaries" is always unavailable.** `local_prompt_cache` rows are
  excluded from every dump by design, so there is nothing to restore. It is pure
  cache and refills on its own. This is correct, not a fault.
- **"Message ratings" says *updates rows that survived*.** Clearing feedback sets
  `rating = NULL` in place; the messages themselves are still there. So ratings
  are written back onto the existing rows rather than inserted.
- **Rows can be reported as unrestorable.** If a user or matter was deleted by
  hand, their chats have nothing to attach to. Those are skipped and counted;
  optional links (a chat's matter) are simply cleared instead.

**If you cleared `feedback` but restore `chats`,** the messages already exist, so
nothing happens and the preflight will show every count as 0. Tick the scope that
was actually cleared.

**If the restore panel is not there,** no verified backup of this bot's database
exists yet - see [Is the backup healthy?](#is-the-backup-healthy).

<details>
<summary>Doing it by hand instead (only if the Developer tab is unreachable)</summary>

1. Restore last night's dump into a **scratch** database, not over the live one:

   ```powershell
   .\deployment\restore_database.ps1 -Database lexchat `
       -TargetDatabase lexchat_recovery -NoAppStop
   ```

2. Copy back only what was lost:

   ```
   pg_dump -Fc -t session_feedback -d lexchat_recovery -f sf.dump
   pg_restore -d lexchat --data-only -t session_feedback sf.dump
   ```

   **Parents before children.** `chats` must land before `session_feedback`
   (whose `chat_id` FK points at it), and `chats` -> `messages` -> `documents`
   in that order.

   **Ratings are an UPDATE, not an INSERT.** A data-only insert restores nothing
   for them, because the message rows still exist and every insert conflicts:

   ```sql
   UPDATE messages m SET rating = s.rating, feedback_comment = s.feedback_comment
   FROM staging.messages s
   WHERE m.id = s.id AND (s.rating IS NOT NULL OR s.feedback_comment IS NOT NULL);
   ```

3. **Reset the sequences afterwards,** or the next real INSERT collides with a
   restored primary key hours later:

   ```sql
   SELECT setval(pg_get_serial_sequence('chats','id'),
                 COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM chats;
   ```

4. Drop the scratch database when you are done.

</details>

### "The database is corrupt / the app will not start / a migration went wrong"

Full restore. Go to [Full database restore](#full-database-restore).

### "The whole VM is gone"

The dumps live on the same box, so they are gone too. **This regime does not
cover VM loss** - see D15 in `docs/TODO.md`, which is blocked on the server owner
naming an off-box destination. Rebuild from `git clone` and start with empty
databases; the app creates its own schema on startup. The parliament corpus can
be re-crawled (about 17 hours against a rate-limited origin).

---

## Full database restore

### Before you start

Know which database you are restoring. They are separate, one per bot:

| Database | Bot |
|---|---|
| `lexchat` | legislation |
| `lexchat_parliament` | parliament (Holyrood) - the big one, ~305 MB |
| `lexchat_westminster` | Westminster |
| `lexchat_drafting` | drafting |

`lexchat_test` is pytest's target and is **not** backed up. That is deliberate.

### The procedure

```powershell
cd C:\Projects\LexChat
.\deployment\restore_database.ps1 -Database lexchat
```

The script does all of this in order, and stops at the first thing that fails:

1. **Picks the newest verified run** under `C:\LexChatBackups` and prints its
   manifest - date, size, and the **commit SHA** the dump's schema belongs to.
2. **Verifies the dump before touching anything.** If it cannot be read, you
   find out here, with the live database untouched.
3. **Stops the app but leaves PostgreSQL running.** (Do not use
   `stop_native.cmd` for this - its last step stops the PostgreSQL service, and
   the restore needs the server up.)
4. **Dumps the current contents first** into `C:\LexChatBackups\pre-restore\`,
   so the restore is undoable. It prints the exact command to undo it.
5. Terminates leftover connections, drops and recreates the database, restores.
6. Runs `ANALYZE` and prints exact per-table row counts.

Then, by hand:

```powershell
.\deployment\start_native.cmd
```

Startup re-applies the additive `ADD COLUMN IF NOT EXISTS` migrations in
`server_py/src/database.py`, which is what makes an older dump safe against
newer code.

**Smoke test:** log in, open a chat, send one message, confirm the Admin Portal
loads. Then check the backend log for schema errors:

```powershell
Get-Content .\deployment\logs\backend.log -Tail 50
```

### Restoring from a specific night

```powershell
.\deployment\restore_database.ps1 -Database lexchat `
    -DumpFile C:\LexChatBackups\2026-08-13_023000\lexchat.dump
```

### Undoing a restore

The pre-restore safety dump is a normal dump:

```powershell
.\deployment\restore_database.ps1 -Database lexchat `
    -DumpFile C:\LexChatBackups\pre-restore\lexchat_2026-08-14_075705.dump
```

### About the commit SHA

The restore script prints the commit SHA the dump was taken at. Compare it with
what is deployed (`git rev-parse HEAD`):

- **Dump older than the code** - fine. Startup brings the schema forward.
- **Dump newer than the code** - not fine. The restored schema carries columns
  the running code does not know about. `git pull` to at least the dump's commit
  before starting the app.

### Restoring into a fresh PostgreSQL cluster

Only in this case do you need the roles as well:

```powershell
.\deployment\restore_database.ps1 -Database lexchat -RestoreGlobals
```

**`lexuser` will have no password.** `lexuser` is not a superuser, so
`pg_dumpall` cannot read the password hashes out of `pg_authid`; the nightly
backup falls back to `--no-role-passwords` and the manifest records
`"globals": {"mode": "no-role-passwords"}`. Set it by hand to whatever
`server_py/.env` expects:

```sql
ALTER ROLE lexuser WITH PASSWORD 'lexpassword';
```

---

## The monthly restore drill

**A backup that has never been restored is a hypothesis, not a backup.** Run
this once a month. It touches nothing live and takes about a minute.

```powershell
cd C:\Projects\LexChat
.\deployment\restore_database.ps1 -Database lexchat_parliament `
    -TargetDatabase lexchat_restore_test -CompareWith lexchat_parliament `
    -NoAppStop -Force
```

It restores into a scratch database and prints row counts side by side with
live, flagging every difference.

**Reading the result:**

- `local_prompt_cache` showing 0 restored rows is **correct** - its rows are
  excluded from every dump by design. The script labels it "excluded by design".
- Differences in `chats`, `messages`, `request_timings`, `activity_log` and
  `service_health_logs` are expected if the app has taken writes since the dump.
- Differences in `users`, `app_settings` or `peer_bots` are **not** expected and
  are worth investigating.

Clean up afterwards:

```powershell
psql -U lexuser -h localhost -d postgres -c "DROP DATABASE lexchat_restore_test;"
```

**Last rehearsed:** 2026-08-14, on the dev machine, against PostgreSQL 18.3.
Both `lexchat` and `lexchat_parliament` restored with every table matching; the
parliament corpus (157 MB dump, 2,423 committee items / 3,763 plenary items /
1,177 caption rows) restored in 33s with identical index and constraint counts
and identical full-text search results.

---

## Is the backup healthy?

**The quickest answer is Admin Portal -> Developer -> Backup status.** It reads
the same `manifest.json` files as the commands below and shows the last run, its
size and duration, the per-database verify result, and the commit SHA the dump's
schema belongs to. It also says plainly when the backup directory does not exist
or holds no runs.

For anything the panel does not cover:

```powershell
# Did last night's run succeed? LastTaskResult 0 = yes.
Get-ScheduledTaskInfo -TaskName "LexChat Database Backup" |
    Select-Object LastRunTime, LastTaskResult, NextRunTime

# What did it say?
Get-Content C:\LexChatBackups\logs\backup.log -Tail 30

# What is on disk?
Get-ChildItem C:\LexChatBackups -Directory | Sort-Object Name -Descending | Select-Object -First 5
```

A run directory containing a file named `FAILED` is a failed run. Failed runs
are kept for 14 days so they can be investigated, and are **never** selected by
the restore script.

Failures also raise an Application event log entry:

```powershell
Get-EventLog -LogName Application -Source "LexChat Backup" -Newest 10
```

### Run a backup on demand

```powershell
Start-ScheduledTask -TaskName "LexChat Database Backup"
# or directly:
.\deployment\backup_databases.ps1
```

It is safe to run against a live system. `pg_dump` takes a consistent MVCC
snapshot; nothing is locked and nobody is interrupted.

---

## Installing the regime on a new server

```powershell
# Elevated PowerShell:
cd C:\Projects\LexChat
.\deployment\install_backup_task.ps1 -RunNow
```

That creates `C:\LexChatBackups`, locks its ACL to SYSTEM and Administrators
only, registers the "LexChat Backup" event log source, and schedules the nightly
run at 02:30 as SYSTEM.

**The ACL matters.** Dumps contain `app_settings` (the OpenRouter API key) and
`peer_bots.api_key`. Treat the backup directory exactly like the PostgreSQL data
directory.

Options:

```powershell
.\deployment\install_backup_task.ps1 `
    -BackupRoot D:\Backups\LexChat `   # somewhere with room
    -At 01:00 `                        # time of day
    -KeepDaily 30                      # retention
```

**Prefer the default `C:\LexChatBackups`.** The app (`config.py`) and the
installer already agree on it, so with the default there is nothing to configure
and nothing to keep in sync.

**If you do change `-BackupRoot`,** the app has to be told too, or the Developer
tab's backup panel reads an empty directory and reports that nothing is being
backed up while the nightly task runs perfectly somewhere else. Set it in
`server_py/.env.native`:

```
BACKUP_ROOT=D:\Backups\LexChat
```

**Not `server_py/.env`** — `start_native.cmd` does `copy /Y .env.native .env` on
every start, so anything written directly to `.env` is silently overwritten the
next time the app restarts.

Be aware that `.env.native` is **tracked in git**, so a local edit to it can
collide with a `git pull`. If that happens:

```powershell
copy server_py\.env.native server_py\.env.native.bak
git checkout -- server_py\.env.native
git pull
copy /Y server_py\.env.native.bak server_py\.env.native
```

---

## Reference

### What gets backed up

Databases are **enumerated at run time**, not hardcoded:

```sql
SELECT datname FROM pg_database
WHERE datname LIKE 'lexchat%' AND datname <> 'lexchat_test'
```

so a new federated bot is backed up the night it is created, with nobody having
to remember to edit anything.

Each run writes one directory, `C:\LexChatBackups\YYYY-MM-DD_HHMMSS\`:

| File | What it is |
|---|---|
| `<database>.dump` | `pg_dump -Fc` custom-format archive |
| `globals.sql` | roles, from `pg_dumpall --globals-only` |
| `manifest.json` | status, commit SHA, sizes, durations, verify results |
| `FAILED` | present only if the run failed; contains the reasons |
| `*.dump.corrupt` | a dump that failed verification, quarantined |

`local_prompt_cache` rows are excluded (`--exclude-table-data`). The table's
schema is kept; only its rows are dropped. It is pure cache, and it is the only
table holding plaintext user queries, so excluding it shrinks the sensitive
surface as well as the file.

Current sizes: about 157 MB per run, dominated by `lexchat_parliament`. A run
takes about 20 seconds.

### How dumps are verified

**Two stages, and the second is the one that matters.**

`pg_restore --list` reads only the table of contents, which sits *ahead* of the
data in a custom-format archive. It therefore does **not** check the data
blocks: measured on this deployment, a dump truncated to exactly half its length
listed all 172 TOC entries and exited 0. On its own it catches only a missing or
header-corrupt file.

`pg_restore -f NUL` converts the whole archive to SQL and discards the output,
forcing every data block to be read and decompressed. That is what actually
catches truncation (`could not read from input file: end of file`). It costs
about 1.7 seconds for the 157 MB parliament dump, so it runs on every database
every night.

A dump that fails either stage is renamed to `<name>.dump.corrupt`, the run is
marked `FAILED`, an event log entry is written, and the script exits 1.

### Retention

GFS, computed as a selection over one flat list of runs - no promotion, no
copying, no hard links:

- the **14** most recent successful runs, plus
- the newest successful run of each of the last **8** ISO weeks, plus
- the newest successful run of each of the last **12** calendar months.

Failed runs never occupy a weekly or monthly slot - a broken backup must not
displace a good one - but are kept for 14 days for investigation. Everything
else is deleted. About 3 GB for a full year.

### What is deliberately not covered

- **WAL archiving / PITR.** RPO is therefore 24 hours: a failure at 18:00 loses
  that day's chats. Revisit if the org states an RPO under 24 hours.
- **Off-box copies.** The dumps sit on the same disk as the database. This
  protects against `DROP TABLE`, a bad migration and the Danger Zone. It does
  **not** protect against loss of the VM. Blocked on the server owner - D15.
- **A download-dump button.** The file contains the OpenRouter key and the
  federation API keys.
