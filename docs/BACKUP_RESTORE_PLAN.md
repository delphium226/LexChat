# Database Backup & Restore — Implementation Plan

**Scoped 2026-08-14.** There is currently **no backup of any kind** on the
target: no `pg_dump`, no scheduled task, no documented restore procedure.
Nothing in `deployment/` touches it and it has never appeared in `docs/TODO.md`.

**Verdict context.** Total data across all five databases is ~335 MB, which
makes this a much smaller problem than it first appears. Nightly logical dumps
(`pg_dump -Fc`) are sufficient. **No WAL archiving / PITR** — see "Deliberately
not built".

**Branch:** `main`, per the usual convention. Phases 1–3 are the load-bearing
part and are worth landing on their own; 4–6 are convenience on top.

---

## Current state

PostgreSQL 18, Windows service `postgresql-x64-18`, started by
`deployment/start_native.cmd` (line 28). Five databases on one instance:

| Database | Size | Notes |
|---|---|---|
| `lexchat_parliament` | 305 MB | ~95% of all bytes — the crawled SP corpus |
| `lexchat` | 11 MB | legislation bot |
| `lexchat_drafting` | 10 MB | drafting bot |
| `lexchat_westminster` | 9 MB | Westminster bot |
| `lexchat_test` | 9 MB | pytest target — **excluded from backup** |

No Alembic. Schema is created by `Base.metadata.create_all` plus a list of
`ALTER TABLE ... ADD COLUMN IF NOT EXISTS` statements at
`server_py/src/database.py:40`+, run on every startup. This makes restore
unusually forgiving: **restore into an empty DB, then start the app, and it
brings its own schema forward.** An older dump onto newer code works. The
reverse does not — hence the commit SHA in the manifest (Phase 1).

### Data tiers

Worth distinguishing, because they justify different retention:

- **Irreplaceable** (~25 MB across all bots) — `users`, `chats` / `messages`,
  `matters` / `matter_notes`, `product_feedback` / `session_feedback` (pilot
  evaluation data), `app_settings`, `peer_bots`, `request_timings`,
  `activity_log`, `documents`.
- **Re-derivable but expensive** — `sp_committee_items`, `sp_plenary_items`,
  `sp_video_captions`. Rebuildable from parliament.scot, but a from-scratch
  backfill is the ~17h walk against a rate-limited origin that intermittently
  serves Cloudflare 524s. Back it up to avoid that, not because it is lost.
- **Discard** — `local_prompt_cache`. Pure cache; dies harmlessly. It is also
  the only table holding plaintext user queries (`query_text`), so excluding
  its rows shrinks the sensitive surface as well as the file.

---

# PART A — BACKUP

## Phase 1 — `deployment/backup_databases.ps1`

Nightly `pg_dump -Fc` per database, plus `pg_dumpall --globals-only` for the
`lexuser` role (a dump does not carry roles; restoring without them fails on
ownership).

**Enumerate, don't hardcode.** Discover targets with:

```sql
SELECT datname FROM pg_database
WHERE datname LIKE 'lexchat%' AND datname <> 'lexchat_test'
```

A new federated bot (`shared/scripts/new_bot.ps1`) is then covered the day it
is created, with nobody needing to remember to edit the script.

**Per database:**

```
pg_dump -Fc --exclude-table-data=local_prompt_cache -d <db> -f <out>.dump
```

Custom format (`-Fc`), not plain SQL — it allows selective restore
(`pg_restore -t messages`), which is what the realistic failure actually needs.
`--exclude-table-data` keeps the table's schema and drops only its rows.

**Write a manifest** (`manifest.json`) beside each run:

```json
{
  "started_at": "...", "finished_at": "...",
  "commit_sha": "<git rev-parse HEAD>",
  "pg_version": "18",
  "databases": [
    {"name": "lexchat", "bytes": 2291712, "verify": "ok", "duration_s": 1.4}
  ]
}
```

