# Manual test harnesses

Scripts here are **not** collected by pytest. They need things the unit suite
deliberately does not have: a live PostgreSQL cluster with `CREATEDB` rights, the
PostgreSQL client binaries, and in one case a real run of a deployment
PowerShell script. Run them by hand when changing the code they cover.

## `e2e_scoped_restore.py` — Developer-tab scoped restore (D14 Phases 4-5)

```powershell
python server_py\tests\manual\e2e_scoped_restore.py
```

Builds a scratch database (`lexchat_e2e`, dropped and recreated on each run —
**it never touches `lexchat`**), seeds it with data that exercises every awkward
column type, then drives the real code paths end to end:

1. `deployment/backup_databases.ps1` for a genuine nightly backup run
   (`lexchat_e2e` is picked up automatically because the script enumerates
   `lexchat%` rather than hardcoding a list);
2. `routers/developer.clear_data()` — the real Danger Zone — for the loss;
3. `services/backup_restore.run_restore()` for the recovery, both dry-run and real.

Ten stages, 67 assertions. What it is actually for:

- **Stage 8b is the reason this file exists.** Clearing `feedback` on its own
  leaves the message rows in place with `rating = NULL`, so an
  `INSERT ... ON CONFLICT (id) DO NOTHING` conflicts on all of them and restores
  **no ratings at all while reporting success**. Stage 8b proves the UPDATE path
  puts them back. Note that the all-six-scopes run in stage 5 **masks** this: with
  `chats` also selected the messages are re-inserted carrying their rating
  columns, so ratings return via the INSERT and a broken UPDATE would go
  unnoticed. Both scenarios are needed.
- Stage 6 proves the identity sequences were reset (4d) by doing a real INSERT.
- Stage 7 proves the restore is additive and re-runnable (4c), and that a second
  run reports zero applied rather than phantom updates.
- Stage 9 deletes a user and a matter by hand to exercise the stale-FK rules (4e).
- Stage 8 pins that the `cache` scope can never be restored, because
  `local_prompt_cache` rows are excluded from every dump.

It leaves `lexchat_e2e` in place for inspection. Drop it when you are done:

```powershell
psql -U lexuser -h localhost -d postgres -c "DROP DATABASE lexchat_e2e;"
```

Backups are written to `C:\Temp\BackupsDev`, not the real backup root.
