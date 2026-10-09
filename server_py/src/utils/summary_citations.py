"""P3.45: a case citation the summariser wrote that its source does not hold.

The Worker's large tool results are summarised (`summarisation.summarise_for_query`)
before the Worker reads them. Batch 12 E found summaries carrying case citations
the summarised text never contained: a case the source never names (an
authority from the summariser's training, in summaries of legislation as well
as of case law) and, for a case the source does name, a citation it does not
give (a law report turned into a neutral citation, sometimes the wrong one).
The Worker cannot tell a summary from its source, so such a citation reached
answers as if it had been retrieved.

This module is the code check at the summary seam, on the principle of P3.16's
gloss detector: compare the summary with the text it was made from. It knows
these citation forms:

* a neutral citation, ``[2001] UKSC 1``, ``[2001] EWCA Civ 2``,
  ``[2001] EWHC 3 (Admin)``, compared on year, court and number (a division
  written one way and not the other is the same judgment);
* an English law report, ``[1901] AC 1``, ``[1901] 2 QB 3``, ``(1901) 15 Ch D 4``,
  ``[2001] ECR I-5``;
* a Scottish law report, ``1901 SC 1``, ``1901 SLT 2``, ``1901 SC (HL) 3``;
* a Find Case Law URL, ``caselaw.nationalarchives.gov.uk/uksc/2001/1``.

A citation is HELD by the source when the source carries it in any written form
(dots, spaces and no-break spaces ignored; a neutral citation also as its Find
Case Law URL and the reverse; a report citation also split by words, "[1901] AC
per Lord X at 1"). A citation the research question itself carries is treated
as held: the summariser took it from the question, not from its training, and
the Worker has it already.

What `strip_unsourced_citations` does with a citation the source does not hold:

* where the source names the case written before it (each side of "X v Y"
  that has a distinctive word is found in the source), only the citation goes:
  the case is the source's, the citation was the summariser's;
* where the source does not name that case, the case is the summariser's own
  addition, and the passage carrying it goes: the list item (with its nested
  lines), the block under a heading line that is the case itself, or the
  sentence;
* where no case name can be read before the citation, only the citation goes
  (the safe direction: never remove text whose source cannot be judged).

It only removes; it never adds a word. A summary with no unheld citation is
returned unchanged, byte for byte. Fail-soft: any error returns the summary
unchanged (Invariant 5).
"""
from __future__ import annotations

import json
import logging
import re
from typing import NamedTuple, Optional

logger = logging.getLogger("agent")

# Court codes of a UK neutral citation (as `tools/replay_report._CL_COURTS`),
# plus the codes a summariser has been seen to write (UKTT for UKFTT).
_COURTS = (r"UKSC|UKHL|UKPC|EWCA|EWHC|EWCOP|EWFC|EWCC|EWCR|UKUT|UKFTT|UKEAT|EAT|UKAIT"
           r"|UKTT|CSOH|CSIH|HCJAC|SAC|SAPC|NICA|NIQB|NICH|NIFam|NIKB|UKIPTrib|UKSIAC")
# Written loosely in judgments, and read loosely so a source's own form is
# never missed: "[2001] UKSC1", "[2001] EWCA Civ. 2", "[2001] EWCA (Civ) 2",
# "[2001] EWHC [3 (Comm)", "2001] UKSC 4" (a search query's own text).
_NCN = re.compile(
    r"\[?(?P<y>(?:18|19|20)\d{2})\]\s*(?P<court>" + _COURTS + r")(?![A-Za-z])\s*"
    r"(?:\(?(?P<div>Civ|Crim)\)?\.?\s*)?\[?"
    r"(?P<num>\d{1,5})(?!\d)(?:\s*\((?P<sub>[A-Za-z]{2,8})\))?")
