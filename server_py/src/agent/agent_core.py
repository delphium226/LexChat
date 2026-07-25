"""Provider-agnostic agent core: Worker and Manager orchestration.

Both provider clients (ollama_client, openrouter_client) previously carried
byte-identical copies of run_worker_agent and process_user_request. The logic
lives here once, parameterised by the provider's chat_loop and summarise-chunk
functions (the only genuinely provider-specific parts — wire format, streaming
parse, and per-provider options).
"""

import asyncio
import logging
import re
import uuid
from typing import Callable, Optional

from ..prompts import (
    DEEP_RESEARCH_SYNTHESIS_PROMPT,
    get_manager_system_prompt,
    get_planner_system_prompt,
    get_worker_system_prompt,
)
from .agent_shared import run_worker_tool
from .federation_client import (
    build_peer_descriptions,
    consult_peer,
    load_peer_registry,
)
from .learning import format_learning_context, get_relevant_examples
from .summarisation import call_chunk
from .tools import get_manager_tools, get_planner_tools, get_worker_tools

logger = logging.getLogger("agent")


def _get_cfg() -> dict:
    """Return the current request's provider config (set by provider_factory)."""
    from .provider_factory import get_request_provider_config
    return get_request_provider_config()


# -----------------------------------------------------------------------
# Worker report structure validation (A4)
# -----------------------------------------------------------------------
# The required Markdown section labels per research mode, mirroring the
# OUTPUT STRUCTURE block in each worker system prompt (prompts.py). Used both
# to grade a returned report and to tell the model the target shape on a
# reformat retry. Conversational chat mode is deliberately unstructured and is
# never validated.
_REPORT_SECTIONS = {
    "legislation_only": [
        "Summary Answer (BLUF)", "Detailed Analysis", "Jurisdiction & Status", "References",
    ],
    "case_law_only": [
        "Summary Answer (BLUF)", "Key Cases", "Analysis", "Jurisdiction & Currency", "References",
    ],
    "legislation_and_case_law": [
        "Summary Answer (BLUF)", "Statutory Framework", "Key Cases", "Jurisdiction & Status", "References",
    ],
    "parliamentary_records": [
        "Summary (BLUF)", "Key Speeches / Evidence", "Source & Date", "References",
    ],
    "westminster_records": [
        "Summary (BLUF)", "Key Contributions", "House & Date", "References",
    ],
}

# A section header line: an ATX header (`## Foo`) or a bold label at the start of
# a line, optionally list-numbered (`1. **Foo:**` / `- **Foo**`). Captures the
# label text so we can look for the mandatory References section.
_HEADER_RE = re.compile(
    r"^\s*(?:#{1,6}\s+(?P<atx>.+?)\s*$|(?:\d+\.\s*|[-*]\s*)?\*\*(?P<bold>[^*]+?)\*\*)",
    re.MULTILINE,
)
_MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\([^)]+\)")


def _extract_section_headers(content: str) -> list[str]:
    """Return the section-header labels found in a Markdown report (lower-cased, stripped)."""
    headers = []
    for m in _HEADER_RE.finditer(content):
        label = (m.group("atx") or m.group("bold") or "").strip().rstrip(":").strip()
        if label:
            headers.append(label.lower())
    return headers


def _report_needs_reformat(content: str, has_sources: bool) -> bool:
    """Return True if a worker report is missing the structure a graded answer needs.

    Targets the observed regression where a worker loses its section headers and/or
    References section despite the prompt rule. High-precision by design — it fires
    only on genuinely malformed output so the one reformat retry is not wasted on a
    well-formed report:
      - fewer than two recognisable section headers (a flat prose blob), OR
      - no References section, OR
      - sources were retrieved but the report cites no link.
    A report with no retrieved sources is not required to carry a link.
    """
    if not content or len(content.strip()) < 40:
        return False  # nothing meaningful to reformat
    headers = _extract_section_headers(content)
    if len(headers) < 2:
        return True
    if not any("reference" in h for h in headers):
        return True
    if has_sources and not _MARKDOWN_LINK_RE.search(content):
        return True
    return False


