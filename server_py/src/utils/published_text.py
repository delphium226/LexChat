"""FIX_PLAN P3.38: the text of an instrument the index lacks, read from legislation.gov.uk.

**Why this exists.** LEX holds under 10% of the instruments made in 2026 and
about 85% of 2025's SSIs (P5.3), so "not held in this index" (P3.7's lookup,
P2.4's not-found note) is common for recent law, and is a fact about the
index, not about the law. Batch 12 F measured it: 20 stored turns in 8
sessions were told an instrument is not held or has no text, every one of the
9 that P3.31's census can check is published by legislation.gov.uk with its
as-made text, and a read would change 10 of those turns (7 fully). Five of the
9 are records LEX holds WITHOUT text, four of them met only by an empty text
read, so the trigger is three outcomes, not one (user decision, Session 44):

* a `lookup_legislation` result of `not_held` or `held_without_text`;
* a `get_legislation_text` read whose `full_text` is empty or LEX's one-line
  "No text content available for this legislation.";
* a `get_legislation_text` read LEX answered with its own "Legislation not
  found" (P2.4's not-held retrieval).

**Run by code, not offered as a tool** (Invariant 2): the read happens at the
seam that saw the outcome (`agent_shared.published_text_route`), through LEX's
`GET /legislation/proxy/<encoded path>`, which returns legislation.gov.uk's
XML byte for byte (P5.4, batch 9 C), so the target needs no new whitelist
entry. Live, never cached across requests, never stored.

This module holds the pure parts: which outcome triggers a read, the paths,
the CLML renderer, every sentence the Worker, the Manager and the lawyer read,
and the recorder that carries the outcome to the last two. The HTTP read is
in `agent/tools/published_text.py`.

**The block reuses P3.12's `[PROVISION FETCHED BY CODE — …]` markers**, so
every strip, grader and leak marker that already handles code-fetched text
handles this too (`_TOOL_BLOCK`, `_FETCHED_BLOCK`, `_BARE_TAG`,
`CORPUS_LEAK_MARKERS`, `depth --seams`, `route_trace.py`). Its lead never
matches `paragraph_restore`'s two leads, so no paragraph of it is ever read
as a handed schedule paragraph.
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from typing import Any, Optional

from .instrument_lookup import (
    HELD_WITHOUT_TEXT,
    LOOKUP_TOOL,
    NOT_HELD,
    citation_label,
    lookup_args,
    parse_lookup_result,
)
from .schedule_units import FETCHED_CLOSE, FETCHED_OPEN

TEXT_TOOL = "get_legislation_text"
PUBLISHED_ENTRY = "published_text"
SOURCE = "legislation.gov.uk"

# The three trigger kinds, one per state of the index the Worker is told:
# a lookup that found no record (`not_held`); a record without text, by lookup
# or by an empty text read (`no_text`); and a text read LEX answered
# "Legislation not found" (`read_not_found`). The last is said as what the read
# returned, never as "the index lacks it": LEX's text endpoint 404s on the
# regnal ids its own search returns for records it holds (batch 12 F: 2 Acts,
# 4 reads).
KIND_NOT_HELD = "not_held"
KIND_NO_TEXT = "no_text"
KIND_READ_NOT_FOUND = "read_not_found"

# Outcomes of a read (`agent/tools/published_text.py`).
OK = "ok"
NOT_PUBLISHED = "not_published"   # every route answered 404 or 400
PDF_ONLY = "pdf_only"             # legislation.gov.uk holds only a scanned PDF
FAILED = "failed"                 # no reply, an error, an unreadable page
LIMIT = "limit"                   # this request has made its reads
UNSUPPORTED = "unsupported"       # an id or type code has no route here (no line)
EARLIER = "earlier"               # this worker run was handed it already

# LEX's one-line body for a record it holds without text (batch 12 F: 5 of 5
# stub reads, 47 characters).
_STUB_BODY = "no text content available"

# Secondary instruments are read as made; primary legislation as enacted; each
# then falls back to legislation.gov.uk's current version. legislation.gov.uk
# serves `/enacted` and `/made` as aliases of one another (checked live, batch
# 13 C: an SSI's `/enacted/data.xml` returns its made document), so the
# label comes from the document read, not from the path asked for.
_SECONDARY = frozenset({
    "ssi", "uksi", "wsi", "nisr", "nisro", "nisi", "uksro", "ukmo", "ukci", "ssr",
})
_PRIMARY = frozenset({
    "ukpga", "asp", "anaw", "asc", "nia", "apni", "ukla", "ukppa", "gbla", "aosp",
    "aep", "apgb", "mwa", "aip", "mnia",
})
# A calendar id ("ssi/1901/3") or a regnal one ("ukpga/Vict/1-2/99" in form, which
# LEX's own search returns for pre-1963 Acts and `get_legislation_text` 404s
# on: batch 12 F, 2 Acts, 4 reads).
_LID = re.compile(r"^([a-z]{2,6})/(?:\d{4}|[A-Z][A-Za-z]{1,8}\d?/\d{1,4}(?:-\d{1,4})?)/\d{1,5}$")

_FORBIDDEN_XML = re.compile(r"<!\s*(?:DOCTYPE|ENTITY)", re.I)
_LEG_NS = "http://www.legislation.gov.uk/namespaces/legislation"
_UKM_NS = "http://www.legislation.gov.uk/namespaces/metadata"
_DC_NS = "http://purl.org/dc/elements/1.1/"


# ---------------------------------------------------------------------------
# the trigger
# ---------------------------------------------------------------------------

def normalise_id(value: Any) -> str:
    """The id legislation.gov.uk names the instrument by, or "" if it is not
    one this route reads. Lower-cases a calendar id; keeps a regnal id's
    capitals ("Vict"), which legislation.gov.uk's path needs."""
    s = str(value or "").strip().strip("/")
    s = re.sub(r"^https?://(?:www\.)?legislation\.gov\.uk/(?:id/)?", "", s, flags=re.I)
    parts = s.split("/")
    if len(parts) >= 1:
        parts[0] = parts[0].lower()
    s = "/".join(parts)
    m = _LID.match(s)
    if not m or m.group(1) not in (_SECONDARY | _PRIMARY):
        return ""
    return s