_SERIES = r"[A-Z][A-Za-z.&]{0,10}(?:\s(?:[A-Z][A-Za-z.&]{0,4}))?"
# An English report in square brackets: "[1901] AC 1", "[1901] 2 QB 3",
# "[1901] 1 W.L.R. 4", "[2001] ECR I-5".
_REPORT = re.compile(
    r"\[(?P<y>(?:18|19|20)\d{2})\]\s*(?P<vol>\d{1,2}\s+)?(?P<series>" + _SERIES + r")\s+"
    r"(?P<page>(?:[IV]{1,3}-)?\d{1,5})(?!\d)")
# A report cited by volume, the year in round brackets: "(1901) 15 Ch D 4".
_REPORT_VOL = re.compile(
    r"\((?P<y>(?:18|19|20)\d{2})\)\s*(?P<vol>\d{1,3}\s+)(?P<series>" + _SERIES + r")\s+"
    r"(?P<page>\d{1,5})(?!\d)")
# A Scottish report: "1901 SC 1", "1901 S.L.T. 2", "1901 SC (HL) 3",
# "1901 SLT (Sh Ct) 4", "1901 SCLR 5", "1901 SCCR 6", "1901 JC 7".
_SCOT = re.compile(
    r"(?<![\d/\[(])(?P<y>(?:18|19|20)\d{2})\s+"
    r"(?P<series>S\.?C\.?(?:L\.?R\.?|C\.?R\.?)?|S\.?L\.?T\.?|J\.?C\.?)"
    r"(?:\s*\((?P<sub>[A-Za-z .]{2,10})\))?\s+(?P<page>\d{1,5})(?!\d)")
_URL = re.compile(
    r"(?:https?://)?caselaw\.nationalarchives\.gov\.uk/(?:id/)?(?P<court>[a-z]{2,8})/"
    r"(?:(?P<sub>[a-z]{2,8})/)?(?P<y>(?:18|19|20)\d{2})/(?P<num>\d{1,5})(?!\d)", re.I)


class Citation(NamedTuple):
    kind: str      # "ncn", "url", "report" or "scot"
    start: int
    end: int
    text: str
    key: str       # neutral citation / URL: "year court number"; a report: its normal form


def _norm(s: str) -> str:
    """One written form for a citation: no dots, spaces or no-break spaces, lower case."""
    s = re.sub(r"&nbsp;|&#160;", "", s or "")
    return re.sub(r"[\s.  ]+", "", s).lower()


def _ncn_key(y: str, court: str, num: str) -> str:
    return "%s %s %d" % (y, court.lower(), int(num))


def find_citations(text: str) -> list[Citation]:
    """Every case citation in text, in order; where two forms overlap the
    first found wins (a neutral citation is also the shape of a report)."""
    found: list[Citation] = []
    taken: list[tuple[int, int]] = []
    text = text or ""

    def _add(kind, m, key):
        s, e = m.span()
        if any(s < te and ts < e for ts, te in taken):
            return
        taken.append((s, e))
        found.append(Citation(kind, s, e, m.group(0), key))

    for m in _NCN.finditer(text):
        _add("ncn", m, _ncn_key(m.group("y"), m.group("court"), m.group("num")))
    for m in _URL.finditer(text):
        _add("url", m, _ncn_key(m.group("y"), m.group("court"), m.group("num")))
    for rx in (_REPORT, _REPORT_VOL):
        for m in rx.finditer(text):
            _add("report", m, _norm(m.group(0)))
    for m in _SCOT.finditer(text):
        _add("scot", m, _norm(m.group(0)))
    found.sort(key=lambda c: c.start)
    return found


def source_text(raw) -> str:
    """The text a citation is looked for in. A JSON result's strings are
    joined (its escaped line breaks and no-break spaces decoded), and the raw
    text is kept beside them, so nothing the source holds in either form is
    missed."""
    raw = "" if raw is None else str(raw)
    try:
        obj = json.loads(raw)
    except Exception:
        return raw
    parts: list[str] = []

    def walk(o):
        if isinstance(o, str):
            parts.append(o)
        elif isinstance(o, dict):
            for k, v in o.items():
                parts.append(str(k))
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
        elif o is not None:
            parts.append(str(o))
    walk(obj)
    return "\n".join(parts) + "\n" + raw


