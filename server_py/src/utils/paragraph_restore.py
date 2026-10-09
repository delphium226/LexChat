"""FIX_PLAN P3.12, the answer seam: a schedule paragraph code handed over and
the answer left out goes back in, in its own words.

**Why here (user decision, 2026-10-09, parallel batch 12 A).** P3.12's route
(`agent_shared.schedule_route_block`) hands the Worker the paragraphs a section
search asked for, cut from the retrieved Schedule, verbatim. In every stored
live answer whose Worker had them, at least one was left out (`notes/batch12_A.md`
section 4.1), and two Worker-facing levers moved the seam and not the live runs.
So, as P3.13 did for a dropped sibling subsection
(`citation_links.restore_dropped_siblings`), code puts the paragraph back
after the answer is written. Nothing is generated: the line carries the
paragraph's number, its heading and its opening sub-paragraphs exactly as the
route cut them.

**What is restored, and the guards (each pinned by a test and a mutant):**

* only a paragraph the route cut exactly at its own heading and the next one
  (`Paragraph N of <unit>, cut at its own heading and the next one:`), from a
  block that handed over named or query-matched paragraphs; never a span, a
  to-the-end piece, a heading list, an annex chapter, a whole unit or a summary;
* only where the answer engages with the unit at paragraph level: it mentions
  the unit and cites, by number, another paragraph handed in the same block
  (a "sibling"): every paragraph of a block the query named, or, in a
  query-matched block, one whose heading shares a word with it (so an
  unrelated paragraph matched on another query word is never added);
* only where the answer cites the paragraph's number nowhere (in a list or a
  range too), and does not already say what its excerpt says
  (a restatement: 60% of its content words in one answer sentence);
* once per paragraph however many blocks handed it, at most `max_lines`;
* the excerpt is whole sub-paragraphs from the first operative one (a bare
  "This paragraph applies to ..." line is skipped), within `MAX_EXCERPT_CHARS`;
  where the first one alone is longer, the line carries the heading only.

`misattributed_paragraphs` is the second half: a sentence that cites one
handed paragraph in the words of another (`wave4_b11_sweep` rep 2 gave one
handed paragraph's limb under its neighbour's number). It only reports; the
caller logs it (user decision pending: a line or a flag).

Fail-soft throughout (Invariant 5): any error returns the answer unchanged.
"""
from __future__ import annotations

import logging
import re
from typing import Iterable, Optional

from .schedule_units import FETCHED_CLOSE, FETCHED_OPEN, _PARA_RX, _expand_range, _word_stems

logger = logging.getLogger("agent")

__all__ = ["handed_paragraphs", "restore_dropped_paragraphs", "misattributed_paragraphs",
           "MAX_EXCERPT_CHARS"]

MAX_EXCERPT_CHARS = 450
_MAX_LINES = 3

_BLOCK = re.compile(re.escape(FETCHED_OPEN) + r"(?P<head>[^\]]*)\]\n(?P<body>.*?)\n"
                    + re.escape(FETCHED_CLOSE), re.S)
_LEAD_LIST = re.compile(r"^the index holds (?P<unit>.+?) of (?P<lid>\S+) as one provision"
                        r"(?: \(url: (?P<url>[^)\s]+)\))?\.")
_LEAD_TEXT = re.compile(r"^the index's provision list for (?P<lid>\S+) did not come back, so "
                        r"code cut (?P<unit>.+?) out of ")
_CUT_TAIL = "Below is the part of it this search named, labelled."
_MATCHED_TAIL = "below are its paragraph headings, in order, and then "
_PARA_LABEL = re.compile(r"(?m)^Paragraph (?P<num>\d{1,3}[A-Z]{0,3}) of (?P<unit>[^\n]+?), "
                         r"cut at its own heading and the next one:$")
_OTHER_LABEL = re.compile(
    r"(?m)^(?:The text of [^\n]+ from the heading of paragraph [^\n]+:"
    r"|The paragraph headings of [^\n]+, in order, each after the number of the paragraph it opens:"
    r"|Chapter [IVXL]+ of [^\n]+, cut at its heading and the next chapter's heading:)$")
