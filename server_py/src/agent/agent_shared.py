"""
Shared worker-tool execution logic used by both ollama_client and openrouter_client.

Both provider clients run an identical pipeline when processing Worker tool results:
execute the tool, optionally summarise large results, append a Phase 2 nudge for
search_legislation calls.  This module owns that logic once so future changes only
need to happen here.
"""
import json
import logging
import uuid
from typing import Callable, Optional

from ..utils.audit_trace import get_audit_collector
from ..utils.citation_links import harvest_legislation_urls, provision_url_block
from ..utils.section_outline import subsection_outline
from ..utils.discovery_budget import (
    legislation_budget_blocks,
    legislation_stop_message,
    section_budget_blocks,
    section_stop_message,
)
from ..utils.search_scope import (
    amendment_search_note,
    currency_note,
    enabling_power_note,
    legislation_search_note,
    not_held_note,
    record_budget_stop,
    record_section_budget_stop,
    record_case_law_search,
    record_currency,
    record_enabling_power,
    record_not_held,
    record_relations,
    record_search,
    section_search_note,
)
from .provider_factory import get_request_provider_config
from .summarisation import call_chunk, summarise_for_query
from .tools import (
    execute_worker_tool,
    execute_parliament_tool,
    execute_westminster_tool,
    extract_legislation_ids_from_search,
    detect_appellate_decisions,
    _PARLIAMENT_TOOL_NAMES,
)

logger = logging.getLogger("agent")


def describe_agent_error(exc: BaseException) -> str:
    """Human-readable one-liner for a provider/agent failure.

    httpx's timeout exceptions are raised through httpcore's exception mapping
    with an EMPTY message, so `str(exc)` is "" — which surfaced to the lawyer as
    an error banner with no text at all, and logged as "[AI] Chat error:" with
    nothing after the colon. Every caller that shows a failure to a user or the
    model should render it through here rather than str().
    """
    import httpx

    if isinstance(exc, httpx.TimeoutException):
        return (
            "the AI provider did not respond in time — this usually means the "
            "request was too large or the provider is overloaded"
        )
    if isinstance(exc, httpx.HTTPStatusError):
        return f"the AI provider returned HTTP {exc.response.status_code}"
    if isinstance(exc, httpx.TransportError):
        return f"could not reach the AI provider ({type(exc).__name__})"
    text = str(exc).strip()
    return text or f"an unexpected {type(exc).__name__}"


def _extract_sources_from_tool(name: str, args: dict, raw_result_str: str, accumulator: list) -> None:
    """Parse a raw tool result JSON string and append structured source dicts to accumulator.

    Called BEFORE summarisation so the full structured response is available.
    Internal bookkeeping keys (prefixed with '_') are stripped before the sources
    are exposed to the frontend.
    """
    try:
        data = json.loads(raw_result_str)
    except Exception:
        return

    if not isinstance(data, dict):
        return

    try:
        _extract_sources_inner(name, args, data, accumulator)
    except Exception as e:
        logger.debug(f"[Sources] Extraction skipped for '{name}': {e}")


def _legislation_kind(legislation_id: str) -> str:
    """Derive a human-readable source kind from the legislation_id path prefix."""
    prefix = legislation_id.split("/")[0].lower()
    if prefix in ("ukpga", "ukla", "ukppa", "ukpba", "nia", "asp", "anaw", "asc", "mwa"):
        return "Act"
    if prefix in ("uksi", "nisi", "wsi", "ssi", "nisr", "ukmo"):
        return "SI"
    if prefix == "ukdsi":
        return "Draft SI"
    return "Statute"


