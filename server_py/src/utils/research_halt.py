"""The research step cap, made honest (FIX_PLAN P2.1, bucket B1).

`chat_loop` stops recursing at `max_turns` and returns
`"[Research halted: exceeded 20 tool-call steps]"` **as the assistant's
content**. That string is not an error anyone handles — it is the worker's
report. So it escapes by three routes, not one:

1. a Manager `delegate_research` receives it as the research findings;
2. `run_deep_research` files it as a plan step's findings and hands it to
   synthesis;
3. the **Manager's own** loop can hit the cap, in which case the raw string is
   the entire answer (6383 turn 1 — and note it appears in no delegation report
   at all, so a check reading only `delegations[].report` is blind to it).

What reached lawyers was worse than the raw string. In 6340 the Manager rendered
it as the agent having *"exceeded its operational limits (timed out)"* — it did
not time out, it hit a step cap — and then supplied a cause for the absence:
*"a broad enabling power has generated a very large volume of statutory
instruments over several decades"*, for an Act that 404s in LEX. A halt was
laundered into a legal finding about the state of the statute book.

**Invariant 1 has a sharp edge here.** Honest failure is the most-praised
behaviour in the corpus, so the fix is not to suppress the halt — it is to make
the disclosure TRUE, and to make it happen whether or not the model cooperates.
Two things follow, and the second is the one the rewritten acceptance turns on:

* the reason stated must be the real one (a cap on tool-call rounds — not a
  timeout, not an API failure, and not evidence the material does not exist);
* **the disclosure is emitted by code, not requested in a prompt.** The original
  acceptance ("produce no halt text") was satisfiable by saying nothing — and
  over the Wave 1 sweep's 11 halted turns, **6 said nothing at all and only 2
  were disclosed acceptably**: a worker stops, a normal-looking report comes
  back, and the lawyer gets no signal it is incomplete. That is worse than the
  raw string leaking, because the raw string at least tells them something is
  wrong.

So `apply_halt_disclosure` always speaks when a halt happened. There is no
detector deciding whether the model already disclosed it well enough — on this
work the detectors have been wrong more often than the product, and a
false negative here is a lawyer relying on a partial answer.
"""

from __future__ import annotations

import re
from typing import Iterable, Optional

__all__ = [
    "HALT_MARKER",
    "halt_marker_text",
    "strip_halt_markers",
    "halt_worker_report",
    "halt_notice",
    "apply_halt_disclosure",
]

# The literal `chat_loop` emits. Matched loosely on the limit so a future change
# to `max_turns` cannot leave a marker behind un-stripped.
HALT_MARKER = re.compile(r"\[Research halted:[^\]]*\]", re.I)


def halt_marker_text(limit: int) -> str:
    """The raw marker `chat_loop` returns as the halted assistant's content."""
    return f"[Research halted: exceeded {limit} tool-call steps]"


def strip_halt_markers(text: str) -> tuple:
    """Remove every raw halt marker from `text`. Returns (text, count).

    Unconditional, like the `<suggestions>` strip: the marker is machine
    bookkeeping and must never render to a lawyer, whatever else happens.
    """
    if not text:
        return text, 0
    out, n = HALT_MARKER.subn("", text)
    if n:
        out = re.sub(r"\n{3,}", "\n\n", out).strip()
    return out, n


def halt_worker_report(halt: dict, sources_retrieved: int = 0) -> str:
    """What a halted worker hands back in place of a report.

    Addressed to the *agent* that will read it — a Manager holding it as a
    `delegate_research` result, or the Deep Research synthesis holding it as a
    step's findings. It states the true cause, and it forbids the two specific
    behaviours observed in 6340: renaming the cap a timeout, and inventing a
    reason for the absence of findings.

    Modelled on the `[Research Agent Error]` containment string in
    `agent_core.manager_tool_executor`, which is proven house style for exactly
    this job: an instruction carried per-occurrence in the tool result beats a
    rule in a system prompt that has to survive the whole conversation.
    """
    limit = halt.get("limit", 20)
    retrieved = (
        f"{sources_retrieved} source(s) had been retrieved when it stopped, but no "
        "findings were written from them."
        if sources_retrieved
        else "No sources had been retrieved when it stopped."
    )
    return (
        "[Research Incomplete — step limit reached]\n"
        f"This research step was stopped by a fixed limit of {limit} tool-call rounds "
        "before it produced any findings. "
        f"{retrieved}\n\n"
        "The cause is the limit itself. It is NOT a timeout, NOT an API failure, and "
        "NOT evidence that the material does not exist or could not be found.\n\n"
        "REQUIRED: tell the user plainly that this part of the research did not "
        "complete, and that the reason was an internal limit on how much work one "
        "research step may do. Suggest narrowing the question so the remaining work "
        "fits. Do NOT present this as a legal finding or as a negative result. Do NOT "
        "state or speculate about why material was not found — you do not know. Do NOT "
        "call delegate_research again for this same question; the same limit will be "
        "reached again."
    )


def _describe(halts: list) -> tuple:
    """Name what stopped, as specifically as the caller knew. (subject, plural).

    `plural` is returned rather than inferred from the subject string because
    the sentence needs "was"/"were" and this text is read by lawyers — a
    number-agnostic phrasing that avoids the agreement reads worse than getting
    the agreement right.
    """
    steps = [h for h in halts if h.get("step")]
    if steps:
        labels = []
        for h in steps:
            title = (h.get("title") or "").strip()
            labels.append(f"step {h['step']}" + (f" ({title})" if title else ""))
        if len(labels) == 1:
            return f"Research {labels[0]} reached", False
        return (
            "Research " + ", ".join(labels[:-1]) + f" and {labels[-1]} reached",
            True,
        )
    if any(h.get("scope") == "manager" for h in halts):
        return "This request reached", False
    if len(halts) == 1:
        return "One research step reached", False
    return f"{len(halts)} research steps reached", True


def halt_notice(halts: list) -> str:
    """The lawyer-facing disclosure. Code-emitted, always, when a halt occurred.

    Prepended rather than appended, deliberately: this is a warning about the
    reliability of everything below it, and a warning read after the findings
    have been relied on is not a warning. It is deliberately short — the answer
    is the product, this is a label on it.
    """
    if not halts:
        return ""
    limit = next((h.get("limit") for h in halts if h.get("limit")), 20)
    subject, plural = _describe(halts)
    return (
        "> **⚠ This answer is incomplete.** "
        f"{subject} a fixed internal limit of {limit} tool-call rounds and "
        f"{'were' if plural else 'was'} stopped before "
        f"{'they' if plural else 'it'} finished. This is a limit on how much work one "
        "research step may do — it is **not** a timeout, and it is **not** a finding "
        "that the material does not exist. Treat the coverage below as partial, and "
        "consider asking again with a narrower question."
    )


def apply_halt_disclosure(text: str, halts: Optional[Iterable]) -> tuple:
    """Strip the raw markers and prepend the notice. Returns (text, disclosed).

    Idempotent: the notice is prepended only if it is not already there, so this
    is safe at the worker seam and again at the answer seam.

    Called with no halts it still strips — a marker can reach an answer by a
    route we have not thought of, and it must never render either way.
    """
    out, _ = strip_halt_markers(text or "")
    halts = list(halts or [])
    if not halts:
        return out, False
    notice = halt_notice(halts)
    if not notice or notice in out:
        return out, bool(notice)
    return (notice + "\n\n" + out).strip() if out else notice, True
