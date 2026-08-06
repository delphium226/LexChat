"""Drafting-guidance corpus admin endpoints (S2).

One-shot, admin-triggered ingest of *Drafting Matters!* plus a corpus-stats read.
There is deliberately **no crawler and no background task** here: the guidance is
near-static (2016 and 2018 editions), so re-running the ingest is a manual act.

The retrieval tool (`search_drafting_guidance`) is S3 and does not live here.
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import get_admin_user
from ..services.drafting_ingest import SOURCE, ingest_drafting_matters

logger = logging.getLogger("app")

router = APIRouter(prefix="/api/drafting", tags=["Drafting"])

# Admin-only by default, following the developer.py convention: a route added
# here later cannot accidentally ship unauthenticated.
admin_router = APIRouter(dependencies=[Depends(get_admin_user)])


@admin_router.post("/ingest")
async def ingest_guidance():
    """Fetch, chunk and store *Drafting Matters!*. Idempotent — safe to re-run.

    Returns the numbers BUILD_PLAN's verification step asks for: row count and
    mean `full_text` length. A mean in the thousands-of-characters range means
    the chunker has regressed to whole-chapter (or whole-document) rows.
    """
    stats = await ingest_drafting_matters()
    return stats


@admin_router.get("/corpus")
async def corpus_stats(db: AsyncSession = Depends(get_db)):
    """Row count, mean/min/max `full_text` length, and a per-part breakdown."""
    overall = (await db.execute(text(
        "SELECT COUNT(*) AS rows, "
        "       COALESCE(AVG(LENGTH(full_text)), 0) AS mean_chars, "
        "       COALESCE(MIN(LENGTH(full_text)), 0) AS min_chars, "
        "       COALESCE(MAX(LENGTH(full_text)), 0) AS max_chars "
        "FROM drafting_guidance WHERE source = :s"
    ), {"s": SOURCE})).mappings().one()

    by_part = (await db.execute(text(
        "SELECT part, COUNT(*) AS rows, "
        "       COALESCE(AVG(LENGTH(full_text)), 0) AS mean_chars "
        "FROM drafting_guidance WHERE source = :s "
        "GROUP BY part ORDER BY rows DESC"
    ), {"s": SOURCE})).mappings().all()

    return {
        "source": SOURCE,
        "rows": overall["rows"],
        "mean_full_text_chars": round(float(overall["mean_chars"]), 1),
        "min_full_text_chars": overall["min_chars"],
        "max_full_text_chars": overall["max_chars"],
        "by_part": [
            {
                "part": r["part"],
                "rows": r["rows"],
                "mean_full_text_chars": round(float(r["mean_chars"]), 1),
            }
            for r in by_part
        ],
    }


router.include_router(admin_router)
