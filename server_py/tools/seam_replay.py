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

`--without-fix` rebuilds the seam as it was at a given commit (default the
commit before P3.1's product code): the synthesis prompt from that revision,
and no pinpoint block. That is how this tool was validated — see
`tests/test_seam_replay.py` and SESSION_LOG Session 17.
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
from src.agent import agent_core  # noqa: E402
from src.agent.openrouter_client import chat_loop  # noqa: E402
from src.agent.provider_factory import set_request_provider_config  # noqa: E402
from src.prompts import get_worker_system_prompt  # noqa: E402
from src.utils.research_halt import halt_writeup_instruction  # noqa: E402
from src.utils.search_scope import strip_scope_blocks  # noqa: E402
from src.utils.stopwatch import TimingCollector  # noqa: E402

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


def worker_messages(doc: dict, turn: dict, delegation: int = 1,
                    without_fix: bool = False, rev: str = PRE_P31_REV) -> list:
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
        results.append({"role": "tool", "tool_call_id": cid,
                        "name": t.get("name") or "",
                        "content": t.get("final_result") or ""})
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": dg.get("brief") or turn.get("question") or ""},
        {"role": "assistant", "content": "", "tool_calls": calls},
        *results,
        {"role": "user", "content": closing},
    ]


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


async def run_seam(messages: list, cfg: dict) -> tuple:
    """One tool-free model call. Returns (content, cost, model)."""
    set_request_provider_config(cfg)
    tc = TimingCollector("seam")
    out = await chat_loop(messages, cfg["model"], None, 0, [], _no_tools,
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
    p.add_argument("seam", choices=["synthesis", "worker"])
    p.add_argument("--run", required=True, help="a replay run file")
    p.add_argument("--turn", type=int, default=1)
    p.add_argument("--delegation", type=int, default=1, help="worker seam only")
    p.add_argument("--reps", type=int, default=1)
    p.add_argument("--without-fix", action="store_true",
                   help=f"rebuild the seam as at {PRE_P31_REV} (the A/B side)")
    p.add_argument("--rev", default=PRE_P31_REV)
    p.add_argument("--print", action="store_true", help="print the answer")
    p.add_argument("--dry-run", action="store_true",
                   help="build the payload and print its shape; no model call")
    p.add_argument("--out", default=None, help="write each answer to this directory")
    args = p.parse_args(list(argv) if argv is not None else None)

    run_path = Path(args.run)
    doc, turn = load_turn(run_path, args.turn)
    sid = str(doc.get("session_id"))
    build = synthesis_messages if args.seam == "synthesis" else worker_messages
    kwargs = {"without_fix": args.without_fix, "rev": args.rev}
    if args.seam == "worker":
        kwargs["delegation"] = args.delegation
    messages = build(doc, turn, **kwargs)

    chars = sum(len(m.get("content") or "") for m in messages)
    print(f"seam={args.seam}  session={sid} turn={args.turn}  "
          f"{'WITHOUT fix (' + args.rev + ')' if args.without_fix else 'current code'}")
    print(f"  payload: {len(messages)} message(s), {chars:,} chars")
    if args.seam == "synthesis":
        print(f"  pinpoint block: "
              f"{'present' if 'PINPOINTS TO KEEP' in messages[1]['content'] else 'absent'}")
    if args.dry_run:
        return 0

    cfg = asyncio.run(_provider_cfg(_cfg_for(doc, turn)))
    total = 0.0
    for rep in range(1, args.reps + 1):
        content, cost, model = asyncio.run(run_seam(messages, cfg))
        total += cost
        clean, _ = strip_scope_blocks(content)
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