def _extract_sources_inner(name: str, args: dict, data: dict, accumulator: list) -> None:
    if name == "search_legislation":
        for item in data.get("results", []):
            lid = item.get("legislation_id") or ""
            if not lid:
                continue
            if any(s.get("_lid") == lid for s in accumulator):
                continue
            accumulator.append({
                "_lid": lid,
                "kind": _legislation_kind(lid),
                "title": item.get("title") or lid,
                "url": item.get("url") or "",
                # P2.5 renamed the slimmed key to `text_version` (see
                # `_slim_search_results`); `status` is read as a fallback so a
                # cached or replayed pre-P2.5 result still populates the rail.
                "meta": item.get("text_version") or item.get("status") or "",
                "year": item.get("year"),
                "extent": item.get("extent") or [],
                "cite": lid,
            })

    elif name == "search_legislation_sections":
        lid = args.get("legislation_id") or ""
        sections = data.get("sections") or data.get("results") or []
        for sec in sections[:1]:  # enrich with first matching section only
            sec_title = sec.get("title") or sec.get("section_title") or ""
            content = sec.get("content") or sec.get("text") or sec.get("excerpt") or ""
            section_number = sec.get("section_number") or sec.get("number") or ""
            excerpt = content[:300] if content else ""
            existing = next((s for s in accumulator if s.get("_lid") == lid), None)
            if existing:
                if not existing.get("sub") and sec_title:
                    existing["sub"] = sec_title
                if not existing.get("excerpt") and excerpt:
                    existing["excerpt"] = excerpt
                if section_number and existing.get("cite") == lid:
                    existing["cite"] = f"{existing.get('title', lid)}, s.{section_number}"
            else:
                accumulator.append({
                    "_lid": lid,
                    "kind": "Statute",
                    "title": data.get("title") or lid,
                    "sub": sec_title,
                    "excerpt": excerpt,
                    "cite": f"{lid}, s.{section_number}" if section_number else lid,
                    "url": data.get("url") or "",
                })

    elif name == "get_legislation_text":
        lid = args.get("legislation_id") or ""
        content = data.get("content") or data.get("text") or ""
        excerpt = content[:300] if content else ""
        existing = next((s for s in accumulator if s.get("_lid") == lid), None)
        if existing:
            if not existing.get("excerpt") and excerpt:
                existing["excerpt"] = excerpt
        else:
            accumulator.append({
                "_lid": lid,
                "kind": "Statute",
                "title": data.get("title") or lid,
                "excerpt": excerpt,
                "cite": lid,
                "url": data.get("url") or "",
            })

    elif name == "get_legislation_changes":
        # P3.5 (B3). The instruments a change record names are the answer to a
        # commencement question, so an answer citing SSI 2025/119 must be able
        # to show it in the References rail.
        #
        # **Deliberately no excerpt, and the subtitle says what was established.**
        # The change record proves that this instrument commenced or amended
        # provisions of the subject; it does NOT mean its text was read.
        # `_source_is_used` keeps a source unconditionally when it carries an
        # excerpt, so giving one here would pin every related instrument into the
        # rail whether or not the answer cited it — overstating what the research
        # did and inflating `sources_kept`. Without one, only the instruments the
        # answer actually names survive the filter.
        for group in (data.get("related") or [])[:10]:
            if not isinstance(group, dict) or group.get("self"):
                continue
            rel_lid = group.get("legislation_id") or ""
            if not rel_lid or any(s.get("_lid") == rel_lid for s in accumulator):
                continue
            effect = group.get("type_of_effect") or "change"
            subject = data.get("legislation_id") or args.get("legislation_id") or ""
            accumulator.append({
                "_lid": rel_lid,
                "kind": "Statute",
                "title": rel_lid,
                "sub": f"recorded as {effect} for provisions of {subject}",
                "cite": rel_lid,
                "url": group.get("url") or "",
            })

    elif name == "search_case_law":
        for case in data.get("results", []):
            url = case.get("url") or case.get("link") or ""
            if url and any(s.get("url") == url for s in accumulator):
                continue
            ncn = case.get("ncn") or case.get("neutral_citation") or ""
            court = case.get("court") or ""
            date = case.get("date") or ""
            meta_parts = [p for p in [court, date] if p]
            accumulator.append({
                "kind": "Case",
                "title": case.get("title") or case.get("name") or "",
                "sub": ncn,
                "meta": ", ".join(meta_parts),
                "cite": ncn,
                "url": url,
            })

    elif name == "get_case_law_text":
        url = data.get("url") or args.get("url") or ""
        text = data.get("text") or ""
        excerpt = text[:300] if text else ""
        existing = next((s for s in accumulator if s.get("url") == url), None)
        if existing:
            if not existing.get("excerpt") and excerpt:
                existing["excerpt"] = excerpt
        else:
            ncn = data.get("ncn") or ""
            accumulator.append({
                "kind": "Case",
                "title": data.get("title") or url,
                "sub": ncn,
                "excerpt": excerpt,
                "cite": ncn or url,
                "url": url,
            })

    elif name == "search_scottish_parliament":
        for speech in data.get("results", []):
            url = speech.get("url", "")
            if url and any(s.get("url") == url for s in accumulator):
                continue
            accumulator.append({
                "kind": "Scottish Parliament",
                "title": speech.get("debate", ""),
                "sub": speech.get("speaker", ""),
                "meta": speech.get("hdate", ""),
                "cite": f"{speech.get('speaker', '')}, {speech.get('hdate', '')}",
                "url": url,
            })

    elif name == "search_bills":
        # Holyrood bills come back camelCase, Westminster bills snake_case — the
        # tool name is shared across both bots, so accept either spelling.
        for bill in data.get("results", []):
            url = bill.get("url", "")
            if url and any(s.get("url") == url for s in accumulator):
                continue
            title = bill.get("shortTitle") or bill.get("short_title") or ""
            accumulator.append({
                "kind": "Bill",
                "title": title,
                "sub": bill.get("currentStage") or bill.get("current_stage") or "",
                "meta": bill.get("current_house") or "",
                "cite": title,
                "url": url,
            })

    elif name == "get_member_info":
        for member in data.get("results", []):
            url = member.get("url", "")
            if url and any(s.get("url") == url for s in accumulator):
                continue
            accumulator.append({
                "kind": "Member",
                "title": member.get("name", ""),
                "sub": member.get("party", ""),
                "meta": member.get("constituency", ""),
                "cite": member.get("name", ""),
                "url": url,
            })

    elif name == "search_hansard":
        for item in data.get("results", []):
            url = item.get("url", "")
            if url and any(s.get("url") == url for s in accumulator):
                continue
            title = item.get("title", "")
            date = item.get("date", "")
            section = item.get("section", "")
            accumulator.append({
                "kind": "Hansard",
                "title": title or "Hansard debate",
                "sub": section,
                "meta": date,
                "cite": f"HC Deb, {date}, {title}" if item.get("house") == "Commons" else f"HL Deb, {date}, {title}",
                "url": url,
            })

    elif name == "get_hansard_debate":
        url = data.get("url") or ""
        title = data.get("title") or ""
        date = data.get("date") or ""
        contributions = data.get("contributions") or []
        excerpt = contributions[0].get("text", "")[:300] if contributions else ""
        # Item-level video entry point: the first contribution with a deep link
        # marks where this debate starts on parliamentlive (mirrors the SP branches).
        video = None
        for c in contributions:
            dl = c.get("video_deeplink")
            if dl and dl.get("url"):
                video = {"url": dl["url"], "clip_start": dl.get("clip_start"), "label": dl.get("label")}
                break
        existing = next((s for s in accumulator if s.get("url") == url), None)
        if existing:
            if not existing.get("excerpt") and excerpt:
                existing["excerpt"] = excerpt
            if video and not existing.get("video"):
                existing["video"] = video
        else:
            src = {
                "kind": "Hansard",
                "title": title or "Hansard debate",
                "sub": data.get("location") or "",
                "meta": date,
                "excerpt": excerpt,
                "cite": f"HC Deb, {date}, {title}" if data.get("house") == "Commons" else f"HL Deb, {date}, {title}",
                "url": url,
            }
            if video:
                src["video"] = video
            accumulator.append(src)

    elif name == "search_scottish_committee_transcripts":
        for item in data.get("results", []):
            url = item.get("url", "")
            if url and any(s.get("url") == url for s in accumulator):
                continue
            committee = item.get("committee_name", "")
            meeting_date = item.get("meeting_date", "")
            agenda_title = item.get("agenda_item_title", "")
            accumulator.append({
                "kind": "Committee",
                "title": committee,
                "sub": agenda_title,
                "meta": meeting_date,
                "cite": f"{committee}, {meeting_date}",
                "url": url,
            })

    elif name == "get_scottish_committee_transcript":
        url = data.get("url") or args.get("url") or ""
        page_title = data.get("page_title") or data.get("committee_name") or ""
        speeches = data.get("speeches") or []
        excerpt = speeches[0].get("text", "")[:300] if speeches else ""
        # Item-level video entry point: the first speech with a confident deep link
        # marks where this agenda item starts on SP TV (mirrors the plenary branch).
        video = None
        for sp in speeches:
            dl = sp.get("video_deeplink")
            if dl and dl.get("url"):
                video = {"url": dl["url"], "clip_start": dl.get("clip_start")}
                break
        existing = next((s for s in accumulator if s.get("url") == url), None)
        if existing:
            if not existing.get("excerpt") and excerpt:
                existing["excerpt"] = excerpt
            if video and not existing.get("video"):
                existing["video"] = video
        else:
            src = {
                "kind": "Transcript",
                "title": page_title or "Scottish Parliament Committee",
                "excerpt": excerpt,
                "cite": page_title or url,
                "url": url,
            }
            if video:
                src["video"] = video
            accumulator.append(src)

    elif name == "search_scottish_plenary":
        for item in data.get("results", []):
            url = item.get("url", "")
            if url and any(s.get("url") == url for s in accumulator):
                continue
            meeting_date = item.get("meeting_date", "")
            agenda_title = item.get("agenda_item_title", "")
            accumulator.append({
                "kind": "Plenary",
                "title": agenda_title or "Meeting of Parliament",
                "sub": "Meeting of Parliament",
                "meta": meeting_date,
                "cite": f"Meeting of Parliament, {meeting_date} — {agenda_title}",
                "url": url,
            })

    elif name == "get_scottish_plenary_debate":
        url = data.get("url") or args.get("url") or ""
        page_title = data.get("page_title") or ""
        speeches = data.get("speeches") or []
        excerpt = speeches[0].get("text", "")[:300] if speeches else ""
        # Item-level video entry point: the first speech with a confident deep link
        # marks where this agenda item starts on SP TV. (Per-moment links are inline
        # in the answer; the panel offers a single "watch from …" for the item.)
        video = None
        for sp in speeches:
            dl = sp.get("video_deeplink")
            if dl and dl.get("url"):
                video = {"url": dl["url"], "clip_start": dl.get("clip_start")}
                break
        existing = next((s for s in accumulator if s.get("url") == url), None)
        if existing:
            if not existing.get("excerpt") and excerpt:
                existing["excerpt"] = excerpt
            if video and not existing.get("video"):
                existing["video"] = video
        else:
            src = {
                "kind": "Plenary",
                "title": page_title or "Scottish Parliament Plenary",
                "excerpt": excerpt,
                "cite": page_title or url,
                "url": url,
            }
            if video:
                src["video"] = video
            accumulator.append(src)


