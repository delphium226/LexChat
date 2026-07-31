"""Structured audit trace for evaluation harnesses.

The SSE stream the agents emit is built for a UI: flat `tool_start` /
`tool_end` / `api_call_start` / `api_call_end` events carrying human-readable
labels. A machine consumer that wants "which tool ran inside which delegation,
what did the API actually return, and what did the model see after
summarisation" has to rebuild that structure with a push/pop stack, correlate
start/end pairs itself, and string-match display labels like "Research Agent"
or "Extracting the relevant sections from a large document" to classify events.

That coupling is brittle in a way that fails silently: rename a label or add a
Deep Research step prefix and the consumer's numbers go quietly wrong rather
than erroring. It is also unnecessary — the server already knows the structure,
it just throws it away at render time.

`AuditCollector` keeps that structure and `/api/system/chat` emits it as a
single `audit` SSE event before the final `result`. Design notes:

* **Off unless requested.** The collector lives in a ContextVar that only
  `/api/system/chat` sets. Every recording site is a `get_audit_collector()`
  null check, so `/api/chat` pays one ContextVar read per tool call and nothing
  else. No signature churn on the hot path.
* **Nesting comes from the call graph, not from event order.** Delegations are
  opened in `run_worker_agent`; tool records are opened in `run_worker_tool`
  and handed the delegation they belong to; API calls are captured by sniffing
  the `on_chunk` callback *inside* the tool record's own scope. Correct
  nesting therefore holds under any future concurrency without a stack.
* **Fail-soft.** Auditing must never break a request. Every public method
  swallows its own errors — a broken trace is acceptable, a broken research
  run is not.
"""

from __future__ import annotations

import logging
import time
import uuid
from contextvars import ContextVar
from typing import Any, Callable, Optional

logger = logging.getLogger("app")

_audit_ctx: ContextVar[Optional["AuditCollector"]] = ContextVar("audit_collector", default=None)

# Trace schema version. Bump on any breaking change to the `audit` event shape
# so consumers can assert against a known contract.
AUDIT_SCHEMA_VERSION = 1


def set_audit_collector(collector: Optional["AuditCollector"]) -> None:
    _audit_ctx.set(collector)


def get_audit_collector() -> Optional["AuditCollector"]:
    return _audit_ctx.get()


def _clip(value: Any, limit: int) -> Any:
    """Truncate an oversized string field, marking it so the consumer can tell
    a truncated capture from a genuinely short one."""
    if limit <= 0 or not isinstance(value, str) or len(value) <= limit:
        return value
    return value[:limit] + f"\n[audit: truncated {len(value) - limit} chars]"


