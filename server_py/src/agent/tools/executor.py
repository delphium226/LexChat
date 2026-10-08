"""Worker tool executor for the legislation/case-law research modes."""

import asyncio
import json
import logging
import random
import time
import uuid
from typing import Callable, Optional

import httpx

from ...config import settings
from ...utils.instrument_lookup import (
    HELD,
    HELD_WITHOUT_TEXT,
    INVALID,
    LOOKUP_FAILED,
    LOOKUP_TOOL,
    NOT_HELD,
    citation_label,
    legislation_id as lookup_legislation_id,
    lookup_args,
)
from ...utils.made_under import MADE_UNDER_TOOL
from ...utils.redact import redact_args
from ...utils import schedule_units
from ..provider_factory import get_request_provider_config
from ._util import _emit
from .caselaw import (
    CASE_LAW_ORDER_PARAMS,
    _fetch_judgment_text,
    _parse_case_law_atom,
    case_law_count,
    case_law_date_window,
)
from .commencement_dates import add_commencement_dates
from .lex import (
    LEX_API_URL,
    _TYPE_CODES,
    _matches_jurisdiction,
    _slim_amendment_results,
    _slim_search_results,
    _slim_section_results,
    extract_legislation_ids_from_search,
)

logger = logging.getLogger("agent")

# How many legislation search results reach the model. Deliberate slimming, not
# a filter: the API is asked for 20 and the top few carry the signal, while the
# rest cost context. Named because the number matters to anyone measuring filter
# loss — a search returning exactly this many is cap-bound and says nothing
# about whether the filters removed anything (see `tools/replay_report.py`).
_MAX_SEARCH_RESULTS = 5

# P3.5: the two `size` values `get_legislation_changes` asks `/amendment/search`
# for. `size` silently truncates and the response carries no count field, so the
# only way to know a result is complete is to ask for more than it holds. The
# first value covers 95% of the instruments the replay corpus touches; the
# second completes every one of the remaining 13 (largest 5,185 rows) and the
# pathological `ukpga/1988/1` (13,681) besides. A second bind is reported, not
# chased — see the branch for the measurements.
_AMENDMENT_FETCH_SIZE = 2000
_AMENDMENT_ESCALATED_SIZE = 20000

# -----------------------------------------------------------------------
# Retry / backoff for the (rate-limited) LEX API
# -----------------------------------------------------------------------
# The LEX API is rate limited and the deployment shares a single outbound IP
# across all users, so under load a burst of worker calls can draw a 429. Without
# a retry the 429 surfaces as raise_for_status() -> a dropped retrieval -> a
# silently incomplete answer. These retryable statuses get a bounded exponential
# backoff (honouring Retry-After); everything else returns to the caller unchanged.
_RETRY_STATUS = {429, 502, 503, 504}
_MAX_RETRIES = 3            # up to 3 retries => 4 attempts total
_BASE_BACKOFF_S = 0.5       # computed backoff: 0.5s, 1s, 2s (+ jitter), capped
_MAX_BACKOFF_S = 8.0        # cap on computed exponential backoff
_MAX_RETRY_AFTER_S = 30.0   # cap on an honoured server Retry-After value


def _retry_after_seconds(resp: httpx.Response) -> Optional[float]:
    """Parse a Retry-After header (delta-seconds or HTTP-date) into seconds, if present."""
    raw = (resp.headers.get("Retry-After") or "").strip()
    if not raw:
        return None
    if raw.isdigit():
        return float(raw)
    try:
        from datetime import datetime, timezone
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(raw)
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (dt - datetime.now(timezone.utc)).total_seconds())
    except Exception:
        return None


def _backoff_delay(attempt: int) -> float:
    """Exponential backoff for the given 0-based attempt, capped, with jitter."""
    delay = min(_BASE_BACKOFF_S * (2 ** attempt), _MAX_BACKOFF_S)
    return delay + random.uniform(0, delay * 0.25)


