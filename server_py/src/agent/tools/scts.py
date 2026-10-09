"""Scottish case law: the Scottish Courts and Tribunals Service judgments search (FIX_PLAN P3.20).

The National Archives' Find Case Law holds no decision of the Court of
Session, the Sheriff Appeal Court, the Sheriff Courts or the High Court of
Justiciary (P5.2), and a Scots-law question came back with English authority
the model then answered from (P3.20's row). SCTS publishes those courts' judgments
through the JSON backend of its judgments search page,
`POST https://api.pa.web.scotcourts.gov.uk/web/search`, with each judgment a
PDF on `https://www.scotcourts.gov.uk`. It is not a published contract (the
page's client is `1.0.0-beta.1`); SCTS agreed to its use by phone
(2026-10-08) and the content is Crown copyright under the Open Government
Licence. Probe detail: `docs/LEGAL_DATA_SOURCES.md` section 3 and
`docs/prepilot-fixes/notes/batch11_D.md`.

**Off unless `settings.scts_caselaw_enabled`** (`scts_enabled`): both hosts
must be whitelisted on the target first. With it off nothing here is called
and every case-law text is what it was before P3.20.

The design, decided by the user on 2026-10-09 (P3.20's row):

* `search_case_law` searches both databases and returns two lists, `results`
  (Find Case Law, unchanged) and `scottish_results` (here). Coverage is code's
  job, not the prompt's (Invariant 2).
* **Every phrase and every word is required.** SCTS's search treats unquoted
  words as OR (an Act's title unquoted matched 12,712 of 13,222 judgments); a
  leading `+` makes a term or quoted phrase required. `AND` is not an operator
  and `-` BROADENS (it matches every document without the term), so neither
  is ever sent. When the all-terms search returns nothing, ONE code fallback
  runs the same terms in any-term form, and the window note says so (17 of 33
  stored Scots-law queries returned 0 when every term was required).
* `additionalDate` is the date of decision (the printed date in 36 of 40
  sampled PDFs). A neutral citation's year can be later (the year of
  publication), so **no date is ever taken from a citation**.
* Rows can repeat: deduped on `documentLink`.
* A per-request cap on SCTS calls and a small process-wide concurrency limit,
  both in code, every call through `_request_with_retry`. SCTS stated no rate
  limit.
* The PDF is parsed with pdfplumber (already a dependency; 40 of 40 sampled,
  median 0.46 s) **off the event loop**, because it is synchronous. No pypdf.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import re
import time
import weakref
from typing import Callable, Optional
from urllib.parse import urlparse

import httpx

from ..provider_factory import get_request_provider_config
from ._util import _emit

logger = logging.getLogger("agent")

SCTS_SEARCH_URL = "https://api.pa.web.scotcourts.gov.uk/web/search"
SCTS_SITE_HOST = "www.scotcourts.gov.uk"
SCTS_SITE = f"https://{SCTS_SITE_HOST}"

# Rows asked for per search. About 2.5K characters slimmed at 10 rows (batch
# 11 D), against Find Case Law's 50; the Scottish list is a second list beside
# that one, and the window note says when more match.
SCTS_PAGE_SIZE = 10

# Per request (one `/api/chat` turn, every Worker and Deep Research step in
# it). Measured over the 66 stored replay directories: a turn made at most 46
# case-law searches (a Deep Research turn), p99 29, p90 11; each SCTS
# search is one call plus at most one fallback. Text fetches: at most 21 a
# turn, p99 18. A search past the cap is not made and says so.
SCTS_MAX_SEARCH_CALLS = 60
SCTS_MAX_PDF_CALLS = 20
# Process-wide: at most this many SCTS calls in flight at once, across every
# request, so parallel Workers cannot burst the host.
SCTS_CONCURRENCY = 2

SCTS_SEARCH_TIMEOUT_S = 15.0
SCTS_PDF_TIMEOUT_S = 30.0
# The sampled PDFs ran 108-624 KB and 2-36 pages.
SCTS_PDF_MAX_BYTES = 15_000_000
SCTS_PDF_MAX_PAGES = 300

_HEADERS = {
    "User-Agent": "AILA legal research assistant (capped, paced)",
    "Accept": "application/json",
}

SCTS_TOOL_STATUS_OK = "ok"
SCTS_TOOL_STATUS_ERROR = "error"
SCTS_TOOL_STATUS_CAPPED = "capped"
SCTS_TOOL_STATUS_NOT_SEARCHED = "not_searched"

CASE_LAW_TYPES = ("case_law_only", "legislation_and_case_law")


def scts_enabled(research_mode: Optional[str] = None) -> bool:
    """The one gate: the setting on, and (when given) a research type that
    searches case law. Never raises; anything unexpected is off."""
    try:
        from ...config import settings
        if not bool(getattr(settings, "scts_caselaw_enabled", False)):
            return False
    except Exception:  # noqa: BLE001 - fail closed
        return False
    return research_mode is None or research_mode in CASE_LAW_TYPES


def scts_enabled_for_request() -> bool:
    """`scts_enabled` for the research type of the current request."""
    try:
        cfg = get_request_provider_config() or {}
        return scts_enabled(cfg.get("_research_mode"))
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# The query: every phrase and word required, and the any-term fallback
# ---------------------------------------------------------------------------

_TOKEN = re.compile(r'"([^"]*)"|(\S+)')
# Characters that are operators or syntax in SCTS's search. A word holding one
# inside it ("3(2)(a)", "and/or", "common-interest") is sent as a phrase, so
# its pieces must sit together; at either end they are trimmed.
_SYNTAX = re.compile(r"[\[\]\(\)\+\|\-\*\"{}~^:\\/!]")
_EDGE = "+-|*~^:!,.;[](){}\\/\"'"


def _clean_phrase(text: str) -> str:
    for ch in '[]()"':
        text = text.replace(ch, " ")
    return re.sub(r"\s+", " ", text).strip()


# A negated term (`-word`, `-"a phrase"`) is DROPPED, never sent: SCTS reads
# `-` as "any document without it", which broadens the search, and stripping
# the `-` alone would make the excluded term required, the opposite of what was
# asked. `NOT x` drops x for the same reason. No stored query held either form
# (census over 1,580 stored case-law searches); this is for the forms none used.
_NEGATED = re.compile(r'(?:(?<=\s)|^)-(?:"[^"]*"|\S+)')


def query_items(query: str) -> list:
    """The query as `[(kind, text)]`, kind 'phrase', 'word' or 'OR'."""
    out = []
    skip_next = False
    for m in _TOKEN.finditer(_NEGATED.sub(" ", query or "")):
        if skip_next:
            skip_next = False
            continue
        if m.group(1) is not None:
            phrase = _clean_phrase(m.group(1))
            if phrase:
                out.append(("phrase", phrase))
            continue
        word = m.group(2)
        if word == "OR":
            out.append(("OR", "OR"))
            continue
        if word == "NOT":
            skip_next = True
            continue
        if word == "AND":
            continue
        word = word.strip(_EDGE)
        if not word:
            continue
        if _SYNTAX.search(word):
            phrase = _clean_phrase(word)
            if phrase:
                out.append(("phrase", phrase))
        else:
            out.append(("word", word))
    return out


def _terms(items: list) -> list:
    """Group the items into terms: each a list of alternatives (an `a OR b`
    run is one term of two alternatives)."""
    terms, i = [], 0
    while i < len(items):
        kind, text = items[i]
        if kind == "OR":
            i += 1
            continue
        alt = [text if kind == "word" else f'"{text}"']
        while i + 2 < len(items) and items[i + 1][0] == "OR" and items[i + 2][0] != "OR":
            k2, t2 = items[i + 2]
            alt.append(t2 if k2 == "word" else f'"{t2}"')
            i += 2
        terms.append(alt)
        i += 1
    return terms


def scts_query_forms(query: str) -> tuple:
    """`(required, any_term)`: the two query strings the search may send.

    `required` puts `+` before every term (an `a OR b` run becomes `+(a | b)`);
    `any_term` is the same terms with no `+`, which SCTS reads as any-term.
    `any_term` is "" when it would match exactly what `required` matched (a
    single term with no alternatives), so no fallback is made for it. Both are
    "" when nothing searchable is left.
    """
    terms = _terms(query_items(query))
    if not terms:
        return "", ""
    required = " ".join(
        f"+({' | '.join(t)})" if len(t) > 1 else f"+{t[0]}" for t in terms)
    if len(terms) == 1 and len(terms[0]) == 1:
        return required, ""
    any_term = " ".join(
        f"({' | '.join(t)})" if len(t) > 1 else t[0] for t in terms)
    return required, any_term


# ---------------------------------------------------------------------------
# Neutral citations: from the filename, or from the opening of the text
# ---------------------------------------------------------------------------
#
# SCTS has no citation field. Newer PDF filenames start with one
# (`2017csih28-…`, `2026sacciv63-…`, `2025scgla002-…`, `2026ut59-…`); older ones
# carry a court reference instead (`p1333_02-…`). The text carries it in its
# opening for 31 of the 34 sampled judgments decided from 2005. A citation is
# a citation only: never a date (its year can be the year of publication).

_FILENAME_NCN = re.compile(
    r"^(19\d\d|20\d\d)(csoh|csih|hcjac|hcj|sacciv|saccrim|ut|sc[a-z]{3,4})(\d+)(?=[-_.]|$)")
_FILENAME_COURT = {
    "csoh": "CSOH", "csih": "CSIH", "hcjac": "HCJAC", "hcj": "HCJ",
    "sacciv": "SAC (Civ)", "saccrim": "SAC (Crim)", "ut": "UT",
}
_TEXT_NCN = re.compile(
    r"\[\s*(19\d\d|20\d\d)\s*\]\s*(CSOH|CSIH|HCJAC|HCJ|SAC\s*\((?:Civ|Crim)\)|SC\s*[A-Z]{2,5}|UT|SAC)"
    r"\s*(\d+)\b")
_NCN_HEAD_CHARS = 4000


def ncn_from_filename(link: str) -> Optional[str]:
    """`[YYYY] COURT N` from a `documentLink` filename that starts with one, else None."""
    name = (link or "").rsplit("/", 1)[-1].lower()
    m = _FILENAME_NCN.match(name)
    if not m:
        return None
    year, court, num = m.group(1), m.group(2), int(m.group(3))
    label = _FILENAME_COURT.get(court) or ("SC " + court[2:].upper())
    return f"[{year}] {label} {num}"


def ncn_from_text(text: str) -> Optional[str]:
    """The first neutral citation printed in the opening of a judgment, else None."""
    m = _TEXT_NCN.search((text or "")[:_NCN_HEAD_CHARS])
    if not m:
        return None
    court = re.sub(r"\s+", " ", m.group(2)).replace("( ", "(")
    court = re.sub(r"^SAC\s*\(", "SAC (", court)
    return f"[{m.group(1)}] {court} {int(m.group(3))}"


# ---------------------------------------------------------------------------
# The result rows
# ---------------------------------------------------------------------------

def _iso_date(value) -> Optional[str]:
    s = str(value or "").strip()
    m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
    return m.group(1) if m else None


def judgment_url(link: str) -> str:
    link = str(link or "").strip()
    if link.startswith(("http://", "https://")):
        return link
    return SCTS_SITE + (link if link.startswith("/") else "/" + link)


def slim_scts_results(body) -> list:
    """The rows the Worker sees, deduped on `documentLink` (rows repeat: 354
    rows held 352 distinct judgments). `decision_date` is SCTS's
    `additionalDate`; `published` its `date`; `ncn` only from a filename that
    starts with a citation. `sheriffdom`, `tags` and `searchType` are dropped
    (empty or constant in every row seen)."""
    rows = body.get("results") if isinstance(body, dict) else None
    out, seen = [], set()
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict):
            continue
        link = str(r.get("documentLink") or "").strip()
        if not link or link in seen:
            continue
        seen.add(link)
        court = r.get("court")
        if isinstance(court, list):
            court = ", ".join(str(c).strip() for c in court if str(c).strip())
        judges = r.get("judges")
        out.append({
            "title": str(r.get("title") or "").strip(),
            "court": str(court or "").strip(),
            "judges": [str(j).strip() for j in judges if str(j).strip()]
            if isinstance(judges, list) else [],
            "decision_date": _iso_date(r.get("additionalDate")),
            "published": _iso_date(r.get("date")),
            "ncn": ncn_from_filename(link),
            "url": judgment_url(link),
        })
    return out


def _total(body) -> Optional[int]:
    try:
        t = body["pagination"]["count"]["total"]
        return int(t) if t is not None else None
    except (KeyError, TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Per-request cap, process-wide concurrency
# ---------------------------------------------------------------------------

def request_state() -> dict:
    """This request's SCTS counters and the titles of the judgments its
    searches returned (for the text fetch), kept on the request's config dict,
    which every Worker and step of one request shares. Without a request
    config (a script, a test) each call gets a fresh, uncounted state."""
    cfg = get_request_provider_config()
    if not isinstance(cfg, dict) or not cfg:
        return {"search_calls": 0, "pdf_calls": 0, "titles": {}}
    state = cfg.get("_scts_state")
    if not isinstance(state, dict):
        state = {"search_calls": 0, "pdf_calls": 0, "titles": {}}
        cfg["_scts_state"] = state
    return state


_SEMAPHORES: "weakref.WeakKeyDictionary" = weakref.WeakKeyDictionary()


def _semaphore() -> asyncio.Semaphore:
    """One semaphore per event loop (a semaphore is bound to the loop it first
    waits on, and tests run several loops)."""
    loop = asyncio.get_running_loop()
    sem = _SEMAPHORES.get(loop)
    if sem is None:
        sem = asyncio.Semaphore(SCTS_CONCURRENCY)
        _SEMAPHORES[loop] = sem
    return sem


# ---------------------------------------------------------------------------
# The search
# ---------------------------------------------------------------------------

def _search_body(query: str, dates: Optional[dict]) -> dict:
    filters = []
    if dates and (dates.get("from") or dates.get("to")):
        filters.append({"field": "AdditionalDate",
                        "value": f"{dates.get('from') or ''}|{dates.get('to') or ''}"})
    return {"query": query, "filters": filters, "page": 1, "limit": SCTS_PAGE_SIZE,
            "indexType": "Judgments", "category": ""}


async def _post_search(client: httpx.AsyncClient, body: dict, *, on_chunk, call_id: str,
                       timing_collector, tool_name: str):
    """One search call, counted and paced. Returns the parsed body, or None on
    any failure (logged)."""
    from .executor import _request_with_retry  # executor imports this module

    state = request_state()
    state["search_calls"] = state.get("search_calls", 0) + 1
    await _emit(on_chunk, {"type": "api_call_start", "id": call_id, "url": SCTS_SEARCH_URL,
                           "method": "POST", "payload": body})
    t0 = time.perf_counter()
    status, parsed = None, None
    try:
        async with _semaphore():
            resp = await _request_with_retry(
                client, "POST", SCTS_SEARCH_URL, name=tool_name, json=body,
                headers=_HEADERS, timeout=SCTS_SEARCH_TIMEOUT_S)
        status = resp.status_code
        try:
            parsed = resp.json()
        except ValueError:
            parsed = None
    except Exception as e:  # noqa: BLE001 - fail-soft, reported as an error
        logger.warning(f"[Worker Tool Exec] SCTS search failed: {e!r}")
    elapsed_ms = (time.perf_counter() - t0) * 1000
    if timing_collector:
        timing_collector.record_lex_api_call(tool_name, elapsed_ms)
    rows = parsed.get("results") if isinstance(parsed, dict) else None
    await _emit(on_chunk, {
        "type": "api_call_end", "id": call_id, "url": SCTS_SEARCH_URL, "status": status,
        "response": {"total": _total(parsed),
                     "rows": len(rows) if isinstance(rows, list) else None},
        "elapsed_ms": round(elapsed_ms),
    })
    if status != 200 or not isinstance(parsed, dict) or not isinstance(rows, list):
        return None
    return parsed


async def search_scts(query: str, dates: Optional[dict], client: httpx.AsyncClient, *,
                      on_chunk: Optional[Callable] = None, call_id: str = "",
                      timing_collector=None, tool_name: str = "search_case_law") -> dict:
    """The Scottish half of `search_case_law`: `{"results": [...], "block": {...}}`.

    `block["status"]` is "ok", "error", "capped" (this request's cap reached,
    no call made) or "not_searched" (nothing searchable in the query). Never
    raises: Find Case Law's half must survive anything that happens here.
    """
    required, any_term = scts_query_forms(query)
    block = {"status": SCTS_TOOL_STATUS_NOT_SEARCHED, "shown": 0, "total": 0,
             "total_exact": True, "match": None, "query_sent": None}
    if dates:
        block["dates"] = dates
    if not required:
        return {"results": [], "block": block}
    try:
        state = request_state()
        out_rows, body_sent = [], None
        for match, q in (("all", required), ("any", any_term)):
            if not q:
                break
            if state.get("search_calls", 0) >= SCTS_MAX_SEARCH_CALLS:
                if match == "all":
                    block.update(status=SCTS_TOOL_STATUS_CAPPED, cap=SCTS_MAX_SEARCH_CALLS)
                    return {"results": [], "block": block}
                break   # the fallback is not made past the cap; the zero stands
            body_sent = _search_body(q, dates)
            parsed = await _post_search(
                client, body_sent, on_chunk=on_chunk,
                call_id=f"{call_id}-scts" + ("" if match == "all" else "-any"),
                timing_collector=timing_collector, tool_name=tool_name)
            if parsed is None:
                if match == "all":
                    block.update(status=SCTS_TOOL_STATUS_ERROR, query_sent=q)
                    return {"results": [], "block": block}
                break   # a failed fallback leaves the all-terms zero as the answer
            rows = slim_scts_results(parsed)
            total = _total(parsed)
            if total is None or total < len(rows):
                total = len(rows)
            # A page that is not full is the whole matching set: count the
            # distinct rows, not the repeated ones the total includes.
            if total <= SCTS_PAGE_SIZE:
                total = len(rows)
            block.update(status=SCTS_TOOL_STATUS_OK, shown=len(rows), total=total,
                         total_exact=True, match=match, query_sent=q)
            out_rows = rows
            if rows:
                break
        titles = state.setdefault("titles", {})
        for r in out_rows:
            titles[r["url"]] = {"title": r["title"], "court": r["court"],
                                "decision_date": r["decision_date"]}
        return {"results": out_rows, "block": block}
    except Exception as e:  # noqa: BLE001 - fail-soft
        logger.warning(f"[Worker Tool Exec] SCTS search failed: {e!r}")
        block.update(status=SCTS_TOOL_STATUS_ERROR)
        return {"results": [], "block": block}


# ---------------------------------------------------------------------------
# The judgment text
# ---------------------------------------------------------------------------

def is_scts_judgment_url(url: str) -> bool:
    """An https PDF on SCTS's site: the only URL the Scottish text route fetches."""
    try:
        p = urlparse(str(url or "").strip())
    except ValueError:
        return False
    return (p.scheme == "https" and p.hostname == SCTS_SITE_HOST
            and p.path.lower().endswith(".pdf") and not p.query)


