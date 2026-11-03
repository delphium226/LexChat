"""The court's own limit on its decision, carried to every agent that states
the holding (FIX_PLAN P3.50, fix A1, Session 52).

**The defect.** Q12 (6347, case law only, Deep Research) asks for a summary of
Rex v Evans [2025] EWCA Crim 1150. The judgment is whole in the Worker's
context at every step, and at [43] the court confines its decision to "the
admitted duties and responsibilities of the appellant on the night in
question", adding that other officers "with different roles at different
times" might be decided differently. [43] reached 0 of 18 step reports and 0
of 6 answers; the answers state the holding as a class rule ("an OSG is a
public officer"), the opposite of [43]. The Deep Research synthesis never
reads the judgment.

**The lever: code finds the passage and hands it on, verbatim.** Three
outlets, one detector (`find_limits`):

1. `court_limit_note`: a `[COURT'S OWN LIMIT]` block on the
   `get_case_law_text` result the Worker reads (after summarisation, from the
   raw text, so a summary cannot drop it);
2. `court_limits_block`: the same passages handed to the Deep Research
   synthesis, beside P3.1's pinpoint block, for a judgment a step report names;
3. `restore_court_limits`: at the answer seam, where an answer names the
   judgment and does not carry the limit, "Also in <case>, at [N], the court
   limited its own decision: "..."" goes after the paragraph that first names
   it (P3.13's and P3.12's pattern; at most `MAX_RESTORES`): a confinement
   (kind 0) only, quoting the matched sentence and, where it fits, the next
   (`restore_excerpt`, at most `MAX_RESTORE_CHARS`).

**Precision over recall.** A passage counts only when the court speaks of its
own decision in the first person or as "this judgment" ("our focus was
necessarily on ...", "nothing in this judgment is intended to ...", "we express
no view as to whether ...", "confined to the facts of this case"). Passages in
quotation marks or attributed to another judge are skipped, and so is a
cited case's "turned on its own facts". Pure, fail-soft, and nothing changes
where no passage is found.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Iterable, Optional

logger = logging.getLogger("agent")

__all__ = [
    "find_limits", "court_limits_from_result", "court_limit_note", "limits_in_text",
    "court_limits_block", "restore_court_limits", "restore_excerpt", "COURT_LIMIT_HEAD", "MAX_RESTORES",
]

CASE_LAW_TEXT_TOOL = "get_case_law_text"
COURT_LIMIT_HEAD = "COURT'S OWN LIMIT"
MAX_PASSAGES = 2          # per judgment
MAX_PASSAGE_CHARS = 700   # a passage over this is cut at a sentence end
MAX_RESTORES = 2          # per answer
MAX_BLOCK_JUDGMENTS = 6   # per synthesis block
# Only a confinement (0) goes back into an answer (user decision, Session 52):
# "not to be taken as deciding" (1) and a question left undecided (2) are the
# Worker's and the synthesis's to weigh, and out of context they read as a
# limit on the holding they are not.
RESTORED_KINDS = (0,)
# The answer note quotes the matched sentence, and the next one where it fits,
# within this (P3.12's excerpt bound); the Worker's and the synthesis's blocks
# keep the whole passage, up to MAX_PASSAGE_CHARS.
MAX_RESTORE_CHARS = 450

_WS = re.compile(r"\s+")

# The court speaking of its own decision. Each pattern is anchored on a
# first-person or "this judgment" subject; the generic "each case turns on its
# own facts" is deliberately absent (in the stored judgments it was said of a
# cited case or of a discretion, never of the decision itself).
_VERB = r"(?:is|was|should|must|will|can|may|are)\b[^.;:]{0,25}?\b(?:intended|taken|read|treated|understood|meant|regarded|construed|seen)"
_JUDGMENT = r"(?:judgment|judgement|decision|ruling|analysis|reasoning)"
# (rank, pattern): rank 0 confines the decision itself, rank 1 says what the
# judgment must not be taken to say, rank 2 leaves a question undecided. The
# best-ranked passages are kept (`MAX_PASSAGES`), so a minor point left open
# never displaces the court's own limit on its holding.
_LIMIT_PATTERNS = [
    # Evans [43]: "our focus was necessarily on the admitted duties ..."
    (0, re.compile(r"\bour (?:focus|decision|conclusion|judgment|ruling|determination|reasoning)s?"
                   r" (?:in this (?:case|appeal) )?(?:was|is|has been) (?:necessarily |therefore |"
                   r"accordingly |only |solely )?(?:on|confined to|limited to|restricted to|"
                   r"directed to|based on)\b", re.I)),
    (0, re.compile(r"\b(?:this|our|the present) (?:decision|judgment|ruling|conclusion)"
                   r" (?:is|was) (?:necessarily )?(?:confined|limited|restricted) to\b", re.I)),
    (0, re.compile(r"\b(?:confined|limited|restricted) to the (?:particular |specific |unusual |"
                   r"special |very )?(?:facts|circumstances) of (?:this|the present) (?:case|appeal|"
                   r"claim|application)\b", re.I)),
    (0, re.compile(r"\b(?:this|our) (?:decision|judgment) (?:is not|should not be (?:taken|read|"
                   r"treated) as|does not) (?:lay(?:ing)? down|establish(?:ing)?|an? authority for|"
                   r"authority for) (?:a|any) (?:general|wider|broader|universal)\b", re.I)),
    (1, re.compile(r"\bnothing (?:in|that is in) (?:this|our|my) " + _JUDGMENT + r"\b"
                   r"[^.;:]{0,30}?\b" + _VERB, re.I)),
    (1, re.compile(r"\bnothing (?:that )?(?:we|I) (?:have|has) (?:said|decided|held)\b"
                   r"(?:[^.;:]{0,30}?\b(?:in this judgment|here|above))?[^.;:]{0,30}?\b" + _VERB,
                   re.I)),
    (2, re.compile(r"\b(?:we|I) (?:would )?(?:prefer to )?(?:express|expressed) no (?:concluded |"
                   r"final |further )?(?:views?|opinion)(?:,? one way or the other,?)? (?:as to|on|"
                   r"about|upon)\b(?! (?:that|this|the) (?:matter|point|issue|question)\b)", re.I)),
    (2, re.compile(r"\b(?:we|I) (?:do|did|need) not (?:need to )?decide(?: in this (?:case|appeal))?"
                   r" whether\b", re.I)),
]

# Paragraph numbers as Find Case Law's text gives them: "\n43.\n" (most),
# "\n[43] " and "\n43. Text".
# A bracketed number of four digits is a law report's year ("[2000] QB 1"),
# never a paragraph.
_PARA_MARK = re.compile(r"(?:^|\n)[ \t]*(?:\[(\d{1,3})\][ \t]+|(\d{1,4})\.[ \t]*\n|(\d{1,4})\.[ \t]+(?=[A-Z\"“(]))")
# The end of the last whole sentence: a heading the text runs on into
# ("... in this decision. Costs") is left out.
_LAST_SENTENCE_END = re.compile(r"^.*[.!?][\"'”’)]*", re.S)
# Another judge's words: "As X LJ said ...", "observed:", "held that" before
# the match in the same sentence.
_ATTRIBUTED = re.compile(
    r"\b(?:said|observed|stated|held|concluded|remarked|explained|put it|noted)\b[^.]{0,6}[:,]?\s*$"
    r"|\b(?:as|per)\s+(?:[A-Z][\w'’-]+\s+){1,3}(?:LJ|J|MR|LCJ|P|JSC|SCJ|Lord\s+\w+|Lady\s+\w+)\b",
    re.I)
# "while our focus has been on X, the same applies to Y" widens the decision.
_CONCESSIVE = re.compile(r"\b(?:while|whilst|although|though)\s*$", re.I)
_SENT_END = re.compile(r"(?<=[.!?])[\"'”’)]*\s+(?=[A-Z\"“(])")


def _norm(text: str) -> str:
    return _WS.sub(" ", text or "").strip()


def _paragraphs(text: str) -> list:
    """[(number or "", start, end)] covering the text, in order."""
    marks = [(m.group(1) or m.group(2) or m.group(3), m.start(), m.end())
             for m in _PARA_MARK.finditer(text)]
    out = []
    for i, (num, _s, e) in enumerate(marks):
        end = marks[i + 1][1] if i + 1 < len(marks) else len(text)
        out.append((num, e, end))
    return out


def _quoted(para: str, rel: int) -> bool:
    """The position `rel` sits inside quotation marks: opened earlier in this
    paragraph, or opened before it (the paragraph closes more quotations than
    it opens: a quoted speech running on from the paragraph above)."""
    before = para[:rel]
    if before.count("“") > before.count("”"):
        return True
    if para.count("”") > para.count("“"):
        return True
    return before.count('"') % 2 == 1


def _sentences(para: str) -> list:
    """[(start, end)] of the paragraph's sentences."""
    bounds = [0] + [m.end() for m in _SENT_END.finditer(para)] + [len(para)]
    return [(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1) if bounds[i] < bounds[i + 1]]