async def _request_with_retry(
    client: httpx.AsyncClient, method: str, url: str, *, name: str = "", **kwargs
) -> httpx.Response:
    """Issue an httpx request with bounded backoff on 429 / transient 5xx.

    Honours Retry-After on rate-limit responses; falls back to exponential backoff
    otherwise. Network-level errors (timeouts, transport errors) are retried too.
    Returns the final response — the caller still handles non-retryable statuses
    (e.g. the case-law 400) and calls raise_for_status() as before. Retries are
    exhausted quietly (the last response/exception is returned/raised) so behaviour
    on a persistent failure is identical to today, just later.
    """
    attempt = 0
    while True:
        try:
            resp = await client.request(method, url, **kwargs)
        except (httpx.TimeoutException, httpx.TransportError) as e:
            if attempt >= _MAX_RETRIES:
                raise
            delay = _backoff_delay(attempt)
            logger.warning(
                f"[LEX Retry] {name or url} network error ({e!r}); "
                f"retry {attempt + 1}/{_MAX_RETRIES} in {delay:.1f}s"
            )
            await asyncio.sleep(delay)
            attempt += 1
            continue

        if resp.status_code in _RETRY_STATUS and attempt < _MAX_RETRIES:
            ra = _retry_after_seconds(resp)
            delay = min(ra, _MAX_RETRY_AFTER_S) if ra is not None else _backoff_delay(attempt)
            logger.warning(
                f"[LEX Retry] {name or url} HTTP {resp.status_code}; "
                f"retry {attempt + 1}/{_MAX_RETRIES} in {delay:.1f}s"
                + (" (Retry-After)" if ra is not None else "")
            )
            await asyncio.sleep(delay)
            attempt += 1
            continue

        return resp


# -----------------------------------------------------------------------
# P3.12: one instrument's provision list, and its whole text, for code
# -----------------------------------------------------------------------
# `/legislation/section/lookup` with a `limit` above the provision count
# returns every provision with its text (batch 7 B, live: 674 of 674 for the
# largest Act the route fires on, 1.6 MB in 405 ms; a schedule is one row, and
# not the last, so a small `limit` cannot be used). Neither call is a tool the
# Worker can make: `agent_shared.run_worker_tool` calls them after a section
# search whose query names a schedule or annex unit its results left out. Each
# emits `api_call_start`/`api_call_end` on the caller's `on_chunk`, so the
# audit records it under that section search, with a size, not the payload.
PROVISION_LIST_LIMIT = 5000


async def fetch_provision_list(
    legislation_id: str, on_chunk: Optional[Callable] = None,
    timing_collector=None, tool_name: str = "search_legislation_sections",
) -> dict:
    """`{"status": "ok", "rows": [...], "complete": bool}`, `{"status":
    "no_text"}` (LEX's own "No sections found"), or `{"status": "failed"}`
    for anything else. Never raises."""
    url = f"{LEX_API_URL}/legislation/section/lookup"
    payload = {"legislation_id": legislation_id, "limit": PROVISION_LIST_LIMIT}
    call_id = f"{uuid.uuid4()}-provision-list"
    try:
        async with httpx.AsyncClient(timeout=60.0, verify=False) as client:
            await _emit(on_chunk, {"type": "api_call_start", "id": call_id, "url": url,
                                   "method": "POST", "payload": payload})
            t0 = time.perf_counter()
            resp = await _request_with_retry(client, "POST", url, name=tool_name, json=payload)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            if timing_collector:
                timing_collector.record_lex_api_call(tool_name, elapsed_ms)
            try:
                body = resp.json()
            except ValueError:
                body = None
            await _emit(on_chunk, {
                "type": "api_call_end", "id": call_id, "url": url,
                "status": resp.status_code,
                "response": {"provisions": len(body) if isinstance(body, list) else None},
                "elapsed_ms": round(elapsed_ms),
            })
    except Exception as e:  # noqa: BLE001 - fail-soft, reported as failed
        logger.warning(f"[Worker Tool Exec] provision list for {legislation_id} failed: {e!r}")
        return {"status": "failed"}
    if resp.status_code == 200 and isinstance(body, list):
        return {"status": "ok", "rows": body, "complete": len(body) < PROVISION_LIST_LIMIT}
    detail = str(body.get("detail") or "") if isinstance(body, dict) else ""
    if resp.status_code == 404 and detail.startswith("No sections found"):
        return {"status": "no_text"}
    return {"status": "failed"}


