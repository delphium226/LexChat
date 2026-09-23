"""Provision-link enforcement (FIX_PLAN P1.6, bucket B14).

**The problem this solves, stated precisely.** A legislation.gov.uk provision URL
that no tool returned still *resolves* — `.../asp/2000/1/section/21` is a real
page whatever the research did — so a manufactured link reads to a lawyer exactly
like a verified citation and survives every link-check the sources rail supports.
That is why B14 is a correctness bucket and not a formatting one.

P1.4 removed the *instruction* to manufacture (`WORKER_SYSTEM_PROMPT` used to say
"you MUST manually append `/section/{number}` to the Base URI") and handed the
model the API's own provision URL instead. Measured over the replay corpus, links
pointing at a provision **no tool ever retrieved** went 75 -> 0. What remains is
the mechanism, not the outcome: in 19% of cited provision links the model is still
*reconstructing* the URL rather than copying one, because the retrieval that
carried it was summarised and the summariser does not keep URLs. It happens to
reconstruct correctly today. Nothing makes it do so.

Invariant 2 (code enforcement over prompt obedience) therefore gives two halves,
and this module holds both:

* **`provision_url_block`** - the cause. Appended *after* summarisation, exactly
  like the Phase-2 nudge and for exactly the same reason: the summariser cannot
  eat what it never saw. The model then copies a URL instead of rebuilding one.
* **`enforce_provision_links`** - the guarantee. At the seam where an answer is
  assembled, any provision-level legislation.gov.uk link whose URL was never
  returned by a tool in this run is demoted to the Act (when the Act *was*
  retrieved) or unlinked, and marked.

**Why this does not simply strip links.** When the model genuinely holds only the
Act, linking the Act is *correct* - the error is the label naming a provision as
though it had been verified. Stripping the link would trade a bad link for a bad
claim, which is the same trade in the other direction.

**Why the marker is a footnote and not prose.** The only thing we can state with
certainty is that no tool returned a URL for this citation. We cannot say the
provision was "not retrieved": a whole-Act `get_legislation_text` carries one URL
for the Act and none for its sections, so the text may well have been read.
Invariant 1 says a disclosure must be TRUE, so the wording asserts what is known
about the *link* and claims nothing about the research.
"""

from __future__ import annotations

import json
import re
from typing import Iterable, Optional

import logging

logger = logging.getLogger("agent")

__all__ = [
    "normalise_leg_url",
    "is_provision_url",
    "act_base_url",
    "harvest_legislation_urls",
    "provision_url_block",
    "enforce_provision_links",
    "link_sibling_pinpoints",
    "restore_dropped_siblings",
    "PROVISION_MARKER",
    "PROVISION_FOOTNOTE",
]

_LEG_HOST = "legislation.gov.uk"

# Markdown inline link. Bounded label so a stray unmatched bracket cannot make
# the scan quadratic over a long report.
_MD_LINK = re.compile(r"\[([^\]\n]{1,300})\]\((https?://[^)\s]+)\)")

# The path segments legislation.gov.uk uses below an instrument. `paragraph` and
# `crossheading` only ever appear beneath one of the others, but they are listed
# so a deep URL is still recognised as provision-level.
_PROVISION_SEGMENT = re.compile(
    r"/(?:section|regulation|article|schedule|rule|order|chapter|part|paragraph|crossheading)/",
    re.I,
)

# Trailing punctuation a model routinely glues onto a URL inside prose.
_URL_TRAILING = ".,;:)]}'\"“”’"

PROVISION_MARKER = "†"
PROVISION_FOOTNOTE = (
    "† No provision-level URL was returned by any search for this citation; "
    "where a link is shown it points at the instrument as a whole."
)


def normalise_leg_url(url: str) -> str:
    """Reduce a legislation.gov.uk URL to a comparable key.

    Four spellings of the same resource are in play at once and every one of
    them appears in real traffic:

      * `http://` and `https://` - LEX returns `http://`, models emit `https://`;
      * with and without `www.`;
      * with and without the `/id/` segment - `legislation/search` returns the
        short form and `legislation/section/search` a full `/id/` URI;
      * with and without a trailing slash, and with prose punctuation stuck on.

    Comparing raw strings would report a URL as manufactured because the model
    upgraded the scheme. Returns "" for anything that is not legislation.gov.uk,
    which is the caller's signal to leave the link alone.
    """
    if not url:
        return ""
    s = str(url).strip().rstrip(_URL_TRAILING)
    s = re.sub(r"^https?://", "", s, flags=re.I)
    if _LEG_HOST not in s.lower():
        return ""
    s = re.sub(r"^www\.", "", s, flags=re.I)
    s = s.split("#", 1)[0].split("?", 1)[0]
    s = s.replace("/id/", "/", 1)
    return s.rstrip("/").lower()