class SourceIndex:
    """What a source (and the research question) holds."""

    def __init__(self, raw, query: str = ""):
        self.text = source_text(raw)
        self.norm = _norm(self.text)
        self.query_norm = _norm(query or "")
        self.ncn_keys = {c.key for c in find_citations(self.text) if c.kind in ("ncn", "url")}
        self.query_keys = {c.key for c in find_citations(query or "") if c.kind in ("ncn", "url")}

    @staticmethod
    def _in_norm(cite_norm: str, hay: str) -> bool:
        """The normal form occurs in hay and is not the head of a longer
        number ("[1901]ac1" is not held by "[1901]ac12")."""
        if not cite_norm:
            return False
        return re.search(re.escape(cite_norm) + r"(?!\d)", hay) is not None

    def _split_held(self, c: Citation) -> bool:
        """A report the source writes in another form: split by words (year,
        series and page within 60 characters, "[1901] AC per Lord X at 1");
        with the series abbreviated differently ("[1901] 2 All 3" for
        "[1901] 2 All ER 3"); or, for a report cited by volume, without its
        year ("15 Ch D 4" for "(1901) 15 Ch D 4")."""
        for rx in ((_REPORT, _REPORT_VOL) if c.kind == "report" else (_SCOT,)):
            m = rx.fullmatch(c.text)
            if m:
                break
        else:
            return False
        series = re.sub(r"[\s.]", "", m.group("series"))
        ser = r"\.?\s*".join(re.escape(ch) for ch in series) + r"\.?"
        vol = (m.groupdict().get("vol") or "").strip()
        vol_rx = (re.escape(vol) + r"\s*") if vol else ""
        y = m.group("y")
        lead = (r"\[" + y + r"\]\s*" if rx is _REPORT else r"\(" + y + r"\)\s*" if rx is _REPORT_VOL
                else y + r"\s+")
        page = r"(?<![\d-])" + re.escape(m.group("page")) + r"(?!\d)"
        pats = [lead + vol_rx + ser + r"[\s\S]{0,60}?" + page,
                lead + vol_rx + "(?i:" + re.escape(series[0]) + r")[A-Za-z.&]{0,6}(?:\s[A-Za-z.&]{1,5})?\s*"
                + page]
        if rx is _REPORT_VOL:
            pats.append(r"(?<!\d)" + vol_rx + ser + r"\s*" + page)
        return any(re.search(p, self.text, re.I) for p in pats)

    def held(self, c: Citation) -> bool:
        if c.kind in ("ncn", "url"):
            return c.key in self.ncn_keys or c.key in self.query_keys
        if self._in_norm(c.key, self.norm) or self._in_norm(c.key, self.query_norm):
            return True
        return self._split_held(c)

    def word_held(self, word: str) -> bool:
        """A distinctive word of a case name occurs in the source as a word,
        in its own capitalisation or in capitals; an acronym ("WCL", "GHL") also as the initials of consecutive capitalised words, skipping
        joining words ("Widget Components and Gadget Holdings Limited")."""
        w = word.strip("'’")
        if not w:
            return False
        if re.search(r"(?<![A-Za-z])(?:" + re.escape(w) + "|" + re.escape(w.upper())
                     + r")(?![A-Za-z])", self.text):
            return True
        if w.isupper() and 3 <= len(w) <= 8:
            joiner = r"(?:[\s,&]+(?:of|for|and|the|de|on)\b)*[\s,&]+"
            pat = joiner.join(re.escape(ch) + r"[A-Za-z'’]*" for ch in w)
            if re.search(r"(?<![A-Za-z])" + pat + r"(?![A-Za-z])", self.text):
                return True
        return False


# --- the case name written before a citation --------------------------------

