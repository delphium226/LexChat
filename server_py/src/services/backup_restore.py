"""Two-stage scoped restore from a nightly dump (D14 Phases 4-5).

The realistic disaster on this system is the Danger Zone, not disk failure:
somebody runs a pilot reset and then wants last night's session feedback back.
So the restore offered here is *scope-shaped*, mirroring
`routers/developer.py:DATA_SCOPES` exactly - it is the inverse of the operation
that caused the loss. A whole-database restore stays a console operation
(`deployment/restore_database.ps1`); see docs/BACKUP_RESTORE_PLAN.md Part A
Phase 3 for why that one must never be a button.

TWO STAGES, and the separation is the whole safety property:

  1. `pg_restore` the chosen dump into `lexchat_restore_staging`, a database the
     app never connects to. Live tables are never a pg_restore target.
  2. Copy staging -> live row by row, additively, scope by scope.

Only the tables the selected scopes actually need are staged (`pg_restore -t`).
That is not just an optimisation: measured on the dev machine, staging the
whole 157 MB parliament dump takes 33s, while staging the nine app tables out
of it takes 0.13s. It also means the crawled SP corpus is never copied about.

Cross-database copying is done in Python rather than SQL because `postgres_fdw`
and `dblink` both need `CREATE EXTENSION`, which needs superuser - and `lexuser`
is deliberately `NOSUPERUSER`. Volumes here are app tables only (~11 MB for
`lexchat`), so the round trip is cheap.

Every value crosses the gap as **text**, cast back to the live column's own type
on insert. That sidesteps driver type-mapping entirely (json, timestamps,
arrays, floats) at the cost of a conversion that is irrelevant at this size.
The cast has to be written `CAST(CAST(:p AS text) AS <type>)` and not the
obvious single `CAST(:p AS <type>)`: asyncpg infers each parameter's type from
the expression around it, so a single cast makes it expect a real int/bool/
timestamp and reject the text we are deliberately sending
(`invalid input for query argument $1: '10'`). The inner cast pins the
parameter as text and lets PostgreSQL do the conversion.

The four correctness details from the plan, and where they live:

  4a. Ordering is the reverse of `_CLEAR_ORDER`   -> `RESTORE_ORDER`
  4b. `feedback` is a mixed DELETE/UPDATE          -> `_OP_UPDATE` component
  4c. Additive only, never overwrite               -> `ON CONFLICT (id) DO NOTHING`
  4d. Reset the sequences afterwards               -> `_reset_sequence`
  4e. Stale FK references                          -> `_FK_RULES`
  4f. `matter_notes.message_id` is severed         -> `_OP_RELINK` component
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Optional
from urllib.parse import unquote, urlparse

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from ..config import settings

logger = logging.getLogger("app")

# The staging database. Never in DATABASE_URL, never connected to by the app,
# dropped again at the end of every operation.
STAGING_DB = "lexchat_restore_staging"

# Run directories written by deployment/backup_databases.ps1.
_RUN_DIR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}$")

# asyncpg refuses a statement with more than 32767 bind parameters. Batches are
# sized from the column count so a 40-column table (request_timings) cannot trip it.
_MAX_BIND_PARAMS = 30000
_MAX_BATCH_ROWS = 500

# Only one restore or preflight at a time: they share one staging database, and
# two concurrent runs would drop it out from under each other mid-copy.
#
# TWO guards, because the asyncio lock alone is per-process: a deployment running
# more than one uvicorn worker would have one lock per worker and no mutual
# exclusion at all. The PostgreSQL advisory lock is cluster-wide, so it holds
# across workers (and across a second bot pointed at the same cluster). The
# asyncio lock is kept as well so the common in-process case queues politely
# instead of failing.
_restore_lock = asyncio.Lock()

# Arbitrary but fixed: any two callers must pick the same key for the lock to mean
# anything. Advisory locks live in their own namespace and collide with nothing.
_ADVISORY_LOCK_KEY = 8_140_014


class RestoreError(Exception):
    """Anything that should surface to the operator as a 400/500 with a reason."""


# ---------------------------------------------------------------------------
# Scope -> component map
# ---------------------------------------------------------------------------

_OP_INSERT = "insert"
_OP_UPDATE = "update"
_OP_RELINK = "relink"


@dataclass(frozen=True)
class Component:
    """One table-shaped piece of work inside a scope.

    A scope is not one table and not one operation: `chats` restores three
    tables and then repairs a fourth, and `feedback` inserts two tables and
    UPDATEs a third. Components make that explicit instead of hiding it in a
    branch, and give the preflight something honest to count per line.
    """

    key: str
    table: str
    operation: str
    label: str
    note: str = ""


# Fixed execution order per scope. Within `chats`: chats -> messages ->
# documents, parents before children.
SCOPE_COMPONENTS: dict[str, list[Component]] = {
    "cache": [
        Component("cache.local_prompt_cache", "local_prompt_cache", _OP_INSERT, "Cached summaries"),
    ],
    "health": [
        Component("health.service_health_logs", "service_health_logs", _OP_INSERT, "Service health records"),
    ],
    "activity": [
        Component("activity.activity_log", "activity_log", _OP_INSERT, "Activity log entries"),
    ],
    "performance": [
        Component("performance.request_timings", "request_timings", _OP_INSERT, "Request timings"),
    ],
    "chats": [
        Component("chats.chats", "chats", _OP_INSERT, "Chats"),
        Component("chats.messages", "messages", _OP_INSERT, "Messages"),
        Component("chats.documents", "documents", _OP_INSERT, "Uploaded documents"),
        Component(
            "chats.matter_notes", "matter_notes", _OP_RELINK, "Matter-note message links",
            note="matter_notes is in no clear scope, but clearing chats severs its "
                 "message_id links (ON DELETE SET NULL). Re-linked here by note id.",
        ),
    ],
    "feedback": [
        Component("feedback.product_feedback", "product_feedback", _OP_INSERT, "Weekly surveys"),
        Component("feedback.session_feedback", "session_feedback", _OP_INSERT, "End-of-session feedback"),
        Component(
            "feedback.messages", "messages", _OP_UPDATE, "Message ratings",
            note="Ratings are nulled in place by a clear, not deleted - the message "
                 "rows survive. An INSERT would conflict on every id and restore "
                 "nothing, so this component is an UPDATE.",
        ),
    ],
}

# The plain reversal of developer.py's _CLEAR_ORDER. The clear runs `feedback`
# before `chats` because session_feedback.chat_id is ON DELETE SET NULL and
# clearing chats first would orphan it; the restore has the mirror-image
# constraint (parents first), so `chats` must land BEFORE `feedback`.
RESTORE_ORDER = ["cache", "health", "activity", "performance", "chats", "feedback"]

# 4e. Stale FK references. `parent_table` is checked in LIVE, because that is
# where the row is about to land. A NOT NULL reference whose parent is missing
# means the row cannot be restored at all (skipped and reported); a nullable one
# is simply nulled, which is exactly what ON DELETE SET NULL would have done.
_FK_RULES: dict[str, list[tuple[str, str, bool]]] = {
    # table: [(column, parent_table, nullable)]
    "chats": [("user_id", "users", False), ("matter_id", "matters", True)],
    "messages": [("chat_id", "chats", False)],
    "documents": [("chat_id", "chats", False), ("user_id", "users", False)],
    "product_feedback": [("user_id", "users", False)],
    "session_feedback": [("user_id", "users", False), ("chat_id", "chats", True)],
}

# Columns the UPDATE component carries across, and the rule that keeps it
# additive: a value that survived in live is never overwritten.
_RATING_COLUMNS = ("rating", "feedback_comment")


def scope_components(scopes: Iterable[str]) -> list[tuple[str, Component]]:
    """(scope, component) pairs for the selected scopes, in restore order."""
    selected = set(scopes)
    out: list[tuple[str, Component]] = []
    for scope in RESTORE_ORDER:
        if scope in selected:
            for comp in SCOPE_COMPONENTS[scope]:
                out.append((scope, comp))
    return out


def _tables_for(scopes: Iterable[str]) -> list[str]:
    """Every table that must be staged for these scopes (deduped, order kept)."""
    seen: list[str] = []
    for _scope, comp in scope_components(scopes):
        if comp.table not in seen:
            seen.append(comp.table)
    return seen


# ---------------------------------------------------------------------------
# Connection settings / tooling
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PgTarget:
    host: str
    port: str
    user: str
    password: str
    database: str


def get_pg_target() -> PgTarget:
    """Parse the app's own DATABASE_URL. The restore holds no credentials of its own."""
    url = urlparse(settings.database_url.replace("postgresql+asyncpg://", "postgresql://"))
    return PgTarget(
        host=url.hostname or "localhost",
        port=str(url.port or 5432),
        user=unquote(url.username or "lexuser"),
        password=unquote(url.password or ""),
        database=(url.path or "/").lstrip("/") or "lexchat",
    )