def is_provision_url(url: str) -> bool:
    """Does this URL point below the level of a whole instrument?"""
    key = normalise_leg_url(url)
    return bool(key) and bool(_PROVISION_SEGMENT.search("/" + key))


def act_base_url(url: str) -> str:
    """`.../asp/2000/1/section/21` -> `.../asp/2000/1`, normalised.

    Returns "" when the URL is not a legislation.gov.uk provision URL.
    """
    key = normalise_leg_url(url)
    if not key:
        return ""
    m = _PROVISION_SEGMENT.search("/" + key)
    if not m:
        return ""
    # The match ran against a leading "/" we prepended, so subtract it.
    return key[: m.start()].rstrip("/")


def _walk(obj, out: set) -> None:
    if isinstance(obj, dict):
        for v in obj.values():
            if isinstance(v, str) and _LEG_HOST in v.lower():
                key = normalise_leg_url(v)
                if key:
                    out.add(key)
            else:
                _walk(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _walk(v, out)


def _loads_prefix(raw):
    """Parse the JSON value a tool result *starts* with.

    `run_worker_tool` appends the Phase-2 nudge after the JSON, so a plain
    `json.loads` raises "Extra data" on exactly the calls that returned results -
    the successful ones.
    """
    if not isinstance(raw, str):
        return raw if isinstance(raw, (dict, list)) else None
    try:
        obj, _ = json.JSONDecoder().raw_decode(raw.lstrip())
        return obj
    except Exception:
        return None


def harvest_legislation_urls(raw_result, into: Optional[set] = None) -> set:
    """Every legislation.gov.uk URL a raw tool result carried, normalised.

    Harvested from the **raw** result, before summarisation - that is the whole
    point. The question this set answers is "did the research retrieve this
    provision", not "was the model shown the string", and the two diverge on
    precisely the ~70% of section searches that get summarised.

    Deliberately recursive and key-agnostic: the two LEX endpoints spell the
    identifier three ways (`uri`, `id`, `url`) and a future tool will spell it a
    fourth. Fail-soft - an unparseable result contributes nothing rather than
    raising into a research run.
    """
    out = into if into is not None else set()
    try:
        parsed = _loads_prefix(raw_result)
        if parsed is not None:
            _walk(parsed, out)
    except Exception:  # pragma: no cover - defensive
        logger.debug("[Citations] URL harvest skipped", exc_info=True)
    return out


def provision_url_block(raw_result, max_entries: int = 12) -> str:
    """The citation-URL block appended after a summarised section retrieval.

    Summarisation turns a 32K `search_legislation_sections` response into ~3.5K
    of prose that names the sections and carries no URLs at all, so the model -
    forbidden from inventing a URL and holding none - reconstructs one from the
    Act's base URI. This hands the URLs back.

    Appended after summarisation for the same reason the Phase-2 nudge is (see
    `run_worker_tool`): the summariser cannot discard what it never saw. Returns
    "" when the result carries no provision URLs, so the caller may append
    unconditionally.
    """
    parsed = _loads_prefix(raw_result)
    if not isinstance(parsed, dict):
        return ""
    results = parsed.get("results")
    if not isinstance(results, list):
        return ""

    lines: list = []
    seen: set = set()
    for item in results:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or item.get("uri") or "")
        if not url or not is_provision_url(url):
            continue
        key = normalise_leg_url(url)
        if key in seen:
            continue
        seen.add(key)
        ptype = str(item.get("provision_type") or "").strip()
        number = item.get("number")
        label = " ".join(
            p for p in (ptype, str(number) if number is not None else "") if p
        )
        lines.append(f"- {label or 'provision'}: {url}")
        if len(lines) >= max_entries:
            break

    if not lines:
        return ""
    return (
        "\n\n[CITATION URLS - these are the URLs this retrieval returned. Use them "
        "verbatim when citing these provisions. Do NOT build a provision URL from "
        "an Act's base URI; if a provision you want to cite is not listed here, "
        "cite it in bold text without a link.]\n" + "\n".join(lines)
    )