# Words that say nothing about which case is meant: a party's corporate or
# procedural form, and public bodies that are a party to thousands of cases.
_NAME_STOP = frozenset("""
the and for ltd limited plc llp inc co company son sons anor ors others another application
on of in at by re ex parte appellant respondent petitioner pursuer defender claimant defendant
secretary state minister ministers lord advocate general solicitor procurator fiscal crown queen
king regina rex police chief constable commissioner commissioners revenue customs hmrc home
department justice health work pensions scottish scotland government council city borough county
district authority board trust committee united kingdom england wales northern ireland british
national royal court office officer registrar uk mr mrs ms dr sir case cases see also per no
""".split())
# Words that may sit inside a party's name, lower case ("Secretary of State for
# the Home Department", "R (on the application of X)").
_JOINERS = frozenset("of the and for de du da van von le la des application ex parte & t/a "
                     "plc ltd llp inc co anor ors".split())
_V = re.compile(r"\s+v\.?\s+")
_MARKUP = "*_`[]\"'“”‘’,:;"


def _clean_token(tok: str) -> str:
    return tok.strip(_MARKUP + "()")


def name_before(text: str, c: Citation) -> str:
    """The "X v Y" case name written immediately before a citation, or "".

    Read back from the citation on its own line, after any earlier citation:
    the second party is everything between " v " and the citation; the first
    is the run of capitalised words (and joining words) before " v ", stopped
    at a lower-case word, a label ("Relevant to Widgetland:") or an opening
    bracket or emphasis mark that starts the name."""
    seg = text[max(0, c.start - 240):c.start]
    seg = seg.split("\n")[-1]
    prev = find_citations(seg)
    if prev:
        seg = seg[prev[-1].end:]
    vs = list(_V.finditer(seg))
    if not vs:
        return _reference_name(seg)
    mv = vs[-1]
    side_b = seg[mv.end():].strip()
    side_b = side_b.rstrip(" *_([,:;–-").strip()
    # The second party ends where prose starts: a lower-case word that is
    # not a joining word means the text before the citation is not the name.
    for tok in side_b.split():
        t = _clean_token(tok)
        if t and t[0].islower() and t.lower() not in _JOINERS and not re.fullmatch(r"\d+\)?", t):
            return ""
    taken: list[str] = []
    depth = 0   # brackets closed inside the name, read backwards ("(South East)")
    for tok in reversed(seg[:mv.start()].split()):
        t = _clean_token(tok)
        if tok.endswith(":") or tok.endswith(";"):
            break
        if not t:
            break
        # "on" joins a name only as "(on the application of"; "in" never does
        # ("Held in Widget Co v ..." is prose before the name).
        joins = t.lower() in _JOINERS or (t.lower() == "on" and tok.startswith("("))
        if t[0].isupper() or t[0].isdigit() or joins:
            taken.append(tok)
            depth += tok.count(")") - tok.count("(")
            if depth < 0 and not joins:
                break       # "(Widget Co v ..." : the bracket opens the name
            if tok[0] in "*_[" and depth <= 0:
                break       # "*Widget Co v ..." : the emphasis opens the name
            continue
        break
    while taken and _clean_token(taken[-1]).lower() in _JOINERS:
        taken.pop()     # a name does not start with "of" / "the"
    if not taken:
        return ""
    side_a = " ".join(reversed(taken))
    return f"{side_a.strip(_MARKUP + '( ')} v {side_b.strip(_MARKUP + ' ')}".strip()


# A case named without "v": a reference or a matter ("Reference by the Lord
# Advocate ...", "Re Widget Co", "In re X", "Widget Co's Application").
_REFERENCE = re.compile(
    r"(?:^|[\s*_(\[])(?P<name>(?:Reference\s+(?:by|re|under|from)\b|In\s+re\b|Re\s+[A-Z]|In\s+the\s+matter\s+of\b)"
    r"[^:;\n]*|[A-Z][\w'’&.-]*(?:\s+[A-Z][\w'’&.-]*)*['’]s\s+(?:Reference|Application|Petition)\b[^:;\n]*)$")


def _reference_name(seg: str) -> str:
    m = _REFERENCE.search(seg.rstrip(" *_([,–-"))
    if not m:
        return ""
    return m.group("name").strip(_MARKUP + " ")


