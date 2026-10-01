"""P3.3 (B11): does the summariser add law that is not in the text it summarises?

**Why this exists (Session 32).** 6338's wrong interpretation Act did not come
from the Worker or the Manager: the summariser (the model that condenses a large
tool result, `summarise_prompt`) was handed the Worker's brief as its "research
question" and answered it from training, adding the Act to section-search
results that never mention it. The Worker then reported it as retrieved. The
source rule (`SUMMARY_SOURCE_RULE`) was built on these numbers.

Three commands, all over stored run files (`audit.delegations[].tools[]` carry
both `raw_result` and `final_result`):

    python -m tools.summary_probe count [--dir D ...]
        FREE. Summarised results whose summary matches a rubric session's
        `summary_adds` pattern while its raw text does not (a tool that
        retrieved one of the rubric's `self_ids` is excluded: its raw text has
        no title to match). By directory and session.

    python -m tools.summary_probe redraw --dir D --session S [--reps N]
        PAID (the summarisation model, about $0.01 a call). Re-summarises each
        slot `count` finds in D, with the product's prompt and with the same
        prompt minus the source rule, N draws a side; counts additions.

    python -m tools.summary_probe panel [--n 24] [--reps 2] [--seed 32]
        PAID. The no-loss check on OTHER sessions' results: provisions kept
        (numbers present in the raw text), characters, and "the text does not
        contain" statements, with and without the rule.

    python -m tools.summary_probe glosses [--dir D ...] [--session S ...] [--list] [--ids]
        FREE (P3.16). Interpretation the summariser wrote into a summary that
        its raw text does not carry: a clause or parenthetical led by a gloss
        marker (`GLOSS_MARKERS`: "by definition", "which means", "i.e.",
        "effectively", "thus", "implies" ...) whose words, in a window round
        the marker, are mostly not a run of the raw text (`gloss_support`
        below `GLOSS_SUPPORT_MIN`). Also counts a change record's id given a
        title of a different year (`--ids` lists them). By directory and
        session; `--list` prints every match for reading (it quotes summary
        text, so it goes to the console, never to a committed file).
        Counted only in summaries of legislation; case-law summaries are
        listed as CASE, not counted.

    Options added for P3.16 to `redraw` and `panel` (both still PAID):
        --rule source|gloss   the rule the "without rule" side drops (default source)
        --side both|with|without   draw one side only, to set against the other
                              side drawn the same day
        --dry-run             list the slots and an estimated cost; draw nothing
        --out D               save every draw as D/NN_<slot>__<side>__<k>.md for
                              reading (the gitignored evidence, never the repo)
    and to `redraw` only:
        --glosses [--max-raw N]   slots are the stored summaries `glosses` flags
                              (--dir and --session take lists), drawn per chunk
                              as the product does, not the rubric's additions
    Both now report glosses, provisions kept, characters and "does not
    contain" statements per side.

The patterns name a matter's law, so they live in the gitignored rubric
(`evidence/rubrics/p33.json`, key `summary_adds` per session); this code is
generic. Temperature 0 is not byte-deterministic: redraw a side on the same
day, and read the counts as a band, not a point.
"""

import argparse
import asyncio
import json
import os
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# The gitignored evidence; PREPILOT_EVIDENCE points a git worktree at the main
# checkout's copy (Session 32's parallel batch).
EVIDENCE = Path(os.environ.get("PREPILOT_EVIDENCE")
                or ROOT / "docs" / "prepilot-fixes" / "evidence")
REPLAY = EVIDENCE / "replay"
RUBRIC = EVIDENCE / "rubrics" / "p33.json"
sys.path.insert(0, str(ROOT / "server_py"))

PROVISION = re.compile(
    r"\b(?:section|s\.|ss\.|regulation|reg\.|article|art\.|schedule|sch\.|paragraph|para\.)"
    r"\s*(\d+[A-Z]*(?:\(\w+\))*)", re.I)
NEGATIVE = re.compile(
    r"does not (?:contain|include|provide|state|define)|not (?:provided|included) in (?:the|this) text",
    re.I)
PANEL_DIRS = ("wave4_p37c", "wave4_p47b", "wave3_p313c", "wave4_p32_pre", "wave4_p46",
              "wave2_p27", "wave3_p38", "wave4_p45")


