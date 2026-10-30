"""Enabling-power recitals: cut from an SI preamble and parsed (FIX_PLAN P3.31).

The recital ("... in exercise of the powers conferred by section 95 of the
Social Security (Scotland) Act 2018 and all other powers enabling them to do
so ...") is the only evidence of what an instrument was MADE UNDER, and no
endpoint we call returns it as a relation (P5.1). This module reads it out of
the instrument's own XML preamble. It is shared by the harvester
(`tools/madeunder_probe.py`, which builds the made-under record from
legislation.gov.uk) and the server (`services/made_under_store.py`, which
refreshes the record daily), so the record is built by one parser.

**Three traps the parser exists for**, each found on a real preamble (i.AI's
Lex Graph finder fell into all three; P3.31's row has the numbers):

* the recital ends where the powers end: "after consulting the committee ...
  under section 413 of the Insolvency Act 1986" is a consultation duty, not a
  power, so the window stops at "with the concurrence", "after consulting",
  "and (of) all other powers" and their relatives (`_WINDOW_END`);
* an Act title may contain parentheses, dots and lower-case words
  ("Community Care and Health (Scotland) Act 2002", "(No. 2)", "etc.");
* provisions come as lists and anaphora: "sections 1(2)(a), 2 and 23(4) of",
  "85(2)(g) and (5) and 95", "section 2(2) of, and paragraph 1A of Schedule 2
  to, the ... Act 1972", "of that Act", "the 2018 Act".

Pure functions; no I/O. Pinned by `tests/test_madeunder_probe.py`.
"""
from __future__ import annotations

import re

_WS = re.compile(r"\s+")


def preamble_text(xml_text: str) -> tuple:
    """(state, text) for an instrument's `SecondaryPreamble`.

    state: `ok`, `none` (no preamble element) or `elided` (dotted out, as on a
    revoked instrument's revised XML).
    """
    m = re.search(r"<SecondaryPreamble\b.*?</SecondaryPreamble>", xml_text, re.S)
    if not m:
        return "none", ""
    raw = re.sub(r"<[^>]+>", " ", m.group(0))
    for ent, ch in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'),
                    ("&apos;", "'"), ("&#8217;", "’"), ("&#160;", " ")):
        raw = raw.replace(ent, ch)
    text = _WS.sub(" ", raw).strip()
    # Spacing around punctuation is an artefact of tag removal.
    text = re.sub(r"\s+([,.;:)])", r"\1", text)
    text = re.sub(r"\(\s+", "(", text)
    letters = sum(c.isalpha() for c in text)
    if letters < 20:
        return "elided", text
    return "ok", text


_WINDOW_START = re.compile(
    r"in (?:the )?exercise of (?:the |his |her |their |its |all )?(?:powers?|functions?)"
    r"|exercising (?:the )?powers?"
    r"|powers? (?:in that behalf )?conferred (?:(?:on|upon) (?:\w+ ){0,3})?by"
    # An Order in Council: "in pursuance of the power in section 179(1)(a) ...".
    r"|in pursuance of (?:the )?powers?(?: (?:in|under|conferred by))?"
    r"|by virtue of (?:the )?powers?"
    # An Act of Sederunt: "makes this Act of Sederunt under the powers ...".
    r"|under (?:the )?powers?"
    # Older forms: "In pursuance of paragraph 3 of Schedule 5 to ...", "having
    # power under section 2 of the Civil Procedure Act 1997 ...".
    r"|\bin pursuance of\b"
    r"|\bhaving powers? (?:under|conferred by)"
    # Modern drafting, which names no "powers" at all: "makes the following
    # Order under section 32(1) of ...", "The Treasury, under section 118 of
    # ..., and the Secretary of State, under section 277 of ... make".
    r"|\b(?:Regulations|Order|Rules|Scheme|Byelaws)\s+under(?=\s+(?:sections?|paragraphs?|articles?|regulations?|Schedule)\s)"
    r"|,\s+under(?=\s+(?:sections?|paragraphs?|articles?|regulations?|Schedule)\s)",
    re.I)
_WINDOW_END = re.compile(
    r"\band (?:of )?(?:all|every) other (?:powers?|enabling)"
    r"|\band all powers enabling"
    r"|\bwith the (?:consent|concurrence|approval|agreement)\b"
    r"|\bafter (?:consult|carrying out|having)"
    r"|\bhaving (?:consulted|regard|carried|had)\b"
    r"|\bin accordance with section\b"
    r"|\b(?:a )?draft of (?:this|these|the) (?:instrument|regulations|order|rules|scheme)"
    r"|\bhereby\b|\bmakes? the following\b|\bmake(?:s)? this\b"
    r"|[:;]"
    # The end of the recital's sentence ("... Act 2013. In accordance with
    # section 58(4) of that Act, a draft ..."). Not an abbreviation's dot:
    # "No. 178/2002" and "etc. (Scotland)" are not followed by a capital.
    # Case-sensitive inside a case-insensitive pattern, or "Nicotine etc. and
    # Care" ends the title at "etc." (ssi/2017/422).
    r"|(?-i:\.\s+(?=[A-Z]))|\.$",
    re.I)


