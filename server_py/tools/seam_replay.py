"""Replay ONE composition seam from a stored run file, for a few cents.

**Why this exists.** Every fix since P2.2 has been a prompt or composition
change, and P3.1 established that the retrieval upstream of them was already
correct: in 9 of 9 HEAD runs the provision the lawyer wanted had been retrieved
with all its subsections, and the depth was lost while the answer was written.
We were nonetheless testing those changes by replaying whole sessions, paying
for retrieval, summarisation and every worker round again to see how the model
writes one answer. Measured over `wave2`: a Deep Research turn averages $0.71
and 20 of 155 turns carry 48% of a sweep's cost.

A stored run file already holds what each seam was handed — each step's
findings, each tool's result, each worker's report. This tool rebuilds one
seam's input from that fixture **using the product's own builders**, makes the
single model call, and grades the output. Both failures the first P3.1 smoke
run found (the synthesis flattening pinpoints, and a Worker rule that never
fired) are visible here for the price of one call.

**What it is not.** Everything upstream is frozen: the retrieval is whatever
the recorded run retrieved, so this cannot test a retrieval change, and it
cannot replace an acceptance sweep. It is the iterate-cheaply step before one.

Usage (from `server_py/`, with the pinned model — `tools.replay pin`):

    python -m tools.seam_replay synthesis --run <run.json> --turn 1
    python -m tools.seam_replay synthesis --run <run.json> --turn 1 --without-fix
    python -m tools.seam_replay worker --run <run.json> --turn 1 [--delegation 1]
    python -m tools.seam_replay worker --run <run.json> --turn 1 --from-raw
    python -m tools.seam_replay manager --run <run.json> --turn 1 [--without-fix] [--no-tools]

`--without-fix` rebuilds the seam as it was at a given commit (default the
commit before P3.1's product code): the synthesis prompt from that revision
for the turn's research type, and the pinpoint block only if that revision
added one (P4.7: it used to be stripped whatever the revision, so an A/B at a
post-P3.1 commit changed two things). Pass `--rev` explicitly. That is how
this tool was validated — see `tests/test_seam_replay.py` and SESSION_LOG
Session 17.

`--from-raw` (Worker seam, P3.11) rebuilds the blocks the product appends after
a SUMMARISED result from each tool's recorded `raw_result`, through the
product's own builder — so a block built since the run was recorded reaches
the seam. The recorded payload is the before-column; `--from-raw` the after.

`--apply-lost` (synthesis and Manager seams, P4.5) rebuilds every recorded
report whose worker's final reply was lost (no halt, no error, and a report
that is empty or the scope block alone) as the product now builds it: the
label from `lost_worker_report`, with the source count the product would have
had (re-extracted from the recorded raw results by the product's own
extractor), then the recorded report. The synthesis is also handed the lost
steps (`incomplete_steps_note`), and the draw is put through the answer seam's
`apply_lost_disclosure`. Without it the recorded payload is the before-column.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tools.replay_report as rr  # noqa: E402
from src.agent import agent_core, agent_shared  # noqa: E402
from src.agent.openrouter_client import chat_loop  # noqa: E402
from src.agent.provider_factory import set_request_provider_config  # noqa: E402
from src.prompts import get_worker_system_prompt  # noqa: E402
from src.utils.citation_links import (  # noqa: E402
    provision_url_block,
    restore_dropped_siblings,
)
from src.utils.research_halt import (  # noqa: E402
    apply_lost_disclosure,
    halt_writeup_instruction,
    lost_worker_report,
)
from src.utils.search_scope import strip_scope_blocks  # noqa: E402
from src.utils.stopwatch import TimingCollector  # noqa: E402
from src.utils.suggestions import extract_suggestions  # noqa: E402

DEFAULT_DB_URL = "postgresql://lexuser:lexpassword@localhost/lexchat"
# The commit before P3.1's product code, for `--without-fix`.
PRE_P31_REV = "2d9ae11"


# --- the fixture ------------------------------------------------------------


def load_turn(run_path: Path, turn: int) -> tuple:
    """(run doc, turn doc) for one turn of a stored replay run file."""
    doc = json.loads(run_path.read_text(encoding="utf-8"))
    for t in doc.get("turns", []):
        if t.get("turn") == turn:
            return doc, t
    raise SystemExit(
        f"turn {turn} not in {run_path.name} "
        f"(has {[t.get('turn') for t in doc.get('turns', [])]})"
    )


def is_lost_shaped(dg: dict) -> bool:
    """A recorded delegation whose worker's final reply was lost, before
    P4.5 labelled it: it did not halt or raise, and its report is empty or
    the scope block alone (`replay_report.lost_sites`' reading)."""
    if dg.get("halted") or dg.get("error") or dg.get("lost"):
        return False
    return rr._report_shape(dg.get("report") or "", None) in ("empty", "scope")


def sources_retrieved(dg: dict) -> int:
    """The sources the product's accumulator would have held for this worker
    run, re-extracted from the recorded raw results by the product's own
    extractor, so the label's count is the one the product would state."""
    from src.agent.agent_shared import _extract_sources_from_tool

    acc: list = []
    for t in dg.get("tools") or []:
        try:
            _extract_sources_from_tool(t.get("name") or "", t.get("args") or {},
                                       t.get("raw_result") or "", acc)
        except Exception:  # noqa: BLE001 — a count, not a gate
            pass
    return len(acc)


def lost_report_for(dg: dict) -> str:
    """The recorded report as the product now builds it for a lost reply:
    the label, then what the step recorded (its scope block, or nothing)."""
    return lost_worker_report(sources_retrieved(dg)) + (dg.get("report") or "")


def lost_from(turn: dict, apply_lost: bool = False) -> list:
    """The lost plan steps, in the shape `incomplete_steps_note` expects:
    recorded as `lost` (schema v6), or lost-shaped when `apply_lost`."""
    out = []
    for dg in (turn.get("audit") or {}).get("delegations", []):
        if dg.get("step") is None:
            continue
        if dg.get("lost"):
            rec = dict(dg["lost"])
        elif apply_lost and is_lost_shaped(dg):
            rec = {"reason": "empty_completion", "sources_retrieved": sources_retrieved(dg)}
        else:
            continue
        out.append({**rec, "scope": "step", "step": dg.get("step"),
                    "title": dg.get("title") or ""})
    return out


def step_findings_from(turn: dict, apply_lost: bool = False) -> list:
    """The Deep Research step findings, as `run_deep_research` assembled them.

    The stored report is what the step handed the synthesis, scope block and
    all, so it is used verbatim. `plan` gives each step its title and detail.
    With `apply_lost` (P4.5), a lost-shaped report is rebuilt by
    `lost_report_for`.
    """
    plan_steps = ((turn.get("plan") or {}).get("steps")) or []
    by_step = {}
    for dg in (turn.get("audit") or {}).get("delegations", []):
        n = dg.get("step")
        if n is not None:
            by_step[n] = dg
    findings = []
    for i, step in enumerate(plan_steps, 1):
        dg = by_step.get(i) or {}
        findings.append({
            "title": step.get("title") or f"Step {i}",
            "detail": step.get("detail") or "",
            "content": (lost_report_for(dg) if apply_lost and dg and is_lost_shaped(dg)
                        else dg.get("report") or ""),
        })
    return findings


def halts_from(turn: dict) -> list:
    """The halted steps, in the shape `incomplete_steps_note` expects."""
    out = []
    for dg in (turn.get("audit") or {}).get("delegations", []):
        halted = dg.get("halted")
        if halted:
            out.append({**halted, "scope": "step", "step": dg.get("step"),
                        "title": dg.get("title") or ""})
    return out


def _prompt_constant_at(rev: str, name: str) -> str:
    """One string constant out of `src/prompts.py` at a git revision.

    Read with a regex rather than by importing the old module: it only has to
    recover a triple-quoted constant, and exec'ing a whole historical prompts
    module would drag its imports in with it.
    """
    blob = subprocess.run(
        ["git", "show", f"{rev}:server_py/src/prompts.py"],
        capture_output=True, check=True,
        cwd=str(Path(__file__).resolve().parents[2]),
    ).stdout.decode("utf-8")
    m = re.search(rf'(?ms)^{re.escape(name)}\s*=\s*"""(.*?)"""', blob)
    if not m:
        raise SystemExit(f"{name} not found in prompts.py at {rev}")
    return m.group(1)


# --- the seams --------------------------------------------------------------


def _file_at(rev: str, path: str) -> str:
    """One tracked file's text at a git revision ("" if it is not there)."""
    proc = subprocess.run(
        ["git", "show", f"{rev}:{path}"], capture_output=True,
        cwd=str(Path(__file__).resolve().parents[2]),
    )
    return proc.stdout.decode("utf-8") if proc.returncode == 0 else ""


def rev_has_pinpoint_block(rev: str) -> bool:
    """Did the synthesis builder at `rev` append P3.1's pinpoint block?

    **Read from the revision, not assumed (P4.7, Session 26).** `--without-fix`
    used to strip the block whatever `--rev` was, because the only A/B it had
    served was P3.1's own, whose before-side predates the block. A P4.7
    before-side at a post-P3.1 commit then differed from the after-side in the
    prompt AND in the block, so the A/B measured two changes as one. P4.6
    found the same class of bug in the Worker seam."""
    return "pinpoint_block(" in _file_at(rev, "server_py/src/agent/agent_core.py")


def _synthesis_prompt_at(rev: str, research_mode: str) -> str:
    """The synthesis system prompt as the code at `rev` built it for this
    research type.

    Before P4.7 it was one literal, `DEEP_RESEARCH_SYNTHESIS_PROMPT`, the same
    for every type, read with `_prompt_constant_at`. From P4.7 it is built per
    type by `get_deep_research_synthesis_prompt`, which a regex cannot
    recover, so that revision's `prompts.py` is executed in isolation, its
    relative imports resolving against the working tree's `src` package (the
    constants it imports are UI strings), and the function is called."""
    blob = _file_at(rev, "server_py/src/prompts.py")
    if not blob:
        raise SystemExit(f"server_py/src/prompts.py not found at {rev}")
    if "def get_deep_research_synthesis_prompt" not in blob:
        return _prompt_constant_at(rev, "DEEP_RESEARCH_SYNTHESIS_PROMPT")
    import types

    mod = types.ModuleType(f"src._prompts_at_{rev}")
    mod.__package__ = "src"
    exec(compile(blob, f"{rev}:server_py/src/prompts.py", "exec"), mod.__dict__)  # noqa: S102
    return mod.get_deep_research_synthesis_prompt(research_mode)


def strip_pinpoint_block(body: str) -> str:
    start = body.find("\n\n[PINPOINTS TO KEEP")
    if start < 0:
        return body
    end = body.find("[/PINPOINTS TO KEEP]", start)
    return body[:start] + (body[end + len("[/PINPOINTS TO KEEP]"):] if end >= 0 else "")


def synthesis_messages(doc: dict, turn: dict, without_fix: bool = False,
                       rev: str = PRE_P31_REV, apply_lost: bool = False) -> list:
    """The Deep Research synthesis seam, via the product's own builder.

    `--without-fix` rebuilds it as the code at `rev` did: that revision's
    prompt for the turn's research type, and the pinpoint block only if that
    revision's builder added one. Nothing else in the payload changes.
    `--apply-lost` (P4.5): lost-shaped step reports are labelled and the lost
    steps are named in the note."""
    findings = step_findings_from(turn, apply_lost)
    if not any(f["content"] for f in findings):
        raise SystemExit("this turn has no Deep Research step findings "
                         "(is it a `plan` turn?)")
    research_mode = _cfg_for(doc, turn)["_research_mode"]
    messages = agent_core.build_synthesis_messages(
        turn.get("question") or "", turn.get("plan") or {}, findings,
        halts_from(turn), len(findings), research_mode=research_mode,
        lost=lost_from(turn, apply_lost),
    )
    if without_fix:
        messages[0]["content"] = _synthesis_prompt_at(rev, research_mode)
        if not rev_has_pinpoint_block(rev):
            messages[1]["content"] = strip_pinpoint_block(messages[1]["content"])
    return messages


def rebuilt_result(tool: dict) -> str:
    """The recorded `final_result` with the blocks the product appends after a
    SUMMARISED result rebuilt from the recorded `raw_result`.

    **Why.** The seam replays `final_result`, which is what the Worker was
    shown at the time. A block built in `run_worker_tool` from the raw result
    (P1.6's URLs, P3.11's outline) is therefore in a fixture only if it
    existed when the run was recorded, and a row whose fix IS such a block
    cannot be prototyped here without this. The summary itself is kept as
    recorded (re-summarising would cost the call this tool exists to avoid)
    and so are the per-tool notes after it; only the summarised-path blocks
    are rebuilt, through `agent_shared.summarised_result_blocks`, the
    product's own builder.

    The rebuilt blocks replace the recorded URL block where it is found (that
    is where the product puts them); on a fixture recorded before P1.6 they
    go in front of the scope note, else at the end. An unsummarised result,
    or one with no raw result, is returned as recorded.
    """
    final = tool.get("final_result") or ""
    raw = tool.get("raw_result")
    if not tool.get("summarised") or not raw:
        return final
    old = provision_url_block(raw)
    new = agent_shared.summarised_result_blocks(tool.get("name") or "", raw)
    if not new or new == old:
        return final
    if old and old in final:
        return final.replace(old, new, 1)
    cut = final.find("\n\n[SEARCH SCOPE")
    return final[:cut] + new + final[cut:] if cut >= 0 else final + new


def _prompt_constant_in_tree(name: str) -> str:
    """The same constant as `_prompt_constant_at`, read from the working tree."""
    text = (Path(__file__).resolve().parents[1] / "src" / "prompts.py").read_text(
        encoding="utf-8")
    m = re.search(rf'(?ms)^{re.escape(name)}\s*=\s*"""(.*?)"""', text)
    if not m:
        raise SystemExit(f"{name} not found in the working tree's prompts.py")
    return m.group(1)


def worker_constant_name(cfg: dict) -> str:
    """The Worker prompt constant `get_worker_system_prompt` builds on for this
    request: the chat mode first (the quick-lookup Worker), then the research
    type. P4.6: this used to be conversational-or-`WORKER_SYSTEM_PROMPT`, so an
    A/B on a case-law-only or hybrid turn swapped in the wrong Worker."""
    rm = cfg.get("_research_mode") or "legislation_only"
    if (cfg.get("_chat_mode") == "conversational"
            and rm not in ("parliamentary_records", "westminster_records")):
        return "WORKER_SYSTEM_PROMPT_CONVERSATIONAL"
    return {
        "case_law_only": "WORKER_SYSTEM_PROMPT_CASE_LAW",
        "legislation_and_case_law": "WORKER_SYSTEM_PROMPT_HYBRID",
        "parliamentary_records": "PARLIAMENT_WORKER_SYSTEM_PROMPT",
        "westminster_records": "WESTMINSTER_WORKER_SYSTEM_PROMPT",
    }.get(rm, "WORKER_SYSTEM_PROMPT")


def _swap_worker_constant(system: str, cfg: dict, rev: str) -> str:
    """The live Worker prompt with its constant's literal replaced by the one
    at `rev`, so the A/B differs in that literal alone.

    The live prompt is the date line, the literal, the rules appended to it
    and the filter block; the constant at `rev` is the literal alone. Before
    P4.6 the whole prompt was replaced by that bare literal, which dropped the
    date line, the rules and the filter block from the "without" side as well
    as the change being tested. If the working tree's literal is not in the
    live prompt (the constant is no longer one literal), the bare literal is
    used, as before.
    """
    name = worker_constant_name(cfg)
    old = _prompt_constant_at(rev, name)
    try:
        current = _prompt_constant_in_tree(name)
    except SystemExit:
        current = ""
    if current and current in system:
        return system.replace(current, old, 1)
    return old


def worker_messages(doc: dict, turn: dict, delegation: int = 1,
                    without_fix: bool = False, rev: str = PRE_P31_REV,
                    from_raw: bool = False) -> list:
    """The Worker's composition seam: its own prompt, brief and tool results.

    **An approximation, and it says so.** The product's Worker reaches this
    point through a ReAct loop; here the recorded tool results are replayed
    into the history as one round and the call is made with no tools, so the
    model must compose. What it tests is "given exactly these retrievals, what
    does the Worker write" — which is where 6348's s.36(2) was lost.

    **A HALTED delegation is the P3.8 seam.** When the recorded run stopped at
    the step cap, the closing message is the product's own write-up
    instruction (`halt_writeup_instruction`, the one `chat_loop` now appends
    at the cap), not the generic "compose" line — so a draw here is the
    write-up round the product would make from those retrievals, for the
    price of one call. `--without-fix` keeps the generic line, which is the
    only way to A/B the instruction itself.

    **`from_raw` rebuilds each summarised result's appended blocks from its
    recorded raw result** (`rebuilt_result`), so a block the product has
    grown since the run was recorded reaches the seam. The recorded payload
    is the before-column; `--from-raw` is the after.
    """
    dgs = (turn.get("audit") or {}).get("delegations", [])
    if not dgs:
        raise SystemExit("this turn has no delegation to compose from")
    dg = dgs[min(max(delegation, 1), len(dgs)) - 1]
    tools = [t for t in (dg.get("tools") or []) if not t.get("budget_blocked")]
    if not tools:
        raise SystemExit("that delegation ran no tools")
    halted = dg.get("halted") or None
    closing = "Compose your report now from the results above."
    if halted and not without_fix:
        closing = halt_writeup_instruction(int(halted.get("limit") or 20))

    cfg = _cfg_for(doc, turn)
    system = get_worker_system_prompt(cfg.get("_research_mode") or "legislation_only", cfg)
    if without_fix:
        system = _swap_worker_constant(system, cfg, rev)
    calls, results = [], []
    for i, t in enumerate(tools, 1):
        cid = f"call_{i:02d}"
        calls.append({"id": cid, "type": "function", "function": {
            "name": t.get("name") or "", "arguments": json.dumps(t.get("args") or {})}})
        content = t.get("final_result") or ""
        if from_raw:
            content = rebuilt_result(t)
        results.append({"role": "tool", "tool_call_id": cid,
                        "name": t.get("name") or "",
                        "content": content})
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": dg.get("brief") or turn.get("question") or ""},
        {"role": "assistant", "content": "", "tool_calls": calls},
        *results,
        {"role": "user", "content": closing},
    ]