class AuditCollector:
    """Accumulates a structured trace of one agent request.

    Not thread-safe and not intended to be — one instance per request, mutated
    from the request's own task tree.
    """

    def __init__(self, request_id: str, max_field_chars: int = 0):
        self.request_id = request_id
        self.max_field_chars = max_field_chars
        self.delegations: list[dict] = []
        self.peer_consults: list[dict] = []
        self.answer: str = ""
        self.suggestions: list[str] = []
        self.sources: list[dict] = []
        self.error: Optional[str] = None
        # Metadata for the next delegation opened, set by a caller that knows
        # more than run_worker_agent does (Deep Research step number/title).
        # Consumed and cleared by the next start_delegation call.
        self._pending_meta: dict = {}
        self._started = time.time()

    # -- delegation scope ------------------------------------------------

    def set_next_delegation_meta(self, **meta) -> None:
        """Attach metadata to the next delegation opened. Deep Research knows
        the step number and approved title; run_worker_agent does not."""
        try:
            self._pending_meta = dict(meta)
        except Exception:
            pass

    def start_delegation(self, brief: str, kind: str = "delegation") -> Optional[dict]:
        try:
            rec = {
                "id": uuid.uuid4().hex[:8],
                "kind": kind,
                "step": None,
                "title": None,
                "brief": _clip(brief, self.max_field_chars),
                "report": "",
                "reformatted": False,
                "error": None,
                "tools": [],
                "started_at": round(time.time() - self._started, 3),
                "duration_s": None,
            }
            rec.update(self._pending_meta)
            self._pending_meta = {}
            self.delegations.append(rec)
            return rec
        except Exception:
            logger.debug("[Audit] start_delegation failed", exc_info=True)
            return None

    def end_delegation(
        self,
        rec: Optional[dict],
        report: str = "",
        error: Optional[str] = None,
        reformatted: bool = False,
    ) -> None:
        if rec is None:
            return
        try:
            rec["report"] = _clip(report or "", self.max_field_chars)
            rec["error"] = error
            rec["reformatted"] = reformatted
            rec["duration_s"] = round(
                time.time() - self._started - rec["started_at"], 3
            )
        except Exception:
            logger.debug("[Audit] end_delegation failed", exc_info=True)

    def mark_reformatted(self, rec: Optional[dict]) -> None:
        if rec is not None:
            try:
                rec["reformatted"] = True
            except Exception:
                pass

    # -- tool scope ------------------------------------------------------

    def start_tool(self, delegation: Optional[dict], name: str, args: dict) -> Optional[dict]:
        try:
            rec = {
                "id": uuid.uuid4().hex[:8],
                "name": name,
                "args": args if isinstance(args, dict) else {},
                "raw_result": "",
                "final_result": "",
                "summarised": False,
                "memo_hit": False,
                "local_cache_hit": False,
                "truncated": False,
                "budget_blocked": False,
                "error": None,
                "api_calls": [],
                "started_at": round(time.time() - self._started, 3),
                "duration_s": None,
            }
            target = delegation["tools"] if delegation is not None else self._orphan_tools()
            target.append(rec)
            return rec
        except Exception:
            logger.debug("[Audit] start_tool failed", exc_info=True)
            return None

    def _orphan_tools(self) -> list:
        """Tool calls made outside any delegation (should not happen, but a
        trace that drops them silently would be worse than one that shows
        them)."""
        for d in self.delegations:
            if d.get("kind") == "orphan":
                return d["tools"]
        rec = {
            "id": "orphan",
            "kind": "orphan",
            "step": None,
            "title": None,
            "brief": "",
            "report": "",
            "reformatted": False,
            "error": None,
            "tools": [],
            "started_at": 0.0,
            "duration_s": None,
        }
        self.delegations.append(rec)
        return rec["tools"]

    def end_tool(
        self,
        rec: Optional[dict],
        raw_result: str = "",
        final_result: str = "",
        summarised: bool = False,
        memo_hit: bool = False,
        local_cache_hit: bool = False,
        truncated: bool = False,
        budget_blocked: bool = False,
        error: Optional[str] = None,
    ) -> None:
        if rec is None:
            return
        try:
            rec["raw_result"] = _clip(raw_result or "", self.max_field_chars)
            rec["final_result"] = _clip(final_result or "", self.max_field_chars)
            rec["summarised"] = summarised
            rec["memo_hit"] = memo_hit
            rec["local_cache_hit"] = local_cache_hit
            rec["truncated"] = truncated
            rec["budget_blocked"] = budget_blocked
            rec["error"] = error
            rec["duration_s"] = round(
                time.time() - self._started - rec["started_at"], 3
            )
        except Exception:
            logger.debug("[Audit] end_tool failed", exc_info=True)

    # -- external API calls ----------------------------------------------

    def sniff_on_chunk(self, tool_rec: Optional[dict], on_chunk: Optional[Callable]) -> Optional[Callable]:
        """Wrap an on_chunk callback so `api_call_start` / `api_call_end`
        events land on `tool_rec` as they pass through.

        Sniffing rather than editing the ~10 emission sites in executor.py
        keeps the capture in one place and gets the tool nesting for free:
        the executor is called from inside this tool's own scope, so anything
        it emits belongs to this tool by construction.
        """
        if tool_rec is None:
            return on_chunk

        async def _sniffer(data):
            try:
                if isinstance(data, dict):
                    etype = data.get("type")
                    if etype == "api_call_start":
                        tool_rec["api_calls"].append({
                            "id": data.get("id"),
                            "url": data.get("url"),
                            "method": data.get("method"),
                            "request": data.get("payload"),
                            "status": None,
                            "response": None,
                            "elapsed_ms": None,
                        })
                    elif etype == "api_call_end":
                        call_id = data.get("id")
                        entry = next(
                            (c for c in reversed(tool_rec["api_calls"])
                             if c["id"] == call_id and c["response"] is None),
                            None,
                        )
                        if entry is None:
                            entry = {
                                "id": call_id, "url": data.get("url"),
                                "method": None, "request": None,
                                "status": None, "response": None, "elapsed_ms": None,
                            }
                            tool_rec["api_calls"].append(entry)
                        entry["status"] = data.get("status")
                        entry["response"] = data.get("response")
                        entry["elapsed_ms"] = data.get("elapsed_ms")
            except Exception:
                logger.debug("[Audit] api_call sniff failed", exc_info=True)
            if on_chunk:
                return await on_chunk(data)

        return _sniffer

    # -- manager level ---------------------------------------------------

    def record_peer_consult(self, peer_id: str, peer_name: str, question: str, answer: str) -> None:
        try:
            self.peer_consults.append({
                "peer_id": peer_id,
                "peer_name": peer_name,
                "question": _clip(question, self.max_field_chars),
                "answer": _clip(answer, self.max_field_chars),
            })
        except Exception:
            logger.debug("[Audit] record_peer_consult failed", exc_info=True)

    def record_final(self, result: Optional[dict]) -> None:
        try:
            if not isinstance(result, dict):
                return
            self.answer = _clip(result.get("content") or "", self.max_field_chars)
            self.suggestions = list(result.get("suggestions") or [])
            self.sources = list(result.get("sources") or [])
        except Exception:
            logger.debug("[Audit] record_final failed", exc_info=True)

    def record_error(self, message: str) -> None:
        try:
            self.error = message
        except Exception:
            pass

    # -- output ----------------------------------------------------------

    def to_event(self, *, config: dict, timings: Optional[dict] = None) -> dict:
        """Build the `audit` SSE event payload."""
        try:
            return {
                "type": "audit",
                "schema_version": AUDIT_SCHEMA_VERSION,
                "request_id": self.request_id,
                "chat_mode": config.get("_chat_mode"),
                "research_mode": config.get("_research_mode"),
                "provider": config.get("_provider"),
                "model": config.get("model"),
                "summarisation_model": config.get("summarisation_model") or None,
                "filters": {
                    "jurisdiction": config.get("_jurisdiction"),
                    "year_from": config.get("_year_from"),
                    "year_to": config.get("_year_to"),
                    "date_from": config.get("_date_from"),
                    "date_to": config.get("_date_to"),
                    "court": config.get("_court"),
                    "legislation_type": config.get("_legislation_type"),
                    "current_only": config.get("_current_only"),
                    "record_type": config.get("_pt_record_type") or config.get("_wm_record_type"),
                    "house": config.get("_wm_house"),
                    "sessions": config.get("_pt_sessions"),
                },
                "answer": self.answer,
                "suggestions": self.suggestions,
                "sources": self.sources,
                "delegations": self.delegations,
                "peer_consults": self.peer_consults,
                "timings": timings or {},
                "error": self.error,
            }
        except Exception:
            logger.error("[Audit] to_event failed", exc_info=True)
            return {
                "type": "audit",
                "schema_version": AUDIT_SCHEMA_VERSION,
                "request_id": self.request_id,
                "error": "audit trace could not be serialised",
            }