def text_before_window(preamble: str) -> str:
    """The preamble up to where the recital opens (for `parse_powers`'s anaphora)."""
    m = _WINDOW_START.search(preamble or "")
    return preamble[: m.start()] if m else ""


def recital_window(preamble: str) -> str:
    """The span that lists the enabling powers, or "" if no recital is found."""
    m = _WINDOW_START.search(preamble)
    if not m:
        return ""
    rest = preamble[m.end():]
    e = _WINDOW_END.search(rest)
    return (rest[: e.start()] if e else rest[:1200]).strip(" ,")


# --------------------------------------------------------------------------
# Powers: provisions + Act
# --------------------------------------------------------------------------

_KIND = (r"(?i:sections?|ss?\.|paragraphs?|paras?\.|articles?|arts?\.|regulations?|regs?\."
         r"|rules?|r\.|Schedules?|Sch\.|Parts?)")
# A number may start with letters: "section A1(1) of the Damages Act 1996",
# "Schedule A1 to the Mental Capacity Act 2005", "section ZA1".
_NUM = r"[A-Z]{0,2}\d+[A-Z]{0,3}(?:\([^)\s]{1,6}\))*"
# A list item may be a bare pinpoint of the previous number ("85(2)(g) and (5)
# and 95"), and the separator may be ", and" ("79(1), and 95"): missing either
# dropped s.95 from two of the 37 s.95 instruments in the first harvest.
_SEP = r"(?:\s*,?\s*(?:and|or|to)\s+|\s*,\s*)"
_LIST = rf"{_NUM}(?:{_SEP}(?:{_NUM}|\([^)\s]{{1,6}}\)(?:\([^)\s]{{1,6}}\))*))*"
# An Act title: capitalised start, then words that may be lower-case or carry
# parentheses or dots ("etc.", "(No. 2)"), up to "Act|Measure YYYY". Bounded so
# it cannot run across a whole recital.
# A title may not START with a provision word followed by its number
# ("Schedule 2 to, the ... Act"), but may start with the word itself: the
# Regulation of Investigatory Powers Act 2000 was cut to "Investigatory Powers
# Act 2000" when the bare word was excluded.
# The same words with a number (arabic or roman: "Part I of Schedule 1 to the
# ... Act 1999") never occur INSIDE a title either.
# So does an unnumbered or ordinal schedule ("the Schedule to the ... Act",
# "the First Schedule to the ... Act").
_PROV_NUMBERED = (r"(?:(?:Schedule|Part|Section|Article|Regulation|Paragraph|Chapter)s?"
                  r"\s+(?:[A-Z]{0,2}\d|[IVXL]+\b)|(?:[A-Z][a-z]+\s+)?Schedule\s+to\b)")
_TITLE = (rf"(?!{_PROV_NUMBERED})"
          # A title never starts with the bare word "Act" ("... of the Act in
          # relation to the revocation of the Competition Act 1998" is "the Act",
          # then other words).
          r"(?!Act\b)"
          # A lower-case provision word ("sections 1(1) and 4(1) of the Trade
          # Act 2021") is never part of a title: without this the title of an
          # Act cited after another instrument swallowed that instrument.
          r"[A-Z][A-Za-z'’(),.\-]*(?:\s+(?!(?:sections?|paragraphs?|articles?|regulations?|schedules?)\b)"
          rf"(?!{_PROV_NUMBERED})"
          # Nor a pinpoint: "64(1), (2), (3) and (5) and 67(3) of the Road
          # Traffic Regulation Act 1984" is a list, not a title. "(No. 2)" is.
          r"(?![A-Z]{0,2}\d+[A-Z]{0,3}\()"
          r"[A-Za-z0-9'’(),.\-&]+){0,16}?\s+(?:Act|Measure)\s+\d{4}")
# "the Act" / "the principal Act" are anaphora like "that Act": in a UK SI the
# preamble or the interpretation has named the Act first.
_ACT_REF = (rf"(?P<title>{_TITLE})"
            # "the said Act of 2003" names its year: the 2003 Act, not the last
            # Act mentioned (uksi/2003/3194 in the 1999-2008 hand-check).
            r"|(?:the )?said Act of (?P<year2>\d{4})"
            r"|(?P<that>that Act|the said Act|that Measure|(?<=the )Act\b|(?<=the )principal Act\b)"
            r"|the (?P<year>\d{4}) Act")