def worker_first_round_messages(doc: dict, turn: dict, delegation: int = 1,
                                without_fix: bool = False,
                                rev: str = PRE_P31_REV) -> list:
    """The Worker's FIRST round (P4.6): its prompt and the brief, nothing else.

    **Why.** The composition seam above needs recorded tool results, and in
    the stored sweeps most of P4.6's scripted sentences came from a Worker
    that made NO tool call: a case-law question sent to the legislation
    Worker, which has no case-law tool and wrote its report at once. The
    first round is therefore the seam for that shape, and it is also the
    probe Session 22 asked for before any prompt change: does the edit move
    what the Worker decides to search? `run_first_round` offers the Worker its
    real tools and stops at the first call it makes.
    """
    dgs = (turn.get("audit") or {}).get("delegations", [])
    if not dgs:
        raise SystemExit("this turn has no delegation to take a brief from")
    dg = dgs[min(max(delegation, 1), len(dgs)) - 1]
    cfg = _cfg_for(doc, turn)
    system = get_worker_system_prompt(cfg.get("_research_mode") or "legislation_only", cfg)
    if without_fix:
        system = _swap_worker_constant(system, cfg, rev)
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": dg.get("brief") or turn.get("question") or ""},
    ]


def tool_rounds(tools: list, tolerance_s: float = 1.0) -> list:
    """Group a delegation's recorded tool calls into the ReAct rounds that
    issued them (P4.10).

    The audit records no round index, but a round's tools are started together
    and the next round cannot start until the model has answered the last, so a
    tool that starts after every tool of the current round has finished (plus
    `tolerance_s`, which absorbs a memo hit's zero duration) opens a new round.
    Checked against the recorded `react_turn` of every stored (a) call before
    it was used.
    """
    rounds: list = []
    end = 0.0
    for t in sorted(tools, key=lambda x: float(x.get("started_at") or 0.0)):
        s = float(t.get("started_at") or 0.0)
        e = s + float(t.get("duration_s") or 0.0)
        if rounds and s <= end + tolerance_s:
            rounds[-1].append(t)
            end = max(end, e)
        else:
            rounds.append([t])
            end = e
    return rounds


