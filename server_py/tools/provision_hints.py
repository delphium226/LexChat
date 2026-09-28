"""P3.2 candidate lever, dry run: "the lawyer's challenge is a retrieval hint".

The idea under test: when a lawyer's message names a provision ("Article
25(4)", "Chapter V of Annex XIV", "s.38"), code fetches that provision's text
before the model answers and hands it over verbatim, instead of leaving the
model to argue from the lawyer's paraphrase or its own earlier answer. Where the
message puts two defined terms in quotation marks, code also finds every place
an instrument in play uses both (a bounded concordance: the Ctrl-F a lawyer
would do). Nothing here is wired into the product. This measures, over every
user turn of the transcript export, what the lever would reach:

  * how often a lawyer names a provision at all;
  * whether the provision resolves to ONE instrument (named in the same
    sentence, or the only instrument already in the conversation that has it),
    to several (ambiguous: the product would have to show each, labelled), or
    to none;
  * whether LEX holds it, and whether code can cut the paragraph / Annex
    chapter / section named out of the provision LEX returns (an Annex is ONE
    provision there: Annex XIV of 2011/142 is 89K characters);
  * how many characters would be handed over.

    python -m tools.provision_hints dryrun [--session ID ...] [--list]
                                           [--show] [--chars N]

`--list` prints one line per turn with the references it found and how each
resolved; `--show` prints the text that would be handed over. Both echo what
lawyers typed and what the law says about their matter: keep that output out of
the repo. The summary alone carries no question text. Needs LEX (network);
every provision list is fetched once per run.

Resolution is deliberately conservative (Invariant 1): handing one
instrument's text over under another's name is the worst outcome this lever
can have, so an ambiguous reference is reported as such and never guessed.
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import statistics
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS.parent))

LEX = "https://lex.lab.i.ai.gov.uk"
PER_REF_CAP = 6_000  # what a product block would plausibly allow per reference

# --- provision references -----------------------------------------------------

_SUB = r"(?:\s?\((?:\d{1,3}[a-z]?|[a-z]{1,4})\))*"
_NUM = r"\d{1,3}[A-Za-z]{0,2}"
_ITEM = _NUM + _SUB
_LIST = rf"({_ITEM}(?:\s*(?:,|and|or|&)\s*{_ITEM})*)"
_ROMAN = r"[IVXL]{1,6}"

PROVISION_PATTERNS = (
    # Annex forms first, so "Section 3 of Chapter II of Annex X" is not also
    # read as a UK section.
    ("annex", re.compile(
        rf"\bSection\s+(\d{{1,2}})\s+of\s+Chapter\s+({_ROMAN})\s+of\s+Annex\s+({_ROMAN})\b")),
    ("annex", re.compile(rf"\bChapter\s+({_ROMAN})\s+of\s+(?:the\s+)?Annex\s+({_ROMAN})\b")),
    ("annex", re.compile(
        rf"\bAnnex\s+({_ROMAN})\b(?:\s*,?\s*Chapter\s+({_ROMAN})\b)?"
        rf"(?:\s*,?\s*Section\s+(\d{{1,2}})\b)?")),
    ("article", re.compile(rf"\bArt(?:icles?|s?\.)\s*{_LIST}", re.I)),
    ("section", re.compile(rf"\b(?:sections?|ss?\.)\s*{_LIST}", re.I)),
    # "Regulation 12", never "Regulation 555/2008" or "Regulation (EC)".
    ("regulation", re.compile(rf"\b(?:regulations?|regs?\.)\s+{_LIST}(?![/\d])", re.I)),
    ("schedule", re.compile(r"\b(?:schedules?|sch\.)\s*(\d{1,2}[A-Z]?|[A-Z]\d?)\b", re.I)),
)

_ITEM_RX = re.compile(rf"({_NUM})({_SUB})")


@dataclass
class Ref:
    kind: str
    num: str                       # "25", "36A", or the Annex numeral
    sub: str = ""                  # "(4)" / "(1)(a)"
    chapter: str = ""              # Annex chapter numeral
    section: str = ""              # Annex section number
    start: int = 0
    end: int = 0

    def label(self) -> str:
        if self.kind == "annex":
            s = f"Annex {self.num}"
            if self.chapter:
                s += f" Ch {self.chapter}"
            if self.section:
                s += f" s.{self.section}"
            return s
        return f"{self.kind} {self.num}{self.sub}"


def extract_provision_refs(text: str) -> list:
    """Every provision `text` names, in order, deduplicated. Never raises."""
    try:
        text = text or ""
        masked = list(text)
        found: list = []
        for kind, rx in PROVISION_PATTERNS:
            for m in rx.finditer("".join(masked)):
                g = m.groups()
                if kind == "annex":
                    if rx.pattern.startswith(r"\bSection"):
                        refs = [Ref("annex", g[2], chapter=g[1], section=g[0])]
                    elif rx.pattern.startswith(r"\bChapter"):
                        refs = [Ref("annex", g[1], chapter=g[0])]
                    else:
                        refs = [Ref("annex", g[0], chapter=g[1] or "", section=g[2] or "")]
                elif kind == "schedule":
                    refs = [Ref("schedule", g[0])]
                else:
                    refs = [Ref(kind, n, re.sub(r"\s", "", s))
                            for n, s in _ITEM_RX.findall(g[0])]
                for r in refs:
                    r.start, r.end = m.start(), m.end()
                    found.append(r)
                for i in range(m.start(), m.end()):
                    masked[i] = " "
        found.sort(key=lambda r: r.start)
        out, seen = [], set()
        for r in found:
            key = r.label()
            if key not in seen:
                seen.add(key)
                out.append(r)
        return out
    except Exception:
        return []


# --- instrument mentions ------------------------------------------------------

_EU_RX = re.compile(
    r"\b(Regulation|Directive|Decision)\s*\((?:EC|EU|EEC)\)\s*(?:No\.?\s*)?(\d{1,4})/(\d{4})\b",
    re.I)
_BARE_EU_RX = re.compile(r"(?<![\d/])(\d{2,4})/(\d{4})(?![\d/])")
# A title is a run of capitalised words (and the connectors legislation titles
# use), ending in Act / Regulations / Order / Rules and a year. The run may
# start mid-sentence ("... under section 9 of the Example (Scotland) Act
# 2001") or on a capitalised sentence opener; leading connectors are trimmed and
# each suffix is tried, longest first.
_TW = r"(?:[A-Z][\w'’.\-]*|\([A-Z][\w\s.'\-]*\)|and|of|the|for|in|on|to|etc\.?)"
_TITLE_RX = re.compile(
    rf"((?:{_TW}\s+)*?{_TW}\s+(?:[Aa]ct|Regulations|Order|Rules))\s+(\d{{4}})\b")
_LEAD_CONNECTORS = re.compile(r"^(?:(?:and|of|the|for|in|on|to)\s+)+")
_URL_RX = re.compile(
    r"legislation\.gov\.uk/(?:id/)?([a-z]{2,5})/(\d{4})/(\d{1,5})", re.I)
_EU_TYPE = {"regulation": "eur", "directive": "eudr", "decision": "eudn"}


def _norm_title(t: str) -> str:
    t = re.sub(r"\s+", " ", t or "").strip().lower()
    return t[4:] if t.startswith("the ") else t


class Lex:
    """LEX calls, memoised for the run."""

    def __init__(self):
        import httpx  # noqa: PLC0415

        self.client = httpx.Client(timeout=60)
        self.provisions: dict = {}
        self.titles: dict = {}
        self.names: dict = {}

    def title_of(self, lid: str) -> str:
        """The instrument's title, by `/legislation/lookup` ("" if unknown)."""
        if lid not in self.names:
            title = ""
            try:
                typ, y, n = lid.split("/")
                r = self.client.post(f"{LEX}/legislation/lookup",
                                     json={"legislation_type": typ, "year": int(y),
                                           "number": int(n)})
                if r.status_code == 200:
                    title = r.json().get("title") or ""
            except Exception:
                title = ""
            self.names[lid] = title
        return self.names[lid]

    def provisions_of(self, lid: str) -> Optional[list]:
        if lid not in self.provisions:
            try:
                r = self.client.post(f"{LEX}/legislation/section/lookup",
                                     json={"legislation_id": lid, "limit": 2000})
                self.provisions[lid] = r.json() if r.status_code == 200 else None
            except Exception:
                self.provisions[lid] = None
        return self.provisions[lid]

    def resolve_title(self, title: str, year: str) -> Optional[str]:
        key = (_norm_title(title), year)
        if key not in self.titles:
            lid = None
            try:
                r = self.client.post(f"{LEX}/legislation/search",
                                     json={"query": f"{title} {year}", "limit": 10,
                                           "include_text": False})
                for x in (r.json().get("results") or []):
                    t = _norm_title(f"{x.get('title', '')}")
                    if t in (f"{key[0]} {year}", key[0]) and str(x.get("year")) == year:
                        lid = str(x.get("id") or "").split("/id/")[-1] or None
                        break
            except Exception:
                lid = None
            self.titles[key] = lid
        return self.titles[key]