_CHUNK = re.compile(
    rf"(?P<prov>(?:{_KIND})\s+{_NUM}.*?)"
    rf",?\s+(?:of|to|in),?\s+(?:the\s+)?(?:{_ACT_REF})(?![A-Za-z])",
    re.S)
_ROLE = re.compile(r"\bas (?:applied|extended|read with|modified|amended)(?: by)?\s*$", re.I)
_PIECE = re.compile(rf"(?P<kind>{_KIND})\s+(?P<list>{_LIST})", re.I)


def _kind_name(k: str) -> str:
    k = k.lower().rstrip(".")
    if k.startswith("s") and not k.startswith("sch"):
        return "section"
    if k.startswith("sch"):
        return "schedule"
    if k.startswith("para"):
        return "paragraph"
    if k.startswith("art"):
        return "article"
    if k.startswith("reg"):
        return "regulation"
    if k in ("r", "rule", "rules"):
        return "rule"
    if k.startswith("part"):
        return "part"
    return k


def _numbers(lst: str) -> list:
    out = []
    # A bare "(5)" is a pinpoint of the previous number, not a new section:
    # `_NUM` needs a leading digit, so it is skipped here.
    for m in re.finditer(rf"(?<![\w(]){_NUM}", lst):
        n = m.group(0)
        out.append(n)
    # "4 to 7": expand plain integer ranges only.
    rng = re.findall(r"(\d+)\s+to\s+(\d+)\b", lst)
    for a, b in rng:
        a, b = int(a), int(b)
        if 0 < b - a <= 50:
            out.extend(str(i) for i in range(a + 1, b))
    return out


def provisions(prov: str) -> list:
    """`provision` keys for one chunk: "section/95", "schedule/2/paragraph/1A".

    The pinpoint (the bracketed subsection) is dropped from the key and kept
    in `pinpoints`, because the reverse question is asked at section level.
    """
    # "Regulations 2016" / "Order 2015" is an instrument's title, not
    # regulation 2016: a capitalised plural kind followed by a year is skipped.
    matches = [m for m in _PIECE.finditer(prov)
               if not (m.group("kind")[:1].isupper() and m.group("kind").endswith("s")
                       and re.match(r"(?:1[6-9]|20)\d\d\b", m.group("list")))]
    pieces = [(_kind_name(m.group("kind")), _numbers(m.group("list"))) for m in matches]
    keys = []
    # A paragraph belongs to the schedule named AFTER it ("paragraph 12 of
    # Schedule 1 and paragraph 9 of Schedule 1B"): pairing every paragraph with
    # one schedule put paragraph 12 in Schedule 1B (uksi/1993/2953, uksi/1993/994
    # in the 1987-1998 hand-check).
    scheds = [None] * len(pieces)
    following = None
    for idx in range(len(pieces) - 1, -1, -1):
        kind, nums = pieces[idx]
        if kind == "schedule" and nums:
            following = re.sub(r"\(.*", "", nums[0])
        scheds[idx] = following
    # ... except the reversed form, "Schedule 1, paragraph 11" (ssi/1999/57,
    # uksi/2009/16): a paragraph straight after "Schedule N," is in Schedule N.
    for idx in range(1, len(pieces)):
        prev_kind, prev_nums = pieces[idx - 1]
        if (pieces[idx][0] == "paragraph" and prev_kind == "schedule" and prev_nums
                and re.fullmatch(r"\s*,\s*", prov[matches[idx - 1].end():matches[idx].start()])):
            scheds[idx] = re.sub(r"\(.*", "", prev_nums[0])
    covered = set()
    for (kind, nums), sched in zip(pieces, scheds):
        for n in nums:
            base = re.sub(r"\(.*", "", n)
            if kind == "schedule":
                key = f"schedule/{base}"
            elif kind == "paragraph" and sched:
                key = f"schedule/{sched}/paragraph/{base}"
                covered.add(sched)
            else:
                key = f"{kind}/{base}"
            if key not in keys:
                keys.append(key)
    # A bare "Schedule 2" that also named paragraphs is covered by them.
    keys = [k for k in keys if not (k.count("/") == 1 and k.startswith("schedule/")
                                    and k.split("/")[1] in covered)]
    return keys


