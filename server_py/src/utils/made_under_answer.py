"""Instruments made under a section the answer cites, listed at the answer
seam (FIX_PLAN P3.51 / P3.52, fix A2, Session 52).

**The defect.** Q16 (6354) asks what mechanisms could lessen a local
authority's duty to accommodate the homeless. The made-under record holds the
Homeless Persons (Suspension of Referrals between Local Authorities)
(Scotland) Order 2022 (`ssi/2022/356`, made under s.33A of the Housing
(Scotland) Act 1987). The answers cite s.33 or s.33A in 4 of 6 stored runs and
name the Order in none; P3.51's Worker block reached the Worker and the
Worker did not use it.

**The lever: code lists them after the Manager writes**, as P3.13, P3.12 and
P3.48 put back what the research had. For each section of an Act the
conversational answer cites, by a legislation.gov.uk link or in words ("s.33A
of the 1987 Act", "section 38 of the Transport (Scotland) Act 2001") resolved
to an Act the turn retrieved, the record's instruments made under that
section (and, for a section cited without a letter, under its lettered
sections: s.33 -> s.33A) that the answer does not already name are listed in
one short block at the end of the answer, at most `MAX_LINES` lines, with
each instrument's title as the record holds it and its revocation as
legislation.gov.uk records it (P3.33's flag, P3.48's wording). An instrument
recorded as revoked in whole is left out and counted.

Off on the parliamentary bots and in Deep Research; no database until the
record is loaded; an answer with nothing to list comes back byte-identical;
idempotent (the block's own heading is never added twice); never raises.
"""
from __future__ import annotations

import logging
import re
from typing import Iterable, Optional

logger = logging.getLogger("agent")

__all__ = ["cited_sections", "plan_made_under_lines", "made_under_answer_block",
           "list_made_under_for_answer", "MADE_UNDER_ANSWER_HEAD", "MAX_LINES"]

MAX_LINES = 3
LISTED_PER_LINE = 3   # a family with more not-named instruments gets no line
MADE_UNDER_ANSWER_HEAD = ("Instruments made under the sections cited above, from the "
                          "made-under record")

_PRIMARY = r"(?:ukpga|asp|anaw|asc|nia|apni|ukla|aep|aosp|apgb|mwa|nisi)"
_SECTION_URL = re.compile(
    r"legislation\.gov\.uk/(?:id/)?(" + _PRIMARY + r"/\d{4}/\d+)/section/(\d{1,4})([A-Z]{0,3})\b")
_MD_LINK = re.compile(r"\[([^\]\n]{1,300})\]\((https?://[^)\s]+)\)")
# "s.33A of the 1987 Act", "sections 31 and 33A of the Housing (Scotland) Act
# 1987", "s.29(3) and (4) of the 1987 Act".
_PLAIN = re.compile(
    r"\b(?i:sections?|ss?\.)\s*(?P<list>\d{1,4}[A-Z]{0,3}(?:\s?\([^)\s]{1,6}\))*"
    r"(?:\s*(?:,|and|or|to)\s*(?:(?i:sections?|ss?\.)\s*)?(?:\d{1,4}[A-Z]{0,3})?"
    r"(?:\s?\([^)\s]{1,6}\))*)*)"
    r"\s+(?:of|in|under)\s+the\s+(?:(?P<year>\d{4}) Act\b|(?P<title>[A-Z][\w,()'’&. -]{2,150}?"
    r" Act \d{4})\b)")
_BARE = re.compile(
    r"\b(?i:sections?|ss?\.)\s*(?P<list>\d{1,4}[A-Z]{0,3}(?:\s?\([^)\s]{1,6}\))*"
    r"(?:\s*(?:,|and|or|to)\s*(?:(?i:sections?|ss?\.)\s*)?(?:\d{1,4}[A-Z]{0,3})?"
    r"(?:\s?\([^)\s]{1,6}\))*)*)")
_BARE_REACH = 250
_ANY_ACT = re.compile(r"\b(?:Act \d{4}|\d{4} Act)\b")
_NUM = re.compile(r"(?<![\w(])(\d{1,4})([A-Z]{0,3})(?![\w)])")
_WS = re.compile(r"\s+")


def _norm_title(t: str) -> str:
    return _WS.sub(" ", re.sub(r"^the\s+", "", str(t or "").strip(), flags=re.I)).lower()


def _year(lid: str) -> str:
    parts = str(lid or "").split("/")
    return parts[1] if len(parts) == 3 else ""