def instrument_mentions(text: str, lex: Optional[Lex]) -> list:
    """(start, legislation_id) for every instrument `text` names: an EU
    measure by number, a typed UK citation (P3.7's extractor), a title with a
    year resolved by exact title match, or a legislation.gov.uk URL."""
    from src.utils.instrument_lookup import extract_instrument_citations  # noqa: PLC0415

    text = text or ""
    out = []
    for m in _EU_RX.finditer(text):
        out.append((m.start(), f"{_EU_TYPE[m.group(1).lower()]}/{m.group(3)}/{m.group(2)}"))
    for m in _BARE_EU_RX.finditer(text):
        n, y = int(m.group(1)), int(m.group(2))
        if 1950 <= y <= 2030 and not (1950 <= n <= 2030):
            out.append((m.start(), f"eur/{y}/{n}"))
    for typ, y, n in extract_instrument_citations(text, limit=20):
        i = text.find(str(n))
        out.append((max(i, 0), f"{typ}/{y}/{n}"))
    for m in _URL_RX.finditer(text):
        out.append((m.start(), f"{m.group(1).lower()}/{m.group(2)}/{m.group(3)}"))
    if lex is not None:
        for m in _TITLE_RX.finditer(text):
            words = _LEAD_CONNECTORS.sub("", m.group(1)).split()
            for i in range(len(words)):
                if not (words[i][:1].isupper() or words[i].startswith("(")):
                    continue
                lid = lex.resolve_title(" ".join(words[i:]), m.group(2))
                if lid:
                    out.append((m.start(), lid))
                    break
    return sorted(set(out))