async def _reformat_worker_report(
    chat_loop_fn: Callable,
    content: str,
    research_mode: str,
    model: str,
    cancel_event: Optional[asyncio.Event],
    num_ctx: int,
    timing_collector=None,
) -> str:
    """One no-tools LLM call that reorganises an existing report into the required
    structure. Adds/changes NO legal content — pure reformat. Fail-soft: any error
    returns the original content unchanged."""
    sections = _REPORT_SECTIONS.get(research_mode, _REPORT_SECTIONS["legislation_only"])
    section_list = "\n".join(f"{i}. **{s}:**" for i, s in enumerate(sections, 1))
    system = (
        "You are reformatting an existing UK legal research report into the required "
        "structure. Do NOT perform any new research. Do NOT add, remove, or alter any "
        "legal content, findings, citations, or URLs — only reorganise what is already "
        "present under the required Markdown section headers. Every source already cited "
        "in the report MUST appear under References with its existing link. If the report "
        "contains no sources, write 'None found' under References.\n\n"
        f"REQUIRED STRUCTURE (Markdown):\n{section_list}"
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": content},
    ]

    async def _no_tools(name: str, args: dict) -> str:  # pragma: no cover - never called
        return "No tools are available during reformatting."

    try:
        reformatted = await chat_loop_fn(
            messages, model, cancel_event, num_ctx,
            [], _no_tools, None,
            emit_tool_details=False,
            timing_collector=timing_collector,
        )
        new_content = (reformatted.get("content") or "").strip()
        return new_content or content
    except Exception as e:
        logger.warning(f"[Worker] Report reformat retry failed, keeping original: {e}")
        return content


# -----------------------------------------------------------------------
# Worker Agent (Legal Research Specialist)
# -----------------------------------------------------------------------

async def run_worker_agent(
    chat_loop_fn: Callable,
    summarise_chunk_fn: Callable,
    query: str,
    model: str,
    cancel_event: Optional[asyncio.Event],
    num_ctx: int,
    parent_on_chunk: Optional[Callable] = None,
    emit_tool_details: bool = False,
    timing_collector=None,
    tool_memo: Optional[dict] = None,
    memo_count_redundant: bool = False,
) -> dict:
    """Run the Worker agent with a fresh context for legal research."""
    logger.info(f"[Worker] Starting research on: {query}")

    cfg = _get_cfg()
    research_mode = cfg.get("_research_mode", "legislation_only")
    summarise_model = cfg.get("summarisation_model") or model

    messages = [
        {"role": "system", "content": get_worker_system_prompt(research_mode, cfg)},
        {"role": "user", "content": query},
    ]

    worker_tools = get_worker_tools(research_mode)
    source_accumulator: list = []
    # Limit parliamentary searches so the model proceeds to Phase 2 instead of looping.
    # Covers the SP search tools on the Holyrood bot and search_hansard on the
    # Westminster bot (see _PARLIAMENT_SEARCH_TOOLS in agent_shared).
    search_budget = (
        {"remaining": 3}
        if research_mode in ("parliamentary_records", "westminster_records")
        else None
    )

    async def worker_tool_executor(name: str, args: dict) -> str:
        return await run_worker_tool(
            name, args, query, summarise_chunk_fn, summarise_model,
            parent_on_chunk=parent_on_chunk,
            timing_collector=timing_collector,
            source_accumulator=source_accumulator,
            search_budget=search_budget,
            cancel_event=cancel_event,
            tool_memo=tool_memo,
            memo_count_redundant=memo_count_redundant,
        )

    result = await chat_loop_fn(
        messages, model, cancel_event, num_ctx,
        worker_tools, worker_tool_executor, None,  # on_chunk=None for worker to avoid mixing tokens
        emit_tool_details=emit_tool_details,
        timing_collector=timing_collector,
    )

    # A4: validate the report structure and, if malformed, issue ONE no-tools
    # reformat retry. Skipped in conversational chat mode (deliberately unstructured).
    # Runs before source filtering so the filter sees the reformatted content.
    if cfg.get("_chat_mode") != "conversational":
        content = result.get("content", "") or ""
        if _report_needs_reformat(content, has_sources=bool(source_accumulator)):
            logger.info("[Worker] Report failed structure check — issuing one reformat retry")
            result["content"] = await _reformat_worker_report(
                chat_loop_fn, content, research_mode, model,
                cancel_event, num_ctx, timing_collector=timing_collector,
            )

    if source_accumulator:
        content = result.get("content", "") or ""
        kept = [src for src in source_accumulator if _source_is_used(src, content)]
        # If filtering removed everything (e.g. the model paraphrased without
        # citing URLs), fall back to the full list rather than showing no sources.
        fallback = not kept
        if fallback:
            kept = source_accumulator
        if timing_collector:
            timing_collector.record_source_stats(
                extracted=len(source_accumulator), kept=len(kept), fallback=fallback
            )
        result["sources"] = [
            {**{k: v for k, v in src.items() if not k.startswith("_")}, "n": i + 1}
            for i, src in enumerate(kept)
        ]

    return result