def _text_body(data: Any) -> Optional[str]:
    """`full_text` of a `get_legislation_text` result, or None if `data` is
    not one (an error string, a refusal, anything else)."""
    if not isinstance(data, str):
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(data.lstrip())
    except ValueError:
        return None
    if isinstance(obj, list):
        obj = obj[0] if obj else {}
    if not isinstance(obj, dict) or "full_text" not in obj or obj.get("error"):
        return None
    return str(obj.get("full_text") or "")


def _is_stub_body(body: str) -> bool:
    return not body.strip() or body.strip().lower().startswith(_STUB_BODY)


_LEX_NOT_FOUND = re.compile(r"Legislation not found")


def trigger(name: str, args: Any, raw_result: Any) -> Optional[tuple]:
    """`(legislation_id, kind)` when this tool result is one P3.38 reads for,
    else None. Keyed on the API's own outcome, never on the model's prose.
    Never raises."""
    try:
        if name == LOOKUP_TOOL:
            got = parse_lookup_result(raw_result)
            if not got:
                return None
            status = got.get("status")
            lid = normalise_id(got.get("legislation_id"))
            if not lid:
                return None
            if status == NOT_HELD:
                return lid, KIND_NOT_HELD
            if status == HELD_WITHOUT_TEXT:
                return lid, KIND_NO_TEXT
            return None
        if name != TEXT_TOOL:
            return None
        lid = normalise_id((args or {}).get("legislation_id"))
        if not lid:
            return None
        if isinstance(raw_result, str) and raw_result.startswith("Error executing tool") \
                and _LEX_NOT_FOUND.search(raw_result):
            return lid, KIND_READ_NOT_FOUND
        body = _text_body(raw_result)
        if body is not None and _is_stub_body(body):
            return lid, KIND_NO_TEXT
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# the paths
# ---------------------------------------------------------------------------

def routes(lid: str) -> list:
    """The legislation.gov.uk paths to try, in order: the version as made (an
    instrument) or as enacted (an Act), then the current version. [] for an id
    this route does not read."""
    lid = normalise_id(lid)
    if not lid:
        return []
    typ = lid.split("/")[0]
    first = "made" if typ in _SECONDARY else "enacted"
    return [f"{lid}/{first}/data.xml", f"{lid}/data.xml"]


def page_url(lid: str, version: str) -> str:
    """legislation.gov.uk's page for the version read, for the Worker to cite."""
    lid = normalise_id(lid)
    suffix = f"/{version}" if version in ("made", "enacted") else ""
    return f"https://www.legislation.gov.uk/{lid}{suffix}"


# ---------------------------------------------------------------------------
# the CLML renderer
# ---------------------------------------------------------------------------

