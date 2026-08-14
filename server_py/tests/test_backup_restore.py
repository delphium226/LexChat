"""Tests for the Developer-tab scoped restore (D14 Phases 4-6).

The data path itself — stage a real dump, clear a scope through the real Danger
Zone, restore it, prove the ratings came back — is exercised end to end against
a scratch database by the harness recorded in docs/BACKUP_RESTORE_PLAN.md; it
needs pg_restore, a live cluster and a real nightly backup run, none of which
belong in the unit suite.

What is pinned HERE is everything that can rot silently:

  * admin-only, via the router-level dependency;
  * the typed confirmation is enforced SERVER-side;
  * RESTORE_ORDER is the exact reversal of _CLEAR_ORDER, and the two scope maps
    agree — a scope added to one and not the other is an ordering bug that would
    otherwise surface as an FK violation months later;
  * `feedback` restores ratings with an UPDATE, not an INSERT (4b). This is the
    one that silently reports success having restored nothing;
  * `chats` carries the matter_notes re-link (4f);
  * backup discovery: manifest parsing, FAILED runs never restorable, a dump
    that did not verify never restorable;
  * the text-cast nesting asyncpg requires.
"""
import json
import os

import pytest

from src.routers.developer import DATA_SCOPES, _CLEAR_ORDER, _RESTORE_CONFIRM_PHRASE
from src.services import backup_restore as br

# Marked per-test rather than module-wide: unlike the other test modules this one
# is a mix of sync invariant checks and async endpoint calls.
asyncio_test = pytest.mark.asyncio

ALL_SCOPES = ["chats", "performance", "feedback", "activity", "health", "cache"]


def _hdr(token):
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------------------- #
# Invariants against the Danger Zone
# --------------------------------------------------------------------------- #

def test_restore_order_is_the_reversal_of_clear_order():
    """The clear runs feedback before chats; the restore must run chats first.

    session_feedback.chat_id is ON DELETE SET NULL, so the clear has to remove
    feedback before chats or it orphans rows. The restore has the mirror-image
    constraint - parents before children - so a plain reversal is correct, and
    anything else puts session_feedback in before the chat it points at.
    """
    assert br.RESTORE_ORDER == list(reversed(_CLEAR_ORDER))


def test_every_clear_scope_has_a_restore_counterpart():
    assert set(br.SCOPE_COMPONENTS) == set(DATA_SCOPES)
    assert set(br.RESTORE_ORDER) == set(DATA_SCOPES)


def test_chats_scope_restores_parents_before_children():
    tables = [c.table for c in br.SCOPE_COMPONENTS["chats"]]
    assert tables.index("chats") < tables.index("messages")
    assert tables.index("messages") < tables.index("documents")


def test_feedback_ratings_are_an_update_not_an_insert():
    """4b - the trap. An INSERT here restores nothing and reports success.

    Clearing `feedback` runs UPDATE messages SET rating = NULL: the message rows
    survive. So every id from the dump already exists, ON CONFLICT (id) DO
    NOTHING skips all of them, and the operation looks like it worked.
    """
    by_table = {c.table: c for c in br.SCOPE_COMPONENTS["feedback"]}
    assert by_table["messages"].operation == "update"
    assert by_table["product_feedback"].operation == "insert"
    assert by_table["session_feedback"].operation == "insert"


def test_chats_scope_relinks_matter_notes():
    """4f - matter_notes is in no clear scope, but a chats clear severs its links."""
    by_table = {c.table: c for c in br.SCOPE_COMPONENTS["chats"]}
    assert by_table["matter_notes"].operation == "relink"


def test_fk_rules_match_the_models():
    """4e - nullable references get nulled, NOT NULL ones make the row unrestorable."""
    chats = dict((col, nullable) for col, _parent, nullable in br._FK_RULES["chats"])
    assert chats["user_id"] is False      # ON DELETE CASCADE, NOT NULL
    assert chats["matter_id"] is True     # ON DELETE SET NULL, nullable
    sf = dict((col, nullable) for col, _parent, nullable in br._FK_RULES["session_feedback"])
    assert sf["chat_id"] is True


def test_text_cast_is_nested():
    """asyncpg types a parameter from its surrounding cast, so one cast is not enough.

    `CAST(:p AS integer)` makes asyncpg expect a Python int and reject the text
    this module deliberately sends. The inner cast pins the parameter as text.
    """
    sql = br._text_cast("p0_1", "character varying(50)")
    assert sql == "CAST(CAST(:p0_1 AS text) AS character varying(50))"
    assert sql.count("CAST") == 2


# --------------------------------------------------------------------------- #
# Backup discovery
# --------------------------------------------------------------------------- #