def _passage(para: str, rel: int) -> str:
    """The paragraph whole when short; else the matched sentence and the one
    after it, cut at a sentence end under MAX_PASSAGE_CHARS."""
    whole = _norm(para)
    if len(whole) <= MAX_PASSAGE_CHARS:
        m = _LAST_SENTENCE_END.match(whole)
        return m.group(0) if m and m.end() > rel else whole
    sents = _sentences(para)
    idx = next((i for i, (a, b) in enumerate(sents) if a <= rel < b), 0)
    text = ""
    for a, b in sents[idx:idx + 2]:
        piece = _norm(para[a:b])
        if text and not re.search(r"[.!?][\"'”’)]*$", piece):
            break  # the next sentence runs on past a line break: leave it out
        nxt = (text + " " + piece) if text else piece
        if text and len(nxt) > MAX_PASSAGE_CHARS:
            break
        text = nxt
    if len(text) > MAX_PASSAGE_CHARS:
        cut = text[:MAX_PASSAGE_CHARS].rsplit(" ", 1)[0]
        text = cut.rstrip(",;:") + " ..."
    return text


def find_limits(text: str, max_passages: int = MAX_PASSAGES) -> list:
    """[{"para": "43" | "", "kind": 0 | 1 | 2, "passage": str}] the passages
    in which the court limits its own decision: at most one a paragraph, the
    `max_passages` best ranked (`_LIMIT_PATTERNS`; `kind` is the rank),
    earliest first within a rank, returned in the judgment's order. Pure; []
    on anything unexpected."""
    try:
        if not text:
            return []
        paras = _paragraphs(text) or [("", 0, len(text))]
        found = []   # (rank, start, para number, passage)
        for num, s, e in paras:
            para = text[s:e]
            best = None
            for rank, rx in _LIMIT_PATTERNS:
                if best is not None and rank >= best[0]:
                    continue
                for m in rx.finditer(para):
                    if _quoted(para, m.start()):
                        continue
                    sent_start = max((a for a, _b in _sentences(para) if a <= m.start()),
                                     default=0)
                    if _ATTRIBUTED.search(para[sent_start:m.start()]):
                        continue
                    if _CONCESSIVE.search(para[max(sent_start, m.start() - 12):m.start()]):
                        continue
                    best = (rank, s, num or "", _passage(para, m.start()))
                    break
            if best is not None:
                found.append(best)
        kept = sorted(found, key=lambda f: (f[0], f[1]))[:max_passages]
        return [{"para": f[2], "kind": f[0], "passage": f[3]}
                for f in sorted(kept, key=lambda f: f[1])]
    except Exception:  # pragma: no cover - defensive
        logger.debug("[CourtLimit] detection skipped", exc_info=True)
        return []


