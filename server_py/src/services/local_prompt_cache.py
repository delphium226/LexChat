"""Local prompt cache — cross-user, cross-provider Worker summary cache (D7).

Caches `summarise_for_query` outputs keyed on
(sha256 of the raw oversized tool result, sha256 of the canonicalised query).
Exact canonicalised match only — NO embeddings, similarity thresholds, or fuzzy
matching of any kind; that constraint is the design (semantic near-miss reuse
risks silent incompleteness). `summarise_model` is stored for provenance but is
deliberately NOT part of the key, which is what makes the cache cross-provider.

Every operation is fail-soft: a DB error must never break a research request —
lookup errors return None (a miss), store errors are logged and swallowed.
See docs/LOCAL_PROMPT_CACHE_PLAN.md.

Key-query source (D8 Phase 5): in standard research mode the key query is the
RAW user question (stashed as _cache_key_query in the request provider config),
not the Manager's LLM-paraphrased delegation brief — briefs vary per model/run,
making cross-user hits luck. Deep Research keys on each step's approved plan
text (deterministic already; steps with different intents must not collide).
Known residual risk (documented, not solved): if the Manager delegates twice in
one request with different sub-aspects and both retrieve byte-identical text,
the second reuses the first's summary despite a different intent. In practice
section retrievals vary text with the query (different intent → different
content_hash), so the exposure is mostly query-independent full-document
retrievals (get_case_law_text); the one-delegation rule makes multi-delegation
rare, and the summary was produced for this user's question in the common case.
If it proves harmful, revert to brief-keying — a one-line change in
agent_shared.py.
"""
import hashlib
import logging
import random
import re

from sqlalchemy import text

logger = logging.getLogger("app")

# Same recipe as _or_tsquery in agent/tools/parliament.py, deliberately
# reimplemented locally (plus a sort — tsquery is order-sensitive, a cache key
# is not) rather than imported from the parliament module.
_STOPWORDS = frozenset(
    "the a an of for in on to and or is are with about said has what which people use".split()
)

# On store, if the table exceeds this many rows, prune never-hit entries older
# than 90 days and any row (hits or not) idle for over a year — amended
# legislation strands old-content-hash rows forever otherwise. Cheap hygiene
# only — no eviction is needed for correctness, so the count-and-prune check
# is only sampled on ~2% of stores (the 20K threshold is soft).
_PRUNE_ROW_THRESHOLD = 20_000
_PRUNE_UNUSED_DAYS = 90
_PRUNE_IDLE_DAYS = 365
_PRUNE_SAMPLE_RATE = 0.02

# Bump this on ANY change to canonicalise_query or _STOPWORDS — it is baked
# into every stored query_hash, so bumping is an explicit full-cache
# invalidation (old rows become unreachable and age out via the prune).
_CANON_VERSION = "v1"


def canonicalise_query(query: str) -> str:
    """Collapse trivial wording variants of a query to one canonical string.

    lowercase → tokenise [a-z0-9]+ → drop tokens <=2 chars and stopwords →
    dedup → sort → join with single spaces. Purely lexical — two queries map to
    the same key only if they contain the same significant words.
    """
    tokens = {
        tok
        for tok in re.findall(r"[a-z0-9]+", query.lower())
        if len(tok) > 2 and tok not in _STOPWORDS
    }
    return " ".join(sorted(tokens))


def content_hash(raw_result: str) -> str:
    """sha256 hex of the raw pre-summarisation result string (the safety gate:
    identical hash ⇒ identical retrieved text ⇒ staleness impossible)."""
    return hashlib.sha256(raw_result.encode("utf-8")).hexdigest()


def _query_hash(query: str) -> str:
    return hashlib.sha256(
        f"{_CANON_VERSION}|{canonicalise_query(query)}".encode("utf-8")
    ).hexdigest()


async def lookup(content_hash_hex: str, query: str) -> dict | None:
    """Return {"summary", "chars_in"} on an exact key match, else None.

    Bumps hit_count/last_hit_at on hit — atomically, in the same statement as
    the read (UPDATE ... RETURNING). Any failure is treated as a miss.
    """
    try:
        from ..database import async_session_maker

        async with async_session_maker() as session:
            row = (await session.execute(
                text(
                    "UPDATE local_prompt_cache "
                    "SET hit_count = hit_count + 1, last_hit_at = NOW() "
                    "WHERE content_hash = :ch AND query_hash = :qh "
                    "RETURNING summary, chars_in"
                ),
                {"ch": content_hash_hex, "qh": _query_hash(query)},
            )).mappings().first()
            await session.commit()
            if row is None:
                return None
            return {"summary": row["summary"], "chars_in": int(row["chars_in"] or 0)}
    except Exception as e:
        logger.debug(f"[LocalCache] Lookup failed (treated as miss): {e}")
        return None


async def store(
    content_hash_hex: str,
    query: str,
    summary: str,
    summarise_model: str | None = None,
    doc_name: str | None = None,
    chars_in: int | None = None,
) -> None:
    """Insert a summary; concurrent double-stores race harmlessly (DO NOTHING)."""
    try:
        from ..database import async_session_maker

        async with async_session_maker() as session:
            await session.execute(
                text(
                    "INSERT INTO local_prompt_cache "
                    "(content_hash, query_hash, query_text, summary, summarise_model, "
                    " doc_name, chars_in, hit_count, created_at) "
                    "VALUES (:ch, :qh, :qt, :s, :m, :d, :ci, 0, NOW()) "
                    "ON CONFLICT (content_hash, query_hash) DO NOTHING"
                ),
                {
                    "ch": content_hash_hex,
                    "qh": _query_hash(query),
                    "qt": query,
                    "s": summary,
                    "m": summarise_model,
                    "d": doc_name,
                    "ci": chars_in,
                },
            )
            # Hygiene sampling, not correctness — a full COUNT(*) on every
            # store is wasteful, and the 20K threshold is soft.
            if random.random() < _PRUNE_SAMPLE_RATE:
                total = (await session.execute(
                    text("SELECT COUNT(*) FROM local_prompt_cache")
                )).scalar() or 0
                if total > _PRUNE_ROW_THRESHOLD:
                    await session.execute(
                        text(
                            "DELETE FROM local_prompt_cache "
                            f"WHERE (hit_count = 0 AND created_at < NOW() - INTERVAL '{_PRUNE_UNUSED_DAYS} days') "
                            f"OR (COALESCE(last_hit_at, created_at) < NOW() - INTERVAL '{_PRUNE_IDLE_DAYS} days')"
                        )
                    )
            await session.commit()
    except Exception as e:
        logger.debug(f"[LocalCache] Store failed (ignored): {e}")