The commit SHA is the field that matters at 2am: it tells you which code the
dump's schema belongs to.

**Runtime:** no need to stop the app. `pg_dump` takes a consistent MVCC
snapshot; at this size the whole run finishes in well under a minute.

## Phase 2 — Verification, retention, scheduling

**Verify every run.** `pg_restore --list <file>` immediately after writing.
Cheap, and it catches truncation and half-written files from a mid-dump reboot
— the failure mode where the file looks fine by size and is worthless. A failed
verify must fail the script loudly, not leave a corrupt file in place.

**Retention (GFS):** 14 daily / 8 weekly / 12 monthly. Compressed, a full set
is ~80–100 MB, so a year is ~3 GB — trivial next to the Ollama models already
on the box.

> Deferred refinement: the SP corpus is ~95% of the bytes and changes only by
> daily delta, so nightly full dumps store near-identical data. Splitting
> cadence (app data nightly, corpus weekly) would cut the footprint several
> times over. **Not worth the complexity at 3 GB/year** — revisit only if
> backup storage becomes constrained.

**Scheduling:** Windows Task Scheduler as `SYSTEM`, registered by
`deployment/install_backup_task.ps1`, following the existing
`install_autostart.ps1` idiom.

**Failure signalling:** write the manifest with per-DB status and emit a
Windows Event Log entry on failure. Wiring backup status into
`service_health_logs` is a natural follow-on but is deliberately out of v1.

**Access control.** Dumps contain `app_settings` (OpenRouter API key) and
`peer_bots.api_key`. The backup directory needs an ACL no broader than the
Postgres data directory itself. If backups leave the box, that is a decision
for whoever owns the OFFICIAL-SENSITIVE classification, not a technical
default.

## Phase 3 — `deployment/restore_database.ps1` + runbook

Full-database restore is a **console operation, never a button.** Three
reasons, each sufficient on its own:

1. **The app holds the connection.** `pg_restore` needs to drop and recreate
   objects, but the async pool has live sessions against that database. You
   cannot `DROP DATABASE` with sessions attached, and dropping tables under a
   running app means in-flight requests hit missing relations.
2. **It saws off its own branch.** The request performing the restore is
   authenticated against the `users` table it is about to replace, writing to
   an `activity_log` it is about to overwrite.
3. **Failure leaves no tool.** If it dies halfway, the Admin Portal you would
   use to retry is sitting on a half-restored database.

**Procedure:**

1. `stop_native.cmd`
2. `pg_dump` current state first (cheap insurance; makes the restore undoable)
3. `dropdb` / `createdb`, restore globals, then `pg_restore -d <db> <file>`
4. `start_native.cmd` — startup re-applies any additive `ADD COLUMN` migrations
5. Smoke: log in, open a chat, check Admin Portal loads

**Rehearse it once, into `lexchat_restore_test`, before calling Phase 3 done.**
A backup that has never been restored is a hypothesis, not a backup. Schedule
the same drill monthly with a row-count comparison against live.

---

# PART B — SCOPED RESTORE (Developer tab)

## The realistic disaster is the Danger Zone, not disk failure

`server_py/src/routers/developer.py:196` defines six clearable scopes
(`DATA_SCOPES`), and a "pilot reset" is all six ticked. It destroys chats /
messages / documents, timings, feedback, activity, health and cache — and
**deliberately preserves** users, `app_settings`, `peer_bots`, matters and the
SP corpus.

So the overwhelmingly likely restore need on this system is **scope-shaped, not
database-shaped**: somebody resets for the pilot, then wants last night's
session feedback back. The restore UI should therefore mirror the Danger Zone
exactly — same six scopes, same checkbox layout, same disclosure pattern. It is
the inverse of the operation that caused the loss.

## Phase 4 — Two-stage scoped restore (backend)

**Never `pg_restore` over live tables.** Two stages:

1. `pg_restore` the chosen nightly dump into a separate
   `lexchat_restore_staging` database that the app never connects to.
