"""The made-under record (FIX_PLAN P3.31): which instruments' own preambles name
which provisions as the powers they were made under.

**Why a store.** "Which SSIs were made under section 95 of the Social Security
(Scotland) Act 2018?" (6382, 6383) needs every instrument's preamble read in
advance; no endpoint returns the relation (P5.1). Measured at P3.31 Step 2: the
record finds 37 of 37 such SSIs with none wrong, against 4 in the product's best
stored run.

**How it gets here.** A harvest from legislation.gov.uk's as-made XML, run on
the dev machine (`python -m tools.madeunder_probe`), is committed as a snapshot
under `server_py/data/made_under/` with a `manifest.json` that states its
coverage. `load_snapshot` copies it into two tables at startup when the
manifest's version is newer than the one loaded (`AppSetting
made_under.snapshot`). `refresh_new` then adds newly published instruments
daily from legislation.gov.uk's new-legislation feed, read through LEX's
`/legislation/proxy` (the host the target already calls; the proxy returns an
as-made XML byte for byte, checked 2026-10-08), so no whitelist entry is added.

**What it can and cannot say.** A row says one instrument's preamble names one
provision. The record says nothing about instruments outside its coverage, so
every answer carries the coverage statement and the Worker is told not to turn
an empty result into "none was made" (`utils.made_under.made_under_note`).

Every entry point is fail-soft: a missing snapshot, an empty table or a DB
error leaves the tool answering `unavailable`, never raising into a research
run.
"""
from __future__ import annotations

import asyncio
import gzip
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from sqlalchemy import text

from ..utils.made_under import (
    MADE_UNDER_TOOL, MAX_LISTED, _short, is_legislation_id, normalise_title,
    parse_powers, preamble_text, provision_key, recital_window, text_before_window,
)

logger = logging.getLogger(__name__)

SNAPSHOT_DIR = Path(__file__).resolve().parents[2] / "data" / "made_under"
SNAPSHOT_FILE = "made_under_snapshot.jsonl.gz"
MANIFEST_FILE = "manifest.json"
SETTING_KEY = "made_under.snapshot"

# The refresh: legislation.gov.uk paths, read through LEX's proxy.
# UK SIs joined the record on 2026-10-09 (SSIs from 1999, UK SIs from 1987).
NEW_FEED_PATHS = ("new/ssi/data.feed", "new/uksi/data.feed")
REFRESH_PAGES = 5
REFRESH_TIMEOUT_S = 20.0
REFRESH_MAX_FETCHES = 120
REFRESH_GAP_S = 0.5

# Set by `load_snapshot` once the record is known to be in the tables. Until
# then `recital_for`, which runs on every SSI text read and section search, does
# not touch the database at all: a server that never loaded the record (a
# parliament bot, a unit test) pays nothing for it and opens no connection.
_STATE = {"available": False}


_FEED_ID = re.compile(r"<id>http://www\.legislation\.gov\.uk/id/((?:ssi|uksi)/\d{4}/\d+)</id>")


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------

def read_manifest(snapshot_dir: Path = SNAPSHOT_DIR) -> Optional[dict]:
    try:
        return json.loads((snapshot_dir / MANIFEST_FILE).read_text(encoding="utf-8"))
    except Exception:
        return None


def read_snapshot(snapshot_dir: Path = SNAPSHOT_DIR) -> list:
    path = snapshot_dir / SNAPSHOT_FILE
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return [json.loads(ln) for ln in fh if ln.strip()]


def _as_datetime(value) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value)) if value else None
    except ValueError:
        return None