def _write_run(root, name, *, status="ok", databases=None, failed=False, dumps=("lexchat",)):
    run_dir = os.path.join(root, name)
    os.makedirs(run_dir, exist_ok=True)
    for db in dumps:
        with open(os.path.join(run_dir, f"{db}.dump"), "wb") as fh:
            fh.write(b"PGDMP fake")
    manifest = {
        "status": status,
        "started_at": "2026-08-14T02:30:00.0000000+01:00",
        "commit_sha": "a" * 40,
        "pg_version": "18.3",
        "excluded_table_data": ["local_prompt_cache"],
        "total_bytes": 10,
        "globals": {"file": "globals.sql", "mode": "no-role-passwords"},
        "databases": databases if databases is not None else [
            {"name": "lexchat", "bytes": 10, "verify": "ok", "toc_entries": 172}
        ],
        "errors": [],
    }
    with open(os.path.join(run_dir, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh)
    if failed:
        with open(os.path.join(run_dir, "FAILED"), "w", encoding="utf-8") as fh:
            fh.write("verify failed")
    return run_dir


def test_list_runs_on_a_missing_root_is_not_an_error(monkeypatch, tmp_path):
    monkeypatch.setattr(br.settings, "backup_root", str(tmp_path / "nope"))
    listing = br.list_runs("lexchat")
    assert listing["root_exists"] is False
    assert listing["runs"] == []
    assert listing["latest"] is None
    assert listing["latest_ok"] is None


def test_list_runs_reads_the_manifest(monkeypatch, tmp_path):
    monkeypatch.setattr(br.settings, "backup_root", str(tmp_path))
    _write_run(str(tmp_path), "2026-08-13_023000")
    _write_run(str(tmp_path), "2026-08-14_023000")

    listing = br.list_runs("lexchat")
    assert [r["id"] for r in listing["runs"]] == ["2026-08-14_023000", "2026-08-13_023000"]
    newest = listing["latest"]
    assert newest["commit_sha"] == "a" * 40
    assert newest["pg_version"] == "18.3"
    assert newest["globals_mode"] == "no-role-passwords"
    assert newest["restorable"] is True
    assert newest["has_dump"] is True
    # Directories that are not run stamps are ignored.
    os.makedirs(tmp_path / "pre-restore", exist_ok=True)
    os.makedirs(tmp_path / "logs", exist_ok=True)
    assert len(br.list_runs("lexchat")["runs"]) == 2


def test_failed_run_is_listed_but_never_restorable(monkeypatch, tmp_path):
    monkeypatch.setattr(br.settings, "backup_root", str(tmp_path))
    _write_run(str(tmp_path), "2026-08-14_023000", status="FAILED", failed=True)
    listing = br.list_runs("lexchat")
    assert listing["runs"][0]["failed"] is True
    assert listing["runs"][0]["restorable"] is False
    assert listing["latest_ok"] is None
    with pytest.raises(br.RestoreError, match="FAILED"):
        br._resolve_run("2026-08-14_023000", "lexchat")


def test_unverified_database_is_not_restorable(monkeypatch, tmp_path):
    """A dump that failed verification at backup time must not be offered."""
    monkeypatch.setattr(br.settings, "backup_root", str(tmp_path))
    _write_run(
        str(tmp_path), "2026-08-14_023000",
        databases=[{"name": "lexchat", "bytes": 10, "verify": "FAILED", "toc_entries": 0}],
    )
    listing = br.list_runs("lexchat")
    assert listing["runs"][0]["restorable"] is False
    with pytest.raises(br.RestoreError, match="did not verify"):
        br._resolve_run("2026-08-14_023000", "lexchat")


def test_run_without_a_dump_for_this_database(monkeypatch, tmp_path):
    """A federated bot added after a backup run has no dump in it."""
    monkeypatch.setattr(br.settings, "backup_root", str(tmp_path))
    _write_run(str(tmp_path), "2026-08-14_023000", dumps=("lexchat",))
    listing = br.list_runs("lexchat_westminster")
    assert listing["runs"][0]["has_dump"] is False
    assert listing["runs"][0]["restorable"] is False
    with pytest.raises(br.RestoreError, match="no dump"):
        br._resolve_run("2026-08-14_023000", "lexchat_westminster")


def test_run_id_must_be_a_run_stamp(monkeypatch, tmp_path):
    """Guards the path join - a run id is never a caller-controlled path fragment."""
    monkeypatch.setattr(br.settings, "backup_root", str(tmp_path))
    for bad in ("..", "../../windows", "pre-restore", "", "2026-8-14_0230"):
        with pytest.raises(br.RestoreError, match="Not a backup run id"):
            br._resolve_run(bad, "lexchat")


def test_scope_validation():
    with pytest.raises(br.RestoreError, match="Unknown scope"):
        br._validate(["chats", "users"])
    with pytest.raises(br.RestoreError, match="at least one"):
        br._validate([])
    # Normalised into restore order regardless of the order they arrive in.
    assert br._validate(["feedback", "chats"]) == ["chats", "feedback"]


def test_tables_for_scopes_are_deduped():
    """`messages` appears in both chats and feedback but is staged once."""
    tables = br._tables_for(["chats", "feedback"])
    assert tables.count("messages") == 1
    assert set(tables) == {
        "chats", "messages", "documents", "matter_notes",
        "product_feedback", "session_feedback",
    }


# --------------------------------------------------------------------------- #
# Endpoint auth and guards
# --------------------------------------------------------------------------- #

@asyncio_test
async def test_backups_requires_admin(client, user_token):
    r = await client.get("/api/developer/backups", headers=_hdr(user_token))
    assert r.status_code == 403


@asyncio_test
async def test_preflight_requires_admin(client, user_token):
    r = await client.post(
        "/api/developer/restore/preflight",
        json={"run_id": "2026-08-14_023000", "scopes": ["chats"]},
        headers=_hdr(user_token),
    )
    assert r.status_code == 403


@asyncio_test
async def test_restore_requires_admin(client, user_token):
    r = await client.post(
        "/api/developer/restore",
        json={"run_id": "2026-08-14_023000", "scopes": ["chats"], "confirm": "RESTORE"},
        headers=_hdr(user_token),
    )
    assert r.status_code == 403


@pytest.mark.parametrize("confirm", ["", "restore", "RESTORE ", "DELETE", "yes"])
@asyncio_test
async def test_wrong_confirmation_is_rejected_before_anything_happens(
    client, admin_token, monkeypatch, tmp_path, confirm
):
    """The phrase is checked before the run is even resolved, so a bad dump path
    cannot be probed without it."""
    monkeypatch.setattr(br.settings, "backup_root", str(tmp_path))
    called = []
    monkeypatch.setattr(br, "run_restore", lambda *a, **k: called.append(1))

    r = await client.post(
        "/api/developer/restore",
        json={"run_id": "2026-08-14_023000", "scopes": ALL_SCOPES, "confirm": confirm},
        headers=_hdr(admin_token),
    )
    assert r.status_code == 400
    assert _RESTORE_CONFIRM_PHRASE in r.json()["detail"]
    assert called == []


@asyncio_test
async def test_backups_endpoint_reports_scopes_and_components(
    client, admin_token, monkeypatch, tmp_path
):
    monkeypatch.setattr(br.settings, "backup_root", str(tmp_path))
    _write_run(str(tmp_path), "2026-08-14_023000", dumps=("lexchat_test",))

    r = await client.get("/api/developer/backups", headers=_hdr(admin_token))
    assert r.status_code == 200
    body = r.json()
    assert body["confirm_phrase"] == "RESTORE"
    assert set(body["scopes"]) == set(DATA_SCOPES)
    assert list(body["components"]) == br.RESTORE_ORDER
    # The UI needs to know feedback's third component is an UPDATE so it can say so.
    ops = [c["operation"] for c in body["components"]["feedback"]]
    assert "update" in ops


@asyncio_test
async def test_preflight_rejects_an_unknown_run(client, admin_token, monkeypatch, tmp_path):
    monkeypatch.setattr(br.settings, "backup_root", str(tmp_path))
    r = await client.post(
        "/api/developer/restore/preflight",
        json={"run_id": "2026-08-14_023000", "scopes": ["chats"]},
        headers=_hdr(admin_token),
    )
    assert r.status_code == 400
    assert "No backup run" in r.json()["detail"]


@asyncio_test
async def test_preflight_rejects_an_unknown_scope(client, admin_token, monkeypatch, tmp_path):
    monkeypatch.setattr(br.settings, "backup_root", str(tmp_path))
    r = await client.post(
        "/api/developer/restore/preflight",
        json={"run_id": "2026-08-14_023000", "scopes": ["users"]},
        headers=_hdr(admin_token),
    )
    assert r.status_code == 400
    assert "users" in r.json()["detail"]


# --------------------------------------------------------------------------- #
# Connection settings
# --------------------------------------------------------------------------- #

def test_pg_target_is_parsed_from_the_app_url(monkeypatch):
    """The restore holds no credentials of its own; it reads the app's DATABASE_URL."""
    monkeypatch.setattr(
        br.settings, "database_url",
        "postgresql+asyncpg://lexuser:p%40ss@db.example:5433/lexchat_parliament",
    )
    target = br.get_pg_target()
    assert target.user == "lexuser"
    assert target.password == "p@ss"       # percent-decoded
    assert target.host == "db.example"
    assert target.port == "5433"
    assert target.database == "lexchat_parliament"


def test_staging_database_is_not_the_live_one(monkeypatch):
    """The app must never be able to connect to the staging database."""
    monkeypatch.setattr(
        br.settings, "database_url",
        "postgresql://lexuser:x@localhost:5432/lexchat",
    )
    assert br.STAGING_DB != br.get_pg_target().database
    assert br.STAGING_DB not in br.settings.database_url
