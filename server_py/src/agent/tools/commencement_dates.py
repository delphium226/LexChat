"""FIX_PLAN P3.21: the date a commencement took effect, not only the instrument.

P3.5's change record (`/amendment/search`) says WHICH instrument commenced
WHICH provision and never WHEN: 0 of 19,031 `coming into force` rows carry a
date (P2.5). legislation.gov.uk's "Changes to Legislation" record does
(`/changes/affected/<id>/data.feed`, Atom): each effect is provision to
provision, like a LEX row, with `ukm:InForceDates` giving the date and its
qualification ("wholly in force", "for specified purposes", "for E."). Batch 8
D measured it against every stored relation (`notes/batch8_D.md`): 8,144 of
the 8,180 stored commencement relations made by another instrument match a
feed effect exactly, every one dated; and the feed passes through LEX's own
`GET /legislation/proxy/{path}` unchanged (30 of 30), so the target needs no
new whitelist entry. Decided by the user (2026-10-06, P3.21's row): **one
affected-feed fetch per change-record call, memoised per request, at most 2
pages, an 8 s timeout, fail-soft, and no date earlier than the commencing
instrument's made date.**

**What this module adds to a `get_legislation_changes` result** (direction
``"to"`` only; ``"by"`` lists changes the subject makes, which the subject's
*affected* feed does not describe):

* on each listed `changes` entry of a `coming into force` group made by
  another instrument (`self: false`) whose relations the feed dates,
  ``"in_force": "YYYY-MM-DD"`` and ``"qualification"`` (the feed's own words).
  An entry whose changed provisions take different dates is split, one entry
  per (date, qualification), so `by` can repeat within a group; an entry with
  no date keeps exactly the old ``{"by", "changed"}`` shape;
* on the result, ``"commencement_dates"``: ``{"status": "retrieved", ...}``
  with counts, or ``{"status": "not_retrieved", "reason": ...}``; absent when
  no hop ran (direction ``"by"``, or no listed commencement by another
  instrument, or not our shape).

**The made-date check, and where the made date comes from.** Batch 8 D found
one feed error: 17 relations dated two months before their instrument was
made. A commencing instrument cannot bring a provision into force before it
exists, so a date earlier than the instrument's made date is refused (the
entry is left undated and counted in ``refused``). The made date is read from
legislation.gov.uk's own metadata for the instrument, `ukm:Made` (an SI) or
`ukm:EnactmentDate` (an Act), in `/<id>/introduction/data.xml` (7.6 KB for a
commencement order, checked live through the proxy, batch 9 C), through the
same proxy. The feed carries no made date (every attribute and element of
29,932 stored effects read) and LEX's lookup does not either (`enactment_date`
null on 156 of 157 commencing instruments). **A date whose instrument's made
date could not be read is not given**: it could not be checked.

Product code never imports `tools/lgu_probe.py`: the parser below is a
re-implementation of its `parse_effects_feed`, keeping only what is used.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
import xml.etree.ElementTree as ET
from typing import Any, Callable, Optional
from urllib.parse import quote

import httpx

from ..provider_factory import get_request_provider_config
from ._util import _emit
from .lex import LEX_API_URL, _short_legislation_id

logger = logging.getLogger("agent")

# The decided bounds (P3.21's row, user decision 2026-10-06).
FEED_PER_PAGE = 500
MAX_FEED_PAGES = 2
HOP_TIMEOUT_S = 8.0
# Made-date reads per change-record call. Measured over the 1,094 stored
# ``"to"`` calls (batch 9 C, `census_calls.py`): 354 list at least one
# commencing instrument by another instrument, median 2, p90 6, max 14; 8
# covers 929 of their 981 instruments (95%) and 337 of the 354 calls in full.
# The groups are listed largest first, so the cap leaves out the smallest.
MAX_MADE_DATE_READS = 8
# How many made-date reads run at once (the feed read runs beside them).
_CONCURRENCY = 4

DATE_SOURCE = (
    "legislation.gov.uk's Changes to Legislation record, read through the LEX API"
)
# Where the per-request memo lives: the request's own config dict, which every
# tool call of the request shares by reference through the ContextVar. With no
# request config set (a script, a test), each call gets its own memo.
MEMO_KEY = "_commencement_dates_memo"

_COMING_INTO_FORCE = "coming into force"
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9/_.-]{2,80}$")
_FORBIDDEN_XML = re.compile(r"<!\s*(?:DOCTYPE|ENTITY)", re.I)

_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "ukm": "http://www.legislation.gov.uk/namespaces/metadata",
    "leg": "http://www.legislation.gov.uk/namespaces/legislation",
    "os": "http://a9.com/-/spec/opensearch/1.1/",
}


# ---------------------------------------------------------------------------
# paths
# ---------------------------------------------------------------------------

def feed_path(subject: str, page: int = 1) -> str:
    """legislation.gov.uk's path for one page of the subject's affected feed."""
    q = f"results-count={FEED_PER_PAGE}" + (f"&page={page}" if page > 1 else "")
    return f"changes/affected/{_short_legislation_id(subject)}/data.feed?{q}"


def introduction_path(instrument: str) -> str:
    """legislation.gov.uk's path for the instrument's introduction and metadata."""
    return f"{_short_legislation_id(instrument)}/introduction/data.xml"


def proxy_url(lgu_path: str) -> str:
    """The same path through LEX's proxy: the whole path, query string included,
    URL-encoded into one segment (as `lgu_probe --via lex` does, batch 8 D)."""
    return f"{LEX_API_URL}/legislation/proxy/{quote(lgu_path.lstrip('/'), safe='')}"


# ---------------------------------------------------------------------------
# parsers
# ---------------------------------------------------------------------------

def _xml_root(text: str):
    """Parse untrusted XML. A document type or entity declaration is refused:
    neither feed nor metadata carries one, and expat would expand entities."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("empty")
    if _FORBIDDEN_XML.search(text):
        raise ValueError("document type or entity declaration")
    try:
        return ET.fromstring(text)
    except ET.ParseError as e:
        raise ValueError(f"not XML: {e}") from None


