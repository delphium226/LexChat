"""P3.52 lever (c): hand the legislation Worker the lawyer's own words.

**Why this exists.** The Worker's only user message used to be the Manager's
brief. The lawyer's own words never reached it, though the request carries them
(`_cache_key_query`, `routers/agent_request.build_request_config`: the raw last
user message). That matters because LEX's legislation searches rank by meaning
(Session 47, `evidence/seam/s47/p352_probe*.jsonl`): Q17's own words, "What
provision enables Scottish Ministers to establish a national bus fare cap
scheme?", put the Transport (Scotland) Act 2001 third at the Act level and s.38
third in its section search, while the Manager's brief named "national
concessionary travel scheme" in 10 of 16 stored turn 1s and steered the Worker
to the 2005 Act. P3.52's lever (a), `prompts._LEGISLATION_QUERY_WORDING`, asks
the quick-lookup Worker to search "in the question's own words"; until this
module it had only the brief's.

**The brief governs scope.** The lawyer's latest message is appended AFTER the
brief, labelled, and the label says the brief sets the scope: a follow-up such
as "and Wales?" means little alone, and a Manager that splits a question into
two delegations hands each Worker the whole message.

**Where it applies.** The legislation research types (`legislation_only`,
`legislation_and_case_law`), in any chat mode but Deep Research. Never drafting:
there the lawyer's message is unpublished legislative text. A no-op where the
message is empty or absent: Deep Research leaves `_cache_key_query` empty (a
step's brief is the approved plan text), and a consult or a script never sets
it.

**The Worker's message only.** `run_worker_agent` logs the brief at INFO and
the audit records it as `delegations[].brief`; both keep the brief as the
Manager wrote it, so no raw user text reaches an INFO log (`utils/redact.py`)
and `tools/seam_replay.py` still reads back the Manager's words. Every other
reader of the brief is unchanged too: P3.7's routed lookup (over 1,916 stored
delegations the question named an instrument by number in 112, and the brief
named the same one in all 112, so reading the question would add nothing; the
lawyer's words would also reach a second delegation the Manager scoped away
from that instrument), and the summariser's query.

One function, `with_lawyer_words`, which `run_worker_agent` and the seam's
Worker builders both call, so a seam draw tests the product's own text. Never
raises: on any failure the brief is returned unchanged (Invariant 5).
"""

from __future__ import annotations

from typing import Any, Optional

# The research types whose Worker gets the lawyer's words.
LAWYER_WORDS_RESEARCH_MODES = frozenset({"legislation_only", "legislation_and_case_law"})

# The longest message handed over whole. Every stored replay question is
# shorter (2,357 turns: median 89 characters, longest 1,131); the cap only
# stops a pasted document being replayed into every round of the Worker.
MAX_LAWYER_WORDS_CHARS = 4000

LAWYER_WORDS_LABEL = "THE LAWYER'S LATEST MESSAGE"


def lawyer_words_block(question: Any, research_mode: Optional[str],
                       chat_mode: Optional[str] = None) -> str:
    """The block appended to the Worker's brief ("" where none applies)."""
    try:
        if research_mode not in LAWYER_WORDS_RESEARCH_MODES:
            return ""
        if chat_mode == "deep_research":
            return ""
        if not isinstance(question, str):
            return ""
        text = question.strip()
        if not text:
            return ""
        size = ""
        if len(text) > MAX_LAWYER_WORDS_CHARS:
            head = text[:MAX_LAWYER_WORDS_CHARS]
            # Cut at a word: drop a word the cap fell inside, if there is
            # another before it.
            if not text[MAX_LAWYER_WORDS_CHARS].isspace() and len(head.split()) > 1:
                head = head.rsplit(None, 1)[0]
            head = head.rstrip()
            size = f" (its first {len(head):,} of {len(text):,} characters)"
            text = head + " …"
        return (
            f"\n\n[{LAWYER_WORDS_LABEL} — as the lawyer wrote it{size}. The brief above "
            f"sets the scope of this research and governs where the two differ; the "
            f"message gives the lawyer's own words.]\n"
            f"{text}\n"
            f"[/{LAWYER_WORDS_LABEL}]"
        )
    except Exception:
        return ""


def with_lawyer_words(brief: str, question: Any, research_mode: Optional[str],
                      chat_mode: Optional[str] = None) -> str:
    """The Worker's user message: the brief, then the lawyer's latest message
    where `lawyer_words_block` gives one."""
    return (brief or "") + lawyer_words_block(question, research_mode, chat_mode)