def _pdf_text(data: bytes, max_pages: int = SCTS_PDF_MAX_PAGES) -> str:
    """The text of every page, joined (synchronous; run it in a thread)."""
    import pdfplumber  # a dependency (requirements.txt); not in the offline bundle yet

    with pdfplumber.open(io.BytesIO(data)) as pdf:
        return "\n".join((page.extract_text() or "") for page in pdf.pages[:max_pages]).strip()


async def fetch_scts_judgment(url: str, client: httpx.AsyncClient, *,
                              on_chunk: Optional[Callable] = None, call_id: str = "",
                              timing_collector=None,
                              tool_name: str = "get_case_law_text") -> dict:
    """`{url, title, ncn, court, decision_date, text}`, or `{error, url, text: ""}`.
    Never raises."""
    from .executor import _request_with_retry  # executor imports this module

    state = request_state()
    if state.get("pdf_calls", 0) >= SCTS_MAX_PDF_CALLS:
        return {"error": (f"Not fetched: this request has already fetched "
                          f"{SCTS_MAX_PDF_CALLS} judgment texts from the Scottish Courts "
                          "and Tribunals Service, its limit. Work from the texts already "
                          "retrieved."),
                "url": url, "text": ""}
    state["pdf_calls"] = state.get("pdf_calls", 0) + 1
    known = (state.get("titles") or {}).get(url) or {}
    await _emit(on_chunk, {"type": "api_call_start", "id": call_id, "url": url,
                           "method": "GET", "payload": {}})
    t0 = time.perf_counter()
    status, data, text, error = None, b"", "", None
    try:
        async with _semaphore():
            resp = await _request_with_retry(
                client, "GET", url, name=tool_name, headers={**_HEADERS, "Accept": "application/pdf"},
                timeout=SCTS_PDF_TIMEOUT_S, follow_redirects=False)
        status = resp.status_code
        data = resp.content or b""
        if status != 200:
            error = f"HTTP {status} fetching judgment"
        elif len(data) > SCTS_PDF_MAX_BYTES:
            error = f"Judgment PDF too large to read ({len(data):,} bytes)"
        elif not data.startswith(b"%PDF"):
            error = "The judgment URL did not return a PDF"
        else:
            text = await asyncio.to_thread(_pdf_text, data)
            if not text:
                error = "No text could be read from the judgment PDF"
    except Exception as e:  # noqa: BLE001 - fail-soft
        error = f"Could not read the judgment: {type(e).__name__}"
        logger.warning(f"[Worker Tool Exec] SCTS judgment fetch failed: {e!r}")
    elapsed_ms = (time.perf_counter() - t0) * 1000
    if timing_collector:
        timing_collector.record_lex_api_call(tool_name, elapsed_ms)
    await _emit(on_chunk, {
        "type": "api_call_end", "id": call_id, "url": url, "status": status,
        "response": {"pdf_bytes": len(data), "text_chars": len(text),
                     "preview": text[:300]},
        "elapsed_ms": round(elapsed_ms),
    })
    if error:
        return {"error": error, "url": url, "text": ""}
    out = {"url": url, "title": known.get("title") or "",
           "ncn": ncn_from_text(text) or ncn_from_filename(urlparse(url).path) or "",
           "text": text}
    if known.get("court"):
        out["court"] = known["court"]
    if known.get("decision_date"):
        out["decision_date"] = known["decision_date"]
    return out


def scottish_block_of(data) -> Optional[dict]:
    """The `scottish` block of a `search_case_law` result, or None (the gate
    was off, or the result is not one)."""
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (ValueError, TypeError):
            return None
    if not isinstance(data, dict):
        return None
    block = data.get("scottish")
    return block if isinstance(block, dict) else None