# A citation label that names a subdivision: "s.57(3)(a)", "section 21(2)",
# "Sch 2 para 3(1)", "reg. 4(3)". The bare "s.57" does not match: that is what
# the block below exists to keep from replacing it.
_PINPOINT = re.compile(
    r"\b(?:ss?\.|sections?|reg(?:ulation)?s?\.?|art(?:icle)?s?\.?|"
    r"para(?:graph)?s?\.?|sch(?:edule)?\.?)\s*\d+[A-Za-z]*"
    r"(?:\s*,?\s*para(?:graph)?\.?\s*\d+[A-Za-z]*)?"
    r"(?:\s?\((?:\d+[A-Za-z]{0,2}|[a-z]{1,4})\))+",
    re.I,
)

PINPOINT_BLOCK_OPEN = "[PINPOINTS TO KEEP"
PINPOINT_BLOCK_CLOSE = "[/PINPOINTS TO KEEP]"


def pinpoint_block(texts, max_urls: int = 12, max_each: int = 6) -> str:
    """The pinpoints the Deep Research step findings used, for the synthesis.

    **FIX_PLAN P3.1 (B10), the synthesis seam.** Measured on 6365: the steps
    cite at subsection depth (`[... - s.57(3)(a)](.../section/57)`) and the
    synthesis rewrote every label to the bare section (`[... - s.57](...)`) -
    HEAD's baseline rep 2 went from 4 of 20 references at depth to 0 of 10, and
    the smoke run on the prompt fix alone did the same. The link target stops at
    the section, so a model that writes its label from the URL loses the
    pinpoint. This hands the synthesis, per section URL, the pinpoints the
    findings attached to it - P1.6's pattern of putting the data where the
    model writes, keyed on the URL rather than on prose (user decision,
    Session 16, over a repair call).

    Only links count: a link is the one citation whose provision the URL makes
    unambiguous. Returns "" when no finding carries a pinpointed link, so the
    caller may append unconditionally. Fail-soft.
    """
    try:
        by_url: dict = {}
        for text in list(texts or []):
            for label, url in _MD_LINK.findall(str(text or "")):
                if not is_provision_url(url):
                    continue
                pins = [re.sub(r"\s+", " ", m.group(0)).strip()
                        for m in _PINPOINT.finditer(label)]
                if not pins:
                    continue
                key = normalise_leg_url(url)
                shown, have = by_url.setdefault(
                    key, (url.strip().rstrip(_URL_TRAILING), []))
                for p in pins:
                    if p.lower() not in {h.lower() for h in have}:
                        have.append(p)
        if not by_url:
            return ""
        lines = [f"- {shown}: " + "; ".join(pins[:max_each])
                 for shown, pins in list(by_url.values())[:max_urls]]
        return (
            "\n\n" + PINPOINT_BLOCK_OPEN + " - the step findings cite these "
            "sections at subsection level. When your report cites one of these "
            "URLs, its label must name the subsection that states the point, as "
            "the findings do (s.12(3), not s.12). Never shorten a pinpoint to the "
            "bare section.]\n" + "\n".join(lines) + "\n" + PINPOINT_BLOCK_CLOSE
        )
    except Exception:  # pragma: no cover - defensive
        logger.debug("[Citations] pinpoint block skipped", exc_info=True)
        return ""


# An unlinked pinpoint whose type maps onto a URL segment: "s.36(2)",
# "section 36(2)(a)", "reg. 4(3)", "art. 2(1)". It must carry at least one
# bracketed subdivision - a bare "s.36" is a section, which is what the link
# the report already carries says; it is not a sibling. Schedules and
# paragraphs are left out: a Schedule's URL is `/schedule/1` and its
# paragraphs are not sections of anything (P3.12).
_SIBLING_PIN = re.compile(
    r"\b(?P<kind>s\.|section|reg\.|regulation|art\.|article)\s?"
    r"(?P<num>\d+[A-Z]{0,2})"
    r"(?P<sub>(?:\s?\((?:\d+[A-Za-z]{0,2}|[a-z]{1,4})\))+)",
    re.I,
)
_SIBLING_SEGMENT = {"s.": "section", "section": "section", "reg.": "regulation",
                    "regulation": "regulation", "art.": "article", "article": "article"}