2. `INSERT ... SELECT` from staging into live, scope by scope.

Four details that make this correct rather than merely plausible.

### 4a. Ordering is the reverse of `_CLEAR_ORDER`

`developer.py:209` runs `feedback` before `chats`, because
`session_feedback.chat_id` is `ON DELETE SET NULL` and clearing chats first
orphans the feedback rows. Restore has the mirror-image constraint — parents
first — so `chats` must land **before** `feedback` or the FK has nothing to
point at. The plain reversal of `_CLEAR_ORDER` is correct:

```python
_RESTORE_ORDER = list(reversed(_CLEAR_ORDER))
# ["cache", "health", "activity", "performance", "chats", "feedback"]
```

Within the `chats` scope: `chats` → `messages` → `documents`.

### 4b. The `feedback` scope is a mixed DELETE/UPDATE — this is the trap

`clear_data` handles feedback in **three different ways** (`developer.py:285`):

| Component | Clear does | Restore must do |
|---|---|---|
| `ProductFeedback` | `DELETE` | `INSERT` |
| `SessionFeedback` | `DELETE` | `INSERT` |
| rated messages | **`UPDATE ... SET rating = NULL`** | **`UPDATE ... FROM staging`** |

Ratings live on `messages` and are **nulled in place**, not deleted. An
`INSERT ... ON CONFLICT DO NOTHING` therefore restores *nothing* for the third
component — the message rows still exist, so every insert conflicts and is
skipped, and the operation reports success having silently restored no ratings.
That component needs:

```sql
UPDATE messages m SET rating = s.rating, feedback_comment = s.feedback_comment
FROM staging.messages s
WHERE m.id = s.id AND (s.rating IS NOT NULL OR s.feedback_comment IS NOT NULL)
```

### 4c. Additive only — `ON CONFLICT (id) DO NOTHING`

Real losses are usually partial. An additive restore puts back what is missing
without overwriting anything that survived, which makes the operation
re-runnable and much harder to regret.

### 4d. Reset the sequences afterwards

Rows return with explicit primary keys, so the identity sequences are left
behind and the next real INSERT collides. Per restored table:

```sql
SELECT setval(pg_get_serial_sequence('chats','id'), COALESCE(MAX(id), 1)) FROM chats;
```

This is the classic bug in hand-rolled restores; it surfaces hours later as a
confusing duplicate-key error with no obvious connection to the restore.

### 4e. Stale FK references

`chats.matter_id` is `ON DELETE SET NULL` and `chats.user_id` is
`ON DELETE CASCADE, NOT NULL`. Neither matters nor users are in any clear
scope, so parents normally survive — but if one was deleted by hand, the
re-INSERT fails the constraint. Null the nullable references whose parent is
gone; skip (and report) rows whose NOT NULL parent is missing.

### 4f. Known lossy edge: `matter_notes.message_id`

`matter_notes.message_id` is `ON DELETE SET NULL` (`models.py:341`), and
`matter_notes` is in **no** clear scope. So clearing `chats` nulls those links
while leaving the notes themselves intact — a silent partial loss inside a
table the Danger Zone claims not to touch.

It is recoverable, because messages are restored with their original IDs, but
**only if handled explicitly**:

```sql
UPDATE matter_notes n SET message_id = s.message_id
FROM staging.matter_notes s
WHERE n.id = s.id AND n.message_id IS NULL AND s.message_id IS NOT NULL
```

Worth doing as part of the `chats` scope restore. Worth documenting in the
Danger Zone UI either way — the current copy implies matters are untouched.

## Phase 5 — Guard rails

Matching conventions already in the codebase:

- **Auto-backup before restore.** Any restore dumps current state first. At
  11 MB for `lexchat` that is seconds, and it makes the restore itself undoable.
- **Preflight dry run.** Mirror `get_data_counts` (`developer.py:224`):
  *"staging holds 1,240 chats and 8,900 messages; live holds 0; 1,240 would be
  inserted, 0 skipped."* Same philosophy as the existing `details` block —
  disclose the cascade rather than let it be discovered afterwards.
