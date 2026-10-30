"""FIX_PLAN P3.34: where a term is defined, across all legislation.

**The defect.** "Every statutory definition of X" was answered from whichever
instruments a Worker happened to search within: on 6341 turn 7 each stored
answer cited 0 to 12 of the instruments that define "shop", 6384 t4 1 to 5 of
5, 6363 t1 0 to 1 of 1 (`notes/batch13_G.md`, `notes/batch12_F.md`). No tool
searched for a definition across the corpus.

**The measurement (batch 13 G, 23 live LEX calls).** `/legislation/section/
search` with no `legislation_id` searches the whole index, and `size` changes
the ranking, not only the page. One call for `"<term>" means` at `size` 300
returned 22 of the 28 defining instruments the stored 6341 runs found (20 under
the four-type filter), 5 of 5 on 6384 and 1 of 1 on 6363, more than any one
stored run on every turn. Raw rows are mostly not definitions (35 of 300 on the
6341 term), so code filters them: a row is kept when its text puts the term in
quotation marks followed by a defining verb. Read by hand, 120 of 120 kept rows
defined the term, and the filter kept 96% of the definitional rows.

**What this module does.** It builds the tool's result from the raw rows
(`build_result`), the block code appends to it for the Worker
(`definitions_note`), and nothing that touches the network: the executor makes
the one call. Never summarised (`run_worker_tool`), so a list is never cut by a
summary that drops instruments from it, and sized by construction to stay under
`DEFINITIONS_WHOLE_CHARS`, which `provider_factory.get_tool_result_threshold`
gives this tool so the chat loops' last-resort cap does not cut it either.

**What it cannot establish:** that no other legislation defines the term. It is
one ranked search: a definition worded another way ("references to a shop are
to ..."), inside a very long provision (a 300,000-character schedule never
ranked in batch 13 G), or outside the 300 rows read is missed. Every text built
here says so, and none says "all definitions".
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

__all__ = [
    "DEFINITIONS_TOOL",
    "DEFINITIONS_ENTRY",
    "DEFINITIONS_SIZE",
    "DEFINITIONS_WHOLE_CHARS",
    "DEFINITIONS_JURISDICTIONS",
    "MAX_LISTED",
    "MAX_LONGER_LISTED",
    "definitions_query",
    "defining_match",
    "longer_term_matches",
    "build_result",
    "definitions_note",
]

DEFINITIONS_TOOL = "find_definitions"
# The scope-record entry's `tool` (`search_scope.record_definitions`).
DEFINITIONS_ENTRY = "definitions_search"
# Batch 13 G decision 3(a): one call at `size` 300. At 100 the 6341 term
# reached 19 of 28, at 300 20 (22 unfiltered); 300 rows are 0.5-1.6 MB, which
# never reach the model.
DEFINITIONS_SIZE = 300
# P3.31's cap (`made_under.MAX_LISTED`): the instruments listed, the rest counted.
MAX_LISTED = 40
MAX_LONGER_LISTED = 15
# The defining words handed over per instrument, cut at a word ("the defining
# clause, cut at the next definition or about 300 characters", batch 13 G).
CLAUSE_CHARS = 300
# The result's size bound, and the threshold `get_tool_result_threshold` gives
# this tool: under the 8,000-character fallback threshold every stored replay
# ran at, the chat loops' cap (threshold + 4,000) would cut a 40-row list.
DEFINITIONS_WHOLE_CHARS = 30_000
# Other provisions of one instrument that define the term, linked, not quoted.
_MAX_ALSO = 3
_MAX_TERM_CHARS = 80

_WS = re.compile(r"\s+")
# Straight and curly, double and single: EU annexes render `‘term’ means`.
_Q = "[“”\"‘’']"
# Inside a quoted phrase: no quotation mark of any kind, a straight apostrophe
# included, or "x'; the term 'y" reads as one phrase.
_NOT_Q = "[^“”\"‘’'\n]"
# Batch 13 G's DEFVERB (terms.py), with "refers to" and "shall be construed"
# added (forms the note listed as untested; synthetic tests cover them).
_DEFVERB = (
    r"\s*(?:,\s*)?(?:\([^)]{0,60}\)\s*)?"
    r"(?:means|includes|include|has the (?:same )?meaning|shall (?:mean|include|have)"
    r"|is to be (?:read|construed|treated)|shall be construed|does not include"
    r"|refers to|in relation to)\b"
)
# A quoted term in a list sharing one verb: `the expressions "x", "shop" and
# "y" have respectively the same meanings as in ...` (batch 13 G's LISTVERB).
_LISTVERB = (
    r"(?P<span>[^.;:\n]{0,150}?)\b(?:means|mean|includes|include"
    r"|ha(?:s|ve)\s+(?:respectively\s+)?the\s+(?:same\s+)?meanings?"
    r"|ha(?:s|ve)\s+the\s+meanings?\s+(?:respectively\s+)?(?:assigned|given))\b"
)
# The list form's span must not be an amendment of someone else's definition
# ('in the definition of "shop", for "x" substitute "y" ... means'): batch 13
# G read 16 such rows among its drops. A guard, not a measured rule.
_AMENDING = re.compile(r"substitut|omit|insert|repeal|for the words", re.I)
# The start of the next definition in a row, where a clause stops.
_NEXT_DEF = re.compile(
    _Q + _NOT_Q + r"{1,80}" + _Q + r"\s*,?\s*(?:\([^)]{0,60}\)\s*)?"
    r"(?:means|includes|has the|shall mean|shall have)\b", re.I)
_CLAUSE_STOPS = ";:\n—"


def _clean_term(term: Any) -> str:
    t = _WS.sub(" ", str(term or "")).strip()
    t = t.strip("“”\"‘’' ")
    return t[:_MAX_TERM_CHARS]


def definitions_query(term: Any) -> str:
    """The one query sent: the quoted term and a defining verb (batch 13 G's F1)."""
    return f'"{_clean_term(term)}" means'


def _term_pattern(term: str) -> str:
    """The term as a regex: flexible whitespace between words, either
    apostrophe, any hyphen, and an optional plural ending."""
    words = []
    for w in _clean_term(term).split(" "):
        parts = []
        for ch in w:
            if ch in "'’":
                parts.append("['’]")
            elif ch in "-‐‑–":
                parts.append("[-‐‑–]")
            else:
                parts.append(re.escape(ch))
        words.append("".join(parts))
    return r"\s+".join(words) + r"(?:s|es)?"


def _strict(term: str) -> "re.Pattern":
    return re.compile(
        _Q + r"\s*" + _term_pattern(term) + r"\s*,?" + _Q
        + r"(?:" + _DEFVERB + r"|" + _LISTVERB + r")", re.I)


def _loose(term: str) -> "re.Pattern":
    return re.compile(
        _Q + r"(?P<phrase>" + _NOT_Q + r"{0,40}\b" + _term_pattern(term) + r"\b"
        + _NOT_Q + r"{0,40})" + _Q + _DEFVERB, re.I)


def defining_match(text: Any, term: str) -> Optional["re.Match"]:
    """The first place `text` defines the bare `term`, or None.

    The term in quotation marks (a comma may sit inside the closing quote),
    followed by a defining verb, or by one within the same clause where the
    term is one of a quoted list. Never raises."""
    try:
        s = str(text or "")
        if not s or not _clean_term(term):
            return None
        for m in _strict(term).finditer(s):
            span = m.groupdict().get("span")
            if span is not None and _AMENDING.search(span):
                continue
            return m
        return None
    except Exception:
        return None


def _norm_phrase(p: str) -> str:
    return _WS.sub(" ", p).strip(" ,").lower()


def longer_term_matches(text: Any, term: str) -> list:
    """[(phrase, match)] for each quoted LONGER term containing `term` that
    `text` defines ("shop premises" when asked "shop"). Never raises."""
    try:
        s = str(text or "")
        bare = _norm_phrase(_clean_term(term))
        bare_re = re.compile(r"^" + _term_pattern(term) + r"$", re.I)
        out, seen = [], set()
        for m in _loose(term).finditer(s):
            phrase = _WS.sub(" ", m.group("phrase")).strip(" ,")
            key = _norm_phrase(phrase)
            if not key or key == bare or bare_re.match(phrase) or key in seen:
                continue
            seen.add(key)
            out.append((phrase, m))
        return out
    except Exception:
        return []


def _cut(text: str, n: int) -> str:
    text = _WS.sub(" ", text).strip()
    if len(text) <= n:
        return text
    cut = text[:n].rsplit(" ", 1)[0].rstrip(" ,;:")
    return (cut or text[:n]) + " …"


def _clause(text: str, m: "re.Match", cap: int) -> str:
    """The defining words around a match, verbatim, cut at a word.

    Starts at the opening of the sentence or list item holding the match where
    that is within 200 characters (`The expression "shop" includes ...`), else
    at the quotation mark; stops before the next definition in the row, at the
    end of the sentence, or at `cap`."""
    start = m.start()
    back = text[max(0, start - 200):start]
    cut_at = max((back.rfind(c) for c in _CLAUSE_STOPS + "."), default=-1)
    if cut_at >= 0:
        start = start - len(back) + cut_at + 1
    # Another term's definition between that opening and this one
    # ('"lease of a dwelling-house" means ..., and "dwelling-house" means'):
    # start at this one, or the cut could keep only the other.
    if _NEXT_DEF.search(text[start:m.start()]):
        start = m.start()
    end = len(text)
    nxt = _NEXT_DEF.search(text, m.end())
    if nxt:
        end = nxt.start()
        semi = text.rfind(";", m.end(), end)
        if semi >= 0:
            end = semi
    stop = re.search(r"\n|\.\s+(?=[A-Z“\"(])", text[m.end():end])
    if stop:
        end = m.end() + stop.start() + (1 if stop.group(0).startswith(".") else 0)
    return _cut(_LEAD.sub("", text[start:end].strip()), cap)


# A list marker left at a clause's start by the cut ("a) ", "2) ", "- ").
_LEAD = re.compile(r"^(?:[-–•]\s+|\(?[a-z0-9]{1,3}\)\s*)", re.I)


def _short_id(value: Any) -> str:
    s = str(value or "").strip()
    s = re.sub(r"^https?://(?:www\.)?legislation\.gov\.uk/", "", s)
    if s.startswith("id/"):
        s = s[3:]
    return s.strip("/")


_PROVISION_PATH = re.compile(
    r"/((?:section|regulation|article|schedule|part|chapter|paragraph|rule|annex"
    r"|crossheading)/.*)$", re.I)


def _provision(row: dict, lid: str) -> str:
    """"section 14", "schedule 1 paragraph 3", from the API's own uri; "" where
    the uri names no provision (the index gave the instrument's own uri)."""
    uri = str(row.get("uri") or row.get("id") or "")
    rest = ""
    if lid and lid.lower() in uri.lower():
        rest = uri[uri.lower().index(lid.lower()) + len(lid):].strip("/")
    if not rest:
        m = _PROVISION_PATH.search(uri)
        rest = m.group(1) if m else ""
    rest = re.sub(r"/(?:made|enacted|contents)$", "", rest).strip("/ .")
    return rest.replace("/", " ")


# An id the index resolves: a type, then two or three path segments, no
# spaces or brackets ("ssi/2013/85", "ukpga/Geo6/12-13-14/25"). The index also
# holds OCR'd records whose id is "[UNCLEAR: ...]" or "S.I. 1948 No. 955", and
# a uri built on such an id is not a working link (batch 13 G: 34 of 300 rows
# on one term had no usable type).
_RESOLVABLE_ID = re.compile(r"^[a-z]{2,6}(?:/[A-Za-z0-9\-]+){2,3}$")


def _resolvable(lid: str) -> bool:
    return bool(_RESOLVABLE_ID.match(lid or ""))


def _stated_extent(row: dict) -> list:
    ext = row.get("extent")
    if isinstance(ext, str):
        ext = [ext]
    return [str(e).strip() for e in (ext or []) if str(e).strip()]


def _jurisdiction_keeps(stated: list, jurisdiction: str, lid: str) -> bool:
    """P1.1's "applies in" rule for a stated extent; an extent the index does
    not state is kept, unless the instrument's own id puts it in another
    jurisdiction (an `nisr/` instrument under a Scotland filter)."""
    from ..agent.tools.lex import _ID_PREFIX_JURISDICTION, _matches_jurisdiction

    if stated:
        return _matches_jurisdiction(stated, jurisdiction, lid)
    if not _resolvable(lid) and re.search(r"N\.\s*I\.|northern.ireland", lid, re.I):
        # An OCR'd Northern Ireland record ("S.R. & O. (N.I.) 1941 No. 188").
        lid = "nisr/" + lid
    if jurisdiction == "uk_wide":
        return lid.split("/")[0].lower() not in _ID_PREFIX_JURISDICTION
    return _matches_jurisdiction([], jurisdiction, lid)


_JURISDICTION_LABELS = {
    "scotland": "Scotland",
    "england_and_wales": "England and Wales",
    "wales": "Wales",
    "northern_ireland": "Northern Ireland",
    "uk_wide": "UK-wide",
}


# The values the tool's optional `jurisdiction` argument takes (the Research
# filter's own values, `_JURISDICTION_ACCEPTS`). The filter, when set, wins.
DEFINITIONS_JURISDICTIONS = tuple(_JURISDICTION_LABELS)


def instrument_ids(rows: Any) -> list:
    """The resolvable instrument ids in the raw rows, for a title lookup."""
    try:
        items = rows if isinstance(rows, list) else (rows or {}).get("results") or []
        out = []
        for r in items:
            lid = _short_id((r or {}).get("legislation_id") or "")
            if _resolvable(lid) and lid not in out:
                out.append(lid)
        return out
    except Exception:
        return []


def jurisdiction_label(j: Optional[str]) -> str:
    return _JURISDICTION_LABELS.get(str(j or ""), str(j or ""))


def _entry(row: dict, lid: str, text: str, m: "re.Match", cap: int, title: str) -> dict:
    stated = _stated_extent(row)
    e = {"legislation_id": lid}
    if title:
        e["title"] = title
    prov = _provision(row, lid)
    if prov:
        e["provision"] = prov
    if _resolvable(lid):
        e["url"] = str(row.get("uri") or row.get("id") or "")
    else:
        # No link, deliberately: it would not resolve, and P1.6 would treat
        # a harvested URL as one the research retrieved.
        e["reference_unclear"] = True
    e["extent"] = ", ".join(stated) if stated else "not stated"
    e["definition"] = _clause(text, m, cap)
    return e


def build_result(rows: Any, term: Any, *, jurisdiction: Optional[str] = None,
                 legislation_type: Optional[str] = None,
                 titles: Optional[dict] = None, year_from=None, year_to=None) -> dict:
    """The tool's result from the raw `/legislation/section/search` rows.

    Grouped by instrument in the order the search returned them; each
    instrument once, with its first defining provision quoted and up to three
    more linked. `jurisdiction` applies P1.1's rule (see `_jurisdiction_keeps`);
    `legislation_type` is the Research filter's category (`_TYPE_CODES`), by id
    prefix, as `search_legislation` applies it. Sized to stay under
    `DEFINITIONS_WHOLE_CHARS`. Never raises: on unexpected input the result
    says no rows were read."""
    clean = _clean_term(term)
    titles = titles or {}
    out = {"tool": DEFINITIONS_TOOL, "term": clean, "query": definitions_query(clean)}
    try:
        items = rows if isinstance(rows, list) else (rows or {}).get("results")
        items = [r for r in (items or []) if isinstance(r, dict)]
    except Exception:
        items = []
    type_codes = None
    if legislation_type:
        from ..agent.tools.lex import _TYPE_CODES
        type_codes = _TYPE_CODES.get(legislation_type)

    out["rows_read"] = len(items)
    if jurisdiction:
        out["jurisdiction"] = jurisdiction_label(jurisdiction)
    if year_from or year_to:
        out["years"] = f"{year_from or 'any'}-{year_to or 'any'}"

    found: dict = {}        # instrument key -> {"row", "text", "m", "also": [...]}
    longer: dict = {}       # (instrument key, phrase key) -> {...}
    removed: set = set()
    for row in items:
        text = str(row.get("text") or "")
        lid = _short_id(row.get("legislation_id") or "")
        if not lid:
            lid = _short_id(re.sub(_PROVISION_PATH, "", str(row.get("uri") or "")))
        key = lid.lower()
        if not key:
            continue
        m = defining_match(text, clean)
        lms = longer_term_matches(text, clean)
        if not m and not lms:
            continue
        if type_codes is not None and key.split("/")[0] not in type_codes:
            if m:
                removed.add(key)
            continue
        if jurisdiction and not _jurisdiction_keeps(_stated_extent(row), jurisdiction, lid):
            if m:
                removed.add(key)
            continue
        if m:
            if key in found:
                url = str(row.get("uri") or row.get("id") or "")
                also = found[key]["also"]
                if (url and _resolvable(lid) and url != found[key]["url"] and url not in also
                        and len(also) < _MAX_ALSO):
                    also.append(url)
            else:
                found[key] = {"row": row, "lid": lid, "text": text, "m": m, "also": [],
                              "url": str(row.get("uri") or row.get("id") or "")}
        for phrase, lm in lms:
            lk = (key, _norm_phrase(phrase))
            if lk not in longer:
                longer[lk] = {"row": row, "lid": lid, "text": text, "m": lm, "phrase": phrase}

    removed -= set(found)
    insts = list(found.values())
    longs = list(longer.values())
    out["count"] = len(insts)
    out["extent_not_stated"] = sum(1 for f in insts if not _stated_extent(f["row"]))
    unclear = sum(1 for f in insts if not _resolvable(f["lid"]))
    if unclear:
        out["reference_unclear"] = unclear
    if removed:
        out["removed_by_filters"] = len(removed)
    out["longer_terms_count"] = len(longs)

    def _render(cap: int, n_listed: int, n_longer: int) -> dict:
        res = dict(out)
        defs = []
        for f in insts[:n_listed]:
            e = _entry(f["row"], f["lid"], f["text"], f["m"], cap,
                       titles.get(f["lid"]) or titles.get(f["lid"].lower()) or "")
            if f["also"]:
                e["also_defined_in"] = list(f["also"])
            defs.append(e)
        res["listed"] = len(defs)
        res["definitions"] = defs
        lt = []
        for g in longs[:n_longer]:
            e = _entry(g["row"], g["lid"], g["text"], g["m"], cap,
                       titles.get(g["lid"]) or titles.get(g["lid"].lower()) or "")
            lt.append({"term": g["phrase"][:_MAX_TERM_CHARS], **e})
        res["longer_terms"] = lt
        return res

    # Shrink until it fits: the clause cap first, then the longer terms, then
    # the list (its count stays the full count).
    plans = [(CLAUSE_CHARS, MAX_LISTED, MAX_LONGER_LISTED), (220, MAX_LISTED, MAX_LONGER_LISTED),
             (160, MAX_LISTED, 8), (160, MAX_LISTED, 0), (120, 30, 0), (120, 20, 0)]
    res = None
    for cap, n, nl in plans:
        res = _render(cap, n, nl)
        if len(json.dumps(res, ensure_ascii=False)) + 2_500 <= DEFINITIONS_WHOLE_CHARS:
            break
    return res


def _quote_safe(s: Any) -> str:
    """No square brackets inside a block (`strip_scope_blocks`' `[^\\[\\]]*`)."""
    return str(s or "").replace("[", "(").replace("]", ")")


def parse_result(raw: Any) -> Optional[dict]:
    """The tool's own result, or None. `raw_decode`, so a result carrying the
    appended block still parses."""
    try:
        d = (json.JSONDecoder().raw_decode(raw.lstrip())[0]
             if isinstance(raw, str) else raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(d, dict) or d.get("tool") != DEFINITIONS_TOOL:
        return None
    return d


def definitions_note(raw_result: Any) -> str:
    """The block appended to a `find_definitions` result, for the Worker.

    A SEARCH SCOPE block by name, so `strip_scope_blocks` removes it from what
    the legal professional reads if a model copies it. Permits exactly what the
    filter established (each listed instrument defines the term as quoted) and
    names the edge of the search. "" for anything that is not the tool's result
    (an error string)."""
    d = parse_result(raw_result)
    if d is None:
        return ""
    term = _quote_safe(d.get("term"))
    query = _quote_safe(d.get("query"))
    rows = int(d.get("rows_read") or 0)
    n = int(d.get("count") or 0)
    head = (f"\n\n[SEARCH SCOPE — definitions search: code searched all legislation in the "
            f"index once, for {query}, and read the {rows} provisions that matched it best")
    if not rows:
        head = (f"\n\n[SEARCH SCOPE — definitions search: code searched all legislation in "
                f"the index once, for {query}, and it returned no provisions")
    if not n:
        none_kept = (f". None of them puts \"{term}\" in quotation marks followed by a defining "
                     "word") if rows else ""
        return (
            head + none_kept + ". That is a statement about this one search, NOT evidence "
            "that no legislation defines the term: say what was searched, and look for a "
            "definition in the instruments the question concerns with "
            "search_legislation_sections.]"
        )
    listed = int(d.get("listed") or 0)
    more = (f" Only {listed} of the {n} are listed here; say how many there are, and that the "
            "list shown is not all of them.") if listed < n else ""
    juris = ""
    gone = int(d.get("removed_by_filters") or 0)
    if d.get("jurisdiction"):
        j = _quote_safe(d["jurisdiction"])
        juris = (f" The {j} filter applies: an instrument whose stated extent does not include "
                 f"{j} was left out, and one whose extent the index does not state was kept "
                 f"and is marked 'not stated' ({int(d.get('extent_not_stated') or 0)} listed); "
                 f"{gone} instrument(s) were left out by the filters.")
    elif gone:
        juris = f" {gone} instrument(s) outside the legislation type filter were left out."
    unclear = ""
    if d.get("reference_unclear"):
        unclear = (f" {int(d['reference_unclear'])} instrument(s) are marked "
                   "reference_unclear: the index does not identify them reliably and gives no "
                   "working link, so name each only as its legislation_id records it, and say so.")
    longer = ""
    lc = int(d.get("longer_terms_count") or 0)
    if lc:
        shown = len(d.get("longer_terms") or [])
        cut = f" ({shown} shown)" if shown < lc else ""
        longer = (f" {lc} definition(s) of longer terms containing \"{term}\"{cut} are listed "
                  "apart under longer_terms: they were found in the same provisions, not "
                  "searched for, so never present them as complete.")
    return (
        head + f", and kept those whose text puts \"{term}\" in quotation marks followed by a "
        f"defining word (means, includes, has the meaning and the like). {n} instrument(s) "
        "define it there, listed in the order the search returned them, each with its defining "
        "words verbatim (cut at a word where long), its provision link and the extent the index "
        "states ('not stated' where it states none, which does not mean the instrument applies "
        f"everywhere).{more}{juris}{unclear}{longer} You MAY state that each listed instrument defines "
        "the term in the words quoted, citing its provision link. This is one search, not a "
        "census: a definition worded another way, inside a very long provision, or outside the "
        "provisions read may be missing, so never call this list every definition of the term, "
        "and never say that no other legislation defines it. An instrument listed without a "
        "title is named by its legislation_id only: take its title from a retrieval, never "
        "from memory.]"
    )