def worker_date_line(d: date) -> str:
    """The Worker prompt's first line, as `get_worker_system_prompt` writes it."""
    return f"Today's date is {d.strftime('%d %B %Y')}."


def as_sent_date(value: Optional[str], doc: dict) -> Optional[date]:
    """`--date`: None (today, as the prompt builder writes it), "recorded" (the
    day the run started, `started_at`), or an ISO date.

    P4.10: at temperature 0 the pinned model draws much the same completion
    for the same bytes, so the date line alone decided whether a stored (a)
    payload ran away. Today's date is not the payload that was sent.
    """
    if not value:
        return None
    raw = (doc.get("started_at") or "")[:10] if value == "recorded" else value
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise SystemExit(f"--date: {value!r} is neither 'recorded' nor YYYY-MM-DD"
                         + (" (the run has no started_at)" if value == "recorded" else ""))


def worker_as_sent_messages(doc: dict, turn: dict, delegation: int = 1,
                            upto_round: Optional[int] = None,
                            on_date: Optional[date] = None) -> list:
    """A Worker's model call rebuilt as `chat_loop` sent it (P4.10).

    `worker_messages` is a composition seam: every result in one round, no
    tools offered, and a closing "compose" message. That is not the call that
    reasoned to nothing. This one is: the system prompt, the brief, then each
    recorded round as an assistant tool-call message followed by its results,
    cut after `upto_round` rounds (the probe's `react_turn`; default: every
    round). No closing message; the caller offers the Worker's real tools.

    Faithful only where the recorded brief is what was sent. Since P3.7 code
    appends an instrument-lookup block to the brief that the audit does not
    record, so the command prints the payload's size the way `chat_loop`
    counts it (`sent_chars`) beside the recorded probes'.

    `on_date` replaces the prompt's date line (see `as_sent_date`). The line
    is the same length on any date of the same month-name length.
    """
    dgs = (turn.get("audit") or {}).get("delegations", [])
    if not dgs:
        raise SystemExit("this turn has no delegation to rebuild")
    dg = dgs[min(max(delegation, 1), len(dgs)) - 1]
    rounds = tool_rounds(dg.get("tools") or [])
    if upto_round is not None:
        rounds = rounds[:upto_round]
    cfg = _cfg_for(doc, turn)
    system = get_worker_system_prompt(cfg.get("_research_mode") or "legislation_only", cfg)
    if on_date is not None:
        today = worker_date_line(date.today())
        if today not in system:
            raise SystemExit("the Worker prompt's date line has changed shape; "
                             "--date cannot pin it")
        system = system.replace(today, worker_date_line(on_date), 1)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": dg.get("brief") or turn.get("question") or ""},
    ]
    n = 0
    for rnd in rounds:
        calls, results = [], []
        for t in rnd:
            n += 1
            cid = f"call_{n:02d}"
            calls.append({"id": cid, "type": "function", "function": {
                "name": t.get("name") or "", "arguments": json.dumps(t.get("args") or {})}})
            results.append({"role": "tool", "tool_call_id": cid,
                            "name": t.get("name") or "",
                            "content": t.get("final_result") or ""})
        messages.append({"role": "assistant", "content": "", "tool_calls": calls})
        messages.extend(results)
    return messages