# A public office or department named as a party says nothing about which
# case is meant ("Secretary of State for Widgets and Local
# Gadgets", "Minister of Widgets and National Gadgetry", "Commissioner of
# Public Widgets"): the phrase is left out of the party's distinctive words, or a
# department's subject word in an instrument would vouch for an unrelated case.
_OFFICE = re.compile(
    r"\b(?:Secretary\s+of\s+State|Ministers?|Department|Commissioners?|Commission|Board|"
    r"Agency|Authority|Council|Office)\s+(?:of|for)\b.*$", re.I)


def name_words(side: str) -> list[str]:
    """The distinctive words of one party: three or more letters, not a
    corporate, procedural or public-body word, and not in a public office's
    title."""
    side = _OFFICE.sub(" ", side or "")
    return [w for w in re.findall(r"[A-Za-z][A-Za-z'’]*", side)
            if len(w) >= 3 and w.lower() not in _NAME_STOP]


def name_held(name: str, index: SourceIndex) -> Optional[bool]:
    """Whether the source names the case: some side of "X v Y" has distinctive
    words and the source has every one of them (a reference or a matter named
    without "v": every capitalised distinctive word). None when there is no
    name, or it has no distinctive word: never read as 'not held'.

    One side suffices because a judgment often names a case by one party
    ("Widgetco at [35]"); every word of that side is required because one
    common word ("Bank") would otherwise vouch for any case."""
    if not name:
        return None
    sides = _V.split(name, maxsplit=1)
    if len(sides) == 1:
        # A reference or a matter: its capitalised distinctive words are
        # what identify it ("Reference by the Lord Advocate respecting the
        # Widget Bill"), and the source names it only if it has every one.
        words = [w for w in name_words(name) if w[0].isupper()]
        if not words:
            return None
        return all(index.word_held(w) for w in words)
    judged = False
    for side in sides:
        words = name_words(side)
        if not words:
            continue
        judged = True
        if all(index.word_held(w) for w in words):
            return True
    return False if judged else None


class Unsourced(NamedTuple):
    citation: Citation
    name: str
    name_held: Optional[bool]


def unsourced_citations(summary: str, raw, query: str = "") -> list[Unsourced]:
    """Every citation in summary that neither raw nor the question holds,
    with the case name before it and whether the source names that case."""
    cites = find_citations(summary)
    if not cites:
        return []
    index = SourceIndex(raw, query)
    out = []
    for c in cites:
        if index.held(c):
            continue
        nm = name_before(summary, c)
        out.append(Unsourced(c, nm, name_held(nm, index)))
    return out


# --- removal -----------------------------------------------------------------

_ITEM = re.compile(r"^(?P<indent>[ \t]*)(?:[-*•+]|\d{1,3}[.)])[ \t]+")
_HEADING = re.compile(r"^[ \t]*(?:#{1,6}[ \t]|\*\*.*\*\*[ \t:]*$|---+[ \t]*$|\*\*\*+[ \t]*$)")
# The end of a sentence: . ! or ? and a space before a capital, an emphasis
# mark or a bracket, where the word before the stop is not an abbreviation.
_SENT_END = re.compile(r"(?<=[.!?])[ \t]+(?=[A-Z*_(\[“\"])")
_ABBREV = re.compile(
    r"(?:\b(?:v|vs|Co|Ltd|No|Nos|s|ss|para|paras|cf|e\.g|i\.e|St|Mr|Mrs|Ms|Dr|Art|Sch|Reg|Regs|al|Inc|"
    r"Corp|plc|Bros|Pt|Ch|art|reg|sch|pp|p|ibid|op|cit|Jr|Sr|Lt|Gen|Rt|Hon|LJ|J|MR|QC|KC)|\b[A-Z])\.$")
_EMPTY_PARENS = re.compile(r"\(\s*(?:(?:also|cited|as|see|reported|at|in|and|or|cf|e\.g\.|eg|per|"
                           r"applied|referenced|followed|considered|approved)[\s,;:]*)*\)", re.I)


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" \t"))


def _is_item(line: str) -> bool:
    return _ITEM.match(line) is not None