def _local(tag: Any) -> str:
    return str(tag).rsplit("}", 1)[-1] if isinstance(tag, str) else ""


# Whole subtrees that are not the instrument's words: metadata, editorial
# commentaries and margin notes on revised text, images, the contents list.
_SKIP = frozenset({
    "Metadata", "Contents", "Commentaries", "CommentaryRef", "MarginNotes",
    "MarginNoteRef", "Resources", "Image", "Figure", "Footnotes", "ExternalVersion",
})
# Elements whose text is one line of output.
_LINE = frozenset({
    "Text", "Title", "Number", "LongTitle", "DateText", "Reference", "PersonName",
    "JobTitle", "AddressLine", "IntroductoryText", "FragmentNumber", "FragmentTitle",
})
_PLEVELS = {"P1": 1, "P2": 2, "P3": 3, "P4": 4, "P5": 5, "P6": 6}
_WS = re.compile(r"\s+")


class _Renderer:
    def __init__(self, footnotes: dict):
        self.lines: list = []
        self.pending: list = []
        self.footnotes = footnotes
        self.cited: list = []
        self.urls: list = []

    def inline(self, el) -> str:
        out = [el.text or ""]
        for child in el:
            name = _local(child.tag)
            if name == "FootnoteRef":
                ref = child.attrib.get("Ref", "")
                if ref in self.footnotes:
                    if ref not in self.cited:
                        self.cited.append(ref)
                    out.append(f" (footnote {self.cited.index(ref) + 1})")
            elif name not in _SKIP:
                out.append(self.inline(child))
            out.append(child.tail or "")
        return "".join(out)

    def emit(self, text: str) -> None:
        text = _WS.sub(" ", text).strip()
        if not text:
            return
        if self.pending:
            text = " ".join(self.pending + [text])
            self.pending = []
        self.lines.append(text)

    def walk(self, el) -> None:
        name = _local(el.tag)
        if name in _SKIP:
            return
        if name in _PLEVELS:
            uri = el.attrib.get("DocumentURI") or ""
            if uri and name == "P1":
                self.urls.append(uri)
            num = ""
            for child in el:
                if _local(child.tag) == "Pnumber":
                    num = _WS.sub(" ", self.inline(child)).strip()
                    break
            if num:
                self.pending.append(f"{num}." if name == "P1" else f"({num})")
            for child in el:
                if _local(child.tag) != "Pnumber":
                    self.walk(child)
            return
        if name in ("Schedule", "Part", "Chapter") and el.attrib.get("DocumentURI"):
            self.urls.append(el.attrib["DocumentURI"])
        if name in _LINE:
            self.emit(self.inline(el))
            return
        if name == "tr":
            cells = [_WS.sub(" ", self.inline(c)).strip() for c in el
                     if _local(c.tag) in ("td", "th")]
            self.emit(" | ".join(c for c in cells if c))
            return
        if name == "ListItem":
            self.pending.append("-")
            for child in el:
                self.walk(child)
            if self.pending and self.pending[-1] == "-":
                self.pending.pop()
            return
        for child in el:
            self.walk(child)


def _xml_root(xml_text: str):
    """Parse untrusted XML. A document type or entity declaration is refused
    (legislation.gov.uk's CLML carries neither; expat would expand entities)."""
    if not isinstance(xml_text, str) or not xml_text.strip():
        raise ValueError("empty")
    if _FORBIDDEN_XML.search(xml_text):
        raise ValueError("document type or entity declaration")
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise ValueError(f"not XML: {e}") from None
    if _local(root.tag) != "Legislation":
        raise ValueError(f"not a legislation document: {_local(root.tag)}")
    return root


def _https(url: str) -> str:
    return re.sub(r"^http://", "https://", str(url or ""))