def _int(text) -> Optional[int]:
    try:
        return int(str(text).strip())
    except (TypeError, ValueError):
        return None


def parse_effects_feed(xml_text: str) -> dict:
    """One page of a Changes to Legislation Atom feed.

    Returns ``{"total", "page", "total_pages", "effects": [...]}``; each effect
    keeps its type, both sides (instrument and provision label) and every
    `ukm:InForce` (``date`` None where the feed states none). Raises ValueError
    on anything that is not a feed, so an error page is never read as "no
    effects".
    """
    root = _xml_root(xml_text)
    if root.tag != f"{{{_NS['atom']}}}feed":
        raise ValueError(f"not an Atom feed: {root.tag}")
    out = {
        "total": _int(root.findtext("os:totalResults", namespaces=_NS)),
        "page": _int(root.findtext("leg:page", namespaces=_NS)) or 1,
        "total_pages": _int(root.findtext("leg:totalPages", namespaces=_NS)),
        "effects": [],
    }
    for eff in root.iter(f"{{{_NS['ukm']}}}Effect"):
        a = eff.attrib
        in_force = []
        for f in eff.iter(f"{{{_NS['ukm']}}}InForce"):
            date = (f.attrib.get("Date") or "").strip()
            in_force.append({
                "date": date if _ISO_DATE.match(date) else None,
                "qualification": (f.attrib.get("Qualification") or "").strip(),
            })
        out["effects"].append({
            "type": (a.get("Type") or "").strip(),
            "affected": _short_legislation_id(a.get("AffectedURI") or ""),
            "affected_provisions": a.get("AffectedProvisions") or "",
            "affecting": _short_legislation_id(a.get("AffectingURI") or ""),
            "affecting_provisions": a.get("AffectingProvisions") or "",
            "in_force": in_force,
        })
    return out


def parse_made_date(xml_text: str) -> Optional[str]:
    """The instrument's made date (`ukm:Made`) or, for an Act, its enactment
    date (`ukm:EnactmentDate`), from legislation.gov.uk's metadata; None if it
    states neither. Raises ValueError on a page that is not XML."""
    root = _xml_root(xml_text)
    for tag in ("Made", "EnactmentDate"):
        for el in root.iter(f"{{{_NS['ukm']}}}{tag}"):
            date = (el.attrib.get("Date") or "").strip()
            if _ISO_DATE.match(date):
                return date
    return None


# ---------------------------------------------------------------------------
# matching
# ---------------------------------------------------------------------------

def _norm(s: Any) -> str:
    return " ".join(str(s or "").lower().split())


def _is_commencement(effect: Any) -> bool:
    return _norm(effect) == _COMING_INTO_FORCE


