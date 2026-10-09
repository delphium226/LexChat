import asyncio
import logging
from typing import Callable, Optional

logger = logging.getLogger("agent")

# Results larger than this are summarised before being fed back to the model.
# Below this threshold the raw text is used as-is.
SUMMARISE_THRESHOLD_CHARS = 8_000

# Maximum chars sent to the LLM in a single summarisation call.
# At ~4 chars/token this is ~37K tokens — well within a 256K context window.
SUMMARISE_CHUNK_CHARS = 150_000

# Fallback: if a chunk summarisation fails, include only this many chars of the
# raw chunk so the Worker still gets some content without blowing the context.
SUMMARISE_CHUNK_FALLBACK_CHARS = 5_000

# Total chars of tool output one Worker run may accumulate before EVERY further
# result is summarised regardless of its own size (~62K tokens at ~4 chars/token).
#
# get_summarise_threshold() is a PER-RESULT cap that scales with the model's
# context window — up to 200K chars each on a 1M-token model. Nothing bounded the
# sum, so a handful of individually-under-threshold retrievals stacked into a
# prefill large enough that the provider took >180s to return response headers,
# tripping the stream read timeout and killing the request. This is the bound on
# the sum. Deliberately generous: early retrievals still arrive verbatim, and only
# the tail of a long research run is compressed.
WORKER_CONTEXT_BUDGET_CHARS = 250_000


async def call_chunk(on_chunk: Callable, data: dict) -> None:
    """Call on_chunk callback, handling both sync and async callables."""
    result = on_chunk(data)
    if asyncio.iscoroutine(result):
        await result


# P3.3 (B11), Session 32. The research question handed to the summariser is the
# Worker's brief, and a brief that asks "what interpretation legislation
# applies" was answered from the summariser's training: 6338's summaries added
# an interpretation Act that does not apply to the Act in question, to
# section-search results that never mention it. The
# Worker then reported it as "the retrieved text establishes". Re-drawn on the
# recorded raw results: 25-26 of 27 without this line, 0 of 27 with it; on 24
# other sessions' results it kept at least as many provisions. An earlier
# wording that also said "if the text does not answer, say so" stopped the
# additions too but multiplied "the text does not contain" statements about
# sixfold, a false-negative risk (Invariant 1), hence "leave out".
SUMMARY_SOURCE_RULE = (
    "Summarise only what the text below contains. Do not add any legislation, definition or "
    "rule of interpretation that is not in it, even where the research question asks for one: "
    "leave out any part of the question the text does not cover, without commenting on it."
)

# P3.16 (B11), Session 33. The source rule stopped the summariser adding an Act,
# not adding its own reading: over every stored audit, 205 summaries of
# legislation carried the summariser's inference as if it were the text's
# ("... and therefore do not fall under the definition", "(including X by
# definition)", "effectively allowing ..."), and one reached a lawyer as a
# quotation of the instrument (`tools/summary_probe glosses`). Re-drawn the same day
# on the two post-rule results where it recurred: without this line 3 of 6
# draws glossed (the recorded gloss itself in 2 of 3), with it 0 of 6; on 24
# other sessions' results, provisions kept 335 against 253 and "does not
# contain" 12 against 13. Worded, like the source rule, as what to leave out:
# a first wording ("State what each provision says; do not add your own
# reading ...") returned an empty summary for a filter-style brief, 2 of 2.
SUMMARY_GLOSS_RULE = (
    "Do not add conclusions of your own either: where the text does not itself say that a "
    "provision includes, excludes or leads to something, leave that out rather than inferring it."
)


def check_summary_citations(summary: str, source, query: str = "") -> str:
    """P3.45: the summary with every case citation its source does not hold
    removed (`utils.summary_citations.strip_unsourced_citations`, which says
    what goes and why). Run on every summary the Worker is handed: a fresh
    one here, and a local-cache hit in `run_worker_tool`, so a row stored
    before this check is checked when it is served. Fail-soft: the summary
    comes back unchanged on any error."""
    try:
        from ..utils.summary_citations import strip_unsourced_citations
        checked, removed = strip_unsourced_citations(summary, source, query)
    except Exception as e:   # Invariant 5
        logger.warning(f"[SummaryCheck] skipped: {type(e).__name__}")
        return summary
    if removed:
        actions = ", ".join(sorted({r["action"] for r in removed}))
        logger.info(f"[SummaryCheck] removed {len(removed)} case citation(s) the summarised "
                    f"text does not hold ({actions}; {len(summary) - len(checked)} chars)")
        logger.debug(f"[SummaryCheck] removed: {[r['citation'] for r in removed]}")
    return checked