# A block the product appends to a tool result ("[CITATION URLS - ...",
# "[MANDATORY NEXT STEP ..."): never part of a summary's own section.
_CODE_BLOCK = re.compile(r"^[ \t]*\[[A-Z][A-Z0-9 /&'’—–-]{3,}")


def _is_heading(line: str) -> bool:
    return _HEADING.match(line) is not None


def _is_boundary(line: str) -> bool:
    return _is_heading(line) or _CODE_BLOCK.match(line) is not None


def _item_span(lines: list[str], i: int) -> tuple[int, int]:
    """Lines [i, j) of the list item at line i with its nested lines."""
    base = _indent(lines[i])
    j = i + 1
    while j < len(lines):
        ln = lines[j]
        if not ln.strip():
            k = j + 1
            while k < len(lines) and not lines[k].strip():
                k += 1
            if k < len(lines) and _indent(lines[k]) > base and not _is_boundary(lines[k]):
                j = k
                continue
            break
        if _indent(ln) > base and not _is_boundary(ln):
            j += 1
            continue
        break
    return i, j


def _block_span(lines: list[str], i: int) -> tuple[int, int]:
    """Lines [i, j) of the block under a heading line: up to the next heading
    line, rule or product block."""
    j = i + 1
    while j < len(lines):
        if _is_boundary(lines[j]):
            break
        j += 1
    while j > i + 1 and not lines[j - 1].strip():
        j -= 1
    return i, j


def _list_after(lines: list[str], i: int) -> tuple[int, int]:
    """Lines [i+1, j) of the list a line ending in a colon introduces
    ("... the three-fold test derived from X:" and its items)."""
    j = i + 1
    while j < len(lines) and _is_item(lines[j]):
        _a, j = _item_span(lines, j)
    return i + 1, j


def _bare_rest(line: str, cites: list[Citation], offset: int, name: str) -> str:
    """What a line says besides its case name and citations: markup, list
    markers, numbering and a trailing colon stripped."""
    s = line
    for c in sorted(cites, key=lambda c: -c.start):
        a, b = c.start - offset, c.end - offset
        if 0 <= a <= b <= len(s):
            s = s[:a] + " " + s[b:]
    if name:
        for side in _V.split(name):
            s = s.replace(side, " ")
    s = re.sub(r"^\s*(?:#{1,6}|[-*•+]|\d{1,3}[.)])\s*", "", s)
    s = re.sub(r"[*_`#:()\[\]\s.]+|\bv\b", " ", s)
    return s.strip()


def _sentence_span(line: str, pos: int) -> tuple[int, int]:
    """The sentence of line holding character pos, as [a, b) in the line."""
    starts = [0]
    for m in _SENT_END.finditer(line):
        if _ABBREV.search(line[:m.start()]):
            continue
        starts.append(m.end())
    a = max(s for s in starts if s <= pos)
    later = [s for s in starts if s > pos]
    b = later[0] if later else len(line)
    return a, b


def _case_segment(line: str, name: str, col: int, end: int) -> Optional[tuple[int, int]]:
    """[a, b) of "Name [citation]" in line where it stands as one entry of a
    list of authorities: preceded by the line's start, a list marker, ";", ":",
    "," or "(", and followed by the line's end, ";", ".", "," or ")". None
    otherwise (inside a sentence, removing the case would break the sentence)."""
    if not name:
        return None
    a = line.rfind(name, 0, col)
    if a < 0:
        return None
    while a > 0 and line[a - 1] in "*_":
        a -= 1
    b = end
    while b < len(line) and line[b] in "*_":
        b += 1
    left = line[:a].rstrip()
    item = _ITEM.match(line)
    left_ok = (not left.strip() or (item is not None and item.end() >= len(left))
               or left.endswith((";", ":", ",", "(")) or re.search(r"[:;,(]\s*\*{1,3}$", left))
    right = line[b:].lstrip()
    right_ok = not right or right[0] in ";.,)"
    if not (left_ok and right_ok):
        return None
    if right.startswith(";"):
        b = len(line) - len(right) + 1
    elif left.endswith(";"):
        a = len(left) - 1
    return a, b


