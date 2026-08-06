"""One-shot ingest of *Drafting Matters!* (Scottish Government PCO, 2nd ed. 2018).

**Not a crawler.** The guidance is near-static (one edition in 2016, one in 2018), so
none of `parliament_crawler.py`'s high-water-mark / trailing-delta / Cloudflare-524
machinery applies. This is an admin-triggered, idempotent, run-it-and-forget ingest:
`INSERT ... ON CONFLICT DO NOTHING` on `(source, rule_ref)`.

Source: the gov.scot **HTML** pages, not the PDF. See `docs/drafting/BUILD_PLAN.md`
and the Session 2 log entry for the reasoning — briefly, the PDF is a designed
publication whose pull-quotes interleave into body sentences under `pdfplumber`, and
which flattens every heading level to an indistinguishable bare line. The HTML encodes
a real two-level hierarchy (`<p><strong>` = chapter/section, `<p><em>` = sub-topic)
which is exactly what per-rule chunking needs.

**Chunking is the make-or-break decision here** (BUILD_PLAN, Risks): one row per
*named topic*, never per chapter. A whole-chapter row ranks poorly under `ts_rank` and
returns a useless excerpt — the same defect the old SP committee parser had.
"""

from __future__ import annotations

import html as _html
import json
import logging
import re
from datetime import date, datetime

import httpx
from sqlalchemy import text

from ..database import async_session_maker

logger = logging.getLogger("app")

BASE_URL = "https://www.gov.scot/publications/drafting-matters/pages/{n}/"

#: Publication date of the 2nd edition. Stored on every row so a future edition
#: can be distinguished without re-deriving it from the text.
VERSION_DATE = date(2018, 12, 1)

SOURCE = "drafting_matters"

#: Page number -> the `part` label recorded on every chunk from that page.
#: Pages 1-3 are the contents list, foreword and preface: navigation and
#: ceremony, no drafting rules, deliberately not ingested.
PAGES = {
    4: "Introductory matters",
    5: "Introductory matters",
    6: "Part 1: Drafting technique",
    7: "Part 2: Guidance on specific topics",
    8: "References and glossary",
}

#: A chunk longer than this is split on paragraph boundaries. Only the handful of
#: "compilation of all model provisions" blocks reach it; the guard exists so a
#: single outlier cannot reintroduce the whole-document-blob failure mode.
MAX_CHUNK_CHARS = 6000

#: Headings are short. Anything longer is a bolded *note*, not a heading —
#: Part 2 opens with one ("Note: As at the date of publication, section 16 …").
MAX_HEADING_CHARS = 120

_BLOCK = re.compile(r"<(p|ul|ol|blockquote|table)\b.*?</\1>", re.S | re.I)
_TAG = re.compile(r"<[^>]+>")
#: An *example provision* is bolded exactly like a heading but is body text. They
#: open with a numeral ("1 Short title", "50A Form of ballot papers") or a quote.
_EXAMPLE_PROVISION = re.compile(r"^[\d'\"‘’“”]")
#: Part 2's chapters are roman-numbered ("I. Arbitration", "II. Criminal law …").
_ROMAN_CHAPTER = re.compile(r"^[IVXL]+\.\s")


def _strip_html(fragment: str) -> str:
    """HTML fragment -> plain text, keeping list structure as '- ' bullets."""
    s = re.sub(r"<li\b[^>]*>", "\n- ", fragment, flags=re.I)
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"</(p|div|blockquote|tr|h\d)>", "\n", s, flags=re.I)
    s = _TAG.sub("", s)
    s = _html.unescape(s)
    s = re.sub(r"[ \t\xa0]+", " ", s)
    s = re.sub(r" *\n *", "\n", s)
    return re.sub(r"\n{2,}", "\n", s).strip()


def _slug(value: str, limit: int = 60) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", _html.unescape(value).lower()).strip("-")
    return s[:limit].strip("-") or "x"


def _page_body(page_html: str) -> str:
    """The content region: everything between the page <h3> and the 'Contact' <h3>."""
    m = re.search(r"<h3[^>]*>.*?</h3>(.*?)<h3", page_html, re.S)
    return m.group(1) if m else ""


def _heading_of(block: str) -> tuple[str, str] | None:
    """(level, text) if `block` is a heading paragraph, else None.

    Level is 'strong' (chapter or section) or 'em' (sub-topic / leaf rule).
    """
    m = re.fullmatch(
        r"<p>\s*(?:<strong>(?P<s>.*?)</strong>|<em>(?P<e>.*?)</em>)\s*"
        r"(?:<br\s*/?>|<em>\s*</em>|\s)*</p>",
        block, re.S | re.I,
    )
    if not m:
        return None
    txt = _strip_html(m.group("s") if m.group("s") is not None else m.group("e"))
    if not txt or len(txt) > MAX_HEADING_CHARS or "\n" in txt:
        return None
    return ("strong" if m.group("s") is not None else "em"), txt