def _is_duplicate_source(src: dict, existing: list) -> bool:
    """Return True if src already appears in the accumulated source list.

    Matches on url when present (most reliable), else on cite/title, so the
    same case or Act reported by two separate delegate_research calls is not
    listed twice in the References panel.
    """
    url = src.get("url")
    cite = src.get("cite")
    title = src.get("title")
    for s in existing:
        if url and s.get("url") == url:
            return True
        if not url and cite and s.get("cite") == cite:
            return True
        if not url and not cite and title and s.get("title") == title:
            return True
    return False


def _source_is_used(src: dict, content: str) -> bool:
    """Return True if a source was actually retrieved or cited in the answer.

    Phase 1 search hits that were never followed up in Phase 2 and never
    referenced in the final answer are noise — a References panel citing a
    repealed Act the answer never discussed undermines trust.  We keep a source
    when either:
      - it carries an excerpt (Phase 2 section/text/judgment retrieval ran), or
      - one of its identifying tokens (legislation_id, url, neutral citation)
        appears in the answer text.
    """
    if src.get("excerpt"):
        return True
    tokens = [
        src.get("_lid"),
        src.get("url"),
        src.get("cite"),
        src.get("sub"),
    ]
    for tok in tokens:
        if tok and len(str(tok)) >= 6 and str(tok) in content:
            return True
    return False


# -----------------------------------------------------------------------
# Deep Research — Phase A: Planner Agent
# -----------------------------------------------------------------------

_MAX_PLAN_STEPS = 8


def _normalise_plan_args(args: dict):
    """Validate and normalise a submit_research_plan payload.

    Returns (plan_dict, None) on success or (None, error_message) when the
    payload is unusable — the error message goes back to the model as the tool
    result so it can retry within the same ReAct loop.
    """
    import json as _json

    steps = args.get("steps")
    if isinstance(steps, str):
        # Weaker models sometimes double-encode the array as a JSON string.
        try:
            steps = _json.loads(steps)
        except (ValueError, TypeError):
            steps = None
    if not isinstance(steps, list):
        return None, "Error: `steps` must be an array of {title, detail} objects. Call submit_research_plan again."

    clean_steps = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        title = str(step.get("title") or "").strip()
        detail = str(step.get("detail") or "").strip()
        if not title:
            continue
        clean_steps.append({"title": title, "detail": detail})

    if not clean_steps:
        return None, "Error: the plan contained no usable steps. Each step needs a non-empty `title` and a `detail`. Call submit_research_plan again."
    clean_steps = clean_steps[:_MAX_PLAN_STEPS]

    plan = {
        "scope_note": str(args.get("scope_note") or "").strip(),
        "steps": [{"id": i + 1, **s} for i, s in enumerate(clean_steps)],
    }
    return plan, None


