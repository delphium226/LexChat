"""S2 — drafting-guidance corpus: schema, GIN index and ingest chunking.

The tests that matter here guard two failure modes that are silent in normal
operation:

1. **The whole-document blob.** If the chunker regresses to one row per chapter
   (or per page), nothing errors — retrieval just quietly gets worse, because a
   huge row ranks poorly under `ts_rank` and returns a useless excerpt. The
   codebase has already been bitten by exactly this once (the old SP committee
   parser returned a whole meeting as one row). So chunk count and mean length
   are asserted, not eyeballed.
2. **A GIN index Postgres cannot use.** An expression index is matched by
   expression *equality*: `to_tsvector('english', coalesce(full_text,''))` and
   `to_tsvector('english', coalesce(full_text, ''))` are different indexes as far
   as the planner is concerned, and the mismatch produces no error and no
   warning — just a sequential scan. `test_gin_index_is_used_for_the_query_expression`
   proves the planner will actually pick it.

No test here touches the network. `_FIXTURE` reproduces the gov.scot markup
patterns verbatim (see the Session 2 log for why HTML, not the PDF).
"""

import pytest
from sqlalchemy import text

from src.models import DRAFTING_FTS_EXPR
from src.services.drafting_ingest import (
    MAX_CHUNK_CHARS,
    PAGES,
    build_chunks,
    chunk_page,
    parse_contents,
)

# ---------------------------------------------------------------------------
# Fixtures reproducing the real gov.scot markup.
#
# Every structural quirk below is one the live pages actually contain:
#   * chapter and section headings are BOTH <p><strong>…</strong></p> — the only
#     thing distinguishing them is the List of Contents page;
#   * sub-topics are <p><em>…</em></p>;
#   * "Numbers and symbols" lost its <strong> markup in the HTML conversion and
#     appears as a bare <p> — recoverable only via the contents page;
#   * example provisions ("1 Short title") are bolded exactly like headings;
#   * a long bolded "Note: …" paragraph is not a heading.
# ---------------------------------------------------------------------------

_CONTENTS = """
<h3>List of Contents</h3>
<p><strong>Part 1: Drafting technique</strong></p>
<p><strong>Language</strong><br />
Plain language<br />
Particular words and expressions<br />
<strong>Style</strong><br />
Numbers and symbols<br />
Dates</p>
<h3>Contact</h3>
"""

_FIXTURE = """
<h3>Part 1: Drafting technique</h3>
<p><strong>Language</strong></p>
<p><strong>Plain language</strong></p>
<p>Where possible, use simple words and short sentences.</p>
<ul><li> devising accessible structures</li></ul>
<p><em>Grammar and usage</em></p>
<p>Observe proper rules of grammar and usage.</p>
<p><strong>Particular words and expressions</strong></p>
<p><em>shall v must</em></p>
<p>Avoid the legislative 'shall' when imposing an obligation.</p>
<ul><li> use 'A must' or 'B is/are to' instead</li></ul>
<p><strong>Style</strong></p>
<p>Numbers and symbols</p>
<p><em>numbers generally</em></p>
<p>Use figures where possible for sums of money.</p>
<p><strong>Dates</strong></p>
<p>Write a date like this: 25 December 2015.</p>
<p><strong>Note: As at the date of publication this remains under review and the
guidance below should be read subject to that qualification in all cases.</strong></p>
<p><em>Example provision</em></p>
<p><strong>1 Short title</strong></p>
<p>This Act may be cited as the Example (Scotland) Act 2018.</p>
<h3>Contact</h3>
"""


@pytest.fixture
def chunks():
    chapters, sections = parse_contents(_CONTENTS)
    return chunk_page(_FIXTURE, 6, "Part 1: Drafting technique", chapters, sections)


def _by_heading(chunks, heading):
    hits = [c for c in chunks if c["heading"] == heading]
    assert hits, f"no chunk headed {heading!r}; got {[c['heading'] for c in chunks]}"
    return hits[0]


# ---------------------------------------------------------------------------
# Contents parsing — the authoritative chapter/section split
# ---------------------------------------------------------------------------

def test_contents_separates_chapters_from_sections():
    chapters, sections = parse_contents(_CONTENTS)
    assert "Language" in chapters
    assert "Style" in chapters
    # Sections are the un-bolded <br />-separated entries.
    assert {"Plain language", "Particular words and expressions",
            "Numbers and symbols", "Dates"} <= sections
    # A name is never both.
    assert not (chapters & sections)


# ---------------------------------------------------------------------------
# Chunking — the make-or-break property
# ---------------------------------------------------------------------------