def parse_powers(window: str, before: str = "") -> list:
    """Each enabling power in a recital window, in order.

    `{"act": title or None, "anaphor": text or None, "provisions": [...],
      "role": "power" | "as applied by" | ..., "text": the chunk}`.
    Anaphora ("that Act", "the 2018 Act") are resolved to an earlier title in
    the same window; one left unresolved keeps `act: None`.
    """
    out = []
    # An anaphor can point before the recital opens: "... the Food Act
    # 1985 ('the said Act') and in exercise of the powers conferred by section
    # 14 of the said Act" (71 of 6,497 SSIs of 1999-2017). Act titles in the
    # preamble before the window seed the antecedents.
    # Only a title introduced by "the" counts: running text before the
    # recital opens with capitalised words ("The Scottish Ministers, being
    # designated ...") that are not a title.
    titles = [_clean_title(m.group(1))
              for m in re.finditer(r"\bthe\s+(" + _TITLE + ")", before or "")]
    window = _normalise_window(window)
    for m in _CHUNK.finditer(window):
        prov = m.group("prov")
        # A chunk's provision text must not itself contain an Act title: if it
        # does, the non-greedy match crossed a boundary the pattern missed.
        if re.search(rf"{_TITLE}", prov):
            prov = re.split(r"\s+(?:of|to),?\s+(?:the\s+)?[A-Z]", prov)[-1]
        act, anaphor = None, None
        if m.group("title"):
            act = _clean_title(m.group("title"))
            titles.append(act)
        elif m.group("that"):
            anaphor = m.group("that")
            act = titles[-1] if titles else None
        elif m.group("year") or m.group("year2"):
            year = m.group("year") or m.group("year2")
            anaphor = f"the {year} Act"
            act = next((t for t in reversed(titles) if t.endswith(year)), None)
        preceding = window[: m.start()].rstrip(" ,")
        role = "power"
        r = _ROLE.search(preceding)
        if r:
            role = r.group(0).strip().lower()
        out.append({"act": act, "anaphor": anaphor, "provisions": provisions(prov),
                    "role": role, "text": m.group(0)[:300]})
    if not out:
        out = _section_anaphora(window, before or "", titles)
    return out


def _normalise_window(window: str) -> str:
    """Repairs the source text before parsing: a missing space ("section2(3)",
    "191of the"), and "subsection (4) of section 17" read as section 17(4)."""
    w = re.sub(r"\b(sections?|regulations?|articles?|paragraphs?)(\d)", r"\1 \2", window)
    # "84 (2)" is 84(2), and "122 123 and 140" is a list missing its comma
    # (uksi/2025/1147, uksi/2024/796: both lost sections in the hand-check).
    w = re.sub(r"(\d[A-Z]*)\s+\(", r"\1(", w)
    w = re.sub(r"(?<=\d)\s+(?=\d)", ", ", w)
    w = re.sub(r"(\d|\))(of|to)\b", r"\1 \2", w)
    w = re.sub(r"\bsub-?sections?\s+((?:\([^)\s]{1,6}\)(?:\s*(?:,|and|or)\s*)?)+)\s*of\s+(section\s+\d+[A-Z]*)",
               lambda m: m.group(2) + re.sub(r"\s*(?:,|and|or)\s*", "", m.group(1)), w)
    return w


# "... a Minister designated for the purposes of section 2(2) of the European
# Communities Act 1972 ... in exercise of the powers conferred on him by that
# section". The most common UK SI recital before 2020 and the largest class of
# unparsed UK SI recitals (P3.31, 1987-2026 harvest): the provision is named
# before the recital opens, and the recital points back at it.
_SECTION_ANAPHOR = re.compile(
    rf"\b(?:that|those|the said|the same)\s+(?P<kind>sections?|paragraphs?|articles?)"
    rf"(?:\s+(?P<list>{_LIST}))?(?!\s+(?:of|to)\s)",
    re.I)


def _section_anaphora(window: str, before: str, titles: list) -> list:
    m = _SECTION_ANAPHOR.search(window)
    if not m:
        return []
    prior = list(_CHUNK.finditer(_normalise_window(before)))
    if not prior:
        return []
    last = prior[-1]
    if last.group("title"):
        act = _clean_title(last.group("title"))
    elif last.group("year"):
        act = next((t for t in reversed(titles) if t.endswith(last.group("year"))), None)
    else:
        act = titles[-1] if titles else None
    if m.group("list"):
        provs = provisions(f"{m.group('kind')} {m.group('list')}")
    else:
        provs = provisions(last.group("prov"))
    return [{"act": act, "anaphor": m.group(0), "provisions": provs, "role": "power",
             "text": (last.group(0) + " ... " + m.group(0))[:300]}]


_TITLE_LEAD = re.compile(r"^(?:and|or|of|to|the|by|in|under|with)\s+", re.I)


def _clean_title(t: str) -> str:
    t = _WS.sub(" ", t).strip(" ,")
    while _TITLE_LEAD.match(t):
        t = _TITLE_LEAD.sub("", t)
    return t




# ---------------------------------------------------------------------------
# The record as the Worker sees it (P3.31 Step 3)
# ---------------------------------------------------------------------------
#
# `find_instruments_made_under` answers the REVERSE question, "which instruments
# were made under section N of Act X", which nothing else can: it needs every
# instrument's preamble read in advance (6340, 6382, 6383 — every made-under
# question of the pre-pilot asked it this way round). The record is a harvest of
# preambles (`services/made_under_store.py`), so what it establishes is exactly
# "this instrument's own preamble names that provision as a power", and what it
# cannot establish is that no OTHER instrument was made under it: the record
# covers a stated class of instruments, and the coverage line says which.