async def draft_research_plan(
    chat_loop_fn: Callable,
    messages: list,
    model: str,
    cancel_event: Optional[asyncio.Event],
    num_ctx: int,
    timing_collector=None,
) -> dict:
    """Deep Research Phase A: draft a structured research plan (no research tools).

    Returns {"plan": {"scope_note": str, "steps": [{"id","title","detail"}]}}
    or {"needs_clarification": True, "question": str}
    or {"error": str} when the model failed to call either planner tool.
    """
    cfg = _get_cfg()
    research_mode = cfg.get("_research_mode", "legislation_only")
    logger.info(f"[Planner] Drafting research plan (mode={research_mode})")

    system_message = {"role": "system", "content": get_planner_system_prompt(research_mode, cfg)}
    final_messages = list(messages)
    if final_messages and final_messages[0].get("role") == "system":
        final_messages[0] = system_message
    else:
        final_messages = [system_message, *final_messages]

    captured: dict = {}

    async def planner_tool_executor(name: str, args: dict) -> str:
        if name == "submit_research_plan":
            plan, err = _normalise_plan_args(args or {})
            if err:
                return err
            captured["plan"] = plan
            return "Plan received. Reply with the single word: Done."
        if name == "request_clarification":
            question = str((args or {}).get("question") or "").strip()
            if not question:
                return "Error: `question` must be a non-empty string. Call request_clarification again."
            captured["question"] = question
            return "Clarification request recorded. Reply with the single word: Done."
        return f"Error: Unknown planner tool {name}"

    result = await chat_loop_fn(
        final_messages, model, cancel_event, num_ctx,
        get_planner_tools(), planner_tool_executor, None,
        timing_collector=timing_collector,
    )

    if not captured:
        # One corrective retry: the model answered in prose instead of calling a tool.
        logger.warning("[Planner] No planner tool called — retrying with explicit instruction")
        retry_messages = [
            *final_messages,
            result if isinstance(result, dict) and result.get("content") else {"role": "assistant", "content": ""},
            {
                "role": "user",
                "content": (
                    "You did not call a tool. You MUST call either submit_research_plan "
                    "(with scope_note and steps) or request_clarification (with one question). "
                    "Do not answer in prose."
                ),
            },
        ]
        await chat_loop_fn(
            retry_messages, model, cancel_event, num_ctx,
            get_planner_tools(), planner_tool_executor, None,
            timing_collector=timing_collector,
        )

    if "plan" in captured:
        logger.info(f"[Planner] Plan drafted with {len(captured['plan']['steps'])} steps")
        return {"plan": captured["plan"]}
    if "question" in captured:
        logger.info("[Planner] Clarification requested")
        return {"needs_clarification": True, "question": captured["question"]}
    logger.error("[Planner] Model failed to produce a plan or clarification")
    return {"error": "The planner did not produce a research plan. Please try rephrasing your question."}


# -----------------------------------------------------------------------
# Manager Agent (Main Chat Interface)
# -----------------------------------------------------------------------