- **Confirm phrase `RESTORE`,** matching `_CONFIRM_PHRASE = "DELETE"`.
- **Log to `activity_log`** — who restored what, from which dump, how many rows.
  Given government-lawyer users and an audit trail that already exists, a
  restore belongs on it.
- **Endpoints go on `admin_router`** (`developer.py:44`), which carries
  `Depends(get_admin_user)` at router level.

New endpoints:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/developer/backups` | List available dumps + manifest data |
| `POST` | `/api/developer/restore/preflight` | Stage + report what would change |
| `POST` | `/api/developer/restore` | Execute (confirm phrase required) |

## Phase 6 — Developer tab UI

Two distinct panels, and the separation is the point:

1. **Backup status (read-only).** Last run, per-DB size, verify result, commit
   SHA. Visible to an operator *before* they go to the console for a full
   restore. This is the panel that earns its place first.
2. **Scoped restore.** Dump picker + the six Danger Zone checkboxes + preflight
   summary + confirm phrase. Sits next to `DangerZone.jsx` and reads as its
   counterpart.

## Deliberately not built

- **WAL archiving / PITR.** Takes RPO from 24h to minutes, but costs a
  `postgresql.conf` change and service restart, an archive directory that grows
  and needs its own pruning, and a materially more complex restore. On a single
  internet-restricted box during a pilot, losing a day of chat history does not
  justify that. Additive later — starting with dumps paints us into no corner.
  Revisit if the org states an RPO under 24h.
- **A download-dump button.** The file contains the OpenRouter key and
  federation API keys. Moving it through a browser turns a server-side secret
  into whatever is in someone's Downloads folder.
- **Arbitrary table-level restore.** Looks like a natural generalisation of the
  scoped restore and is not. The six scopes are safe *precisely because* their
  FK ordering has been worked out. An arbitrary table picker has no such
  guarantee and will eventually be pointed at `messages` without `chats`.

---

## Open question — off-box copy (BLOCKING for real DR)

Everything above protects against `DROP TABLE`, a bad migration, and the Danger
Zone. **It protects against nothing if the VM is lost**, because the dumps sit
on the same box.

Getting files off the box needs one of: a second volume, a UNC share the server
can reach, or an org backup agent already sweeping a directory. All three are
outside this repo and unknown on the target. **Needs an answer from whoever
owns the server.** Until then, Phases 1–3 are still worth having — they cover
the likely failures — but the regime is not disaster recovery.

---

## What this plan got wrong (found while implementing Phases 1-3, 2026-08-14)

Three corrections, all now reflected in the scripts and the runbook. The first
one invalidated the central claim of Phase 2.

### 1. `pg_restore --list` does NOT catch truncation

Phase 2 above says `--list` "catches truncation and half-written files from a
mid-dump reboot - the failure mode where the file looks fine by size and is
worthless." **It does not.** In a custom-format archive the table of contents is
written *ahead* of the data, and `--list` reads only the TOC. Measured on the
dev machine: `lexchat.dump` truncated to exactly half its length listed **all
172 TOC entries and exited 0**. The one failure mode the whole phase exists to
prevent would have sailed through the check designed to catch it.

Verification is therefore **two-stage**:

| Stage | Command | Catches |
|---|---|---|
| 1 | `pg_restore --list` | missing or header-corrupt archive; gives the TOC count for the manifest |
| 2 | `pg_restore -f NUL` | **truncation and data-block corruption** - converts the whole archive to SQL and discards it, forcing every block to be read and decompressed |

Stage 2 costs **1.7s for the 157 MB parliament dump** (it emits 724 MB of SQL to
`NUL`), so it runs on every database every night. `restore_database.ps1` runs the
same two stages *before* it drops anything.

### 2. `pg_dumpall --globals-only` requires superuser; `lexuser` is not one

Phase 1 calls for `pg_dumpall --globals-only` without noting that it reads
`pg_authid` for the password hashes, which needs superuser rights. `lexuser` is
`NOSUPERUSER CREATEDB`, so the command fails outright:

```
pg_dumpall: error: query failed: ERROR:  permission denied for table pg_authid
```

The script now tries the full dump first and falls back to
`--no-role-passwords`, recording which variant it got in
`manifest.json` (`"globals": {"mode": "no-role-passwords"}`). Role *definitions*
are captured; passwords are not. Consequence, documented in the runbook: a
restore into a **fresh cluster** needs `ALTER ROLE lexuser WITH PASSWORD ...`
by hand. Restores into the existing cluster are unaffected, since the role is
already there.

### 3. The restore procedure cannot start with `stop_native.cmd`

Phase 3 step 1 says `stop_native.cmd`, step 3 then runs `dropdb`/`pg_restore`.
But `stop_native.cmd` step 4 of 4 stops the `postgresql-x64-18` service - so the
restore would have no server to connect to. `restore_database.ps1` instead stops
the *app* only (the autostart task, nginx, the uvicorn process) and explicitly
ensures the PostgreSQL service is running.

### Also worth recording

- **`pg_restore --list` output has no stable exit-code signal for an empty
  archive**, so the script also fails a dump whose TOC entry count is zero.
- **PowerShell 5.1 gotchas** that cost time and are pinned by comments in the
  scripts: (a) a BOM-less `.ps1` is read as ANSI, so a UTF-8 em dash decodes to a
  smart quote that silently terminates a string literal - **these three scripts
  are deliberately ASCII-only**; (b) under `$ErrorActionPreference = "Stop"`, a
  native command's redirected stderr becomes a *terminating* error, which killed
  the run before the `--no-role-passwords` fallback could be tried (hence the
  `Invoke-Native` helper).
- **Backups live at `C:\LexChatBackups`, outside the repo**, so no git operation
  can touch them.

---

## What Part B got wrong (found while implementing Phases 4-6, 2026-08-14)

Four corrections. The first removes a scope from the restore UI entirely; the
second is a bug the plan's own worked example would have produced.

### 4. The `cache` scope can never be restored - Part B offers six, there are five

Part B says the restore UI should mirror the Danger Zone with "the same six
scopes". It can, but one of them is permanently empty: Phase 1 dumps with
`--exclude-table-data=local_prompt_cache`, so **no dump contains a single cached
summary**. Confirmed against the TOC - `local_prompt_cache` has a `TABLE` entry
and no `TABLE DATA` entry.

Restoring `cache` was therefore never going to do anything, and a bare `0` in the
preflight would read as a bug. The component is marked unavailable with the
reason stated, and the checkbox is disabled. **The exclusion list is read from
`manifest.json` (`excluded_table_data`), not hardcoded**, so if the backup script's
exclusions ever change the UI follows without an edit. Nothing is lost: the table
is pure cache and refills on demand.

### 5. `CAST(:p AS integer)` does not work - asyncpg types the parameter from the cast

Values are copied staging -> live as **text** and cast back to the live column's
type, which sidesteps driver type-mapping for json, timestamps, booleans and
floats in one move. The obvious spelling fails:

```
invalid input for query argument $1: '10' ('str' object cannot be interpreted as an integer)
```

asyncpg infers each bind parameter's type from the expression around it, so
`CAST($1 AS integer)` makes it *expect a Python int* and reject the text being
sent deliberately. It has to be `CAST(CAST($1 AS text) AS integer)` - the inner
cast pins the parameter as text and leaves the conversion to PostgreSQL. Pinned
by `test_text_cast_is_nested`.

### 6. 4b's UPDATE needs a tighter predicate than the plan's, or it lies on a re-run

Part B's worked example is:

```sql
WHERE m.id = s.id AND (s.rating IS NOT NULL OR s.feedback_comment IS NOT NULL)
```

That restores correctly, but combined with the additive rule (never overwrite a
value that survived) the natural candidate test - *live has a NULL in either
column* - is wrong. A rating with no comment leaves `feedback_comment`
legitimately NULL **forever**, so the row stays a candidate on every subsequent
run and each one reports it as restored again having changed nothing. Measured:
a second identical restore reported 3 rows applied with the database unchanged.

The predicate has to be per column and directional: apply only where the dump
has a value **and** live has none. Caught by re-running the restore in the
harness, not by reasoning about it - which is the argument for stage 7 existing.

### Also worth recording

- **Staging only the tables the selected scopes need** (`pg_restore -t`) is not
  just an optimisation. Staging the whole parliament dump takes **33s**; staging
  the nine app tables out of it takes **0.13s**. It also means the crawled SP
  corpus is never copied about. The tables arrive with **no indexes, primary keys
  or foreign keys** (those are separate TOC entries whose tags do not match a
  `-t` pattern), which is exactly right for a read-only source and means nothing
  in staging depends on insert order.
- **A dump may not contain a table at all.** `session_feedback` does not exist in
  `lexchat_parliament` - that database predates it. Components resolve per table
  against what actually landed and report "does not exist in this backup"
  instead of failing the run.
- **`postgres_fdw` / `dblink` are not available.** Both need `CREATE EXTENSION`,
  which needs superuser, and `lexuser` is `NOSUPERUSER` - the same constraint
  that broke `pg_dumpall` in Phase 1. The staging -> live copy is therefore done
  in Python. Fine at this size (app tables only), but it does mean the restore
  holds a table in memory; the irreplaceable tier is ~25 MB by design.
- **The asyncio lock is not enough on its own.** It is per-process, so a
  deployment running more than one uvicorn worker would have one lock per worker
  and no mutual exclusion - two runs would drop each other's staging database
  mid-copy. A cluster-wide `pg_try_advisory_lock` was added alongside it.
- **The `chats` scope masks the 4b trap.** When `chats` and `feedback` are
  restored together the message rows are re-INSERTed *carrying their rating
  columns*, so ratings come back via the INSERT and a broken UPDATE component
  goes unnoticed. Only a `feedback`-only restore exercises the real case. The
  first version of the harness tested the combined case and would have passed
  with the bug present.

---

## Session ledger

| Phase | Status | Notes |
|---|---|---|
| 1. `backup_databases.ps1` + manifest | **DONE** 2026-08-14 | Enumerated targets, `-Fc`, `local_prompt_cache` rows excluded, manifest with commit SHA |
| 2. Verify / retention / scheduled task | **DONE** 2026-08-14 | Two-stage verify (see corrections above), GFS 14/8/12, `install_backup_task.ps1` |
| 3. `restore_database.ps1` + runbook + rehearsal | **DONE** 2026-08-14 | Rehearsed - see below. Runbook: `docs/deployment/BACKUP_RUNBOOK.md` |
| 4. Scoped restore backend | **DONE** 2026-08-14 | `services/backup_restore.py`. Exercised end to end - see below |
| 5. Guard rails + endpoints | **DONE** 2026-08-14 | 3 endpoints on `admin_router`, auto-backup, preflight, `RESTORE` phrase, `activity_log` |
| 6. Developer tab UI | **DONE** 2026-08-14 | `BackupStatus.jsx` (read-only) + `ScopedRestore.jsx` (next to `DangerZone.jsx`) |
| Off-box copy | BLOCKED | Awaiting answer on available destinations (D15) |

**Still not run anywhere: `install_backup_task.ps1`.** It needs an elevated
session on the target, so despite Phases 1-6 being complete **no backup is
actually running on any machine yet**. Until that is run there is nothing for the
restore UI to restore from, and the Developer tab will say so.

### Scoped-restore verification record - 2026-08-14, dev machine

`server_py/tests/manual/e2e_scoped_restore.py` (10 stages, **67 assertions, all
passing**) against a scratch `lexchat_e2e`, driving the real code both ways: a
real `backup_databases.ps1` run, then `developer.clear_data()` for the loss and
`backup_restore.run_restore()` for the recovery. Plus
`tests/test_backup_restore.py` (28 tests) in the unit suite, and an HTTP-level
pass through the three endpoints with a real admin JWT.

What the run actually proved, beyond row counts:

| | Result |
|---|---|
| Pilot reset (all six scopes) cleared and restored | chats 5, messages 10, documents 3, surveys 2, session feedback 3, timings 3, activity 3, health 3 - all back |
| **Message ratings after a `feedback`-only restore (4b)** | **4 of 4, values and comments exact** - including a comment-with-no-rating row |
| matter_note message links repaired (4f) | 3 of 3, after the clear severed all 3 |
| Sequences (4d) | all 8 restored tables advanced past `max(id)`; a real post-restore INSERT succeeded |
| Re-run (4c) | second identical restore applied **0** rows and changed nothing |
| Stale FK parents (4e) | user deleted -> its chat skipped and reported, its 2 messages skipped with it; matter deleted -> chat kept with `matter_id` nulled |
| `cache` scope | reported unavailable with the reason, never silently 0 |
| Type fidelity | `json` (`sources`, `research_plan`, `filters`), `float8`, `bool` and `timestamp` all exact after the text round trip |
| Exclusivity | a second caller holding the advisory lock is refused; released, it succeeds |
| Hygiene | staging database dropped, safety dump written, `RESTORE` row on the activity log |

Two bugs were found by running it rather than by reading it - the asyncpg cast
typing and the re-run over-reporting, both recorded above. A third finding is
about the *test*: the all-six-scopes scenario masks the 4b trap entirely, so the
`feedback`-only stage had to be added separately.

### Rehearsal record - 2026-08-14, dev machine, PostgreSQL 18.3

Both restores went into `lexchat_restore_test` and were compared against the
live database with exact per-table counts (`query_to_xml`, not `n_live_tup` -
the estimate reads 0 until `ANALYZE` and would have made the comparison
meaningless).

| | `lexchat` | `lexchat_parliament` |
|---|---|---|
| Dump size | 128 KB | 157 MB |
| Restore time | 0.3s | 32.8s |
| pg_restore errors | 0 | 0 |
| Tables matching live | 16 of 16 | 15 of 15 |
| `local_prompt_cache` | 44 -> 0, as designed | 14 -> 0, as designed |

The parliament corpus came back complete: 2,423 `sp_committee_items`, 3,763
`sp_plenary_items`, 1,177 `sp_video_captions`. Row counts alone would not have
proved the corpus is *usable*, so the restored database was also checked for
schema objects and retrieval behaviour: **59 indexes, 3 GIN indexes and 144
constraints in both**, and the same FTS query (`plainto_tsquery('english',
'homeless')` over `sp_plenary_items.full_text`) returned **314 rows in both**.

Failure paths were exercised deliberately, not just reasoned about:

- **Bad credentials** - run aborts, exit 1, loud summary, no partial run
  directory left behind.
- **Verify failure** - forced with a stand-in `pg_restore.exe` that always
  fails. All four dumps were renamed to `*.dump.corrupt`, a `FAILED` marker was
  written, `manifest.json` recorded `"status": "FAILED"`, and the script exited
  1. Nothing usable-looking was left in place.
- **Retention** - run against 62 synthetic dated run directories (45 daily + 18
  monthly, 3 marked FAILED). Kept 31: the 14 most recent *successful* runs, the
  weekly and monthly representatives, and the 3 failed runs (within their 14-day
  investigation window, and correctly **not** occupying a weekly or monthly
  slot). Deleted 31, all older than the 12-month horizon.

Not yet exercised on the dev machine, because it needs an elevated session on
the real target: `install_backup_task.ps1` (the ACL tightening, event log source
registration and task registration). The Application event log write is
fail-soft by design and was observed degrading correctly when unprivileged.
