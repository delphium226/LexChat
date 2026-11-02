"""FIX_PLAN P3.57: a literal search over a made-under list, made by code.

**The defect.** 6382 and 6383 ask which of the 37 instruments made under s.95
of the Social Security (Scotland) Act 2018 "feature a £ symbol within their
text". The only search a Worker has within an instrument,
`search_legislation_sections`, ranks provisions by meaning, so a character is
found only where a returned provision happens to carry it: SSI 2025/340 holds
"£11.29" in regulation 3 and was missed in every stored run, and the Workers
searched 2 to 37 of the 37. Read in full (`evidence/seam/s52/p357/`, 55 live
calls), 20 of the 37 hold '£'.

**The lever (code-routed, P3.7's and P3.38's precedent; Invariant 2).** Where
a `find_instruments_made_under` result lists every instrument it found (40 or
fewer) and the Worker's brief or the lawyer's message asks for a literal string
(`detect_literal`), code reads each listed instrument's text and searches it
for the string, then appends one compact block to the made-under result: for
each instrument found or not found, the count, the provisions holding it with
up to two short verbatim snippets, and every instrument it could not read. The
texts themselves never enter the Worker's context, only the block, so the scan
costs the context budget a few thousand characters, not the 1.3M characters of
the 37 texts. The read is LEX's provision list (`/legislation/section/lookup`,
one call an instrument, every provision and schedule with its `uri`), and for
an instrument the index holds no text of, P3.38's read of legislation.gov.uk
through LEX's proxy.

This module is pure: the detector, the matcher, the per-instrument outcome,
the Worker's block, the scope-record entry and the Manager's limb. The reads
are in `agent/tools/literal_scan.py`. Never raises.

**What a scan establishes:** that the string does, or does not, appear in the
text read, which is the instrument's provisions and schedules as LEX holds
them (as made), or legislation.gov.uk's text as made. Not explanatory notes,
not text a later amendment inserted, and nothing about an instrument it could
not read. Every text built here says so.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Optional

__all__ = [
    "SCAN_ENTRY",
    "MAX_SCANNED",
    "detect_literal",
    "literal_pattern",
    "outcome_from_rows",
    "outcome_from_text",
    "scan_block",
    "scan_entry",
    "scan_limb",
    "scan_footer",
]

# The scope-record entry's `tool` (`search_scope`'s recorders read it).
SCAN_ENTRY = "literal_scan"
# P3.31's cap (`made_under.MAX_LISTED`): a list cut at 40 is not scanned, since
# a scan of the first 40 would read as a scan of the list.
MAX_SCANNED = 40
# Snippets: per instrument, the provisions named with a snippet, then named
# without one; each snippet this many characters either side of the match.
SNIPPETS_PER_INSTRUMENT = 2
MORE_PROVISIONS_NAMED = 4
SNIPPET_SIDE = 60
# The block's own bound. 37 instruments with two snippets each measured 9,846
# characters on the s.95 list; past the bound the snippets go first.
BLOCK_MAX_CHARS = 16_000

_WS = re.compile(r"\s+")

# ---------------------------------------------------------------------------
# The detector
# ---------------------------------------------------------------------------
#
# A literal is asked for in three shapes, measured over the stored briefs and
# questions (`evidence/seam/s52/p357/detector_reach.txt`): a quoted string with
# a word saying the text should contain it ("contain the '£' symbol", "use the
# phrase 'qualifying week'"), a bare symbol called a symbol or sign ("feature a
# £ symbol"), and a symbol named in words ("a pound sign"). A quoted string
# with a defining word nearby is P3.34's question, not this one; a quoted
# provision ("section 95") or title (ends in a year) is never a literal.

_CUE = re.compile(
    r"\b(?:contain(?:s|ed|ing)?|feature(?:s|d)?|featuring|includ(?:e|es|ed|ing)|"
    r"mention(?:s|ed|ing)?|appear(?:s|ed|ing)?|occur(?:s|red|ring|rences?)?|"
    r"use(?:s|d)?|using|words?|phrases?|expressions?|strings?|symbols?|characters?|"
    r"signs?)\b", re.I)
_SYMBOL_WORD = re.compile(r"\b(?:symbols?|signs?|characters?|glyphs?)\b", re.I)
_DEFINE = re.compile(r"\bdefin(?:e|es|ed|ing|ition|itions)\b", re.I)
_QUOTED = [
    re.compile(r"(?:(?<=^)|(?<=[\s(:,;]))'(?P<lit>[^'\n‘’“”\"]{1,40})'(?=$|[\s).,;:!?])"),
    re.compile(r'(?:(?<=^)|(?<=[\s(:,;]))"(?P<lit>[^"\n‘’“”]{1,40})"(?=$|[\s).,;:!?])'),
    re.compile(r"‘(?P<lit>[^‘’\n“”\"]{1,40})’"),
    re.compile(r"“(?P<lit>[^“”\n]{1,40})”"),
]
_PROVISION = re.compile(
    r"^(?:s|ss|reg|regs|art|para|sch)\.?\s*\d|^(?:section|regulation|article|paragraph|"
    r"schedule|part|chapter|rule|annex)\s+[\dIVXivx]", re.I)
_TITLE_YEAR = re.compile(r"\b(?:1[89]|20)\d\d\s*$")
_EXTRA_SYMBOLS = frozenset("§¶©®™")
_NAMED = [
    (re.compile(r"\b(?:pound(?:s)?(?:\s+sterling)?|sterling)\s+(?:sign|symbol)\b", re.I), "£"),
    (re.compile(r"\beuro\s+(?:sign|symbol)\b", re.I), "€"),
    (re.compile(r"\bdollar\s+(?:sign|symbol)\b", re.I), "$"),
    (re.compile(r"\bsection\s+(?:sign|symbol)\b", re.I), "§"),
    (re.compile(r"\b(?:per\s?cent|percent(?:age)?)\s+(?:sign|symbol)\b", re.I), "%"),
]
_THE_WORD = re.compile(r"\bthe\s+word\s+(?P<lit>[A-Za-z][A-Za-z'’-]{1,30})\b")
_WINDOW = 120


def _window(text: str, start: int, end: int) -> str:
    return text[max(0, start - _WINDOW): end + _WINDOW]


def _is_symbol(ch: str) -> bool:
    return unicodedata.category(ch) == "Sc" or ch in _EXTRA_SYMBOLS


def _quoted(text: str) -> Optional[tuple]:
    best = None
    for rx in _QUOTED:
        for m in rx.finditer(text):
            lit = m.group("lit").strip()
            if not lit or _PROVISION.search(lit) or _TITLE_YEAR.search(lit):
                continue
            around = _window(text, m.start(), m.end())
            if _DEFINE.search(around) or not _CUE.search(around):
                continue
            if best is None or m.start() < best[0]:
                best = (m.start(), lit)
            break
    return best


def _bare_symbol(text: str) -> Optional[tuple]:
    for i, ch in enumerate(text):
        if not _is_symbol(ch):
            continue
        before = text[i - 1] if i else " "
        after = text[i + 1] if i + 1 < len(text) else " "
        if before.isdigit() or after.isdigit() or before.isalpha() or after.isalpha():
            continue    # an amount ("£300") or part of a word, not a literal ask
        around = _window(text, i, i + 1)
        if _SYMBOL_WORD.search(around) or _CUE.search(around):
            return (i, ch)
    return None


def detect_literal(*texts: Any) -> str:
    """The literal string the text asks to be found, or "".

    Read in order (the brief, then the lawyer's message); within one text a
    quoted string comes first, then a bare symbol, a symbol named in words,
    and "the word X". Never raises."""
    try:
        for raw in texts:
            text = str(raw or "")
            if not text.strip():
                continue
            for found in (_quoted(text), _bare_symbol(text)):
                if found:
                    return found[1]
            for rx, sym in _NAMED:
                if rx.search(text):
                    return sym
            m = _THE_WORD.search(text)
            if m and not _DEFINE.search(_window(text, m.start(), m.end())):
                return m.group("lit")
        return ""
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# The matcher
# ---------------------------------------------------------------------------

def literal_pattern(literal: str) -> Optional["re.Pattern"]:
    """The regex a literal is searched with: exactly as written, except that
    letter case is ignored when it has letters, any run of white space matches
    any other, an apostrophe matches either form, and a literal that begins or
    ends with a letter or digit matches only as a whole word there."""
    lit = str(literal or "").strip()
    if not lit:
        return None
    parts = []
    for ch in lit:
        if ch.isspace():
            if not parts or parts[-1] != r"\s+":
                parts.append(r"\s+")
        elif ch in "'’":
            parts.append("['’]")
        else:
            parts.append(re.escape(ch))
    body = "".join(parts)
    if lit[0].isalnum():
        body = r"(?<![\w])" + body
    if lit[-1].isalnum():
        body = body + r"(?![\w])"
    flags = re.I if any(c.isalpha() for c in lit) else 0
    return re.compile(body, flags)


def _clean(text: Any, cap: int = 400) -> str:
    """One line, no square brackets (a bracket would end `_TOOL_BLOCK`'s match),
    no double quotes (the snippet is put in them)."""
    s = _WS.sub(" ", str(text or "")).strip()
    s = s.replace("[", "(").replace("]", ")").replace('"', "'")
    return s if len(s) <= cap else s[:cap].rstrip() + "…"


def _snippet(text: str, m: "re.Match") -> str:
    a, b = max(0, m.start() - SNIPPET_SIDE), min(len(text), m.end() + SNIPPET_SIDE)
    # Widen to word edges so a snippet never starts or ends mid-word.
    while a > 0 and not text[a - 1].isspace() and m.start() - a < SNIPPET_SIDE + 20:
        a -= 1
    while b < len(text) and not text[b].isspace() and b - m.end() < SNIPPET_SIDE + 20:
        b += 1
    s = _clean(text[a:b], 3 * SNIPPET_SIDE)
    return ("…" if a > 0 else "") + s + ("…" if b < len(text) else "")


def _https(url: str) -> str:
    u = str(url or "").strip()
    return "https://" + u[len("http://"):] if u.startswith("http://") else u


_PROV_PATH = re.compile(r"legislation\.gov\.uk/(?:id/)?[a-z]+/\d{4}/\d+/(.+?)(?:/(?:made|enacted))?/?$")


def _provision_label(row: dict) -> str:
    m = _PROV_PATH.search(str(row.get("uri") or row.get("id") or ""))
    if not m:
        return "a provision"
    bits = m.group(1).split("/")
    out = []
    for i in range(0, len(bits) - 1, 2):
        out.append(f"{bits[i]} {bits[i + 1]}")
    if len(bits) % 2:
        out.append(f"the {bits[-1]}")
    return ", ".join(out) or "a provision"


def _provision_url(row: dict) -> str:
    """The provision's URL without the version, https (P1.6's form)."""
    u = _https(row.get("uri") or row.get("id") or "")
    u = re.sub(r"/(?:made|enacted)/?$", "", u)
    return u.replace("legislation.gov.uk/id/", "legislation.gov.uk/")


def outcome_from_rows(rows: Any, literal: str) -> dict:
    """One instrument's outcome from its provision list (`fetch_provision_list`
    rows): `{"status": "read", "source": "index", "count", "provisions": [...]}`,
    each provision `{"label", "url", "count", "snippet"}`."""
    rx = literal_pattern(literal)
    rows = [r for r in (rows if isinstance(rows, list) else []) if isinstance(r, dict)]
    if rx is None or not rows:
        return {"status": "not_read", "reason": "no_text"}
    provs, total = [], 0
    made = all(str(r.get("uri") or "").rstrip("/").endswith("/made") for r in rows)
    for r in rows:
        text = str(r.get("text") or "")
        hits = list(rx.finditer(text))
        if not hits:
            continue
        total += len(hits)
        provs.append({"label": _provision_label(r), "url": _provision_url(r),
                      "count": len(hits), "snippet": _snippet(text, hits[0])})
    return {"status": "read", "source": "index", "version": "made" if made else "",
            "provisions_read": len(rows), "count": total, "provisions": provs}


def outcome_from_text(text: Any, literal: str, url: str = "", version: str = "") -> dict:
    """One instrument's outcome from legislation.gov.uk's text (P3.38's read):
    the same shape, the matches given against the instrument, not a provision."""
    rx = literal_pattern(literal)
    text = str(text or "")
    if rx is None or not text.strip():
        return {"status": "not_read", "reason": "no_text"}
    hits = list(rx.finditer(text))
    provs = []
    if hits:
        provs.append({"label": "its text", "url": _https(url), "count": len(hits),
                      "snippet": _snippet(text, hits[0])})
    return {"status": "read", "source": "legislation.gov.uk", "version": version or "",
            "count": len(hits), "provisions": provs}


# ---------------------------------------------------------------------------
# The Worker's block
# ---------------------------------------------------------------------------

_REASONS = {
    "no_text": "neither LEX nor legislation.gov.uk gave a text",
    "failed": "the read did not complete",
    "no_reply": "no reply in time",
    "limit": "this request's limit of legislation.gov.uk reads was reached",
    "pdf_only": "legislation.gov.uk holds it only as a scanned PDF",
    "not_published": "legislation.gov.uk does not publish its text",
}


def _q(literal: str) -> str:
    return '"' + _clean(literal, 60) + '"'


def _times(n: int) -> str:
    return "once" if n == 1 else f"{n} times"


def _found_line(lid: str, title: str, o: dict, snippets: int) -> str:
    provs = o.get("provisions") or []
    where = ("in legislation.gov.uk's text" if o.get("source") == "legislation.gov.uk"
             else f"in {len(provs)} provision" + ("" if len(provs) == 1 else "s"))
    parts = []
    for p in provs[:snippets]:
        parts.append(f"{p['url']}: \"{p['snippet']}\"" if p["label"] == "its text"
                     else f"{p['label']} ({p['url']}): \"{p['snippet']}\"")
    rest = provs[snippets:]
    if rest:
        named = ", ".join(p["label"] for p in rest[:MORE_PROVISIONS_NAMED])
        more = len(rest) - MORE_PROVISIONS_NAMED
        parts.append(f"also {named}" + (f" and {more} more" if more > 0 else ""))
    head = f"- {lid}" + (f" ({_clean(title, 110)})" if title else "")
    return f"{head}: {_times(int(o.get('count') or 0))} {where}" + (
        "; " + "; ".join(parts) if parts else "")


def _id_list(ids: list) -> str:
    return ", ".join(ids) if ids else "none"


def scan_block(literal: str, listed: list, outcomes: dict, titles: Optional[dict] = None,
               max_chars: int = BLOCK_MAX_CHARS) -> str:
    """The block appended to the made-under result for the Worker. A SEARCH
    SCOPE block by name, so `strip_scope_blocks` removes it if a report echoes
    it; no square brackets inside. Sized under `max_chars` (at most
    `BLOCK_MAX_CHARS`; the caller passes what remains of the context budget):
    past it the snippets go, and then the found list is cut, saying so. ""
    when nothing was scanned."""
    if not listed or not literal:
        return ""
    titles = titles or {}
    max_chars = min(int(max_chars or BLOCK_MAX_CHARS), BLOCK_MAX_CHARS)
    found = [l for l in listed if (outcomes.get(l) or {}).get("status") == "read"
             and int(outcomes[l].get("count") or 0) > 0]
    absent = [l for l in listed if (outcomes.get(l) or {}).get("status") == "read"
              and not int(outcomes[l].get("count") or 0)]
    unread = [l for l in listed if (outcomes.get(l) or {}).get("status") != "read"]
    read = len(found) + len(absent)
    q = _q(literal)
    for snippets in (SNIPPETS_PER_INSTRUMENT, 1, 0):
        lines = [_found_line(l, titles.get(l, ""), outcomes[l], snippets) for l in found]
        unread_bits = [f"{l} ({_REASONS.get((outcomes.get(l) or {}).get('reason'), 'the read did not complete')})"
                       for l in unread]
        body = (
            f"\n\n[SEARCH SCOPE — text scan by code: the question asks which of these "
            f"instruments contain {q}, and a section "
            "search ranks provisions by meaning, so it cannot find a string. Code therefore read "
            f"the text of {read} of the {len(listed)} instruments listed above, every provision "
            "and schedule as made (from this index, or from legislation.gov.uk where the index "
            f"holds no text; explanatory notes are not part of it), and searched it for {q} "
            "exactly as written (letter case and line breaks aside).\n"
            f"Found in {len(found)}:\n" + ("\n".join(lines) if lines else "- none") + "\n"
            f"Not found in the text read, {len(absent)}: {_id_list(absent)}.\n"
            + (f"Not read, {len(unread)}: {'; '.join(unread_bits)}.\n" if unread else "")
            + f"You MAY state that each instrument under Found contains {q}, citing the provision "
            f"shown. You MAY state that an instrument under Not found does not contain {q} in its "
            "provisions and schedules as made; do not say it never has, or that no later amendment "
            "inserts it. "
            + (f"Name each instrument under Not read as not checked for {q}, and say nothing of "
               "what it contains. " if unread else "")
            + f"Do not section-search these instruments for {q}: this scan has read them.]"
        )
        if len(body) <= max_chars:
            return body
    head, tail = body.split("\nNot found in the text read", 1)
    tail = "\nNot found in the text read" + tail
    cut = head[:max(0, max_chars - len(tail) - 40)].rsplit("\n", 1)[0]
    return cut + "\n- (this list is cut here for length)" + tail


# ---------------------------------------------------------------------------
# The scope record, the Manager's limb and the footer
# ---------------------------------------------------------------------------

def scan_entry(literal: str, listed: list, outcomes: dict) -> dict:
    """The scope-record entry `search_scope` reads (`list_coverage`, the limb,
    the footer)."""
    found = [l for l in listed if (outcomes.get(l) or {}).get("status") == "read"
             and int(outcomes[l].get("count") or 0) > 0]
    absent = [l for l in listed if (outcomes.get(l) or {}).get("status") == "read"
              and not int(outcomes[l].get("count") or 0)]
    unread = [l for l in listed if (outcomes.get(l) or {}).get("status") != "read"]
    return {"tool": SCAN_ENTRY, "literal": _clean(literal, 60), "listed": len(listed),
            "ids": list(listed), "found": found, "absent": absent, "unread": unread}


def _scan_rows(log: Optional[list]) -> list:
    return [e for e in (log or []) if e.get("tool") == SCAN_ENTRY]


def scan_limb(log: Optional[list]) -> str:
    """The line in the Worker's scope block for the Manager and the synthesis,
    which never see the tool result. "" where no scan ran."""
    rows = _scan_rows(log)
    if not rows:
        return ""
    e = rows[-1]
    q = _q(e["literal"])
    read = len(e["found"]) + len(e["absent"])
    unread = (f"; {len(e['unread'])} could not be read ({_id_list(e['unread'])})"
              if e["unread"] else "")
    rule = (f" An instrument may be said to contain {q} only where it was found; one not found "
            f"may be said not to contain it in its provisions and schedules as made, never that "
            f"no later amendment inserts it")
    rule += ("; one not read must be named as not checked, with nothing said of what it "
             "contains." if e["unread"] else ".")
    return (f"Text scan by code: of the {e['listed']} instruments the made-under record listed, "
            f"code read the text of {read} in full and searched each for {q}: found in "
            f"{len(e['found'])} ({_id_list(e['found'])}), not found in the text read in "
            f"{len(e['absent'])} ({_id_list(e['absent'])}){unread}." + rule)


def scan_footer(entries: Optional[list]) -> str:
    """The legal professional's sentence: what was read, and what was not."""
    rows = _scan_rows(entries)
    if not rows:
        return ""
    e = rows[-1]
    q = _q(e["literal"])
    read = len(e["found"]) + len(e["absent"])
    if not e["unread"]:
        return (f" Of the {e['listed']} instruments the made-under record lists, code read the "
                f"text of every one (its provisions and schedules as made) and searched it for {q}.")
    n = len(e["unread"])
    return (f" Of the {e['listed']} instruments the made-under record lists, code read the text "
            f"of {read} (their provisions and schedules as made) and searched it for {q}; the "
            f"other {n} could not be read and {'was' if n == 1 else 'were'} not checked.")