def parse_published(xml_text: str) -> dict:
    """legislation.gov.uk's CLML for one instrument, rendered as plain text.

    Returns ``{"title", "version", "url", "text", "has_schedules", "pdf",
    "provision_urls"}``. ``version`` is ``made``, ``enacted`` or ``current``,
    read from the document's own `DocumentURI`. ``text`` is "" for a document
    with no body, which is how legislation.gov.uk publishes an instrument it
    holds only as a scanned PDF (``pdf`` then names the scan). Raises
    ValueError on anything that is not a CLML document, so an error page is
    never read as an instrument with no text.
    """
    root = _xml_root(xml_text)
    doc_uri = root.attrib.get("DocumentURI") or ""
    tail = doc_uri.rstrip("/").rsplit("/", 1)[-1]
    version = tail if tail in ("made", "enacted") else "current"
    title = ""
    for el in root.iter(f"{{{_DC_NS}}}title"):
        title = _WS.sub(" ", el.text or "").strip()
        break
    pdf = ""
    for el in root.iter(f"{{{_UKM_NS}}}Alternative"):
        uri = el.attrib.get("URI") or ""
        if uri.lower().endswith(".pdf"):
            pdf = _https(uri)
            break
    footnotes = {}
    for fn in root.iter(f"{{{_LEG_NS}}}Footnote"):
        fid = fn.attrib.get("id")
        if fid:
            footnotes[fid] = fn
    r = _Renderer(footnotes)
    has_body = False
    for child in root:
        name = _local(child.tag)
        if name in ("Primary", "Secondary", "EURetained"):
            has_body = any(_local(g.tag) in ("Body", "Schedules", "EUBody") for g in child)
            r.walk(child)
    if r.cited:
        r.emit("Footnotes:")
        for i, ref in enumerate(r.cited, 1):
            fn = footnotes[ref]
            parts = [r.inline(t) for t in fn.iter(f"{{{_LEG_NS}}}Text")]
            r.emit(f"({i}) " + " ".join(parts))
    has_schedules = any(_local(e.tag) == "Schedule" for e in root.iter())
    text = "\n".join(r.lines) if has_body else ""
    # The preamble on its own, for P2.3's enabling-power rule: the recital is
    # in it, and `agent_shared` builds the permitting block from it where no
    # other record states one (P3.31's `made_under.recital_window` decides).
    preamble = ""
    for el in root.iter(f"{{{_LEG_NS}}}SecondaryPreamble"):
        p = _Renderer({})
        p.walk(el)
        preamble = " ".join(p.lines)
        break
    return {
        "title": title,
        "version": version,
        "url": _https(doc_uri),
        "text": text,
        "has_schedules": has_schedules,
        "pdf": pdf,
        "preamble": preamble,
        "provision_urls": list(dict.fromkeys(_https(u) for u in r.urls)),
    }


# ---------------------------------------------------------------------------
# the sentences
# ---------------------------------------------------------------------------

def _clean(text: Any, cap: int = 200) -> str:
    """One line, no square brackets (a bracket would end `_TOOL_BLOCK`'s match)."""
    s = _WS.sub(" ", str(text or "")).strip().replace("[", "(").replace("]", ")")
    return s if len(s) <= cap else s[:cap].rsplit(" ", 1)[0] + "…"


def label_for(lid: str) -> str:
    """"SSI 1901/3" for a calendar id the lookup can parse; the id otherwise."""
    ref = lookup_args({"legislation_id": lid})
    return citation_label(ref) if ref else lid


def _index_state(lid: str, kind: str, title: str = "") -> str:
    """The index's state, as the lead's opening clause; `title` (the one
    legislation.gov.uk gave) goes straight after the instrument's label."""
    label = label_for(lid) + (f" ({title})" if title else "")
    # "lacks", not "does not hold": every sentence here is screened against
    # the answer detectors (`test_footer_trips_no_detector`), and "index does
    # not hold" is `NEG_ASSERTED`'s and `NEG_BLAMED_INDEX`'s own phrase.
    if kind == KIND_NO_TEXT:
        return f"this index holds the record of {label} but none of its text"
    if kind == KIND_READ_NOT_FOUND:
        return f"this index's text read gave no text for {label} under that id"
    return f"this index lacks {label}"


_VERSION_WORDS = {
    "made": "the version as made",
    "enacted": "the version as enacted",
    "current": "legislation.gov.uk's current version (it publishes no version as made "
               "or enacted of it)",
}


def _version_words(version: str) -> str:
    return _VERSION_WORDS.get(version, _VERSION_WORDS["current"])


def _currency_sentence(version: str) -> str:
    """What the version read cannot show. Worded clear of `IN_FORCE_CLAIM`
    ("is in force") and P2.5's currency detectors: the text read says nothing
    either way about the instrument's present status."""
    if version in ("made", "enacted"):
        return (f"{_version_words(version)[:1].upper()}{_version_words(version)[1:]} shows "
                "no later amendment or revocation and says nothing about the instrument's "
                "status today.")
    return "This text by itself says nothing about the instrument's status today."


# Why the text was read elsewhere, per kind, for the block's instruction.
_WHY = {
    KIND_NOT_HELD: "the index lacks it",
    KIND_NO_TEXT: "the index holds none of its text",
    KIND_READ_NOT_FOUND: "the index's text read gave none",
}