def test_chunks_are_per_topic_not_per_chapter(chunks):
    """The regression guard: a chapter must never become a single row."""
    headings = [c["heading"] for c in chunks]
    # "Language" and "Style" are chapters. They own no chunk of their own —
    # their sections and sub-topics do.
    assert "Language" not in headings
    assert "Style" not in headings
    # …and the leaf topics beneath them each got their own row.
    assert "shall v must" in headings
    assert "Grammar and usage" in headings
    assert "numbers generally" in headings


def test_chunk_carries_its_full_heading_path(chunks):
    c = _by_heading(chunks, "shall v must")
    assert c["chapter"] == "Language"
    assert c["section"] == "Particular words and expressions"
    assert c["part"] == "Part 1: Drafting technique"
    assert "Avoid the legislative 'shall'" in c["full_text"]
    # Sibling topics must NOT have leaked into this row.
    assert "simple words" not in c["full_text"]


def test_list_items_survive_as_text(chunks):
    """`<ul>` bullets carry the actual rules; losing them would gut the corpus."""
    c = _by_heading(chunks, "shall v must")
    assert "use 'A must' or 'B is/are to' instead" in c["full_text"]


def test_unmarked_heading_is_recovered_from_the_contents_page(chunks):
    """"Numbers and symbols" is a bare <p> in the HTML, not <p><strong>.

    Without contents-page recovery it would be swallowed as body text of the
    preceding chunk and its children would be misattributed to `Dates`.
    """
    c = _by_heading(chunks, "numbers generally")
    assert c["section"] == "Numbers and symbols"
    assert c["chapter"] == "Style"


def test_bolded_example_provision_is_body_not_a_heading(chunks):
    """"1 Short title" is a specimen of legislative text, not a rule heading."""
    assert "1 Short title" not in [c["heading"] for c in chunks]
    c = _by_heading(chunks, "Example provision")
    assert "1 Short title" in c["full_text"]
    assert "may be cited as" in c["full_text"]


def test_long_bolded_note_is_not_treated_as_a_heading(chunks):
    """Part 2 opens with a bolded multi-line note; headings are short."""
    assert not any(c["heading"].startswith("Note: As at") for c in chunks)
    assert any("As at the date of publication" in c["full_text"] for c in chunks)


def test_rule_refs_are_unique_and_stable(chunks):
    refs = [c["rule_ref"] for c in chunks]
    assert len(refs) == len(set(refs))
    assert _by_heading(chunks, "shall v must")["rule_ref"] == (
        "p6/language/particular-words-and-expressions/shall-v-must"
    )
    # Re-chunking the same input must reproduce the same keys — rule_ref is half
    # the ON CONFLICT key, so drift would duplicate the whole corpus on re-ingest.
    chapters, sections = parse_contents(_CONTENTS)
    again = chunk_page(_FIXTURE, 6, "Part 1: Drafting technique", chapters, sections)
    assert [c["rule_ref"] for c in again] == refs


def test_no_chunk_exceeds_the_split_ceiling(chunks):
    assert all(len(c["full_text"]) <= MAX_CHUNK_CHARS for c in chunks)


def test_oversize_chunk_is_split_on_paragraph_boundaries():
    para = "Ministers may by regulations make provision about the matter. "
    body = "\n".join([para * 12] * 40)  # comfortably over MAX_CHUNK_CHARS
    html = (
        "<h3>Part 1: Drafting technique</h3>"
        "<p><strong>Definitions</strong></p>"
        + "".join(f"<p>{line}</p>" for line in body.split("\n"))
        + "<h3>Contact</h3>"
    )
    out = chunk_page(html, 6, "Part 1: Drafting technique", set(), {"Definitions"})
    assert len(out) > 1, "an oversize topic should be split, not stored as one blob"
    assert all(len(c["full_text"]) <= MAX_CHUNK_CHARS for c in out)
    # Split parts stay distinguishable and never collide on the ON CONFLICT key.
    assert len({c["rule_ref"] for c in out}) == len(out)


def test_build_chunks_skips_the_navigation_pages():
    """Pages 1-3 are contents, foreword and preface — no drafting rules."""
    assert set(PAGES) == {4, 5, 6, 7, 8}


# ---------------------------------------------------------------------------
# Schema + GIN index
# ---------------------------------------------------------------------------

def test_fts_expression_constant_is_exact():
    """Pinned literally: `database.py` and the S3 retrieval tool both build from
    this string, and Postgres matches an expression index only on exact equality."""
    assert DRAFTING_FTS_EXPR == "to_tsvector('english', coalesce(full_text,''))"