async def process_user_request(
    chat_loop_fn: Callable,
    run_worker_agent_fn: Callable,
    messages: list,
    model: str,
    on_chunk: Optional[Callable],
    cancel_event: Optional[asyncio.Event],
    num_ctx: int,
    db_session=None,
    emit_tool_details: bool = False,
    timing_collector=None,
    depth: int = 0,
) -> dict:
    """Main entry point: Manager agent with learning injection."""
    _cfg = _get_cfg()
    research_mode = _cfg.get("_research_mode", "legislation_only")
    system_content = get_manager_system_prompt(research_mode, _cfg)

    doc_context = _cfg.get("_doc_context", "")
    if doc_context:
        system_content += f"\n\n{doc_context}"

    matter_context = _cfg.get("_matter_context", "")
    if matter_context:
        system_content += f"\n\n{matter_context}"

    # Learning mechanism injection
    if db_session:
        try:
            last_msg = messages[-1] if messages else None
            if last_msg and last_msg.get("role") == "user":
                learning_data = await get_relevant_examples(
                    last_msg["content"], db_session, timing_collector=timing_collector
                )
                context_injection = format_learning_context(learning_data)
                if context_injection:
                    logger.info("[Learning] Injecting feedback context into System Prompt.")
                    system_content += f"\n\n{context_injection}"
        except Exception as e:
            logger.error(f"[Learning] Failed to inject context: {e}", exc_info=True)

    system_message = {"role": "system", "content": system_content}

    final_messages = list(messages)
    if final_messages and final_messages[0].get("role") == "system":
        final_messages[0] = system_message
    else:
        final_messages = [system_message, *final_messages]

    # Load peer registry and build dynamic tool list
    peers = []
    if db_session:
        try:
            peers = await load_peer_registry(db_session)
        except Exception as e:
            logger.warning(f"[Federation] Could not load peer registry: {e}", exc_info=True)
    peer_descriptions = build_peer_descriptions(peers)
    manager_tools = get_manager_tools(peer_descriptions)

    accumulated_sources: list = []

    # Per-request tool-result memo (D8 Phase 4) — same mechanism as Deep
    # Research (see run_deep_research): exact (tool_name, canonical args)
    # repeats are served from this dict instead of re-fetching + re-summarising.
    # Created ONCE per request, outside the executor, so multiple
    # delegate_research calls share it. Unlike DR, standard-mode memo hits are
    # also counted as redundant tool calls (memo_count_redundant=True) — the
    # Efficiency tab's "model re-fetched the same Act" signal must survive
    # even though the repeat now costs nothing.
    tool_memo: Optional[dict] = (
        {} if _cfg.get("_tool_memo_enabled", True) else None
    )

    async def manager_tool_executor(name: str, args: dict) -> str:
        if name == "delegate_research":
            if timing_collector:
                timing_collector.record_delegation()
            research_id = uuid.uuid4().hex[:8]
            if on_chunk:
                await call_chunk(on_chunk, {"type": "tool_start", "tool": "Research Agent", "id": research_id})

            result = await run_worker_agent_fn(
                args["query"], model, cancel_event, num_ctx, on_chunk,
                emit_tool_details=emit_tool_details,
                timing_collector=timing_collector,
                tool_memo=tool_memo,
                memo_count_redundant=True,
            )

            if on_chunk:
                await call_chunk(on_chunk, {"type": "tool_end", "tool": "Research Agent", "id": research_id, "result": "Research Complete"})

            # Dedup across multiple delegate_research calls — the manager can
            # delegate more than once, and each worker independently reports the
            # same case/Act, producing duplicate entries in the References panel.
            for src in result.get("sources", []):
                if not _is_duplicate_source(src, accumulated_sources):
                    accumulated_sources.append(src)
            return f"[Research Agent Result]\n{result['content']}"

        if name == "consult_peer":
            if timing_collector:
                timing_collector.record_peer_consult()
            peer_id = args.get("peer_id", "")
            question = args.get("question", "")
            peer = next((p for p in peers if p.peer_id == peer_id), None)
            if not peer:
                return f"Error: Unknown peer '{peer_id}'"
            try:
                consult_id = uuid.uuid4().hex[:8]
                consult_label = f'Querying {peer.name} - "{question}"'
                if on_chunk:
                    await call_chunk(on_chunk, {"type": "tool_start", "tool": consult_label, "id": consult_id})
                answer = await consult_peer(peer, question, depth=depth + 1)
                if on_chunk:
                    await call_chunk(on_chunk, {"type": "tool_end", "tool": consult_label, "id": consult_id, "result": "Peer consult complete"})
                return f"[Peer Bot: {peer.name}]\n{answer}"
            except Exception as e:
                return f"Error consulting peer '{peer_id}': {e}"

        return f"Error: Unknown manager tool {name}"

    final = await chat_loop_fn(
        final_messages, model, cancel_event, num_ctx,
        manager_tools, manager_tool_executor, on_chunk,
        emit_tool_details=emit_tool_details,
        timing_collector=timing_collector,
    )

    if accumulated_sources:
        final["sources"] = [
            {**{k: v for k, v in s.items() if k != "n"}, "n": i + 1}
            for i, s in enumerate(accumulated_sources)
        ]

    return final


# -----------------------------------------------------------------------
# Deep Research — Phase B: code-orchestrated executor
# -----------------------------------------------------------------------

def _last_user_content(messages: list) -> str:
    for msg in reversed(messages or []):
        if msg.get("role") == "user":
            return str(msg.get("content") or "")
    return ""


def _build_step_brief(step: dict, approved_plan: dict, user_query: str) -> str:
    """Build a self-contained worker brief for one approved plan step.

    The Worker has no access to the conversation or the rest of the plan, so the
    brief carries the original question and the plan's scope note as context.
    Identifiers in the step text are passed through verbatim (NO SPECULATION —
    the planner was instructed to copy them exactly as the user gave them).
    """
    parts = [f"RESEARCH TASK: {step['title']}"]
    detail = step.get("detail") or ""
    if detail:
        parts.append(detail)
    scope_note = approved_plan.get("scope_note") or ""
    if scope_note:
        parts.append(f"SCOPE: {scope_note}")
    if user_query:
        parts.append(
            "CONTEXT: This task is one step of a wider research plan answering the "
            f"user's question: \"{user_query}\". Research ONLY this step's task — "
            "the other aspects are covered by separate steps."
        )
    return "\n\n".join(parts)


