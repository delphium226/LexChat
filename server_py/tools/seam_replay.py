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
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import subprocess
import sys
from collections import Counter
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
from src.utils.research_halt import halt_writeup_instruction  # noqa: E402
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


def step_findings_from(turn: dict) -> list:
    """The Deep Research step findings, as `run_deep_research` assembled them.

    The stored report is what the step handed the synthesis, scope block and
    all, so it is used verbatim. `plan` gives each step its title and detail.
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
            "content": dg.get("report") or "",
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
                       rev: str = PRE_P31_REV) -> list:
    """The Deep Research synthesis seam, via the product's own builder.

    `--without-fix` rebuilds it as the code at `rev` did: that revision's
    prompt for the turn's research type, and the pinpoint block only if that
    revision's builder added one. Nothing else in the payload changes."""
    findings = step_findings_from(turn)
    if not any(f["content"] for f in findings):
        raise SystemExit("this turn has no Deep Research step findings "
                         "(is it a `plan` turn?)")
    messages = agent_core.build_synthesis_messages(
        turn.get("question") or "", turn.get("plan") or {}, findings,
        halts_from(turn), len(findings),
    )
    if without_fix:
        research_mode = _cfg_for(doc, turn)["_research_mode"]
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


def manager_messages(doc: dict, turn: dict, without_fix: bool = False,
                     rev: str = PRE_P31_REV) -> list:
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
    the bare report.
    """
    from src.prompts import get_manager_system_prompt
    from src.utils.mode_change import apply_mode_change_marker

    dgs = [dg for dg in (turn.get("audit") or {}).get("delegations", [])
           if dg.get("step") is None]
    if not dgs:
        raise SystemExit("this turn has no delegation to compose from")
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
    messages = [{"role": "system", "content": system}, *history]
    messages, _change = apply_mode_change_marker(messages, cfg)
    for i, dg in enumerate(dgs, 1):
        cid = f"call_{i:02d}"
        messages.append({"role": "assistant", "content": "", "tool_calls": [{
            "id": cid, "type": "function", "function": {
                "name": "delegate_research",
                "arguments": json.dumps({"query": dg.get("brief") or ""})}}]})
        report = dg.get("report") or ""
        # The product's own builder (P3.13's sibling links included); the
        # pre-fix result is the bare report under the same prefix.
        messages.append({"role": "tool", "tool_call_id": cid,
                         "name": "delegate_research",
                         "content": f"[Research Agent Result]\n{report}" if without_fix
                         else agent_core.worker_result_for_manager(report, cfg)})
    # Strip the client-side stamps: they are not provider fields.
    return [{k: v for k, v in m.items() if k not in ("research_mode", "chat_mode")}
            for m in messages]


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
    p.add_argument("--print", action="store_true", help="print the answer")
    p.add_argument("--no-tools", action="store_true",
                   help="manager seam only: make the call tool-free. By default "
                        "the Manager is offered its tools, as the live call is "
                        "(a call it makes is refused), because tool-free it "
                        "delivered a payload the live Manager flattened (P3.13)")
    p.add_argument("--first-round", action="store_true",
                   help="worker seam only (P4.6): the Worker's first round - its "
                        "prompt and the brief, with its real tools offered, "
                        "stopped at the first call. Prints the calls it chose, or "
                        "the report it wrote without searching")
    p.add_argument("--without-lookup", action="store_true",
                   help="--first-round only (P3.7): leave out the instrument-lookup "
                        "block code appends to the brief, and the lookup tool")
    p.add_argument("--dry-run", action="store_true",
                   help="build the payload and print its shape; no model call")
    p.add_argument("--out", default=None, help="write each answer to this directory")
    args = p.parse_args(list(argv) if argv is not None else None)

    run_path = Path(args.run)
    doc, turn = load_turn(run_path, args.turn)
    sid = str(doc.get("session_id"))
    if args.first_round:
        if args.seam != "worker":
            raise SystemExit("--first-round is a worker seam option")
        return _first_round_command(args, doc, turn, sid)
    build = {"synthesis": synthesis_messages, "worker": worker_messages,
             "manager": manager_messages}[args.seam]
    kwargs = {"without_fix": args.without_fix, "rev": args.rev}
    if args.seam == "worker":
        kwargs["delegation"] = args.delegation
        kwargs["from_raw"] = args.from_raw
    messages = build(doc, turn, **kwargs)

    chars = sum(len(m.get("content") or "") for m in messages)
    print(f"seam={args.seam}  session={sid} turn={args.turn}  "
          f"{'WITHOUT fix (' + args.rev + ')' if args.without_fix else 'current code'}")
    print(f"  payload: {len(messages)} message(s), {chars:,} chars")
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
            suffix = "_nofix" if args.without_fix else ""
            (d / f"{sid}_t{args.turn}_{args.seam}{suffix}_rep{rep}.md").write_text(
                clean, encoding="utf-8")
        if args.print:
            print(clean)
    print(f"  total ${total:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