def cited_sections(answer: str, titles: Optional[dict] = None) -> list:
    """`[(act_id, num, letters)]` each Act section the answer cites, in the
    answer's order, each once: every legislation.gov.uk section link, and every
    section named in words with the Act it is "of", where that Act resolves to
    exactly one id: by title against `titles` ({id: title}, the turn's own),
    or "the 1987 Act" to the one primary Act of that year the answer links or
    the turn retrieved. Pure; never raises."""
    out, seen = [], set()
    try:
        text = answer or ""
        titles = {str(k).lower(): v for k, v in (titles or {}).items() if k}
        found = []   # (pos, act, num, letters)
        linked = set()
        for m in _SECTION_URL.finditer(text):
            found.append((m.start(), m.group(1).lower(), m.group(2), m.group(3)))
            linked.add(m.group(1).lower())
        plain = _MD_LINK.sub(lambda m: m.group(1) + " " * (len(m.group(0)) - len(m.group(1))), text)
        by_title: dict = {}
        for lid, t in titles.items():
            if re.fullmatch(_PRIMARY + r"/\d{4}/\d+", lid) and t:
                by_title.setdefault(_norm_title(t), set()).add(lid)
        primaries = {lid for lid in titles if re.fullmatch(_PRIMARY + r"/\d{4}/\d+", lid)} | linked
        # Where an Act was last placed: a section link's end, or a resolved
        # "of the ... Act" cite's end. A bare "section 33" takes it (below).
        anchors = [(m.end(), m.group(1).lower()) for m in _SECTION_URL.finditer(text)]
        taken = [(m.start(), m.end()) for m in _MD_LINK.finditer(text)
                 if _SECTION_URL.search(m.group(2))]
        for m in _PLAIN.finditer(plain):
            taken.append((m.start(), m.end()))
            if m.group("year"):
                ids = {lid for lid in primaries if _year(lid) == m.group("year")}
            else:
                ids = by_title.get(_norm_title(m.group("title")), set())
            if len(ids) != 1:
                continue
            (act,) = ids
            anchors.append((m.end(), act))
            lst = re.sub(r"\([^)\s]{1,6}\)", " ", m.group("list"))
            for n in _NUM.finditer(lst):
                found.append((m.start(), act, n.group(1), n.group(2)))
        # "Under section 31(2) of the 1987 Act, an authority may refer the
        # applicant under section 33": a section named with no Act is the
        # Act placed last on the same line, within _BARE_REACH characters,
        # with no other Act named between them; otherwise it is not read.
        for m in _BARE.finditer(plain):
            if any(a <= m.start() < b for a, b in taken):
                continue
            prev = [a for a in anchors if a[0] <= m.start()]
            if not prev:
                continue
            pos, act = max(prev)
            between = plain[pos:m.start()]
            if m.start() - pos > _BARE_REACH or "\n" in between or _ANY_ACT.search(between):
                continue
            lst = re.sub(r"\([^)\s]{1,6}\)", " ", m.group("list"))
            for n in _NUM.finditer(lst):
                found.append((m.start(), act, n.group(1), n.group(2)))
        for _pos, act, num, letters in sorted(found, key=lambda f: f[0]):
            key = (act, num, letters)
            if key not in seen:
                seen.add(key)
                out.append(key)
    except Exception:
        return []
    return out


def _label(lid: str) -> str:
    from .revocation_marks import _label as label
    return label(lid)


_MARKS = {
    "partly": "recorded on legislation.gov.uk as revoked in part",
    "qualified": "recorded on legislation.gov.uk with a qualified removal only",
    "revoked_later": "recorded on legislation.gov.uk as revoked from a date still to come",
}
_GONE = ("revoked", "revoked_undated")


def _act_short(act_title: str, act_id: str) -> str:
    return act_title or act_id