# An instrument named in plain words, outside any link: "Order 1963",
# "Regulations 2004", "the 2002 Act", "Regulation (EC) No 1069/2009",
# "SSI 2004/520", "asp/2002/13". Which instrument it is cannot be known, so it
# only ever blocks a link, never licenses one.
_PLAIN_INSTRUMENT = re.compile(
    r"\b(?:Act|Order|Regulations|Rules|Measure|Directive)\s+\d{4}\b"
    r"|\b\d{4}\s+(?:Act|Order|Regulations|Rules)\b"
    r"|\((?:EC|EU|EEC)\)\s*No\.?\s*\d+/\d{4}"
    r"|\b(?:Regulation|Directive|Decision)\s+(?:No\.?\s*)?\d+/\d{4}"
    r"|\b(?:S\.?S\.?I\.?|S\.?I\.?)\s*\d{4}/\d+"
    r"|\b(?:asp|ukpga|ssi|uksi|nisr|nia|anaw|asc|wsi|eur)/\d{4}/\d+",
    re.I,
)
# "s.36(2) of the ...": the instrument named straight after a pinpoint is the
# one it belongs to, whatever came before it.
_NAMED_AFTER = re.compile(r"\s*,?\s*(?:of|in|under)\s+(?:the\s+)?(?=\S)")
_SCOPE_OPEN = "\n\n[SEARCH SCOPE"


def _instrument_refs(para: str, masked: str) -> list:
    """(start, end, instrument key or None) for every instrument reference in a
    paragraph: each legislation link (keyed on its instrument) and each plain
    title (None: unknown)."""
    refs = []
    for m in _MD_LINK.finditer(para):
        key = normalise_leg_url(m.group(2))
        if key:
            refs.append((m.start(), m.end(), act_base_url(m.group(2)) or key))
    links = list(refs)
    for m in _PLAIN_INSTRUMENT.finditer(masked):
        # "[s.36(1)](...) of the Freedom of Information (Scotland) Act 2002":
        # a title written straight after a link, joined by "of the", names the
        # link's own instrument, so it takes the link's key.
        key = None
        prior = [r for r in links if r[1] <= m.start()]
        if prior:
            gap = masked[prior[-1][1]:m.start()]
            if (_NAMED_AFTER.match(gap) and not re.search(r"[.;:\x00]", gap)
                    and len(gap) <= 120):
                key = prior[-1][2]
        refs.append((m.start(), m.end(), key))
    return sorted(refs)


def _owning_instrument(refs: list, start: int, end: int, masked: str):
    """The instrument a pinpoint at [start, end) belongs to: the one named
    straight after it if there is one, else the nearest reference before it,
    else the nearest after it. False when there is no reference at all."""
    after = _NAMED_AFTER.match(masked, end)
    if after:
        # The first reference in the same clause after "of the": a title match
        # starts at "Act 2018" in "of the Data Protection Act 2018", not at
        # "Data", so it is looked for up to the clause's end, not at one offset.
        named = [r for r in refs if r[0] >= after.end()]
        if named:
            gap = masked[after.end():named[0][0]]
            if len(gap) <= 100 and not re.search(r"[.;:,]", gap):
                return named[0][2]
    before = [r for r in refs if r[1] <= start]
    if before:
        return before[-1][2]
    later = [r for r in refs if r[0] >= end]
    return later[0][2] if later else False


