"""P3.14: the quick-lookup (conversational) Worker is told which research
filters are active.

`get_worker_system_prompt` returns that Worker's prompt from an early return,
before the ACTIVE RESEARCH FILTERS block is appended, so the research Workers
were told of the lawyer's filters and the quick-lookup one never was. The
filters were always enforced; the Worker could not know that a filter, not the
index or the law, narrowed its search (6357, Acts only: an SSI "the legislation
index does not hold").

The note goes in the Worker's USER message, not its system prompt: P2.4
measured a block appended to this Worker's system prompt moving its reports to
bullets and costing case-law links (Session 14). Pinned here: every Worker a
filtered request can reach hears of the filters (the dispatch branches, the
`test_suggestions.py` pattern); the quick-lookup system prompt is byte-identical
with and without filters; only filters that can exclude something are named;
each Worker hears only of the filters on its own tools; the run sends it; the
seam builds it with the product's own function; and the note trips none of the
answer detectors, since a Worker can echo it.
"""

import asyncio
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import prompts  # noqa: E402
from src.agent import agent_core  # noqa: E402
from src.agent.agent_core import run_worker_agent  # noqa: E402
from src.agent.provider_factory import set_request_provider_config  # noqa: E402
from src.agent.tools.schemas import is_quick_lookup_worker  # noqa: E402
from src.prompts import (  # noqa: E402
    QUICK_LOOKUP_FILTERS_LABEL,
    get_worker_system_prompt,
    quick_lookup_filter_note,
)
from src.utils.lawyer_words import with_lawyer_words  # noqa: E402
from tools import seam_replay as sr  # noqa: E402

TODAY = date(2026, 11, 2)
LEG_MODES = ["legislation_only", "legislation_and_case_law", "case_law_only"]
ALL_MODES = LEG_MODES + ["parliamentary_records", "westminster_records"]
CHAT_MODES = ["conversational", "research", "deep_research", None]
# One filter of every kind, each able to exclude something.
BITING = {"_jurisdiction": "scotland", "_legislation_type": "primary",
          "_year_from": 2000, "_year_to": 2020,
          "_date_from": "2010-01-01", "_date_to": "2020-12-31"}
HEAD = f"\n\n[{QUICK_LOOKUP_FILTERS_LABEL} — "


@pytest.fixture(autouse=True)
def _clean_request_state():
    yield
    set_request_provider_config({})


def _cfg(chat_mode, research_mode, **filters):
    cfg = {"_chat_mode": chat_mode, "_research_mode": research_mode}
    cfg.update(filters)
    return cfg


# --- 1. the dispatch: every Worker a filtered request reaches hears of it ----


@pytest.mark.parametrize("research_mode", LEG_MODES)
@pytest.mark.parametrize("chat_mode", CHAT_MODES)
def test_every_legislation_bot_worker_is_told_of_a_filter(research_mode, chat_mode):
    """The research Workers by the system-prompt block (unchanged), the
    quick-lookup Worker by the note; never both, never neither."""
    cfg = _cfg(chat_mode, research_mode, **BITING)
    system = get_worker_system_prompt(research_mode, cfg)
    note = quick_lookup_filter_note(research_mode, cfg, TODAY)
    in_system = "ACTIVE RESEARCH FILTERS" in system
    assert in_system != bool(note)
    assert bool(note) == is_quick_lookup_worker(research_mode, chat_mode)


@pytest.mark.parametrize("research_mode", ["parliamentary_records", "westminster_records"])
@pytest.mark.parametrize("chat_mode", CHAT_MODES)
def test_the_parliament_bots_keep_their_own_block_and_get_no_note(research_mode, chat_mode):
    cfg = _cfg(chat_mode, research_mode, _date_from="2022-01-01", _date_to="2023-01-01",
               _pt_record_type="committee")
    assert "ACTIVE RESEARCH FILTERS" in get_worker_system_prompt(research_mode, cfg)
    assert quick_lookup_filter_note(research_mode, cfg, TODAY) == ""


@pytest.mark.parametrize("research_mode", LEG_MODES)
def test_the_quick_lookup_system_prompt_is_byte_identical_with_filters(research_mode):
    """The lever is the user message: Session 14's format shift came from a
    block appended to this system prompt."""
    plain = get_worker_system_prompt(research_mode, _cfg("conversational", research_mode))
    filtered = get_worker_system_prompt(research_mode,
                                        _cfg("conversational", research_mode, **BITING))
    assert plain == filtered


# --- 2. what is named ----------------------------------------------------------


@pytest.mark.parametrize("research_mode", LEG_MODES)
def test_no_filter_no_note(research_mode):
    assert quick_lookup_filter_note(research_mode, _cfg("conversational", research_mode),
                                    TODAY) == ""
    assert quick_lookup_filter_note(research_mode, None, TODAY) == ""
    assert quick_lookup_filter_note(research_mode, {}, TODAY) == ""