# ---- P3.16: glosses --------------------------------------------------------
#
# Session 32's source rule stopped the summariser adding an Act but not adding
# its own reading of the text: `wave4_p33_post` p32_6406 r1 run-file turn 6
# carries a parenthetical gloss that the instruments do not contain, and the
# same turn's answer quoted it as the text's own words. A gloss is recognised by its
# connective, not by new vocabulary: every word of that one IS in its 271K raw
# text, and so is the phrase "by definition", elsewhere. What is not in the raw
# is the run of words round the marker, so support is judged locally: the share
# of the window's word trigrams that occur, in order, in the raw text.
#
# Not markers, deliberately (measured over every stored audit, Session 33):
# "in effect" is mostly temporal ("the rate in effect on the day"); "impliedly"
# is statutory ("expressly or impliedly"); "is treated as", "falls within" and
# "qualifies as" paraphrase deeming provisions; "e.g.", "such as", "explicitly",
# "typically", "generally" and "Note:" are commentary at a volume (hundreds to
# a thousand each) no one can read, and are not glosses of the text's meaning.
# A parenthetical with no marker is not counted either: 8,183 of them carry a
# word the raw lacks, overwhelmingly paraphrase ("the final version").
GLOSS_MARKERS = (
    "by definition", "which means", "this means", "that means", "meaning that",
    "i.e.", "that is,", "in other words", "by extension", "by implication",
    "implicitly", "implies", "implying", "effectively", "thus", "therefore",
    "hence", "it follows", "necessarily", "suggests", "suggesting",
)
GLOSS_SUPPORT_MIN = 0.5
# Counted only in summaries of legislation. In a judgment's summary the same
# connectives restate the COURT's reasoning (131 of 159 read matches, Session
# 33), which words cannot tell from a gloss; those are listed, not counted.
GLOSS_TOOLS = ("search_legislation_sections", "get_legislation_text", "get_legislation_changes")
# Three shapes that carry a marker and are not a gloss (Session 33: of 274
# legislation matches read by hand, these drop 29 of 31 notes, 23 of 37
# paraphrases and 1 of 206 real glosses):
# a note that the supplied text lacks something ("did not include X; therefore
# ..."), which is the negatives count's business; a statutory condition ("if
# information suggests"); and "effectively" as an adverb of manner ("used
# economically, efficiently and effectively").
# The note is recognised by what follows the marker (it is about the summary),
# not by a negative nearby: "does not contain X, suggesting these Regulations
# do not govern Y" is a gloss drawn from absence, and is counted.
_ABOUT_SUMMARY = re.compile(
    r"summar|\bthis (?:excerpt|response|material)\b|\bno provisions\b"
    r"|\b(?:does|did|do)\s+not\s+(?:explicitly\s+)?(?:contain|include|outline|confirm)"
    r"|\bnot\s+(?:included|reflected|represented|present|extracted)\b|\bnot possible to confirm"
    r"|\bavailable in the (?:provided |source )?(?:text|material)"
    r"|\bcannot\s+be\s+(?:confirmed|identified|determined|extracted)|\bcould not be\b", re.I)
# Batch 2 (agent A): the note can also say what the supplied text "does not
# provide" ("The provided text does not contain X; therefore, it does not
# provide Y"). Adding "provide" to the verbs above would drop a gloss from
# absence ("...; therefore, these Regulations do not provide for appeals"), so
# this shape is recognised by its two subjects instead: the supplied text
# before the marker, and "it" (or the text itself) right after it.
_NOTE_SUBJECT = re.compile(
    r"\b(?:provided|supplied|retrieved|source)\s+(?:text|material|results?|excerpts?|sections?)\b"
    r"|\btext\s+(?:provided|supplied)\b|\bthis\s+(?:text|excerpt)\b", re.I)
_NOTE_PRONOUN = re.compile(
    r"^\W*(?:it|the\s+(?:provided\s+|supplied\s+)?text|this\s+text)\s+(?:does|did)\s+not\b", re.I)
_STATUTORY_SUGGESTS = re.compile(r"\b(?:information|evidence)\s+$", re.I)
_MANNER_BEFORE = re.compile(r"(?:\b(?:and|as|be|been|or)\s+|[\"'“‘])$", re.I)
_MANNER_AFTER = re.compile(r"^\s*(?:[)\].,;:\"'”’(]|$)")
_GLOSS_RX = re.compile(
    r"(?<![A-Za-z])(" + "|".join(re.escape(m) for m in GLOSS_MARKERS) + r")(?![A-Za-z])", re.I)