def plan_made_under_lines(answer: str, cited: list, rows_by_act: dict,
                          today=None) -> list:
    """The block's lines, at most MAX_LINES. `rows_by_act`: {act_id: rows},
    each row `(provision, legislation_id, title, act_title, revocation,
    revocation_checked)` as `made_under_store.section_family_rows` returns
    them. One line per cited section, in the answer's order, that has from one
    to LISTED_PER_LINE instruments not revoked in whole that the answer does
    not name (a larger family gets no line); a cited section with no letter
    takes its lettered sections' instruments too. Pure."""
    from .made_under import _names_instrument, _rev_flag, _plain
    from .instrument_lookup import extract_instrument_citations
    from .revocation_record import category

    low = _WS.sub(" ", answer or "").lower()
    named_ids = {f"{t}/{y}/{n}" for t, y, n in extract_instrument_citations(answer or "", limit=999)}
    lines, done = [], set()
    for act, num, letters in cited:
        rows = rows_by_act.get(act) or []
        insts: dict = {}
        act_title = ""
        for row in rows:
            prov, lid, title, a_title = row[:4]
            m = re.fullmatch(r"section/(\d+)([A-Z]*)", str(prov or ""))
            if not m or m.group(1) != num or not lid:
                continue
            if letters and m.group(2) != letters:
                continue
            act_title = act_title or str(a_title or "")
            e = insts.setdefault(lid, {"title": str(title or lid), "secs": []})
            sec = f"s.{m.group(1)}{m.group(2)}"
            if sec not in e["secs"]:
                e["secs"].append(sec)
            checked = row[5] if len(row) > 5 else None
            try:
                e["cat"] = category(_rev_flag(row[4] if len(row) > 4 else None), today) \
                    if checked else "unchecked"
            except Exception:
                e["cat"] = "unchecked"
        live = sorted((lid for lid, e in insts.items()
                       if e["cat"] not in _GONE and lid not in done
                       and not _names_instrument(answer or "", low, named_ids, lid, e["title"])),
                      key=lambda lid: _id_key(lid))
        if not live:
            continue
        gone = sum(1 for e in insts.values() if e["cat"] in _GONE)
        act_name = _plain(_act_short(act_title, act), 120)
        cited_label = f"s.{num}{letters} of the {act_name}"

        def _one(lid):
            e = insts[lid]
            mark = _MARKS.get(e["cat"])
            ref = f"{_label(lid)}; {mark}" if mark else _label(lid)
            return f"{_plain(e['title'])} ({ref}), made under {' and '.join(e['secs'])}"

        if len(live) > LISTED_PER_LINE:
            # A large family (17 concession scheme orders under s.40, 36
            # instruments under s.95) is the made-under tool's to list, not a
            # line under an answer: counted, it adds a number and no mechanism.
            continue
        text = f"{cited_label}: " + "; ".join(_one(lid) for lid in live) + "."
        if gone:
            text = text[:-1] + (f" ({gone} more recorded on legislation.gov.uk as revoked in "
                                "whole, not listed).")
        done.update(live)
        lines.append(text)
    return lines[:MAX_LINES]


def _id_key(lid: str) -> tuple:
    parts = str(lid).split("/")
    try:
        return (int(parts[-2]), int(parts[-1]))
    except (ValueError, IndexError):
        return (0, 0)


def made_under_answer_block(lines: list) -> str:
    """The block the lines go in, or "" for none."""
    if not lines:
        return ""
    return (f"\n\n{MADE_UNDER_ANSWER_HEAD} (each instrument's own preamble names the section "
            "as a power it was made under; the record does not establish that no other "
            "instrument was made under these sections):\n"
            + "\n".join(f"- {line}" for line in lines))


def titles_from(sources: Iterable[dict] = (), titles: Optional[dict] = None) -> dict:
    """{legislation_id: title} from the turn's retrieved sources and lookups."""
    out: dict = {}
    for lid, t in (titles or {}).items():
        if lid and t:
            out.setdefault(str(lid).lower(), str(t))
    for s in sources or []:
        if not isinstance(s, dict):
            continue
        lid = str(s.get("_lid") or "").lower()
        t = str(s.get("title") or "")
        if lid and t and t.lower() != lid:
            out.setdefault(lid, t)
    return out


async def list_made_under_for_answer(answer: str, sources: Iterable[dict] = (),
                                     titles: Optional[dict] = None) -> tuple:
    """(answer, lines added). The block at the end of the answer, or the
    answer byte-identical. Never raises; no database until the record is
    loaded."""
    if not answer or MADE_UNDER_ANSWER_HEAD in answer:
        return answer, 0
    try:
        from ..services.made_under_store import _STATE, section_family_rows

        if not _STATE.get("available"):
            return answer, 0
        cited = cited_sections(answer, titles_from(sources, titles))
        if not cited:
            return answer, 0
        rows_by_act: dict = {}
        for act in dict.fromkeys(a for a, _n, _l in cited):
            bases = list(dict.fromkeys(n for a, n, _l in cited if a == act))
            rows, _cov = await section_family_rows(act, bases)
            rows_by_act[act] = rows
        lines = plan_made_under_lines(answer, cited, rows_by_act)
        if not lines:
            return answer, 0
        return answer.rstrip() + made_under_answer_block(lines), len(lines)
    except Exception:  # pragma: no cover - defensive
        logger.debug("[MadeUnder] answer listing skipped", exc_info=True)
        return answer, 0