def sent_chars(messages: list) -> int:
    """A payload's size as `chat_loop` logs and probes it."""
    return sum(len(str(m.get("content", "") or "")) for m in messages)


async def run_as_sent(messages: list, cfg: dict, tools: list,
                      extra: Optional[dict] = None) -> dict:
    """ONE streamed attempt of `messages`, with the product's payload shape
    (model, messages, stream, temperature, tools, tool_choice) plus `extra`
    (a lever under test: `reasoning`, `max_tokens`). No retry, so one draw is
    one attempt and an (a) draw costs one attempt, not three.

    Returns what an `empty_completions` record would hold, and the attempt's
    seconds and cost, which no record holds.
    """
    import time

    import httpx

    from src.agent import openrouter_client as oc

    set_request_provider_config(cfg)
    payload = {
        "model": cfg["model"],
        "messages": oc._convert_messages_to_openai(messages),
        "stream": True,
        "temperature": cfg.get("temperature", 0),
    }
    if tools:
        payload["tools"] = oc._convert_tools_to_openai(tools)
        payload["tool_choice"] = "auto"
    payload.update(extra or {})
    out = {"content_chars": 0, "tool_calls": [], "finish_reason": None,
           "native_finish_reason": None, "reasoning_chars": 0,
           "completion_tokens": None, "reasoning_tokens": None, "cost": 0.0,
           "stream_error": None, "seconds": 0.0, "content": ""}
    names: dict = {}
    t0 = time.perf_counter()
    timeout = httpx.Timeout(None, connect=30.0, read=180.0)  # as chat_loop's
    try:
        async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
            async with client.stream("POST", f"{oc._base_url()}/chat/completions",
                                     json=payload, headers=oc._get_headers()) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    raw = line[6:].strip()
                    if raw == "[DONE]":
                        break
                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if data.get("usage"):
                        u = data["usage"]
                        out["completion_tokens"] = u.get("completion_tokens")
                        out["reasoning_tokens"] = (u.get("completion_tokens_details")
                                                   or {}).get("reasoning_tokens")
                        out["cost"] = float(u.get("cost") or 0.0)
                    if data.get("error"):
                        out["stream_error"] = (data["error"].get("message")
                                               if isinstance(data["error"], dict)
                                               else str(data["error"]))
                    for ch in data.get("choices") or []:
                        if ch.get("finish_reason"):
                            out["finish_reason"] = ch["finish_reason"]
                        if ch.get("native_finish_reason"):
                            out["native_finish_reason"] = ch["native_finish_reason"]
                        d = ch.get("delta") or {}
                        out["reasoning_chars"] += len(d.get("reasoning")
                                                      or d.get("reasoning_content") or "")
                        out["content"] += d.get("content") or ""
                        out["content_chars"] += len(d.get("content") or "")
                        for tc in d.get("tool_calls") or []:
                            f = (tc.get("function") or {}).get("name")
                            if f:
                                names[tc.get("index", 0)] = f
    except httpx.TimeoutException as e:
        out["stream_error"] = f"{type(e).__name__} (client read timeout)"
    out["tool_calls"] = [names[k] for k in sorted(names)]
    out["seconds"] = time.perf_counter() - t0
    return out


def as_sent_outcome(r: dict) -> str:
    """"answered", "tool call", or the empty-completion mechanism ((a)-(d)).

    Empty is the product's test (`is_empty_completion`): whitespace alone is
    empty. A capped runaway ended in a lone newline (P4.10, Session 29), which
    `chat_loop` treats as empty and this used to call "answered".
    """
    text = r["content"] if "content" in r else ("x" if r.get("content_chars") else "")
    if (text or "").strip():
        return "answered"
    if r["tool_calls"]:
        return "tool call"
    return "empty (" + rr.empty_mechanism(r) + ")"


def _as_sent_command(args, doc: dict, turn: dict, sid: str) -> int:
    """`worker --as-sent`: redraw a recorded Worker call as it was sent."""
    from src.agent.tools import get_worker_tools

    on_date = as_sent_date(args.date, doc)
    messages = worker_as_sent_messages(doc, turn, args.delegation, args.round, on_date)
    cfg0 = _cfg_for(doc, turn)
    probes = (turn.get("audit") or {}).get("empty_completions") or []
    dgs = (turn.get("audit") or {}).get("delegations", [])
    dg = dgs[min(max(args.delegation, 1), len(dgs)) - 1] if dgs else {}
    rounds = tool_rounds(dg.get("tools") or [])
    extra = {}
    if args.reasoning_effort:
        extra["reasoning"] = {"effort": args.reasoning_effort}
    if args.max_tokens:
        extra["max_tokens"] = args.max_tokens
    print(f"seam=worker --as-sent  session={sid} turn={args.turn} "
          f"delegation={args.delegation}")
    print(f"  recorded rounds: {len(rounds)}; sent here: "
          f"{args.round if args.round is not None else len(rounds)}")
    print(f"  payload: {len(messages)} message(s), sent_chars {sent_chars(messages):,}")
    for sc, rt in sorted({(p.get('sent_chars'), p.get('react_turn')) for p in probes},
                         key=lambda x: (x[1] or 0)):
        print(f"  recorded empty-completion call: sent_chars {sc:,}, react_turn {rt}")
    print(f"  date line: {(on_date or date.today()).strftime('%d %B %Y')} "
          f"({'pinned by --date' if on_date else 'today'})")
    print(f"  lever: {json.dumps(extra) if extra else 'none (the pre-P4.10 payload)'}")
    if args.dry_run:
        return 0
    cfg = asyncio.run(_provider_cfg(cfg0))
    tools = get_worker_tools(cfg0.get("_research_mode") or "legislation_only")
    total = 0.0
    for rep in range(1, args.reps + 1):
        r = asyncio.run(run_as_sent(messages, cfg, tools, extra))
        total += r["cost"]
        print(f"  rep{rep}: {as_sent_outcome(r):<12} ${r['cost']:.4f} {r['seconds']:6.0f}s "
              f"completion_tokens={r['completion_tokens']} "
              f"reasoning_tokens={r['reasoning_tokens']} "
              f"reasoning_chars={r['reasoning_chars']} content_chars={r['content_chars']} "
              f"tools={','.join(r['tool_calls']) or '-'} "
              f"finish={r['finish_reason']}/{r['native_finish_reason']}"
              + (f" error={r['stream_error'][:60]!r}" if r["stream_error"] else ""))
        text = r.get("content") or ""
        if text.strip():
            # What a lever costs in answer quality: links, and the depth grader
            # where the session has a ground truth (6348: s.36(2)).
            grade = _grade(sid, text)
            print(f"      links: {text.count('](http')}"
                  + (f"  depth: {grade}" if grade else ""))
        if args.out:
            d = Path(args.out)
            d.mkdir(parents=True, exist_ok=True)
            lever = "_".join(f"{k}-{v}" for k, v in (
                ("effort", args.reasoning_effort), ("max", args.max_tokens),
                ("date", on_date)) if v)
            (d / f"{sid}_t{args.turn}_d{args.delegation}_as_sent"
                 f"{'_' + lever if lever else ''}_rep{rep}.md").write_text(
                text, encoding="utf-8")
    print(f"  total ${total:.4f}")
    return 0