_HEADING_LINE = re.compile(r"^[ \t]*Section\s+(?P<num>\d{1,3}[A-Z]{0,3})\)[ \t]*"
                           r"(?:\*\*(?P<h>[^\n]*?)\*\*)?[ \t]*(?:\n|$)")
_SUB = re.compile(r"^(?P<n>\d{1,2}[A-Z]{0,2})\)[ \t]*(?P<t>.*)$")
_ITEM = re.compile(r"^(?P<n>[a-z]{1,2}|[ivx]{1,5})\)[ \t]*(?P<t>.*)$")
_BARE_APPLIES = re.compile(r"^This paragraph applies to [^—:;]*\.$")
_CONTENT_WORD = re.compile(r"[a-z]{4,}")
_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z*(\[\"“])|\n+")
_MD_LINK = re.compile(r"\[([^\]\n]{1,300})\]\((https?://[^)\s]+)\)")


def _clean(s: str) -> str:
    """Whitespace collapsed; square brackets made round, so a statutory
    insertion mark never reads as a markdown link or a tool block."""
    return re.sub(r"\s+", " ", str(s or "")).strip().replace("[", "(").replace("]", ")")


def handed_paragraphs(tool_result: str) -> list:
    """Every paragraph a PROVISION FETCHED BY CODE block in `tool_result`
    handed over cut exactly, as dicts: lid, unit, url, para, heading, text,
    block (an id for the block it came in), how ("cut": the query named the
    paragraphs; "matched": its heading matched the query). [] on anything
    else. Never raises."""
    out = []
    try:
        for bi, m in enumerate(_BLOCK.finditer(str(tool_result or ""))):
            head, body = m.group("head"), m.group("body")
            lead = _LEAD_LIST.match(head) or _LEAD_TEXT.match(head)
            if not lead:
                continue
            if _CUT_TAIL in head:
                how = "cut"
            elif _MATCHED_TAIL in head:
                how = "matched"
            else:
                continue
            unit, lid = lead.group("unit"), lead.group("lid")
            url = lead.groupdict().get("url") or ""
            starts = sorted([(x.start(), x) for x in _PARA_LABEL.finditer(body)]
                            + [(x.start(), None) for x in _OTHER_LABEL.finditer(body)],
                            key=lambda t: t[0])
            block_id = f"{m.start()}:{lid}:{unit}"
            for i, (pos, lab) in enumerate(starts):
                if lab is None or lab.group("unit") != unit:
                    continue
                end = starts[i + 1][0] if i + 1 < len(starts) else len(body)
                text = body[lab.end():end].strip("\n")
                hl = _HEADING_LINE.match(text)
                # The cut opens with the paragraph's own heading line; a piece
                # that does not is not what its label says, and is skipped.
                if not hl or hl.group("num") != lab.group("num"):
                    continue
                out.append({"lid": lid, "unit": unit, "url": url, "para": lab.group("num"),
                            "heading": _clean(hl.group("h") or ""), "text": text[hl.end():].strip("\n"),
                            "block": block_id, "how": how})
    except Exception:  # pragma: no cover - defensive
        logger.debug("[Restore] handed paragraphs unreadable", exc_info=True)
        return []
    return out


def _subparagraphs(text: str) -> list:
    """[(number or "", rendered text)] for a cut paragraph's body: each
    "N) ..." line opens a sub-paragraph, an indented "a) ..." line is an item
    of it, any other line continues the last. A paragraph with no numbered
    sub-paragraph is one piece with no number."""
    subs = []
    for raw in str(text or "").split("\n"):
        line = raw.strip()
        if not line:
            continue
        sm = _SUB.match(line) if not raw[:1].isspace() else None
        im = _ITEM.match(line) if raw[:1].isspace() else None
        if sm:
            subs.append([sm.group("n"), sm.group("t")])
        elif im and subs:
            subs[-1][1] += f" ({im.group('n')}) {im.group('t')}"
        elif subs:
            subs[-1][1] += " " + line
        else:
            subs.append(["", line])
    return [(n, _clean(t)) for n, t in subs if _clean(t)]


def excerpt(text: str, cap: int = MAX_EXCERPT_CHARS) -> str:
    """Whole sub-paragraphs from the first operative one, while they fit
    `cap`; "" when the first alone does not (the line then carries the
    heading only). A bare application line is skipped."""
    subs = _subparagraphs(text)
    if subs and _BARE_APPLIES.match(subs[0][1]) and len(subs) > 1:
        subs = subs[1:]
    parts = []
    for n, t in subs:
        piece = f"({n}) {t}" if n else t
        if len(" ".join(parts + [piece])) > cap:
            break
        parts.append(piece)
    return " ".join(parts)


def render_line(p: dict) -> str:
    """The line put into the answer for one restored paragraph."""
    unit = p["unit"]
    opener = unit[:1].upper() + unit[1:]
    where = f"[{opener}]({p['url']})" if p.get("url") else opener
    head = f" ({p['heading']})" if p.get("heading") else ""
    ex = excerpt(p.get("text") or "")
    line = f"Also in {where}, paragraph {p['para']}{head}"
    return f"{line}: \"{ex}\"" if ex else f"{line}."


def _cited_numbers(answer: str) -> dict:
    """{paragraph number: first position} for every number the answer gives
    after a paragraph word, lists and ranges included ("paragraphs 42 and
    43", "paras 42-44", "para 43(5)")."""
    out: dict = {}
    for m in _PARA_RX.finditer(answer or ""):
        body = re.sub(r"\([^)]{1,6}\)", "", m.group(1))
        nums = []
        for piece in re.split(r"[ \t]*(?:,|&|\band\b|\bor\b)[ \t]*", body):
            piece = piece.strip()
            rng = re.fullmatch(r"(\d{1,3}[A-Z]{0,2})[ \t]*(?:to|-|–)[ \t]*(\d{1,3}[A-Z]{0,2})", piece)
            if rng:
                nums += _expand_range(rng.group(1), rng.group(2))
            else:
                nums += re.findall(r"\d{1,3}[A-Z]{0,2}", piece)
        for n in nums:
            out.setdefault(n.upper(), m.start())
    return out


def _unit_rx(unit: str) -> re.Pattern:
    m = re.fullmatch(r"Schedule (\S+)", unit)
    if m:
        lab = re.escape(m.group(1))
        return re.compile(rf"\bSch(?:edule|ed)?\.?\s*{lab}\b|/schedule/{lab}\b", re.I)
    return re.compile(r"\bSchedule\b|/schedule\b", re.I)


def _group(records: list) -> tuple:
    """(paragraphs by key, blocks): one record per (lid, unit, para), the
    first; each block's kind and its paragraphs' keys, in order."""
    paras, blocks = {}, {}
    for r in records:
        key = (r["lid"], r["unit"], r["para"].upper())
        paras.setdefault(key, r)
        b = blocks.setdefault(r["block"], {"how": r["how"], "keys": []})
        if key not in b["keys"]:
            b["keys"].append(key)
    return paras, blocks


def _siblings(key, paras, blocks) -> list:
    """Paragraphs handed in a block with `key` for the same reason: every one
    of a block the query named; in a query-matched block, one whose heading
    shares a word with this one's."""
    unit_words = frozenset(re.findall(r"[a-z]+", key[1].lower()))
    mine = _word_stems(paras[key]["heading"], unit_words)
    out = []
    for b in blocks.values():
        if key not in b["keys"]:
            continue
        for k in b["keys"]:
            if k == key or k in out:
                continue
            if b["how"] == "cut" or (mine & _word_stems(paras[k]["heading"], unit_words)):
                out.append(k)
    return out


def restore_dropped_paragraphs(answer: str, records: Optional[Iterable[dict]],
                               max_lines: int = _MAX_LINES) -> tuple:
    """Put back a schedule paragraph code handed over and the answer left
    out. Returns (answer, lines added). See the module docstring."""
    if not answer or not records:
        return answer, 0
    try:
        paras, blocks = _group([r for r in records if isinstance(r, dict)])
        cited = _cited_numbers(answer)
        masked = _MD_LINK.sub(lambda m: m.group(1), answer)
        sentences = [set(_CONTENT_WORD.findall(s.lower())) for s in _SENT.split(masked)]
        adds = []      # (insert position, line)
        for key, p in paras.items():
            if len(adds) >= max_lines:
                break
            if key[2] in cited or not _unit_rx(p["unit"]).search(answer):
                continue
            sibs = [k for k in _siblings(key, paras, blocks) if k[2] in cited]
            if not sibs:
                continue
            ex = excerpt(p["text"])
            cw = set(_CONTENT_WORD.findall(ex.lower()))
            if cw and any(len(cw & s) >= 0.6 * len(cw) for s in sentences):
                continue
            at = min(cited[k[2]] for k in sibs)
            brk = re.compile(r"\n[ \t]*\n").search(answer, at)
            pos = brk.start() if brk else len(answer.rstrip())
            adds.append((pos, render_line(p)))
        if not adds:
            return answer, 0
        # Lines for one position keep the paragraphs' handed order; positions
        # are filled from the end backwards so earlier offsets hold.
        by_pos: dict = {}
        for pos, line in adds:
            by_pos.setdefault(pos, []).append(line)
        for pos in sorted(by_pos, reverse=True):
            answer = answer[:pos] + "".join("\n\n" + ln for ln in by_pos[pos]) + answer[pos:]
        return answer, len(adds)
    except Exception:  # pragma: no cover - defensive
        logger.debug("[Restore] paragraph restore skipped", exc_info=True)
        return answer, 0


_DISTINCT_MIN = 5
# Generic words only: a word every handed paragraph shares is not distinctive
# anyway (it is removed by the comparison below).
_DISTINCT_STOP = frozenset("""paragraph paragraphs schedule section which where under other
there their shall would""".split())


def misattributed_paragraphs(answer: str, records: Optional[Iterable[dict]],
                             min_shared: int = 3) -> list:
    """[(cited, apparently meant, sentence)] where a sentence cites exactly one
    handed paragraph P of a unit and shares at least `min_shared` of another
    handed paragraph Q's distinctive words (in Q's text and in no other handed
    paragraph of that unit) and none of P's. Reports only. Never raises."""
    try:
        paras, _blocks = _group([r for r in records or [] if isinstance(r, dict)])
        by_unit: dict = {}
        for key, p in paras.items():
            by_unit.setdefault((key[0], key[1]), {})[key[2]] = p
        masked = _MD_LINK.sub(lambda m: m.group(1), answer or "")
        found = []
        for (lid, unit), ps in by_unit.items():
            if not _unit_rx(unit).search(answer or ""):
                continue
            words = {n: {w for w in re.findall(r"[a-z]{%d,}" % _DISTINCT_MIN,
                                               (p["heading"] + " " + p["text"]).lower())
                         if w not in _DISTINCT_STOP} for n, p in ps.items()}
            distinct = {n: w - set().union(*(words[o] for o in words if o != n))
                        for n, w in words.items()}
            for s in _SENT.split(masked):
                nums = [n for n in _cited_numbers(s) if n in ps]
                if len(set(nums)) != 1:
                    continue
                p_num = nums[0]
                sw = set(re.findall(r"[a-z]{%d,}" % _DISTINCT_MIN, s.lower()))
                if sw & distinct[p_num]:
                    continue
                for q, d in distinct.items():
                    if q != p_num and len(sw & d) >= min_shared:
                        found.append((p_num, q, s.strip()[:300]))
                        break
        return found
    except Exception:  # pragma: no cover - defensive
        return []