# The opening every block and line shares, and what the recorder parses back.
_READ_LEAD = "so code read its text from legislation.gov.uk"


def published_block(lid: str, kind: str, outcome: dict, pieces_how: str = "whole",
                    body: str = "", total_chars: int = 0) -> str:
    """The block handed to the Worker after a read that returned text.

    `pieces_how` is "whole" (the text verbatim) or "summary" (a summary of it
    for the query, because it is longer than one result hands over whole or
    than the context budget allows). One block per instrument.
    """
    version = outcome.get("version") or "current"
    title = _clean(outcome.get("title"), 200)
    url = _clean(outcome.get("url") or page_url(lid, version), 160)
    sched = (" with its schedules" if outcome.get("has_schedules")
             else " (it has no schedule)")
    # The title check is P3.7's, for the same reason: an id a model built can
    # name a different instrument (a stored run's SSI read under `uksi/`, a
    # number legislation.gov.uk publishes as an unrelated UK SI; batch 13 C's
    # dry run).
    lead = (f"{_index_state(lid, kind, title)}, {_READ_LEAD}, the official "
            f"publisher, through the LEX API: {_version_words(version)}{sched}, "
            f"{total_chars:,} characters. Check that its title is the instrument the "
            "question is about before relying on it.")
    if pieces_how == "summary":
        how = (" It is longer than one result hands over whole, so below is a summary of "
               "that retrieved text, condensed for this research question. A provision "
               "the summary leaves out is still part of the retrieved text. Quote its "
               "words only from text shown verbatim.")
    else:
        how = " Below is the whole of it."
    cite = (f" This text comes from legislation.gov.uk, a different source from the index: "
            f"cite it as {url}, and say in the report that it was read from "
            f"legislation.gov.uk because {_WHY.get(kind, _WHY[KIND_NOT_HELD])}. "
            f"{_currency_sentence(version)}")
    return (f"\n\n{FETCHED_OPEN}{lead}{how}{cite}]\n{str(body or '').strip()}\n"
            f"{FETCHED_CLOSE}")


_REASON_WORDS = {
    "no_reply": "no reply",
    "too_large": "the document was too large to read",
    "unreadable": "the page was not a legislation document",
}


def published_line(lid: str, kind: str, outcome: dict) -> str:
    """The one-line note for a read that returned no text. "" where nothing
    should be said (an id or type this route does not read)."""
    status = outcome.get("status")
    label = label_for(lid)
    state = _index_state(lid, kind)
    if status == NOT_PUBLISHED:
        return (f"\n\n{FETCHED_OPEN}{state}, and code asked legislation.gov.uk for its "
                f"text: legislation.gov.uk returned no document under {lid} either, so "
                "its text could not be checked here. That says nothing about whether the "
                "citation is accurate.]")
    if status == PDF_ONLY:
        where = f" ({_clean(outcome.get('pdf'), 160)})" if outcome.get("pdf") else ""
        return (f"\n\n{FETCHED_OPEN}{state}, and legislation.gov.uk publishes {label} only "
                f"as a scanned PDF{where}, which code cannot read, so its text could not be "
                "checked here.]")
    if status == FAILED:
        reason = _REASON_WORDS.get(str(outcome.get("reason") or ""), "an error")
        return (f"\n\n{FETCHED_OPEN}{state}, and code's read of its text from "
                f"legislation.gov.uk did not complete ({reason}), so its text could not be "
                "checked here. That says nothing about the instrument.]")
    if status == LIMIT:
        return (f"\n\n{FETCHED_OPEN}{state}, and code did not read its text from "
                f"legislation.gov.uk: this request has already read "
                f"{int(outcome.get('limit') or 0)} instruments from there, the most it "
                "reads, so its text could not be checked here.]")
    if status == EARLIER:
        return (f"\n\n{FETCHED_OPEN}{state}; code read its text from legislation.gov.uk "
                "earlier in this research, and that text was handed over there.]")
    return ""


# ---------------------------------------------------------------------------
# the record, for the Manager's block and the lawyer's footer
# ---------------------------------------------------------------------------