def court_limits_from_result(raw_result) -> list:
    """[{"url", "title", "ncn", "para", "kind", "passage"}] for one
    `get_case_law_text` result (Find Case Law's or SCTS's shape). [] for an
    error, an empty text, or no passage. Never raises."""
    try:
        d = json.loads(raw_result) if isinstance(raw_result, str) else raw_result
        if not isinstance(d, dict) or d.get("error") or not d.get("text"):
            return []
        meta = {"url": str(d.get("url") or ""), "title": _norm(str(d.get("title") or "")),
                "ncn": _norm(str(d.get("ncn") or d.get("citation") or ""))}
        return [{**meta, **lim} for lim in find_limits(str(d["text"]))]
    except Exception:
        return []


# What each kind of passage is, as the Worker's block and the synthesis's
# block label it (and as `limits_in_text` reads it back).
KIND_LABELS = {
    0: "the court confines its decision",
    1: "what the court says its judgment is not to be taken as deciding",
    2: "a question the court leaves undecided",
}
_KIND_BY_LABEL = {v: k for k, v in KIND_LABELS.items()}


def _judgment_label(lim: dict) -> str:
    parts = [p for p in (lim.get("title"), lim.get("ncn")) if p]
    return ", ".join(parts) or "this judgment"


def _para_ref(para: str) -> str:
    return f"paragraph {para}" if para else "a passage without a paragraph number"