def commencing_groups(slimmed: dict) -> list:
    """The listed `coming into force` groups made by another instrument."""
    if not isinstance(slimmed, dict) or (slimmed.get("direction") or "to") != "to":
        return []
    return [
        g for g in (slimmed.get("related") or [])
        if isinstance(g, dict) and not g.get("self") and g.get("legislation_id")
        and _is_commencement(g.get("type_of_effect"))
        and isinstance(g.get("changes"), list)
    ]


def commencing_instruments(slimmed: dict) -> list:
    """Their instruments, in the order the record lists them (largest first)."""
    out = []
    for g in commencing_groups(slimmed):
        if g["legislation_id"] not in out:
            out.append(g["legislation_id"])
    return out


def feed_date_index(effects: list, subject: str) -> dict:
    """``(changed provision, instrument, affecting provision) -> {(date,
    qualification)}`` over the feed's commencements of `subject` by another
    instrument, scheme-free and case- and space-insensitive (batch 8 D's
    `compare_commencements`). Undated and prospective effects add nothing."""
    lid = _short_legislation_id(subject)
    idx: dict = {}
    for e in effects or []:
        if not isinstance(e, dict) or not _is_commencement(e.get("type")):
            continue
        if e.get("affected") != lid or not e.get("affecting") or e.get("affecting") == lid:
            continue
        key = (_norm(e.get("affected_provisions")), e.get("affecting"),
               _norm(e.get("affecting_provisions")))
        for f in e.get("in_force") or []:
            if f.get("date"):
                idx.setdefault(key, set()).add((f["date"], f.get("qualification") or ""))
    return idx


def apply_dates(slimmed: dict, feed: dict, made: dict) -> dict:
    """Date each listed commencement relation by another instrument.

    `feed` is ``{"status": "ok", "effects", "total", "read"}`` or ``{"status":
    "failed", "reason"}``; `made` maps an instrument to its made date, or to
    None where it could not be read (or was not read: the cap). Returns a new
    dict; `slimmed` is not modified. On a failed feed the record is returned
    as it was, with the status saying the dates were not retrieved.
    """
    out = dict(slimmed)
    groups = commencing_groups(slimmed)
    if not groups:
        return out
    if not isinstance(feed, dict) or feed.get("status") != "ok":
        out["commencement_dates"] = {
            "status": "not_retrieved",
            "reason": str((feed or {}).get("reason") or "error"),
        }
        return out

    subject = slimmed.get("legislation_id") or ""
    idx = feed_date_index(feed.get("effects") or [], subject)
    relations = dated = refused = 0
    refused_by, unchecked_by = [], []
    new_related = []
    gids = {id(g) for g in groups}
    for g in slimmed.get("related") or []:
        if id(g) not in gids:
            new_related.append(g)
            continue
        inst = g["legislation_id"]
        made_date = (made or {}).get(inst)
        entries = []
        for entry in g["changes"]:
            if not isinstance(entry, dict):
                entries.append(entry)
                continue
            by = entry.get("by")
            changed = entry.get("changed") if isinstance(entry.get("changed"), list) else []
            buckets: dict = {}
            undated = []
            for ch in changed:
                relations += 1
                dates = idx.get((_norm(ch), inst, _norm(by))) if ch and by else None
                if not dates:
                    undated.append(ch)
                    continue
                if not made_date:
                    undated.append(ch)
                    if inst not in unchecked_by:
                        unchecked_by.append(inst)
                    continue
                ok = sorted(d for d in dates if d[0] >= made_date)
                if not ok:
                    refused += 1
                    undated.append(ch)
                    if inst not in refused_by:
                        refused_by.append(inst)
                    continue
                dated += 1
                for d in ok:
                    buckets.setdefault(d, []).append(ch)
            for (date, qual) in sorted(buckets):
                e = {"by": by, "changed": buckets[(date, qual)], "in_force": date}
                if qual:
                    e["qualification"] = qual
                entries.append(e)
            if undated or not buckets:
                entries.append({**entry, "changed": undated})
        new_related.append({**g, "changes": entries})
    out["related"] = new_related
    status = {
        "status": "retrieved",
        "source": DATE_SOURCE,
        "relations": relations,
        "dated": dated,
        "refused": refused,
    }
    if refused_by:
        status["refused_instruments"] = refused_by
    if unchecked_by:
        status["made_date_not_read"] = unchecked_by
    if feed.get("total") is not None and feed.get("read", 0) < feed["total"]:
        status["feed_window"] = {"read": feed.get("read", 0), "total": feed["total"]}
    out["commencement_dates"] = status
    return out