def record_published(log: Optional[list], lid: str, kind: str, outcome: dict) -> None:
    """Record one read's outcome for `published_limb` and the footer. A read
    that this route does not make (`unsupported`) is not recorded. Never raises."""
    if log is None:
        return
    try:
        status = outcome.get("status")
        if status not in (OK, NOT_PUBLISHED, PDF_ONLY, FAILED, LIMIT, EARLIER):
            return
        log.append({
            "tool": PUBLISHED_ENTRY,
            "legislation_id": lid[:60],
            "label": label_for(lid),
            "kind": kind,
            "status": status,
            "version": outcome.get("version") or "",
        })
    except Exception:
        pass


def handed_in_run(log: Optional[list], lid: str) -> bool:
    """Whether this worker run was already handed this instrument's text."""
    return any(e.get("tool") == PUBLISHED_ENTRY and e.get("legislation_id") == lid[:60]
               and e.get("status") == OK for e in (log or []))


# Every lead opens with `_index_state`, which no P3.12 lead does.
_OPENING = r"this index(?: lacks|'s text read gave no text for| holds the record of) "
_BLOCK_RE = re.compile(
    re.escape(FETCHED_OPEN) + _OPENING + r"[^\]]*" + re.escape(_READ_LEAD) + r"[^\]]*\]"
    r"[\s\S]*?" + re.escape(FETCHED_CLOSE))
_LINE_RE = re.compile(
    re.escape(FETCHED_OPEN) + _OPENING + r"[^\]]*legislation\.gov\.uk[^\]]*\]")


def blocks_in(result: Any) -> str:
    """Every published-text block and line in a tool result, joined, so a
    caller that re-composes a lookup's outcome (the brief block, the quick-
    lookup Worker's suffix) hands on what code read. "" if none."""
    if not isinstance(result, str):
        return ""
    found = []
    for m in _BLOCK_RE.finditer(result):
        found.append((m.start(), m.group(0)))
    spans = [(s, s + len(t)) for s, t in found]
    for m in _LINE_RE.finditer(result):
        if not any(a <= m.start() < b for a, b in spans):
            found.append((m.start(), m.group(0)))
    return "".join("\n\n" + t for _, t in sorted(found))


def has_published_text(result: Any) -> bool:
    """Whether a tool result carries a published-text block with text."""
    return isinstance(result, str) and bool(_BLOCK_RE.search(result))


def published_limb(log: Optional[list]) -> str:
    """The Manager's (and the Deep Research synthesis's) line on what code
    read from legislation.gov.uk in this step. "" if nothing was attempted."""
    rows: dict = {}
    for e in log or []:
        if e.get("tool") == PUBLISHED_ENTRY and e.get("legislation_id"):
            prev = rows.get(e["legislation_id"])
            if prev is None or prev.get("status") != OK:
                rows[e["legislation_id"]] = e
    if not rows:
        return ""
    read = [e for e in rows.values() if e.get("status") in (OK, EARLIER)]
    unread = [e for e in rows.values() if e.get("status") not in (OK, EARLIER)]
    out = []
    if read:
        listed = "; ".join(
            f"{e['label']} ({_version_words(e.get('version') or 'current').split(' (')[0]})"
            if e.get("status") == OK else f"{e['label']}"
            for e in read[:8])
        out.append(
            f"Read from legislation.gov.uk by code, because the index lacks the text: "
            f"{listed}. The report may state and cite what that text provides, "
            "attributed to legislation.gov.uk, and the answer must say that it was read "
            "from there. That changes nothing about what this index holds, and a version "
            "as made or enacted shows no later amendment or revocation and says nothing "
            "about an instrument's status today.")
    if unread:
        listed = ", ".join(e["label"] for e in unread[:8])
        out.append(
            f"Asked legislation.gov.uk for the text, and none was read: {listed}. "
            f"{'Its' if len(unread) == 1 else 'Their'} text could not be checked here.")
    return " ".join(out)


def published_footer_clause(entries: Optional[list]) -> str:
    """The lawyer-facing clause: one sentence naming each instrument whose
    text this turn read from legislation.gov.uk. "" when none was read."""
    seen, read = set(), []
    for e in entries or []:
        if e.get("tool") == PUBLISHED_ENTRY and e.get("status") == OK \
                and e.get("legislation_id") not in seen:
            seen.add(e.get("legislation_id"))
            read.append(e)
    if not read:
        return ""
    labels = [f"{e['label']} ({_FOOTER_VERSION.get(e.get('version'), 'its current version')})"
              for e in read]
    joined = labels[0] if len(labels) == 1 else ", ".join(labels[:-1]) + " and " + labels[-1]
    return f" The text of {joined} was read from legislation.gov.uk."


_FOOTER_VERSION = {"made": "as made", "enacted": "as enacted"}
