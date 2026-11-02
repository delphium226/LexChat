"""FIX_PLAN P3.57: the reads behind a text scan of a made-under list.

The pure parts (the detector, the matcher, the block, the limb, the footer) are
in `utils/literal_scan.py`; this module reads each listed instrument's text.
Bounds (measured on the 37 s.95 instruments, `evidence/seam/s52/p357/`):

* **LEX's provision list first** (`executor.fetch_provision_list`,
  `/legislation/section/lookup`): one call an instrument, every provision and
  schedule with its text and `uri`, so a match is placed in its provision.
  31 of 37 came back with text, 1.66 MB in all, 59-162 ms each; the '£' count
  equalled the stored `/legislation/text` count on every one of the 31, and
  legislation.gov.uk's own count on the 3 cross-checked.
* **legislation.gov.uk for an instrument the index holds no text of**, through
  P3.38's read (`published_text.read_published_text`: LEX's proxy, memoised per
  request, at most 8 instruments a request, 15 s a call), which the scan shares
  with P3.38's own route. 6 of 37; 0.2-17.6 s, so one may not answer in time.
* **`SCAN_CONCURRENCY` reads at once, and `SCAN_DEADLINE_S` for the whole
  scan:** an instrument not read by then is "not read", and said so.
* **The provision lists are memoised per request** (`MEMO_KEY`, on the
  request's own config dict as P3.38's memo is), so a second scan of the same
  list, or a Deep Research step repeating it, reads nothing again. Nothing is
  kept past the request.

Never raises: every failure is an outcome ("not read", with a reason).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Callable, Optional

from ...utils import literal_scan as ls
from ...utils import published_text as pt
from ..provider_factory import get_request_provider_config
from . import executor
from . import published_text

logger = logging.getLogger("agent")

SCAN_CONCURRENCY = 4
SCAN_DEADLINE_S = 45.0
MEMO_KEY = "_literal_scan_memo"

_PUBLISHED_REASONS = {
    pt.LIMIT: "limit",
    pt.PDF_ONLY: "pdf_only",
    pt.NOT_PUBLISHED: "not_published",
}


def _memo() -> dict:
    try:
        cfg = get_request_provider_config()
    except Exception:
        cfg = None
    if not isinstance(cfg, dict) or not cfg:
        return {}
    memo = cfg.get(MEMO_KEY)
    if not isinstance(memo, dict):
        memo = {}
        cfg[MEMO_KEY] = memo
    return memo


async def _read_list(lid: str, on_chunk, timing_collector, tool_name: str) -> dict:
    """The seam tests replace: no test may reach the network (`conftest.py`)."""
    return await executor.fetch_provision_list(
        lid, on_chunk=on_chunk, timing_collector=timing_collector, tool_name=tool_name)


async def _provision_list(lid: str, memo: dict, on_chunk, timing_collector, tool_name: str) -> dict:
    task = memo.get(lid)
    if task is None:
        task = asyncio.ensure_future(_read_list(lid, on_chunk, timing_collector, tool_name))
        memo[lid] = task
    return dict(await asyncio.shield(task))


async def _one(lid: str, literal: str, memo: dict, sem: asyncio.Semaphore, on_chunk,
               timing_collector, tool_name: str) -> dict:
    async with sem:
        listed = await _provision_list(lid, memo, on_chunk, timing_collector, tool_name)
        status = listed.get("status")
        if status == "ok" and listed.get("complete") is True and listed.get("rows"):
            return ls.outcome_from_rows(listed["rows"], literal)
        if status != "no_text":
            return {"status": "not_read", "reason": "failed"}
        # The index holds no text of it (Session 50: no instrument held with
        # text ever answered "No sections found"), so P3.38's read.
        got = await published_text.read_published_text(
            lid, on_chunk=on_chunk, timing_collector=timing_collector, tool_name=tool_name)
        if got.get("status") == pt.OK:
            return ls.outcome_from_text(got.get("text"), literal, url=got.get("url") or "",
                                        version=got.get("version") or "")
        reason = _PUBLISHED_REASONS.get(got.get("status"))
        if reason is None:
            reason = "no_reply" if got.get("reason") == "no_reply" else "failed"
        return {"status": "not_read", "reason": reason}


async def scan_instruments(
    lids: list,
    literal: str,
    *,
    on_chunk: Optional[Callable] = None,
    timing_collector=None,
    tool_name: str = "find_instruments_made_under",
) -> dict:
    """`{legislation_id: outcome}` for each of `lids` (`utils.literal_scan`'s
    outcome shape). Never raises; an instrument not read in time, or at all,
    is `{"status": "not_read", "reason": ...}`."""
    out = {lid: {"status": "not_read", "reason": "failed"} for lid in lids}
    try:
        memo = _memo()
        sem = asyncio.Semaphore(SCAN_CONCURRENCY)
        tasks = {asyncio.ensure_future(_one(lid, literal, memo, sem, on_chunk, timing_collector,
                                            tool_name)): lid for lid in lids}
        done, pending = await asyncio.wait(tasks, timeout=SCAN_DEADLINE_S)
        for t in pending:
            out[tasks[t]] = {"status": "not_read", "reason": "no_reply"}
            t.cancel()
        for t in done:
            try:
                out[tasks[t]] = t.result()
            except Exception as e:  # noqa: BLE001 - fail-soft
                logger.warning(f"[Worker] Text scan of {tasks[t]} failed: {e!r}")
        return out
    except asyncio.CancelledError:
        raise
    except Exception as e:  # noqa: BLE001 - fail-soft (Invariant 5)
        logger.warning(f"[Worker] Text scan failed: {e!r}")
        return out