# --- fetching and slicing -----------------------------------------------------

_KIND_PATH = {"article": ("article", "section"), "section": ("section",),
              "regulation": ("regulation", "article"), "schedule": ("schedule",),
              "annex": ("annex",)}


def find_provision(items: list, ref: Ref) -> Optional[dict]:
    for seg in _KIND_PATH[ref.kind]:
        want = f"/{seg}/{ref.num}".lower()
        for it in items or []:
            if str(it.get("uri", "")).lower().endswith(want):
                return it
    return None


def _cut_numbered(text: str, sub: str) -> Optional[str]:
    """The paragraph `(4)` of an article or section: from its marker to the
    next marker at the same level. LEX renders it '4) ' or '(4) ' at a line
    start."""
    first = re.match(r"\((\w+)\)", sub or "")
    if not first:
        return None
    tok = first.group(1)
    m = re.search(rf"(?m)^[ \t]*\(?{re.escape(tok)}\)\s", text)
    if not m:
        return None
    rest = text[m.end():]
    if tok.isdigit():
        nxt = re.search(rf"(?m)^[ \t]*\(?{int(tok) + 1}\)\s", rest)
    else:
        nxt = re.search(r"(?m)^[ \t]*\(?[a-z]{1,3}\)\s", rest)
    return text[m.start(): m.end() + (nxt.start() if nxt else len(rest))]