def _rows_for(rec: dict) -> tuple:
    """`(instrument_row, [power_rows])` for one snapshot or refresh record."""
    inst = {
        "lid": rec["id"], "title": _short(rec.get("title") or "", 300),
        "recital": (rec.get("recital") or rec.get("window") or "")[:2000],
        "version": rec.get("version") or "", "source": rec.get("source") or "snapshot",
        # asyncpg types the bind from the column and rejects a string, even
        # one inside a CAST, so the date is parsed here.
        "harvested_at": _as_datetime(rec.get("harvested_at")),
    }
    powers = []
    for p in rec.get("powers") or []:
        act = p.get("act")
        if not act:
            continue
        for prov in p.get("provisions") or []:
            powers.append({"lid": rec["id"], "act_title": act[:300],
                           "act_norm": normalise_title(act)[:300],
                           "act_id": (p.get("act_id") or None),
                           "provision": prov[:64], "role": (p.get("role") or "power")[:32]})
    return inst, powers


_INSERT_INSTRUMENT = text(
    "INSERT INTO made_under_instruments (legislation_id, title, recital, version, source, harvested_at) "
    "VALUES (:lid, :title, :recital, :version, :source, :harvested_at) "
    "ON CONFLICT (legislation_id) DO UPDATE SET title = EXCLUDED.title, recital = EXCLUDED.recital, "
    "version = EXCLUDED.version, source = EXCLUDED.source, harvested_at = EXCLUDED.harvested_at")
_INSERT_POWER = text(
    "INSERT INTO made_under_powers (legislation_id, act_title, act_norm, act_id, provision, role) "
    "VALUES (:lid, :act_title, :act_norm, :act_id, :provision, :role)")


async def _store(session, records: list) -> int:
    insts, powers = [], []
    for rec in records:
        i, p = _rows_for(rec)
        insts.append(i)
        powers.extend(p)
    if not insts:
        return 0
    ids = [i["lid"] for i in insts]
    await session.execute(text("DELETE FROM made_under_powers WHERE legislation_id = ANY(:ids)"),
                          {"ids": ids})
    await session.execute(_INSERT_INSTRUMENT, insts)
    if powers:
        await session.execute(_INSERT_POWER, powers)
    return len(insts)


async def load_snapshot(snapshot_dir: Path = SNAPSHOT_DIR) -> dict:
    """Copy the committed snapshot into the tables if it is newer than the one
    loaded. Instruments the daily refresh added and the snapshot lacks are kept."""
    from ..database import async_session_maker
    from ..models import AppSetting
    manifest = read_manifest(snapshot_dir)
    if not manifest:
        logger.info("[MadeUnder] No snapshot manifest; the made-under record is empty.")
        return {"loaded": 0, "reason": "no_manifest"}
    version = str(manifest.get("version") or "")
    try:
        async with async_session_maker() as session:
            current = await session.get(AppSetting, SETTING_KEY)
            if current is not None and current.value == version:
                _STATE["available"] = True
                return {"loaded": 0, "reason": "current", "version": version}
            records = await asyncio.to_thread(read_snapshot, snapshot_dir)
            for rec in records:
                rec.setdefault("harvested_at", manifest.get("harvested_at"))
                rec["source"] = "snapshot"
            await session.execute(text(
                "DELETE FROM made_under_powers WHERE legislation_id IN "
                "(SELECT legislation_id FROM made_under_instruments WHERE source = 'snapshot')"))
            await session.execute(text("DELETE FROM made_under_instruments WHERE source = 'snapshot'"))
            n = 0
            for k in range(0, len(records), 2000):
                n += await _store(session, records[k:k + 2000])
            if current is None:
                session.add(AppSetting(key=SETTING_KEY, value=version))
            else:
                current.value = version
            await session.commit()
        _STATE["available"] = n > 0
        logger.info("[MadeUnder] Loaded snapshot %s: %d instruments.", version, n)
        return {"loaded": n, "version": version}
    except Exception as e:
        logger.error("[MadeUnder] Snapshot load failed: %s", e)
        return {"loaded": 0, "reason": f"error: {type(e).__name__}"}


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

