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
"""
import hashlib
import logging
import re
from datetime import datetime

from sqlalchemy import text

logger = logging.getLogger("app")

# Same recipe as _or_tsquery in agent/tools/parliament.py, deliberately
# reimplemented locally (plus a sort — tsquery is order-sensitive, a cache key
# is not) rather than imported from the parliament module.
_STOPWORDS = frozenset(
    "the a an of for in on to and or is are with about said has what which people use".split()
)

# On store, if the table exceeds this many rows, prune never-hit entries older
# than 90 days. Cheap hygiene only — no eviction is needed for correctness.
_PRUNE_ROW_THRESHOLD = 20_000
_PRUNE_UNUSED_DAYS = 90


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
    return hashlib.sha256(canonicalise_query(query).encode("utf-8")).hexdigest()


async def lookup(content_hash_hex: str, query: str) -> dict | None:
    """Return {"summary", "chars_in"} on an exact key match, else None.

    Bumps hit_count/last_hit_at on hit. Any failure is treated as a miss.
    """
    try:
        from ..database import async_session_maker

        async with async_session_maker() as session:
            row = (await session.execute(
                text(
                    "SELECT id, summary, chars_in FROM local_prompt_cache "
                    "WHERE content_hash = :ch AND query_hash = :qh"
                ),
                {"ch": content_hash_hex, "qh": _query_hash(query)},
            )).mappings().first()
            if row is None:
                return None
            await session.execute(
                text(
                    "UPDATE local_prompt_cache "
                    "SET hit_count = hit_count + 1, last_hit_at = :now WHERE id = :id"
                ),
                {"now": datetime.utcnow(), "id": row["id"]},
            )
            await session.commit()
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
                    "VALUES (:ch, :qh, :qt, :s, :m, :d, :ci, 0, :now) "
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
                    "now": datetime.utcnow(),
                },
            )
            total = (await session.execute(
                text("SELECT COUNT(*) FROM local_prompt_cache")
            )).scalar() or 0
            if total > _PRUNE_ROW_THRESHOLD:
                await session.execute(
                    text(
                        "DELETE FROM local_prompt_cache WHERE hit_count = 0 "
                        f"AND created_at < NOW() - INTERVAL '{_PRUNE_UNUSED_DAYS} days'"
                    )
                )
            await session.commit()
    except Exception as e:
        logger.debug(f"[LocalCache] Store failed (ignored): {e}")
