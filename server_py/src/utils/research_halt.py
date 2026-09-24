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

**P3.8 — the halted worker's lost findings.** A halt discarded every retrieval
the worker had paid for: `halt_worker_report` replaced the content outright,
so 16 sources reached the rail behind 6340's empty halted turn and 6335's
worker, with five provisions of the Insolvency Act 1986 in its context, told
the lawyer only "could you narrow this down?". `run_halt_writeup` is the fix:
at the cap, `chat_loop` makes ONE more call with NO tools and an instruction
to write up what is already in the conversation, and the halt keeps its
status (`halted.written_up` says whether that round produced anything). The
disclosure is untouched — the header above the partial findings is still
addressed to the agent, and the lawyer's notice is still prepended by code —
because a partial report that reads as complete is the failure P2.1 exists to
prevent. Prototyped on the seam before it was built: two tool-free draws from
6335's recorded retrievals both produced a structured partial report whose
every link the tools had returned, and both said the Schedule B1 paragraphs
had not been retrieved rather than inventing them (SESSION_LOG Session 18).

**P4.5 — the lost step, which is not a halt.** A worker's final completion
can come back empty on every attempt of `chat_loop`'s bounded retry (P4.2).
`chat_loop` then returns `content: ""` with no flag, and before this the report
the Manager or the synthesis received was the scope block alone, "Searched the
legislation index 2 time(s) for: ...", which reads as searched and found
nothing (6409 r3 t11, 6373 r1 t3), or nothing at all for a case-law step, which
the synthesis told a lawyer "found no results" (6375 r3 t2). So a lost step
gets its own label, in code, the way a halt does, with its own wording:
`halt_notice` says "a fixed internal limit of 20 tool-call rounds", which is
false for a lost reply, and Invariant 1 is that the disclosure is TRUE. Two
differences from the halt, both from the stored runs: the report does not
forbid a further `delegate_research` (the Manager re-delegated after 15 of 18
lost worker reports and every later delegation returned a body), and it never
says "not a timeout" (6409's failed attempts ended "Upstream idle timeout
exceeded"). The block is closed, so the answer seam can strip it whole if a
Manager copies it.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Callable, Iterable, Optional

logger = logging.getLogger("app")

__all__ = [
    "HALT_MARKER",
    "halt_marker_text",
    "strip_halt_markers",
    "halt_writeup_instruction",
    "run_halt_writeup",
    "halt_worker_report",
    "halt_notice",
    "apply_halt_disclosure",
    "LOST_REPORT_TAG",
    "lost_worker_report",
    "strip_lost_blocks",
    "lost_notice",
    "apply_lost_disclosure",
    "progress_result",
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


def halt_writeup_instruction(limit: int) -> str:
    """The message appended at the step cap: write up what you have, tool-free.

    Addressed to the agent whose loop just hit the cap, in the conversation
    that holds its retrievals. Three things it must do, each learned on this
    work: say plainly that no tool will run again (the model otherwise spends
    its last turn calling one); say what to do with a provision it needed and
    did not reach (state it was not retrieved because the limit was reached —
    never that it does not exist, the bare negative P2.2 exists to stop, and
    the shape P2.7's and P3.1's stop messages already use); and name the stop
    correctly (a fixed limit, not a timeout — 6340's falsehood).
    """
    return (
        "[STEP LIMIT REACHED — WRITE UP NOW]\n"
        f"You have used all {limit} tool-call rounds this research step is "
        "allowed. No further tool call will be executed: this is your final "
        "turn and it has no tools.\n"
        "Write your report NOW, in the required output structure, from the "
        "results already in this conversation.\n"
        "- Use only what those results contain. Cite only provisions, cases "
        "and URLs that appear in them.\n"
        "- Where something you needed was not retrieved before the limit, say "
        "that it was not retrieved because this step's limit was reached. Do "
        "NOT say it does not exist, was not made, or could not be found, and do "
        "NOT speculate about why it was not retrieved.\n"
        "- Name the stop correctly if you mention it: a fixed limit on how much "
        "work one research step may do — not a time limit, not an error.\n"
        "- Do not call any tool. Do not ask for more time."
    )


# What a tool call made in the write-up round gets back. It should never run:
# the round is made with no tool schemas. If a model calls one anyway, the
# nested loop is capped at that very round, so the call gets this and the
# write-up is abandoned for the plain halt.
_NO_TOOLS_AT_CAP = (
    "No tool is available in this final round. Write your report from the "
    "results already in this conversation."
)


async def run_halt_writeup(
    chat_loop_fn: Callable,
    messages: list,
    model: str,
    cancel_event: Optional[asyncio.Event],
    num_ctx: int,
    on_chunk: Optional[Callable],
    emit_tool_details: bool,
    timing_collector,
    turn: int,
    limit: int,
    log_prefix: str = "[ChatLoop]",
) -> str:
    """One bounded, tool-free call at the step cap. Returns the write-up or "".

    Shared by both providers' `chat_loop`, which pass themselves in: the
    nested call is that same loop, given no tools, with `max_turns` set to the
    very next round and `_final_round=True`, so it can make at most one model
    call and, if the model calls a tool regardless, one more round that ends in
    the plain halt. Fail-soft on any error — the caller then returns exactly
    what it returned before this existed. A cancel is a `BaseException` and
    still propagates.
    """
    async def _no_tools(name: str, args: dict) -> str:
        return _NO_TOOLS_AT_CAP

    try:
        out = await chat_loop_fn(
            [*messages, {"role": "user", "content": halt_writeup_instruction(limit)}],
            model, cancel_event, num_ctx, [], _no_tools, on_chunk,
            emit_tool_details=emit_tool_details,
            timing_collector=timing_collector,
            _turn=turn,
            max_turns=turn + 1,
            _final_round=True,
        )
    except Exception as e:  # noqa: BLE001 — fail-soft by design; see docstring
        logger.warning(
            "%s Write-up at the step cap failed — keeping the plain halt: %s",
            log_prefix, e,
        )
        return ""
    if not isinstance(out, dict) or out.get("halted") or out.get("tool_calls"):
        logger.warning(
            "%s Write-up round called a tool or halted — keeping the plain halt",
            log_prefix,
        )
        return ""
    text, _ = strip_halt_markers(out.get("content") or "")
    return text.strip()


def halt_worker_report(halt: dict, sources_retrieved: int = 0, writeup: str = "") -> str:
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

    P3.8: with a `writeup` (the final tool-free round's output), the report is
    the same header, saying the findings are partial, above those findings.
    Without one the text is byte-for-byte what P2.1 shipped.
    """
    limit = halt.get("limit", 20)
    if writeup:
        retrieved = (
            f"{sources_retrieved} source(s) had been retrieved when it stopped"
            if sources_retrieved
            else "Some material may have been retrieved when it stopped"
        )
        return (
            "[Research Incomplete — step limit reached; PARTIAL findings below]\n"
            f"This research step was stopped by a fixed limit of {limit} tool-call rounds "
            "before it finished. "
            f"{retrieved}, and the findings below were written from those "
            "retrievals alone, in one final round with no tools. They are PARTIAL: "
            "anything the step had not yet retrieved is absent from them.\n\n"
            "The cause is the limit itself. It is NOT a timeout, NOT an API failure, and "
            "NOT evidence that the material does not exist or could not be found.\n\n"
            "REQUIRED: use the findings below, and tell the user plainly that this part "
            "of the research did not complete, and that the reason was an internal "
            "limit on how much work one research step may do. Suggest narrowing the "
            "question so the remaining work fits. Do NOT present the stop as a legal "
            "finding or as a negative result. Do NOT state or speculate about why "
            "material was not retrieved — you do not know. Do NOT call delegate_research "
            "again for this same question; the same limit will be reached again.\n\n"
            "--- PARTIAL FINDINGS (written after the limit was reached) ---\n"
            f"{writeup}"
        )
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


# ---------------------------------------------------------------------------
# P4.5: a step whose final reply was lost
# ---------------------------------------------------------------------------

LOST_REPORT_TAG = "[Research Incomplete — answer lost]"
LOST_REPORT_CLOSE = "[/Research Incomplete]"
# The whole block, or a stray marker if a model quoted only one line of it.
_LOST_BLOCK = re.compile(
    re.escape(LOST_REPORT_TAG) + r"[\s\S]*?" + re.escape(LOST_REPORT_CLOSE)
)
_LOST_MARKER = re.compile(
    re.escape(LOST_REPORT_TAG) + "|" + re.escape(LOST_REPORT_CLOSE)
)


def lost_worker_report(sources_retrieved: int = 0) -> str:
    """What a worker whose final reply was lost hands back in place of a report.

    Addressed to the agent that reads it, like `halt_worker_report`. The
    worker's scope block is appended AFTER it by `run_worker_agent`, so the
    first thing the Manager or the synthesis reads is that the answer was lost,
    and the search record below reads as work done, not as a search that found
    nothing.
    """
    retrieved = (
        f"{sources_retrieved} source(s) had been retrieved by then; none of them "
        "was written up."
        if sources_retrieved
        else "No sources had been retrieved by then."
    )
    return (
        f"{LOST_REPORT_TAG}\n"
        "This research step ran, but the language model's final reply (the "
        "research agent's own write-up) came back empty on every attempt, so it "
        f"wrote no findings. {retrieved}\n\n"
        "The cause is a lost model reply. It is NOT a fault in the legislation "
        "index or any other database, NOT the step limit, and NOT evidence that "
        "the material does not exist or could not be found. Any search record "
        "below lists what the step ran: it is a record of work, not findings, and "
        "nothing was concluded from it.\n\n"
        "REQUIRED: do NOT tell the user that anything was not found, does not "
        "exist or was not made on the strength of this step. If you can call "
        "delegate_research, you may call it once more for the same question: the "
        "failure is intermittent, and a repeat has usually returned findings. "
        "Otherwise, or if it fails again, tell the user plainly that this part of "
        "the research did not return its findings, and that the reason was a lost "
        "reply from the language model (not the database, and not a finding about "
        "the law). Do NOT invent findings or answer from memory.\n"
        f"{LOST_REPORT_CLOSE}"
    )


def strip_lost_blocks(text: str) -> tuple:
    """Remove every lost-report block, and any stray marker, from `text`.
    Returns (text, count). Unconditional, like `strip_halt_markers`: the block
    is addressed to an agent and must never render to a lawyer."""
    if not text:
        return text, 0
    out, n = _LOST_BLOCK.subn("", text)
    out, n2 = _LOST_MARKER.subn("", out)
    n += n2
    if n:
        out = re.sub(r"\n{3,}", "\n\n", out).strip()
    return out, n


def lost_notice(lost: list, any_completed: bool = True) -> str:
    """The lawyer-facing disclosure of a lost step. Code-emitted.

    Deliberately its own wording, not `halt_notice`'s: no limit was reached.
    `any_completed` says whether any research in the turn did return findings,
    which decides the last sentence: the answer below either rests on partial
    research or on none.
    """
    if not lost:
        return ""
    steps = [x for x in lost if x.get("step")]
    if steps:
        labels = []
        for x in sorted(steps, key=lambda y: y["step"]):
            title = (x.get("title") or "").strip()
            labels.append(f"step {x['step']}" + (f" ({title})" if title else ""))
        if len(labels) == 1:
            subject, plural = f"Research {labels[0]}", False
        else:
            subject = "Research " + ", ".join(labels[:-1]) + f" and {labels[-1]}"
            plural = True
    elif len(lost) == 1:
        subject, plural = "One research step", False
    else:
        subject, plural = f"{len(lost)} research steps", True
    tail = (
        "Treat the coverage below as partial, and consider asking again."
        if any_completed
        else "No completed research stands behind what follows, so do not rely "
             "on it as researched. Please ask again."
    )
    return (
        "> **⚠ This answer is incomplete.** "
        f"{subject} did not return {'their' if plural else 'its'} findings: the "
        "model's reply came back empty on every attempt, so what "
        f"{'they' if plural else 'it'} retrieved did not reach this answer. This "
        "is **not** the step limit, and it is **not** a finding that the "
        f"material does not exist. {tail}"
    )


def apply_lost_disclosure(text: str, lost: Optional[Iterable],
                          any_completed: bool = True) -> tuple:
    """Strip the lost-report blocks and prepend the notice. Returns
    (text, disclosed). Idempotent; strips even with nothing lost."""
    out, _ = strip_lost_blocks(text or "")
    lost = list(lost or [])
    if not lost:
        return out, False
    notice = lost_notice(lost, any_completed)
    if notice in out:
        return out, True
    return (notice + "\n\n" + out).strip() if out else notice, True


def progress_result(result: dict, step: bool) -> str:
    """The `tool_end` progress event's `result` for one worker run.

    It used to read "Step complete" (and "Research Complete") for every run,
    halted or lost. The chat UI does not show it; the developer page and an
    eval harness reading the stream do.
    """
    if result.get("lost"):
        outcome = "incomplete: no reply returned"
    elif result.get("halted"):
        outcome = "incomplete: stopped at the step limit" + (
            " (partial findings)" if result["halted"].get("written_up") else "")
    else:
        return "Step complete" if step else "Research Complete"
    return ("Step " if step else "Research ") + outcome