class _FirstRoundDone(BaseException):
    """Raised by the probe's tool executor to end the loop at the first call.
    A BaseException, so no `except Exception` on the way out swallows it."""


async def run_first_round(messages: list, cfg: dict, tools: list) -> tuple:
    """One Worker round with its real tools offered. Returns (content, calls,
    cost, model): the report it wrote if it called no tool, else the calls."""
    set_request_provider_config(cfg)
    tc = TimingCollector("seam")
    calls: list = []

    async def _seen(event: dict) -> None:
        # `chat_loop` emits the round's whole batch before executing any of it.
        if event.get("type") == "tool_call":
            for c in event.get("tool_calls") or []:
                fn = c.get("function") or {}
                calls.append((fn.get("name") or "", fn.get("arguments") or ""))

    async def _stop(name: str, args: dict) -> str:
        raise _FirstRoundDone()

    try:
        out = await chat_loop(messages, cfg["model"], None, 0, tools, _stop,
                              on_chunk=_seen, emit_tool_details=True,
                              timing_collector=tc)
        content = (out or {}).get("content") or ""
    except _FirstRoundDone:
        content = ""
    return content, calls, tc.total_cost_usd, cfg["model"]


def manager_history(doc: dict, turn_no: int) -> list:
    """The conversation the Manager was sent at `turn_no`, rebuilt the way
    `tools.replay.replay_session` built it: each earlier user turn, then the
    answer the replay got back (a planner clarification's question on a
    clarification turn), stamped with the modes it ran under as the client
    stamps a saved message (P4.1); a turn with no answer adds nothing."""
    default_rm = (doc.get("filters") or {}).get("research_mode") or None
    messages = []
    for t in doc.get("turns", []):
        messages.append({"role": "user", "content": t.get("question") or ""})
        if t.get("turn") == turn_no:
            return messages
        reply = ((t.get("plan_clarification") or {}).get("question")
                 if t.get("status") == "needs_clarification" else t.get("answer"))
        if reply:
            messages.append({"role": "assistant", "content": reply,
                             "research_mode": t.get("research_mode") or default_rm,
                             "chat_mode": t.get("chat_mode")})
    raise SystemExit(f"turn {turn_no} not in the run file")


def manager_cfg(doc: dict, turn: dict, messages: list) -> dict:
    """The Manager's request config, via the product's own builder
    (`build_request_config`), with the feature flags the run recorded.

    `research_mode_enabled` was not recorded before P4.1 made it a pinned flag;
    it defaults to the pinned value (OFF, as on the target), not the app's
    default, so the conversational prompt is the one the acceptance runs.
    """
    from src.routers.agent_request import ChatRequest, build_request_config

    f = doc.get("filters") or {}
    state = doc.get("runtime_state") or {}
    body = ChatRequest(
        messages=messages, model=state.get("model") or "",
        research_mode=turn.get("research_mode") or f.get("research_mode") or "legislation_only",
        jurisdiction=f.get("jurisdiction"), year_from=f.get("year_from"),
        year_to=f.get("year_to"), date_from=f.get("date_from"),
        date_to=f.get("date_to"), legislation_type=f.get("legislation_type"),
        chat_mode=turn.get("chat_mode") or "research",
    )
    features = {k: state[k] for k in (
        "prompt_caching_enabled", "tool_memo_enabled", "suggested_questions_enabled")
        if k in state}
    features["local_prompt_cache_enabled"] = False
    features["research_mode_enabled"] = state.get("research_mode_enabled", False)
    return build_request_config(body, {}, "openrouter", features,
                                chat_mode=body.chat_mode)


def manager_head(doc: dict, turn: dict, without_fix: bool = False,
                 rev: str = PRE_P31_REV, on_date: Optional[date] = None) -> tuple:
    """The Manager's prompt and the conversation up to this turn's question,
    before any delegation: (messages, cfg). The start of `manager_messages`,
    and the whole of the Manager's first round (`--first-round`, P3.15).
    `without_fix` swaps the conversational Manager body for the one at `rev`.
    `on_date` replaces the prompt's date line, as `--as-sent --date` does for
    the Worker (P4.10: that line alone decided what a stored payload drew).
    Messages keep the client's mode stamps; callers strip them."""
    from src.prompts import get_manager_system_prompt
    from src.utils.mode_change import apply_mode_change_marker

    history = manager_history(doc, turn.get("turn"))
    cfg = manager_cfg(doc, turn, history)
    system = get_manager_system_prompt(cfg["_research_mode"], cfg)
    if without_fix:
        # The constant at `rev` is the triple-quoted literal alone; the live
        # body is that literal plus the research-mode hint appended to it.
        import src.prompts as prompts
        live = prompts._MANAGER_CONV_BODY
        hint = prompts.RESEARCH_MODE_HINT_ON
        literal = live[:-len(hint)] if live.endswith(hint) else live
        if literal not in system:
            raise SystemExit("--without-fix: the live conversational body is not in the prompt")
        system = system.replace(literal, _prompt_constant_at(rev, "_MANAGER_CONV_BODY"), 1)
    if on_date is not None:
        today = worker_date_line(date.today())
        if today not in system:
            raise SystemExit("the Manager prompt's date line has changed shape; "
                             "--date cannot pin it")
        system = system.replace(today, worker_date_line(on_date), 1)
    messages = [{"role": "system", "content": system}, *history]
    messages, _change = apply_mode_change_marker(messages, cfg)
    return messages, cfg


def _strip_stamps(messages: list) -> list:
    """The client-side mode stamps are not provider fields."""
    return [{k: v for k, v in m.items() if k not in ("research_mode", "chat_mode")}
            for m in messages]