MADE_UNDER_TOOL = "find_instruments_made_under"
MAX_LISTED = 40
# P1.8: the result's size bound, and the threshold `get_tool_result_threshold`
# gives this tool (P3.34's pattern for `find_definitions`). The list is never
# summarised; 40 rows with titles cut at 110 characters measured at most 11,612
# characters over every stored call (the longest row 337), under the 12,000
# the fallback threshold allowed, which a list of longer rows would cross.
MADE_UNDER_WHOLE_CHARS = 30_000

_ID = re.compile(r"^[a-z]{2,6}/(?:[A-Za-z0-9]+/)?[0-9\-]+/\d+$")


def normalise_title(title: str) -> str:
    """An Act title as a match key: case, a leading "the", the old comma before
    the year ("Act, 1962") and curly quotes do not distinguish two Acts."""
    t = _WS.sub(" ", str(title or "")).strip().lower()
    t = t.replace("’", "'")
    t = re.sub(r"^the\s+", "", t)
    t = re.sub(r",\s*(\d{4})$", r" \1", t)
    return t.strip(" .")


def is_legislation_id(value: str) -> bool:
    return bool(_ID.match(str(value or "").strip().strip("/")))


def provision_key(section: str) -> str:
    """"95", "s.95", "section 95(1)(a)", "Section 95" -> "section/95".

    A key already in the stored form ("schedule/2/paragraph/1") passes through.
    "" for anything without a number.
    """
    s = str(section or "").strip().lower()
    if re.match(r"^[a-z]+/\w+(?:/[a-z]+/\w+)*$", s):
        return s
    m = re.search(r"(\d+[a-z]{0,3})", s)
    if not m:
        return ""
    num = m.group(1).upper() if re.search(r"\d[a-z]", m.group(1)) else m.group(1)
    num = re.sub(r"(\d+)([A-Z]+)", r"\1\2", num)
    kind = "section"
    if re.match(r"^(?:reg|regulation)", s):
        kind = "regulation"
    elif re.match(r"^(?:art|article)", s):
        kind = "article"
    return f"{kind}/{num}"


def _short(text: str, n: int) -> str:
    text = _WS.sub(" ", str(text or "")).strip()
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def revocation_note(d: dict) -> str:
    r"""P3.33: the block on what legislation.gov.uk records about these instruments' revocation.

    A CURRENCY block by name, so `strip_scope_blocks` removes it from what the lawyer reads
    (no square brackets inside). It permits a RECORDED revocation, stated as the record gives
    it, and forbids the two inferences the B4 rules forbid (P2.5, P3.24): that an instrument
    with no revocation recorded is in force, and that a revocation dated after today has
    already taken effect. Empty where the result carries no counts (a record loaded before
    P3.33) or nothing was checked.
    """
    rv = d.get("revocations")
    if not isinstance(rv, dict):
        return ""
    n = int(d.get("count") or 0)
    unchecked = int(rv.get("unchecked") or 0)
    if not n or unchecked >= n:
        return ""
    whole = int(rv.get("revoked") or 0) + int(rv.get("revoked_undated") or 0) \
        + int(rv.get("revoked_later") or 0)
    detail = []
    if rv.get("revoked_undated"):
        detail.append(f"{rv['revoked_undated']} with no date recorded")
    if rv.get("revoked_later"):
        detail.append(f"{rv['revoked_later']} with effect from a date still to come")
    parts = [f"{whole} recorded as revoked in whole" + (f" ({'; '.join(detail)})" if detail else ""),
             f"{int(rv.get('partly') or 0)} as revoked in part"]
    if rv.get("qualified"):
        parts.append(f"{rv['qualified']} with a qualified removal only")
    checked = rv.get("checked") or "an unrecorded date"
    if rv.get("checked_from") and rv.get("checked_from") != rv.get("checked"):
        checked = f"{rv['checked_from']} to {rv['checked']}"
    tail = (f"; {_plural(unchecked, 'instrument was', 'instruments were')} added to the record "
            "after the check and not checked") if unchecked else ""
    listed = len(d.get("instruments") or [])
    order = (" The list leads with the instruments not recorded as revoked in whole, oldest first."
             if d.get("listed_order") == "not_wholly_revoked_first" else "")
    cut = (f" Only the {listed} listed instruments carry a line; the counts cover all {n}.{order}"
           if listed < n else "")
    return (
        f"\n\n[CURRENCY — revocations as recorded on legislation.gov.uk (checked {checked}): "
        f"of the {_plural(n, 'instrument', 'instruments')}, {', '.join(parts)}; for the other "
        f"{int(rv.get('none') or 0)} no revocation is recorded{tail}. Each listed instrument's "
        f"revocation line says which, with the revoking instrument and its date.{cut} When you "
        "list or name any of these instruments, say against each one the record shows revoked, "
        "in whole or in part, what its line says. You MAY "
        "state a recorded revocation as the line gives it: by which instrument, and from which "
        "date or that no date is recorded. A revocation dated after today has not yet taken "
        "effect: give its date, and do not say the instrument has been revoked. No revocation "
        "recorded is NOT evidence that an instrument is in force: say only that "
        f"legislation.gov.uk records no revocation of it as at {rv.get('checked') or 'the check'}, "
        "never that it is in force, current or still has effect.]"
    )


