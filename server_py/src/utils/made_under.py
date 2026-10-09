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
          # A lower-case provision word ("sections 1(1) and 4(1) of the Trade
          # Act 2021") is never part of a title: without this the title of an
          # Act cited after another instrument swallowed that instrument.
          r"[A-Z][A-Za-z'’(),.\-]*(?:\s+(?!(?:sections?|paragraphs?|articles?|regulations?|schedules?)\b)"
          rf"(?!{_PROV_NUMBERED})"
          r"[A-Za-z0-9'’(),.\-&]+){0,16}?\s+(?:Act|Measure)\s+\d{4}")
# "the Act" / "the principal Act" are anaphora like "that Act": in a UK SI the
# preamble or the interpretation has named the Act first.
_ACT_REF = (rf"(?P<title>{_TITLE})"
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
    pieces = [(_kind_name(m.group("kind")), _numbers(m.group("list")))
              for m in _PIECE.finditer(prov)
              if not (m.group("kind")[:1].isupper() and m.group("kind").endswith("s")
                      and re.match(r"(?:1[6-9]|20)\d\d\b", m.group("list")))]
    keys = []
    sched = None
    for kind, nums in pieces:
        if kind == "schedule" and nums:
            sched = re.sub(r"\(.*", "", nums[0])
    for kind, nums in pieces:
        for n in nums:
            base = re.sub(r"\(.*", "", n)
            if kind == "schedule":
                key = f"schedule/{base}"
            elif kind == "paragraph" and sched:
                key = f"schedule/{sched}/paragraph/{base}"
            else:
                key = f"{kind}/{base}"
            if key not in keys:
                keys.append(key)
    # A bare "Schedule 2" that also named paragraphs is covered by them.
    if sched and any(k.startswith(f"schedule/{sched}/") for k in keys):
        keys = [k for k in keys if k != f"schedule/{sched}"]
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
        elif m.group("year"):
            anaphor = f"the {m.group('year')} Act"
            act = next((t for t in reversed(titles) if t.endswith(m.group("year"))), None)
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
        return (
            f"\n\n[ENABLING POWER — the made-under record: each instrument listed above "
            f"has its own preamble naming {prov} of the {act} as a power it was made "
            f"under ({n} instrument(s)). You MAY state that each of them was made under "
            f"that provision, citing the instrument.{more} The record covers {cov} It "
            "does NOT establish that no other instrument was made under the provision: "
            "outside its coverage nothing was checked, so state the coverage rather "
            "than a total.]"
        )
    if status in ("act_known_section_not_cited", "act_not_in_record"):
        return (
            f"\n\n[ENABLING POWER — the made-under record: no instrument it holds names "
            f"{prov} of the {act} in its preamble. That is a statement about the record, "
            f"which covers {cov} It is NOT evidence that nothing was made under the "
            "provision: say that the record checked holds none, and name its coverage. "
            "Do not name any instrument as made under it from search results instead.]"
        )
    return ""