# ---------------------------------------------------------------------------
# the hop
# ---------------------------------------------------------------------------

def _request_memo() -> dict:
    """The per-request memo: ``{"feed": {subject: task}, "made": {id: task}}``."""
    try:
        cfg = get_request_provider_config()
    except Exception:
        cfg = None
    if not isinstance(cfg, dict) or not cfg:
        return {"feed": {}, "made": {}}
    memo = cfg.get(MEMO_KEY)
    if not isinstance(memo, dict):
        memo = {"feed": {}, "made": {}}
        cfg[MEMO_KEY] = memo
    return memo


def _reserved(table: dict, key: str, make) -> "asyncio.Future":
    """The memo slot for `key`, reserved BEFORE any await (P3.12's lesson, batch
    8 A2): two calls in one batched round share one fetch instead of making two."""
    task = table.get(key)
    if task is None:
        task = asyncio.ensure_future(make())
        table[key] = task
    return task


def _make_client() -> httpx.AsyncClient:
    """The hop's HTTP client: one attempt per read, `HOP_TIMEOUT_S` on every
    phase, no retry (the decided bound; `_request_with_retry` would multiply
    it)."""
    return httpx.AsyncClient(timeout=HOP_TIMEOUT_S, verify=False)


def _client() -> httpx.AsyncClient:
    """The seam tests replace: no test may reach the network (`conftest.py`)."""
    return _make_client()


async def _get(client: httpx.AsyncClient, url: str, call_id: str, on_chunk,
               timing_collector, tool_name: str, parse, summary) -> tuple:
    """One GET through the proxy, parsed, and recorded on the audit by size and
    by what was read from it, never by body.

    Returns ``(parsed_or_None, reason_or_None)``; never raises. `reason` is
    ``"no_reply"`` (no answer within `HOP_TIMEOUT_S`), ``"http_<status>"``,
    ``"unreadable"`` (a 200 that `parse` rejected: an error page, or not XML)
    or ``"error"``. Not "timeout": the reason reaches the model, and
    `replay_report`'s `HALT_AS_TIMEOUT` reads answers for that word.
    """
    await _emit(on_chunk, {"type": "api_call_start", "id": call_id, "url": url,
                           "method": "GET", "payload": None})
    t0 = time.perf_counter()
    status, parsed, reason, body_len = None, None, None, 0
    try:
        resp = await client.get(url)
        status = resp.status_code
        body_len = len(resp.content)
        if status == 200:
            try:
                parsed = parse(resp.text)
            except ValueError as e:
                reason = "unreadable"
                logger.info(f"[Worker Tool Exec] commencement-date read unusable: {e}")
        else:
            reason = f"http_{status}"
    except httpx.TimeoutException:
        reason = "no_reply"
    except Exception as e:  # noqa: BLE001 - fail-soft
        logger.warning(f"[Worker Tool Exec] commencement-date read failed: {e!r}")
        reason = "error"
    elapsed_ms = (time.perf_counter() - t0) * 1000
    if timing_collector:
        try:
            timing_collector.record_lex_api_call(tool_name, elapsed_ms)
        except Exception:
            pass
    info = {"bytes": body_len}
    if reason:
        info["error"] = reason
    else:
        info.update(summary(parsed))
    await _emit(on_chunk, {"type": "api_call_end", "id": call_id, "url": url,
                           "status": status, "response": info,
                           "elapsed_ms": round(elapsed_ms)})
    return parsed, reason


def _feed_summary(p: dict) -> dict:
    return {"effects": len(p["effects"]), "total": p["total"], "page": p["page"],
            "total_pages": p["total_pages"]}


def _made_summary(made: Optional[str]) -> dict:
    return {"made": made}


