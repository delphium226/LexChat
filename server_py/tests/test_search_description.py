"""FIX_PLAN P3.6: `description` kept in `search_legislation` rows, cut to a cap.

`_slim_search_results` used to strip `description` because it was large; it is
also where an instrument says what it commences or amends, with the date. It is
now kept, whitespace collapsed, cut at a word to `SEARCH_DESCRIPTION_CAP` (600)
and marked "...", and dropped where it has no letter. Two clauses of the
`[SEARCH SCOPE …]` block were written when no row carried one and would be false
or self-defeating beside it, so the block uses variants wherever a shown row has
a description, and keeps its old clauses byte for byte where none does.

The booked acceptance: (1) `description` survives slimming within the cap
(here); (2) Phase-1 summarisation calls unchanged over the stored results
(measured in batch 9 D's note: 0 of 6,521 re-run results cross the 8,000
characters they were summarised at; the worst case is pinned below).

All synthetic: "Widget" instruments, years 1899-1902.
"""
import json
import re

import pytest

from src.agent.provider_factory import set_request_provider_config
from src.agent.summarisation import SUMMARISE_THRESHOLD_CHARS
from src.agent.tools import lex
from src.agent.tools.lex import SEARCH_DESCRIPTION_CAP, _search_description, _slim_search_results
from src.utils import search_scope as ss
from src.utils.search_scope import legislation_search_note, section_search_note

CAP = SEARCH_DESCRIPTION_CAP
DATED = ("These Regulations bring sections 3 and 4 of the Widget Act 1901 into force on "
         "8 October 1901.")


def _row(i=1, description=None, series="ssi", title=None):
    r = {"uri": f"http://www.legislation.gov.uk/id/{series}/1901/{i}",
         "title": title or f"The Widget Regulations 1901 (No. {i})",
         "status": "revised", "year": 1901, "extent": [""]}
    if description is not None:
        r["description"] = description
    return r


def _long(n_words=200, word="widget"):
    return " ".join(f"{word}{i}" for i in range(n_words))


# ---------------------------------------------------------------------------
# 1. The slimmer: kept, within the cap, never cut mid-word
# ---------------------------------------------------------------------------

def test_the_cap_is_the_measured_one():
    assert CAP == 600


def test_a_description_under_the_cap_survives_whole():
    out = _slim_search_results({"results": [_row(description=DATED)], "total": 9})
    assert out["results"][0]["description"] == DATED


def test_a_long_description_is_cut_within_the_cap_and_marked():
    text = DATED + " " + _long()
    got = _search_description(text)
    assert len(got) <= CAP
    assert got.endswith("...")
    assert got.startswith(DATED)
    # Cut at a word: every word before the mark is a whole word of the source.
    body = got[:-3].split(" ")
    assert all(w in text.split(" ") for w in body), body[-1]