def link_sibling_pinpoints(text: str, retrieved: Optional[Iterable[str]] = None) -> tuple:
    """Link each unlinked pinpoint to the section URL the same paragraph already
    links for that section. Returns (text, linked).

    **FIX_PLAN P3.13 (B10), the conversational Manager seam.** The quick-lookup
    Worker cites a subsection with a link (`[s.36(1)](.../section/36)`) and
    states its sibling in plain words ("s.36(2) exempts information obtained
    from another person..."), because both subsections share one URL. The
    conversational Manager is told to keep each provision the Worker cites
    "with its link", and over every replayed run it kept a sibling subsection
    it had been handed as a link 58 times in 60 and one handed as plain text 70
    in 104 - 6348 turn 1's s.36(2) among the drops. Linking the sibling hands it
    to the Manager as a citation, the form it keeps. P1.6's pattern: put the
    data in the shape the model already honours rather than add a rule.

    Only links to a URL the report already carries, in the same paragraph, for
    the same section number and provision type; never builds a URL. Skipped,
    so the text is left alone, when that paragraph links two different URLs for
    the section; when the pinpoint does not belong to the URL's instrument - the
    instrument named straight after it ("s.36(2) of the Data Protection Act
    2018"), else the nearest instrument reference before it, must be that
    instrument, and a title in plain words counts as an unknown instrument
    unless it directly follows the link it restates ("[s.36(1)](...) of the
    Freedom of Information (Scotland) Act 2002"); when `retrieved` is given
    and does not hold the URL; and anywhere in the search-scope block.

    Checked over every recorded worker report before it shipped (Session 22):
    it would have added 102 links to 63 of the 777 conversational reports in
    the 35 replay directories, every one read in context, and the one a first
    draft got wrong - a list of Use Classes Orders where the 1963 Order's
    s.2(2) took the 1950 Order's s.2 URL - is what the instrument rule is for.
    Idempotent and fail-soft.
    """
    if not text:
        return text, 0
    try:
        retrieved_keys = (None if retrieved is None else
                          {k for k in (normalise_leg_url(u) for u in retrieved) if k})
        cut = text.find(_SCOPE_OPEN)
        body, tail = (text, "") if cut < 0 else (text[:cut], text[cut:])
        linked = 0
        out = []
        for para in re.split(r"(\n\s*\n)", body):
            # (segment, number) -> {normalised key: URL as written}
            urls: dict = {}
            for _label, url in _MD_LINK.findall(para):
                m = re.search(r"/(section|regulation|article)/(\d+[a-z]{0,2})/?$",
                              normalise_leg_url(url))
                if m and not re.search(r"/schedule/", normalise_leg_url(url)):
                    urls.setdefault((m.group(1), m.group(2).lower()), {})[
                        normalise_leg_url(url)] = url.strip().rstrip(_URL_TRAILING)
            if not urls:
                out.append(para)
                continue
            # Mask existing links so a pinpoint inside a label or URL is never
            # matched; the masks keep offsets, so the edits map straight back.
            masked = _MD_LINK.sub(lambda m: "\x00" * len(m.group(0)), para)
            refs = _instrument_refs(para, masked)
            edits = []
            for m in _SIBLING_PIN.finditer(masked):
                key = (_SIBLING_SEGMENT[m.group("kind").lower()], m.group("num").lower())
                cands = urls.get(key) or {}
                if len(cands) != 1:
                    continue
                (norm, url), = cands.items()
                # The pinpoint must belong to the instrument the URL is for: a
                # list that runs "Order 1950 - [s.2](...) / Order 1963 - s.2(2)"
                # would otherwise hand the 1963 Order's s.2(2) the 1950 Order's
                # URL, a real page for the wrong instrument (Invariant 1).
                if _owning_instrument(refs, m.start(), m.end(), masked) != act_base_url(url):
                    continue
                if retrieved_keys is not None and norm not in retrieved_keys:
                    continue
                edits.append((m.start(), m.end(), url))
            for start, end, url in reversed(edits):
                para = f"{para[:start]}[{para[start:end]}]({url}){para[end:]}"
            linked += len(edits)
            out.append(para)
        return "".join(out) + tail, linked
    except Exception:  # pragma: no cover - defensive
        logger.debug("[Citations] sibling linking skipped", exc_info=True)
        return text, 0


_SECTION_URL = re.compile(r"/(section|regulation|article)/(\d+[a-z]{0,2})/?$")
_NOTE_LABEL = {"section": "s.", "regulation": "reg. ", "article": "art. "}
_FIRST_SUB = re.compile(r"\s?\((\w+)\)")
# "subsection (2)", "subsections (1) and (2)": a sibling the answer kept in words.
_SUBSECTION_WORDS = re.compile(
    r"\bsub-?sections?\s*((?:\(\w+\)(?:\s*(?:,|and|or|to|-|–)\s*)?)+)", re.I)
# Where a sentence ends: after . ! ? and before what can open the next one. A
# pinpoint's "s.36" has no space after its dot, so it never splits here.
_SENTENCE_END = re.compile(
    r"(?:(?<=[.!?])|(?<=[.!?][\"'”’)]))\s+(?=[A-Z\x00*(\[])")
