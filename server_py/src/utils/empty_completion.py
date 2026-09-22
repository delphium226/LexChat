"""Diagnostic and retry policy for a provider completion that carries nothing.

FIX_PLAN P4.2 (bucket B13 — lost turns and blank replies).

**The failure this exists for.** A streaming chat completion can return HTTP 200,
emit no content chunks and no tool-call deltas, and finish normally. `chat_loop`
then builds `{"role": "assistant", "content": ""}` and returns it as the answer:
`status: ok`, no error, and full billing. The lawyer sees a blank reply — or, once
the scope footer is appended, a footer with nothing above it — for a turn that ran
real research and was charged for it. Measured over the ten replay directories:
**8 billed blank turns in 616** (1.3%), in three chat modes, across six sessions.

**Why the existing stream retry cannot catch it.** That retry fires on an
*exception* raised while nothing has been emitted. A successful 200 carrying no
content raises nothing, so an empty completion is indistinguishable from a
finished answer at the point the loop decides whether to retry.

**Why a retry is the right shape, and why it is not keyed to tool calls.** Eight
of the nine observed blanks followed tool execution in the same request, which
matches the public reports of streaming-plus-function-calling returning an empty
final message. The ninth did not: it was a Deep Research synthesis call that
declared no tools at all (`tools=0, msgs=2`). So the failure is **not** confined to
tool-call turns and a guard scoped to them would miss it. The same payload also
succeeded five times and failed once, so it is stochastic rather than deterministic
— which is exactly the condition a bounded retry answers.

**Why this is a diagnostic first.** Four mechanisms produce this signature and the
stored evidence cannot tell them apart, which is why the ledger row could never
name a cause. They are distinguishable at the seam, so capture them there:

  1. the provider genuinely returned nothing  — `completion_tokens` ~0;
  2. the model spent the completion on reasoning and emitted no content
     — `reasoning_chars` > 0 with `content_chars` 0;
  3. a mid-stream failure arriving as a payload the parser ignores
     — `stream_error` set, and/or `finish_reason: "error"` carrying
       `native_finish_reason`;
  4. the model chose to say nothing — `finish_reason: "stop"`, no reasoning,
     non-zero completion tokens.

Only (4) is legitimate, and three attempts at it cost no more than the blank turn
already costs today. Nothing here changes behaviour when a completion has content.

Fail-soft throughout (Invariant 5): a diagnostic must never fail a research run.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger("app")


def is_empty_completion(content: str, tool_calls: Any) -> bool:
    """A completion that gives the caller nothing to act on.

    Whitespace-only counts as empty: it reaches the user as a blank reply just
    the same, and `_without_footer` in the replay tooling grades it that way.
    """
    return not (content or "").strip() and not tool_calls


def build_probe(
    *,
    provider: str,
    model: str,
    attempt: int,
    attempts_max: int,
    finish_reason: Optional[str] = None,
    native_finish_reason: Optional[str] = None,
    reasoning_chars: int = 0,
    stream_error: Any = None,
    usage: Optional[dict] = None,
    sent_chars: int = 0,
    turn: int = 0,
) -> dict:
    """The record describing one empty completion. Never raises."""
    try:
        usage = usage or {}
        completion_tokens = usage.get("completion_tokens")
        if completion_tokens is None:
            # Ollama's field name for the same quantity.
            completion_tokens = usage.get("eval_count")
        err = stream_error
        if isinstance(err, dict):
            err = err.get("message") or str(err)
        if err is not None and not isinstance(err, str):
            err = str(err)
        return {
            "provider": provider,
            "model": model,
            "attempt": attempt + 1,
            "attempts_max": attempts_max,
            "finish_reason": finish_reason,
            "native_finish_reason": native_finish_reason,
            "reasoning_chars": int(reasoning_chars or 0),
            "completion_tokens": completion_tokens,
            "stream_error": (err[:500] if isinstance(err, str) else None),
            "sent_chars": int(sent_chars or 0),
            "react_turn": int(turn or 0),
        }
    except Exception:
        logger.debug("[EmptyCompletion] build_probe failed", exc_info=True)
        return {"provider": provider, "model": model, "attempt": attempt + 1}


def report_empty_completion(probe: dict, *, retrying: bool) -> None:
    """Log the probe and record it on the audit trace, if one is collecting.

    Imported inside the function: `utils.audit_trace` imports from `agent`, and
    both provider clients import this module at load time.
    """
    try:
        logger.warning(
            "[EmptyCompletion] %s returned no content and no tool calls "
            "(model=%s, attempt %s/%s, finish_reason=%s, native=%s, "
            "completion_tokens=%s, reasoning_chars=%s, stream_error=%s, "
            "sent=%s chars, react_turn=%s) — %s",
            probe.get("provider"), probe.get("model"), probe.get("attempt"),
            probe.get("attempts_max"), probe.get("finish_reason"),
            probe.get("native_finish_reason"), probe.get("completion_tokens"),
            probe.get("reasoning_chars"), probe.get("stream_error"),
            probe.get("sent_chars"), probe.get("react_turn"),
            "retrying" if retrying else "giving up, returning empty",
        )
    except Exception:
        pass
    try:
        from .audit_trace import get_audit_collector
        collector = get_audit_collector()
        if collector is not None:
            collector.record_empty_completion({**probe, "retried": bool(retrying)})
    except Exception:
        logger.debug("[EmptyCompletion] audit record failed", exc_info=True)


# ---------------------------------------------------------------------------
# Fallbacks — what the lawyer sees when the retry did not recover
# ---------------------------------------------------------------------------
#
# Invariant 1 governs the wording. A fallback assembled out of research the
# answering step never managed to use is **not** an answer, and must not read
# like one: the whole point of this bucket is that the lawyer could not tell a
# lost answer from a completed one. So each fallback opens by naming the failure,
# says plainly what has and has not been done to the material below, and tells
# the lawyer what to do next. Nothing is paraphrased, summarised or reordered —
# doing any of that would be composing an answer without a model, which is a
# worse failure than the blank reply.

_SYNTHESIS_FALLBACK_HEADER = (
    "**The final synthesis step returned no text, so this report is not an "
    "integrated answer.** The research itself completed and every step's "
    "findings are reproduced below, unedited and in the order the plan ran "
    "them. They have **not** been synthesised, reconciled where two steps "
    "disagree, or checked for gaps against the question you asked. Re-run the "
    "question if you need the integrated report."
)

_MANAGER_FALLBACK_HEADER = (
    "**The answering step returned no text, so this is not a composed answer.** "
    "The research completed and the research agent's own report is reproduced "
    "below, unedited. It has **not** been shaped to the question you asked or "
    "checked against the rest of this conversation. Re-run the question if you "
    "need a composed answer."
)

LOST_ANSWER_NOTICE = (
    "**No answer was returned for this turn.** The model produced an empty "
    "response on every attempt, and no research output was gathered that could "
    "be shown instead. Nothing has been answered from memory. Please send the "
    "question again."
)


def fallback_from_reports(reports: list, *, kind: str) -> str:
    """Compose a labelled fallback body from research that was already produced.

    `reports` is a list of `{"title": str | None, "content": str}`. Entries with
    no content are dropped — a fallback that reproduces nothing is the bare
    notice instead. `kind` is "synthesis" (Deep Research) or "manager".
    """
    try:
        usable = [
            r for r in (reports or [])
            if isinstance(r, dict) and (r.get("content") or "").strip()
        ]
    except Exception:
        usable = []
    if not usable:
        return LOST_ANSWER_NOTICE

    header = (
        _SYNTHESIS_FALLBACK_HEADER if kind == "synthesis" else _MANAGER_FALLBACK_HEADER
    )
    parts = [header]
    for i, r in enumerate(usable, 1):
        title = (r.get("title") or "").strip()
        parts.append(f"## {title}" if title else f"## Research output {i}")
        parts.append((r.get("content") or "").strip())
    return "\n\n".join(parts)