def resolve_pg_bin() -> str:
    """Locate the PostgreSQL bin directory holding pg_restore.exe / pg_dump.exe.

    Mirrors Resolve-PgBin in the deployment scripts: explicit setting, then the
    highest installed version under Program Files, then PATH.
    """
    if settings.pg_bin:
        if not os.path.isfile(os.path.join(settings.pg_bin, _exe("pg_restore"))):
            raise RestoreError(f"PG_BIN is set to {settings.pg_bin!r} but pg_restore is not there.")
        return settings.pg_bin

    root = r"C:\Program Files\PostgreSQL"
    if os.path.isdir(root):
        versions = []
        for name in os.listdir(root):
            candidate = os.path.join(root, name, "bin")
            if os.path.isfile(os.path.join(candidate, _exe("pg_restore"))):
                digits = re.sub(r"\D", "", name) or "0"
                versions.append((int(digits), candidate))
        if versions:
            return max(versions)[1]

    found = shutil.which("pg_restore")
    if found:
        return os.path.dirname(found)

    raise RestoreError(
        "Could not locate the PostgreSQL bin directory. Set PG_BIN in server_py/.env."
    )


def _exe(name: str) -> str:
    return f"{name}.exe" if os.name == "nt" else name


def _run_tool(exe_path: str, args: list[str], password: str, timeout: int = 900) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PGPASSWORD"] = password
    return subprocess.run(
        [exe_path, *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
        # Never pop a console window when uvicorn runs as a service.
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


# ---------------------------------------------------------------------------
# Backup discovery
# ---------------------------------------------------------------------------

def list_runs(database: Optional[str] = None) -> dict:
    """Enumerate backup runs under settings.backup_root, newest first.

    Reads manifest.json where present. A run directory containing a FAILED
    marker is reported but flagged, and is never restorable.
    """
    target_db = database or get_pg_target().database
    root = settings.backup_root
    runs: list[dict] = []

    if os.path.isdir(root):
        for name in sorted(os.listdir(root), reverse=True):
            if not _RUN_DIR_RE.match(name):
                continue
            run_dir = os.path.join(root, name)
            if not os.path.isdir(run_dir):
                continue

            failed_marker = os.path.isfile(os.path.join(run_dir, "FAILED"))
            manifest: dict = {}
            manifest_path = os.path.join(run_dir, "manifest.json")
            if os.path.isfile(manifest_path):
                try:
                    with open(manifest_path, "r", encoding="utf-8") as fh:
                        manifest = json.load(fh)
                except (OSError, ValueError) as exc:
                    logger.warning(f"[Restore] Unreadable manifest in {name}: {exc}")

            databases = manifest.get("databases") or []
            this_db = next((d for d in databases if d.get("name") == target_db), None)

            dump_path = os.path.join(run_dir, f"{target_db}.dump")
            has_dump = os.path.isfile(dump_path)

            runs.append({
                "id": name,
                "status": manifest.get("status") or ("FAILED" if failed_marker else "unknown"),
                "failed": failed_marker or manifest.get("status") not in (None, "ok"),
                "started_at": manifest.get("started_at"),
                "finished_at": manifest.get("finished_at"),
                "duration_s": manifest.get("duration_s"),
                "commit_sha": manifest.get("commit_sha"),
                "pg_version": manifest.get("pg_version"),
                "host": manifest.get("host"),
                "globals_mode": (manifest.get("globals") or {}).get("mode"),
                "excluded_table_data": manifest.get("excluded_table_data") or [],
                "total_bytes": manifest.get("total_bytes"),
                "databases": [
                    {
                        "name": d.get("name"),
                        "bytes": d.get("bytes"),
                        "verify": d.get("verify"),
                        "toc_entries": d.get("toc_entries"),
                        "duration_s": d.get("duration_s"),
                        "error": d.get("error"),
                    }
                    for d in databases
                ],
                "errors": manifest.get("errors") or [],
                # Everything below is about THIS bot's database specifically.
                "has_dump": has_dump,
                "dump_bytes": (os.path.getsize(dump_path) if has_dump else None),
                "database_verify": (this_db or {}).get("verify"),
                "restorable": bool(
                    has_dump
                    and not failed_marker
                    and (this_db or {}).get("verify", "ok") == "ok"
                ),
            })

    return {
        "backup_root": root,
        "root_exists": os.path.isdir(root),
        "database": target_db,
        "runs": runs,
        "latest": runs[0] if runs else None,
        "latest_ok": next((r for r in runs if r["restorable"]), None),
    }


def _resolve_run(run_id: str, database: str) -> dict:
    if not _RUN_DIR_RE.match(run_id or ""):
        raise RestoreError(f"Not a backup run id: {run_id!r}")
    listing = list_runs(database)
    run = next((r for r in listing["runs"] if r["id"] == run_id), None)
    if not run:
        raise RestoreError(f"No backup run {run_id!r} under {listing['backup_root']}.")
    if not run["has_dump"]:
        raise RestoreError(f"Backup run {run_id} holds no dump for database {database!r}.")
    if run["failed"]:
        raise RestoreError(f"Backup run {run_id} was marked FAILED and cannot be restored from.")
    if run.get("database_verify") not in (None, "ok"):
        raise RestoreError(
            f"{database} did not verify at backup time in run {run_id} "
            f"({run['database_verify']}). Use an older run."
        )
    run["dump_file"] = os.path.join(settings.backup_root, run_id, f"{database}.dump")
    return run


# ---------------------------------------------------------------------------
# Staging
# ---------------------------------------------------------------------------

async def _admin_exec(target: PgTarget, sql: str) -> None:
    """Run a statement against the `postgres` database in autocommit.

    CREATE/DROP DATABASE cannot run inside a transaction block.
    """
    url = (
        f"postgresql+asyncpg://{target.user}:{target.password}"
        f"@{target.host}:{target.port}/postgres"
    )
    engine = create_async_engine(url, poolclass=NullPool, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as conn:
            await conn.execute(text(sql))
    finally:
        await engine.dispose()


async def _drop_staging(target: PgTarget) -> None:
    await _admin_exec(
        target,
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        f"WHERE datname = '{STAGING_DB}' AND pid <> pg_backend_pid()",
    )
    await _admin_exec(target, f'DROP DATABASE IF EXISTS "{STAGING_DB}"')


def _verify_dump(pg_bin: str, dump_file: str, password: str) -> None:
    """Two-stage verification, exactly as the deployment scripts do it.

    `pg_restore --list` reads only the table of contents, which in a
    custom-format archive sits AHEAD of the data - a dump truncated to half its
    length still lists every entry and exits 0 (measured: 172 of 172). It
    catches a missing or header-corrupt file and nothing else.

    `pg_restore -f NUL` converts the whole archive to SQL and throws it away,
    forcing every data block to be read and decompressed. That is the stage that
    actually catches truncation, and it costs ~1.7s for the 157 MB dump.
    """
    pg_restore = os.path.join(pg_bin, _exe("pg_restore"))

    listed = _run_tool(pg_restore, ["--list", dump_file], password)
    toc_entries = len([ln for ln in listed.stdout.splitlines() if re.match(r"^\d+;", ln)])
    if listed.returncode != 0:
        raise RestoreError(f"Dump failed pg_restore --list: {(listed.stderr or '').strip()[:400]}")
    if toc_entries == 0:
        raise RestoreError("Dump listed successfully but contains no TOC entries.")

    devnull = "NUL" if os.name == "nt" else "/dev/null"
    deep = _run_tool(pg_restore, ["-f", devnull, dump_file], password)
    if deep.returncode != 0:
        raise RestoreError(
            "Dump is corrupt: it lists correctly but cannot be read in full "
            f"({(deep.stderr or '').strip()[:400]}). Use an older run."
        )


async def _stage(target: PgTarget, pg_bin: str, dump_file: str, tables: list[str]) -> list[str]:
    """Drop, recreate and populate the staging database. Returns the tables that landed.

    Only the tables the selected scopes need are restored. With `-t`, pg_restore
    matches TOC tags, so the tables arrive with their column definitions and data
    but WITHOUT indexes, primary keys or foreign keys - which is exactly right
    for a read-only source, and means nothing here depends on insert order.
    """
    await _drop_staging(target)
    await _admin_exec(target, f'CREATE DATABASE "{STAGING_DB}" OWNER "{target.user}"')

    args = [
        "-U", target.user, "-h", target.host, "-p", target.port,
        "-d", STAGING_DB, "--no-owner", "--no-privileges",
    ]
    for table in tables:
        args += ["-t", table]
    args.append(dump_file)

    result = _run_tool(os.path.join(pg_bin, _exe("pg_restore")), args, target.password)

    landed = await _staging_tables(target)
    if not landed:
        raise RestoreError(
            "Staging restore produced no tables. pg_restore said: "
            f"{(result.stderr or result.stdout or '').strip()[:400]}"
        )
    if result.returncode != 0:
        # Partial is survivable - a table absent from an older dump is reported
        # per component rather than failing the whole operation.
        logger.warning(
            f"[Restore] pg_restore exited {result.returncode} staging {len(landed)} table(s): "
            f"{(result.stderr or '').strip()[:400]}"
        )
    return landed


async def _staging_tables(target: PgTarget) -> list[str]:
    async with _staging_engine(target).connect() as conn:
        rows = await conn.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
        ))
        return [r[0] for r in rows]


def _staging_engine(target: PgTarget):
    url = (
        f"postgresql+asyncpg://{target.user}:{target.password}"
        f"@{target.host}:{target.port}/{STAGING_DB}"
    )
    return create_async_engine(url, poolclass=NullPool)


# ---------------------------------------------------------------------------
# Column introspection
# ---------------------------------------------------------------------------

_COLUMN_SQL = """
SELECT a.attname, format_type(a.atttypid, a.atttypmod)
FROM pg_attribute a
JOIN pg_class c ON c.oid = a.attrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relname = :table
  AND a.attnum > 0 AND NOT a.attisdropped
ORDER BY a.attnum
"""


async def _columns(conn, table: str) -> dict[str, str]:
    rows = await conn.execute(text(_COLUMN_SQL), {"table": table})
    return {r[0]: r[1] for r in rows}


def _shared_columns(staging: dict[str, str], live: dict[str, str]) -> tuple[list[str], list[str]]:
    """Columns present in both, plus the ones only live has (reported, not fatal).

    An older dump onto newer code is an explicitly supported case - startup
    re-applies the additive ADD COLUMN migrations - so a column the dump predates
    simply takes its default. Copying only the intersection is what makes that work.
    """
    shared = [c for c in live if c in staging]
    live_only = [c for c in live if c not in staging]
    return shared, live_only


# ---------------------------------------------------------------------------
# The copy
# ---------------------------------------------------------------------------

@dataclass
class ComponentResult:
    key: str
    scope: str
    table: str
    operation: str
    label: str
    available: bool = True
    staging_rows: int = 0
    live_rows: int = 0
    would_apply: int = 0
    applied: int = 0
    already_present: int = 0
    skipped_missing_parent: int = 0
    nulled_references: int = 0
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "key": self.key,
            "scope": self.scope,
            "table": self.table,
            "operation": self.operation,
            "label": self.label,
            "available": self.available,
            "staging_rows": self.staging_rows,
            "live_rows": self.live_rows,
            "would_apply": self.would_apply,
            "applied": self.applied,
            "already_present": self.already_present,
            "skipped_missing_parent": self.skipped_missing_parent,
            "nulled_references": self.nulled_references,
            "notes": self.notes,
        }