# Where a clause of one sentence ends and the next begins ("..., while s.36(2)").
# Never at ", and": that splits a list ("(the First Minister, Ministers, and
# the Lord Advocate)") as readily as a clause.
_CLAUSE_CUT = re.compile(r";\s+|,\s+(?=(?:while|whereas|but)\b)|\s+(?=(?:while|whereas)\b)")
# "126(6) to (8)", "36(1)-(3)": a range of subsections the answer names.
_SUB_RANGE = re.compile(r"(\d+[A-Za-z]{0,2})\s?\((\d+)\)\s*(?:to|-|–)\s*\((\d+)\)")
_CONTENT_WORD = re.compile(r"[a-z]{4,}")
_LEAD_IN = re.compile(
    r"^(?:while|whereas|but|and|additionally|furthermore|separately|also|"
    r"in addition|moreover)\b[,\s]*", re.I)
_MAX_NOTE_CHARS = 450


def _section_key(url: str):
    """(normalised URL, provision type, number) for a section/regulation/
    article URL, else None. Schedules are never a sibling's section (P3.12)."""
    norm = normalise_leg_url(url)
    m = _SECTION_URL.search(norm) if norm else None
    if not m or "/schedule/" in norm:
        return None
    return norm, m.group(1), m.group(2)


def _mask_links(text: str) -> str:
    return _MD_LINK.sub(lambda m: "\x00" * len(m.group(0)), text)


def _clause_around(body: str, start: int, end: int) -> str:
    """The Worker's own words about the link at [start, end): the parenthetical
    it sits in when that says something, else the clause of its sentence.
    "" when there is no clean cut."""
    masked = _mask_links(body)
    ls = body.rfind("\n", 0, start) + 1
    le = body.find("\n", end)
    le = len(body) if le < 0 else le
    s0, s1 = ls, le
    for m in _SENTENCE_END.finditer(masked, ls, le):
        if m.end() <= start:
            s0 = m.end()
        elif m.start() >= end:
            s1 = m.start()
            break
    # An enclosing parenthesis, matched on the masked text so a URL's or a
    # pinpoint's brackets never count.
    depth, open_at = 0, None
    for i in range(start - 1, s0 - 1, -1):
        c = masked[i]
        if c == ")":
            depth += 1
        elif c == "(":
            if depth == 0:
                open_at = i
                break
            depth -= 1
    if open_at is not None:
        depth, close_at = 0, None
        for i in range(end, s1):
            c = masked[i]
            if c == "(":
                depth += 1
            elif c == ")":
                if depth == 0:
                    close_at = i
                    break
                depth -= 1
        if close_at is not None:
            inner = body[open_at + 1:close_at]
            # "(...[s.36(2)](url))" after a statement is a citation, not a clause.
            if len(re.findall(r"[A-Za-z]{2,}", _mask_links(inner))) >= 4:
                s0, s1 = open_at + 1, close_at
    c0, c1 = s0, s1
    for m in _CLAUSE_CUT.finditer(masked, s0, s1):
        if m.end() <= start:
            c0 = m.end()
        elif m.start() >= end:
            c1 = m.start()
            break
    clause = body[c0:c1].strip().rstrip(";,:").strip()
    clause = _LEAD_IN.sub("", clause).strip()
    if not clause or len(clause) > _MAX_NOTE_CHARS or "\x00" in clause:
        return ""
    bare = _mask_links(clause)
    if bare.count("(") != bare.count(")") or bare.count('"') % 2:
        return ""
    if len(re.findall(r"[A-Za-z]{2,}", _mask_links(clause))) < 4:
        return ""
    clause = clause[0].upper() + clause[1:] if clause[0].isalpha() else clause
    return clause if clause.endswith((".", "!", "?")) else clause + "."


