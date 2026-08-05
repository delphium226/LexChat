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
from ...utils.redact import redact_args
from ..provider_factory import get_request_provider_config
from ._util import _emit
from .caselaw import _fetch_judgment_text, _parse_case_law_atom
from .lex import (
    LEX_API_URL,
    _TYPE_CODES,
    _matches_jurisdiction,
    _slim_search_results,
    extract_legislation_ids_from_search,
)

logger = logging.getLogger("agent")

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
                current_only = cfg.get("_current_only", False)

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

                needs_post_filter = bool(jurisdiction or legislation_type or current_only)
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

                # Post-filter: legislation type (by legislation_id prefix)
                if legislation_type:
                    type_codes = _TYPE_CODES.get(legislation_type, set())
                    results = [
                        r for r in results
                        if r.get("legislation_id", "").split("/")[0] in type_codes
                    ]

                # Post-filter: current legislation only (exclude known non-in-force)
                if current_only:
                    _INACTIVE = {"repealed", "revoked", "spent", "expired", "not in force"}
                    results = [
                        r for r in results
                        if r.get("status", "").lower() not in _INACTIVE
                    ]

                # Post-filter: jurisdiction (by extent field)
                if jurisdiction:
                    results = [
                        r for r in results
                        if _matches_jurisdiction(r.get("extent", []), jurisdiction)
                    ]

                results = results[:5]
                slimmed["results"] = results
                slimmed["total"] = len(results)
                return json.dumps(slimmed)

            elif name == "search_legislation_sections":
                url = f"{LEX_API_URL}/legislation/section/search"
                payload = {
                    "query": args["query"],
                    "legislation_id": args["legislation_id"],
                    "limit": 10,
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
                return json.dumps(resp_json)

            elif name == "get_legislation_text":
                url = f"{LEX_API_URL}/legislation/text"
                payload = {"legislation_id": args["legislation_id"]}

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
                return json.dumps(resp_json)

            elif name == "search_case_law":
                url = "https://caselaw.nationalarchives.gov.uk/atom.xml"
                params: dict = {"query": args["query"]}
                if args.get("court"):
                    params["court"] = args["court"]
                if args.get("date_from"):
                    params["date_from"] = args["date_from"]
                if args.get("date_to"):
                    params["date_to"] = args["date_to"]

                # Apply user's hard filter constraints (override model args)
                cl_cfg = get_request_provider_config()
                if cl_cfg.get("_court"):
                    params["court"] = cl_cfg["_court"]
                if cl_cfg.get("_date_from"):
                    model_df = args.get("date_from") or ""
                    params["date_from"] = max(model_df, cl_cfg["_date_from"]) if model_df else cl_cfg["_date_from"]
                if cl_cfg.get("_date_to"):
                    model_dt = args.get("date_to") or ""
                    params["date_to"] = min(model_dt, cl_cfg["_date_to"]) if model_dt else cl_cfg["_date_to"]

                await _emit(on_chunk, {
                    "type": "api_call_start",
                    "id": call_id,
                    "url": url,
                    "method": "GET",
                    "payload": params,
                })

                t0 = time.perf_counter()
                resp = await client.get(url, params=params, timeout=15.0)
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
                return json.dumps({
                    "results": entries,
                    "total": len(entries),
                    "query": args["query"],
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
                    result = await _fetch_judgment_text(url)
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
