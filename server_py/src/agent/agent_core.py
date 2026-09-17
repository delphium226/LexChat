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
from ..utils.audit_trace import get_audit_collector
from ..utils.citation_links import enforce_provision_links
from ..utils.empty_completion import (
    LOST_ANSWER_NOTICE,
    fallback_from_reports,
    is_empty_completion,
)
from ..utils.research_halt import apply_halt_disclosure, halt_worker_report
from ..utils.search_scope import (
    answer_scope_footer,
    carried_scope_footer,
    case_law_scope_footer,
    strip_answer_footer,
    incomplete_steps_note,
    strip_scope_blocks,
    worker_scope_block,
)
from ..utils.suggestions import diagnose_suggestions, extract_suggestions
from .agent_shared import describe_agent_error, run_worker_tool
from .federation_client import (
    build_peer_descriptions,
    consult_peer,
    load_peer_registry,
)
from .learning import format_learning_context, get_relevant_examples
from .summarisation import WORKER_CONTEXT_BUDGET_CHARS, call_chunk
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
    retrieved_urls: Optional[set] = None,
) -> dict:
    """Run the Worker agent with a fresh context for legal research.

    `retrieved_urls` is the per-REQUEST set of legislation.gov.uk URLs any tool
    has returned (P1.6/B14). It is passed in rather than created here because a
    Manager delegating twice, or a Deep Research plan of six steps, is still one
    answer: a provision retrieved in step 2 is legitimately cited in step 5. A
    caller that passes nothing gets a run-local set, so a standalone worker is
    still enforced against its own retrievals.
    """
    logger.info(f"[Worker] Starting research on: {query}")

    cfg = _get_cfg()
    research_mode = cfg.get("_research_mode", "legislation_only")
    summarise_model = cfg.get("summarisation_model") or model

    # Audit trace (evaluation harnesses only — None on /api/chat). One worker
    # run is one delegation, which is the right granularity for BOTH callers:
    # a Manager delegate_research call and a Deep Research plan step.
    _audit = get_audit_collector()
    _audit_delegation = _audit.start_delegation(query) if _audit else None

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
    # Bound on the SUM of tool output in this worker's context. The per-result
    # summarisation threshold scales with the model's context window and so caps
    # each result but not their total; without this, several individually-legal
    # retrievals stack into a prefill that trips the stream read timeout.
    # Fresh per run_worker_agent call, so each Deep Research step gets its own.
    context_budget = {"used": 0, "limit": WORKER_CONTEXT_BUDGET_CHARS}

    # See the docstring: request-scoped when the caller threads one, run-local
    # otherwise, never None — the enforcement below must not silently no-op.
    if retrieved_urls is None:
        retrieved_urls = set()

    # P2.2 (B5): what this step searched for, and under what limits. Run-scoped
    # rather than request-scoped (unlike `retrieved_urls`), because "what this
    # step searched for" is a statement about one step and is rendered onto that
    # step's report.
    search_log: list = []

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
            context_budget=context_budget,
            audit_delegation=_audit_delegation,
            retrieved_urls=retrieved_urls,
            search_log=search_log,
        )

    try:
        result = await chat_loop_fn(
            messages, model, cancel_event, num_ctx,
            worker_tools, worker_tool_executor, None,  # on_chunk=None for worker to avoid mixing tokens
            emit_tool_details=emit_tool_details,
            timing_collector=timing_collector,
        )
    except BaseException as e:
        # Close the audit delegation on the failure path too — a trace that
        # simply ends mid-delegation is indistinguishable from a hang.
        if _audit:
            _audit.end_delegation(_audit_delegation, error=describe_agent_error(e) or type(e).__name__)
        raise

    # A4: validate the report structure and, if malformed, issue ONE no-tools
    # reformat retry. Skipped in conversational chat mode (deliberately unstructured).
    # Runs before source filtering so the filter sees the reformatted content.
    #
    # P2.6 (B1): and skipped for a HALTED worker. A halt has no findings to
    # reformat, so the retry is pure cost — and worse, it is what laundered the
    # failure: in 6340 it spent an LLM call turning the halt marker into a
    # perfectly-structured empty report ("Jurisdiction & Status: Not applicable
    # (no research generated). References: None found."), which is what let the
    # halt read downstream as a finished piece of research. It also polluted the
    # measurement — `report_reformat_retries` and the Efficiency tab's
    # `reformat_rate` scored these as prompt-adherence failures when the model
    # never had a report to format.
    if result.get("halted"):
        logger.info("[Worker] Halted — skipping the A4 reformat retry (nothing to format)")
    elif cfg.get("_chat_mode") != "conversational":
        content = result.get("content", "") or ""
        if _report_needs_reformat(content, has_sources=bool(source_accumulator)):
            logger.info("[Worker] Report failed structure check — issuing one reformat retry")
            if timing_collector:
                timing_collector.record_report_reformat()
            if _audit:
                _audit.mark_reformatted(_audit_delegation)
            result["content"] = await _reformat_worker_report(
                chat_loop_fn, content, research_mode, model,
                cancel_event, num_ctx, timing_collector=timing_collector,
            )

    # P2.1 (B1): a halted worker produced NO findings, so whatever is sitting in
    # `content` is bookkeeping, not research. Replace it with a statement of what
    # actually happened, addressed to the agent that will read it. Done AFTER the
    # reformat retry so this text is the last word — the retry currently still
    # fires on a halt and dresses it up as a finished report, which is P2.6's
    # (separate) cost problem, not a correctness one once this overwrite lands.
    if result.get("halted"):
        logger.warning(
            "[Worker] Halted at the step cap (%s rounds) — %d source(s) retrieved, "
            "no findings produced",
            result["halted"].get("limit"), len(source_accumulator),
        )
        result["content"] = halt_worker_report(
            result["halted"], sources_retrieved=len(source_accumulator)
        )

    # P1.6 (B14): a provision URL no tool returned still resolves, so it reads
    # to a lawyer as a verified citation. Enforced here, AFTER the reformat retry
    # (which rewrites the report and could reintroduce one) and BEFORE source
    # filtering, so `_source_is_used` matches against the text the user will see.
    _content = result.get("content", "") or ""
    if _content:
        _content, _demoted, _unlinked = enforce_provision_links(_content, retrieved_urls)
        if _demoted or _unlinked:
            logger.info(
                f"[Worker] Provision links not returned by any tool: "
                f"{_demoted} demoted to the Act, {_unlinked} unlinked"
            )
            result["content"] = _content

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

    # P2.2 (B5): hand the search scope forward, in code, to the agent that will
    # actually write the negative. The tool-result block instructs the WORKER;
    # the Manager sees only this report, and the Deep Research synthesis sees
    # only the step findings, so neither had ever seen a scope block. Measured in
    # the first acceptance run: 6367 rep 1 carried the block in the Worker's
    # context **27 times**, three of its four reports carried no scope language
    # at all, and the answer still said a search "confirms" that no SSIs
    # prescribe the detail. Same fix shape as `provision_url_block` — carry the
    # fact across the lossy boundary rather than asking the model to.
    #
    # Appended LAST, after source filtering, and the order is load-bearing:
    # `_source_is_used` matches a source on its bare `legislation_id`, and the
    # record names the instruments that were section-searched. Appending before
    # the filter would mark those sources as cited by our own footer and silently
    # suppress P4.3's `turns_source_fallback` signal — a diagnostic corrupting
    # the measurement of a different bucket.
    _scope = worker_scope_block(search_log, cfg)
    if _scope:
        result["content"] = (result.get("content", "") or "") + _scope
    # Carried out to the answer seam, where the lawyer-facing footer is written.
    # One worker run is one delegation or one plan step; the caller accumulates
    # across them, because the footer describes the whole turn.
    result["searches"] = list(search_log)

    if _audit:
        _audit.end_delegation(
            _audit_delegation,
            report=result.get("content", "") or "",
            reformatted=bool(_audit_delegation and _audit_delegation.get("reformatted")),
            halted=result.get("halted"),
        )

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
            captured["options"] = [
                str(o).strip() for o in ((args or {}).get("options") or []) if str(o).strip()
            ][:4]
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
        return {
            "needs_clarification": True,
            "question": captured["question"],
            # Dropped when chips are off — the prompt tells the planner to fold
            # the alternatives into the question text instead.
            "options": (
                (captured.get("options") or [])
                if cfg.get("_suggested_questions_enabled", True)
                else []
            ),
        }
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
    # P2.2 (B5): every legislation search this turn ran, across ALL delegations,
    # and (P2.4) every case-law search. The footer describes the turn the lawyer
    # asked, not one delegation of it.
    all_searches: list = []
    # P2.8 (B5): set when this turn's searches cannot be known from
    # `all_searches`. A delegation that raised took its search record with it,
    # and a consulted peer searches with its own tools. In either case "no
    # search was run for this reply" might be false, so the carried scope line
    # stays silent.
    scope_unknown: list = []

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

    # P1.6 (B14): every legislation.gov.uk URL any tool returned this request.
    # Request-scoped, not delegation-scoped — the Manager may delegate several
    # times and the answer it composes draws on all of them.
    retrieved_urls: set = set()

    # P2.1 (B1): every worker that stopped at the step cap. Collected in code
    # rather than read back off the answer, because the failure being fixed is
    # precisely that the answer does not mention it.
    halts: list = []

    # P4.2 (B13): every completed worker report, kept so an empty Manager
    # completion does not also discard the research the lawyer already paid for.
    # Read only on that failure path; ordinary turns never touch it.
    worker_reports: list = []

    async def manager_tool_executor(name: str, args: dict) -> str:
        if name == "delegate_research":
            if timing_collector:
                timing_collector.record_delegation()
            research_id = uuid.uuid4().hex[:8]
            if on_chunk:
                await call_chunk(on_chunk, {"type": "tool_start", "tool": "Research Agent", "id": research_id})

            try:
                result = await run_worker_agent_fn(
                    args["query"], model, cancel_event, num_ctx, on_chunk,
                    emit_tool_details=emit_tool_details,
                    timing_collector=timing_collector,
                    tool_memo=tool_memo,
                    memo_count_redundant=True,
                    retrieved_urls=retrieved_urls,
                )
            except ConnectionError:
                # Provider unreachable: the Manager's own next call would fail too,
                # and ai.py renders this one with a specific message. Let it through.
                raise
            except Exception as e:
                # Contain the failure. A worker that dies (provider timeout, transport
                # error) used to take the entire SSE request with it — the lawyer got a
                # dead stream and lost the conversation along with every retrieval
                # already paid for. Handing the Manager an error string instead lets it
                # close the loop honestly. asyncio.CancelledError is a BaseException, so
                # a genuine user abort still propagates untouched.
                logger.error(
                    f"[Manager] Delegated research failed: {type(e).__name__}: {e}",
                    exc_info=True,
                )
                scope_unknown.append("delegation_failed")
                if on_chunk:
                    await call_chunk(on_chunk, {
                        "type": "tool_end", "tool": "Research Agent",
                        "id": research_id, "result": "Research failed",
                    })
                return (
                    "[Research Agent Error] The research step did not complete: "
                    f"{describe_agent_error(e)}. Do NOT call delegate_research again for "
                    "this question — the same failure will recur. Tell the user plainly "
                    "that the research could not be completed and suggest narrowing the "
                    "question. Do NOT invent findings or answer from memory."
                )

            if on_chunk:
                await call_chunk(on_chunk, {"type": "tool_end", "tool": "Research Agent", "id": research_id, "result": "Research Complete"})

            # Dedup across multiple delegate_research calls — the manager can
            # delegate more than once, and each worker independently reports the
            # same case/Act, producing duplicate entries in the References panel.
            for src in result.get("sources", []):
                if not _is_duplicate_source(src, accumulated_sources):
                    accumulated_sources.append(src)
            if result.get("halted"):
                halts.append({**result["halted"], "scope": "delegation"})
            all_searches.extend(result.get("searches") or [])
            if (result.get("content") or "").strip():
                worker_reports.append({
                    "title": f"Research step {len(worker_reports) + 1}",
                    "content": result["content"],
                })
            return f"[Research Agent Result]\n{result['content']}"

        if name == "consult_peer":
            scope_unknown.append("peer_consulted")
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
                _audit = get_audit_collector()
                if _audit:
                    _audit.record_peer_consult(peer_id, peer.name, question, answer)
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

    # P4.2 (B13). Last line of defence, above every strip below - all of which
    # are no-ops on an empty body, so without this the scope footer is appended
    # to nothing and the lawyer is shown a footer with no answer above it. That
    # is the exact shape of all nine blank turns measured across the replay
    # directories. `chat_loop` has already retried three times by the time this
    # runs, so reaching here means the provider returned nothing on every
    # attempt; the choice is between the research already in hand, labelled, and
    # a blank screen.
    if is_empty_completion(final.get("content"), None):
        logger.error(
            "[Manager] Empty completion returned as the answer - "
            "falling back to %d worker report(s)", len(worker_reports),
        )
        final["content"] = (
            fallback_from_reports(worker_reports, kind="manager")
            if worker_reports else LOST_ANSWER_NOTICE
        )
        final["answer_failed"] = True

    # Strip the model's <suggestions> block off the answer and attach it to the
    # result. This is the single manager return behind BOTH /api/chat and
    # /api/consult, so a consulted peer's block never reaches the calling bot's
    # context as a tool result. It must stay ABOVE the source block: sources are
    # matched against the content, and a URL inside a suggestion line would
    # otherwise falsely mark a source as cited.
    # The STRIP is unconditional even when the flag is off: the prompt asks the
    # model not to emit a block, but nothing enforces that, and an unstripped tag
    # would render as raw markup in the answer.
    suggestions_enabled = _cfg.get("_suggested_questions_enabled", True)
    clean, suggestions = extract_suggestions(final.get("content") or "")
    # P1.6 (B14) belt and braces. The Worker's report was already enforced, but
    # the Manager is instructed to pass it through verbatim and is not compelled
    # to — and in conversational mode it answers in its own words. Idempotent, so
    # a report that came through untouched is not marked twice.
    clean, _demoted, _unlinked = enforce_provision_links(clean, retrieved_urls)
    if _demoted or _unlinked:
        logger.info(
            f"[Manager] Provision links not returned by any tool: "
            f"{_demoted} demoted to the Act, {_unlinked} unlinked"
        )

    # P2.1 (B1). The Manager's OWN loop can hit the cap, in which case the raw
    # marker is the entire answer and no delegation report carries it (6383
    # turn 1) — so the Manager's result is checked here as well as the workers'.
    if final.get("halted"):
        halts.append({**final["halted"], "scope": "manager"})
    # Emitted by code, unconditionally when a halt occurred: the model may
    # disclose it well, badly ("timed out"), or not at all. Over the Wave 1
    # sweep's 11 halted turns, 6 said nothing and only 2 disclosed it
    # acceptably — and under Invariant 1 the silent halt is the worst of the
    # three outcomes, because the lawyer gets a normal-looking report with no
    # signal it is partial. The strip runs even with no halts, so a marker that
    # arrives by some other route still never renders.
    # P2.2 (B5): the scope block is an instruction to this agent, not prose for a
    # lawyer, and in research mode the Manager is told to pass the Worker's
    # report through verbatim — so without an unconditional strip the
    # bookkeeping renders on screen. Same shape and same reasoning as the halt
    # marker strip directly below.
    clean, _stripped = strip_scope_blocks(clean)
    if _stripped:
        logger.info("[Manager] Stripped %d search-scope block(s) from the answer", _stripped)
    clean, _disclosed = apply_halt_disclosure(clean, halts)
    if halts:
        logger.warning(
            "[Manager] %d halted worker(s) — answer marked incomplete", len(halts)
        )
        final["research_incomplete"] = {
            "reason": "step_cap",
            "halts": halts,
            "disclosed": _disclosed,
        }
    final["content"] = clean
    if suggestions and suggestions_enabled:
        final["suggestions"] = suggestions

    # Prompt-adherence floor: the block is enforced only by prompt wording, so
    # log drift rather than letting it surface in front of a user first. Skipped
    # for a consulted peer, which is explicitly told NOT to emit a block — and
    # when the flag is off, where a missing block is the intended behaviour.
    if suggestions_enabled and not _cfg.get("_consulted"):
        for issue in diagnose_suggestions(
            clean, suggestions, has_sources=bool(accumulated_sources)
        ):
            logger.warning("[Suggestions] %s", issue)

    if accumulated_sources:
        final["sources"] = [
            {**{k: v for k, v in s.items() if k != "n"}, "n": i + 1}
            for i, s in enumerate(accumulated_sources)
        ]

    # P2.2 (B5): the lawyer-facing scope line, emitted by code because carrying
    # the facts to this agent and asking it to state them got 52% of negatives,
    # not all of them. Appended last — after the source block is built, so a
    # query string in it can never be read as a citation. Empty on a turn that
    # ran no legislation search, so a purely conversational reply is untouched.
    # P3.5 found a P2.2 defect here: the footer is prose, so it survives into the
    # next turn's history, the model copies it back verbatim, and the code then
    # appends its own — the lawyer reads the same disclosure twice. Strip any
    # echo before appending the one computed from THIS turn's searches.
    _footer = answer_scope_footer(all_searches, _cfg)
    # P2.8 (B5): a reply that searched nothing gets no footer above, even when
    # it restates an earlier turn's negative. That is the case of a follow-up
    # answered from history. The earlier searches are restated here, labelled
    # as earlier, whenever an earlier reply in the history carries a fresh
    # footer. The gate is structural and never reads the answer. Manager path
    # only: the Deep Research synthesis sees the step findings and not the
    # conversation, so it cannot restate an earlier turn's negative.
    if not _footer and not scope_unknown:
        _footer = carried_scope_footer(messages, all_searches)
    # P2.4 (B12): the case-law corpus disclosure. Both lines above already carry
    # it as a clause when this turn searched case law; this is the turn with no
    # legislation line to join it to, which is every `case_law_only` turn. Not
    # suppressed by `scope_unknown`: it describes only the case-law searches
    # this turn recorded, and those did run.
    if not _footer:
        _footer = case_law_scope_footer(all_searches)
    final["content"] = strip_answer_footer(final.get("content") or "") + _footer

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
    # P1.6 (B14): shared across every step, deliberately. A provision retrieved
    # in step 2 is legitimately cited by the synthesis, which sees all the steps
    # at once; a per-step set would flag that as manufactured.
    retrieved_urls: set = set()
    # P2.1 (B1): plan steps that stopped at the step cap, with the step number
    # and approved title — only this loop knows them, and "step 4 is incomplete"
    # is far more use to a lawyer than "some research was incomplete".
    halts: list = []
    # P2.2 (B5): every legislation search the plan ran, across all steps, and
    # (P2.4) every case-law search.
    all_searches: list = []

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
        # run_worker_agent opens the audit delegation, but only this loop knows
        # the step number and the approved title — hand them over first.
        _audit = get_audit_collector()
        if _audit:
            _audit.set_next_delegation_meta(
                kind="deep_research_step", step=i, title=title,
            )
        result = await run_worker_agent_fn(
            brief, model, cancel_event, num_ctx, on_chunk,
            emit_tool_details=emit_tool_details,
            timing_collector=timing_collector,
            tool_memo=tool_memo,
            retrieved_urls=retrieved_urls,
        )

        if on_chunk:
            await call_chunk(on_chunk, {"type": "tool_end", "tool": label, "id": step_id, "result": "Step complete"})

        if result.get("halted"):
            halts.append({**result["halted"], "scope": "step", "step": i, "title": title})

        step_findings.append({
            "title": title,
            "detail": step.get("detail") or "",
            "content": result.get("content", "") or "",
        })
        for src in result.get("sources", []):
            if not _is_duplicate_source(src, accumulated_sources):
                accumulated_sources.append(src)
        all_searches.extend(result.get("searches") or [])

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
    # P2.2 (B5), the half P2.1 narrows but cannot close: a negative reached under
    # a halted step is a negative reached under a limit. 6382 rep 2 of P2.1's
    # acceptance sweep still opened "no SSIs ... were found" — from the two steps
    # that halted. Named here, in the payload, rather than in the synthesis
    # system prompt, for the reason halt_worker_report is a tool result: an
    # instruction about THESE steps travels with them.
    synthesis_user += incomplete_steps_note(halts, len(steps))
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

    # P4.2 (B13). `chat_loop` has already retried an empty completion up to three
    # times; this is what the lawyer gets if all three came back empty. 6383 rep 1
    # of P2.5's sweep is the measured case: 30 tool calls, 219 commencement
    # relations, three intact step reports of 4,836 / 5,777 / 7,190 chars — and a
    # report whose body was empty, footered and returned as though it were an
    # answer. Nothing downstream checked, so the failure was invisible.
    if is_empty_completion(final.get("content"), None):
        logger.error(
            "[DeepResearch] Synthesis returned no text after %d step(s) — "
            "falling back to the step findings, labelled as such",
            len(step_findings),
        )
        final["content"] = fallback_from_reports(
            [
                {"title": f"Step {i}: {f['title']}", "content": f["content"]}
                for i, f in enumerate(step_findings, 1)
            ],
            kind="synthesis",
        )
        final["synthesis_failed"] = True

    # Belt and braces: Deep Research reports are out of scope for suggestions
    # (the synthesis prompt never asks for a block), but this guarantees a stray
    # tag can never reach a report. Normally a no-op.
    final["content"] = extract_suggestions(final.get("content") or "")[0]

    # P1.6 (B14). The synthesis call composes its own prose from the step
    # reports, so a provision link the steps never carried can appear here for
    # the first time — this seam is not redundant with the per-worker one.
    _content, _demoted, _unlinked = enforce_provision_links(
        final.get("content") or "", retrieved_urls
    )
    if _demoted or _unlinked:
        logger.info(
            f"[DeepResearch] Provision links not returned by any tool: "
            f"{_demoted} demoted to the Act, {_unlinked} unlinked"
        )

    # P2.1 (B1). Synthesis is handed the step findings and composes freely, so a
    # halted step can vanish into a report that reads as complete — 6406 halted
    # ALL FOUR steps and produced a $2.36 report. The disclosure is code-emitted
    # and names the steps.
    # P2.2 (B5). Synthesis composes its own prose and should not copy the block,
    # but "should not" is not "cannot" — and a stray instruction block in a
    # finished report is worse than the clutter it saves.
    _content, _stripped = strip_scope_blocks(_content)
    if _stripped:
        logger.info(
            "[DeepResearch] Stripped %d search-scope block(s) from the report", _stripped
        )
    _content, _disclosed = apply_halt_disclosure(_content, halts)
    if halts:
        logger.warning(
            "[DeepResearch] %d of %d plan step(s) halted at the step cap — "
            "report marked incomplete", len(halts), len(steps),
        )
        final["research_incomplete"] = {
            "reason": "step_cap",
            "halts": halts,
            "steps_total": len(steps),
            "disclosed": _disclosed,
        }
    final["content"] = _content

    if accumulated_sources:
        final["sources"] = [
            {**{k: v for k, v in s.items() if k != "n"}, "n": i + 1}
            for i, s in enumerate(accumulated_sources)
        ]

    # P2.2 (B5): same code-emitted scope line as the Manager path. A Deep
    # Research report is composed from step findings and is the furthest any
    # answer travels from the searches that produced it.
    # P2.4 (B12): the case-law disclosure rides the same `searches` record
    # across steps, and joins the legislation line when there is one. 6375's
    # failing turn is this path: 18-30 case-law searches and no disclosure.
    final["content"] = strip_answer_footer(
        final.get("content") or ""
    ) + (answer_scope_footer(all_searches, _get_cfg())
         or case_law_scope_footer(all_searches))

    return final