# The code-appended blocks after a summary (P1.6 URLs, P3.11 outline, scope
# notes, nudges, the truncation marker): the summariser never wrote them.
_CODE_BLOCK = re.compile(
    r"\n\n\[(?:[A-Z]{2,}[ :\-]|This search returned|These Scottish|No (?:committee|plenary)"
    r"|Content truncated|NOTE\b)")
_SENT_END = re.compile(r"\n|(?<=[a-z0-9)\]\"'*])[.!?](?=\s+[A-Z*#])")
_WORD = re.compile(r"[a-z0-9]+")
_BEFORE, _AFTER = 6, 10
# An instrument title: legitimate when it expands an id the raw text carries
# (section results carry ids and URIs, not titles), so it is taken out of the
# window before support is judged when its year is an id year in the raw.
_TITLE = re.compile(
    r"(?:[A-Z][\w'&.,-]*\s+|\([A-Z][\w' ]*\)\s+|(?:of|and|the|for|etc\.?)\s+){0,14}?"
    r"(?:Act|Regulations|Order|Rules|Measure)\s+(\d{4})"
    r"|Regulation\s+\((?:EU|EC|EEC)\)\s+No\s+\d+/(\d{4})"
    r"|Directive\s+(\d{4})/\d+")
_ID = re.compile(r"\b[a-z]{2,8}/(\d{4})/(\d+)\b")


def summary_part(final: str) -> str:
    """The summariser's own text: `final_result` up to the first code-appended block."""
    m = _CODE_BLOCK.search(final)
    return final[:m.start()] if m else final


def _strings(o, out: list) -> None:
    if isinstance(o, str):
        out.append(o)
    elif isinstance(o, dict):
        for k, v in o.items():
            out.append(str(k))
            _strings(v, out)
    elif isinstance(o, list):
        for v in o:
            _strings(v, out)
    elif o is not None:
        out.append(str(o))


def raw_words(raw: str) -> str:
    """The raw result as one space-padded run of lowercase words (JSON decoded,
    so an escaped character does not split a word)."""
    try:
        parts: list = []
        _strings(json.loads(raw), parts)
        text = "\n".join(parts)
    except (ValueError, TypeError):
        text = raw
    return " " + " ".join(_WORD.findall(text.lower())) + " "


def gloss_support(words: list, rjoin: str) -> float:
    """Share of the window's word trigrams found, in order, in the raw text."""
    tri = [" ".join(words[k:k + 3]) for k in range(len(words) - 2)]
    if not tri:
        return 1.0
    return sum(1 for t in tri if f" {t} " in rjoin) / len(tri)


def _window(s: str, a: int, b: int) -> tuple:
    """The sentence round the marker at [a, b), narrowed to its parenthetical."""
    lo = 0
    # endpos past the marker, so a boundary's lookahead can see a marker that
    # opens its sentence ("... included. Therefore, ...").
    for m in _SENT_END.finditer(s, 0, b):
        if m.end() <= a:
            lo = m.end()
    m = _SENT_END.search(s, b)
    hi = m.start() if m else len(s)
    depth, i = 0, a - 1
    while i >= lo:
        if s[i] == ")":
            depth += 1
        elif s[i] == "(":
            if depth == 0:
                lo = i + 1
                depth, j = 0, b
                while j < hi:
                    if s[j] == "(":
                        depth += 1
                    elif s[j] == ")":
                        if depth == 0:
                            hi = j
                            break
                        depth -= 1
                    j += 1
                break
            depth -= 1
        i -= 1
    return lo, hi


def glosses_in(raw: str, final: str) -> list:
    """Every gloss in a summary: dicts of marker, support (0..1) and the window text."""
    summ = summary_part(final)
    rjoin = raw_words(raw)
    id_years = {y for y, _n in _ID.findall(raw)}
    out = []
    for m in _GLOSS_RX.finditer(summ):
        marker = m.group(1).lower()
        before, after = summ[max(0, m.start() - 40):m.start()], summ[m.end():m.end() + 3]
        if marker == "suggests" and _STATUTORY_SUGGESTS.search(before):
            continue
        if marker == "effectively" and (_MANNER_BEFORE.search(before) or _MANNER_AFTER.match(after)):
            continue
        lo, hi = _window(summ, m.start(), m.end())
        if _ABOUT_SUMMARY.search(summ[m.end():hi]):
            continue
        if _NOTE_SUBJECT.search(summ[lo:m.start()]) and _NOTE_PRONOUN.match(summ[m.end():hi]):
            continue
        pre = _WORD.findall(summ[lo:m.start()].lower())[-_BEFORE:]
        mark = _WORD.findall(m.group(1).lower())
        post_text = summ[m.end():hi]
        # Take out a title that expands an id the raw text carries.
        post_text = _TITLE.sub(
            lambda t: " " if (t.group(1) or t.group(2) or t.group(3)) in id_years else t.group(0),
            post_text)
        post = _WORD.findall(post_text.lower())[:_AFTER]
        words = pre + mark + post
        sup = gloss_support(words, rjoin)
        if sup < GLOSS_SUPPORT_MIN:
            out.append({"marker": marker, "support": round(sup, 2),
                        "text": summ[lo:hi].strip()})
    return out