def lookup_grade(doc: dict, turn: dict, text: str) -> Optional[dict]:
    """`replay_report lookup`'s verdict on `text` as this turn's answer given
    from history (no delegation), where the run file grades a slot here
    (P3.15). None where it does not."""
    t2 = {**turn, "answer": text,
          "audit": {**(turn.get("audit") or {}), "delegations": []}}
    doc2 = {**doc, "turns": [t2 if t.get("turn") == turn.get("turn") else t
                             for t in doc.get("turns") or []]}
    rows = [r for r in rr.lookup_rows(doc2) if r["turn"] == turn.get("turn")]
    if not rows:
        return None
    verdict, why = rr.lookup_verdict(rows[0])
    return {**rows[0], "verdict": verdict, "why": why}


def _named_in(brief: str) -> list:
    """Instrument numbers a delegation brief names (the drift probe's read)."""
    return sorted(set(rr.LK_ANY_NUMBER.findall(brief or "")))


def manager_messages(doc: dict, turn: dict, without_fix: bool = False,
                     rev: str = PRE_P31_REV, apply_lost: bool = False) -> list:
    """The Manager's composition seam (P3.13): the conversation, then each
    recorded delegation as the `delegate_research` call it was and the
    `[Research Agent Result]` it returned, then the call that composes.

    Built with the product's builders (`get_manager_system_prompt`,
    `apply_mode_change_marker`), and the tool result is the one
    `manager_tool_executor` returns — the audit's `report` is the worker
    result's `content` verbatim, scope block included. **Approximations:** the
    learning-examples injection (needs the feedback table) is left out, each
    delegation is one round of its own (the live Manager may have batched
    them). **The Manager is offered its tools, as the live call is** (a call
    it makes is refused, and it composes on the next round): tool-free, the
    seam DELIVERED in 3 of 3 draws a payload the live Manager had flattened
    (`wave3_p313` rep 1 turn 1), and with the tools offered it reproduced the
    miss in 3 of 3. `--no-tools` is the tool-free draw. `--without-fix`
    swaps the conversational Manager body for the one at `rev` and hands over
    the bare report. `--apply-lost` (P4.5) hands over a lost-shaped report as
    the product now builds it (`lost_report_for`).
    """
    dgs = [dg for dg in (turn.get("audit") or {}).get("delegations", [])
           if dg.get("step") is None]
    if not dgs:
        raise SystemExit("this turn has no delegation to compose from")
    messages, cfg = manager_head(doc, turn, without_fix, rev)
    for i, dg in enumerate(dgs, 1):
        cid = f"call_{i:02d}"
        messages.append({"role": "assistant", "content": "", "tool_calls": [{
            "id": cid, "type": "function", "function": {
                "name": "delegate_research",
                "arguments": json.dumps({"query": dg.get("brief") or ""})}}]})
        report = (lost_report_for(dg) if apply_lost and is_lost_shaped(dg)
                  else dg.get("report") or "")
        # The product's own builder (P3.13's sibling links included); the
        # pre-fix result is the bare report under the same prefix.
        messages.append({"role": "tool", "tool_call_id": cid,
                         "name": "delegate_research",
                         "content": f"[Research Agent Result]\n{report}" if without_fix
                         else agent_core.worker_result_for_manager(report, cfg)})
    return _strip_stamps(messages)


def _cfg_for(doc: dict, turn: dict) -> dict:
    """The request config the recorded turn ran under (filters included)."""
    f = doc.get("filters") or {}
    return {
        "_provider": "openrouter",
        # The TURN's type, as the request sent it (P4.1); then, for a run file
        # written before turns carried it, the type the product recorded on
        # the turn's audit trace (P4.7); the session filter is only the
        # export's value, and is None where the export was blank (P0.6).
        "_research_mode": (turn.get("research_mode")
                           or (turn.get("audit") or {}).get("research_mode")
                           or f.get("research_mode") or "legislation_only"),
        "_chat_mode": turn.get("chat_mode") or doc.get("filter_snapshot_chat_mode") or "",
        "_jurisdiction": f.get("jurisdiction"),
        "_legislation_type": f.get("legislation_type"),
        "_year_from": f.get("year_from"),
        "_year_to": f.get("year_to"),
    }


# --- the call ---------------------------------------------------------------


async def _provider_cfg(extra: dict) -> dict:
    """Provider settings from `app_settings`, as the app resolves them."""
    import asyncpg

    conn = await asyncpg.connect(DEFAULT_DB_URL)
    try:
        row = await conn.fetchval(
            "SELECT value FROM app_settings WHERE key='provider.openrouter'")
    finally:
        await conn.close()
    p = json.loads(row or "{}")
    if not p.get("api_key"):
        raise SystemExit("no OpenRouter api_key in app_settings")
    cfg = {k: p[k] for k in ("base_url", "api_key", "model", "temperature")
           if p.get(k) is not None}
    cfg.update(extra)
    return cfg


async def _no_tools(name: str, args: dict) -> str:
    return f"Error: Unknown tool {name}"


async def run_seam(messages: list, cfg: dict, tools: Optional[list] = None) -> tuple:
    """One model call, tool-free unless `tools` is given (then a call the model
    makes is refused and it composes on the next round). Returns (content,
    cost, model)."""
    set_request_provider_config(cfg)
    tc = TimingCollector("seam")
    out = await chat_loop(messages, cfg["model"], None, 0, tools or [], _no_tools,
                          timing_collector=tc)
    content = (out or {}).get("content") or ""
    return content, tc.total_cost_usd, cfg["model"]


# --- the command ------------------------------------------------------------


def _grade(session_id: str, text: str) -> str:
    """The depth grader's verdict, when the session has a ground truth."""
    truth = rr.DEPTH_TRUTH.get(str(session_id))
    if not truth:
        return ""
    verdict, graded = rr.depth_verdict(session_id, text)
    body = rr._without_footer(text)
    bits = []
    for req, status, _m, _w in graded:
        deep, total = rr.depth_counts(body, req, truth["acts"])
        bits.append(f"{req.label}: {status} ({deep}/{total} at depth)")
    return verdict + "\n      " + "\n      ".join(bits)


def _scripted_line(text: str) -> str:
    """P4.6's counts for one draw: the failing lines, then the counted ones."""
    c = rr._scripted_counts(text)
    fail = ", ".join(f"{k} {c[k]}" for k in rr.SCRIPTED_NEGATIVES)
    info = ", ".join(f"{k} {c[k]}" for k in rr.SCRIPTED_INFORMATIONAL)
    return f"{rr._scripted_failing(c)} failing ({fail}); counted: {info}"