def summarise_prompt(text: str, query: str) -> str:
    return (
        "You are summarising a piece of UK legislation to assist with a legal research question.\n\n"
        f"Research question: {query}\n\n"
        "Summarise the legislation text below. Retain only the sections, provisions, "
        "definitions, and legal thresholds directly relevant to the research question. "
        "Preserve exact section numbers, citations, and statutory references. "
        f"{SUMMARY_SOURCE_RULE} "
        f"{SUMMARY_GLOSS_RULE} "
        "Discard preamble, unrelated schedules, and provisions that do not bear on the question.\n\n"
        f"Legislation text:\n{text}\n\nSummary:"
    )


async def summarise_for_query(
    text: str,
    query: str,
    model: str,
    chunk_fn: Callable,
    on_progress: Optional[Callable] = None,
    timing_collector=None,
    doc_name: str = "document",
    cancel_event=None,
) -> tuple[str, bool]:
    """Produce a query-focused summary of a legislation text.

    Returns (text, degraded). degraded is True when any fallback path fired —
    a failed single-chunk call (raw text returned), any failed chunk in the
    multi-chunk path (raw head substituted), or a failed final consolidation
    (concatenated partials returned). Degraded output is still usable for the
    current request but must NOT be cached for reuse.

    chunk_fn is the provider-specific summarise_chunk callable with signature:
        async (text, query, model, *, timing_collector=None) -> Optional[str]

    Texts larger than SUMMARISE_CHUNK_CHARS are split into chunks, each
    summarised independently, then the partial summaries are combined and
    optionally consolidated in a final pass.  Falls back gracefully when
    individual chunk calls fail.

    on_progress(msg) is called before each chunk so the UI can show progress.

    cancel_event, if set, aborts before each stage so a disconnected client
    stops paying for summarisation work that will never be read.
    """
    def _check_cancel():
        if cancel_event is not None and cancel_event.is_set():
            raise asyncio.CancelledError("Aborted")

    _check_cancel()
    if len(text) <= SUMMARISE_CHUNK_CHARS:
        result = await chunk_fn(text, query, model, timing_collector=timing_collector)
        if result is None:
            logger.warning("[Summarise] Single-chunk summarisation failed, returning original text")
            return text, True
        return check_summary_citations(result, text, query), False

    # Split into chunks and summarise each.
    chunks = [
        text[i: i + SUMMARISE_CHUNK_CHARS]
        for i in range(0, len(text), SUMMARISE_CHUNK_CHARS)
    ]
    n = len(chunks)
    logger.info(f"[Summarise] {len(text)} chars exceeds chunk limit — splitting into {n} chunks")

    if on_progress:
        await on_progress(f"Searching through large document ({doc_name}) - {n} parts")

    _check_cancel()
    logger.info(f"[Summarise] Summarising {n} chunks concurrently...")
    raw_summaries = await asyncio.gather(
        *[chunk_fn(chunk, query, model, timing_collector=timing_collector) for chunk in chunks]
    )
    partial_summaries = []
    degraded = False
    for i, (summary, chunk) in enumerate(zip(raw_summaries, chunks)):
        if summary is None:
            logger.warning(
                f"[Summarise] Chunk {i + 1}/{n} failed — using first "
                f"{SUMMARISE_CHUNK_FALLBACK_CHARS} chars of chunk"
            )
            partial_summaries.append(chunk[:SUMMARISE_CHUNK_FALLBACK_CHARS])
            degraded = True
        else:
            partial_summaries.append(summary)

    combined = "\n\n---\n\n".join(partial_summaries)
    logger.info(f"[Summarise] Combined {n} partial summaries into {len(combined)} chars")

    # If the combined summaries are still large, do one final consolidation pass.
    if len(combined) > SUMMARISE_CHUNK_CHARS:
        _check_cancel()
        if on_progress:
            await on_progress("Consolidating extracted sections")
        logger.info("[Summarise] Running final consolidation pass")
        final = await chunk_fn(combined, query, model, timing_collector=timing_collector)
        if final is None:
            logger.warning("[Summarise] Final consolidation failed — returning combined partials")
            return check_summary_citations(combined, text, query), True
        logger.info(f"[Summarise] Consolidated to {len(final)} chars")
        return check_summary_citations(final, text, query), degraded

    return check_summary_citations(combined, text, query), degraded