async def fetch_text_with_schedules(
    legislation_id: str, on_chunk: Optional[Callable] = None,
    timing_collector=None, tool_name: str = "search_legislation_sections",
) -> Optional[str]:
    """The instrument's whole text with its schedules appended (P3.27's flag),
    or None. P3.12's fallback when the provision list does not come back."""
    url = f"{LEX_API_URL}/legislation/text"
    payload = {"legislation_id": legislation_id, "include_schedules": True}
    call_id = f"{uuid.uuid4()}-text-with-schedules"
    try:
        async with httpx.AsyncClient(timeout=60.0, verify=False) as client:
            await _emit(on_chunk, {"type": "api_call_start", "id": call_id, "url": url,
                                   "method": "POST", "payload": payload})
            t0 = time.perf_counter()
            resp = await _request_with_retry(client, "POST", url, name=tool_name, json=payload)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            if timing_collector:
                timing_collector.record_lex_api_call(tool_name, elapsed_ms)
            text = schedule_units.full_text_of(resp.json()) if resp.status_code == 200 else None
            await _emit(on_chunk, {
                "type": "api_call_end", "id": call_id, "url": url,
                "status": resp.status_code,
                "response": {"full_text_chars": len(text) if text is not None else None},
                "elapsed_ms": round(elapsed_ms),
            })
            return text
    except Exception as e:  # noqa: BLE001 - fail-soft
        logger.warning(f"[Worker Tool Exec] text with schedules for {legislation_id} failed: {e!r}")
        return None


# -----------------------------------------------------------------------
# Tool execution (LEX API client)
# -----------------------------------------------------------------------