def coverage(manifest: Optional[dict], refreshed_to: Optional[str], refreshed: int) -> dict:
    m = manifest or {}
    label = m.get("label") or "a harvest of instrument preambles"
    harvested = m.get("harvested_at") or "an unrecorded date"
    statement = f"{label}, as harvested from legislation.gov.uk on {harvested}"
    if refreshed and refreshed_to:
        statement += f", with {refreshed} newer instrument(s) added up to {refreshed_to}"
    statement += "."
    if m.get("not_covered"):
        statement += f" Not covered: {m['not_covered']}."
    return {"statement": statement, "label": label, "harvested_at": harvested,
            "refreshed_to": refreshed_to}


def _sort_key(lid: str) -> tuple:
    parts = lid.split("/")
    try:
        return (int(parts[-2]), int(parts[-1]))
    except (ValueError, IndexError):
        return (0, 0)


def build_result(act: str, section: str, provision: str, rows: list, act_rows: list,
                 cov: dict) -> dict:
    """The tool's JSON from query rows. Pure, so it is tested without a DB.

    `rows`: (legislation_id, title, act_title, act_id, role) for the provision.
    `act_rows`: (provision, count) for every provision of the Act the record
    holds, used only when `rows` is empty.
    """
    out = {"tool": MADE_UNDER_TOOL, "act": act, "section": section,
           "provision": provision, "coverage": cov}
    if not rows:
        if act_rows:
            cited = [p for p, _ in sorted(act_rows, key=lambda r: -r[1])][:12]
            out.update(status="act_known_section_not_cited",
                       matched_act=act, count=0, instruments=[],
                       provisions_of_act_cited=cited)
        else:
            out.update(status="act_not_in_record", count=0, instruments=[])
        return out
    by_id = {}
    for lid, title, act_title, act_id, role in rows:
        e = by_id.setdefault(lid, {"legislation_id": lid, "title": _short(title, 110),
                                   "url": f"https://www.legislation.gov.uk/{lid}",
                                   "roles": []})
        if role not in e["roles"]:
            e["roles"].append(role)
        out.setdefault("matched_act", act_title)
        if act_id:
            out.setdefault("act_id", act_id)
    insts = sorted(by_id.values(), key=lambda e: _sort_key(e["legislation_id"]))
    for e in insts:
        # "power" is the common case and says nothing; a qualifier
        # ("as applied by") is kept because it changes what the claim is.
        if e["roles"] == ["power"]:
            e.pop("roles")
    out.update(status="found", count=len(insts), instruments=insts[:MAX_LISTED])
    return out


async def query(act: str, section: str) -> dict:
    """`find_instruments_made_under`'s result. Never raises."""
    provision = provision_key(section)
    base = {"tool": MADE_UNDER_TOOL, "act": act, "section": section, "provision": provision}
    if not str(act or "").strip() or not provision:
        return dict(base, status="invalid",
                    note="Give the Act (its title or legislation id) and a section number.")
    try:
        from ..database import async_session_maker
        manifest = read_manifest()
        key = str(act).strip().strip("/")
        col = "act_id" if is_legislation_id(key) else "act_norm"
        val = key if col == "act_id" else normalise_title(key)
        async with async_session_maker() as session:
            total = (await session.execute(text("SELECT count(*) FROM made_under_instruments"))).scalar() or 0
            if not total:
                return dict(base, status="unavailable",
                            note="The made-under record is not loaded on this server.")
            rows = (await session.execute(text(
                "SELECT p.legislation_id, i.title, p.act_title, p.act_id, p.role "
                "FROM made_under_powers p JOIN made_under_instruments i USING (legislation_id) "
                f"WHERE p.{col} = :v AND p.provision = :prov"), {"v": val, "prov": provision})).all()
            act_rows = []
            if not rows:
                act_rows = (await session.execute(text(
                    f"SELECT provision, count(DISTINCT legislation_id) FROM made_under_powers "
                    f"WHERE {col} = :v GROUP BY provision"), {"v": val})).all()
            ref = (await session.execute(text(
                "SELECT count(*), max(harvested_at) FROM made_under_instruments "
                "WHERE source = 'refresh'"))).one()
        refreshed, refreshed_to = int(ref[0] or 0), (ref[1].date().isoformat() if ref[1] else None)
        return build_result(act, section, provision, [tuple(r) for r in rows],
                            [tuple(r) for r in act_rows], coverage(manifest, refreshed_to, refreshed))
    except Exception as e:
        logger.error("[MadeUnder] Query failed: %s", e)
        return dict(base, status="unavailable", note="The made-under record could not be read.")