def _tidy_line(s: str) -> str:
    """Remove what a removed citation leaves behind: an empty or label-only
    bracket, a doubled space, a space before punctuation, an empty emphasis."""
    lead = s[:_indent(s)]
    body = s[len(lead):]
    m = _ITEM.match(body)
    marker = body[:m.end()] if m else ""     # a list marker "*   " is not emphasis
    body = body[len(marker):]
    for _ in range(3):
        body = re.sub(r"\[([^\[\]\n]+)\]\(\s*\)", r"\1", body)   # a link left with no URL
        body = _EMPTY_PARENS.sub("", body)
        body = re.sub(r",[ \t]*,", ",", body)
        body = re.sub(r"\[\s*\]", "", body)
        # An emphasis pair left empty ("****", "** **"), never a marker that
        # opens or closes a word ("**Section 5**").
        body = re.sub(r"(?<![*\w])(\*\*\*|\*\*|__)[ \t]*\1(?![*\w])", "", body)
        body = re.sub(r"(?<![*\w])(\*|_)[ \t]+\1(?![*\w])", "", body)
        body = re.sub(r"[ \t]{2,}", " ", body)
        body = re.sub(r"[ \t]+([,.;:)\]])", r"\1", body)
        # a space left before a closing emphasis mark: "Widget Co *)"
        body = re.sub(r"[ \t]+(\*{1,3}|_{1,2})(?=[)\],.;:]|$)", r"\1", body)
        body = re.sub(r"([(\[])[ \t]+", r"\1", body)
        body = re.sub(r"[,;][ \t]*([.;:)])", r"\1", body)
        body = re.sub(r"[ \t]*[/;,][ \t]*$", "", body)
    return lead + marker + body.strip()


def _contentless(line: str) -> bool:
    """A line left with no words: a list marker, emphasis or a label ("**URL:**")."""
    s = re.sub(r"^\s*(?:#{1,6}|[-*•+]|\d{1,3}[.)])\s*", "", line)
    s = re.sub(r"[*_`]", "", s).strip()
    return not s or re.fullmatch(r"[\w ()/'’-]{1,40}:", s) is not None


def strip_unsourced_citations(summary: str, raw, query: str = "") -> tuple[str, list[dict]]:
    """The summary with every citation the source does not hold removed, as
    described in the module docstring, and one record per removal:
    {"citation", "name", "action": "citation" | "item" | "block" | "sentence"}.

    Unchanged (and []) where nothing is unheld, and on any error."""
    try:
        return _strip(summary, raw, query)
    except Exception as e:   # Invariant 5: a check never fails the research run
        logger.warning(f"[SummaryCheck] citation check failed, summary kept: {type(e).__name__}")
        return summary, []