@pytest.mark.parametrize("filters", [
    {"_year_to": 2026},                       # the replay harness's recorded bound
    {"_year_to": 2030},
    {"_date_to": "2026-11-02"},
    {"_date_to": "2027-01-01"},
    {"_year_to": 2026, "_date_to": "2026-12-31", "_current_only": True, "_court": "uksc"},
])
@pytest.mark.parametrize("research_mode", LEG_MODES)
def test_an_inert_filter_is_not_named(filters, research_mode):
    """An upper bound at or after today excludes nothing; P1.2's and P4.4's
    retired filters were never applied."""
    assert quick_lookup_filter_note(research_mode,
                                    _cfg("conversational", research_mode, **filters),
                                    TODAY) == ""


def test_the_inert_test_follows_the_date_it_is_given():
    cfg = _cfg("conversational", "legislation_only", _year_to=2026)
    assert quick_lookup_filter_note("legislation_only", cfg, date(2026, 11, 2)) == ""
    note = quick_lookup_filter_note("legislation_only", cfg, date(2027, 1, 1))
    assert "legislation up to 2026 only" in note


def test_the_whole_note_for_the_6357_filters():
    cfg = _cfg("conversational", "legislation_only", _jurisdiction="scotland",
               _legislation_type="primary", _year_to=2026)
    assert quick_lookup_filter_note("legislation_only", cfg, TODAY) == (
        "\n\n[RESEARCH FILTERS — set by the lawyer and applied by the system to every search "
        "you make: legislation searches return Acts only (primary legislation); legislation "
        "search results whose stated extent leaves out Scotland are removed (most results "
        "state no extent and are kept, so a result is not thereby shown to apply in "
        "Scotland). Something the brief asks about that your searches do not return may "
        "have been left out by these filters: if so, say that the filters left it out, "
        "never that it is unavailable or does not exist.]")


@pytest.mark.parametrize("lt,phrase", [
    ("primary", "Acts only (primary legislation)"),
    ("secondary", "statutory instruments only (secondary legislation)"),
    ("draft", "draft statutory instruments only"),
])
def test_each_legislation_type(lt, phrase):
    note = quick_lookup_filter_note("legislation_only",
                                    _cfg("conversational", "legislation_only",
                                         _legislation_type=lt), TODAY)
    assert f"legislation searches return {phrase}." in note


@pytest.mark.parametrize("yf,yt,phrase", [
    (2000, 2020, "legislation from 2000 to 2020 only"),
    (2000, None, "legislation from 2000 onwards only"),
    (2000, 2026, "legislation from 2000 onwards only"),   # the inert end dropped
    (None, 2019, "legislation up to 2019 only"),
])
def test_each_year_window(yf, yt, phrase):
    note = quick_lookup_filter_note("legislation_only",
                                    _cfg("conversational", "legislation_only",
                                         _year_from=yf, _year_to=yt), TODAY)
    assert phrase in note


@pytest.mark.parametrize("df,dt,phrase", [
    ("2010-01-01", "2020-12-31", "judgments dated 2010-01-01 to 2020-12-31 only"),
    ("2010-01-01", None, "judgments dated from 2010-01-01 only"),
    ("2010-01-01", "2030-01-01", "judgments dated from 2010-01-01 only"),
    (None, "2019-06-30", "judgments dated up to 2019-06-30 only"),
])
def test_each_case_law_date_window(df, dt, phrase):
    note = quick_lookup_filter_note("case_law_only",
                                    _cfg("conversational", "case_law_only",
                                         _date_from=df, _date_to=dt), TODAY)
    assert phrase in note


def test_each_worker_hears_only_of_the_filters_on_its_own_tools():
    leg = quick_lookup_filter_note("legislation_only",
                                   _cfg("conversational", "legislation_only", **BITING), TODAY)
    case = quick_lookup_filter_note("case_law_only",
                                    _cfg("conversational", "case_law_only", **BITING), TODAY)
    both = quick_lookup_filter_note("legislation_and_case_law",
                                    _cfg("conversational", "legislation_and_case_law",
                                         **BITING), TODAY)
    assert "legislation searches" in leg and "case-law" not in leg
    assert "case-law searches" in case and "legislation" not in case
    assert "legislation searches" in both and "case-law searches" in both
    # A legislation filter alone says nothing to the case-law Worker.
    assert quick_lookup_filter_note("case_law_only",
                                    _cfg("conversational", "case_law_only",
                                         _jurisdiction="wales"), TODAY) == ""