def read_as(rows: list) -> str:
    """The record's reading of a recital, from its power rows.

    `rows`: (act_title, provision, role). A recital often points back ("section
    2(2) of that Act"), so the words alone do not say which Act; this says what
    the record resolved them to: "section 2 of the European Communities Act 1972".
    """
    by_act: dict = {}
    for act, prov, role in rows:
        key = (act, role)
        by_act.setdefault(key, [])
        label = prov.replace("schedule/", "Schedule ").replace("/paragraph/", " paragraph ")
        label = label.replace("section/", "section ").replace("regulation/", "regulation ")
        label = label.replace("article/", "article ").replace("paragraph/", "paragraph ")
        if label not in by_act[key]:
            by_act[key].append(label)
    parts = []
    for (act, role), provs in by_act.items():
        lead = "" if role == "power" else f"{role} "
        parts.append(f"{lead}{', '.join(provs[:8])}{' and others' if len(provs) > 8 else ''} of the {act}")
    return "; ".join(parts)


async def recital_for(legislation_id: str) -> Optional[str]:
    """The stored recital of one instrument, with the record's reading of it
    where the record resolved one, or None. Never raises."""
    if not _STATE["available"]:
        return None
    try:
        from ..database import async_session_maker
        lid = str(legislation_id).strip().strip("/")
        async with async_session_maker() as session:
            row = (await session.execute(text(
                "SELECT recital FROM made_under_instruments WHERE legislation_id = :lid"),
                {"lid": lid})).first()
            if not row or not row[0]:
                return None
            powers = (await session.execute(text(
                "SELECT act_title, provision, role FROM made_under_powers "
                "WHERE legislation_id = :lid ORDER BY id"), {"lid": lid})).all()
        reading = read_as([tuple(p) for p in powers])
        return row[0] + (f" (read by the record as: {reading})" if reading else "")
    except Exception:
        return None


def majority_act_titles(rows) -> dict:
    """`{act_id: title}` from `(act_id, act_title, count)` rows: the spelling
    most of the record's recital rows use. Recitals misspell an Act now and
    then (106 of 2,215 resolved Acts carry a second spelling, the larger one
    nearly always by far); a tie gives no title rather than a guess."""
    by: dict = {}
    for act_id, title, n in rows or []:
        if act_id and title:
            by.setdefault(act_id, []).append((int(n or 0), str(title)))
    out = {}
    for act_id, cands in by.items():
        cands.sort(reverse=True)
        if len(cands) == 1 or cands[0][0] > cands[1][0]:
            out[act_id] = cands[0][1]
    return out


async def titles_for(legislation_ids) -> dict:
    """P4.24: `{legislation_id: title}` from the record, for the Sources rail.
    An instrument's own title where the record holds the instrument, else an
    Act's title as the record's recitals resolved it (`majority_act_titles`).
    Like `recital_for`, no database until the record is loaded; never raises."""
    if not _STATE["available"]:
        return {}
    ids = sorted({str(i).strip().strip("/") for i in legislation_ids or () if i})
    if not ids:
        return {}
    try:
        from ..database import async_session_maker
        async with async_session_maker() as session:
            rows = (await session.execute(text(
                "SELECT legislation_id, title FROM made_under_instruments "
                "WHERE legislation_id = ANY(:ids)"), {"ids": ids})).all()
            out = {r[0]: r[1] for r in rows if r[1]}
            rest = [i for i in ids if i not in out]
            acts = []
            if rest:
                acts = (await session.execute(text(
                    "SELECT act_id, act_title, COUNT(*) FROM made_under_powers "
                    "WHERE act_id = ANY(:ids) GROUP BY act_id, act_title"),
                    {"ids": rest})).all()
        out.update(majority_act_titles([tuple(a) for a in acts]))
        return out
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Daily refresh
# ---------------------------------------------------------------------------