def _first_round_command(args, doc: dict, turn: dict, sid: str) -> int:
    from src.agent.tools import get_worker_tools

    messages = worker_first_round_messages(doc, turn, args.delegation,
                                           args.without_fix, args.rev)
    cfg_turn = _cfg_for(doc, turn)
    rm = cfg_turn.get("_research_mode") or "legislation_only"
    tools = get_worker_tools(rm)
    # P3.7: the product looks up every instrument the brief names by number
    # before the Worker's first round and appends the outcome to the brief.
    # Rebuilt here by the product's own routing, against live LEX (two cheap
    # calls per instrument, no model). `--without-lookup` is the before side:
    # neither the block nor the tool.
    from src.utils.instrument_lookup import LOOKUP_TOOL, routed_lookup_block

    if args.without_lookup:
        tools = [t for t in tools if t["function"]["name"] != LOOKUP_TOOL]
    else:
        from src.agent.tools.executor import execute_worker_tool

        block = asyncio.run(routed_lookup_block(
            messages[1]["content"], [t["function"]["name"] for t in tools],
            execute_worker_tool))
        messages[1]["content"] += block
    recorded = (turn.get("audit") or {}).get("delegations", [])
    dg = recorded[min(max(args.delegation, 1), len(recorded)) - 1] if recorded else {}
    print(f"seam=worker FIRST ROUND  session={sid} turn={args.turn} "
          f"delegation={args.delegation}  research type={rm}  "
          f"{'WITHOUT fix (' + args.rev + ')' if args.without_fix else 'current code'}"
          f"{'; WITHOUT the P3.7 lookup' if args.without_lookup else ''}")
    print(f"  prompt: {len(messages[0]['content']):,} chars; brief {len(messages[1]['content']):,} "
          f"chars; tools offered: {len(tools)}; recorded run made "
          f"{len(dg.get('tools') or [])} tool call(s)")
    if args.dry_run:
        return 0
    cfg = asyncio.run(_provider_cfg(cfg_turn))
    total = 0.0
    for rep in range(1, args.reps + 1):
        content, calls, cost, model = asyncio.run(run_first_round(messages, cfg, tools))
        total += cost
        if calls:
            names = Counter(n for n, _ in calls)
            print(f"  rep{rep}: ${cost:.4f}  SEARCHED: {len(calls)} call(s) "
                  + ", ".join(f"{n} x{k}" for n, k in names.items()) + f"  model={model}")
        else:
            print(f"  rep{rep}: ${cost:.4f}  WROTE WITHOUT SEARCHING: {len(content):,} chars  "
                  f"model={model}")
            print(f"      scripted negatives (P4.6): {_scripted_line(content)}")
        if args.out and content:
            d = Path(args.out)
            d.mkdir(parents=True, exist_ok=True)
            suffix = ("_nofix" if args.without_fix else "") + (
                "_nolookup" if args.without_lookup else "")
            (d / f"{sid}_t{args.turn}_first{suffix}_rep{rep}.md").write_text(
                content, encoding="utf-8")
        if args.print:
            print(content if content else "\n".join(f"      {n}({a})" for n, a in calls))
    print(f"  total ${total:.4f}")
    return 0


def _manager_first_round_command(args, doc: dict, turn: dict, sid: str) -> int:
    """`manager --first-round` (P3.15): the Manager's first round of a turn,
    its tools offered, stopped at the first call. A turn it answers from its
    history is graded by `replay_report lookup` for the turn's slot; a turn it
    delegates prints the instrument numbers the brief names, which is the
    first-delegation drift probe (Session 22: a Manager prompt edit moved the
    first brief to another Act)."""
    from src.agent.tools import get_manager_tools

    on_date = as_sent_date(args.date, doc)
    messages, _cfg = manager_head(doc, turn, args.without_fix, args.rev, on_date)
    messages = _strip_stamps(messages)
    tools = get_manager_tools("")
    recorded = [d for d in (turn.get("audit") or {}).get("delegations", [])
                if d.get("step") is None]
    print(f"seam=manager FIRST ROUND  session={sid} turn={args.turn}  "
          f"{'WITHOUT fix (' + args.rev + ')' if args.without_fix else 'current code'}  "
          f"date line: {(on_date or date.today()).strftime('%d %B %Y')}")
    print(f"  payload: {len(messages)} message(s), "
          f"{sum(len(m.get('content') or '') for m in messages):,} chars; "
          f"the recorded turn delegated {len(recorded)} time(s)"
          + (f"; its first brief named {', '.join(_named_in(recorded[0].get('brief'))) or 'no number'}"
             if recorded else ""))
    if args.dry_run:
        return 0
    cfg = asyncio.run(_provider_cfg(_cfg_for(doc, turn)))
    total = 0.0
    for rep in range(1, args.reps + 1):
        content, calls, cost, model = asyncio.run(run_first_round(messages, cfg, tools))
        total += cost
        text = ""
        if calls:
            print(f"  rep{rep}: ${cost:.4f}  DELEGATED: "
                  + ", ".join(n for n, _ in calls) + f"  model={model}")
            for name, raw in calls:
                try:
                    brief = (json.loads(raw or "{}") or {}).get("query") or ""
                except ValueError:
                    brief = raw or ""
                if name == "delegate_research":
                    print(f"      brief names: {', '.join(_named_in(brief)) or 'no number'}"
                          f"  ({len(brief):,} chars)")
                    text += brief + "\n"
        else:
            text, _s = extract_suggestions(content)
            g = lookup_grade(doc, turn, text)
            print(f"  rep{rep}: ${cost:.4f}  ANSWERED FROM HISTORY: {len(text):,} chars  "
                  f"model={model}")
            if g:
                k = g["kinds"]
                print(f"      lookup: {g['lid']} {g['verdict']}"
                      f"{' (not graded)' if not g['graded'] else ''}"
                      f"{': ' + g['why'] if g['why'] else ''}  (rec {k['record_absent']}, "
                      f"txt {k['text_only']}, hdg {k['hedged']}, blm {k['blame']})")
        if args.out and text:
            d = Path(args.out)
            d.mkdir(parents=True, exist_ok=True)
            (d / f"{sid}_t{args.turn}_manager_first{'_nofix' if args.without_fix else ''}"
                 f"_rep{rep}.md").write_text(text, encoding="utf-8")
        if args.print:
            print(text)
    print(f"  total ${total:.4f}")
    return 0