@pytest.mark.parametrize("jur,label", [
    ("england_and_wales", "England and Wales"),
    ("wales", "Wales"),
    ("northern_ireland", "Northern Ireland"),
])
def test_another_territory_overrides_the_scotland_default(jur, label):
    """P3.4's note on the row: the prompt's default is Scotland, so a brief
    naming no jurisdiction under another territory's filter needs the filter's
    territory."""
    note = quick_lookup_filter_note("legislation_only",
                                    _cfg("conversational", "legislation_only",
                                         _jurisdiction=jur), TODAY)
    assert f"stated extent leaves out {label} are removed" in note
    assert f"where the brief names no jurisdiction, answer for {label}." in note


def test_scotland_is_the_default_already_and_gets_no_override():
    note = quick_lookup_filter_note("legislation_only",
                                    _cfg("conversational", "legislation_only",
                                         _jurisdiction="scotland"), TODAY)
    assert "names no jurisdiction" not in note


def test_uk_wide_says_what_it_leaves_out():
    note = quick_lookup_filter_note("legislation_only",
                                    _cfg("conversational", "legislation_only",
                                         _jurisdiction="uk_wide"), TODAY)
    assert "kept only where their stated extent is the United Kingdom" in note
    assert "names no jurisdiction" not in note


def test_the_note_names_no_control_by_hand():
    """P4.1: a prompt names a UI control only through `utils/mode_change`."""
    note = quick_lookup_filter_note("legislation_and_case_law",
                                    _cfg("conversational", "legislation_and_case_law",
                                         **BITING), TODAY)
    for word in ("Research mode", "Filters button", "mode selector", "switch"):
        assert word not in note


def test_the_note_never_raises():
    cfg = _cfg("conversational", "legislation_only", _year_to="not a year")
    assert quick_lookup_filter_note("legislation_only", cfg, TODAY) == ""
    assert quick_lookup_filter_note("legislation_only", "not a dict", TODAY) == ""


# --- 3. the detectors -----------------------------------------------------------


def _every_note():
    out = []
    for rm in LEG_MODES:
        for extra in ({}, {"_jurisdiction": "england_and_wales"}, {"_jurisdiction": "uk_wide"},
                      {"_legislation_type": "secondary"}, {"_legislation_type": "draft"}):
            out.append(quick_lookup_filter_note(rm, _cfg("conversational", rm,
                                                          **{**BITING, **extra}), TODAY))
    return [n for n in out if n]


def test_the_note_trips_no_answer_detector():
    """A Worker can echo the note into its report, and the Manager into the
    answer: it must not enrol a turn as a negative, a blamed citation, an
    in-force claim or a derivation claim (P2.2's twelfth instrument error)."""
    from tools.replay_report import (IN_FORCE_CLAIM, NEG_ASSERTED, NEG_BLAMED_INDEX,
                                     NEG_BLAMED_USER, derivation_claims)
    notes = _every_note()
    assert len(notes) == 15
    for note in notes:
        assert not NEG_ASSERTED.search(note), NEG_ASSERTED.search(note)
        assert not NEG_BLAMED_USER.search(note)
        # P2.2's credit for blaming the index: an echo must not earn it.
        assert not NEG_BLAMED_INDEX.search(note), NEG_BLAMED_INDEX.search(note)
        assert not IN_FORCE_CLAIM.search(note)
        assert derivation_claims(note)[0] == []


# --- 4. the run sends it ------------------------------------------------------


def _run(cfg_extra, research_mode="legislation_only", chat_mode="conversational",
         question="What does the Act say?"):
    cfg = {"_provider": "openrouter", "_research_mode": research_mode,
           "_chat_mode": chat_mode, "model": "test-model", "_cache_key_query": question}
    cfg.update(cfg_extra)
    set_request_provider_config(cfg)
    seen = {}

    async def loop(messages, model, cancel_event, num_ctx, tools, tool_exec, on_chunk=None,
                   **kw):
        seen["system"] = messages[0]["content"]
        seen["message"] = messages[1]["content"]
        return {"role": "assistant", "content": "Report."}

    asyncio.run(run_worker_agent(loop, lambda *a, **k: None, "Find it.", "test-model",
                                 None, 0))
    return cfg, seen


def test_the_quick_lookup_worker_gets_the_note_after_the_lawyers_words():
    cfg, seen = _run({"_jurisdiction": "england_and_wales", "_year_to": 2026})
    head = with_lawyer_words("Find it.", "What does the Act say?", "legislation_only",
                             "conversational")
    assert seen["message"] == head + quick_lookup_filter_note("legislation_only", cfg)
    assert seen["message"].startswith(head + HEAD)
    assert seen["message"].endswith("or does not exist.]")
    assert "ACTIVE RESEARCH FILTERS" not in seen["system"]