def _cut_annex(text: str, ref: Ref) -> tuple:
    """(slice, how). Chapter headings survive in LEX's Annex text only
    sometimes (`CHAPTER V RULES FOR ...` in Annex XIV; none in Annex X), so a
    chapter is cut only on an upper-case heading; a section only where its
    heading ('Section 3Specific ...') occurs once in the chapter span."""
    span, how = text, "whole annex"
    if ref.chapter:
        m = re.search(rf"\bCHAPTER\s+{ref.chapter}\b", text)
        if m:
            nxt = re.search(r"\bCHAPTER\s+[IVXL]+\b", text[m.end():])
            span = text[m.start(): m.end() + (nxt.start() if nxt else len(text))]
            how = "chapter cut"
        else:
            how = "chapter heading absent"
    if ref.section:
        hits = list(re.finditer(rf"Section\s*{ref.section}(?=\s*[A-Z])", span))
        if len(hits) == 1:
            nxt = re.search(r"Section\s*\d+(?=\s*[A-Z])", span[hits[0].end():])
            span = span[hits[0].start(): hits[0].end() + (nxt.start() if nxt else len(span))]
            how = (how + ", section cut") if how == "chapter cut" else "section cut"
        else:
            how += f", section heading x{len(hits)}"
    return span, how


_OPEN_Q = "‘'\"“"
_CLOSE_Q = "’'\"”"


def cut_definitions(text: str, terms: list) -> Optional[str]:
    """The definitions of the quoted `terms` in a definitions provision
    ("'red fats' means ...;"), each to the next definition. None when
    the provision defines none of them."""
    parts = []
    for t in terms:
        stem = re.escape(t.rstrip("s"))
        m = re.search(rf"[{_OPEN_Q}]{stem}s?[{_CLOSE_Q}]\s+means\b", text, re.I)
        if not m:
            continue
        nxt = re.search(rf";\s*(?:and\s+)?[{_OPEN_Q}]|;\s*$", text[m.end():m.end() + 2000])
        parts.append(text[m.start(): m.end() + (nxt.start() + 1 if nxt else 1500)])
    return "\n".join(dict.fromkeys(parts)) or None


def slice_provision(item: dict, ref: Ref, terms: Optional[list] = None) -> tuple:
    text = item.get("text") or ""
    if terms and re.search(r"\bmeans\b", text[:4000]):
        cut = cut_definitions(text, terms)
        if cut:
            return cut, "definitions cut"
    if ref.kind == "annex":
        return _cut_annex(text, ref)
    if ref.sub:
        cut = _cut_numbered(text, ref.sub)
        if not cut:
            return text, "paragraph not found, whole provision"
        # Deeper levels ("(1)(i)") are not cut, only checked: a level the
        # provision does not have is a citation that does not exist, which is
        # exactly what the lawyer (or the model) needs to see.
        deeper = re.findall(r"\((\w+)\)", ref.sub)[1:]
        missing = [t for t in deeper
                   if not re.search(rf"(?m)^[ \t\-]*\(?{re.escape(t)}\)\s", cut)]
        if missing:
            return cut, "paragraph cut, (" + ")(".join(missing) + ") not present"
        return cut, "paragraph cut"
    return text, "whole provision"


# --- concordance --------------------------------------------------------------

_QUOTED = re.compile(r"[“\"‘]([^”\"’\n]{3,60})[”\"’]")


def _term_key(t: str) -> str:
    return " ".join(w.rstrip("s") for w in t.lower().split())


def quoted_terms(text: str) -> list:
    """Short quoted phrases (at most five words) that look like terms, one
    per singular/plural form."""
    out, keys = [], set()
    for m in _QUOTED.finditer(text or ""):
        t = m.group(1).strip().strip(".,;:")
        if 1 <= len(t.split()) <= 5 and _term_key(t) not in keys:
            keys.add(_term_key(t))
            out.append(t)
    return out[:4]


def _term_rx(term: str):
    words = [re.escape(w.rstrip("s")) + r"s?" for w in term.split()]
    return re.compile(r"\b" + r"\s+".join(words) + r"\b", re.I)