def id_title_mismatches(final: str) -> list:
    """A change record's id given, next to it, an instrument title of another
    year: `Widget Act 1902 (widget/1905/3)` or `widget/1905/3 (Widget Act 1902)`.
    (A wrong title of the RIGHT year cannot be seen without the index.)"""
    summ = summary_part(final)
    out = []
    for m in _ID.finditer(summ):
        year = m.group(1)
        # id then a parenthetical title: the title's year is its LAST year.
        after = re.match(r"[`*]*\s*\((?:the\s+)?([^()]*(?:\([^()]*\)[^()]*)*)\)", summ[m.end():m.end() + 300], re.I)
        titles = []
        if after:
            ts = list(_TITLE.finditer(after.group(1)))
            if ts:
                titles.append(ts[-1])
        # a title then the id in brackets or backticks.
        before = summ[max(0, m.start() - 200):m.start()]
        bm = re.search(r"(?:Act|Regulations|Order|Rules|Measure)\s+(\d{4})[*`\s]*\(?\s*(?:cited as\s+)?[`*]*$", before)
        if bm:
            titles.append(bm)
        for t in titles:
            ty = next(g for g in t.groups() if g)
            if ty != year:
                out.append({"id": m.group(0), "title_year": ty,
                            "text": summ[max(0, m.start() - 120):m.end() + 120].strip()})
                break
    return out


def _dirs(given) -> list:
    if not given:
        return sorted(p for p in REPLAY.iterdir() if p.is_dir())
    return [Path(d) if Path(d).is_dir() else REPLAY / d for d in given]


def _base(doc: dict) -> str:
    return str((doc.get("script") or {}).get("base") or doc.get("session_id"))


def _is_summary(tl: dict) -> bool:
    if "summarised" in tl:
        return bool(tl.get("summarised")) and not tl.get("memo_hit")
    return _summarised(tl) and len(tl["final_result"]) < len(tl["raw_result"])


def scan_glosses(dirs, sessions=None) -> tuple:
    """(summaries read by family, rows): one row per gloss or id mismatch, as
    dicts of dir, file, session, turn, tool, kind, counted, marker/id, support/
    title_year, text. `counted` is False for a gloss in a case-law summary."""
    sessions = set(sessions or [])
    read = {"legislation": 0, "other": 0}
    rows = []
    for d in dirs:
        for f in sorted(d.glob("*.json")):
            doc = json.loads(f.read_text(encoding="utf-8"))
            base = _base(doc)
            if sessions and base not in sessions:
                continue
            for t, _dg, tl in _tools(doc):
                if not _is_summary(tl):
                    continue
                name = tl.get("name")
                leg = name in GLOSS_TOOLS
                read["legislation" if leg else "other"] += 1
                if leg:
                    read.setdefault(d.name, 0)
                    read[d.name] += 1
                raw, fin = tl.get("raw_result") or "", tl.get("final_result") or ""
                where = {"dir": d.name, "file": f.stem, "session": base, "turn": t.get("turn"), "tool": name}
                for g in glosses_in(raw, fin):
                    rows.append({**where, "kind": "gloss", "counted": leg, "key": g["marker"],
                                 "value": g["support"], "text": g["text"]})
                for x in id_title_mismatches(fin):
                    rows.append({**where, "kind": "id", "counted": True, "key": x["id"],
                                 "value": x["title_year"], "text": x["text"]})
    return read, rows


