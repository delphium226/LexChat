"""Recorded revocations marked at the answer seam (FIX_PLAN P3.48).

**The defect.** A conversational answer that names an instrument from the
made-under record which legislation.gov.uk records as revoked, in whole or in
part, sometimes names it without saying so (6383 t1: `wave4_p333b`,
`wave5_p338b`, and SSI 2021/122 in `wave5_s51` r3). The Manager's limb names
the ids and asks for the mark (`search_scope._revocation_limb`), and the
Manager mostly does it, but not always.

**The lever (user decision): code marks it after the Manager writes**, as
P3.13's and P3.12's restores put back what the Worker had. For each instrument
the answer names (a link whose URL is the instrument or one of its provisions,
its id, its SI number, or the title the record holds) that the turn's
made-under record says is revoked in whole or in part, and that the answer
does not already mark near any mention of it (the list item, or the sentence
and the one after it), an inline parenthetical goes after its first mention:

    "(recorded on legislation.gov.uk as revoked in part)"

or, inside a parenthesis that holds only the mention, "(SSI 1901/1; recorded
...)"; after a link to one of its provisions, or after the last of a run of
instruments ("A, B and C"), the mark names its instrument: "(SSI 1901/1 is
recorded ...)".

Only what the record states: in whole or in part; for a whole revocation, the
revoking instrument and the date where the record line carries them cleanly;
never "in force". The checked date is the footer's ("Revocations of those
instruments are as recorded on legislation.gov.uk on D"); a mark from the
section-family route, whose entries put no date in the footer, carries it.

Nothing goes inside a quotation, a code span, a fenced block, a heading, a
`[...]` label or a link (a mark goes after the link's closing parenthesis),
or after a title that is the head of a longer one. Fail-soft and idempotent:
the mark itself is a revocation word in the item, so a second pass adds
nothing; an answer with nothing to mark comes back byte-identical.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger("agent")

__all__ = ["revocation_facts", "mark_revoked_instruments", "plan_revocation_marks",
           "MARK_PER_CLASS"]

# At most this many marks per class (whole, part), as the limb names at most
# `search_scope._REVOKED_NAMED` ids per class.
MARK_PER_CLASS = 8

WHOLE = ("revoked", "revoked_undated", "revoked_later")
PART = ("partly",)

_PART_PHRASE = "recorded on legislation.gov.uk as revoked in part"

# `revocation_record.describe`'s line for a whole revocation, in its plain
# form only: one date, no quoted qualification, no record's words.
_WHOLE_LINE = re.compile(
    r"^recorded (as (?:revoked|repealed|lapsed|omitted|ceasing to have effect)) in whole "
    r"(by its own provisions|by ([a-z]+/\d{4}/\d+)), "
    r"(no date recorded|with effect from (\d{4}-\d{2}-\d{2})(, a date still to come)?)$")
_WHOLE_HEAD = re.compile(
    r"^recorded (as (?:revoked|repealed|lapsed|omitted|ceasing to have effect)) in whole "
    r"(by its own provisions|by ([a-z]+/\d{4}/\d+))\b")

# A word that marks a revocation already, near a mention.
_REVOKE_WORD = re.compile(
    r"\b(?:revok\w*|revoc\w*|repeal\w*|ceas\w*\s+to\s+have\s+effect|lapsed"
    r"|remov\w*\s+(?:a\s+)?provisions?\s+wholly\s+or\s+in\s+part)\b", re.I)
# "no longer in force, having been revoked" states a revocation; it is not a negation.
_NEGATED = re.compile(
    r"\b(?:no(?!\s+longer)|not|never|none|without)\b[^.;\n]{0,40}\b(?:revok|revoc|repeal)", re.I)
# A title is not a mark: "(Consequential Amendment, Revocation and Saving Provision)".
_TITLE_PAREN = re.compile(r"\([^()\n]*\b(?:Revocations?|Repeals?)\b[^()\n]*\)", re.I)
_LIST_ITEM = re.compile(r"^\s*(?:[*+-]|\d{1,3}[.)])\s+")
_TABLE_ROW = re.compile(r"^\s*\|")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s")
_SENTENCE_END = re.compile(r"(?<=[.!?])[)\"'”’]*\s+(?=[A-Z(*\[\"“])")


def _label(lid: str) -> str:
    from .instrument_lookup import _LABELS

    typ, _, rest = (lid or "").partition("/")
    yr, _, num = rest.partition("/")
    fmt = _LABELS.get(typ)
    return fmt.format(y=yr, n=num) if fmt and yr and num else lid


# ---------------------------------------------------------------------------
# the turn's facts
# ---------------------------------------------------------------------------

def revocation_facts(searches) -> dict:
    """{lid: {"status", "title", "line", "checked", "dated_footer"}} from the
    turn's scope log: every `made_under` entry's `revoked` map (P3.48, written
    by `record_made_under` and the section-family route). `dated_footer` is
    whether the footer will state the checked date (a `made_under` entry with
    `revocations`). Never raises."""
    out: dict = {}
    try:
        rows = [e for e in (searches or []) if isinstance(e, dict) and e.get("tool") == "made_under"]
        dated = any(isinstance(e.get("revocations"), dict) and e["revocations"].get("checked")
                    for e in rows)
        for e in rows:
            for lid, f in (e.get("revoked") or {}).items():
                if not isinstance(f, dict) or f.get("status") not in WHOLE + PART:
                    continue
                out.setdefault(str(lid).lower(), {
                    "status": f.get("status"), "title": str(f.get("title") or ""),
                    "line": str(f.get("line") or ""), "checked": f.get("checked"),
                    "dated_footer": dated})
    except Exception:
        logger.debug("[Revocations] facts skipped", exc_info=True)
        return {}
    return out


def _phrase(fact: dict) -> str:
    """What the record states, as a clause beginning "recorded on legislation.gov.uk"."""
    st = fact.get("status")
    if st in PART:
        phrase = _PART_PHRASE
    else:
        line = fact.get("line") or ""
        m = _WHOLE_LINE.match(line)
        h = m or _WHOLE_HEAD.match(line)
        verb = h.group(1) if h else "as revoked"
        by = ("by its own provisions" if h and h.group(2) == "by its own provisions"
              else f"by {_label(h.group(3))}" if h and h.group(3) else "")
        phrase = f"recorded on legislation.gov.uk {verb} in whole" + (f" {by}" if by else "")
        if m and m.group(5):
            phrase += f", with effect from {m.group(5)}" + (", a date still to come" if m.group(6) else "")
        elif m:
            phrase += ", no date recorded"
        elif st == "revoked_later":
            # Never let a removal still to come read as done.
            phrase += ", from a date still to come"
    if not fact.get("dated_footer") and fact.get("checked"):
        phrase += f", as checked on {fact['checked']}"
    return phrase


# ---------------------------------------------------------------------------
# mentions
# ---------------------------------------------------------------------------

def _masks(answer: str) -> list:
    """Spans no mark goes into and no mention is read from: restored notes,
    fenced code blocks."""
    from .citation_links import _RESTORED_NOTE

    spans = [(m.start(), m.end()) for m in _RESTORED_NOTE.finditer(answer)]
    spans += [(m.start(), m.end()) for m in re.finditer(r"```.*?(?:```|\Z)", answer, re.S)]
    return spans


def _inside(spans, s, e) -> bool:
    return any(s < b and a < e for a, b in spans)


_PROVISION_WORDS = re.compile(
    r"\b(?:reg|regs|regulations?|art|arts|articles?|sections?|s|ss|paras?|paragraphs?"
    r"|sch|schedules?|rules?|r|parts?)\b\.?\s*\d", re.I)


def _label_rx(lid: str):
    from .citation_links import _SI_NAME

    typ, _, rest = (lid or "").partition("/")
    yr, _, num = rest.partition("/")
    if not (yr.isdigit() and num.isdigit()):
        return None
    return re.compile(rf"(?:(?<![\w/]){re.escape(lid)}|{_SI_NAME}(?<![\w/]){yr}/{num})(?![\w/])", re.I)


def _mentions(answer: str, lid: str, title: str, links: list, masks: list) -> list:
    """[(start, end, kind)] of every mention of `lid`, in order. kind: "link"
    (a link to the instrument), "plink" (a link to one of its provisions), "id",
    "cite", "title". Mentions inside a link are the link."""
    from .citation_links import _SI_NAME, _below_instrument, _title_pattern, instrument_key
    from .source_naming import SI_TYPES, heads_longer_title, nameable_title

    out = []
    link_spans = [(s, e) for s, e, _u in links]
    label_rx = _label_rx(lid)
    for s, e, url in links:
        if instrument_key(url) == lid and not _inside(masks, s, e):
            # "[SSI 2020/351](.../regulation/20)": a provision URL under a
            # label that names the instrument alone names the instrument.
            label = answer[s:e].split("](", 1)[0]
            whole = (not _below_instrument(url)
                     or (label_rx is not None and label_rx.search(label)
                         and not _PROVISION_WORDS.search(label)))
            out.append((s, e, "link" if whole else "plink"))
    cands = []
    if title and not title.endswith("…") and nameable_title(title):
        rx = _title_pattern(title)
        if rx is not None:
            cands += [(m.start(), m.end(), "title") for m in rx.finditer(answer)
                      if not heads_longer_title(answer[m.end():m.end() + 120])]
    typ, _, rest = lid.partition("/")
    yr, _, num = rest.partition("/")
    if yr.isdigit() and num.isdigit():
        cands += [(m.start(), m.end(), "id") for m in re.finditer(
            rf"(?<![\w/]){re.escape(lid)}(?![\w/])", answer, re.I)]
        if typ in SI_TYPES:
            cands += [(m.start(), m.end(), "cite") for m in re.finditer(
                rf"{_SI_NAME}(?<![\w/]){yr}/{num}(?![\w/])", answer, re.I)]
    for s, e, k in cands:
        if not _inside(link_spans, s, e) and not _inside(masks, s, e):
            out.append((s, e, k))
    out.sort(key=lambda x: (x[0], -x[1]))
    # one mention per span: the longest at each start, none nested in another
    kept = []
    for m in out:
        if kept and m[0] < kept[-1][1]:
            continue
        kept.append(m)
    return kept


def _unit(answer: str, pos: int) -> tuple:
    """(start, end) of the text a mark near `pos` would sit in: the list item
    or table row the mention is on; else its sentence and the next one."""
    ls = answer.rfind("\n", 0, pos) + 1
    le = answer.find("\n", pos)
    le = len(answer) if le == -1 else le
    line = answer[ls:le]
    if _LIST_ITEM.match(line) or _TABLE_ROW.match(line):
        # continuation lines: indented, not a new item, not blank
        end = le
        while end < len(answer):
            nxt_e = answer.find("\n", end + 1)
            nxt_e = len(answer) if nxt_e == -1 else nxt_e
            nxt = answer[end + 1:nxt_e]
            if not nxt.strip() or _LIST_ITEM.match(nxt) or not nxt.startswith((" ", "\t")):
                break
            end = nxt_e
        return ls, end
    # a prose paragraph: blank-line delimited
    ps = answer.rfind("\n\n", 0, pos)
    ps = 0 if ps == -1 else ps + 2
    pe = answer.find("\n\n", pos)
    pe = len(answer) if pe == -1 else pe
    para = answer[ps:pe]
    bounds = [0] + [m.end() for m in _SENTENCE_END.finditer(para)] + [len(para)]
    rel = pos - ps
    for i in range(len(bounds) - 1):
        if bounds[i] <= rel < bounds[i + 1]:
            end = bounds[i + 2] if i + 2 < len(bounds) else bounds[i + 1]
            return ps + bounds[i], ps + end
    return ps, pe


def _marked(text: str, titles) -> bool:
    """The text already says a revocation (not negated, not inside a title or a URL)."""
    t = re.sub(r"\]\((?:https?://)[^)\s]*\)", "]", text)
    t = re.sub(r"https?://\S+", " ", t)
    for title in titles:
        if title:
            t = t.replace(title, " ")
    t = _TITLE_PAREN.sub(" ", t)
    for m in _REVOKE_WORD.finditer(t):
        window = t[max(0, m.start() - 60):m.end()]
        if not _NEGATED.search(window):
            return True
    return False


def _guarded(answer: str, s: int, e: int) -> str:
    """Why a mark must not go at a mention [s, e), or ""."""
    ls = answer.rfind("\n", 0, s) + 1
    line = answer[ls:s]
    if _HEADING.match(answer[ls:ls + 8]):
        return "heading"
    if (line.count('"') % 2 or line.count("“") > line.count("”") or line.count("`") % 2):
        return "quoted"
    # inside a [...] label that is not this mention's own link
    if line.count("[") > line.count("]"):
        return "bracketed"
    return ""


def _insertion(answer: str, s: int, e: int, kind: str) -> tuple:
    """(position, wrap): where the mark goes after the mention [s, e), and
    whether it goes inside a parenthesis that holds only the mention."""
    end = e
    ls = answer.rfind("\n", 0, s) + 1
    # a closing emphasis straight after the mention: "**SSI 2020/351**"
    for mark in ("**", "__", "*", "_"):
        if answer.startswith(mark, end) and answer[ls:s].count(mark) % 2 == 1:
            end += len(mark)
            break
    before = answer[ls:s].rstrip("*_[")
    if kind != "plink" and answer.startswith(")", end) and before.endswith("("):
        return end, True
    return end, False


# Any instrument named by number or id, for `_ends_run`.
_ANY_INSTRUMENT = re.compile(
    r"(?:\b(?:S\.\s?S\.\s?I\.?|SSI|S\.\s?I\.?|SI|UKSI|WSI|SR)\s*\d{4}/\d{1,5}"
    r"|(?<![\w/])[a-z]{2,5}/\d{4}/\d{1,5})(?![\w/])", re.I)
_RUN_JOIN = re.compile(r"^[\s*_\])]*(?:,\s*(?:and|or)?|\s(?:and|or))[\s*_\[(]*$", re.I)
_RUN_NEXT = _RUN_JOIN


def _ends_run(answer: str, s: int, pos: int) -> bool:
    """The mention at [s, pos) is the last of a run of two or more instruments
    joined by commas, "and" or "or": another instrument straight before it, none
    straight after it."""
    ls = answer.rfind("\n", 0, s) + 1
    le = answer.find("\n", pos)
    le = len(answer) if le == -1 else le
    prev = [m for m in _ANY_INSTRUMENT.finditer(answer, ls, s) if m.end() <= s]
    if not prev or not _RUN_JOIN.match(re.sub(r"\]\([^)\s]*\)", "]", answer[prev[-1].end():s])):
        return False
    nxt = _ANY_INSTRUMENT.search(answer, pos, le)
    return not (nxt and _RUN_NEXT.match(re.sub(r"\]\([^)\s]*\)", "]", answer[pos:nxt.start()])))


def plan_revocation_marks(answer: str, facts: dict) -> list:
    """[(position, text, lid, cls)] the marks to insert, in answer order; cls
    "whole" or "part". Pure."""
    from .citation_links import _links_at

    if not answer or not facts:
        return []
    links = _links_at(answer)
    masks = _masks(answer)
    titles = [f.get("title") for f in facts.values() if f.get("title")]
    plans = []
    for lid, fact in facts.items():
        ms = _mentions(answer, lid, fact.get("title") or "", links, masks)
        if not ms:
            continue
        if any(_marked(answer[a:b], titles) for a, b in {_unit(answer, m[0]) for m in ms}):
            continue
        eligible = [m for m in ms if not _guarded(answer, m[0], m[1])]
        anchor = next((m for m in eligible if m[2] != "plink"), None) or \
            next((m for m in eligible if m[2] == "plink"), None)
        if anchor is None:
            continue
        # a mention straight after the anchor ("Title (SSI 2020/351)",
        # "**SSI 2020/351**: Title") is the same naming: mark after the last.
        i = eligible.index(anchor)
        while i + 1 < len(eligible) and eligible[i + 1][2] != "plink" \
                and 0 <= eligible[i + 1][0] - eligible[i][1] <= 6:
            i += 1
            anchor = eligible[i]
        pos, wrap = _insertion(answer, anchor[0], anchor[1], anchor[2])
        phrase = _phrase(fact)
        if anchor[2] == "plink" or (not wrap and _ends_run(answer, anchor[0], pos)):
            # A provision's link, or the last of a run of instruments ("A, B
            # and C (...)"), where a bare parenthesis would read as about
            # the provision or the whole run: the mark names its instrument.
            text = f" ({_label(lid)} is {phrase})"
        elif wrap:
            text = f"; {phrase}"
        else:
            text = f" ({phrase})"
        plans.append((pos, text, lid, "whole" if fact.get("status") in WHOLE else "part"))
    plans.sort()
    out, n = [], {"whole": 0, "part": 0}
    for p in plans:
        if n[p[3]] >= MARK_PER_CLASS:
            continue
        n[p[3]] += 1
        out.append(p)
    return out


def mark_revoked_instruments(answer: str, searches) -> tuple:
    """(answer, marks added). Byte-identical where nothing is to be marked;
    idempotent; never raises."""
    if not answer:
        return answer, 0
    try:
        facts = revocation_facts(searches)
        if not facts:
            return answer, 0
        plans = plan_revocation_marks(answer, facts)
        out = answer
        for pos, text, _lid, _cls in reversed(plans):
            out = out[:pos] + text + out[pos:]
        return out, len(plans)
    except Exception:  # pragma: no cover - defensive
        logger.debug("[Revocations] marking skipped", exc_info=True)
        return answer, 0