def _text_cast(param: str, pg_type: str) -> str:
    """`CAST(CAST(:p AS text) AS <type>)` - and the nesting is load-bearing.

    asyncpg resolves each bind parameter's type from the expression it sits in,
    so a bare `CAST(:p AS integer)` makes it expect a Python int and reject the
    text this module deliberately sends ("invalid input for query argument $1:
    '10' ('str' object cannot be interpreted as an integer)"). Casting to text
    first pins the parameter as text and leaves the real conversion to
    PostgreSQL, which is the whole point of moving values across as text.
    """
    return f"CAST(CAST(:{param} AS text) AS {pg_type})"


async def _existing_ids(conn, table: str, ids: list[int]) -> set[int]:
    """Which of these ids already exist in the live table."""
    if not ids:
        return set()
    found: set[int] = set()
    for i in range(0, len(ids), 20000):
        chunk = ids[i:i + 20000]
        rows = await conn.execute(
            text(f'SELECT id FROM public."{table}" WHERE id = ANY(:ids)'), {"ids": chunk}
        )
        found.update(int(r[0]) for r in rows)
    return found


async def _parent_ids(conn, parent_table: str) -> set[int]:
    rows = await conn.execute(text(f'SELECT id FROM public."{parent_table}"'))
    return {int(r[0]) for r in rows}


