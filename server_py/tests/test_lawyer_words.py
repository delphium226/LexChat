"""P3.52 lever (c): the legislation Worker is handed the lawyer's own words.

The Worker's only user message used to be the Manager's brief. LEX's
legislation searches rank by meaning, and Q17's own words reach s.38 of the
Transport (Scotland) Act 2001 where the brief's "national concessionary travel
scheme" does not (Session 47). Code now appends the lawyer's latest message
(`_cache_key_query`) after the brief, labelled, with the brief governing scope.

Pinned here: where it applies and where it must not (drafting, Deep Research,
a consult); that it reaches the Worker's message and nothing else (the INFO
log, the audit's brief, P3.7's routed lookup and the summariser's query keep
the Manager's brief); the order beside P3.7's block; and that the seam builds
the message with the product's own function.
"""

import asyncio
import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agent import agent_core  # noqa: E402
from src.agent.agent_core import run_worker_agent  # noqa: E402
from src.agent.provider_factory import set_request_provider_config  # noqa: E402
from src.agent.tools import executor  # noqa: E402
from src.utils import lawyer_words as lw  # noqa: E402
from src.utils.audit_trace import AuditCollector, set_audit_collector  # noqa: E402
from src.utils.lawyer_words import (  # noqa: E402
    LAWYER_WORDS_LABEL,
    MAX_LAWYER_WORDS_CHARS,
    lawyer_words_block,
    with_lawyer_words,
)
from tools import seam_replay as sr  # noqa: E402

Q17 = "What provision enables Scottish Ministers to establish a national bus fare cap scheme?"
BRIEF = ("Find the legislative provision that enables Scottish Ministers to establish a "
         "national bus fare cap scheme. Look for powers related to bus fares, capping, or "
         "national concessionary travel schemes in Scotland.")


@pytest.fixture(autouse=True)
def _clean_request_state():
    """The request config is a ContextVar: a `_cache_key_query` left set here
    would key every later test's local-cache lookups on Q17."""
    set_audit_collector(None)
    yield
    set_audit_collector(None)
    set_request_provider_config({})


# --- 1. the block ----------------------------------------------------------


@pytest.mark.parametrize("research_mode", ["legislation_only", "legislation_and_case_law"])
@pytest.mark.parametrize("chat_mode", ["conversational", "research", None, ""])
def test_a_legislation_worker_gets_the_lawyers_message_verbatim(research_mode, chat_mode):
    block = lawyer_words_block(Q17, research_mode, chat_mode)
    assert block.startswith(f"\n\n[{LAWYER_WORDS_LABEL} — as the lawyer wrote it. ")
    assert "The brief above sets the scope of this research and governs where the two " \
           "differ" in block
    assert f"]\n{Q17}\n[/{LAWYER_WORDS_LABEL}]" in block
    assert block.endswith(f"[/{LAWYER_WORDS_LABEL}]")
    assert with_lawyer_words(BRIEF, Q17, research_mode, chat_mode) == BRIEF + block


@pytest.mark.parametrize("research_mode", [
    "case_law_only", "drafting", "parliamentary_records", "westminster_records", "", None])
def test_no_other_research_type_gets_it(research_mode):
    """Never drafting: there the lawyer's message is unpublished legislative text."""
    assert lawyer_words_block(Q17, research_mode, "conversational") == ""
    assert with_lawyer_words(BRIEF, Q17, research_mode, "conversational") == BRIEF


def test_a_deep_research_step_never_gets_it():
    """The product leaves `_cache_key_query` empty in Deep Research; the gate
    holds even where a caller (the seam) has the turn's question."""
    assert lawyer_words_block(Q17, "legislation_only", "deep_research") == ""


@pytest.mark.parametrize("question", ["", "   \n ", None, 42, ["a list"], {"content": Q17}])
def test_no_message_is_a_no_op(question):
    assert with_lawyer_words(BRIEF, question, "legislation_only", "conversational") == BRIEF


def test_a_follow_up_keeps_its_lines_and_is_stripped_only_at_the_ends():
    q = "  And Wales?\nSame question, but s.2 only.  "
    block = lawyer_words_block(q, "legislation_only", "conversational")
    assert "]\nAnd Wales?\nSame question, but s.2 only.\n[/" in block