def _passage_line(lim: dict) -> str:
    label = KIND_LABELS.get(lim.get("kind"), KIND_LABELS[2])
    return f"{_para_ref(lim.get('para') or '').capitalize()} ({label}): \"{lim['passage']}\""


def court_limit_note(name: str, raw_result) -> str:
    """The Worker's block for a `get_case_law_text` result, or "". Self-gated
    on the tool name; never raises."""
    if name != CASE_LAW_TEXT_TOOL:
        return ""
    try:
        lims = court_limits_from_result(raw_result)
        if not lims:
            return ""
        first = lims[0]
        lines = [f"Judgment: {_judgment_label(first)}"]
        if first.get("url"):
            lines.append(f"Link: {first['url']}")
        lines += [_passage_line(lim) for lim in lims]
        paras = " and ".join(f"paragraph {lim['para']}" for lim in lims if lim["para"])
        cite = f"cite {paras} and " if paras else ""
        return (
            f"\n\n[{COURT_LIMIT_HEAD} — passages in which the court limits its own decision, "
            "found by code in the text of this judgment]\n" + "\n".join(lines) + "\n"
            "State this judgment's holding within these limits: say what the court decided on "
            "the facts before it, and do not state the holding as a rule for every case. When "
            f"you state the holding, {cite}give the limit in the court's own words.\n"
            f"[/{COURT_LIMIT_HEAD}]"
        )
    except Exception:
        return ""


_NOTE_BLOCK = re.compile(
    r"\[" + re.escape(COURT_LIMIT_HEAD) + r" — [^\]\n]*\]\n(?P<body>[\s\S]*?)\n\[/"
    + re.escape(COURT_LIMIT_HEAD) + r"\]")
_PASSAGE_LINE = re.compile(
    r"^(?:Paragraph (?P<para>\d{1,4})|A passage without a paragraph number)"
    r" \((?P<kind>[^()]+)\): \"(?P<passage>.*)\"$")


def limits_in_text(text: str) -> list:
    """The limits a tool result's `[COURT'S OWN LIMIT]` blocks carry, parsed
    back (a memo hit carries the block too), as `court_limits_from_result`
    returns them. [] where there is none. Never raises."""
    out = []
    try:
        for m in _NOTE_BLOCK.finditer(text or ""):
            lines = m.group("body").split("\n")
            if not lines or not lines[0].startswith("Judgment: "):
                continue
            label = lines[0][len("Judgment: "):]
            title, ncn = (label.rsplit(", [", 1) if ", [" in label else (label, None))
            ncn = f"[{ncn}" if ncn is not None else ""
            url = ""
            for line in lines[1:]:
                if line.startswith("Link: "):
                    url = line[len("Link: "):].strip()
                    continue
                p = _PASSAGE_LINE.match(line)
                if p and p.group("kind") in _KIND_BY_LABEL:
                    out.append({"url": url, "title": title, "ncn": ncn,
                                "para": p.group("para") or "",
                                "kind": _KIND_BY_LABEL[p.group("kind")],
                                "passage": p.group("passage")})
    except Exception:
        return []
    return out


def dedupe_limits(limits: Iterable[dict]) -> list:
    """Each (judgment, paragraph, passage) once, in first-seen order."""
    out, seen = [], set()
    for lim in limits or []:
        key = ((lim.get("url") or lim.get("ncn") or lim.get("title") or "").lower(),
               lim.get("para"), lim.get("passage"))
        if key in seen:
            continue
        seen.add(key)
        out.append(lim)
    return out


# ---------------------------------------------------------------------------
# naming a judgment
# ---------------------------------------------------------------------------

