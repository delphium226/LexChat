"""FIX_PLAN P3.38: read an instrument's text from legislation.gov.uk through LEX's proxy.

The pure parts (the trigger, the paths, the CLML renderer, the wording) are in
`utils/published_text.py`; this module makes the reads. Bounds (user decision
at the build, batch 13 C's note):

* **through LEX's `GET /legislation/proxy/<encoded path>`** only, the route
  P3.21 and P3.31 already use, so the target needs no new whitelist entry;
* **one document a route**, the whole instrument with its schedules
  (`/<id>/made/data.xml` or `/enacted/`, then the current `/<id>/data.xml`),
  so at most `len(routes)` = 2 calls an instrument;
* **`READ_TIMEOUT_S` a call**, one attempt (no retry: it would multiply the
  bound), and at most `MAX_BYTES` read from a body;
* **at most `MAX_READS_PER_REQUEST` instruments a request**, memoised per
  request (the slot reserved before the await, P3.12's lesson), so a lookup
  and a text read of the same instrument, or two Deep Research steps, share
  one read;
* **live and never cached**: nothing is kept past the request, and the text
  never reaches `local_prompt_cache` (it is appended after the tool result's
  own summarisation, and summarised, when it must be, without the cache).

Never raises: every failure is an outcome the Worker is told about in one line.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Callable, Optional
from urllib.parse import quote

import httpx

from ...utils import published_text as pt
from ..provider_factory import get_request_provider_config
from ._util import _emit
from .lex import LEX_API_URL

logger = logging.getLogger("agent")

READ_TIMEOUT_S = 15.0
MAX_BYTES = 8_000_000
MAX_READS_PER_REQUEST = 8
MEMO_KEY = "_published_text_memo"
TOOL_LABEL = "legislation.gov.uk text"

# The proxy's two answers for a document legislation.gov.uk does not publish
# (batch 13 C, live): a 404 with LEX's own "Legislation not found: <path>"
# (an SSI number not yet used, asked for as made), and a 502 wrapping
# the upstream error ("External API error: Client error '400 Bad Request' for
# url ..."; an SSI number out of range).
_LEX_NOT_FOUND = "Legislation not found"
_UPSTREAM_ERROR = "External API error"
_UPSTREAM_ABSENT = ("'404 ", "'400 ", "'410 ")


def proxy_url(lgu_path: str) -> str:
    """The legislation.gov.uk path through LEX's proxy, as one encoded segment."""
    return f"{LEX_API_URL}/legislation/proxy/{quote(lgu_path.lstrip('/'), safe='')}"


def _make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=READ_TIMEOUT_S, verify=False)


def _client() -> httpx.AsyncClient:
    """The seam tests replace: no test may reach the network (`conftest.py`)."""
    return _make_client()


def _request_memo() -> dict:
    """``{"reads": int, "docs": {lid: Future}}``, on the request's own config
    dict (shared by reference through the ContextVar), as P3.21's memo is.
    With no request config (a script, a test) each call gets its own."""
    try:
        cfg = get_request_provider_config()
    except Exception:
        cfg = None
    if not isinstance(cfg, dict) or not cfg:
        return {"reads": 0, "docs": {}}
    memo = cfg.get(MEMO_KEY)
    if not isinstance(memo, dict):
        memo = {"reads": 0, "docs": {}}
        cfg[MEMO_KEY] = memo
    return memo


