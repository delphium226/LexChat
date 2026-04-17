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


async def call_chunk(on_chunk: Callable, data: dict) -> None:
    """Call on_chunk callback, handling both sync and async callables."""
    result = on_chunk(data)
    if asyncio.iscoroutine(result):
        await result


def summarise_prompt(text: str, query: str) -> str:
    return (
        "You are summarising a piece of UK legislation to assist with a legal research question.\n\n"
        f"Research question: {query}\n\n"
        "Summarise the legislation text below. Retain only the sections, provisions, "
        "definitions, and legal thresholds directly relevant to the research question. "
        "Preserve exact section numbers, citations, and statutory references. "
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
) -> str:
    """Produce a query-focused summary of a legislation text.

    chunk_fn is the provider-specific summarise_chunk callable with signature:
        async (text, query, model, *, timing_collector=None) -> Optional[str]

    Texts larger than SUMMARISE_CHUNK_CHARS are split into chunks, each
    summarised independently, then the partial summaries are combined and
    optionally consolidated in a final pass.  Falls back gracefully when
    individual chunk calls fail.

    on_progress(msg) is called before each chunk so the UI can show progress.
    """
    if len(text) <= SUMMARISE_CHUNK_CHARS:
        result = await chunk_fn(text, query, model, timing_collector=timing_collector)
        if result is None:
            logger.warning("[Summarise] Single-chunk summarisation failed, returning original text")
            return text
        return result

    # Split into chunks and summarise each.
    chunks = [
        text[i: i + SUMMARISE_CHUNK_CHARS]
        for i in range(0, len(text), SUMMARISE_CHUNK_CHARS)
    ]
    n = len(chunks)
    logger.info(f"[Summarise] {len(text)} chars exceeds chunk limit — splitting into {n} chunks")

    if on_progress:
        await on_progress(f"Searching through large document ({doc_name}) - {n} parts")

    logger.info(f"[Summarise] Summarising {n} chunks concurrently...")
    raw_summaries = await asyncio.gather(
        *[chunk_fn(chunk, query, model, timing_collector=timing_collector) for chunk in chunks]
    )
    partial_summaries = []
    for i, (summary, chunk) in enumerate(zip(raw_summaries, chunks)):
        if summary is None:
            logger.warning(
                f"[Summarise] Chunk {i + 1}/{n} failed — using first "
                f"{SUMMARISE_CHUNK_FALLBACK_CHARS} chars of chunk"
            )
            partial_summaries.append(chunk[:SUMMARISE_CHUNK_FALLBACK_CHARS])
        else:
            partial_summaries.append(summary)

    combined = "\n\n---\n\n".join(partial_summaries)
    logger.info(f"[Summarise] Combined {n} partial summaries into {len(combined)} chars")

    # If the combined summaries are still large, do one final consolidation pass.
    if len(combined) > SUMMARISE_CHUNK_CHARS:
        if on_progress:
            await on_progress("Consolidating extracted sections")
        logger.info("[Summarise] Running final consolidation pass")
        final = await chunk_fn(combined, query, model, timing_collector=timing_collector)
        if final is None:
            logger.warning("[Summarise] Final consolidation failed — returning combined partials")
            return combined
        logger.info(f"[Summarise] Consolidated to {len(final)} chars")
        return final

    return combined