def concordance(items: list, terms: list, window: int = 150) -> list:
    """Every place in `items` where two different quoted terms occur within
    `window` characters of each other: (uri, excerpt), overlapping windows
    in one provision merged."""
    out = []
    if len(terms) < 2:
        return out
    # Only terms the instrument DEFINES: a quoted ordinary word ("apply")
    # matches everywhere. And never a term with one it contains
    # ("plan" / "XY plan" match the same words).
    defined = [t for t in terms if any(
        re.search(rf"[{_OPEN_Q}]{re.escape(t.rstrip('s'))}s?[{_CLOSE_Q}]\s+means\b",
                  it.get("text") or "", re.I) for it in items or [])]
    pairs = [(_term_rx(a), _term_rx(b)) for i, a in enumerate(defined) for b in defined[i + 1:]
             if _term_key(a) not in _term_key(b) and _term_key(b) not in _term_key(a)]
    for it in items or []:
        text = it.get("text") or ""
        spans = []
        for a, b in pairs:
            if True:
                for m in a.finditer(text):
                    lo, hi = max(0, m.start() - window), min(len(text), m.end() + window)
                    if b.search(text, lo, hi):
                        spans.append((lo, hi))
        spans.sort()
        merged: list = []
        for lo, hi in spans:
            if merged and lo <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], hi)
            else:
                merged.append([lo, hi])
        out.extend((it.get("uri", ""), text[lo:hi]) for lo, hi in merged)
    return out


_NICK = re.compile(r"^[^.;\n]{0,60}?\b(\w{4,})\s+Regulations?\b", re.I)
_NICK_SKIP = {"assimilated", "these", "those", "this", "same", "retained", "domestic",
              "scottish", "such", "above", "relevant"}


def nickname_pick(text: str, ref: Ref, holders: list, lex: "Lex") -> Optional[tuple]:
    """Break a tie between instruments that all hold the provision by the word
    the lawyer used for the instrument right after the reference ("Article
    25(4) of the Implementing Regulation"): the one holder whose title
    contains that word's stem, or None."""
    m = _NICK.search(text[ref.start: ref.start + 140])
    if not m or m.group(1).lower() in _NICK_SKIP:
        return None
    stem = m.group(1).lower()[:7]
    hit = [h for h in holders if stem in lex.title_of(h[0]).lower()]
    return hit[0] if len(hit) == 1 else None


# --- the dry run --------------------------------------------------------------


@dataclass
class TurnResult:
    session: str
    msg: int
    refs: list = field(default_factory=list)     # (label, outcome, lid|None, how, chars)
    terms: list = field(default_factory=list)
    conc_hits: int = 0
    conc_chars: int = 0
    shown: list = field(default_factory=list)    # (label, lid, text) for --show


_QUOTE_SPAN = re.compile(r"[“\"][^”\"]{0,400}[”\"]")


def _unquoted(mentions: list, text: str) -> list:
    """Mentions outside quotation marks: an instrument named INSIDE a quoted
    passage is what the provision says, not the instrument it belongs to
    (6370: reg 3(2)(a) of one set of Regulations, quoting another)."""
    spans = [(m.start(), m.end()) for m in _QUOTE_SPAN.finditer(text)]
    return [(p, lid) for p, lid in mentions if not any(a <= p < b for a, b in spans)]


def linked_instrument(text: str, ref: Ref, mentions: list) -> Optional[str]:
    """The instrument a reference is tied to by "of (the)" right after it
    ("section 4 of the ... Act 2013"), else None."""
    for pos, lid in mentions:
        if ref.end <= pos <= ref.end + 60 and re.fullmatch(
                r"\s*,?\s*of\s+(?:the\s+)?(?:assimilated\s+|retained\s+)?",
                text[ref.end:pos], re.I):
            return lid
    return None