async def _get(client: httpx.AsyncClient, url: str, call_id: str, on_chunk,
               timing_collector, tool_name: str) -> tuple:
    """One GET. Returns ``(status, text_or_None, reason_or_None, absent)``;
    never raises. `absent` is True only when legislation.gov.uk itself
    answered that it has no such document. Recorded on the audit by size,
    never by body."""
    await _emit(on_chunk, {"type": "api_call_start", "id": call_id, "url": url,
                           "method": "GET", "payload": None})
    t0 = time.perf_counter()
    status, text, reason, absent, size = None, None, None, False, 0
    try:
        async with client.stream("GET", url) as resp:
            status = resp.status_code
            chunks = []
            async for chunk in resp.aiter_bytes():
                size += len(chunk)
                if size > MAX_BYTES:
                    reason = "too_large"
                    break
                chunks.append(chunk)
            body = b"".join(chunks)
        if reason is None:
            if status == 200:
                text = body.decode("utf-8", "replace")
            else:
                detail = body[:600].decode("utf-8", "replace")
                # Only the proxy's own two "no such document" answers: a bare
                # route 404 (`{"detail": "Not Found"}`, an endpoint moved)
                # must not read as legislation.gov.uk publishing nothing.
                absent = (status == 404 and _LEX_NOT_FOUND in detail) or (
                    status == 502 and _UPSTREAM_ERROR in detail
                    and any(code in detail for code in _UPSTREAM_ABSENT))
                reason = "absent" if absent else f"http_{status}"
    except httpx.TimeoutException:
        reason = "no_reply"
    except Exception as e:  # noqa: BLE001 - fail-soft
        logger.warning(f"[Worker Tool Exec] legislation.gov.uk text read failed: {e!r}")
        reason = "error"
    elapsed_ms = (time.perf_counter() - t0) * 1000
    if timing_collector:
        try:
            timing_collector.record_lex_api_call(tool_name, elapsed_ms)
        except Exception:
            pass
    info = {"bytes": size}
    if reason:
        info["error"] = reason
    await _emit(on_chunk, {"type": "api_call_end", "id": call_id, "url": url,
                           "status": status, "response": info,
                           "elapsed_ms": round(elapsed_ms)})
    return status, text, reason, absent


async def _read(lid: str, call_id: str, on_chunk, timing_collector, tool_name: str) -> dict:
    """The outcome for one instrument, trying each route in order. A route
    legislation.gov.uk says it has no document for moves on to the next; any
    other failure ends the read, as failed."""
    paths = pt.routes(lid)
    if not paths:
        return {"status": pt.UNSUPPORTED}
    async with _client() as client:
        for i, path in enumerate(paths):
            status, text, reason, absent = await _get(
                client, proxy_url(path), f"{call_id}-lgu-text-{i + 1}", on_chunk,
                timing_collector, tool_name)
            if absent:
                continue
            if reason:
                return {"status": pt.FAILED, "reason": reason}
            try:
                parsed = pt.parse_published(text)
            except ValueError as e:
                logger.info(f"[Worker Tool Exec] legislation.gov.uk page unusable: {e}")
                return {"status": pt.FAILED, "reason": "unreadable"}
            if not parsed["text"].strip():
                if parsed.get("pdf"):
                    return {"status": pt.PDF_ONLY, "pdf": parsed["pdf"],
                            "title": parsed["title"]}
                continue
            return {"status": pt.OK, **parsed}
    return {"status": pt.NOT_PUBLISHED}


async def read_published_text(
    lid: str,
    *,
    on_chunk: Optional[Callable] = None,
    timing_collector=None,
    tool_name: str = "",
) -> dict:
    """legislation.gov.uk's text for `lid`, read through LEX's proxy, or an
    outcome saying why not. Memoised per request; at most
    `MAX_READS_PER_REQUEST` instruments a request. Never raises."""
    try:
        lid = pt.normalise_id(lid)
        if not lid:
            return {"status": pt.UNSUPPORTED}
        memo = _request_memo()
        docs = memo["docs"]
        task = docs.get(lid)
        if task is None:
            if memo["reads"] >= MAX_READS_PER_REQUEST:
                return {"status": pt.LIMIT, "limit": MAX_READS_PER_REQUEST}
            memo["reads"] += 1
            call_id = str(uuid.uuid4())
            task = asyncio.ensure_future(
                _read(lid, call_id, on_chunk, timing_collector, tool_name or TOOL_LABEL))
            docs[lid] = task
        return dict(await asyncio.shield(task))
    except asyncio.CancelledError:
        raise
    except Exception as e:  # noqa: BLE001 - fail-soft (Invariant 5)
        logger.warning(f"[Worker Tool Exec] legislation.gov.uk text not read: {e!r}")
        return {"status": pt.FAILED, "reason": "error"}