# P3.53: the made-under block's note on a list question, from this many listed
# (`search_scope.LIST_COVERAGE_MIN_LISTED`, the scope line's gate).
LIST_NOTE_MIN = 5


def made_under_note(raw_result) -> str:
    r"""The block appended to a `find_instruments_made_under` result.

    Permits exactly what the record establishes and names its edge. Square
    brackets never appear inside: `strip_scope_blocks` removes the block with
    `[^\[\]]*`. It is an ENABLING POWER block by name on purpose: P2.3's rule
    already permits a made-under claim only from one, and the strip already
    removes one from what the lawyer reads.
    """
    import json
    try:
        d = json.loads(raw_result) if isinstance(raw_result, str) else dict(raw_result or {})
    except Exception:
        return ""
    if not isinstance(d, dict) or d.get("tool") != MADE_UNDER_TOOL:
        return ""
    cov = (d.get("coverage") or {}).get("statement") or ""
    cov = cov.replace("[", "(").replace("]", ")")
    status = d.get("status")
    act = _short(d.get("matched_act") or d.get("act") or "", 120).replace("[", "(").replace("]", ")")
    prov = str(d.get("provision") or "").replace("/", " ")
    if status == "found":
        n, listed = int(d.get("count") or 0), len(d.get("instruments") or [])
        more = (f" Only {listed} of the {n} are listed here; say how many there are, and "
                "that the list shown is not all of them.") if listed < n else ""
        # P3.53: a question about which of the listed instruments has a
        # property was answered from 2-8 of 37 (`search_scope.list_coverage`).
        each = (f" {listed} listed; if the question asks which of them have a property, "
                "search each or say which you did not.") if listed >= LIST_NOTE_MIN else ""
        return (
            f"\n\n[ENABLING POWER — the made-under record: each instrument listed above "
            f"has its own preamble naming {prov} of the {act} as a power it was made "
            f"under ({n} instrument(s)). You MAY state that each of them was made under "
            f"that provision, citing the instrument.{more}{each} The record covers {cov} It "
            "does NOT establish that no other instrument was made under the provision: "
            "outside its coverage nothing was checked, so state the coverage rather "
            "than a total.]"
        ) + revocation_note(d)
    if status in ("act_known_section_not_cited", "act_not_in_record"):
        return (
            f"\n\n[ENABLING POWER — the made-under record: no instrument it holds names "
            f"{prov} of the {act} in its preamble. That is a statement about the record, "
            f"which covers {cov} It is NOT evidence that nothing was made under the "
            "provision: say that the record checked holds none, and name its coverage. "
            "Do not name any instrument as made under it from search results instead.]"
        )
    return ""


# ---------------------------------------------------------------------------
# P3.51: the record, for the sections a section search returned
# ---------------------------------------------------------------------------
#
# `find_instruments_made_under` runs only when a question asks the made-under
# question. Thomas's Q16 (6354, 13 October) did not: it asked what mechanisms
# could lessen one local authority's duty to the homeless, the research relied
# on s.33 of the Housing (Scotland) Act 1987, and the record's ssi/2022/356,
# made under s.33A, went unnamed. Measured over the stored replays (Session 48,
# `evidence/seam/s48/p351_measure.py`): 417 turns relied on a section whose
# FAMILY in the record (the section and the lettered sections beside it, s.33
# and s.33A) holds instruments, and 265 named none of them.
#
# So after each section search code hands the Worker the record's instruments
# for the sections the search returned (user decision, Session 48): a family
# with at most SECTION_FAMILY_LISTED instruments not revoked in whole is listed
# by title, a larger one is counted with its earliest and latest, a family
# whose every instrument is revoked in whole is left out. Measured: a median of
# 3 lines a turn, p90 11. Each family once per Worker run. The block is an
# ENABLING POWER block by name, so P2.3's rule already permits a made-under
# claim from it and `strip_scope_blocks` removes it from what the lawyer reads.
#
# Its log entries (`source: made_under_sections`) reach the Manager's limb and
# the lawyer's footer only for an instrument the Worker's report names
# (`prune_section_family_entries`): a family nobody used must not add a clause
# to every answer that section-searched an Act.