async def _read_feed(subject: str, call_id: str, on_chunk, timing_collector,
                     tool_name: str) -> dict:
    """At most `MAX_FEED_PAGES` pages of the subject's affected feed, in order.
    A failed first page fails the hop; a failed later page leaves the pages
    already read standing, and the window is stated."""
    effects, total, read_pages = [], None, 0
    async with _client() as client:
        for page in range(1, MAX_FEED_PAGES + 1):
            parsed, reason = await _get(
                client, proxy_url(feed_path(subject, page)), f"{call_id}-lgu-feed-p{page}",
                on_chunk, timing_collector, tool_name, parse_effects_feed, _feed_summary)
            if reason:
                if page == 1:
                    return {"status": "failed", "reason": reason}
                break
            effects.extend(parsed["effects"])
            total = parsed["total"]
            read_pages = page
            if not parsed["total_pages"] or page >= parsed["total_pages"]:
                break
    return {"status": "ok", "effects": effects,
            "total": total if total is not None else len(effects),
            "read": len(effects), "pages": read_pages}


# Made dates already read, for the life of the process. A made date never
# changes, so a date read once is the date; only a successful read is kept
# (a failure is retried by the next request that needs it), and the store is
# bounded. Batch 9 C's live smoke: 3 of 10 made-date reads through the proxy
# took longer than 8 s, and each such failure leaves an instrument's dates
# ungiven, so a date read once is not read again.
_MADE_CACHE: dict = {}
_MADE_CACHE_MAX = 4096


def _cache_made(instrument: str, made: Optional[str]) -> None:
    if made and _ISO_DATE.match(made):
        if len(_MADE_CACHE) >= _MADE_CACHE_MAX:
            _MADE_CACHE.pop(next(iter(_MADE_CACHE)))
        _MADE_CACHE[instrument] = made


async def _read_made(instrument: str, call_id: str, on_chunk, timing_collector,
                     tool_name: str, gate: asyncio.Semaphore) -> Optional[str]:
    """The instrument's made date, or None (not stated, or not read)."""
    async with gate:
        async with _client() as client:
            made, reason = await _get(
                client, proxy_url(introduction_path(instrument)),
                f"{call_id}-made-{_short_legislation_id(instrument).replace('/', '-')}",
                on_chunk, timing_collector, tool_name, parse_made_date, _made_summary)
    if reason:
        return None
    _cache_made(instrument, made)
    return made


async def add_commencement_dates(
    slimmed: Any,
    *,
    on_chunk: Optional[Callable] = None,
    timing_collector=None,
    call_id: str = "",
    tool_name: str = "get_legislation_changes",
) -> Any:
    """Run the hop for one slimmed change record, or return it untouched.

    Untouched (no ``commencement_dates`` key) where there is nothing to date:
    not our shape, direction ``"by"``, or no listed commencement by another
    instrument. Never raises: on any failure the record comes back as it was,
    with ``commencement_dates`` saying the dates were not retrieved.
    """
    try:
        if not isinstance(slimmed, dict) or "relations" not in slimmed:
            return slimmed
        groups = commencing_groups(slimmed)
        subject = _short_legislation_id(str(slimmed.get("legislation_id") or ""))
        if not groups or not _SAFE_ID.match(subject):
            return slimmed
        call_id = call_id or str(uuid.uuid4())
        memo = _request_memo()
        gate = asyncio.Semaphore(_CONCURRENCY)
        feed_task = _reserved(memo["feed"], subject, lambda: _read_feed(
            subject, call_id, on_chunk, timing_collector, tool_name))
        instruments = [i for i in commencing_instruments(slimmed)
                       if _SAFE_ID.match(_short_legislation_id(i))]
        # The cap is on READS: an instrument whose made date this process
        # already holds costs none, so it is checked however far down it is.
        made, made_tasks, reads = {}, {}, 0
        for inst in instruments:
            if inst in _MADE_CACHE:
                made[inst] = _MADE_CACHE[inst]
            elif inst in memo["made"] or reads < MAX_MADE_DATE_READS:
                if inst not in memo["made"]:
                    reads += 1
                made_tasks[inst] = _reserved(memo["made"], inst, lambda inst=inst: _read_made(
                    inst, call_id, on_chunk, timing_collector, tool_name, gate))
        feed = await asyncio.shield(feed_task)
        for inst, task in made_tasks.items():
            try:
                made[inst] = await asyncio.shield(task)
            except Exception:
                made[inst] = None
        return apply_dates(slimmed, feed, made)
    except asyncio.CancelledError:
        raise
    except Exception as e:  # noqa: BLE001 - fail-soft (Invariant 5)
        logger.warning(f"[Worker Tool Exec] commencement dates not added: {e!r}")
        try:
            out = dict(slimmed)
            out["commencement_dates"] = {"status": "not_retrieved", "reason": "error"}
            return out
        except Exception:
            return slimmed