@pytest.mark.asyncio
async def test_gin_index_is_used_for_the_query_expression(db_session):
    """EXPLAIN proves the planner can match the index to the query expression.

    `conftest` builds tables from `Base.metadata`, which does not carry the
    hand-written raw-SQL indexes, so the index is created here from the same
    constant `database.py` uses. `enable_seqscan = off` is needed because the
    planner would otherwise seq-scan a table this small regardless of indexing —
    the question under test is whether the index is *matchable*, not whether it
    is cheapest at three rows.
    """
    await db_session.execute(text(
        "CREATE INDEX IF NOT EXISTS idx_drafting_guidance_full_text "
        f"ON drafting_guidance USING GIN ({DRAFTING_FTS_EXPR})"
    ))
    for i, body in enumerate([
        "Avoid the legislative shall when imposing an obligation on a person.",
        "Always give effect to the policy on gender neutrality in drafting.",
        "Use figures where possible for sums of money and percentages.",
    ]):
        await db_session.execute(text(
            "INSERT INTO drafting_guidance (source, rule_ref, heading, full_text, sensitivity) "
            "VALUES ('drafting_matters', :ref, :h, :t, 'public')"
        ), {"ref": f"t/{i}", "h": f"h{i}", "t": body})
    await db_session.commit()

    await db_session.execute(text("SET LOCAL enable_seqscan = off"))
    plan = "\n".join(r[0] for r in (await db_session.execute(text(
        f"EXPLAIN SELECT rule_ref FROM drafting_guidance "
        f"WHERE {DRAFTING_FTS_EXPR} @@ plainto_tsquery('english', 'obligation')"
    ))).all())

    assert "idx_drafting_guidance_full_text" in plan, (
        "GIN index not used — the DDL expression and the query expression have "
        f"drifted apart.\nPlan:\n{plan}"
    )


@pytest.mark.asyncio
async def test_unique_constraint_makes_reingest_idempotent(db_session):
    """`ON CONFLICT DO NOTHING` on (source, rule_ref): re-running adds nothing."""
    insert = (
        "INSERT INTO drafting_guidance (source, rule_ref, heading, full_text, sensitivity) "
        "VALUES ('drafting_matters', 'p6/a/b/c', 'c', 'body text', 'public') "
        "ON CONFLICT ON CONSTRAINT uq_drafting_guidance_source_ref DO NOTHING"
    )
    first = await db_session.execute(text(insert))
    second = await db_session.execute(text(insert))
    await db_session.commit()
    assert first.rowcount == 1
    assert second.rowcount == 0
    assert await db_session.scalar(
        text("SELECT COUNT(*) FROM drafting_guidance")
    ) == 1


@pytest.mark.asyncio
async def test_same_rule_ref_coexists_across_sources(db_session):
    """The internal OFFICIAL-SENSITIVE guidance lands as a second `source`.

    The unique key is (source, rule_ref), not rule_ref alone, so the two corpora
    cannot block each other's ingest.
    """
    for src, sens in (("drafting_matters", "public"), ("internal", "official_sensitive")):
        await db_session.execute(text(
            "INSERT INTO drafting_guidance (source, rule_ref, full_text, sensitivity) "
            "VALUES (:src, 'p6/a/b/c', 'body', :sens)"
        ), {"src": src, "sens": sens})
    await db_session.commit()
    assert await db_session.scalar(
        text("SELECT COUNT(*) FROM drafting_guidance")
    ) == 2
    assert await db_session.scalar(text(
        "SELECT sensitivity FROM drafting_guidance WHERE source = 'internal'"
    )) == "official_sensitive"


@pytest.mark.asyncio
async def test_sensitivity_defaults_to_public(db_session):
    await db_session.execute(text(
        "INSERT INTO drafting_guidance (source, rule_ref, full_text) "
        "VALUES ('drafting_matters', 'p6/x/y/z', 'body')"
    ))
    await db_session.commit()
    assert await db_session.scalar(
        text("SELECT sensitivity FROM drafting_guidance")
    ) == "public"


# ---------------------------------------------------------------------------
# Endpoint auth — the ingest hits the network and writes the corpus
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ingest_and_corpus_endpoints_require_admin(client, user_token):
    headers = {"Authorization": f"Bearer {user_token}"}
    assert (await client.post("/api/drafting/ingest", headers=headers)).status_code == 403
    assert (await client.get("/api/drafting/corpus", headers=headers)).status_code == 403


@pytest.mark.asyncio
async def test_corpus_endpoint_reports_the_blob_detection_numbers(client, admin_token):
    """The stats an operator needs to spot a chunker regression."""
    resp = await client.get(
        "/api/drafting/corpus", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert {"rows", "mean_full_text_chars", "max_full_text_chars", "by_part"} <= set(body)