def cmd_glosses(args) -> int:
    read, rows = scan_glosses(_dirs(args.dir), args.session)
    counted = [r for r in rows if r["kind"] == "gloss" and r["counted"]]
    listed = [r for r in rows if r["kind"] == "gloss" and not r["counted"]]
    ids = [r for r in rows if r["kind"] == "id"]
    n_with = len({(r["dir"], r["file"], r["turn"]) for r in counted})
    print(f"summaries of legislation read: {read['legislation']} (memo hits not counted); "
          f"GLOSSES: {len(counted)} (in {n_with} run-file turns); "
          f"id given a title of another year: {len(ids)}")
    print(f"case-law summaries read: {read['other']}; marker matches there (listed, NOT counted: "
          f"a judgment's own reasoning reads the same): {len(listed)}")

    def tally(rs, key):
        out = {}
        for r in rs:
            out[r[key]] = out.get(r[key], 0) + 1
        return ", ".join(f"{k} {v}" for k, v in sorted(out.items(), key=lambda kv: -kv[1]))

    print("  by marker: " + tally(counted, "key"))
    print("  by tool:   " + tally(counted, "tool"))
    by = {}
    for r in counted:
        by.setdefault(r["dir"], {}).setdefault(r["session"], 0)
        by[r["dir"]][r["session"]] += 1
    for d, s in by.items():
        print(f"  glosses {d:<24} {sum(s.values()):>3} in {read.get(d, 0):>4} summaries  {s}")
    for r in ids:
        print(f"  ids     {r['dir']:<24} {r['session']}")
    for r in rows:
        text = " ".join(r["text"].split())
        loc = f"{r['dir']} {r['file']} t{r['turn']} {r['tool']}"
        if r["kind"] == "gloss" and args.list:
            tag = "GLOSS" if r["counted"] else "CASE "
            print(f"  {tag} {loc} [{r['key']} {r['value']:.2f}] {text}")
        elif r["kind"] == "id" and args.ids:
            print(f"  ID    {loc} [{r['key']} titled {r['value']}] {text}")
    return 0