def dry_run_turn(session: str, msg: int, text: str, context: list, lex: Lex) -> TurnResult:
    tr = TurnResult(session, msg)
    mentions = instrument_mentions(text, lex)
    tr.terms = quoted_terms(text)
    outside = _unquoted(mentions, text)
    named = list(dict.fromkeys(lid for _, lid in outside))
    for ref in extract_provision_refs(text):
        link = linked_instrument(text, ref, outside)
        near = [link] if link else (named if len(named) == 1 else [])
        how_near = "linked" if link else "only one named"
        cands = list(near) or list(context)
        holders = []
        for lid in cands:
            items = lex.provisions_of(lid)
            it = find_provision(items, ref) if items else None
            if it is not None:
                holders.append((lid, it))
        if not cands:
            tr.refs.append((ref.label(), "no instrument in play", None, "", 0))
            continue
        if not holders:
            tr.refs.append((ref.label(), "not found in " + ",".join(cands[:3]), None, "", 0))
            continue
        outcome = how_near if near else "context"
        if len(holders) > 1:
            pick = nickname_pick(text, ref, holders, lex)
            if pick is None:
                tr.refs.append((ref.label(), "ambiguous: " + ",".join(h[0] for h in holders),
                                None, "", 0))
                continue
            holders, outcome = [pick], "nickname"
        lid, it = holders[0]
        text_cut, how = slice_provision(it, ref, tr.terms)
        tr.refs.append((ref.label(), outcome, lid, how, len(text_cut)))
        tr.shown.append((ref.label(), lid, text_cut))
    if len(tr.terms) >= 2:
        pool = list(dict.fromkeys([lid for _, lid in mentions] + context))
        for lid in pool:
            hits = concordance(lex.provisions_of(lid) or [], tr.terms)
            tr.conc_hits += len(hits)
            tr.conc_chars += sum(len(x) for _, x in hits)
            tr.shown.extend((f"concordance {lid}", u.split("/id/")[-1], x) for u, x in hits)
    return tr


HINT_TOTAL_CAP = 16_000


def hint_block(question: str, context: list, lex: "Lex") -> tuple:
    """The block a product would prefix onto the lawyer's turn: the text of
    every provision the message names that resolves to ONE instrument, then
    the concordance of two quoted terms the instrument defines. ("" , meta)
    when there is nothing to hand over. Prototype for the seam only
    (`seam_replay manager --hint`); nothing in the product calls it."""
    tr = dry_run_turn("-", 0, question, list(context), lex)
    parts, used = [], 0
    for label, lid, text in tr.shown:
        if label.startswith("concordance"):
            continue
        title = lex.title_of(lid) or lid
        if len(text) > PER_REF_CAP:
            # The first N characters of a long Annex are some other chapter:
            # say what is held rather than hand over the wrong text.
            chunk = (f"{label} of {title} ({lid}): held, but the part named could not be "
                     f"cut out of the text held ({len(text):,} characters), so it is not "
                     "reproduced here; retrieve it before relying on it.")
        else:
            chunk = f"{label} of {title} ({lid}):\n{text.strip()}"
        if used + len(chunk) > HINT_TOTAL_CAP:
            break
        parts.append(chunk)
        used += len(chunk)
    conc = [(lid, text) for label, lid, text in tr.shown if label.startswith("concordance")]
    if conc and used < HINT_TOTAL_CAP:
        lines = []
        for uri, text in conc:
            excerpt = re.sub(r"\s+", " ", text).strip()
            line = f"- http://www.legislation.gov.uk/{uri}: ...{excerpt}..."
            if used + len(line) > HINT_TOTAL_CAP:
                break
            lines.append(line)
            used += len(line)
        if lines:
            terms = " and ".join(f"'{t}'" for t in tr.terms)
            parts.append(f"Every passage where the instrument uses both {terms} together:\n"
                         + "\n".join(lines))
    meta = {"refs": tr.refs, "terms": tr.terms, "concordance_hits": tr.conc_hits,
            "chars": used}
    if not parts:
        return "", meta
    block = ("[PROVISIONS NAMED IN THE USER'S MESSAGE — the text below was retrieved "
             "from the legislation index by code for this turn, verbatim, and has not "
             "been summarised]\n\n" + "\n\n".join(parts)
             + "\n[END OF PROVISIONS NAMED IN THE USER'S MESSAGE]")
    return block, meta


def context_from_history(messages: list) -> list:
    """Instrument ids the conversation already carries: every one an earlier
    message names or links, in order of first appearance."""
    out: list = []
    for m in messages:
        for _, lid in instrument_mentions(m.get("content") or "", None):
            if lid not in out:
                out.append(lid)
    return out