async def run_deep_research(
    chat_loop_fn: Callable,
    run_worker_agent_fn: Callable,
    approved_plan: dict,
    messages: list,
    model: str,
    on_chunk: Optional[Callable],
    cancel_event: Optional[asyncio.Event],
    num_ctx: int,
    db_session=None,
    emit_tool_details: bool = False,
    timing_collector=None,
) -> dict:
    """Deep Research Phase B: execute an approved plan, code-orchestrated.

    Loops over the approved steps in Python — one run_worker_agent call per step
    (deterministic 1:1 mapping between approved steps and work done, unlike
    prompt-driven Manager delegation) — then composes an integrated report via a
    single tool-free synthesis call. Sources are deduped across steps.
    """
    steps = list(approved_plan.get("steps") or [])
    user_query = _last_user_content(messages)
    logger.info(f"[DeepResearch] Executing approved plan: {len(steps)} steps")

    step_findings: list = []
    accumulated_sources: list = []
    # Per-request tool-result memo: plan steps run as isolated workers, so two
    # steps that retrieve the same Act would each pay fetch + summarise. Exact
    # (tool_name, canonical args) repeats are served from this dict instead.
    # Dies with the request — no TTL/invalidation. See run_worker_tool.
    # Admin kill-switch (Developer tab → Feature flags): None = memo disabled,
    # which run_worker_tool already treats as "no memo". Absent key = enabled.
    tool_memo: Optional[dict] = (
        {} if _get_cfg().get("_tool_memo_enabled", True) else None
    )

    for i, step in enumerate(steps, 1):
        if cancel_event and cancel_event.is_set():
            raise asyncio.CancelledError("Aborted")

        title = step.get("title") or f"Step {i}"
        label = f"Research Agent — Step {i}: {title}"
        step_id = uuid.uuid4().hex[:8]
        if on_chunk:
            await call_chunk(on_chunk, {"type": "tool_start", "tool": label, "id": step_id})

        if timing_collector:
            timing_collector.record_delegation()

        brief = _build_step_brief(step, approved_plan, user_query)
        logger.info(f"[DeepResearch] Step {i}/{len(steps)}: {title}")
        result = await run_worker_agent_fn(
            brief, model, cancel_event, num_ctx, on_chunk,
            emit_tool_details=emit_tool_details,
            timing_collector=timing_collector,
            tool_memo=tool_memo,
        )

        if on_chunk:
            await call_chunk(on_chunk, {"type": "tool_end", "tool": label, "id": step_id, "result": "Step complete"})

        step_findings.append({
            "title": title,
            "detail": step.get("detail") or "",
            "content": result.get("content", "") or "",
        })
        for src in result.get("sources", []):
            if not _is_duplicate_source(src, accumulated_sources):
                accumulated_sources.append(src)

    if cancel_event and cancel_event.is_set():
        raise asyncio.CancelledError("Aborted")

    # Synthesis: one tool-free call composing the integrated report.
    findings_blocks = [
        f"### Step {i}: {f['title']}\n{f['detail']}\n\nFINDINGS:\n{f['content']}"
        for i, f in enumerate(step_findings, 1)
    ]
    scope_note = approved_plan.get("scope_note") or ""
    synthesis_user = (
        f"USER'S ORIGINAL QUESTION:\n{user_query}\n\n"
        f"APPROVED RESEARCH PLAN SCOPE:\n{scope_note}\n\n"
        f"STEP FINDINGS:\n\n" + "\n\n---\n\n".join(findings_blocks)
    )
    synthesis_messages = [
        {"role": "system", "content": DEEP_RESEARCH_SYNTHESIS_PROMPT},
        {"role": "user", "content": synthesis_user},
    ]

    async def _no_tools_executor(name: str, args: dict) -> str:
        return f"Error: Unknown tool {name}"

    logger.info("[DeepResearch] Synthesising final report")
    final = await chat_loop_fn(
        synthesis_messages, model, cancel_event, num_ctx,
        [], _no_tools_executor, on_chunk,
        emit_tool_details=emit_tool_details,
        timing_collector=timing_collector,
    )

    if accumulated_sources:
        final["sources"] = [
            {**{k: v for k, v in s.items() if k != "n"}, "n": i + 1}
            for i, s in enumerate(accumulated_sources)
        ]

    return final