def main(argv: Optional[list] = None) -> int:
    rr._utf8_stdout()
    p = argparse.ArgumentParser(prog="seam_replay")
    p.add_argument("seam", choices=["synthesis", "worker", "manager"])
    p.add_argument("--run", required=True, help="a replay run file")
    p.add_argument("--turn", type=int, default=1)
    p.add_argument("--delegation", type=int, default=1, help="worker seam only")
    p.add_argument("--reps", type=int, default=1)
    p.add_argument("--without-fix", action="store_true",
                   help=f"rebuild the seam as at {PRE_P31_REV} (the A/B side)")
    p.add_argument("--rev", default=PRE_P31_REV)
    p.add_argument("--from-raw", action="store_true",
                   help="worker seam only: rebuild each summarised result's "
                        "appended blocks from its recorded raw_result through "
                        "the product's builder (P3.11's outline reaches the seam)")
    p.add_argument("--apply-lost", action="store_true",
                   help="synthesis and manager seams (P4.5): rebuild each lost-shaped "
                        "recorded report (no halt, no error, empty or scope block "
                        "alone) through the product's lost-report builder, and put "
                        "the draw through the answer seam's lost disclosure")
    p.add_argument("--print", action="store_true", help="print the answer")
    p.add_argument("--no-tools", action="store_true",
                   help="manager seam only: make the call tool-free. By default "
                        "the Manager is offered its tools, as the live call is "
                        "(a call it makes is refused), because tool-free it "
                        "delivered a payload the live Manager flattened (P3.13)")
    p.add_argument("--first-round", action="store_true",
                   help="worker seam (P4.6): the Worker's first round - its "
                        "prompt and the brief, with its real tools offered, "
                        "stopped at the first call. Prints the calls it chose, or "
                        "the report it wrote without searching. Manager seam "
                        "(P3.15): the Manager's first round of the turn - an "
                        "answer from history, graded by `replay_report lookup`, "
                        "or the delegation, with the numbers its brief names")
    p.add_argument("--without-lookup", action="store_true",
                   help="--first-round only (P3.7): leave out the instrument-lookup "
                        "block code appends to the brief, and the lookup tool")
    p.add_argument("--as-sent", action="store_true",
                   help="worker seam only (P4.10): the Worker's model call rebuilt "
                        "as chat_loop sent it (recorded rounds, tools offered, no "
                        "closing message), ONE attempt per rep, and the attempt's "
                        "outcome, tokens, seconds and cost")
    p.add_argument("--round", type=int, default=None,
                   help="--as-sent only: send the first N recorded rounds (the "
                        "empty-completion record's react_turn); default all")
    p.add_argument("--reasoning-effort", choices=["low", "medium", "high"],
                   help="--as-sent only: add reasoning.effort to the payload "
                        "(a lever under test; the product sends none)")
    p.add_argument("--max-tokens", type=int, default=None,
                   help="--as-sent only: add max_tokens to the payload. Since P4.10 "
                        "the product's Worker call sends 32000; without this flag "
                        "the seam sends none, i.e. the pre-P4.10 payload")
    p.add_argument("--date", default=None,
                   help="--as-sent, or manager --first-round: the prompt's date line: 'recorded' "
                        "(the run's started_at) or YYYY-MM-DD; default today. The "
                        "date line alone decided whether a stored (a) payload ran "
                        "away (P4.10, Session 29)")
    p.add_argument("--dry-run", action="store_true",
                   help="build the payload and print its shape; no model call")
    p.add_argument("--out", default=None, help="write each answer to this directory")
    args = p.parse_args(list(argv) if argv is not None else None)

    run_path = Path(args.run)
    doc, turn = load_turn(run_path, args.turn)
    sid = str(doc.get("session_id"))
    if args.first_round:
        if args.seam == "manager":
            return _manager_first_round_command(args, doc, turn, sid)
        if args.seam != "worker":
            raise SystemExit("--first-round is a worker or manager seam option")
        return _first_round_command(args, doc, turn, sid)
    if args.as_sent:
        if args.seam != "worker":
            raise SystemExit("--as-sent is a worker seam option")
        return _as_sent_command(args, doc, turn, sid)
    if args.round is not None or args.reasoning_effort or args.max_tokens or args.date:
        raise SystemExit("--round, --reasoning-effort, --max-tokens and --date need "
                         "--as-sent")
    build ={"synthesis": synthesis_messages, "worker": worker_messages,
             "manager": manager_messages}[args.seam]
    kwargs = {"without_fix": args.without_fix, "rev": args.rev}
    if args.seam == "worker":
        kwargs["delegation"] = args.delegation
        kwargs["from_raw"] = args.from_raw
        if args.apply_lost:
            raise SystemExit("--apply-lost is a synthesis or manager seam option")
    else:
        kwargs["apply_lost"] = args.apply_lost
    messages = build(doc, turn, **kwargs)
    # P4.5: what the answer seam does with a lost step, in code.
    lost_for_answer, any_completed = [], True
    _dgs = (turn.get("audit") or {}).get("delegations", [])
    if args.seam == "synthesis":
        lost_for_answer = lost_from(turn, args.apply_lost)
        any_completed = any(not (d.get("lost") or d.get("halted") or d.get("error")
                                 or (args.apply_lost and is_lost_shaped(d)))
                            for d in _dgs if d.get("step") is not None)
    elif args.seam == "manager":
        mgr = [d for d in _dgs if d.get("step") is None]
        is_lost = [bool(d.get("lost") or (args.apply_lost and is_lost_shaped(d)))
                   for d in mgr]
        done = [not is_lost[i] and not d.get("halted") and not d.get("error")
                for i, d in enumerate(mgr)]
        lost_for_answer = [{"reason": "empty_completion"}
                           for i in range(len(mgr)) if is_lost[i] and not any(done[i + 1:])]
        any_completed = any(done)

    chars = sum(len(m.get("content") or "") for m in messages)
    print(f"seam={args.seam}  session={sid} turn={args.turn}  "
          f"{'WITHOUT fix (' + args.rev + ')' if args.without_fix else 'current code'}")
    print(f"  payload: {len(messages)} message(s), {chars:,} chars")
    if args.seam in ("synthesis", "manager"):
        labelled = sum(1 for m in messages
                       if "[Research Incomplete — answer lost]" in (m.get("content") or ""))
        print(f"  lost-report labels in the payload: {labelled}"
              f"{'  (--apply-lost)' if args.apply_lost else '  (as recorded)'}; "
              f"lawyer notice at the answer seam: "
              f"{'yes' if lost_for_answer else 'no'}")
    if args.seam == "manager":
        reports = [m for m in messages if m.get("role") == "tool"]
        print(f"  delegations: {len(reports)}")
        for i, m in enumerate(reports, 1):
            grade = _grade(sid, strip_scope_blocks(m.get("content") or "")[0])
            if grade:
                print(f"  report {i} depth: {grade}")
    elif args.seam == "synthesis":
        print(f"  research type: {_cfg_for(doc, turn)['_research_mode']}")
        print(f"  pinpoint block: "
              f"{'present' if 'PINPOINTS TO KEEP' in messages[1]['content'] else 'absent'}"
              + (f" ({args.rev} {'has' if rev_has_pinpoint_block(args.rev) else 'predates'}"
                 " P3.1's block)" if args.without_fix else ""))
    else:
        tool_msgs = [m for m in messages if m.get("role") == "tool"]
        with_outline = sum(1 for m in tool_msgs if "[SECTION OUTLINE" in (m.get("content") or ""))
        print(f"  results: {len(tool_msgs)}, with a subsection outline: {with_outline}"
              f"{'  (rebuilt from raw)' if args.from_raw else '  (as recorded)'}")
    if args.dry_run:
        return 0

    cfg = asyncio.run(_provider_cfg(_cfg_for(doc, turn)))
    tools = None
    if args.seam == "manager" and not args.no_tools:
        from src.agent.tools import get_manager_tools
        tools = get_manager_tools("")
    total = 0.0
    for rep in range(1, args.reps + 1):
        content, cost, model = asyncio.run(run_seam(messages, cfg, tools))
        total += cost
        clean, _ = strip_scope_blocks(content)
        if args.seam in ("synthesis", "manager"):
            clean, _ = apply_lost_disclosure(clean, lost_for_answer, any_completed)
        if args.seam == "manager":
            # What the product does to the Manager's text before the lawyer sees
            # it, in the order `process_user_request` does it.
            clean, _s = extract_suggestions(clean)
            if not args.without_fix:
                # The answer seam the product runs next (P3.13), on the
                # reports exactly as the Manager was handed them.
                handed = [(m.get("content") or "")[len(agent_core.RESEARCH_RESULT_PREFIX):]
                          for m in messages if m.get("role") == "tool"]
                clean, restored = restore_dropped_siblings(clean, handed)
                if restored:
                    print(f"      restored {restored} dropped sibling(s)")
        print(f"  rep{rep}: ${cost:.4f}  {len(clean):,} chars  model={model}")
        if args.seam == "worker":
            print(f"      scripted negatives (P4.6): {_scripted_line(clean)}")
        grade = _grade(sid, clean)
        if grade:
            print(f"      depth: {grade}")
        if args.out:
            d = Path(args.out)
            d.mkdir(parents=True, exist_ok=True)
            suffix = ("_nofix" if args.without_fix else "") + (
                "_lost" if args.apply_lost else "")
            (d / f"{sid}_t{args.turn}_{args.seam}{suffix}_rep{rep}.md").write_text(
                clean, encoding="utf-8")
        if args.print:
            print(clean)
    print(f"  total ${total:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
