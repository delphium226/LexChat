"""P3.52 Fix 1: provisions ranked, by code, against the legal professional's own words.

**Why this exists.** Q17 (6345), "What provision enables Scottish Ministers to
establish a national bus fare cap scheme?": the reviewer's answer is s.38 of
the Transport (Scotland) Act 2001 (grants to bus operators, the fare cap a
condition of grant). Since levers (a) and (c) the quick-lookup Worker's first
section search is of the Transport (Scotland) Act 2005 in 13 of 16 runs, its
query copying "national concessionary fares schemes" from that Act's long title
(the `description` P3.6 hands it); it section-searches the 2001 Act in only 7 of
16; when it does, s.38 comes back 6 of 7 and, once held, is cited 6 of 6
(`evidence/seam/s52/brief/crosstab.md`). LEX ranks by meaning, and a section
search of the 2001 Act in the question's own words puts s.38 third (Session 47
probe). So the provision is reachable in one call the Worker usually does not
make; a prompt rule asking it to make that call would be followed at a rate
(Invariant 2), so code makes it.

**What it does.** After the quick-lookup Worker's FIRST `search_legislation`
of a run, code runs one `search_legislation_sections` per Act in that result
(Acts only, in the result's order, at most `MAX_ACTS`), each with the legal professional's
latest message as the query, and appends one block to that result: the top
`PER_ACT` provisions of each Act, with label, heading, URL and the opening
`OPENING_CHARS` characters, saying they were ranked by meaning against the
question as asked and are not established as relevant.

**Scope** (lever (c)'s, narrowed to the quick-lookup Worker): conversational
chat mode, the legislation research types; never Deep Research, Research
mode, the parliamentary bots, drafting, or a consult or script (no
`_cache_key_query`). A message with fewer than `MIN_QUESTION_WORDS`
distinctive words ("and Wales?") gets no block: ranked alone it says nothing.

**What it leaves alone.** The code calls are not Worker tool calls: they are
not charged to P3.1's per-instrument section budget or P2.7's discovery
budget, not counted as Worker tool calls, and add nothing to the Sources rail
(a section result's excerpt pins its Act in the rail, `_source_is_used`). They
are recorded in the run's scope record as section searches (`by_code`), so the
Manager's block says truthfully that code searched within those Acts, and the
URLs the block shows are retrieved URLs for P1.6. Memoised per request; fail
soft (Invariant 5): on any failure, no block and the result is unchanged.

Every function here is pure apart from `question_sections_block`, which awaits
the caller's `fetch`; `agent_shared.run_worker_tool` supplies it.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Awaitable, Callable, Optional

from .lawyer_words import LAWYER_WORDS_RESEARCH_MODES

logger = logging.getLogger(__name__)

SECTION_TOOL = "search_legislation_sections"

# Measured over every stored quick-lookup first search (`evidence/seam/s52/
# lev1/scan_first_searches.py`): of 1,336 conversational legislation first
# searches, 674 return at least one Act and 173 more than three. Since lever
# (a), the 2001 Act's rank among the Acts of Q17's first search is 1 to 3 in
# all 19 runs that returned it, so three Acts reach it every time.
MAX_ACTS = 3
PER_ACT = 3
OPENING_CHARS = 200
_TITLE_CHARS = 120
_HEADING_CHARS = 120
# The query sent: the legal professional's message, cut at a word past this (stored
# questions: median 89 characters, longest 1,131).
MAX_QUERY_CHARS = 1000
# Distinctive words (three letters or more, not a stop word) a message must
# have before it is ranked on its own. Over the stored conversational
# legislation messages, 2 of 31 turn-1 questions have fewer than 4 and 1 fewer
# than 3 ("Is the Scotland Act 1998 in force?"); the follow-ups below 3 are
# "This is not correct.", "Where is this stated?", "SSI 2025/119" and the like.
MIN_QUESTION_WORDS = 3
# The whole round of code calls, not each: a slow index leaves no block.
TIMEOUT_S = 20.0
# The Acts carry these prefixes (`lex._TYPE_CODES["primary"]`).
PRIMARY_PREFIXES = frozenset({"ukpga", "ukppa", "ukla", "asp", "nia", "apni", "anaw", "asc", "mwa"})

MEMO_KEY = "_question_sections_memo"
ENTRY_SOURCE = "question_sections"

BLOCK_OPEN = "[PROVISIONS RANKED AGAINST THE LEGAL PROFESSIONAL'S OWN WORDS"
BLOCK_CLOSE = "[/PROVISIONS RANKED AGAINST THE LEGAL PROFESSIONAL'S OWN WORDS]"

_STOP = frozenset("""
a an the of and or to in on for by with under from at as be is are was were any other its it
their this that these those which where when what who how not no nor into onto upon about after
before between within without than then there such each all some more most may must shall will
would can could should does did has have had act acts order orders section sections provision
provisions law laws legislation please tell explain give list does do also just there here
""".split())

_LABEL_PREFIX = {
    "section": "s.", "schedule": "Sch. ", "regulation": "reg.", "article": "art.",
    "rule": "r.", "paragraph": "para. ", "part": "Part ", "chapter": "Chapter ",
}
_URL_TAIL = re.compile(r"/(section|schedule|regulation|article|rule|paragraph|part|chapter)"
                       r"/([0-9A-Za-z]+)(?:/[^\s]*)?$")


def _words(text: str) -> set:
    return {w for w in re.findall(r"[a-z]+", text.lower()) if len(w) > 2 and w not in _STOP}


def question_query(question: Any, research_mode: Optional[str],
                   chat_mode: Optional[str]) -> str:
    """The query code ranks the Acts' provisions against, or "" where the
    block does not apply. Never raises."""
    try:
        if chat_mode != "conversational":
            return ""
        if research_mode not in LAWYER_WORDS_RESEARCH_MODES:
            return ""
        if not isinstance(question, str):
            return ""
        text = " ".join(question.split())
        if len(_words(text)) < MIN_QUESTION_WORDS:
            return ""
        if len(text) > MAX_QUERY_CHARS:
            head = text[:MAX_QUERY_CHARS]
            if not text[MAX_QUERY_CHARS].isspace() and len(head.split()) > 1:
                head = head.rsplit(None, 1)[0]
            text = head.rstrip()
        return text
    except Exception:
        return ""


def acts_in(raw_result: Any) -> list:
    """[(legislation_id, title)] of the Acts in a `search_legislation` result,
    in its order, at most `MAX_ACTS`, each once. [] on anything else."""
    try:
        data = json.loads(raw_result) if isinstance(raw_result, str) else raw_result
        out, seen = [], set()
        for row in (data or {}).get("results") or []:
            if not isinstance(row, dict):
                continue
            lid = str(row.get("legislation_id") or "").strip().strip("/")
            if not lid or lid in seen or lid.split("/")[0].lower() not in PRIMARY_PREFIXES:
                continue
            seen.add(lid)
            out.append((lid, str(row.get("title") or "").strip()))
            if len(out) >= MAX_ACTS:
                break
        return out
    except Exception:
        return []


def _cut(text: Any, limit: int) -> str:
    t = " ".join(str(text or "").split())
    if len(t) <= limit:
        return t
    head = t[:limit]
    if not t[limit].isspace() and len(head.split()) > 1:
        head = head.rsplit(None, 1)[0]
    return head.rstrip(" ,;:") + " …"


def provision_label(row: dict) -> str:
    """"s.38", "Sch. 2", "reg.4"; the number from the URL where LEX gives
    none (it returns lettered sections with `number: null`)."""
    kind = str(row.get("provision_type") or "").strip().lower()
    number = str(row.get("number") or "").strip()
    m = _URL_TAIL.search(str(row.get("url") or "").strip())
    if m and (not number or not kind):
        kind = kind or m.group(1).lower()
        number = number or m.group(2)
    if not number:
        return ""
    return f"{_LABEL_PREFIX.get(kind, kind + ' ' if kind else '')}{number}"


# The provision's own heading line at the head of its text ("Section 40)
# **National travel concession schemes**", "SCHEDULE 17 Homelessness: ..."),
# which the label and heading already give.
_HEAD_LINE = re.compile(r"^\s*(?:Section|Article|Regulation|Rule)\s+[0-9A-Za-z]+\)\s*"
                        r"(?:\*\*[^*]*\*\*)?\s*", re.I)


def _opening(text: Any, heading: str) -> str:
    t = " ".join(str(text or "").split())
    t2 = _HEAD_LINE.sub("", t, count=1)
    if t2 == t and heading:
        # "SCHEDULE 17 Homelessness: consequential amendments Section 216(3). ..."
        m = re.match(r"^\s*(?:SCHEDULE|Schedule)\s+[0-9A-Za-z]*\s*", t)
        if m and t[m.end():].startswith(heading.rstrip(" …")):
            t2 = t[m.end() + len(heading.rstrip(" …")):]
    return _cut(t2.replace("**", "").strip(), OPENING_CHARS)


def top_provisions(section_raw: Any, k: int = PER_ACT) -> list:
    """The first `k` provisions of a (slimmed) section-search result that
    carry a URL: [{"label", "heading", "url", "opening"}]. [] on anything
    else (an error string, no results)."""
    try:
        data = json.loads(section_raw) if isinstance(section_raw, str) else section_raw
        rows = (data or {}).get("results")
        if not isinstance(rows, list):
            return []
        out = []
        for row in rows:
            if not isinstance(row, dict) or not str(row.get("url") or "").strip():
                continue
            heading = _cut(row.get("title"), _HEADING_CHARS)
            out.append({
                "label": provision_label(row),
                "heading": heading,
                "url": str(row["url"]).strip(),
                "opening": _opening(row.get("text"), heading),
            })
            if len(out) >= k:
                break
        return out
    except Exception:
        return []


def render_block(per_act: list) -> str:
    """The block for [(legislation_id, title, provisions)], "" when no Act
    has a provision."""
    held = [(lid, title, provs) for lid, title, provs in per_act if provs]
    if not held:
        return ""
    lines = [
        f"\n\n{BLOCK_OPEN} — after this search, code searched within "
        f"{'the Act' if len(held) == 1 else f'each of the {len(held)} Acts'} below, "
        "using the legal professional's latest message as written as the query, and lists the "
        "provisions the index ranked first. The index ranks by meaning, not by what a "
        "provision does: none of these is established as relevant to the question, and "
        "a provision not listed is not established as irrelevant. Before citing one, "
        "read it in full (search_legislation_sections) and cite it for what its own "
        "words provide.]"
    ]
    for lid, title, provs in held:
        lines.append(f"{_cut(title, _TITLE_CHARS) or lid} ({lid}):")
        for p in provs:
            name = " ".join(x for x in (p["label"], p["heading"]) if x) or "provision"
            line = f"  - {name} — {p['url']}"
            if p["opening"]:
                line += f' — "{p["opening"]}"'
            lines.append(line)
    lines.append(BLOCK_CLOSE)
    return "\n".join(lines)


def _request_memo() -> dict:
    """``{(legislation_id, query): Task}`` on the request's own config dict
    (shared by reference through the ContextVar, as P3.21's and P3.38's
    memos are). With no request config (a script, a test) each call gets
    its own."""
    try:
        from ..agent.provider_factory import get_request_provider_config
        cfg = get_request_provider_config()
    except Exception:
        cfg = None
    if not isinstance(cfg, dict) or not cfg:
        return {}
    memo = cfg.get(MEMO_KEY)
    if not isinstance(memo, dict):
        memo = {}
        cfg[MEMO_KEY] = memo
    return memo


async def question_sections_block(
    raw_result: Any, query: str,
    fetch: Callable[[str, str], Awaitable[str]],
) -> tuple:
    """`(block, fetched)` for a first `search_legislation` result: the block
    to append ("" for none) and, for each Act the block lists,
    `(args, shown_result)`, where `shown_result` holds only the provisions
    the block shows (for the scope record and the retrieved URLs).

    `fetch(legislation_id, query)` runs one section search and returns its
    (slimmed) JSON string. Never raises but CancelledError; on a timeout or
    any other failure returns ("", [])."""
    try:
        if not query:
            return "", []
        acts = acts_in(raw_result)
        if not acts:
            return "", []
        memo = _request_memo()
        loop = asyncio.get_running_loop()
        pending = []
        for lid, _ in acts:
            key = (lid, query)
            held = memo.get(key)
            # A finished call is kept as its result; an unfinished one as its
            # task, which a concurrent run of the same request awaits too.
            if isinstance(held, str):
                continue
            if not (isinstance(held, asyncio.Future) and held.get_loop() is loop):
                memo[key] = asyncio.ensure_future(fetch(lid, query))
            pending.append(key)
        if pending:
            got = await asyncio.wait_for(
                asyncio.gather(*(asyncio.shield(memo[k]) for k in pending),
                               return_exceptions=True),
                TIMEOUT_S)
            for key, raw in zip(pending, got):
                if isinstance(raw, str):
                    memo[key] = raw
        done = [memo.get((lid, query)) for lid, _ in acts]
        per_act, fetched = [], []
        for (lid, title), raw in zip(acts, done):
            if not isinstance(raw, str):
                continue
            provs = top_provisions(raw)
            if not provs:
                continue
            per_act.append((lid, title, provs))
            shown = {"results": [{"legislation_id": lid, "url": p["url"]} for p in provs],
                     "returned": len(provs)}
            fetched.append(({"query": query, "legislation_id": lid}, shown))
        return render_block(per_act), fetched
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.warning("[Worker] Provisions ranked against the legal professional's words: failed",
                       exc_info=True)
        return "", []