async def execute_worker_tool(
    name: str,
    args: dict,
    on_chunk: Optional[Callable] = None,
    timing_collector=None,
) -> str:
    """Execute a worker tool (LEX API call) and return JSON string result."""
    # Free-text arguments (`query` and friends) are redacted at INFO — they are
    # the user's own words, and on the drafting bot they can be a clause of
    # unpublished legislative text. Structural args (Act IDs, dates, filters)
    # stay in the clear, which is what makes the line useful. Full args remain
    # available at DEBUG (LOG_LEVEL) for local debugging.
    logger.info(f"[Worker Tool Exec] {name} with args: {json.dumps(redact_args(args))}")
    logger.debug(f"[Worker Tool Exec] {name} full args: {json.dumps(args)}")

    call_id = str(uuid.uuid4())

    try:
        # Disable SSL verification to support internal deployments with self-signed certs or SSL inspection
        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
            if name == "search_legislation":
                url = f"{LEX_API_URL}/legislation/search"
                cfg = get_request_provider_config()
                user_year_from = cfg.get("_year_from")
                user_year_to = cfg.get("_year_to")
                jurisdiction = cfg.get("_jurisdiction")
                legislation_type = cfg.get("_legislation_type")

                # Merge user filter with model-supplied year args (take intersection)
                model_year_from = args.get("year_from")
                model_year_to = args.get("year_to")
                if user_year_from and model_year_from:
                    final_year_from = max(user_year_from, model_year_from)
                else:
                    final_year_from = user_year_from or model_year_from
                if user_year_to and model_year_to:
                    final_year_to = min(user_year_to, model_year_to)
                else:
                    final_year_to = user_year_to or model_year_to

                needs_post_filter = bool(jurisdiction or legislation_type)
                payload = {
                    "query": args["query"],
                    "year_from": final_year_from,
                    "year_to": final_year_to,
                    # Over-fetch when post-filters are active so they have enough results to work with
                    "limit": 20 if needs_post_filter else 5,
                    "include_text": False,
                }

                await _emit(on_chunk, {
                    "type": "api_call_start",
                    "id": call_id,
                    "url": url,
                    "method": "POST",
                    "payload": payload
                })

                t0 = time.perf_counter()
                resp = await _request_with_retry(client, "POST", url, name=name, json=payload)
                elapsed_ms = (time.perf_counter() - t0) * 1000

                if timing_collector:
                    timing_collector.record_lex_api_call(name, elapsed_ms)

                # Emit result before raising error, to see what happened
                try:
                    resp_json = resp.json()
                except ValueError:
                    resp_json = {"text": resp.text}

                await _emit(on_chunk, {
                    "type": "api_call_end",
                    "id": call_id,
                    "url": url,
                    "status": resp.status_code,
                    "response": resp_json,
                    "elapsed_ms": round(elapsed_ms),
                })

                resp.raise_for_status()
                slimmed = _slim_search_results(resp_json)
                results = slimmed["results"]
                # How many rows the API actually handed us, before any
                # post-filter. `total` is the API's match count across the whole
                # corpus and is usually much larger than this page.
                api_returned = len(results)

                # Post-filter: legislation type (by legislation_id prefix)
                if legislation_type:
                    type_codes = _TYPE_CODES.get(legislation_type, set())
                    results = [
                        r for r in results
                        if r.get("legislation_id", "").split("/")[0] in type_codes
                    ]

                # Post-filter: jurisdiction (by extent field, with the
                # legislation id as a tie-break when extent is unknown — see
                # `_matches_jurisdiction`, which is why the id is passed).
                if jurisdiction:
                    results = [
                        r for r in results
                        if _matches_jurisdiction(
                            r.get("extent", []),
                            jurisdiction,
                            r.get("legislation_id", ""),
                        )
                    ]

                # P1.3 (bucket B5): report the three counts separately.
                #
                # This used to be `slimmed["total"] = len(results)`, which threw
                # away the API's real match count and left the model unable to
                # tell "5 instruments match your question" from "138 match and
                # your filters removed all but 5". Measured over the P0.3
                # baseline, 1,010 of 1,531 searches misreported `total` —
                # including 438 with no filter set at all, because the [:5] cap
                # alone was enough to destroy it.
                #
                # `total` is kept, still meaning the API's match count, so any
                # consumer reading it gets a truer number than before rather
                # than a differently-wrong one. The new keys are additive.
                matched = slimmed.get("total")
                after_filters = len(results)
                results = results[:_MAX_SEARCH_RESULTS]

                slimmed["results"] = results
                slimmed["returned"] = len(results)
                slimmed["total_matched"] = matched
                slimmed["removed_by_filters"] = max(0, api_returned - after_filters)
                slimmed["total"] = matched
                if slimmed["removed_by_filters"]:
                    slimmed["filters_applied"] = {
                        k: v for k, v in (
                            ("jurisdiction", jurisdiction),
                            ("legislation_type", legislation_type),
                        ) if v
                    }
                return json.dumps(slimmed)

            elif name == "search_legislation_sections":
                url = f"{LEX_API_URL}/legislation/section/search"
                payload = {
                    "query": args["query"],
                    "legislation_id": args["legislation_id"],
                    # P3.1: this endpoint's page-size parameter is `size`, not
                    # `limit` (`/openapi.json`, verified live 2026-09-18:
                    # `limit=3` returns 10 rows, `size=3` returns 3). `limit`
                    # was silently ignored and only happened to match the
                    # default of 10. Any change to the number must use `size`.
                    "size": 10,
                }

                await _emit(on_chunk, {
                    "type": "api_call_start",
                    "id": call_id,
                    "url": url,
                    "method": "POST",
                    "payload": payload,
                })

                t0 = time.perf_counter()
                resp = await _request_with_retry(client, "POST", url, name=name, json=payload)
                elapsed_ms = (time.perf_counter() - t0) * 1000

                if timing_collector:
                    timing_collector.record_lex_api_call(name, elapsed_ms)

                try:
                    resp_json = resp.json()
                except Exception:
                    resp_json = {"text": resp.text}

                await _emit(on_chunk, {
                    "type": "api_call_end",
                    "id": call_id,
                    "url": url,
                    "status": resp.status_code,
                    "response": resp_json,
                    "elapsed_ms": round(elapsed_ms),
                })

                resp.raise_for_status()
                # P1.4: slim to the fields the model needs, keeping the API's
                # own provision-level URL so citations link to the provision
                # rather than to the Act's contents page.
                return json.dumps(_slim_section_results(resp_json))

            elif name == "get_legislation_changes":
                # P3.5 (bucket B3): the relation itself, instead of a
                # prohibition on claiming it. See `_slim_amendment_results` for
                # what the feed actually looks like and why it cannot be passed
                # through raw.
                url = f"{LEX_API_URL}/amendment/search"
                direction = "by" if str(
                    args.get("direction") or ""
                ).strip().lower() == "by" else "to"
                legislation_id = args["legislation_id"]

                # **Fetch past the cap rather than misreport it (P1.3's lesson).**
                # `size` silently truncates and the response carries NO count
                # field of any kind, so a modest `size` under-reports the
                # relations with nothing to signal it — which is exactly the
                # windowing defect `search_legislation` had, where `total` was
                # misreported on 1,010 of 1,531 searches.
                #
                # Measured over the distinct legislation_ids the replay
                # corpus actually touched (272 at the last run): median 12
                # relation rows, p90 870, and **13 (4.8%) exceed 2,000** —
                # re-run with `python -m tools.lex_probe --commencement`, which
                # reads the ids out of the run files, so the median drifts as
                # the corpus grows while the 4.8% is what decided this value. Every one of those 13 completes at
                # `_ESCALATED_SIZE` (largest 5,185 rows / 5.3 MB / 2.3 s), so one
                # escalation on 5% of calls buys a true count on all of them.
                # A large `size` costs nothing when the relations are few — the
                # API returns what exists — so the only reason to start at 2,000
                # at all is to keep the pathological instrument (`ukpga/1988/1`,
                # 13,681 rows / 11.9 MB) off the common path.
                rows = []
                requested = _AMENDMENT_FETCH_SIZE
                for attempt, requested in enumerate(
                    (_AMENDMENT_FETCH_SIZE, _AMENDMENT_ESCALATED_SIZE)
                ):
                    # Two requests, two ids: the escalation is a second HTTP
                    # call and a trace that showed one would be wrong about what
                    # the run actually did.
                    this_id = call_id if not attempt else f"{call_id}-escalated"
                    payload = {
                        "legislation_id": legislation_id,
                        "search_amended": direction == "to",
                        "size": requested,
                    }

                    await _emit(on_chunk, {
                        "type": "api_call_start",
                        "id": this_id,
                        "url": url,
                        "method": "POST",
                        "payload": payload,
                    })

                    t0 = time.perf_counter()
                    resp = await _request_with_retry(
                        client, "POST", url, name=name, json=payload, timeout=120.0
                    )
                    elapsed_ms = (time.perf_counter() - t0) * 1000

                    if timing_collector:
                        timing_collector.record_lex_api_call(name, elapsed_ms)

                    try:
                        resp_json = resp.json()
                    except ValueError:
                        resp_json = {"text": resp.text}

                    await _emit(on_chunk, {
                        "type": "api_call_end",
                        "id": this_id,
                        "url": url,
                        "status": resp.status_code,
                        "response": resp_json,
                        "elapsed_ms": round(elapsed_ms),
                    })

                    resp.raise_for_status()
                    rows = resp_json
                    # Exactly `size` rows can only mean the cap bound. Escalate
                    # once; a second bind is reported rather than chased.
                    if not (isinstance(rows, list) and len(rows) >= requested):
                        break

                slimmed = _slim_amendment_results(rows, legislation_id, direction)
                # Stamped only on our own shape. An unexpected response passes
                # through the slimmer untouched, and marking it "complete" would
                # be a statement about a payload we did not understand.
                if isinstance(slimmed, dict) and "relations" in slimmed:
                    slimmed["window_complete"] = not (
                        isinstance(rows, list) and len(rows) >= requested
                    )
                    if not slimmed["window_complete"]:
                        slimmed["window_size"] = requested
                # P3.21: the date of each commencement made by another
                # instrument, from legislation.gov.uk's Changes to Legislation
                # record read through LEX's proxy (one feed per change record,
                # memoised per request, at most 2 pages, 8 s, fail-soft, no
                # date before the instrument's made date). A record with no such
                # relation, or direction "by", comes back untouched. See
                # `commencement_dates.py`.
                slimmed = await add_commencement_dates(
                    slimmed, on_chunk=on_chunk, timing_collector=timing_collector,
                    call_id=call_id, tool_name=name,
                )
                return json.dumps(slimmed)

            elif name == MADE_UNDER_TOOL:
                # P3.31: a DB read of the made-under record, no external call.
                from ...services.made_under_store import query as made_under_query
                result = await made_under_query(str(args.get("act") or ""),
                                                str(args.get("section") or ""))
                return json.dumps(result, ensure_ascii=False)

            elif name == LOOKUP_TOOL:
                # P3.7 (bucket B5): the one question a ranked search cannot
                # answer, "does the index hold this instrument?". See
                # `utils/instrument_lookup.py` for the three states and why a
                # 200 on its own does not mean the text is held.
                ref = lookup_args(args)
                if ref is None:
                    return json.dumps({
                        "tool": LOOKUP_TOOL, "status": INVALID,
                        "note": (
                            "Not looked up: pass legislation_type (e.g. 'ssi', 'uksi', "
                            "'asp', 'ukpga'), year and number, or a legislation_id such "
                            "as 'ssi/2025/377'. This says nothing about the index."
                        ),
                    })
                lid = lookup_legislation_id(ref)
                out = {"tool": LOOKUP_TOOL, "legislation_id": lid,
                       "label": citation_label(ref)}

                async def _post(path: str, payload: dict, suffix: str):
                    call = f"{call_id}{suffix}"
                    call_url = f"{LEX_API_URL}{path}"
                    await _emit(on_chunk, {
                        "type": "api_call_start", "id": call, "url": call_url,
                        "method": "POST", "payload": payload,
                    })
                    t0 = time.perf_counter()
                    resp = await _request_with_retry(
                        client, "POST", call_url, name=name, json=payload)
                    elapsed_ms = (time.perf_counter() - t0) * 1000
                    if timing_collector:
                        timing_collector.record_lex_api_call(name, elapsed_ms)
                    try:
                        body = resp.json()
                    except ValueError:
                        body = {"text": resp.text}
                    await _emit(on_chunk, {
                        "type": "api_call_end", "id": call, "url": call_url,
                        "status": resp.status_code, "response": body,
                        "elapsed_ms": round(elapsed_ms),
                    })
                    return resp.status_code, body

                def _detail(body) -> str:
                    return str(body.get("detail") or "") if isinstance(body, dict) else ""

                # A failure of either call is `lookup_failed`, never a negative:
                # only the API's own "not found" is evidence of absence
                # (Invariant 1).
                try:
                    status, record = await _post(
                        "/legislation/lookup",
                        {"legislation_type": ref[0], "year": ref[1], "number": ref[2]}, "")
                except (httpx.TimeoutException, httpx.TransportError) as e:
                    status, record = None, {"text": repr(e)}
                # The API's own sentence, not any 404: a route 404 (an endpoint
                # moved) says `{"detail": "Not Found"}`, and reading that as
                # not-held would tell a lawyer something false about every
                # instrument at once.
                if status == 404 and _detail(record).startswith("Legislation not found"):
                    out.update(status=NOT_HELD, http_status=404,
                               lex_detail=_detail(record)[:200])
                    return json.dumps(out)
                if status != 200 or not isinstance(record, dict):
                    out.update(status=LOOKUP_FAILED, http_status=status,
                               note="The lookup did not complete. This says nothing about "
                                    "whether the index holds the instrument; search for it "
                                    "as usual.")
                    return json.dumps(out)

                url = str(record.get("uri") or record.get("id") or "")
                if url.startswith("http://"):
                    url = "https://" + url[len("http://"):]
                out.update(
                    title=record.get("title"),
                    url=url or None,
                    category=record.get("category"),
                    enactment_date=record.get("enactment_date"),
                    # P3.25: the date the held text is stated to be up to date
                    # to, the field `get_legislation_text` was the only route
                    # to (equal on 9 of 9 stored pairs). Not an in-force date;
                    # `record_currency` reads it, for a held record only.
                    valid_date=record.get("valid_date") or None,
                    # The description carries a commencement instrument's
                    # effect and date ("bring sections 2, 9 … into force on 10
                    # May 2025"), which is all a stub has to offer. Capped: the
                    # reason `_slim_search_results` drops it is its size.
                    # P3.25: it is also where an SI's recital sits (7 of the 8
                    # stored text records carrying one), and each of those 7
                    # descriptions is 600 characters or fewer in whole, so the
                    # cap loses none of them (batch 7 C, `p325_fields.py`).
                    description=(str(record.get("description") or "")[:600] or None),
                )
                try:
                    s_status, sections = await _post(
                        "/legislation/section/lookup",
                        {"legislation_id": lid, "limit": 1}, "-sections")
                except (httpx.TimeoutException, httpx.TransportError):
                    s_status, sections = None, None
                if s_status == 200 and isinstance(sections, list) and sections:
                    out.update(status=HELD, http_status=200, text_held=True)
                elif s_status == 404 and _detail(sections).startswith("No sections found"):
                    out.update(status=HELD_WITHOUT_TEXT, http_status=200, text_held=False)
                else:
                    # Held, and whether its text is held could not be checked.
                    # Reported as held with the text question left open, which
                    # is what was established.
                    out.update(status=HELD, http_status=200, text_held=None)
                return json.dumps(out)

            elif name == "get_legislation_text":
                url = f"{LEX_API_URL}/legislation/text"
                # P3.27: `include_schedules` (default false: "only sections
                # are returned") was never sent, so every whole-text read left
                # out every schedule and annex, and said nothing (batch 7 B: 98
                # of 195 reading turns). With it the text is the sections and
                # then the schedules (60 of 60 live). The unflagged call below
                # tells code exactly where the schedules start, which one
                # flagged call does in only 22 of 27; `schedules_note` builds
                # the Worker's line from the two.
                payload = {"legislation_id": args["legislation_id"],
                           "include_schedules": True}

                await _emit(on_chunk, {
                    "type": "api_call_start",
                    "id": call_id,
                    "url": url,
                    "method": "POST",
                    "payload": payload
                })

                t0 = time.perf_counter()
                resp = await _request_with_retry(client, "POST", url, name=name, json=payload)
                elapsed_ms = (time.perf_counter() - t0) * 1000

                if timing_collector:
                    timing_collector.record_lex_api_call(name, elapsed_ms)

                try:
                    resp_json = resp.json()
                except ValueError:
                    resp_json = {"text": resp.text}

                await _emit(on_chunk, {
                    "type": "api_call_end",
                    "id": call_id,
                    "url": url,
                    "status": resp.status_code,
                    "response": resp_json,
                    "elapsed_ms": round(elapsed_ms),
                })

                resp.raise_for_status()
                # P3.27: the same call without the flag, for the boundary
                # only. Fail-soft (Invariant 5): any failure here keeps the
                # flagged text and leaves the boundary unknown, so the line
                # says less, never more. Its response reaches the audit as a
                # length, not the text again (a large Act's sections are
                # 0.9 MB, already carried by the call above).
                unflagged = None
                base_id = f"{call_id}-without-schedules"
                base_payload = {"legislation_id": args["legislation_id"]}
                try:
                    await _emit(on_chunk, {
                        "type": "api_call_start", "id": base_id, "url": url,
                        "method": "POST", "payload": base_payload,
                    })
                    t1 = time.perf_counter()
                    base_resp = await _request_with_retry(
                        client, "POST", url, name=name, json=base_payload)
                    base_ms = (time.perf_counter() - t1) * 1000
                    if timing_collector:
                        timing_collector.record_lex_api_call(name, base_ms)
                    if base_resp.status_code == 200:
                        unflagged = base_resp.json()
                    base_text = schedule_units.full_text_of(unflagged)
                    await _emit(on_chunk, {
                        "type": "api_call_end", "id": base_id, "url": url,
                        "status": base_resp.status_code,
                        "response": {"full_text_chars": len(base_text)
                                     if base_text is not None else None},
                        "elapsed_ms": round(base_ms),
                    })
                except Exception as e:  # noqa: BLE001 - the boundary is optional
                    logger.warning(f"[Worker Tool Exec] {name}: unflagged text call failed: {e!r}")
                    unflagged = None
                return json.dumps(schedule_units.mark_schedule_boundary(resp_json, unflagged))

            elif name == "search_case_law":
                url = "https://caselaw.nationalarchives.gov.uk/atom.xml"
                params: dict = {"query": args["query"]}
                if args.get("court"):
                    params["court"] = args["court"]

                # Apply user's hard filter constraints (override model args).
                # `_court` is gone (P4.4): the UI filter used to clobber the
                # model's own `court` argument here, so a court selected turns
                # earlier beat the model's per-query judgement. The date
                # filters deliberately INTERSECT rather than override, which
                # is what court should always have done.
                #
                # P3.9: and they are now sent in the one form the feed honours
                # (`from_date_0/1/2`, `to_date_0/1/2`; NOT in the published
                # spec, see `case_law_date_window`). `date_from`/`date_to`
                # were sent until P3.9 and the feed ignored them, so neither
                # the model's dates nor the lawyer's ever applied. An empty
                # window or a malformed date is refused here, with no call.
                cl_cfg = get_request_provider_config()
                window = case_law_date_window(args, cl_cfg)
                if window["error"]:
                    return json.dumps({
                        "error": window["error"],
                        "results": [],
                        "shown": 0,
                        "total": 0,
                        "query": args["query"],
                    })
                params.update(window["params"])
                # P3.22: by relevance, not newest first (the feed's default).
                # `order=relevance` is not in the published spec and `per_page`
                # must travel with it, or the page falls to 10 rows: see
                # `caselaw.CASE_LAW_ORDER_PARAMS`.
                params.update(CASE_LAW_ORDER_PARAMS)

                await _emit(on_chunk, {
                    "type": "api_call_start",
                    "id": call_id,
                    "url": url,
                    "method": "GET",
                    "payload": params,
                })

                t0 = time.perf_counter()
                # P4.19: through the retry helper, as every LEX call is. The
                # National Archives publishes a limit of 1,000 requests per
                # rolling five minutes per IP and answers it with a 429; the
                # target is one IP for every user, so a direct `client.get`
                # turned a 429 into a dropped retrieval. A 400 (an invalid
                # court code) is not in `_RETRY_STATUS` and still returns at
                # once to the branch below. The helper also retries a timeout
                # or transport error, which is wanted here: the only failures
                # in 1,149 stored calls were 3 DNS transport errors, and none
                # reached the 15 s timeout (batch 7 D's note).
                resp = await _request_with_retry(
                    client, "GET", url, name=name, params=params, timeout=15.0
                )
                elapsed_ms = (time.perf_counter() - t0) * 1000

                if timing_collector:
                    timing_collector.record_lex_api_call(name, elapsed_ms)

                await _emit(on_chunk, {
                    "type": "api_call_end",
                    "id": call_id,
                    "url": url,
                    "status": resp.status_code,
                    "response": {"preview": resp.text[:300]},
                    "elapsed_ms": round(elapsed_ms),
                })

                if resp.status_code == 400:
                    court = args.get("court", "")
                    return json.dumps({
                        "error": f"Invalid court filter '{court}'. Use only the exact court codes listed in the tool description (e.g. 'uksc', 'ewca/civ', 'ewhc/admin'). Retry without the court filter, or with a valid code.",
                        "results": [],
                        "total": 0,
                    })
                resp.raise_for_status()
                entries = _parse_case_law_atom(resp.text)
                # P3.23: the shown count and the matching total, separately.
                # `total` was `len(entries)`, never more than the 50-row page,
                # so `total: 50` read as "every match seen" when the feed held
                # thousands. `case_law_count` reads the real figure from the
                # feed's `last` link; `shown` is what anything deciding "did
                # this search return results" must key on.
                return json.dumps({
                    "results": entries,
                    **case_law_count(resp.text, len(entries)),
                    "query": args["query"],
                    # P3.9: the window the search ran under, for the note.
                    **({"dates": window["dates"]} if window["dates"] else {}),
                })

            elif name == "get_case_law_text":
                url = args["url"]

                await _emit(on_chunk, {
                    "type": "api_call_start",
                    "id": call_id,
                    "url": url + "/data.xml",
                    "method": "GET",
                    "payload": {},
                })

                t0 = time.perf_counter()
                try:
                    # P4.19: the shared client, so the fetch can go through
                    # `_request_with_retry` like the search above.
                    result = await _fetch_judgment_text(url, client=client)
                except httpx.HTTPStatusError as e:
                    result = {"error": f"HTTP {e.response.status_code} fetching judgment", "url": url, "text": ""}
                except Exception as e:
                    result = {"error": str(e), "url": url, "text": ""}
                elapsed_ms = (time.perf_counter() - t0) * 1000

                if timing_collector:
                    timing_collector.record_lex_api_call(name, elapsed_ms)

                await _emit(on_chunk, {
                    "type": "api_call_end",
                    "id": call_id,
                    "url": url + "/data.xml",
                    "status": 200 if "text" in result and result["text"] else 0,
                    "response": {"preview": result.get("text", "")[:300]},
                    "elapsed_ms": round(elapsed_ms),
                })

                return json.dumps(result)

            else:
                return f"Error: Tool {name} not found in worker toolset."

    except httpx.HTTPStatusError as e:
        logger.error(f"[Tool Error] {name}: {e.response.text}")
        return f"Error executing tool: {e.response.text}"
    except Exception as e:
        logger.error(f"[Tool Error] {name}: {e}", exc_info=True)
        return f"Error executing tool: {str(e)}"