SECTION_FAMILY_LISTED = 5
SECTION_FAMILIES_PER_BLOCK = 6
SECTION_FAMILY_SOURCE = "made_under_sections"
SECTION_FAMILY_HEAD = "ENABLING POWER — the made-under record, for the sections this search returned"
_RETURNED_SECTION = re.compile(
    r"legislation\.gov\.uk/(?:id/)?([a-z]+/\d{4}/\d+)/section/(\d+)([A-Z]*)/?$")
_FAMILY_PROVISION = re.compile(r"section/(\d+)([A-Z]*)")
_GONE = ("revoked", "revoked_undated")


def returned_section_families(raw_result) -> tuple:
    """`(act_id, [base, ...])`: the Act a section search searched and the
    section numbers it returned, letters dropped (s.33A -> "33"), in rank
    order, each once. `("", [])` for anything else. Never raises."""
    import json
    try:
        d = json.loads(raw_result) if isinstance(raw_result, str) else raw_result
        rows = d.get("results") if isinstance(d, dict) else None
        act, bases = "", []
        for r in rows if isinstance(rows, list) else []:
            url = str(r.get("url") or "") if isinstance(r, dict) else ""
            m = _RETURNED_SECTION.search(url)
            if not m or (act and m.group(1) != act):
                continue
            act = act or m.group(1)
            if m.group(2) not in bases:
                bases.append(m.group(2))
        return (act, bases) if act else ("", [])
    except Exception:
        return ("", [])


def handed_families(log) -> set:
    """`{(act_id, base)}` this Worker run has already been handed."""
    return {(e.get("act_id"), e.get("family")) for e in (log or [])
            if e.get("tool") == "made_under" and e.get("source") == SECTION_FAMILY_SOURCE}


def _rev_flag(value):
    import json
    if isinstance(value, dict):
        return value
    try:
        f = json.loads(value) if value else None
        return f if isinstance(f, dict) else None
    except (TypeError, ValueError):
        return None


def _id_key(lid: str) -> tuple:
    parts = str(lid).split("/")
    try:
        return (int(parts[-2]), int(parts[-1]))
    except (ValueError, IndexError):
        return (0, 0)


def _plain(text, n: int = 160) -> str:
    return _short(text, n).replace("[", "(").replace("]", ")")


def _secs(secs: list) -> str:
    return " and ".join(secs) if len(secs) <= 2 else ", ".join(secs[:-1]) + " and " + secs[-1]


_MARK = {
    "partly": " (recorded on legislation.gov.uk as revoked in part)",
    "qualified": " (recorded on legislation.gov.uk with a qualified removal only)",
    "revoked_later": " (recorded on legislation.gov.uk as revoked from a date still to come)",
}