def test_a_long_paste_is_cut_at_a_word_and_says_so():
    word = "provision "
    q = word * (MAX_LAWYER_WORDS_CHARS // len(word) + 50)
    block = lawyer_words_block(q, "legislation_only", "conversational")
    body = block.split("]\n", 1)[1].rsplit("\n[/", 1)[0]
    assert body.endswith("provision …")
    kept = body[: -len(" …")]
    assert len(kept) <= MAX_LAWYER_WORDS_CHARS
    assert f"(its first {len(kept):,} of {len(q.strip()):,} characters)" in block
    # at the cap exactly, nothing is cut
    exact = "x" * MAX_LAWYER_WORDS_CHARS
    assert f"]\n{exact}\n[/" in lawyer_words_block(exact, "legislation_only", "")
    assert "its first" not in lawyer_words_block(exact, "legislation_only", "")


def test_a_cut_falling_inside_a_word_drops_that_word():
    q = "a" * (MAX_LAWYER_WORDS_CHARS - 3) + " bcdefgh"
    block = lawyer_words_block(q, "legislation_only", "conversational")
    assert "]\n" + "a" * (MAX_LAWYER_WORDS_CHARS - 3) + " …\n[/" in block
    assert "bcd" not in block


def test_every_stored_question_goes_whole():
    """The cap is above the longest stored replay question (1,131 characters)."""
    assert MAX_LAWYER_WORDS_CHARS >= 1131


def test_the_block_never_raises(monkeypatch):
    monkeypatch.setattr(lw, "LAWYER_WORDS_RESEARCH_MODES", None)   # `in None` raises
    assert lawyer_words_block(Q17, "legislation_only", "conversational") == ""


# --- 2. the Worker seam: run_worker_agent -----------------------------------


class _Log:
    def __init__(self):
        self.lines = []

    def _rec(self, msg, *args, **kw):
        try:
            self.lines.append(str(msg) % args if args else str(msg))
        except Exception:
            self.lines.append(str(msg))

    info = warning = debug = error = exception = _rec


def _run(monkeypatch, brief, *, question=Q17, research_mode="legislation_only",
         chat_mode="conversational", lex_by_id=None, tool_calls=()):
    cfg = {"_provider": "openrouter", "_research_mode": research_mode,
           "_chat_mode": chat_mode, "model": "test-model"}
    if question is not None:
        cfg["_cache_key_query"] = question
    set_request_provider_config(cfg)
    seen = {"lex": [], "tool_queries": []}
    log = _Log()
    monkeypatch.setattr(agent_core, "logger", log)

    async def fake_lex(client, method, url, *, name="", **kwargs):
        body = kwargs.get("json") or {}
        lid = body.get("legislation_id") or "{legislation_type}/{year}/{number}".format(**body)
        seen["lex"].append(lid)
        lookup, sections = (lex_by_id or {})[lid]
        status, payload = sections if url.endswith("/section/lookup") else lookup
        return httpx.Response(status, json=payload, request=httpx.Request(method, url))

    monkeypatch.setattr(executor, "_request_with_retry", fake_lex)

    real_tool = agent_core.run_worker_tool

    async def spy_tool(name, args, query, *a, **kw):
        seen["tool_queries"].append((name, query))
        if name == "search_legislation":
            return json.dumps({"results": [], "total": 0})
        return await real_tool(name, args, query, *a, **kw)

    monkeypatch.setattr(agent_core, "run_worker_tool", spy_tool)

    async def loop(messages, model, cancel_event, num_ctx, tools, tool_exec, on_chunk=None,
                   **kw):
        seen["message"] = messages[1]["content"]
        for name, args in tool_calls:
            await tool_exec(name, args)
        return {"role": "assistant", "content": "Report."}

    asyncio.run(run_worker_agent(loop, lambda *a, **k: None, brief, "test-model", None, 0))
    seen["log"] = log.lines
    return seen


def test_the_worker_message_is_the_brief_then_the_lawyers_words(monkeypatch):
    seen = _run(monkeypatch, BRIEF)
    assert seen["message"] == with_lawyer_words(BRIEF, Q17, "legislation_only",
                                                "conversational")
    assert seen["message"].startswith(BRIEF + "\n\n[THE LAWYER'S LATEST MESSAGE")
    assert seen["message"].count(Q17) == 1


def test_a_research_mode_legislation_and_case_law_worker_gets_it_too(monkeypatch):
    seen = _run(monkeypatch, BRIEF, research_mode="legislation_and_case_law",
                chat_mode="research")
    assert seen["message"].endswith(f"{Q17}\n[/{LAWYER_WORDS_LABEL}]")


@pytest.mark.parametrize("kw", [
    {"question": None},                                # a consult or a script
    {"question": ""},                                  # Deep Research, as the product sets it
    {"chat_mode": "deep_research"},
    {"research_mode": "drafting"},
    {"research_mode": "case_law_only"},
])
def test_elsewhere_the_worker_gets_the_brief_alone(monkeypatch, kw):
    seen = _run(monkeypatch, BRIEF, **kw)
    assert seen["message"] == BRIEF


def test_the_audit_keeps_the_brief_as_the_manager_wrote_it(monkeypatch):
    """`delegations[].brief` is what an eval harness and `seam_replay` read back."""
    audit = AuditCollector("req-c")
    set_audit_collector(audit)
    _run(monkeypatch, BRIEF)
    assert [d["brief"] for d in audit.delegations] == [BRIEF]


def test_no_raw_user_text_reaches_an_info_log(monkeypatch):
    """The Worker's start line logs the brief at INFO (as before); the
    lawyer's words must not join it (utils/redact.py)."""
    seen = _run(monkeypatch, "Short brief.", question="My client Jane Doe asks about s.38.")
    assert any("Short brief." in line for line in seen["log"])
    assert not any("Jane Doe" in line for line in seen["log"])


def test_the_tools_and_the_summariser_still_get_the_brief(monkeypatch):
    seen = _run(monkeypatch, BRIEF, tool_calls=[("search_legislation", {"query": Q17})])
    assert seen["tool_queries"] == [("search_legislation", BRIEF)]


NOT_FOUND = (404, {"detail": "Legislation not found"})


def test_the_routed_lookup_reads_the_brief_not_the_lawyers_words(monkeypatch):
    """Over 1,916 stored delegations the question named an instrument by number
    in 112 and the brief named the same one in all 112: reading the question
    adds nothing, and would reach a delegation the Manager scoped away."""
    seen = _run(monkeypatch, "Is the Example Act 2025 in force?",
                question="Is the Example Act 2025 in force? And SSI 2025/377?",
                lex_by_id={"ssi/2025/377": (NOT_FOUND, None)})
    assert seen["lex"] == []
    assert "NOT HELD" not in seen["message"]


def test_the_lookup_block_follows_the_lawyers_words(monkeypatch):
    seen = _run(monkeypatch, "What does SSI 2025/377 do?",
                question="what does ssi 2025/377 do",
                lex_by_id={"ssi/2025/377": (NOT_FOUND, None)})
    assert seen["lex"] == ["ssi/2025/377"]
    msg = seen["message"]
    head = with_lawyer_words("What does SSI 2025/377 do?", "what does ssi 2025/377 do",
                             "legislation_only", "conversational")
    assert msg.startswith(head)
    assert "SSI 2025/377: NOT HELD" in msg[len(head):]


# --- 3. the seam builds it with the product's function ----------------------


def _doc(chat_mode="conversational", research_mode="legislation_only", brief=BRIEF):
    return {"session_id": "6345", "rep": 1,
            "filters": {"research_mode": research_mode},
            "turns": [{"turn": 1, "question": Q17, "chat_mode": chat_mode,
                       "research_mode": research_mode,
                       "audit": {"delegations": [{"brief": brief, "tools": [
                           {"name": "search_legislation", "args": {"query": "x"},
                            "final_result": "R1", "started_at": 1.0,
                            "duration_s": 1.0}]}]}}]}


def test_the_first_round_seam_sends_what_the_product_sends():
    doc = _doc()
    msgs = sr.worker_first_round_messages(doc, doc["turns"][0])
    assert msgs[1]["content"] == with_lawyer_words(BRIEF, Q17, "legislation_only",
                                                   "conversational")
    # the before side of (c)
    off = sr.worker_first_round_messages(doc, doc["turns"][0], lawyer_words=False)
    assert off[1]["content"] == BRIEF


def test_the_seam_calls_the_product_function_not_a_copy(monkeypatch):
    monkeypatch.setattr(lw, "lawyer_words_block", lambda *a, **k: " <SENTINEL>")
    doc = _doc()
    turn = doc["turns"][0]
    for msgs in (sr.worker_first_round_messages(doc, turn),
                 sr.worker_messages(doc, turn),
                 sr.worker_as_sent_messages(doc, turn)):
        assert msgs[1]["content"] == BRIEF + " <SENTINEL>"


def test_the_seam_leaves_a_deep_research_step_and_a_case_law_turn_alone():
    for doc in (_doc(chat_mode="deep_research"), _doc(research_mode="case_law_only")):
        assert sr.worker_first_round_messages(doc, doc["turns"][0])[1]["content"] == BRIEF


def test_the_as_sent_rebuild_uses_the_recorded_revisions_function(monkeypatch):
    """A revision before (c) sent the brief alone; one after it, the block as
    that revision wrote it."""
    new_src = ('def with_lawyer_words(brief, question, research_mode, chat_mode=None):\n'
               '    return brief + " [REV " + question + "]"\n')

    def fake_file_at(rev, path):
        if path == sr.LAWYER_WORDS_PATH:
            return new_src if rev == "after" else ""
        return ""

    monkeypatch.setattr(sr, "_file_at", fake_file_at)
    monkeypatch.setattr(sr, "worker_prompt_and_tools_at", lambda rev, cfg: ("SYS", []))
    doc = _doc()
    turn = doc["turns"][0]
    assert sr.worker_as_sent_messages(doc, turn, at_rev="before")[1]["content"] == BRIEF
    assert sr.worker_as_sent_messages(doc, turn, at_rev="after")[1]["content"] == \
        BRIEF + f" [REV {Q17}]"


def test_a_turn_without_a_brief_still_falls_back_to_its_question():
    doc = _doc(brief="")
    assert sr.worker_first_round_messages(doc, doc["turns"][0])[1]["content"] == Q17