def _strip(summary: str, raw, query: str) -> tuple[str, list[dict]]:
    if not summary:
        return summary, []
    uns = unsourced_citations(summary, raw, query)
    if not uns:
        return summary, []
    lines = summary.split("\n")
    starts = []
    pos = 0
    for ln in lines:
        starts.append(pos)
        pos += len(ln) + 1

    def line_of(off: int) -> int:
        lo = 0
        for i, s in enumerate(starts):
            if s <= off:
                lo = i
        return lo

    all_cites = find_citations(summary)
    absent_at = {u.citation.start for u in uns if u.name_held is False}
    drop_lines: set[int] = set()
    sentence_cuts: dict[int, list[tuple[int, int]]] = {}
    cite_cuts: dict[int, list[tuple[int, int]]] = {}
    records: list[dict] = []

    def _cut_sentence(li: int, col: int) -> None:
        a, b = _sentence_span(lines[li], col)
        # The emphasis that closes the line ("... last sentence.*") stays,
        # or the line's opening mark is left unclosed.
        end = len(lines[li].rstrip())
        at_end = b >= end
        if at_end:
            k = end
            while k > a and end - k < 3 and lines[li][k - 1] in "*_":
                k -= 1
            b = k
        sentence_cuts.setdefault(li, []).append((a, b))
        # A sentence that introduces a list ("... the test derived from X:")
        # takes the list with it: the items are that case's test.
        if at_end and lines[li].rstrip(" *_").endswith(":"):
            i0, i1 = _list_after(lines, li)
            drop_lines.update(range(i0, i1))
    for u in uns:
        c = u.citation
        li = line_of(c.start)
        line = lines[li]
        col = c.start - starts[li]
        rec = {"citation": c.text, "name": u.name}
        if u.name_held is not False:
            cite_cuts.setdefault(li, []).append((col, c.end - starts[li]))
            rec["action"] = "citation"
        else:
            line_cites = [x for x in all_cites if starts[li] <= x.start < starts[li] + len(line)]
            rest = _bare_rest(line, line_cites, starts[li], u.name)
            seg = _case_segment(line, u.name, col, c.end - starts[li])
            staying = [x for x in line_cites if x.start not in absent_at]
            if seg and staying:
                # A list of authorities in one line, some the source's: the
                # summariser's case goes with its citation, the rest stay.
                cite_cuts.setdefault(li, []).append(seg)
                rec["action"] = "case"
            elif _is_item(line):
                body_at = _ITEM.match(line).end()
                a, _b = _sentence_span(line[body_at:], max(0, col - body_at))
                if a == 0:
                    i0, i1 = _item_span(lines, li)
                    drop_lines.update(range(i0, i1))
                    rec["action"] = "item"
                else:
                    _cut_sentence(li, col)
                    rec["action"] = "sentence"
            elif _is_heading(line) and len(rest.split()) <= 6:
                i0, i1 = _block_span(lines, li)
                drop_lines.update(range(i0, i1))
                rec["action"] = "block"
            else:
                _cut_sentence(li, col)
                rec["action"] = "sentence"
        records.append(rec)

    out: list[Optional[str]] = []
    for i, ln in enumerate(lines):
        if i in drop_lines:
            out.append(None)
            continue
        cuts = [(a, b) for a, b in sentence_cuts.get(i, [])]
        cuts += [(a, b) for a, b in cite_cuts.get(i, [])
                 if not any(sa <= a and b <= sb for sa, sb in sentence_cuts.get(i, []))]
        if not cuts:
            out.append(ln)
            continue
        merged: list[list[int]] = []
        for a, b in sorted(set(cuts)):
            if merged and a <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], b)
            else:
                merged.append([a, b])
        s = ln
        for a, b in reversed(merged):
            s = s[:a] + s[b:]
        s = _tidy_line(s)
        out.append(None if _contentless(s) else s)

    # A heading (or a bold label line) whose whole section went with the
    # removals ("### Case Law Search Results" over a list of the summariser's
    # cases) goes too, with any one-line italic note under it ("*Keywords: ...*").
    for i, ln in enumerate(lines):
        if out[i] is None or not _is_heading(ln) or re.match(r"^[ \t]*(?:---+|\*\*\*+)[ \t]*$", ln):
            continue
        j = i + 1
        removed_here = False
        kept: list[int] = []
        while j < len(lines) and not (_is_boundary(lines[j]) and out[j] is not None):
            if out[j] is None and lines[j].strip():
                removed_here = True
            elif out[j] is not None and out[j].strip():
                kept.append(j)
            j += 1
        if not removed_here:
            continue
        if len(kept) <= 1 and all(re.fullmatch(r"\s*[*_].*[*_]\s*", out[k]) for k in kept):
            out[i] = None
            for k in kept:
                out[k] = None

    # A removal between two blank lines leaves one blank line, not two. Only
    # around a removal: the rest of the summary is returned as it came.
    i = 0
    while i < len(out):
        if out[i] is None:
            j = i
            while j < len(out) and out[j] is None:
                j += 1
            before = next((out[k] for k in range(i - 1, -1, -1) if out[k] is not None), None)
            if (before is not None and not before.strip() and j < len(out)
                    and out[j] is not None and not out[j].strip()):
                out[j] = None
            i = j
        else:
            i += 1
    text = "\n".join(x for x in out if x is not None)
    if summary.endswith("\n") and not text.endswith("\n"):
        text += "\n"
    return text, records