def _rubric(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _tools(doc: dict):
    for t in doc.get("turns") or []:
        for dg in (t.get("audit") or {}).get("delegations") or []:
            for tl in dg.get("tools") or []:
                yield t, dg, tl


def _summarised(tl: dict) -> bool:
    raw, fin = tl.get("raw_result") or "", tl.get("final_result") or ""
    return bool(raw and fin and raw != fin)


def added_slots(doc: dict, adds: list, self_ids: list) -> list:
    """(turn, delegation, tool) where the summary names what the raw text does not."""
    pats = [re.compile(p, re.I) for p in adds]
    selfs = [re.compile(re.escape(s), re.I) for s in self_ids]
    out = []
    for t, dg, tl in _tools(doc):
        if not _summarised(tl):
            continue
        if any(s.search(json.dumps(tl.get("args") or {})) for s in selfs):
            continue
        raw, fin = tl["raw_result"], tl["final_result"]
        if any(p.search(fin) for p in pats) and not any(p.search(raw) for p in pats):
            out.append((t, dg, tl))
    return out


def cmd_count(args) -> int:
    rub = _rubric(Path(args.rubric))
    dirs = [Path(d) for d in args.dir] if args.dir else sorted(p for p in REPLAY.iterdir() if p.is_dir())
    total = hits = 0
    by = {}
    for d in dirs:
        for f in sorted(d.glob("*.json")):
            doc = json.loads(f.read_text(encoding="utf-8"))
            total += sum(1 for _t, _d, tl in _tools(doc) if _summarised(tl))
            base = str((doc.get("script") or {}).get("base") or doc.get("session_id"))
            entry = rub.get(base) or {}
            if not entry.get("summary_adds"):
                continue
            n = len(added_slots(doc, entry["summary_adds"], entry.get("self_ids") or []))
            if n:
                hits += n
                by.setdefault(d.name, {}).setdefault(base, 0)
                by[d.name][base] += n
    print(f"summarised tool results: {total}; with a rubric addition absent from the raw text: {hits}")
    for d, s in by.items():
        print(f"  {d:<24} {s}")
    return 0


async def _key_and_model() -> tuple:
    import asyncpg  # noqa: PLC0415
    from tools.seam_replay import DEFAULT_DB_URL  # noqa: PLC0415
    conn = await asyncpg.connect(DEFAULT_DB_URL)
    try:
        row = await conn.fetchval("SELECT value FROM app_settings WHERE key='provider.openrouter'")
    finally:
        await conn.close()
    p = json.loads(row or "{}")
    if not p.get("api_key"):
        raise SystemExit("no OpenRouter api_key in app_settings")
    return p["api_key"], p.get("summarisation_model") or "google/gemini-3-flash-preview"


def _prompts(rule: str = "source"):
    """The product prompt, and the same prompt minus one rule (`source`, P3.3's
    SUMMARY_SOURCE_RULE, or `gloss`, P3.16's SUMMARY_GLOSS_RULE)."""
    from src.agent import summarisation as s  # noqa: PLC0415
    name = {"source": "SUMMARY_SOURCE_RULE", "gloss": "SUMMARY_GLOSS_RULE"}[rule]
    const = getattr(s, name, None)
    if const is None:
        raise SystemExit(f"this checkout's summarise_prompt has no {name}")

    def without_rule(text, query):
        return s.summarise_prompt(text, query).replace(f"{const} ", "", 1)

    return s, {"with rule": s.summarise_prompt, "without rule": without_rule}


def _sides(args) -> tuple:
    """`--side with|without` draws one side only, to set against the other side
    drawn the same day (a second wording costs half)."""
    s, sides = _prompts(args.rule)
    pick = getattr(args, "side", "both")
    if pick != "both":
        sides = {k: v for k, v in sides.items() if k == f"{pick} rule"}
    return s, sides


# For `--dry-run` only: approximate prices of the summarisation model per token
# and a typical summary's length. Every paid run prints the cost the responses
# report, which is the figure to book.
_PRICE_IN, _PRICE_OUT, _OUT_TOKENS = 0.5e-6, 3.0e-6, 1500


async def _draw(client, key, model, prompt) -> tuple:
    r = await client.post("https://openrouter.ai/api/v1/chat/completions",
                          headers={"Authorization": f"Bearer {key}"},
                          json={"model": model, "temperature": 0, "stream": False,
                                "messages": [{"role": "user", "content": prompt}]}, timeout=300)
    j = r.json()
    return (j["choices"][0]["message"]["content"] or ""), float((j.get("usage") or {}).get("cost") or 0)


def _chunks(s, raw: str) -> list:
    n = s.SUMMARISE_CHUNK_CHARS
    return [raw[i:i + n] for i in range(0, len(raw), n)] or [raw]


async def _summarise(client, key, model, fn, s, raw, brief) -> tuple:
    """One summary as `summarise_for_query` makes it: each chunk summarised with
    the prompt, the partials joined. (Its consolidation pass, run only when the
    joined partials exceed a chunk, is not reproduced.)"""
    res = await asyncio.gather(*[_draw(client, key, model, fn(c, brief)) for c in _chunks(s, raw)])
    return "\n\n---\n\n".join(o for o, _c in res), sum(c for _o, c in res)


def _estimate(s, raws: list, reps: int, sides: int = 2) -> tuple:
    calls = sum(len(_chunks(s, r)) for r in raws) * reps * sides
    chars = sum(len(r) for r in raws) * reps * sides
    return calls, chars / 4 * _PRICE_IN + calls * _OUT_TOKENS * _PRICE_OUT


def _measure(raw: str, text: str, name: str) -> dict:
    return {"glosses": len(glosses_in(raw, text)) if name in GLOSS_TOOLS else 0,
            "prov": len(_provisions(text) & _provisions(raw)), "chars": len(text),
            "neg": len(NEGATIVE.findall(text))}


def _gloss_slots(args) -> list:
    """(label, tool, raw, brief) for every summary of legislation whose stored
    summary carries a gloss, in --dir and --session."""
    slots, seen = [], set()
    for d in _dirs(args.dir):
        for f in sorted(d.glob("*.json")):
            doc = json.loads(f.read_text(encoding="utf-8"))
            if args.session and _base(doc) not in args.session:
                continue
            for t, dg, tl in _tools(doc):
                raw, brief = tl.get("raw_result") or "", dg.get("brief") or ""
                if (_is_summary(tl) and tl.get("name") in GLOSS_TOOLS
                        and (not args.max_raw or len(raw) <= args.max_raw)
                        and (raw, brief) not in seen
                        and glosses_in(raw, tl["final_result"])):
                    seen.add((raw, brief))
                    slots.append((f"{d.name} {f.stem} t{t.get('turn')}", tl.get("name"), raw, brief))
    return slots


async def _redraw(args) -> int:
    import httpx  # noqa: PLC0415
    s, sides = _sides(args)
    pats = []
    if args.glosses:
        slots = _gloss_slots(args)
    else:
        session = (args.session or [None])[0]
        rub = _rubric(Path(args.rubric)).get(session) or {}
        if not rub.get("summary_adds"):
            print(f"  the rubric has no summary_adds for {session}")
            return 2
        pats = [re.compile(p, re.I) for p in rub["summary_adds"]]
        slots = []
        for d in _dirs(args.dir):
            for f in sorted(d.glob(f"{session}_rep*.json")):
                doc = json.loads(f.read_text(encoding="utf-8"))
                for t, dg, tl in added_slots(doc, rub["summary_adds"], rub.get("self_ids") or []):
                    if len(tl["raw_result"]) <= s.SUMMARISE_CHUNK_CHARS:
                        slots.append((f"{d.name} {f.stem} t{t.get('turn')}", tl.get("name"),
                                      tl["raw_result"], dg.get("brief") or ""))
    calls, est = _estimate(s, [raw for _l, _n, raw, _b in slots], args.reps, len(sides))
    print(f"{len(slots)} slot(s), {args.reps} draw(s) a side, rule '{args.rule}': "
          f"{calls} calls, estimated ${est:.2f}")
    if args.dry_run:
        for label, name, raw, _b in slots:
            print(f"  {label} {name} raw {len(raw)} chars, {len(_chunks(s, raw))} chunk(s)")
        return 0
    key, model = await _key_and_model()
    print(f"model {model}")
    keys = ("glosses", "prov", "chars", "neg")
    tally = {k: dict.fromkeys(keys + ("adds", "n"), 0) for k in sides}
    cost = 0.0
    async with httpx.AsyncClient() as client:
        for i, (label, name, raw, brief) in enumerate(slots, 1):
            row = []
            for side, fn in sides.items():
                res = await asyncio.gather(*[_summarise(client, key, model, fn, s, raw, brief)
                                             for _ in range(args.reps)])
                cost += sum(c for _o, c in res)
                _save(args, f"{i:02d} {label} {name}", side, [o for o, _c in res])
                ms = [_measure(raw, o, name) for o, _c in res]
                adds = sum(1 for o, _c in res if any(p.search(o) for p in pats))
                for k in keys:
                    tally[side][k] += sum(m[k] for m in ms)
                tally[side]["adds"] += adds
                tally[side]["n"] += args.reps
                row.append(f"{side}: glosses {sum(m['glosses'] for m in ms)} prov "
                           f"{sum(m['prov'] for m in ms)} neg {sum(m['neg'] for m in ms)}"
                           + (f" adds {adds}/{args.reps}" if pats else ""))
            print(f"  {label} {name:<28} " + " | ".join(row), flush=True)
    for side, t in tally.items():
        print(f"TOTAL {side}: {t['n']} summaries, glosses {t['glosses']}, provisions {t['prov']}, "
              f"chars {t['chars']}, 'does not contain' {t['neg']}"
              + (f", adds {t['adds']}/{t['n']}" if pats else ""))
    print(f"cost ${cost:.3f}")
    return 0


def _provisions(s: str) -> set:
    return {m.group(1).lower() for m in PROVISION.finditer(s)}


def _save(args, label: str, side: str, texts: list) -> None:
    """With --out D: every draw as D/<label>__<side>__<k>.md, for reading (the
    drawn text quotes the law, so D belongs in the gitignored evidence)."""
    if not getattr(args, "out", None):
        return
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    # The label leads with the slot's index: two results of one turn share the rest.
    stem = re.sub(r"[^\w.-]+", "_", label).strip("_")
    for k, text in enumerate(texts, 1):
        (out / f"{stem}__{side.replace(' ', '_')}__{k}.md").write_text(text, encoding="utf-8")


async def _panel(args) -> int:
    import httpx  # noqa: PLC0415
    s, sides = _sides(args)
    pool = []
    for d in PANEL_DIRS:
        for f in sorted((REPLAY / d).glob("*.json")):
            doc = json.loads(f.read_text(encoding="utf-8"))
            if str(doc.get("session_id")) in (args.exclude or []):
                continue
            for t, dg, tl in _tools(doc):
                if (_summarised(tl) and len(tl["final_result"]) < len(tl["raw_result"])
                        and len(tl["raw_result"]) <= s.SUMMARISE_CHUNK_CHARS):
                    pool.append((d, doc.get("session_id"), t.get("turn"), tl.get("name"),
                                 tl["raw_result"], dg.get("brief") or ""))
    random.seed(args.seed)
    slots = random.sample(pool, min(args.n, len(pool)))
    calls, est = _estimate(s, [x[4] for x in slots], args.reps, len(sides))
    print(f"{len(slots)} of {len(pool)} eligible results; {args.reps} draw(s) a side; seed {args.seed}; "
          f"rule '{args.rule}': {calls} calls, estimated ${est:.2f}")
    if args.dry_run:
        for d, sid, turn, name, raw, _b in slots:
            print(f"  {d:<14} {sid} t{turn} {name:<28} raw {len(raw)} chars")
        return 0
    key, model = await _key_and_model()
    keys = ("prov", "chars", "neg", "glosses")
    agg, cost = {k: dict.fromkeys(keys, 0) for k in sides}, 0.0
    async with httpx.AsyncClient() as client:
        for i, (d, sid, turn, name, raw, brief) in enumerate(slots, 1):
            row = []
            for side, fn in sides.items():
                res = await asyncio.gather(*[_draw(client, key, model, fn(raw, brief))
                                             for _ in range(args.reps)])
                cost += sum(c for _o, c in res)
                _save(args, f"{i:02d} {d} {sid} t{turn} {name}", side, [o for o, _c in res])
                ms = [_measure(raw, o, name) for o, _c in res]
                for k in keys:
                    agg[side][k] += sum(m[k] for m in ms)
                row.append(f"{side}: prov {sum(m['prov'] for m in ms)} chars "
                           f"{sum(m['chars'] for m in ms) // args.reps} neg {sum(m['neg'] for m in ms)} "
                           f"glosses {sum(m['glosses'] for m in ms)}")
            print(f"  {d:<14} {sid} t{turn} {name:<28} " + " | ".join(row), flush=True)
    print("TOTAL " + " | ".join(f"{k}: provisions {a['prov']}, chars {a['chars']}, "
                                f"'does not contain' {a['neg']}, glosses {a['glosses']}"
                                for k, a in agg.items()) + f"; cost ${cost:.3f}")
    return 0


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    p = argparse.ArgumentParser(prog="summary_probe")
    p.add_argument("--rubric", default=str(RUBRIC))
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("count", help="free: summaries adding what the raw text lacks")
    c.add_argument("--dir", nargs="+", default=None)
    r = sub.add_parser("redraw", help="paid: re-summarise with and without a rule")
    r.add_argument("--dir", nargs="+", required=True)
    r.add_argument("--session", nargs="+", required=True)
    r.add_argument("--reps", type=int, default=3)
    r.add_argument("--rule", choices=("source", "gloss"), default="source",
                   help="the rule the 'without rule' side drops")
    r.add_argument("--glosses", action="store_true",
                   help="slots are the stored summaries `glosses` flags, not the rubric's additions")
    r.add_argument("--max-raw", type=int, default=0, help="with --glosses: skip raw results longer than this")
    r.add_argument("--dry-run", action="store_true", help="list the slots and the estimated cost; draw nothing")
    r.add_argument("--out", default=None, help="save every draw here (use the gitignored evidence)")
    r.add_argument("--side", choices=("both", "with", "without"), default="both")
    pn = sub.add_parser("panel", help="paid: the no-loss check on other sessions")
    pn.add_argument("--n", type=int, default=24)
    pn.add_argument("--reps", type=int, default=2)
    pn.add_argument("--seed", type=int, default=32)
    pn.add_argument("--exclude", nargs="*", default=["6338"])
    pn.add_argument("--rule", choices=("source", "gloss"), default="source")
    pn.add_argument("--dry-run", action="store_true")
    pn.add_argument("--out", default=None, help="save every draw here (use the gitignored evidence)")
    pn.add_argument("--side", choices=("both", "with", "without"), default="both")
    g = sub.add_parser("glosses", help="free: interpretation a summary adds that its raw text lacks")
    g.add_argument("--dir", nargs="+", default=None,
                   help="replay directories (a name under the evidence replay/ or a path); default all")
    g.add_argument("--session", nargs="+", default=None, help="only these sessions (script base or id)")
    g.add_argument("--list", action="store_true", help="print every gloss (quotes summary text)")
    g.add_argument("--ids", action="store_true", help="print every id given a title of another year")
    args = p.parse_args(argv)
    if args.cmd == "count":
        return cmd_count(args)
    if args.cmd == "glosses":
        return cmd_glosses(args)
    return asyncio.run(_redraw(args) if args.cmd == "redraw" else _panel(args))


if __name__ == "__main__":
    raise SystemExit(main())
