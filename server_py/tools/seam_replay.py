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
commit before P3.1's product code): the synthesis prompt from that revision,
and no pinpoint block. That is how this tool was validated — see
`tests/test_seam_replay.py` and SESSION_LOG Session 17.

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
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tools.replay_report as rr  # noqa: E402
from src.agent import agent_core, agent_shared  # noqa: E402
from src.agent.openrouter_client import chat_loop  # noqa: E402
from src.agent.provider_factory import set_request_provider_config  # noqa: E402
from src.prompts import get_worker_system_prompt  # noqa: E402
from src.utils.citation_links import provision_url_block  # noqa: E402
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


def synthesis_messages(doc: dict, turn: dict, without_fix: bool = False,
                       rev: str = PRE_P31_REV) -> list:
    """The Deep Research synthesis seam, via the product's own builder."""
    findings = step_findings_from(turn)
    if not any(f["content"] for f in findings):
        raise SystemExit("this turn has no Deep Research step findings "
                         "(is it a `plan` turn?)")
    messages = agent_core.build_synthesis_messages(
        turn.get("question") or "", turn.get("plan") or {}, findings,
        halts_from(turn), len(findings),
    )
    if without_fix:
        messages[0]["content"] = _prompt_constant_at(
            rev, "DEEP_RESEARCH_SYNTHESIS_PROMPT")
        body = messages[1]["content"]
        start = body.find("\n\n[PINPOINTS TO KEEP")
        if start >= 0:
            end = body.find("[/PINPOINTS TO KEEP]", start)
            body = body[:start] + (body[end + len("[/PINPOINTS TO KEEP]"):]
                                   if end >= 0 else "")
        messages[1]["content"] = body
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
        name = ("WORKER_SYSTEM_PROMPT_CONVERSATIONAL"
                if cfg.get("_chat_mode") == "conversational" else "WORKER_SYSTEM_PROMPT")
        system = _prompt_constant_at(rev, name)
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
        "_research_mode": f.get("research_mode") or "legislation_only",
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
    p.add_argument("--dry-run", action="store_true",
                   help="build the payload and print its shape; no model call")
    p.add_argument("--out", default=None, help="write each answer to this directory")
    args = p.parse_args(list(argv) if argv is not None else None)

    run_path = Path(args.run)
    doc, turn = load_turn(run_path, args.turn)
    sid = str(doc.get("session_id"))
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
        print(f"  pinpoint block: "
              f"{'present' if 'PINPOINTS TO KEEP' in messages[1]['content'] else 'absent'}")
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
        print(f"  rep{rep}: ${cost:.4f}  {len(clean):,} chars  model={model}")
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