def summarised_result_blocks(name: str, raw_result) -> str:
    """What a SUMMARISED tool result gets back, built from the RAW result.

    Two blocks, both restoring what the summariser dropped: P1.6's provision
    URLs (`provision_url_block`, any tool) and P3.11's subsection outline
    (`subsection_outline`, section searches only - a whole-Act retrieval has
    no `results` rows and a change record no provision text). One definition,
    shared with `tools/seam_replay.py --from-raw`, so the seam rebuilds
    exactly the blocks the product appends rather than a copy that drifts.
    Returns "" when there is nothing to hand back.
    """
    blocks = provision_url_block(raw_result)
    if name == "search_legislation_sections":
        blocks += subsection_outline(raw_result)
    return blocks


def _worker_tool_key_arg(args: dict) -> Optional[str]:
    """Identifying argument for redundancy detection (record_worker_tool).

    A transcript's identity is (meeting_id, iob_id) — two different agenda
    items of one meeting are legitimate distinct retrievals, not redundant.
    slug is derivable and must NOT be part of the key.

    **P3.5 adds `direction` to the key for the same reason** (bucket B3).
    `get_legislation_changes` is the first legislation tool that takes a second
    identifying argument: the two directions over one `legislation_id` are
    different questions — what commenced this Act, and what this Act commences —
    and on `asp/2025/2` they return 36 and 143 relations respectively. Keyed on
    the id alone, asking both would be scored a redundant re-fetch and, on the
    legislation profile where `max_redundant_tool_calls` is 0, would write an
    EFFICIENCY breach for correct behaviour.
    """
    key_arg = args.get("legislation_id") or args.get("url") or args.get("gid") or args.get("debate_ext_id")
    if key_arg and args.get("direction"):
        key_arg = f"{key_arg}:{args['direction']}"
    if not key_arg and args.get("meeting_id"):
        key_arg = f"{args['meeting_id']}:{args.get('iob_id', '')}"
    return key_arg