def section_families_block(act_id: str, bases: list, rows: list, cov: dict,
                           today=None) -> tuple:
    """`(block, entries)` for the sections a section search returned.

    `rows`: `(provision, legislation_id, title, act_title, revocation,
    revocation_checked)`, every record row under a section of `act_id` whose
    number is in `bases`. Families in `bases` order (the search's rank), at
    most SECTION_FAMILIES_PER_BLOCK. `entries` go into the run's log: one
    `made_under` entry per family spoken of (coverage, for the limb and the
    footer, and the family, so the run is handed it once) and one stated
    `enabling_power` entry per instrument named. Pure; `("", [])` where no
    family has an instrument not revoked in whole.
    """
    from .revocation_record import category

    fams: dict = {}
    titles: dict = {}
    for row in rows or []:
        prov, lid, title, act_title = row[:4]
        m = _FAMILY_PROVISION.fullmatch(str(prov or ""))
        if not m or m.group(1) not in bases or not lid:
            continue
        e = fams.setdefault(m.group(1), {}).setdefault(lid, {"title": title or lid, "secs": []})
        sec = f"s.{m.group(1)}{m.group(2)}"
        if sec not in e["secs"]:
            e["secs"].append(sec)
        checked = row[5] if len(row) > 5 else None
        e["checked"] = str(checked)[:10] if checked else None
        flag = _rev_flag(row[4] if len(row) > 4 else None)
        try:
            e["cat"] = category(flag, today) if checked else "unchecked"
        except Exception:
            # One malformed flag reads as never checked; it must not cost the
            # block every other instrument.
            e["cat"] = "unchecked"
        if act_title:
            titles[act_title] = titles.get(act_title, 0) + 1
    act = _plain(max(titles, key=titles.get) if titles else act_id, 120)
    lines, entries, spoken, more = [], [], 0, 0
    label = (cov or {}).get("label") or ""
    for base in bases:
        insts = fams.get(base)
        if not insts:
            continue
        live = sorted((lid for lid, e in insts.items() if e["cat"] not in _GONE), key=_id_key)
        if not live:
            continue
        if spoken >= SECTION_FAMILIES_PER_BLOCK:
            more += 1
            continue
        spoken += 1
        gone = len(insts) - len(live)
        secs = sorted({s for e in insts.values() for s in e["secs"]}, key=lambda s: (len(s), s))
        gone_note = (f" ({gone} more recorded on legislation.gov.uk as revoked in whole, "
                     "not listed)") if gone else ""
        if len(live) <= SECTION_FAMILY_LISTED:
            named = live
            parts = [f"made under {_secs(insts[lid]['secs'])}: {_plain(insts[lid]['title'])} "
                     f"({lid}){_MARK.get(insts[lid]['cat'], '')}" for lid in live]
            line = "; ".join(parts)
            lines.append(line[0].upper() + line[1:] + gone_note + ".")
        else:
            named = [live[0], live[-1]]
            lines.append(
                f"Made under {_secs(secs)}: {len(live)} instruments not recorded as revoked in "
                f"whole{gone_note}, the earliest {_plain(insts[live[0]]['title'])} ({live[0]}), "
                f"the latest {_plain(insts[live[-1]]['title'])} ({live[-1]}); "
                f"{MADE_UNDER_TOOL} lists them all.")
        entries.append({"tool": "made_under", "source": SECTION_FAMILY_SOURCE, "status": "found",
                        "act_id": act_id, "family": base, "act": act[:160],
                        "provision": ", ".join(f"section/{s[2:]}" for s in secs)[:60],
                        "count": len(insts), "listed": len(named), "coverage": label[:200],
                        "named": [[lid, _short(insts[lid]["title"], 160)] for lid in named],
                        # P3.48 (answer seam): a named instrument this block
                        # marks, for `utils.revocation_marks`.
                        "revoked": {lid: {"status": insts[lid]["cat"],
                                          "title": _short(insts[lid]["title"], 160),
                                          "checked": insts[lid].get("checked")}
                                    for lid in named
                                    if insts[lid]["cat"] in ("partly", "revoked_later")}})
        entries.extend({"tool": "enabling_power", "legislation_id": lid[:60], "stated": True,
                        "source": SECTION_FAMILY_SOURCE,
                        "title": _short(insts[lid]["title"], 160)} for lid in named)
    if not lines:
        return "", []
    tail = (f" {more} more of the returned sections have instruments in the record; "
            f"{MADE_UNDER_TOOL} lists them.") if more else ""
    stmt = _plain((cov or {}).get("statement") or "a stated class of instruments.", 1200)
    block = (
        f"\n\n[{SECTION_FAMILY_HEAD} of the {act} ({act_id}) and the lettered sections beside "
        "them: instruments whose own preamble names the section given as a power they were "
        "made under. " + " ".join(lines) + tail + " You MAY state that an instrument named "
        "here was made under the section given for it, citing the instrument; where only a "
        f"count is given, call {MADE_UNDER_TOOL} for that section before naming any other. "
        f"The record covers {stmt} It does NOT establish that no other instrument was made "
        "under these sections. A revocation is stated only as legislation.gov.uk records it; "
        "where none is recorded, that says nothing about whether an instrument still applies, "
        "so do not state its currency from this record.]"
    )
    return block, entries


def _names_instrument(text: str, low: str, cited: set, lid: str, title: str) -> bool:
    if not lid:
        return False
    if lid in cited or re.search(r"(?<![\w/])" + re.escape(lid) + r"(?![\w/])", text):
        return True
    t = re.sub(r"^the\s+", "", _WS.sub(" ", str(title or "")).strip().lower())
    return len(t) > 20 and t in low


def prune_section_family_entries(log: list, report: str) -> list:
    """The run's log with this route's entries kept only for an instrument the
    Worker's report names (by id, citation or title), and a family's entry only
    where the report names one of its instruments. Every other entry is
    untouched. Never raises: on a failure the log is returned as it was."""
    try:
        from .instrument_lookup import extract_instrument_citations

        text = report or ""
        low = _WS.sub(" ", text).lower()
        cited = {f"{t}/{y}/{n}" for t, y, n in extract_instrument_citations(text, limit=999)}
        out = []
        for e in log or []:
            if e.get("source") != SECTION_FAMILY_SOURCE:
                out.append(e)
            elif e.get("tool") == "enabling_power":
                if _names_instrument(text, low, cited, e.get("legislation_id") or "", e.get("title")):
                    out.append(e)
            elif any(_names_instrument(text, low, cited, lid, title)
                     for lid, title in e.get("named") or []):
                out.append(e)
        return out
    except Exception:
        return list(log or [])