async def _fetch_staging_rows(sconn, table: str, columns: list[str]) -> list[dict[str, Any]]:
    """Read the whole table out of staging with every value rendered as text.

    Text is the one representation every PostgreSQL type round-trips through
    losslessly, and it keeps the asyncpg <-> SQLAlchemy type mapping out of the
    picture for json, timestamps, arrays and floats alike. `float8` output uses
    the shortest round-trip form in PG 12+, so numbers survive exactly.
    """
    select_list = ", ".join(f'"{c}"::text AS "{c}"' for c in columns)
    rows = await sconn.execute(text(f'SELECT {select_list} FROM public."{table}"'))
    return [dict(r._mapping) for r in rows]


async def _insert_component(
    lconn, sconn, comp: Component, result: ComponentResult, dry_run: bool,
) -> None:
    staging_cols = await _columns(sconn, comp.table)
    live_cols = await _columns(lconn, comp.table)
    columns, live_only = _shared_columns(staging_cols, live_cols)

    if "id" not in columns:
        result.available = False
        result.notes.append("No shared `id` column between the dump and the live table.")
        return
    if live_only:
        result.notes.append(
            "Columns absent from this (older) dump, left at their default: " + ", ".join(live_only)
        )

    rows = await _fetch_staging_rows(sconn, comp.table, columns)
    result.staging_rows = len(rows)
    result.live_rows = int(
        (await lconn.execute(text(f'SELECT count(*) FROM public."{comp.table}"'))).scalar() or 0
    )
    if not rows:
        return

    # 4c. Additive: anything already in live is left exactly as it is.
    ids = [int(r["id"]) for r in rows]
    present = await _existing_ids(lconn, comp.table, ids)

    # 4e. Stale FK references, resolved against LIVE.
    fk_rules = [r for r in _FK_RULES.get(comp.table, []) if r[0] in columns]
    parents = {p: await _parent_ids(lconn, p) for _c, p, _n in fk_rules}

    to_insert: list[dict[str, Any]] = []
    # Which parents actually caused a skip, so the note names those and not every
    # parent the table happens to have.
    blamed: set[str] = set()
    for row in rows:
        if int(row["id"]) in present:
            result.already_present += 1
            continue
        skip = False
        for column, parent, nullable in fk_rules:
            raw = row.get(column)
            if raw is None:
                continue
            if int(raw) in parents[parent]:
                continue
            if nullable:
                row[column] = None
                result.nulled_references += 1
            else:
                skip = True
                blamed.add(parent)
                break
        if skip:
            result.skipped_missing_parent += 1
            continue
        to_insert.append(row)

    result.would_apply = len(to_insert)
    if result.skipped_missing_parent:
        parents_named = " / ".join(sorted(blamed))
        result.notes.append(
            f"{result.skipped_missing_parent} row(s) cannot be restored: the "
            f"{parents_named} row they belong to no longer exists."
        )
    if result.nulled_references:
        result.notes.append(
            f"{result.nulled_references} optional reference(s) nulled because the parent is gone."
        )
    if dry_run or not to_insert:
        return

    col_sql = ", ".join(f'"{c}"' for c in columns)
    types = [live_cols[c] for c in columns]
    batch_rows = max(1, min(_MAX_BATCH_ROWS, _MAX_BIND_PARAMS // max(1, len(columns))))

    applied = 0
    for start in range(0, len(to_insert), batch_rows):
        batch = to_insert[start:start + batch_rows]
        values_sql = []
        params: dict[str, Any] = {}
        for r_idx, row in enumerate(batch):
            placeholders = []
            for c_idx, column in enumerate(columns):
                name = f"p{r_idx}_{c_idx}"
                params[name] = row[column]
                placeholders.append(_text_cast(name, types[c_idx]))
            values_sql.append("(" + ", ".join(placeholders) + ")")

        res = await lconn.execute(
            text(
                f'INSERT INTO public."{comp.table}" ({col_sql}) VALUES '
                + ", ".join(values_sql)
                + " ON CONFLICT (id) DO NOTHING RETURNING id"
            ),
            params,
        )
        applied += len(res.fetchall())

    result.applied = applied


async def _update_ratings(
    lconn, sconn, comp: Component, result: ComponentResult, dry_run: bool,
) -> None:
    """4b. The component that an INSERT would silently restore nothing for.

    Clearing the `feedback` scope runs
    `UPDATE messages SET rating = NULL, feedback_comment = NULL` - the message
    rows are still there. So every id from staging conflicts, ON CONFLICT DO
    NOTHING skips all of them, and the operation reports success having restored
    no ratings at all. It has to be an UPDATE keyed on the surviving row.

    Kept additive per column with COALESCE: a rating that survived in live is
    never overwritten by the dump's older value.
    """
    staging_cols = await _columns(sconn, comp.table)
    live_cols = await _columns(lconn, comp.table)
    columns = [c for c in _RATING_COLUMNS if c in staging_cols and c in live_cols]

    if not columns:
        result.available = False
        result.notes.append("Neither rating column is present in both the dump and the live table.")
        return

    predicate = " OR ".join(f'"{c}" IS NOT NULL' for c in columns)
    # Read as text for the same reason _fetch_staging_rows does, and because the
    # placeholders below are typed text - a real int here would be rejected.
    select_list = ", ".join(['id::text AS id'] + [f'"{c}"::text AS "{c}"' for c in columns])
    rows = await sconn.execute(text(
        f'SELECT {select_list} FROM public."{comp.table}" WHERE {predicate}'
    ))
    staged = [dict(r._mapping) for r in rows]
    result.staging_rows = len(staged)
    result.live_rows = int(
        (await lconn.execute(text(
            f'SELECT count(*) FROM public."{comp.table}" WHERE {predicate}'
        ))).scalar() or 0
    )
    if not staged:
        return

    # A row is a candidate only if the UPDATE would actually change something:
    # it still exists in live, and for at least one column the dump has a value
    # where live has none. The weaker test "live has a NULL in either column" is
    # wrong in a way that only shows on a re-run - a rating with no comment
    # leaves feedback_comment legitimately NULL forever, so it stays a candidate
    # and every re-run reports it as restored again having changed nothing.
    live_state: dict[int, dict[str, Any]] = {}
    ids = [int(r["id"]) for r in staged]
    col_list = ", ".join(f'"{c}"::text AS "{c}"' for c in columns)
    for i in range(0, len(ids), 20000):
        chunk = ids[i:i + 20000]
        found = await lconn.execute(
            text(f'SELECT id, {col_list} FROM public."{comp.table}" WHERE id = ANY(:ids)'),
            {"ids": chunk},
        )
        for row in found:
            mapping = dict(row._mapping)
            live_state[int(mapping["id"])] = mapping

    targets = []
    for row in staged:
        current = live_state.get(int(row["id"]))
        if current is None:
            continue
        if any(row[c] is not None and current[c] is None for c in columns):
            targets.append(row)
    result.already_present = len(staged) - len(targets)
    result.would_apply = len(targets)
    if result.already_present:
        gone = len([1 for r in staged if int(r["id"]) not in live_state])
        kept = result.already_present - gone
        parts = []
        if kept:
            parts.append(f"{kept} already carry their rating")
        if gone:
            parts.append(f"{gone} no longer exist")
        result.notes.append(
            f"{result.already_present} rated message(s) left untouched ({', '.join(parts)})."
        )
    if dry_run or not targets:
        return

    types = {c: live_cols[c] for c in columns}
    set_sql = ", ".join(f'"{c}" = COALESCE(m."{c}", s."{c}")' for c in columns)
    batch_rows = max(1, min(_MAX_BATCH_ROWS, _MAX_BIND_PARAMS // (len(columns) + 1)))

    applied = 0
    for start in range(0, len(targets), batch_rows):
        batch = targets[start:start + batch_rows]
        values_sql = []
        params: dict[str, Any] = {}
        for r_idx, row in enumerate(batch):
            parts = [_text_cast(f"id{r_idx}", "bigint")]
            params[f"id{r_idx}"] = str(row["id"])
            for c_idx, column in enumerate(columns):
                name = f"v{r_idx}_{c_idx}"
                params[name] = row[column]
                parts.append(_text_cast(name, types[column]))
            values_sql.append("(" + ", ".join(parts) + ")")

        col_names = ", ".join(f'"{c}"' for c in columns)
        res = await lconn.execute(
            text(
                f'UPDATE public."{comp.table}" m SET {set_sql} '
                f'FROM (VALUES {", ".join(values_sql)}) AS s(id, {col_names}) '
                "WHERE m.id = s.id RETURNING m.id"
            ),
            params,
        )
        applied += len(res.fetchall())

    result.applied = applied


async def _relink_matter_notes(
    lconn, sconn, comp: Component, result: ComponentResult, dry_run: bool,
) -> None:
    """4f. Repair note -> message links severed by a `chats` clear.

    matter_notes.message_id is ON DELETE SET NULL and matter_notes sits in no
    clear scope, so clearing chats quietly nulls those links inside a table the
    Danger Zone implies it does not touch. The notes themselves survive, so this
    is an UPDATE keyed on note id - and only where live is currently NULL and
    the message has actually come back.
    """
    staging_cols = await _columns(sconn, comp.table)
    live_cols = await _columns(lconn, comp.table)
    if "message_id" not in staging_cols or "message_id" not in live_cols:
        result.available = False
        result.notes.append("matter_notes.message_id is not present in both the dump and live.")
        return

    rows = await sconn.execute(text(
        'SELECT id, message_id FROM public."matter_notes" WHERE message_id IS NOT NULL'
    ))
    staged = [(int(r[0]), int(r[1])) for r in rows]
    result.staging_rows = len(staged)
    result.live_rows = int(
        (await lconn.execute(text(
            'SELECT count(*) FROM public."matter_notes" WHERE message_id IS NOT NULL'
        ))).scalar() or 0
    )
    if not staged:
        return

    severed = await lconn.execute(text(
        'SELECT id FROM public."matter_notes" WHERE message_id IS NULL AND id = ANY(:ids)'
    ), {"ids": [n for n, _m in staged]})
    severed_ids = {int(r[0]) for r in severed}

    # The message must exist in live now - if its chat was skipped for a missing
    # user, the link still has nothing to point at.
    live_messages = await lconn.execute(text(
        'SELECT id FROM public."messages" WHERE id = ANY(:ids)'
    ), {"ids": sorted({m for _n, m in staged})})
    message_ids = {int(r[0]) for r in live_messages}

    targets = [(n, m) for n, m in staged if n in severed_ids and m in message_ids]
    result.would_apply = len(targets)
    missing = len([1 for n, m in staged if n in severed_ids and m not in message_ids])
    if missing:
        result.notes.append(
            f"{missing} severed link(s) cannot be repaired: the message was not restored."
        )
    if dry_run or not targets:
        return

    applied = 0
    for start in range(0, len(targets), _MAX_BATCH_ROWS):
        batch = targets[start:start + _MAX_BATCH_ROWS]
        values_sql = []
        params: dict[str, Any] = {}
        for idx, (note_id, message_id) in enumerate(batch):
            params[f"n{idx}"] = note_id
            params[f"m{idx}"] = message_id
            values_sql.append(f"(CAST(:n{idx} AS bigint), CAST(:m{idx} AS bigint))")
        res = await lconn.execute(
            text(
                'UPDATE public."matter_notes" n SET message_id = s.message_id '
                f'FROM (VALUES {", ".join(values_sql)}) AS s(id, message_id) '
                "WHERE n.id = s.id AND n.message_id IS NULL RETURNING n.id"
            ),
            params,
        )
        applied += len(res.fetchall())

    result.applied = applied


async def _reset_sequence(lconn, table: str) -> Optional[str]:
    """4d. Put the identity sequence back above the restored primary keys.

    Rows return with their original ids, so the sequence is left where the clear
    left it and the next real INSERT collides - hours later, as a duplicate-key
    error with no obvious connection to the restore. This is the classic bug in
    hand-rolled restores.

    The third setval argument matters: on an empty table, setval(seq, 1, false)
    makes the next value 1 rather than skipping it.
    """
    seq = (await lconn.execute(
        text("SELECT pg_get_serial_sequence(:t, 'id')"), {"t": f"public.{table}"}
    )).scalar()
    if not seq:
        return None
    await lconn.execute(text(
        f'SELECT setval(:seq, COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM public."{table}"'
    ), {"seq": seq})
    return seq


# ---------------------------------------------------------------------------
# Public operations
# ---------------------------------------------------------------------------

def _validate(scopes: list[str]) -> list[str]:
    unknown = sorted(set(scopes) - set(SCOPE_COMPONENTS))
    if unknown:
        raise RestoreError(f"Unknown scope(s): {', '.join(unknown)}")
    if not scopes:
        raise RestoreError("Select at least one thing to restore.")
    return [s for s in RESTORE_ORDER if s in set(scopes)]


async def run_restore(
    db: AsyncSession,
    run_id: str,
    scopes: list[str],
    dry_run: bool,
) -> dict:
    """Stage the dump and either measure (dry_run) or apply the scoped restore.

    The preflight and the real thing walk exactly the same code with the same
    filters, so what the operator is shown is what will happen - not a separate
    estimate that can drift from the implementation.
    """
    ordered = _validate(scopes)
    target = get_pg_target()
    pg_bin = resolve_pg_bin()
    run = _resolve_run(run_id, target.database)
    dump_file = run["dump_file"]
    started = time.monotonic()

    async with _restore_lock:
        # Cluster-wide guard, so a second uvicorn worker cannot drop the staging
        # database from under this run. Released in the outer finally below.
        got_lock = bool(
            (await db.execute(
                text("SELECT pg_try_advisory_lock(:k)"), {"k": _ADVISORY_LOCK_KEY}
            )).scalar()
        )
        if not got_lock:
            raise RestoreError(
                "Another restore or preflight is already running. Wait for it to finish."
            )

        try:
            return await _run_restore_locked(
                db, target, pg_bin, run, dump_file, ordered, dry_run, started
            )
        finally:
            try:
                await db.execute(
                    text("SELECT pg_advisory_unlock(:k)"), {"k": _ADVISORY_LOCK_KEY}
                )
                await db.commit()
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"[Restore] Could not release the advisory lock: {exc}")


async def _run_restore_locked(
    db: AsyncSession,
    target: PgTarget,
    pg_bin: str,
    run: dict,
    dump_file: str,
    ordered: list[str],
    dry_run: bool,
    started: float,
) -> dict:
    """The body of run_restore, with exclusivity already established."""
    _verify_dump(pg_bin, dump_file, target.password)

    safety_dump = None
    if not dry_run:
        safety_dump = _safety_dump(pg_bin, target)

    tables = _tables_for(ordered)
    landed = await _stage(target, pg_bin, dump_file, tables)
    missing_tables = [t for t in tables if t not in landed]

    results: list[ComponentResult] = []
    touched_tables: list[str] = []
    sequences: list[str] = []
    engine = _staging_engine(target)

    try:
        async with engine.connect() as sconn:
            lconn = db
            for scope, comp in scope_components(ordered):
                result = ComponentResult(
                    key=comp.key, scope=scope, table=comp.table,
                    operation=comp.operation, label=comp.label,
                )
                if comp.note:
                    result.notes.append(comp.note)

                # Rows excluded from the dump by design can never come back.
                # Read from the manifest, not hardcoded, so this stays true
                # if the exclusion list ever changes.
                if comp.table in (run.get("excluded_table_data") or []):
                    result.available = False
                    result.notes.append(
                        f"{comp.table} rows are excluded from every backup by design "
                        "(--exclude-table-data), so there is nothing to restore."
                    )
                    results.append(result)
                    continue

                if comp.table in missing_tables:
                    result.available = False
                    result.notes.append(
                        f"{comp.table} does not exist in this backup - it predates the table."
                    )
                    results.append(result)
                    continue

                if comp.operation == _OP_INSERT:
                    await _insert_component(lconn, sconn, comp, result, dry_run)
                    if result.applied:
                        touched_tables.append(comp.table)
                elif comp.operation == _OP_UPDATE:
                    await _update_ratings(lconn, sconn, comp, result, dry_run)
                elif comp.operation == _OP_RELINK:
                    await _relink_matter_notes(lconn, sconn, comp, result, dry_run)

                results.append(result)

            if not dry_run:
                for table in dict.fromkeys(touched_tables):
                    seq = await _reset_sequence(lconn, table)
                    if seq:
                        sequences.append(seq)
                await db.commit()
            else:
                await db.rollback()
    except Exception:
        await db.rollback()
        raise
    finally:
        await engine.dispose()
        try:
            await _drop_staging(target)
        except Exception as exc:  # noqa: BLE001 - housekeeping must not mask the real error
            logger.warning(f"[Restore] Could not drop {STAGING_DB}: {exc}")

    total = sum(r.applied for r in results)
    would = sum(r.would_apply for r in results)
    return {
        "dry_run": dry_run,
        "run_id": run["id"],
        "database": target.database,
        "dump_file": dump_file,
        "commit_sha": run.get("commit_sha"),
        "backup_started_at": run.get("started_at"),
        "scopes": ordered,
        "components": [r.as_dict() for r in results],
        "total_rows": would if dry_run else total,
        "sequences_reset": sequences,
        "safety_dump": safety_dump,
        "duration_s": round(time.monotonic() - started, 2),
    }


def _safety_dump(pg_bin: str, target: PgTarget) -> str:
    """Dump the live database before changing it, so the restore is itself undoable.

    Written beside the console script's own safety dumps, and in the same format,
    so `restore_database.ps1 -DumpFile <this>` will undo it.
    """
    out_dir = os.path.join(settings.backup_root, "pre-restore")
    os.makedirs(out_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    out_file = os.path.join(out_dir, f"{target.database}_{stamp}_scoped.dump")

    result = _run_tool(
        os.path.join(pg_bin, _exe("pg_dump")),
        [
            "-U", target.user, "-h", target.host, "-p", target.port,
            "-d", target.database, "-Fc", "-f", out_file,
        ],
        target.password,
    )
    if result.returncode != 0 or not os.path.isfile(out_file):
        raise RestoreError(
            "Aborted: could not dump the current contents first, so the restore "
            f"would not be undoable. pg_dump said: {(result.stderr or '').strip()[:400]}"
        )
    logger.warning(f"[Restore] Pre-restore safety dump written to {out_file}")
    return out_file