def restore_dropped_siblings(answer: str, reports, max_notes: int = 3) -> tuple:
    """Put back a sibling subsection the Manager dropped from its Worker's
    report. Returns (answer, notes added).

    **FIX_PLAN P3.13 (B10), the answer seam.** Linking the sibling
    (`link_sibling_pinpoints`), with a CITATION PRESERVATION clause then in
    the prompt, still left the conversational Manager flattening 6348's
    s.36(2) at a rate (rep 1 of `wave3_p313`: a two-Act bullet list keeping
    s.36(1) only). Invariant 2's last step is to make it so, and with this in
    place the clause was taken out again (it moved the Manager's first
    delegation brief, see the P3.13 row). Where the answer cites a section at
    subsection level (s.N(j), linked to the section's URL, or in plain words
    when every section link in the reports is to one instrument) and a
    report handed to the Manager cites another subsection of that section as
    a link, s.N(k), and the answer mentions s.N(k) nowhere, the report's own
    words about s.N(k) are placed after the answer paragraph that cites the
    section, as "Also in s.N: ...".

    **The text is the Worker's, verbatim** - the clause or parenthetical the
    link sits in, lead-in connective dropped - so nothing is generated and the
    link inside it is one a tool returned. Nothing is added when the answer
    does not cite the section at subsection level (dropping the whole section
    is a different failure), when the words cannot be cut out cleanly, or
    beyond `max_notes`. The scope block is never read. Fail-soft.
    """
    if not answer or not reports:
        return answer, 0
    try:
        # What the answer cites, per section URL: the first-level subsections
        # its links name, and where the first such link sits.
        cited: dict = {}
        for m in _MD_LINK.finditer(answer):
            key = _section_key(m.group(2))
            if not key:
                continue
            shown = re.search(r"/(?:section|regulation|article)/([^/?#)\s]+)", m.group(2))
            entry = cited.setdefault(key[0], {"key": key, "subs": set(), "at": m.start(),
                                              "num": shown.group(1) if shown else key[2]})
            for p in _SIBLING_PIN.finditer(m.group(1)):
                if p.group("num").lower() == key[2]:
                    sub = _FIRST_SUB.match(p.group("sub"))
                    if sub:
                        entry["subs"].add(sub.group(1).lower())
        cited = {k: v for k, v in cited.items() if v["subs"]}
        masked_answer = _mask_links(answer)
        # A Manager that drops every link still cites in plain words ("section
        # 36(1) of the ... Act"; `wave3_p311_conv` rep 2 on the seam). Such a
        # pinpoint cites the reports' section URL only when every section-level
        # link in the reports is to ONE instrument, so a plain "s.36(1)" can
        # never be matched to another Act's s.36.
        by_num: dict = {}
        instruments = set()
        for report in list(reports):
            for m in _MD_LINK.finditer((report or "").split(_SCOPE_OPEN, 1)[0]):
                key = _section_key(m.group(2))
                if key:
                    instruments.add(act_base_url(m.group(2)))
                    by_num.setdefault((key[1], key[2]), {})[key[0]] = m.group(2)
        if len(instruments) == 1:
            for p in _SIBLING_PIN.finditer(masked_answer):
                kind = _SIBLING_SEGMENT[p.group("kind").lower()]
                urls = by_num.get((kind, p.group("num").lower())) or {}
                sub = _FIRST_SUB.match(p.group("sub"))
                if len(urls) != 1 or not sub:
                    continue
                (url_key, url), = urls.items()
                entry = cited.setdefault(url_key, {
                    "key": _section_key(url), "subs": set(), "at": p.start(),
                    "num": p.group("num")})
                entry["subs"].add(sub.group(1).lower())
                entry["at"] = min(entry["at"], p.start())
        if not cited:
            return answer, 0
        # Subsections the answer names in plain words count as kept.
        plain: dict = {}
        for p in _SIBLING_PIN.finditer(masked_answer):
            sub = _FIRST_SUB.match(p.group("sub"))
            if sub:
                plain.setdefault(p.group("num").lower(), set()).add(sub.group(1).lower())
        words = {s.lower() for m in _SUBSECTION_WORDS.finditer(masked_answer)
                 for s in re.findall(r"\((\w+)\)", m.group(1))}
        for m in _SUB_RANGE.finditer(answer):
            lo, hi = int(m.group(2)), int(m.group(3))
            if 0 < hi - lo <= 20:
                plain.setdefault(m.group(1).lower(), set()).update(
                    str(i) for i in range(lo, hi + 1))
        sentences = [set(_CONTENT_WORD.findall(s.lower()))
                     for s in _SENTENCE_END.split(masked_answer)]

        notes: dict = {}   # section URL -> [clause, ...]
        seen: set = set()
        total = 0
        for report in list(reports):
            body = (report or "").split(_SCOPE_OPEN, 1)[0]
            for m in _MD_LINK.finditer(body):
                key = _section_key(m.group(2))
                if not key or key[0] not in cited:
                    continue
                entry = cited[key[0]]
                for p in _SIBLING_PIN.finditer(m.group(1)):
                    if p.group("num").lower() != key[2]:
                        continue
                    sub = _FIRST_SUB.match(p.group("sub"))
                    k = sub.group(1).lower() if sub else ""
                    if (not k or k in entry["subs"] or k in plain.get(key[2], set())
                            or k in words or (key[0], k) in seen):
                        continue
                    clause = _clause_around(body, m.start(), m.end())
                    if not clause or total >= max_notes:
                        continue
                    # A clause that also cites a subsection the answer already
                    # has restates it, with the sibling in passing.
                    also = set()
                    for q in _SIBLING_PIN.finditer(clause):
                        qs = _FIRST_SUB.match(q.group("sub"))
                        if q.group("num").lower() == key[2] and qs:
                            also.add(qs.group(1).lower())
                    if also & entry["subs"]:
                        continue
                    # The answer already says this, pinpoint aside.
                    cw = set(_CONTENT_WORD.findall(_mask_links(clause).lower()))
                    if cw and any(len(cw & s) >= 0.6 * len(cw) for s in sentences):
                        continue
                    seen.add((key[0], k))
                    notes.setdefault(key[0], []).append(clause)
                    total += 1
        if not total:
            return answer, 0
        # Insert after the paragraph holding the section's first citation,
        # from the end of the answer backwards so earlier offsets hold.
        inserts = []
        for url_key, clauses in notes.items():
            entry = cited[url_key]
            kind = entry["key"][1]
            num = entry["num"]
            brk = re.compile(r"\n[ \t]*\n").search(answer, entry["at"])
            pos = brk.start() if brk else len(answer.rstrip())
            label = f"{_NOTE_LABEL[kind]}{num}"
            inserts.append((pos, f"\n\nAlso in {label}: " + " ".join(clauses)))
        for pos, text in sorted(inserts, reverse=True):
            answer = answer[:pos] + text + answer[pos:]
        return answer, total
    except Exception:  # pragma: no cover - defensive
        logger.debug("[Citations] sibling restore skipped", exc_info=True)
        return answer, 0