def parse_contents(contents_html: str) -> tuple[set[str], set[str]]:
    """Authoritative (chapters, sections) from the List of Contents page.

    The contents page is the only place the chapter/section split is stated
    unambiguously: entries are `<br />`-separated inside one `<p>`, and chapter
    entries are wrapped in `<strong>`. Deriving the hierarchy from it beats
    guessing at it in the body, and it also recovers headings whose `<strong>`
    markup is missing in the body (e.g. "Numbers and symbols").
    """
    body = _page_body(contents_html)
    chapters: set[str] = set()
    sections: set[str] = set()
    for block in _BLOCK.finditer(body):
        frag = block.group(0)
        for strong in re.finditer(r"<strong>(.*?)</strong>", frag, re.S):
            lines = [ln.strip() for ln in _strip_html(strong.group(1)).split("\n") if ln.strip()]
            # gov.scot sometimes leaves a <strong> open across several <br />-separated
            # entries, so a multi-line span does not reliably mean "these are all
            # chapters". Only an unambiguous single-line span promotes to chapter;
            # the rest fall through to sections. That bias is deliberate: a chapter
            # misread as a section still gets its own chunk, whereas a section
            # misread as a chapter loses its heading.
            target = chapters if len(lines) == 1 else sections
            for t in lines:
                if len(t) <= MAX_HEADING_CHARS:
                    target.add(t)
        # Remove the chapter spans, then treat each <br />-separated line as a section.
        rest = re.sub(r"<strong>.*?</strong>", "\n", frag, flags=re.S)
        for line in _strip_html(rest).split("\n"):
            t = line.lstrip("- ").strip()
            if t and len(t) <= MAX_HEADING_CHARS:
                sections.add(t)
    return chapters, sections - chapters


def _split_oversize(body_text: str) -> list[str]:
    """Split an over-long chunk on paragraph boundaries, never mid-paragraph."""
    if len(body_text) <= MAX_CHUNK_CHARS:
        return [body_text]
    parts, cur = [], ""
    for para in body_text.split("\n"):
        if cur and len(cur) + len(para) + 1 > MAX_CHUNK_CHARS:
            parts.append(cur)
            cur = para
        else:
            cur = f"{cur}\n{para}" if cur else para
    if cur:
        parts.append(cur)
    return parts


def chunk_page(
    page_html: str,
    page_no: int,
    part_label: str,
    chapters: set[str],
    sections: set[str],
) -> list[dict]:
    """Split one gov.scot page into one row per named topic.

    Walks the block sequence, maintaining (chapter, section) as headings go by and
    emitting a chunk per heading. A heading with no body of its own (a chapter
    introducing its first section) emits nothing.
    """
    body = _page_body(page_html)
    url = BASE_URL.format(n=page_no)
    blocks = [m.group(0) for m in _BLOCK.finditer(body)]

    chunks: list[dict] = []
    chapter: str | None = None
    section: str | None = None
    heading: str | None = None
    buf: list[str] = []

    def flush() -> None:
        nonlocal buf
        joined = "\n".join(buf).strip()
        buf = []
        if not joined:
            return
        title = heading or section or chapter or part_label
        for i, piece in enumerate(_split_oversize(joined)):
            chunks.append({
                "part": part_label,
                "chapter": chapter,
                "section": section,
                "heading": title,
                "full_text": piece,
                "url": url,
                "_key": [chapter, section, title, i],
            })

    for i, block in enumerate(blocks):
        h = _heading_of(block)
        plain = _strip_html(block)

        # Recover headings whose <strong> markup is missing in the body but which
        # the contents page names (e.g. "Numbers and symbols").
        if h is None and re.fullmatch(r"<p>\s*[^<]+\s*</p>", block, re.S) and plain in sections:
            h = ("strong", plain)

        if h and h[0] == "strong" and _EXAMPLE_PROVISION.match(h[1]) and h[1] not in sections:
            h = None  # a bolded example provision — body text, not a heading

        if h:
            level, txt = h
            flush()
            if level == "strong":
                is_chapter = txt in chapters or bool(_ROMAN_CHAPTER.match(txt))
                if not is_chapter and txt not in sections:
                    # Unlisted bold heading: a chapter iff the next block is also a
                    # heading, i.e. it introduces a section rather than prose.
                    nxt = _heading_of(blocks[i + 1]) if i + 1 < len(blocks) else None
                    is_chapter = bool(nxt and nxt[0] == "strong")
                if is_chapter:
                    chapter, section, heading = txt, None, None
                else:
                    section, heading = txt, txt
            else:
                heading = txt
            continue

        if plain:
            buf.append(plain)

    flush()

    # rule_ref must be stable across re-runs (it is half the ON CONFLICT key) and
    # unique within the source. Build it from the heading path, then disambiguate
    # repeats — "Example provision" recurs under many sections.
    seen: dict[str, int] = {}
    out = []
    for c in chunks:
        ch, sec, head, part_i = c.pop("_key")
        base = "/".join([
            f"p{page_no}",
            _slug(ch or part_label, 40),
            _slug(sec or "", 40),
            _slug(head, 60),
        ])
        ref = f"{base}#{part_i + 1}" if part_i else base
        n = seen.get(ref, 0)
        seen[ref] = n + 1
        c["rule_ref"] = ref if not n else f"{ref}~{n + 1}"
        out.append(c)
    return out