def _proxy(path: str) -> str:
    from ..config import settings
    return f"{settings.lex_api_url.rstrip('/')}/legislation/proxy/{quote(path.lstrip('/'), safe='')}"


def record_from_xml(lid: str, xml_text: str) -> dict:
    m = re.search(r"<dc:title>(.*?)</dc:title>", xml_text, re.S)
    title = re.sub(r"\s+", " ", m.group(1)).strip() if m else ""
    state, pre = preamble_text(xml_text)
    window = recital_window(pre) if state == "ok" else ""
    return {"id": lid, "title": title, "version": "made", "recital": window,
            "powers": parse_powers(window, text_before_window(pre)) if window else []}


async def refresh_new(client=None) -> dict:
    """Add instruments published since the snapshot. Fail-soft; bounded."""
    import httpx
    from ..database import async_session_maker
    own = client is None
    client = client or httpx.AsyncClient(timeout=REFRESH_TIMEOUT_S, verify=False)
    stats = {"seen": 0, "added": 0, "errors": 0}
    try:
        async with async_session_maker() as session:
            have = {r[0] for r in (await session.execute(text(
                "SELECT legislation_id FROM made_under_instruments"))).all()}
            known = {r[0]: r[1] for r in (await session.execute(text(
                "SELECT DISTINCT act_norm, act_id FROM made_under_powers WHERE act_id IS NOT NULL"))).all()}
        if not have:
            return dict(stats, reason="no_record")
        new_ids = []
        for path in NEW_FEED_PATHS:
            for page in range(1, REFRESH_PAGES + 1):
                r = await client.get(_proxy(f"{path}?page={page}"))
                if r.status_code != 200:
                    break
                ids = _FEED_ID.findall(r.text)
                stats["seen"] += len(ids)
                fresh = [i for i in ids if i not in have and i not in new_ids]
                new_ids.extend(fresh)
                if not fresh:
                    break
        records = []
        for lid in new_ids[:REFRESH_MAX_FETCHES]:
            await asyncio.sleep(REFRESH_GAP_S)
            try:
                # The introduction view: the whole preamble, a fraction of
                # the size (same recital on 50 of 50 sampled SSIs).
                r = await client.get(_proxy(f"{lid}/introduction/made/data.xml"))
                if r.status_code == 404:
                    r = await client.get(_proxy(f"{lid}/made/data.xml"))
                if r.status_code != 200:
                    stats["errors"] += 1
                    continue
                rec = record_from_xml(lid, r.text)
            except Exception:
                stats["errors"] += 1
                continue
            for p in rec["powers"]:
                if p.get("act"):
                    p["act_id"] = known.get(normalise_title(p["act"]))
            rec["source"] = "refresh"
            rec["harvested_at"] = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")
            records.append(rec)
        if records:
            async with async_session_maker() as session:
                stats["added"] = await _store(session, records)
                await session.commit()
        logger.info("[MadeUnder] Refresh: %s", stats)
        return stats
    except Exception as e:
        logger.error("[MadeUnder] Refresh failed: %s", e)
        return dict(stats, reason=f"error: {type(e).__name__}")
    finally:
        if own:
            await client.aclose()


async def background_made_under_loop(interval_s: int = 86400, first_delay_s: int = 600) -> None:
    """Load the snapshot, then refresh daily. Staggered so startup is not slowed."""
    await load_snapshot()
    await asyncio.sleep(first_delay_s)
    while True:
        try:
            await refresh_new()
        except Exception as e:  # pragma: no cover - refresh_new is fail-soft already
            logger.error("[MadeUnder] Loop error: %s", e)
        await asyncio.sleep(interval_s)