_PARTY_SKIP = {"the", "king", "queen", "rex", "regina", "r", "and", "another", "others", "ors",
               "anor", "ltd", "limited", "plc", "llp", "of", "for", "secretary", "state",
               "home", "department", "council", "city", "borough", "county", "district",
               "ministers", "scottish", "commissioners", "revenue", "customs", "hm", "his",
               "her", "majesty", "majesty's", "attorney", "general", "lord", "advocate",
               "crown", "prosecution", "service", "director", "public", "prosecutions", "v",
               "vs", "on", "application", "appellant", "respondent", "petitioner", "in", "re",
               "matter", "applicant", "claimant", "defendant"}


def _party_words(title: str) -> list:
    """The distinctive words of a case title's parties ("Graham Andrew Evans v
    R" -> ["evans"]: the last distinctive word of each side)."""
    sides = re.split(r"\s+v\.?\s+", title or "", flags=re.I)
    words = []
    for side in sides[:2]:
        toks = [t for t in re.findall(r"[A-Za-z][A-Za-z'’-]+", side)
                if t.lower() not in _PARTY_SKIP and len(t) > 2]
        if toks:
            words.append(toks[-1].lower())
    return words


def _url_path(url: str) -> str:
    m = re.search(r"caselaw\.nationalarchives\.gov\.uk/(?:id/)?([a-z0-9/_-]+?)/?(?:$|[?#)])", url or "")
    return m.group(1) if m else ""


def _names_judgment(answer: str, lim: dict) -> Optional[int]:
    """Where the answer first names the judgment: its URL, its neutral
    citation, or "X v Y" with a distinctive party word; None if nowhere."""
    hits = []
    path = _url_path(lim.get("url") or "")
    if path:
        m = re.search(re.escape(path) + r"(?![\w/])", answer)
        if m:
            hits.append(m.start())
    ncn = _norm(lim.get("ncn") or "")
    if ncn:
        m = re.search(r"\s+".join(re.escape(p) for p in ncn.split(" ")), answer)
        if m:
            hits.append(m.start())
    for w in _party_words(lim.get("title") or ""):
        m = re.search(rf"\b(?:{re.escape(w)}\b[^\n]{{0,40}}?\bv\.?\s|\bv\.?\s+[^\n]{{0,40}}?\b{re.escape(w)}\b)",
                      answer, re.I)
        if m:
            hits.append(m.start())
    return min(hits) if hits else None


_CONTENT = re.compile(r"[a-z]{3,}")
_STOP = {"the", "and", "that", "this", "with", "which", "were", "was", "for", "our", "its", "their",
         "have", "has", "had", "not", "but", "from", "should", "would", "could", "may", "might",
         "been", "being", "any", "all", "such", "other", "case", "court", "judgment", "decision",
         "appeal", "nothing", "intended", "taken", "view", "express", "whether", "there", "these",
         "those", "into", "upon", "than", "then", "also", "only", "are", "will", "can", "must"}


def _carried(answer: str, lim: dict) -> bool:
    """The answer already gives the limit: it pinpoints the paragraph ("[43]",
    "para 43", "paragraph 43"), or holds two of the passage's three-word runs."""
    para = lim.get("para")
    if para and re.search(rf"(?:\[{para}\]|\bparas?\.?\s*{para}\b|\bparagraphs?\s+{para}\b)",
                          answer, re.I):
        return True
    words = [w for w in _CONTENT.findall((lim.get("passage") or "").lower())]
    low = " ".join(_CONTENT.findall(answer.lower()))
    runs = {" ".join(words[i:i + 3]) for i in range(len(words) - 2)
            if not set(words[i:i + 3]) <= _STOP}
    return sum(1 for r in runs if r in low) >= 2


# ---------------------------------------------------------------------------
# the Deep Research synthesis
# ---------------------------------------------------------------------------