@pytest.mark.parametrize("kw", [
    {"cfg_extra": {}},                                                  # no filter
    {"cfg_extra": {"_year_to": 2026}},                                  # an inert one
    {"cfg_extra": {"_jurisdiction": "scotland"}, "chat_mode": "research"},
    {"cfg_extra": {"_jurisdiction": "scotland"}, "chat_mode": "deep_research"},
])
def test_elsewhere_the_message_is_unchanged(kw):
    rm = "legislation_only"
    cfg, seen = _run(**kw)
    question = "What does the Act say?"
    assert seen["message"] == with_lawyer_words("Find it.", question, rm,
                                                cfg.get("_chat_mode"))


# --- 5. the seam builds it with the product's function --------------------------


def _doc(filters, chat_mode="conversational", research_mode="legislation_only"):
    return {"session_id": "6357", "rep": 1, "started_at": "2026-09-18T10:00:00",
            "filters": {"research_mode": research_mode, **filters},
            "turns": [{"turn": 1, "question": "Q?", "chat_mode": chat_mode,
                       "research_mode": research_mode,
                       "audit": {"delegations": [{"brief": "Find it.", "tools": [
                           {"name": "search_legislation", "args": {"query": "x"},
                            "final_result": "R1", "started_at": 1.0,
                            "duration_s": 1.0}]}]}}]}


def test_the_seam_sends_what_the_product_sends():
    doc = _doc({"jurisdiction": "scotland", "legislation_type": "primary", "year_to": 2026})
    turn = doc["turns"][0]
    cfg = sr._cfg_for(doc, turn)
    want = (with_lawyer_words("Find it.", "Q?", "legislation_only", "conversational")
            + quick_lookup_filter_note("legislation_only", cfg))
    assert "Acts only" in want
    for msgs in (sr.worker_first_round_messages(doc, turn), sr.worker_messages(doc, turn),
                 sr.worker_as_sent_messages(doc, turn)):
        assert msgs[1]["content"] == want
    # the before side of P3.14
    dg = turn["audit"]["delegations"][0]
    assert sr.worker_user_message(doc, turn, dg, filter_note=False) == with_lawyer_words(
        "Find it.", "Q?", "legislation_only", "conversational")


def test_the_seam_carries_the_case_law_dates_into_the_config():
    doc = _doc({"date_from": "2010-01-01", "date_to": "2020-12-31"},
               research_mode="case_law_only")
    cfg = sr._cfg_for(doc, doc["turns"][0])
    assert (cfg["_date_from"], cfg["_date_to"]) == ("2010-01-01", "2020-12-31")
    msg = sr.worker_first_round_messages(doc, doc["turns"][0])[1]["content"]
    assert msg.endswith(quick_lookup_filter_note("case_law_only", cfg))
    assert "judgments dated 2010-01-01 to 2020-12-31 only" in msg


def test_the_as_sent_date_decides_what_is_inert():
    """`--date` pins the note's today as it pins the prompt's date line."""
    doc = _doc({"year_to": 2026})
    turn = doc["turns"][0]
    on = sr.worker_as_sent_messages(doc, turn, on_date=date(2027, 3, 1))[1]["content"]
    assert "legislation up to 2026 only" in on
    off = sr.worker_as_sent_messages(doc, turn, on_date=date(2026, 9, 18))[1]["content"]
    assert QUICK_LOOKUP_FILTERS_LABEL not in off


def test_the_as_sent_rebuild_uses_the_revisions_own_note(monkeypatch):
    """A revision before P3.14 sent no note; one after it, its own."""
    new_src = ('def quick_lookup_filter_note(research_mode, cfg, today=None):\n'
               '    return " [REV NOTE " + str(cfg.get("_jurisdiction")) + "]"\n')

    def fake_file_at(rev, path):
        if path == "server_py/src/prompts.py":
            return new_src if rev == "after" else "def something_else(): pass\n"
        return ""

    monkeypatch.setattr(sr, "_file_at", fake_file_at)
    monkeypatch.setattr(sr, "worker_prompt_and_tools_at", lambda rev, cfg: ("SYS", []))
    doc = _doc({"jurisdiction": "scotland"})
    turn = doc["turns"][0]
    assert sr.worker_as_sent_messages(doc, turn, at_rev="before")[1]["content"] == "Find it."
    assert sr.worker_as_sent_messages(doc, turn, at_rev="after")[1]["content"] == \
        "Find it. [REV NOTE scotland]"


def test_the_seam_calls_the_product_function_not_a_copy(monkeypatch):
    monkeypatch.setattr(prompts, "quick_lookup_filter_note", lambda *a, **k: " <SENTINEL>")
    doc = _doc({"jurisdiction": "scotland"})
    turn = doc["turns"][0]
    head = with_lawyer_words("Find it.", "Q?", "legislation_only", "conversational")
    assert sr.worker_first_round_messages(doc, turn)[1]["content"] == head + " <SENTINEL>"


def test_agent_core_imports_the_product_function():
    assert agent_core.quick_lookup_filter_note is prompts.quick_lookup_filter_note