def export_sessions(only=None) -> dict:
    import replay_set  # noqa: PLC0415

    grouped: dict = {}
    for r in csv.DictReader(io.open(Path(replay_set.DEFAULT_CSV), encoding="utf-8-sig")):
        if only and r["Session ID"] not in only:
            continue
        grouped.setdefault(r["Session ID"], []).append(r)
    for rows in grouped.values():
        rows.sort(key=lambda r: int(r["Message #"] or 0))
    return grouped


def cmd_dryrun(args) -> int:
    sys.path.insert(0, str(TOOLS))
    lex = Lex()
    grouped = export_sessions(set(args.session) if args.session else None)
    results = []
    user_turns = 0
    for sid, rows in sorted(grouped.items()):
        context: list = []
        prev_user = None
        for r in rows:
            content = r["Message content"] or ""
            if r["Message role"] == "user":
                if content.strip() == (prev_user or "").strip():
                    continue  # a resubmitted identical message is one turn
                prev_user = content
                user_turns += 1
                results.append(dry_run_turn(sid, int(r["Message #"]), content, context, lex))
                for _, lid in instrument_mentions(content, lex):
                    if lid not in context:
                        context.append(lid)
            elif r["Message role"] == "assistant":
                for _, lid in instrument_mentions(content, None):
                    if lid not in context:
                        context.append(lid)

    with_ref = [t for t in results if t.refs]
    refs = [x for t in results for x in t.refs]
    out = Counter()
    for label, outcome, lid, how, n in refs:
        out[outcome.split(":")[0].split(" in ")[0]] += 1
    hows = Counter(how for _, _, lid, how, _ in refs if lid)
    sizes = [n for _, _, lid, _, n in refs if lid]
    kinds = Counter(label.split()[0] for label, *_ in refs)
    conc = [t for t in results if t.conc_hits]

    print("P3.2 retrieval-hint dry run over the transcript export")
    print(f"  sessions {len(grouped)}, user turns {user_turns} (identical resubmissions merged)")
    print(f"  turns naming at least one provision: {len(with_ref)} "
          f"in {len({t.session for t in with_ref})} session(s)")
    print(f"  provision references: {len(refs)}  by kind: "
          + ", ".join(f"{k} {v}" for k, v in kinds.most_common()))
    print("  resolution: " + ", ".join(f"{k} {v}" for k, v in out.most_common()))
    if sizes:
        q = sorted(sizes)
        print(f"  resolved: {len(sizes)}; cut: " + ", ".join(f"{k} {v}" for k, v in hows.most_common()))
        print(f"  characters handed over per resolved reference: median "
              f"{int(statistics.median(q)):,}, p90 {q[int(0.9 * (len(q) - 1))]:,}, max {q[-1]:,}; "
              f"over the {PER_REF_CAP:,} cap: {sum(1 for n in q if n > PER_REF_CAP)}")
    print(f"  turns with two or more quoted terms: {sum(1 for t in results if len(t.terms) >= 2)}; "
          f"with concordance hits: {len(conc)} "
          f"({sum(t.conc_hits for t in conc)} hits, {sum(t.conc_chars for t in conc):,} chars)")

    if args.list:
        print("\n  per turn (echoes lawyer text: scratchpad only):")
        for t in results:
            if not (t.refs or t.conc_hits):
                continue
            print(f"    {t.session} msg {t.msg}")
            for label, outcome, lid, how, n in t.refs:
                print(f"        {label:<22} {outcome:<40} {lid or '':<16} {how} {n:,}")
            if t.conc_hits:
                print(f"        concordance {t.terms}: {t.conc_hits} hits, {t.conc_chars:,} chars")
    if args.show:
        print("\n  text that would be handed over (scratchpad only):")
        for t in results:
            for label, lid, text in t.shown:
                print(f"\n    ---- {t.session} msg {t.msg} {label} [{lid}]")
                print("    " + re.sub(r"\s+", " ", text)[: args.chars])
    return 0


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    p = argparse.ArgumentParser(prog="provision_hints")
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dryrun", help="what the retrieval hint would fetch, per user turn")
    d.add_argument("--session", nargs="+", default=None)
    d.add_argument("--list", action="store_true")
    d.add_argument("--show", action="store_true")
    d.add_argument("--chars", type=int, default=1500)
    args = p.parse_args(argv)
    return {"dryrun": cmd_dryrun}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