def test_a_cut_never_leaves_part_of_a_word_or_a_date():
    """A date cut to "8 Octo" is worse than no date."""
    lead = "x " * ((CAP - 30) // 2)
    text = lead + "into force on 8 October 1901 and later provisions on 1 April 1902."
    got = _search_description(text)
    assert len(got) <= CAP and got.endswith("...")
    tail = got[:-3].rstrip().split(" ")[-1]
    assert tail in text.split(" "), tail
    assert "Octo..." not in got and "Octobe..." not in got


@pytest.mark.parametrize("value", [None, "", "   ", ". . . . . . . .", "....", 12, ["a"], {"a": 1}])
def test_no_letter_no_key(value):
    """Dot leaders and blanks (586 stored rows) carry nothing: no key at all."""
    out = _slim_search_results({"results": [_row(description=value)], "total": 1})
    assert "description" not in out["results"][0]


def test_a_row_without_the_field_is_unchanged():
    base = {"results": [_row()], "total": 1}
    out = _slim_search_results(base)
    assert set(out["results"][0]) == {"legislation_id", "title", "url", "text_version",
                                       "year", "extent"}


def test_whitespace_is_collapsed():
    got = _search_description("These   Regulations\n\namend the\tWidget Order 1901.")
    assert got == "These Regulations amend the Widget Order 1901."


def test_the_cut_is_at_a_space_in_the_second_half_only():
    """One unbroken token longer than half the cap is cut hard rather than
    reduced to nothing."""
    text = "a " + "w" * (CAP * 2)
    got = _search_description(text)
    assert len(got) <= CAP and got.endswith("...")
    assert len(got) > CAP // 2


def test_the_sources_rail_is_unchanged():
    """`extract_sources` reads named keys only, so the lawyer's rail is byte-identical."""
    from src.agent.agent_shared import _extract_sources_from_tool
    acc = []
    slim = _slim_search_results({"results": [_row(description=DATED)], "total": 1})
    _extract_sources_from_tool("search_legislation", {}, json.dumps(slim), acc)
    assert acc and "description" not in acc[0]
    assert DATED not in json.dumps(acc)


# ---------------------------------------------------------------------------
# 2. Through the executor, as the Worker receives it
# ---------------------------------------------------------------------------

class _Resp:
    def __init__(self, body):
        self._b, self.status_code, self.text = body, 200, json.dumps(body)

    def json(self):
        return self._b

    def raise_for_status(self):
        return None


async def _run_search(monkeypatch, rows, cfg=None):
    from src.agent.tools import executor

    async def fake(client, method, url, name=None, **kw):
        return _Resp({"results": rows, "total": 141})

    monkeypatch.setattr(executor, "_request_with_retry", fake)
    set_request_provider_config(dict(cfg or {}))
    try:
        return await executor.execute_worker_tool("search_legislation", {"query": "widget"})
    finally:
        set_request_provider_config({})


@pytest.mark.asyncio
async def test_the_executor_hands_the_worker_the_description(monkeypatch):
    out = json.loads(await _run_search(monkeypatch, [_row(1, DATED), _row(2)]))
    assert out["results"][0]["description"] == DATED
    assert "description" not in out["results"][1]


@pytest.mark.asyncio
async def test_a_jurisdiction_filter_keeps_the_description(monkeypatch):
    out = json.loads(await _run_search(
        monkeypatch, [_row(1, DATED), _row(2, DATED, series="nisr")], {"_jurisdiction": "scotland"}))
    assert [r["legislation_id"] for r in out["results"]] == ["ssi/1901/1"]
    assert out["results"][0]["description"] == DATED


@pytest.mark.asyncio
async def test_five_long_rows_stay_under_the_default_summarise_threshold(monkeypatch):
    """Phase 1 must not start being summarised (the reason `description` was
    stripped). The worst realistic case: five rows, long titles, every
    description over the cap with curly quotes and dashes, which JSON escapes
    to six characters each. Every stored replay ran at 8,000 characters (the
    fallback; the dynamic context cache is cold there), and so does an Ollama
    model missing from `MODEL_LIST`."""
    desc = ("These Regulations amend the “Widget Order 1901” – the “principal Order” – "
            "and bring it into force on 8 October 1901. ") * 12
    rows = [_row(i, desc, title="The Widget (Miscellaneous Amendments and Transitional "
                                "Provisions) (No. %d) Regulations 1901 (revoked)" % i)
            for i in range(1, 6)]
    out = await _run_search(monkeypatch, rows)
    assert len(json.loads(out)["results"]) == 5
    assert len(out) < SUMMARISE_THRESHOLD_CHARS == 8_000, len(out)


# ---------------------------------------------------------------------------
# 3. The [SEARCH SCOPE] block: variants only where a row has a description
# ---------------------------------------------------------------------------

def _slim(described: bool, secondary: bool = True):
    rows = [_row(i, DATED if described else None, series="ssi" if secondary else "asp")
            for i in range(1, 4)]
    d = _slim_search_results({"results": rows, "total": 141})
    d.update(returned=3, total_matched=141, removed_by_filters=0)
    return d


def test_without_descriptions_the_block_is_byte_identical_to_before():
    note = legislation_search_note({"query": "widget"}, _slim(False))
    assert ss._ADJACENCY_CLAUSE in note
    assert ss._RELATION_ROUTE_CLAUSE in note
    assert ss._CURRENCY_CLAUSE in note
    assert ss._DESCRIPTION_CLAUSE not in note
    assert "`description`" not in note


def test_with_descriptions_the_false_sentence_goes_and_the_clause_comes():
    note = legislation_search_note({"query": "widget"}, _slim(True))
    # P2.3's sentence would be false beside a description quoting the powers.
    assert "These rows carry NO relationship data" not in note
    assert "nothing here states what any instrument was made under" not in note
    assert ss._ADJACENCY_CLAUSE_DESCRIBED in note
    # The route clause is about which rows came back, not what they say.
    assert "do NOT conclude anything about them from these rows" not in note
    assert ss._RELATION_ROUTE_CLAUSE_DESCRIBED in note
    assert "from which rows came back" in note
    # Currency is unchanged and stays true beside a description.
    assert ss._CURRENCY_CLAUSE in note
    assert ss._DESCRIPTION_CLAUSE in note
    assert note.index(ss._CURRENCY_CLAUSE) < note.index(ss._DESCRIPTION_CLAUSE)


def test_a_page_of_acts_with_descriptions_gets_no_adjacency_clause():
    note = legislation_search_note({"query": "widget"}, _slim(True, secondary=False))
    assert ss._ADJACENCY_CLAUSE_DESCRIBED not in note and ss._ADJACENCY_CLAUSE not in note
    assert ss._DESCRIPTION_CLAUSE in note


def test_the_description_clause_says_what_a_description_is_and_is_not():
    c = ss._DESCRIPTION_CLAUSE
    assert "own published summary, possibly cut short" in c
    assert "you may quote it, citing the instrument" in c
    assert "it is not the change record" in c
    assert "no evidence of current in-force status" in c
    assert "an enabling power it quotes still needs an ENABLING POWER block" in c


def test_the_section_block_is_untouched():
    note = section_search_note({"query": "widget", "legislation_id": "ssi/1901/1"},
                               {"results": [{"legislation_id": "ssi/1901/1", "number": "1",
                                             "text": "x", "url": "u"}], "returned": 1})
    assert ss._RELATION_ROUTE_CLAUSE in note
    assert ss._DESCRIPTION_CLAUSE not in note


def test_the_empty_branch_is_untouched():
    d = _slim_search_results({"results": [], "total": 0})
    d.update(returned=0, total_matched=0, removed_by_filters=0)
    note = legislation_search_note({"query": "widget"}, d)
    assert ss._DESCRIPTION_CLAUSE not in note


@pytest.mark.asyncio
async def test_the_worker_receives_the_description_and_the_clause(monkeypatch):
    """Asserted on what `run_worker_tool` returns (P1.6's lesson)."""
    from src.agent import agent_shared
    from src.agent.tools import executor

    async def fake(client, method, url, name=None, **kw):
        return _Resp({"results": [_row(1, DATED), _row(2)], "total": 141})

    monkeypatch.setattr(executor, "_request_with_retry", fake)
    set_request_provider_config({"_provider": "openrouter", "_research_mode": "legislation_only",
                                 "model": "test-model"})
    try:
        out = await agent_shared.run_worker_tool("search_legislation", {"query": "widget"},
                                                 "q", None, "m")
    finally:
        set_request_provider_config({})
    assert DATED in out
    assert ss._DESCRIPTION_CLAUSE in out
    assert out.index(ss._DESCRIPTION_CLAUSE) < out.index("[NEXT STEP")


def test_the_new_clauses_trip_no_detector():
    """A Worker can echo a tool-result sentence. Screened as
    `test_footer_trips_no_detector` screens the footer. `NEGATIVE_EXPLAINED`
    is not asserted: the adjacency clause's "search for" already matched it
    before P3.6, unchanged. No bracket either: the clauses ride inside a
    `[SEARCH SCOPE …]` block, and a bracket stops the strippers."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools.replay_report import (
        HALT_AS_TIMEOUT, HALT_LITERAL, HALT_PARAPHRASE, IN_FORCE_CLAIM, NEG_ASSERTED,
        NEG_BLAMED_INDEX, NEG_BLAMED_USER, NEG_LIMITS, NEG_TERMS, NOT_FOUND, OPENER_VOCAB,
        _CMC_CONTEXT, _CMC_DENIED, _CUR_DATED, _CUR_DISCLOSED, _currency_asserted, _sentences,
        _without_footer, derivation_claims, negcurrency_claim, sched_unit_clauses,
    )
    unit_rx = re.compile(r"\b(?:schedules?|annex(?:es)?)\b", re.I)
    for text in (ss._ADJACENCY_CLAUSE_DESCRIBED, ss._RELATION_ROUTE_CLAUSE_DESCRIBED,
                 ss._DESCRIPTION_CLAUSE):
        assert "[" not in text and "]" not in text, text
        assert derivation_claims(text)[0] == [], text
        assert _without_footer(text) == text.strip()
        for rx in (NEG_ASSERTED, NOT_FOUND, NEG_TERMS, NEG_LIMITS, NEG_BLAMED_INDEX,
                   NEG_BLAMED_USER, IN_FORCE_CLAIM, _CUR_DISCLOSED, _CUR_DATED, HALT_LITERAL,
                   HALT_PARAPHRASE, HALT_AS_TIMEOUT, OPENER_VOCAB):
            assert not rx.search(text), (rx.pattern[:40], text)
        assert not [c for c, _, _ in sched_unit_clauses(text, unit_rx) if c], text
        for s in _sentences(text):
            assert not (_CMC_CONTEXT.search(s) and _CMC_DENIED.search(s)), s
            assert not _currency_asserted(s), s
            assert negcurrency_claim(s)[0] is None, s


def test_a_described_block_stays_bounded():
    """The block grows where it applies (batch 9 D: 268 to 363 characters); a
    long query on a page of instruments must still stay under 2,500."""
    note = legislation_search_note({"query": "x" * 5000}, _slim(True))
    assert len(note) < 2500, len(note)