def court_limits_block(limits: Iterable[dict], texts: Iterable[str]) -> str:
    """The synthesis's block: the court's own limits for each judgment a step
    report names, or "". Never raises."""
    try:
        body = "\n\n".join(t or "" for t in texts or [])
        rows, judgments = [], []
        for lim in dedupe_limits(limits):
            if _names_judgment(body, lim) is None:
                continue
            key = (lim.get("url") or lim.get("ncn") or "").lower()
            if key not in judgments:
                if len(judgments) >= MAX_BLOCK_JUDGMENTS:
                    continue
                judgments.append(key)
            where = f" ({lim['url']})" if lim.get("url") else ""
            rows.append(f"- {_judgment_label(lim)}{where}. {_passage_line(lim)}")
        if not rows:
            return ""
        return (
            f"\n\n[{COURT_LIMIT_HEAD}S — passages in which a judgment the steps read limits its "
            "own decision, quoted by code from the judgment's text]\n" + "\n".join(rows) + "\n"
            "Where your report states one of these judgments' holding, state it within the "
            "court's limit: say what the court decided on the facts before it, cite the "
            "paragraph, and give the limit in the court's own words. Do not state the holding as "
            "a rule for every case.\n"
            f"[/{COURT_LIMIT_HEAD}S]"
        )
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# the answer seam
# ---------------------------------------------------------------------------

def restore_excerpt(passage: str, limit: int = MAX_RESTORE_CHARS) -> str:
    """What the answer note quotes of a passage: the sentence the limit is in,
    and the sentence after it where both fit within `limit` (Evans [43]'s
    second sentence, "would yield a different result", is what completes the
    limit); a matched sentence over `limit` is cut at a word with " ...".
    Verbatim apart from whitespace. Never raises."""
    try:
        text = _norm(passage)
        rel = 0
        for _rank, rx in sorted(_LIMIT_PATTERNS, key=lambda p: p[0]):
            m = rx.search(text)
            if m:
                rel = m.start()
                break
        sents = _sentences(text)
        idx = next((i for i, (a, b) in enumerate(sents) if a <= rel < b), 0)
        a, b = sents[idx] if sents else (0, len(text))
        out = text[a:b].strip()
        if idx + 1 < len(sents):
            two = text[a:sents[idx + 1][1]].strip()
            if len(two) <= limit:
                out = two
        if len(out) > limit:
            out = out[:limit].rsplit(" ", 1)[0].rstrip(",;:") + " ..."
        return out
    except Exception:
        return _norm(passage)[:limit]


def restore_court_limits(answer: str, limits: Iterable[dict],
                         max_notes: int = MAX_RESTORES) -> tuple:
    """(answer, notes added). For each judgment the answer names whose limit
    it does not carry, "Also in <case>, at [N], the court limited its own
    decision: "..."" goes after the paragraph that first names it. Verbatim,
    one note a judgment, at most `max_notes`; byte-identical where nothing is
    added; idempotent; never raises."""
    if not answer:
        return answer, 0
    try:
        from .citation_links import _RESTORED_NOTE

        # A restored note (P3.13, P3.12, this one) is never read as the
        # answer naming a judgment, nor as carrying a limit.
        masked = _RESTORED_NOTE.sub(lambda m: " " * len(m.group(0)), answer)
        inserts, done = [], set()
        for lim in dedupe_limits(limits):
            if len(inserts) >= max_notes:
                break
            key = (lim.get("url") or lim.get("ncn") or lim.get("title") or "").lower()
            if (not key or key in done or not lim.get("passage")
                    or lim.get("kind") not in RESTORED_KINDS):
                continue
            at = _names_judgment(masked, lim)
            if at is None or _carried(answer, lim):
                continue
            done.add(key)
            brk = re.compile(r"\n[ \t]*\n").search(answer, at)
            pos = brk.start() if brk else len(answer.rstrip())
            name = " ".join(p for p in (lim.get("title"), lim.get("ncn")) if p) or "this judgment"
            at_para = f", at [{lim['para']}]" if lim.get("para") else ""
            inserts.append((pos, f"\n\nAlso in {name}{at_para}, the court limited its own "
                                 f"decision: \"{restore_excerpt(lim['passage'])}\""))
        if not inserts:
            return answer, 0
        for pos, text in sorted(inserts, key=lambda x: x[0], reverse=True):
            answer = answer[:pos] + text + answer[pos:]
        return answer, len(inserts)
    except Exception:  # pragma: no cover - defensive
        logger.debug("[CourtLimit] restore skipped", exc_info=True)
        return answer, 0