def enforce_provision_links(
    text: str,
    retrieved: Optional[Iterable[str]],
) -> tuple:
    """Rewrite provision links that no tool returned. Returns (text, demoted, unlinked).

    Three cases, and the middle one is the whole design:

      * URL **was** returned by a tool -> untouched, however the model spells it.
      * URL not returned but the **Act** was -> the link is retargeted at the Act
        and the label marked. The lawyer still gets a working link to the right
        instrument and is told it is not the provision they were shown.
      * neither -> the link is removed and the citation left in bold, which is
        what `CITATION PROTOCOL -> VALIDATION` already tells the model to do.
        This is enforcement making a stated rule true, not a new policy.

    Only legislation.gov.uk provision URLs are considered. Case law, Official
    Report and every other host pass through untouched - they have their own
    identifier discipline and are not what B14 measures.

    Idempotent: re-running over already-marked text is a no-op, so it is safe at
    both the worker-report seam and the final-answer seam (a Manager that passes
    the report through verbatim would otherwise mark it twice).
    """
    if not text or retrieved is None:
        return text, 0, 0
    retrieved_keys = {k for k in (normalise_leg_url(u) for u in retrieved) if k}

    counts = {"demoted": 0, "unlinked": 0}

    def _fix(m) -> str:
        label, url = m.group(1), m.group(2)
        key = normalise_leg_url(url)
        if not key or not is_provision_url(url):
            return m.group(0)
        if key in retrieved_keys:
            return m.group(0)
        if PROVISION_MARKER in label:          # already enforced upstream
            return m.group(0)
        base = act_base_url(url)
        marked = f"{label} {PROVISION_MARKER}"
        if base and base in retrieved_keys:
            counts["demoted"] += 1
            # Truncate the model's own URL rather than rebuilding from the
            # normalised key: the key has lost the scheme and the `www.`, and a
            # rewritten link that changes host spelling mid-answer looks like a
            # different source to a lawyer checking citations.
            cut = _PROVISION_SEGMENT.search(url)
            return f"[{marked}]({url[: cut.start()] if cut else base})"
        counts["unlinked"] += 1
        return f"**{marked}**"

    out = _MD_LINK.sub(_fix, text)
    if (counts["demoted"] or counts["unlinked"]) and PROVISION_FOOTNOTE not in out:
        out = out.rstrip() + "\n\n" + PROVISION_FOOTNOTE
    return out, counts["demoted"], counts["unlinked"]