async def fetch_pages(client: httpx.AsyncClient) -> dict[int, str]:
    """Fetch the contents page plus every ingested page."""
    wanted = sorted({1, *PAGES})
    out: dict[int, str] = {}
    for n in wanted:
        resp = await client.get(BASE_URL.format(n=n))
        resp.raise_for_status()
        resp.encoding = "utf-8"  # gov.scot serves UTF-8; do not let httpx guess
        out[n] = resp.text
    return out


def build_chunks(pages: dict[int, str]) -> list[dict]:
    """Contents page + content pages -> the full list of rows to insert."""
    chapters, sections = parse_contents(pages[1])
    chunks: list[dict] = []
    for n, label in PAGES.items():
        if n in pages:
            chunks.extend(chunk_page(pages[n], n, label, chapters, sections))
    return chunks


async def ingest_drafting_matters(
    *, source: str = SOURCE, sensitivity: str = "public"
) -> dict:
    """Fetch, chunk and insert. Idempotent: ON CONFLICT (source, rule_ref) DO NOTHING.

    Returns the counts the BUILD_PLAN verification asks for — row count and mean
    `full_text` length, which is the check that catches a whole-document blob.
    """
    async with httpx.AsyncClient(
        timeout=60.0, follow_redirects=True,
        headers={"User-Agent": "AILA-drafting-ingest/1.0"},
    ) as client:
        pages = await fetch_pages(client)

    chunks = build_chunks(pages)
    if not chunks:
        raise RuntimeError("Drafting Matters ingest produced no chunks — parse failed.")

    now = datetime.utcnow()
    inserted = 0
    async with async_session_maker() as session:
        for c in chunks:
            result = await session.execute(
                text(
                    "INSERT INTO drafting_guidance "
                    "(source, part, chapter, rule_ref, heading, full_text, "
                    " structured, url, version_date, sensitivity, fetched_at) "
                    "VALUES (:source, :part, :chapter, :rule_ref, :heading, :full_text, "
                    " CAST(:structured AS JSONB), :url, :version_date, :sensitivity, :fetched_at) "
                    "ON CONFLICT ON CONSTRAINT uq_drafting_guidance_source_ref DO NOTHING"
                ),
                {
                    "source": source,
                    "part": c["part"],
                    "chapter": c["chapter"],
                    "rule_ref": c["rule_ref"],
                    "heading": c["heading"],
                    "full_text": c["full_text"],
                    "structured": _json_section(c),
                    "url": c["url"],
                    "version_date": VERSION_DATE,
                    "sensitivity": sensitivity,
                    "fetched_at": now,
                },
            )
            inserted += result.rowcount or 0
        await session.commit()

        total = await session.scalar(
            text("SELECT COUNT(*) FROM drafting_guidance WHERE source = :s"),
            {"s": source},
        )
        mean_len = await session.scalar(
            text(
                "SELECT AVG(LENGTH(full_text)) FROM drafting_guidance "
                "WHERE source = :s"
            ),
            {"s": source},
        )

    stats = {
        "source": source,
        "chunks_parsed": len(chunks),
        "inserted": inserted,
        "skipped_existing": len(chunks) - inserted,
        "total_rows": total,
        "mean_full_text_chars": round(float(mean_len or 0), 1),
    }
    logger.info("[DraftingIngest] %s", stats)
    return stats


def _json_section(chunk: dict) -> str:
    """The `structured` payload: the heading path this chunk sits at.

    Kept as JSON rather than more columns because the internal guidance (which
    lands later under the same schema) is not known to share this hierarchy.
    """
    return json.dumps({
        "part": chunk["part"],
        "chapter": chunk["chapter"],
        "section": chunk["section"],
        "heading": chunk["heading"],
    })