async def run_worker_tool(
    name: str,
    args: dict,
    query: str,
    chunk_fn: Callable,
    summarise_model: str,
    parent_on_chunk: Optional[Callable] = None,
    timing_collector=None,
    source_accumulator: Optional[list] = None,
    search_budget: Optional[dict] = None,
    cancel_event=None,
    tool_memo: Optional[dict] = None,
    memo_count_redundant: bool = False,
    context_budget: Optional[dict] = None,
    audit_delegation: Optional[dict] = None,
    retrieved_urls: Optional[set] = None,
    search_log: Optional[list] = None,
) -> str:
    """Execute a single Worker tool call and return the (possibly summarised) result.

    Args:
        name: Tool function name.
        args: Tool arguments dict.
        query: The original research query, used to focus summarisation.
        chunk_fn: Provider-specific summarisation chunk function.
        summarise_model: Model to use for summarisation (may differ from main model).
        parent_on_chunk: SSE streaming callback for progress events.
        timing_collector: Optional timing collector for metrics.
        source_accumulator: If provided, structured sources are extracted from the
            raw result (before summarisation) and appended here.
        tool_memo: Per-request memo dict keyed
            (tool_name, canonical args JSON) → {"raw", "final"}. Exact-match
            repeats return the cached final result without the API call or
            re-summarisation; the memo dies with the request.
        memo_count_redundant: If True (standard research mode), a memo hit is
            ALSO counted via record_worker_tool so the "model re-fetched the
            same Act" loop-health signal survives — the hit costs nothing but
            still reflects model behaviour. Deep Research leaves this False:
            cross-step reuse there is by design, not misbehaviour.
        context_budget: Per-worker-run {"used": chars, "limit": chars}. Once the
            accumulated tool output would exceed the limit, results are summarised
            regardless of their own size — the per-result threshold alone does not
            bound the sum. None disables the budget.
        audit_delegation: The audit trace's delegation record this tool call
            belongs to (evaluation harnesses only; None on /api/chat). Passed
            explicitly rather than read from a ContextVar so nesting stays
            correct if worker runs are ever parallelised.
        retrieved_urls: Per-request set of every legislation.gov.uk URL any tool
            returned, harvested from the RAW response (P1.6/B14). Feeds the
            provision-link enforcement at the answer seam. None disables both the
            harvest and, downstream, the enforcement — so a caller that does not
            thread it keeps exactly the previous behaviour.
        search_log: Per-WORKER-RUN list of the searches this run issued (P2.2/B5).
            Rendered onto the worker's report by `run_worker_agent`, because the
            agent that writes the negative — the Manager, or the Deep Research
            synthesis — never sees a tool result. Run-scoped, not request-scoped,
            unlike `retrieved_urls`: "what this step searched for" is a statement
            about one step. None disables the record.
    """
    activity_id = uuid.uuid4().hex[:8]

    # Audit trace: open a tool record and sniff the on_chunk callback so the
    # external API calls the executor makes land inside THIS tool's record.
    _audit = get_audit_collector()
    _audit_tool = _audit.start_tool(audit_delegation, name, args) if _audit else None
    if _audit_tool is not None:
        parent_on_chunk = _audit.sniff_on_chunk(_audit_tool, parent_on_chunk)

    # P2.7: the legislation discovery budget, checked BEFORE the memo lookup
    # (the parliamentary one below is checked after it, and is unchanged). A
    # step repeating its own search is the loop this budget exists for, so a
    # memo-served search is refused too once the step's search rounds are
    # spent (see utils/discovery_budget.py). A blocked call is not a search:
    # it is kept out of `record_search` and the phase counts, and recorded
    # instead as a stop, which the worker's block and the lawyer's footer
    # both state as a limit.
    #
    # P3.1: the per-instrument section budget, the same way one level down: at
    # most 3 rounds of `search_legislation_sections` on one legislation_id per
    # worker run, also checked before the memo. Its refusals share this path,
    # the audit's `budget_blocked` flag and the `search_budget_blocked`
    # counter; the audit record's tool name tells the two apart.
    refusal = None
    if search_budget is not None:
        if legislation_budget_blocks(search_budget, name):
            record_budget_stop(search_log, name, args, search_budget)
            refusal = (legislation_stop_message(search_budget),
                       "Discovery budget spent", "Search limit reached")
        elif section_budget_blocks(search_budget, name, args):
            record_section_budget_stop(search_log, name, args, search_budget)
            refusal = (section_stop_message(search_budget, args),
                       "Section budget spent for this instrument",
                       "Section-search limit reached")
    if refusal is not None:
        stop_msg, log_label, ui_label = refusal
        if timing_collector:
            timing_collector.record_search_budget_blocked()
        logger.info(f"[Worker] {log_label} — '{name}' not run")
        if parent_on_chunk:
            await call_chunk(parent_on_chunk, {"type": "tool_start", "tool": f"Worker: {name}", "id": activity_id})
            await call_chunk(parent_on_chunk, {"type": "tool_end", "tool": f"Worker: {name}", "id": activity_id, "result": ui_label})
        if _audit:
            _audit.end_tool(
                _audit_tool, raw_result=stop_msg, final_result=stop_msg,
                budget_blocked=True,
            )
        return stop_msg

    # Tool-result memo: exact-arg repeats within one request are served from
    # the per-request memo. In Deep Research, counted only as memo_hits — NOT
    # as a worker tool call / phase call / redundant call (it's a saving, not
    # a loop-health signal); standard mode also counts redundancy (see
    # memo_count_redundant). A hit never consumes the search budget.
    memo_key = None
    if tool_memo is not None:
        try:
            memo_key = (name, json.dumps(args, sort_keys=True))
        except (TypeError, ValueError):
            memo_key = None
        if memo_key is not None and memo_key in tool_memo:
            hit = tool_memo[memo_key]
            logger.info(f"[Worker] Memo hit for '{name}' — returning cached result")
            if timing_collector:
                timing_collector.record_memo_hit()
                if memo_count_redundant:
                    timing_collector.record_worker_tool(name, _worker_tool_key_arg(args))
            # The reusing step must still get this retrieval's sources: re-run
            # extraction on the stored RAW result against this step's accumulator.
            if source_accumulator is not None:
                _extract_sources_from_tool(name, args, hit["raw"], source_accumulator)
            # Same for the retrieved-URL set: the memo saves the fetch, not the
            # provenance. A step reusing a memoised retrieval has still retrieved
            # those provisions and must be allowed to cite them.
            if retrieved_urls is not None:
                harvest_legislation_urls(hit["raw"], into=retrieved_urls)
            # P2.9 (B5): the search itself, which P2.2 did not record on this
            # path. `search_log` is per-WORKER-RUN while the memo is
            # per-REQUEST, so a step served from an earlier step's search had
            # that query missing from its own record — and the block still told
            # the agent writing the negative that it "MUST quote the search
            # terms above", with none above. Measured over the six replay
            # directories that have a scope block (`replay_report scoperecord`):
            # 277 of 1,189 searches (23%) absent, in 86 of 259 worker runs
            # (33%), 11 of which recorded NO search at all; and `issued -
            # recorded == memo hits` exactly, per run, with no exceptions across
            # all six — which is what identifies the memo as the sole cause.
            # Gated on the tool name here because `record_search` does not
            # self-gate: the two call sites on the non-memo path do it, and this
            # is the third.
            if name in ("search_legislation", "search_legislation_sections"):
                record_search(search_log, name, args, hit["raw"])
            # P2.3 (B3b): a memo hit is still a retrieval for this step, and the
            # enabling-power record drives a PERMISSION as well as a prohibition
            # — omitting it here would forbid a claim the material supports.
            record_enabling_power(search_log, name, args, hit["raw"])
            # P3.5 (B3): and the change record, for the same reason — a step
            # reusing a memoised retrieval has still consulted it, and the
            # record drives a PERMISSION (state the relation) as well as a
            # disclosure. Silent here, the worker's report would say the step
            # never looked.
            record_relations(search_log, name, args, hit["raw"])
            # P2.5 (B4): and the currency evidence. Same argument a third time,
            # and it bites hardest here: `_currency_limb` speaks on every step
            # that touched legislation, so a memo hit that did not record its
            # `valid_date` or its `coming into force` count would leave the
            # report block forbidding a currency statement the step's own
            # retrieval supports.
            record_currency(search_log, name, args, hit["raw"])
            # P2.4 (B12): and a case-law search, for the lawyer-facing corpus
            # disclosure. A memo-served search is still a search this step ran;
            # P2.9 is the measured cost of forgetting that on this path.
            # Self-gated on the tool name.
            record_case_law_search(search_log, name, args, hit["raw"])
            # P2.4 (6373): a memoised not-found is still this step's not-found.
            record_not_held(search_log, name, args, hit["raw"])
            if parent_on_chunk:
                await call_chunk(parent_on_chunk, {"type": "tool_start", "tool": f"Worker: {name}", "id": activity_id})
                await call_chunk(parent_on_chunk, {"type": "tool_end", "tool": f"Worker: {name}", "id": activity_id, "result": "Done (cached)"})
            # A memo hit costs no API call, but the result still lands in the
            # context a second time — so it still spends context budget.
            if context_budget is not None:
                context_budget["used"] += len(hit["final"])
            if _audit:
                _audit.end_tool(
                    _audit_tool, raw_result=hit["raw"], final_result=hit["final"],
                    memo_hit=True,
                )
            return hit["final"]

    # Parliamentary search budget: after the allowed number of search/listing calls,
    # return a hard-stop so the model proceeds to retrieval instead of looping.
    _PARLIAMENT_SEARCH_TOOLS = {
        "search_scottish_parliament", "search_scottish_committee_transcripts", "search_scottish_plenary",
        "search_hansard",  # Westminster discovery tool — same budget, same stop semantics
    }
    # `"remaining" in` since P2.7: a legislation budget is also a dict now, and
    # a parliamentary tool name hallucinated in a legislation mode must reach
    # the executor's unknown-tool path, not a KeyError here.
    if search_budget is not None and "remaining" in search_budget and name in _PARLIAMENT_SEARCH_TOOLS:
        if search_budget["remaining"] <= 0:
            # The parliament bot's defining constraint: a budget-blocked search
            # means the model looped on discovery instead of retrieving. Count it
            # on its own counter (NOT worker_tool_calls / phase counts).
            if timing_collector:
                timing_collector.record_search_budget_blocked()
            if name == "search_hansard":
                instruction = (
                    "STOP calling search_hansard. You MUST now either: (a) call get_hansard_debate "
                    "with a debate_ext_id from your previous search results to retrieve the full "
                    "verbatim contributions, or (b) if no results were found at all, synthesize your "
                    "answer stating that no relevant records were found."
                )
            else:
                instruction = (
                    "STOP calling search_scottish_plenary, search_scottish_parliament, or "
                    "search_scottish_committee_transcripts. "
                    "You MUST now either: (a) call get_scottish_plenary_debate or "
                    "get_scottish_committee_transcript with the IDs from your previous search results to "
                    "retrieve full text (search_scottish_parliament results are excerpt-only and need no "
                    "retrieval), or (b) if no results were found at all, synthesize your answer stating that "
                    "no relevant records were found."
                )
            stop_msg = json.dumps({
                "notice": "Search limit reached — you have already performed the maximum number of parliamentary searches.",
                "instruction": instruction,
                "results": [],
                "total": 0,
            })
            if parent_on_chunk:
                await call_chunk(parent_on_chunk, {"type": "tool_start", "tool": f"Worker: {name}", "id": activity_id})
                await call_chunk(parent_on_chunk, {"type": "tool_end", "tool": f"Worker: {name}", "id": activity_id, "result": "Search limit reached"})
            if _audit:
                _audit.end_tool(
                    _audit_tool, raw_result=stop_msg, final_result=stop_msg,
                    budget_blocked=True,
                )
            return stop_msg
        search_budget["remaining"] -= 1

    # Efficiency: count the worker tool call, classify its phase, and flag a
    # repeat fetch of the same resource (same Act sectioned twice, same case
    # fetched twice). key_arg is the identifying argument for redundancy.
    if timing_collector:
        timing_collector.record_worker_tool(name, _worker_tool_key_arg(args))

    if parent_on_chunk:
        await call_chunk(parent_on_chunk, {"type": "tool_start", "tool": f"Worker: {name}", "id": activity_id})

    # Dispatch by research mode first: get_member_info / search_bills exist in BOTH
    # the Holyrood and Westminster tool sets with the same names but different
    # backing APIs, so name alone cannot pick the executor.
    if get_request_provider_config().get("_research_mode") == "westminster_records":
        result = await execute_westminster_tool(name, args, on_chunk=parent_on_chunk, timing_collector=timing_collector)
    elif name in _PARLIAMENT_TOOL_NAMES:
        result = await execute_parliament_tool(name, args, on_chunk=parent_on_chunk, timing_collector=timing_collector)
    else:
        result = await execute_worker_tool(name, args, on_chunk=parent_on_chunk, timing_collector=timing_collector)

    # Kept for the memo: source extraction on a memo hit re-parses the raw
    # (pre-summarisation) response, not the summarised final string.
    raw_result = result

    # Extract sources from the raw structured response BEFORE summarisation compresses it.
    if source_accumulator is not None:
        _extract_sources_from_tool(name, args, result, source_accumulator)

    # P1.6 (B14): record every legislation.gov.uk URL this retrieval returned,
    # from the RAW response. "Did the research retrieve this provision" and "was
    # the model shown the string" are different questions, and they diverge on
    # the ~70% of section searches that get summarised — the summary keeps the
    # section numbers and drops every URL.
    if retrieved_urls is not None:
        harvest_legislation_urls(raw_result, into=retrieved_urls)

    # For search_case_law: inject a Phase 2 nudge to call get_case_law_text for
    # the most relevant results, or a stop note on zero results.
    case_law_note = ""
    # P2.4 (B12): recorded before the parse below, so an errored search (which
    # is not always JSON) is still recorded, as not ok. It feeds the code-emitted
    # corpus disclosure on the answer, which fires on any turn that searched
    # case law, not only on the empty result this note handles.
    record_case_law_search(search_log, name, args, result)
    if name == "search_case_law":
        try:
            raw_data = json.loads(result)
            n = raw_data.get("total", 0)
            if n == 0 and not raw_data.get("error"):
                # P2.4 (B12): "does not comprehensively index" was false; the
                # gap is total (TNA rejects `court=csoh` with a 400). The UKSC
                # half matters as much: Scottish appeals ARE indexed.
                case_law_note = (
                    "\n\n[This search returned 0 results. The National Archives Find Case Law database "
                    "holds no decisions of the Court of Session, the Sheriff Appeal Court, the Sheriff "
                    "Courts or the High Court of Justiciary; Scottish appeals decided by the UK Supreme "
                    "Court are included. "
                    "If you have already tried 2–3 different queries without results, stop searching "
                    "and compose your answer noting that no directly relevant case law was found in this database.]"
                )
            elif n > 0:
                results = raw_data.get("results", [])
                url_lines = "\n".join(
                    f'  - url: "{r["url"]}"  ({r.get("title", "")} {r.get("ncn", "")})'
                    for r in results[:3]
                    if r.get("url")
                )
                case_law_note = (
                    f"\n\n[MANDATORY NEXT STEP — DO NOT synthesise yet. "
                    f"Call get_case_law_text for the 1–3 most relevant cases below to retrieve the full judgment text "
                    f"before composing your answer. Pass the exact url field:\n{url_lines}]"
                )
                # Appeals nudge: when both a first-instance judgment and its appeal
                # appear in the results, cite the higher court, not only the lower one.
                appeals = detect_appellate_decisions(results)
                if appeals:
                    logger.info(
                        "[Worker] A2 appellate nudge fired: flagged %d appellate decision(s) — %s",
                        len(appeals),
                        ", ".join(r.get("url", "") for r in appeals[:3]),
                    )
                    appeal_lines = "\n".join(
                        f'  - url: "{r["url"]}"  ({r.get("title", "")} {r.get("ncn", "")})'
                        for r in appeals[:3]
                    )
                    case_law_note += (
                        f"\n\n[NOTE — APPELLATE DECISION PRESENT: the results include an appeal "
                        f"of a case that also appears at a lower court level. You MUST retrieve and "
                        f"cite the appellate (higher-court) decision below via get_case_law_text — "
                        f"do not rely on the first-instance judgment alone:\n{appeal_lines}]"
                    )
        except Exception:
            pass

    # For search_scottish_parliament: the results are excerpt-only (TheyWorkForYou
    # exposes no full-text retrieval endpoint for Holyrood plenary content), so nudge
    # the model to synthesise from the excerpts rather than re-searching or trying to
    # fetch full text.
    sp_phase2_note = ""
    if name == "search_scottish_parliament":
        try:
            raw_data = json.loads(result)
            results = raw_data.get("results", [])
            if results:
                sp_phase2_note = (
                    "\n\n[These Scottish Parliament plenary results are EXCERPT-ONLY — there is no full-text "
                    "retrieval tool for them. DO NOT call search_scottish_parliament again (unless you received "
                    "ZERO results). Compose your answer from the excerpts above, citing the speaker, date, and URL "
                    "of each. If the question concerns committee activity, call search_scottish_committee_transcripts.]"
                )
            else:
                sp_phase2_note = (
                    "\n\n[This search returned 0 results. You may retry search_scottish_parliament with "
                    "different or broader keywords. If after 2 searches you still have 0 results, "
                    "state that no relevant Scottish Parliament records were found and compose your answer.]"
                )
        except Exception:
            pass

    sp_committee_phase2_note = ""
    if name == "search_scottish_committee_transcripts":
        try:
            raw_data = json.loads(result)
            items = raw_data.get("results", [])
            note = raw_data.get("note", "")
            if note and not items:
                sp_committee_phase2_note = f"\n\n[{note}]"
            elif items:
                item_lines = [
                    f'  - meeting_id: "{r["meeting_id"]}"  slug: "{r["slug"]}"  iob_id: "{r["iob_id"]}"'
                    f'  ({r.get("committee_name", "")}, {r.get("meeting_date", "")} — {r.get("agenda_item_title", "")})'
                    for r in items[:8]
                    if r.get("meeting_id") and r.get("iob_id")
                ]
                if item_lines:
                    sp_committee_phase2_note = (
                        f"\n\n[MANDATORY NEXT STEP — Call get_scottish_committee_transcript for the most "
                        f"relevant result(s) below to retrieve full speech text before composing your answer. "
                        f"Pass meeting_id, slug, and iob_id exactly as shown:\n"
                        + "\n".join(item_lines)
                        + "]"
                    )
            else:
                sp_committee_phase2_note = (
                    "\n\n[No committee transcript results found. "
                    "Try search_scottish_committee_transcripts with different or broader keywords, "
                    "or use search_scottish_parliament for plenary debates.]"
                )
        except Exception:
            pass

    sp_plenary_phase2_note = ""
    if name == "search_scottish_plenary":
        try:
            raw_data = json.loads(result)
            items = raw_data.get("results", [])
            note = raw_data.get("note", "")
            if note and not items:
                sp_plenary_phase2_note = f"\n\n[{note}]"
            elif items:
                item_lines = [
                    f'  - meeting_id: "{r["meeting_id"]}"  slug: "{r["slug"]}"  iob_id: "{r["iob_id"]}"'
                    f'  ({r.get("meeting_date", "")} — {r.get("agenda_item_title", "")})'
                    for r in items[:8]
                    if r.get("meeting_id") and r.get("iob_id")
                ]
                if item_lines:
                    sp_plenary_phase2_note = (
                        f"\n\n[MANDATORY NEXT STEP — Call get_scottish_plenary_debate for the most "
                        f"relevant result(s) below to retrieve the full verbatim speeches before composing "
                        f"your answer. Pass meeting_id, slug, and iob_id exactly as shown:\n"
                        + "\n".join(item_lines)
                        + "]"
                    )
            else:
                sp_plenary_phase2_note = (
                    "\n\n[No plenary debate results found. "
                    "Try search_scottish_plenary with different or broader keywords, "
                    "or use search_scottish_parliament for excerpt-only plenary content.]"
                )
        except Exception:
            pass

    hansard_phase2_note = ""
    if name == "search_hansard":
        try:
            raw_data = json.loads(result)
            items = raw_data.get("results", [])
            note = raw_data.get("note", "")
            if items:
                item_lines = [
                    f'  - debate_ext_id: "{r["debate_ext_id"]}"'
                    f'  ({r.get("house", "")} {r.get("section", "")}, {r.get("date", "")} — {r.get("title", "")})'
                    for r in items[:8]
                    if r.get("debate_ext_id")
                ]
                if item_lines:
                    hansard_phase2_note = (
                        "\n\n[MANDATORY NEXT STEP — Call get_hansard_debate for the most relevant "
                        "result(s) below to retrieve the full verbatim contributions before composing "
                        "your answer. Pass debate_ext_id exactly as shown:\n"
                        + "\n".join(item_lines)
                        + "]"
                    )
            elif note:
                hansard_phase2_note = f"\n\n[{note}]"
            else:
                hansard_phase2_note = (
                    "\n\n[This search returned 0 results. You may retry search_hansard once with "
                    "different or broader keywords. If you still have 0 results, state that no "
                    "relevant Hansard records were found and compose your answer.]"
                )
        except Exception:
            pass

    # For search_legislation: capture legislation_ids from the raw response before
    # any summarisation strips them, so we can inject a Phase 2 instruction into
    # the final result the model actually sees.
    #
    # P2.2 (B5) adds the scope block alongside. The row was written against the
    # missing `else:` on `if id_pairs:` — the only search tool with no
    # zero-result nudge — but that branch fires on 4 of 790 searches post-Wave-1,
    # while **783 of 783** are windowed (5 rows of a median 141 matches) and all
    # 17 measured bare negatives came from a NON-empty result. So the block is
    # attached on both branches, and the non-empty one is the one that matters.
    phase2_note = ""
    scope_note = ""
    if name == "search_legislation":
        try:
            raw_data = json.loads(result)
            id_pairs = extract_legislation_ids_from_search(raw_data)
            if timing_collector:
                timing_collector.record_legislation_ids_seen(lid for lid, _ in id_pairs)
            scope_note = legislation_search_note(
                args, raw_data, get_request_provider_config()
            )
            record_search(search_log, name, args, raw_data)
            # P2.5 (B4): the repeal/revocation marker legislation.gov.uk puts in
            # the title itself — the only currency signal a search result
            # carries, on 1.7% of rows, and the one a lawyer must not miss.
            scope_note += currency_note(args, raw_data)
            record_currency(search_log, name, args, raw_data)
            if id_pairs:
                id_lines = "\n".join(
                    f'  - legislation_id: "{lid}"  ({title})'
                    for lid, title in id_pairs[:5]
                )
                phase2_note = (
                    f"\n\n[NEXT STEP: Call search_legislation_sections with the relevant "
                    f"legislation_id(s) below to retrieve the actual legal text before "
                    f"composing your answer:\n{id_lines}]"
                )
        except Exception:
            phase2_note = (
                "\n\n[NEXT STEP: Call search_legislation_sections with the legislation_id "
                "from this result to retrieve the actual legal text.]"
            )

    # P2.2 (B5), second source of bare negatives: a provision absent from the
    # ranked ten is not absent from the Act. 6335 turn 7 reported that a targeted
    # search "returned no results" when it had returned results, and then
    # invented a cause for it. This tool had no note of any kind before now.
    if name == "search_legislation_sections":
        try:
            _sec_data = json.loads(result)
            scope_note = section_search_note(args, _sec_data)
            record_search(search_log, name, args, _sec_data)
        except Exception:
            scope_note = ""

    # P2.3 (B3b): *made under* is the one B3 relation no endpoint returns, so the
    # only evidence of it is an instrument's own preamble — which arrives in
    # `legislation.description` on this response and nowhere else. Computed from
    # the RAW result for the same reason `provision_url_block` is: a large
    # instrument gets summarised and the summariser drops the preamble, so by
    # the time the model reads the text the evidence has gone.
    enabling_note = ""
    if name == "get_legislation_text":
        enabling_note = enabling_power_note(args, raw_result)
    record_enabling_power(search_log, name, args, raw_result)

    # P3.5 (B3): the other four relations of the bucket, which ARE retrievable.
    # Computed from the RAW result for the same reason as everything else at
    # this seam — a large change record is summarised, and a summary of a
    # relation list keeps the prose and drops the counts the block is about.
    relations_note = ""
    if name == "get_legislation_changes":
        relations_note = amendment_search_note(args, raw_result)
    record_relations(search_log, name, args, raw_result)

    # P2.5 (B4): the change record's currency-bearing counts, and `valid_date`
    # off a `/legislation/text` response. From the RAW result for the reason
    # every other recorder at this seam is — a summarised change record keeps
    # the prose and drops the counts, and a summarised instrument drops the
    # metadata block `valid_date` lives in.
    #
    # **Name-gated here rather than left to `record_currency`'s own dispatch.**
    # `record_currency` also handles `search_legislation`, and that call is made
    # further up next to `currency_note`, which needs the same parsed page. At
    # this point `raw_result` is still the executor's own output — summarisation
    # is below — so the two calls would see identical data and record the page
    # twice. One seam per tool.
    if name in ("get_legislation_changes", "get_legislation_text"):
        record_currency(search_log, name, args, raw_result)

    # P2.4 (6373): a retrieval by id that the index answered with not-found.
    # The Worker read that as proof the lawyer's citation was wrong in all three
    # reps of the pre-measurement. Stated at the result, and carried to the
    # Manager in the worker's block. Keyed on the API's own not-found detail,
    # never on the model's prose.
    not_held = not_held_note(args, raw_result)
    record_not_held(search_log, name, args, raw_result)

    from .provider_factory import get_summarise_threshold
    # Two independent triggers: this result is large on its own, OR the run has
    # accumulated enough context that even a modest addition is no longer free.
    # The second is what stops several under-threshold retrievals stacking into a
    # prefill the provider cannot start streaming inside the read timeout.
    _over_budget = (
        context_budget is not None
        and context_budget["used"] + len(result) > context_budget["limit"]
    )
    # Audit flags — what happened to the raw result on its way to the model.
    _audit_summarised = False
    _audit_local_hit = False
    _audit_truncated = False
    if len(result) > get_summarise_threshold() or _over_budget:
        if _over_budget and len(result) <= get_summarise_threshold():
            logger.info(
                f"[Worker] Context budget reached "
                f"({context_budget['used']}/{context_budget['limit']} chars) — "
                f"summarising {len(result)}-char result from '{name}' that would "
                f"otherwise pass through raw"
            )
        else:
            logger.info(
                f"[Worker] Result from '{name}' is {len(result)} chars — summarising "
                f"with model '{summarise_model}'"
            )

        doc_name = name
        try:
            result_data = json.loads(result)
            doc_name = (
                result_data.get("title")
                or result_data.get("name")
                or args.get("legislation_id")
                or name
            )
        except Exception:
            doc_name = args.get("legislation_id") or name

        summarise_id = uuid.uuid4().hex[:8]

        if parent_on_chunk:
            await call_chunk(parent_on_chunk, {
                "type": "tool_start",
                "tool": "Extracting the relevant sections from a large document",
                "id": summarise_id,
            })

        # Local prompt cache (D7): cross-user/cross-provider summary reuse,
        # exact (content_hash, canonicalised-query) match only. Flag-gated;
        # every cache operation is fail-soft (a DB error is just a miss).
        _req_cfg = get_request_provider_config()
        _local_cache_on = _req_cfg.get("_local_prompt_cache_enabled", True)
        # Cache-key query (D8 Phase 5): standard mode keys on the raw user
        # question (deterministic across models/runs) rather than the Manager's
        # paraphrased delegation brief. Deep Research leaves _cache_key_query
        # unset/empty, so each step's plan text keys as before.
        _cache_key_query = _req_cfg.get("_cache_key_query") or query
        _content_hash = None
        _cached = None
        if _local_cache_on:
            from ..services import local_prompt_cache as _local_cache
            # Cross-user safety invariant: only allowlisted (public-source)
            # tools may enter the shared cache — see local_prompt_cache docstring.
            if name not in _local_cache.CACHEABLE_TOOLS:
                _local_cache_on = False
            else:
                _content_hash = _local_cache.content_hash(result)
                _cached = await _local_cache.lookup(_content_hash, _cache_key_query)

        if _cached is not None:
            logger.info(
                f"[Worker] Local cache hit for '{name}' ({len(result)} chars) — "
                f"skipping summarisation"
            )
            # A hit is a saving, not a summarisation: no record_summarisation.
            if timing_collector:
                timing_collector.record_local_cache_hit(_cached["chars_in"] or len(result))
            result = _cached["summary"]
            _audit_summarised = True
            _audit_local_hit = True
        else:
            async def _emit_progress(msg: str) -> None:
                if parent_on_chunk:
                    await call_chunk(parent_on_chunk, {"type": "tool_start", "tool": msg})

            _chars_in = len(result)
            result, _degraded = await summarise_for_query(
                result, query, summarise_model,
                chunk_fn=chunk_fn,
                on_progress=_emit_progress,
                timing_collector=timing_collector,
                doc_name=doc_name,
                cancel_event=cancel_event,
            )
            logger.info(f"[Worker] Summarised to {len(result)} chars")

            if timing_collector:
                from .summarisation import SUMMARISE_CHUNK_CHARS
                _chunks = max(1, -(-_chars_in // SUMMARISE_CHUNK_CHARS))  # ceil division
                timing_collector.record_summarisation(_chars_in, len(result), _chunks)

            _audit_summarised = True

            # Enforce the size cap here, BEFORE the phase nudges are appended, so a
            # summary that still exceeds the threshold is trimmed without losing the
            # nudges (the chat loop's own truncation would chop them off the tail).
            threshold = get_summarise_threshold()
            _truncated = False
            if len(result) > threshold:
                logger.warning(
                    f"[Worker] Summarised result from '{name}' still exceeds threshold "
                    f"({len(result)} -> {threshold} chars)"
                )
                if timing_collector:
                    timing_collector.record_truncation()
                _truncated = True
                _audit_truncated = True
                result = (
                    result[:threshold]
                    + "\n\n[Content truncated — summary exceeded context limit]"
                )

            # Store post-cap, pre-nudge (nudges are request-contextual). Fail-soft.
            # Never store degraded (summariser fell back to raw/partial text) or
            # truncated output — it would poison the key cross-user permanently.
            if _local_cache_on and _content_hash is not None:
                if _degraded or _truncated:
                    logger.info(
                        f"[LocalCache] Not storing degraded/truncated summary for '{doc_name}'"
                    )
                else:
                    await _local_cache.store(
                        _content_hash, _cache_key_query, result,
                        summarise_model=summarise_model,
                        doc_name=str(doc_name) if doc_name else None,
                        chars_in=_chars_in,
                    )

        if parent_on_chunk:
            await call_chunk(parent_on_chunk, {
                "type": "tool_end",
                "tool": "Extracting the relevant sections from a large document",
                "id": summarise_id,
                "result": result,
            })

    # P1.6 (B14): hand the provision URLs back after summarisation. A 32K
    # section retrieval summarises to ~3.5K of prose that names the sections and
    # carries no URLs at all, so the model — forbidden from inventing one and
    # holding none — rebuilds it from the Act's base URI. Appended here for the
    # same reason the nudges are: the summariser cannot discard what it never
    # saw. Only on the summarised path; an unsummarised result already carries
    # its own `url` per row, and restating them would be noise.
    #
    # P3.11 (B10 residual): and the subsection outline, for the same reason
    # and on the same path. Measured over every stored 6348 run: the section
    # search returns s.36 with both subsections, and the summariser keeps the
    # second in 1 of 11 summaries - the Worker then describes the first alone.
    # Both blocks are appended OUTSIDE the local-cache summary, so a cache hit
    # gets them too. `summarised_result_blocks` is the one definition.
    if _audit_summarised:
        result += summarised_result_blocks(name, raw_result)

    # Append phase nudges after summarisation so they are not discarded
    # by the summariser and remain visible in the message the model receives.
    # P2.2's scope block goes on before the Phase-2 nudge, so the imperative
    # ("call search_legislation_sections with these ids") stays the last thing
    # the model reads on a productive search.
    result += scope_note
    result += not_held
    result += enabling_note
    result += relations_note
    result += phase2_note
    result += sp_phase2_note
    result += sp_committee_phase2_note
    result += sp_plenary_phase2_note
    result += hansard_phase2_note
    result += case_law_note

    if parent_on_chunk:
        await call_chunk(parent_on_chunk, {"type": "tool_end", "tool": f"Worker: {name}", "id": activity_id, "result": "Done"})

    if tool_memo is not None and memo_key is not None:
        tool_memo[memo_key] = {"raw": raw_result, "final": result}

    # Charged after the nudges are appended: what is counted is exactly what the
    # model receives, so the budget tracks the real context growth.
    if context_budget is not None:
        context_budget["used"] += len(result)

    if _audit:
        _audit.end_tool(
            _audit_tool,
            raw_result=raw_result,
            final_result=result,
            summarised=_audit_summarised,
            local_cache_hit=_audit_local_hit,
            truncated=_audit_truncated,
        )

    return result
