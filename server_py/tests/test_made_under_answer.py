"""FIX_PLAN P3.51 / P3.52, fix A2 (Session 52): the made-under record's
instruments for a section the conversational answer cites, listed at the answer
seam (`utils/made_under_answer.py`), and P3.51's section-family block keyed on
a section a returned provision inserts into another Act."""
from __future__ import annotations

import asyncio
import json

import pytest

from src.agent import agent_shared
from src.agent.provider_factory import set_request_provider_config
from src.services import made_under_store as store
from src.utils import made_under as mu
from src.utils import made_under_answer as mua

ACT = "ukpga/1987/26"
ACT_T = "Housing (Scotland) Act 1987"
ORDER = ("section/33A", "ssi/2022/356",
         "The Homeless Persons (Suspension of Referrals between Local Authorities) (Scotland) "
         "Order 2022", ACT_T, None, "2026-10-10")
DECISIONS = ("section/33", "uksi/1998/1603",
             "The Homelessness (Decisions on Referrals) (Scotland) Order 1998", ACT_T, None,
             "2026-10-10")
S29 = [
    ("section/29", "ssi/2004/489", "The Homeless Persons (Unsuitable Accommodation) (Scotland) "
     "Order 2004", ACT_T, json.dumps({"state": "wholly", "whole": [
         {"type": "revoked", "by": "ssi/2014/243", "dates": [{"date": "2014-12-01"}]}]}), "2026-10-10"),
    ("section/29", "ssi/2014/243", "The Homeless Persons (Unsuitable Accommodation) (Scotland) "
     "Order 2014", ACT_T, json.dumps({"state": "partly", "partial": {"count": 1}}), "2026-10-10"),
    ("section/29", "ssi/2017/273", "The Homeless Persons (Unsuitable Accommodation) (Scotland) "
     "Amendment Order 2017", ACT_T, None, "2026-10-10"),
    ("section/29", "ssi/2021/222", "The Homeless Persons (Unsuitable Accommodation) (Scotland) "
     "(Modification and Revocation) (Coronavirus) Order 2021", ACT_T, None, "2026-10-10"),
]
S31 = [("section/31", "ssi/2002/414", "The Homeless Persons Advice and Assistance (Scotland) "
        "Regulations 2002", ACT_T, None, "2026-10-10")]
ROWS = {ACT: [ORDER, DECISIONS] + S29 + S31}
TITLES = {ACT: ACT_T, "asp/2003/10": "Homelessness etc. (Scotland) Act 2003",
          "asp/2001/10": "Housing (Scotland) Act 2001"}


# --- what the answer cites ---------------------------------------------------------

@pytest.mark.parametrize("answer, cited", [
    (f"Under [s.33A](http://www.legislation.gov.uk/{ACT}/section/33A) Ministers may ...",
     [(ACT, "33", "A")]),
    ("Under s.33A of the 1987 Act Ministers may ...", [(ACT, "33", "A")]),
    ("Under section 29(3) and (4) of the Housing (Scotland) Act 1987 they may ...",
     [(ACT, "29", "")]),
    ("Sections 31 and 33A of the 1987 Act apply.", [(ACT, "31", ""), (ACT, "33", "A")]),
    # "the 2001 Act" is one Act of the turn's; "the 1999 Act" none; no Act named, nothing
    ("Under section 5(3) of the 2001 Act ...", [("asp/2001/10", "5", "")]),
    ("Under section 5 of the 1999 Act ...", []),
    ("Under section 33 a referral may be made.", []),
])
def test_cited_sections(answer, cited):
    assert mua.cited_sections(answer, TITLES) == cited


def test_a_year_two_acts_of_the_turn_share_is_not_resolved():
    titles = {**TITLES, "asp/2001/2": "Transport (Scotland) Act 2001"}
    assert mua.cited_sections("Under section 38 of the 2001 Act ...", titles) == []
    assert mua.cited_sections("Under section 38 of the Transport (Scotland) Act 2001 ...",
                              titles) == [("asp/2001/2", "38", "")]


# --- the lines ------------------------------------------------------------------------

def _lines(answer):
    return mua.plan_made_under_lines(answer, mua.cited_sections(answer, TITLES), ROWS,
                                     today="2026-10-30")


def test_a_section_cited_without_a_letter_takes_its_lettered_sections():
    lines = _lines("Under s.33 of the 1987 Act a referral may be made.")
    assert lines == [
        f"s.33 of the {ACT_T}: The Homelessness (Decisions on Referrals) (Scotland) Order 1998 "
        "(SI 1998/1603), made under s.33; The Homeless Persons (Suspension of Referrals between "
        "Local Authorities) (Scotland) Order 2022 (SSI 2022/356), made under s.33A."]


def test_a_lettered_section_takes_its_own_instruments_only():
    assert _lines("Under s.33A of the 1987 Act ...") == [
        f"s.33A of the {ACT_T}: The Homeless Persons (Suspension of Referrals between Local "
        "Authorities) (Scotland) Order 2022 (SSI 2022/356), made under s.33A."]


@pytest.mark.parametrize("named", ["SSI 2022/356", "ssi/2022/356",
                                   "the Homeless Persons (Suspension of Referrals between Local "
                                   "Authorities) (Scotland) Order 2022"])
def test_an_instrument_the_answer_names_is_not_listed(named):
    assert _lines(f"Under s.33A of the 1987 Act, by {named}, ...") == []


def test_whole_revocations_are_left_out_and_counted_and_a_partial_one_marked():
    (line,) = _lines("Under s.29 of the 1987 Act ...")
    assert line.startswith(f"s.29 of the {ACT_T}: The Homeless Persons (Unsuitable "
                           "Accommodation) (Scotland) Order 2014 (SSI 2014/243; recorded on "
                           "legislation.gov.uk as revoked in part), made under s.29; ")
    assert "(SSI 2017/273), made under s.29; " in line and "(SSI 2021/222), made under s.29" in line
    assert line.endswith("(1 more recorded on legislation.gov.uk as revoked in whole, not listed).")
    assert "2004" not in line


def test_a_family_larger_than_the_line_gets_no_line():
    rows = {ACT: S29 + [("section/29", f"ssi/2023/{i}", f"Order 2023 No. {i}", ACT_T, None,
                         "2026-10-10") for i in range(1, 3)]}
    answer = "Under s.29 of the 1987 Act ..."
    assert mua.plan_made_under_lines(answer, mua.cited_sections(answer, TITLES), rows,
                                     today="2026-10-30") == []


def test_lines_follow_the_answer_and_are_capped():
    lines = _lines("Under s.29, s.31, s.33 and s.33A of the 1987 Act ... and s.31 again.")
    assert [ln.split(":")[0] for ln in lines] == [
        f"s.29 of the {ACT_T}", f"s.31 of the {ACT_T}", f"s.33 of the {ACT_T}"]
    rows = {ACT: ROWS[ACT] + [("section/7", "ssi/2009/7", "The Seven Order 2009", ACT_T, None,
                                "2026-10-10")]}
    answer = "Under s.7, s.29, s.31 and s.33 of the 1987 Act."
    many = mua.plan_made_under_lines(answer, mua.cited_sections(answer, TITLES), rows,
                                     today="2026-10-30")
    assert len(many) == mua.MAX_LINES and many[0].startswith(f"s.7 of the {ACT_T}")


@pytest.mark.parametrize("answer, cited", [
    # the Act placed last on the line
    ("Under section 31(2) of the 1987 Act an authority may refer the applicant under "
     "section 33 if they have a local connection.", [(ACT, "31", ""), (ACT, "33", "")]),
    (f"Under [s.31](http://www.legislation.gov.uk/{ACT}/section/31) it may refer under s.33A.",
     [(ACT, "31", ""), (ACT, "33", "A")]),
    # another Act named between, a new line, or too far away: not read
    ("Under section 31 of the 1987 Act and the Housing (Scotland) Act 2001 it may refer under "
     "section 33.", [(ACT, "31", "")]),
    ("Under section 31 of the 1987 Act.\nIt may refer under section 33.", [(ACT, "31", "")]),
    ("Under section 31 of the 1987 Act " + "x " * 140 + "under section 33.", [(ACT, "31", "")]),
])
def test_a_section_named_without_its_act(answer, cited):
    assert mua.cited_sections(answer, TITLES) == cited


def test_one_instrument_is_listed_once():
    lines = _lines("Under s.33 and s.33A of the 1987 Act ...")
    assert sum(ln.count("SSI 2022/356") for ln in lines) == 1


# --- the seam ---------------------------------------------------------------------------

@pytest.fixture
def _record(monkeypatch):
    calls = []

    async def rows(act, bases):
        calls.append((act, list(bases)))
        return [r for r in ROWS.get(act, []) if r[0].split("/")[1].rstrip("ABC") in bases], {}

    monkeypatch.setitem(store._STATE, "available", True)
    monkeypatch.setattr(store, "section_family_rows", rows)
    return calls


ANSWER = "Ministers may suspend referrals under s.33A of the 1987 Act."
SOURCES = [{"_lid": ACT, "title": ACT_T}]


def test_the_block_goes_at_the_end_and_once(_record):
    out, n = asyncio.run(mua.list_made_under_for_answer(ANSWER, SOURCES))
    assert n == 1 and out.startswith(ANSWER + "\n\n" + mua.MADE_UNDER_ANSWER_HEAD)
    assert out.endswith("(SSI 2022/356), made under s.33A.")
    calls = len(_record)
    assert asyncio.run(mua.list_made_under_for_answer(out, SOURCES)) == (out, 0)
    assert len(_record) == calls          # the block's heading is seen; no record read


def test_nothing_to_list_is_byte_identical(_record):
    for answer in ("No section is cited here.", "Under s.40 of the 1987 Act ...", ""):
        assert asyncio.run(mua.list_made_under_for_answer(answer, SOURCES)) == (answer, 0)


def test_no_database_until_the_record_is_loaded(monkeypatch):
    monkeypatch.setitem(store._STATE, "available", False)
    touched = []

    async def rows(*a):
        touched.append(a)
        return [ORDER], {}
    monkeypatch.setattr(store, "section_family_rows", rows)
    assert asyncio.run(mua.list_made_under_for_answer(ANSWER, SOURCES)) == (ANSWER, 0)
    assert touched == []


def test_a_failure_returns_the_answer_unchanged(_record, monkeypatch):
    monkeypatch.setattr(mua, "plan_made_under_lines", lambda *a, **k: 1 / 0)
    assert asyncio.run(mua.list_made_under_for_answer(ANSWER, SOURCES)) == (ANSWER, 0)


@pytest.fixture
def _cfg():
    def set_(chat_mode, research_mode="legislation_only"):
        set_request_provider_config({
            "_provider": "openrouter", "_research_mode": research_mode,
            "_chat_mode": chat_mode, "model": "test-model", "_tool_memo_enabled": False})
    yield set_
    set_request_provider_config({})


def _manager(answer):
    async def manager(messages, model, cancel_event, num_ctx, tools, tool_executor,
                      on_chunk=None, **kw):
        await tool_executor("delegate_research", {"query": "q"})
        return {"role": "assistant", "content": answer}
    return manager


async def _worker(query, model, cancel_event, num_ctx, on_chunk, **kw):
    return {"content": "Report.", "sources": [], "searches": [],
            "retrieved_sources": SOURCES}


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["legislation_only", "legislation_and_case_law"])
async def test_the_conversational_answer_gets_the_list(_cfg, _record, mode):
    from src.agent.agent_core import process_user_request
    _cfg("conversational", mode)
    final = await process_user_request(_manager(ANSWER), _worker,
                                       [{"role": "user", "content": "q"}], "test-model", None, None, 0)
    assert mua.MADE_UNDER_ANSWER_HEAD in final["content"]
    assert "(SSI 2022/356), made under s.33A." in final["content"]


@pytest.mark.asyncio
@pytest.mark.parametrize("chat, mode", [("research", "legislation_only"),
                                        ("conversational", "case_law_only"),
                                        ("conversational", "parliamentary_records")])
async def test_every_other_path_is_left_alone(_cfg, _record, chat, mode):
    from src.agent.agent_core import process_user_request
    _cfg(chat, mode)
    final = await process_user_request(_manager(ANSWER), _worker,
                                       [{"role": "user", "content": "q"}], "test-model", None, None, 0)
    assert mua.MADE_UNDER_ANSWER_HEAD not in final["content"]


# --- P3.51's block: a section a returned provision inserts -------------------------------

INSERTING = {"legislation_id": "asp/2003/10", "number": "8",
             "url": "http://www.legislation.gov.uk/id/asp/2003/10/section/8",
             "text": "Section 8) **Power to modify section 33 of the 1987 Act**\nAfter section 33 "
                     "(referral of application to another local authority) of the 1987 Act "
                     "insert— \n\nSection 33A) **Power to modify section 33**\n\n1) The "
                     "Scottish Ministers may by order ..."}
PLAIN_ROW = {"legislation_id": "asp/2003/10", "number": "9",
             "url": "http://www.legislation.gov.uk/id/asp/2003/10/section/9",
             "text": "Section 9) In section 29 of the 1987 Act, in subsection (1) insert (c)."}


def _search(*rows):
    return json.dumps({"results": list(rows), "returned": len(rows)})


@pytest.mark.parametrize("text, found", [
    (INSERTING["text"], [("year", "1987", "33", "33A", "s.8 of asp/2003/10")]),
    ("After section 2 of the Transport (Scotland) Act 2001 insert—\nSection 2A) **X**",
     [("title", "Transport (Scotland) Act 2001", "2", "2A", "s.8 of asp/2003/10")]),
    (PLAIN_ROW["text"], []),                                   # no inserted section heading
    ("Section 33A) **Power** inserted somewhere", []),         # no "insert ... Section"
    ("insert—\nSection 4A) **X**", []),                     # no Act named before it
])
def test_inserted_sections(text, found):
    assert mu.inserted_sections(_search({**INSERTING, "text": text})) == found


@pytest.fixture
def _block_record(monkeypatch):
    calls = []

    async def rows(act, bases):
        calls.append(("rows", act, list(bases)))
        return [r for r in ROWS.get(act, []) if r[0].split("/")[1].rstrip("ABC") in bases], \
            {"label": "SSIs", "statement": "SSIs 1999 to 2026."}

    async def amended(kind, ref, provision):
        calls.append(("amended", kind, ref, provision))
        return ACT if (kind, ref, provision) == ("year", "1987", "section/33A") else None

    monkeypatch.setattr(store, "section_family_rows", rows)
    monkeypatch.setattr(store, "amended_act_id", amended)
    return calls


def test_an_inserted_section_is_keyed_on_the_amended_act(_block_record):
    block, entries = asyncio.run(agent_shared.made_under_sections_note(
        "search_legislation_sections", _search(PLAIN_ROW, INSERTING), []))
    assert block.startswith(f"\n\n[{mu.SECTION_FAMILY_INSERTED_HEAD} into the {ACT_T} ({ACT}) "
                            "(s.33A, inserted by s.8 of asp/2003/10), and the lettered sections "
                            "beside them: ")
    assert "ssi/2022/356" in block and "uksi/1998/1603" in block
    assert {(e["tool"], e.get("family") or e.get("legislation_id")) for e in entries} == {
        ("made_under", "33"), ("enabling_power", "ssi/2022/356"),
        ("enabling_power", "uksi/1998/1603")}
    assert ("rows", "asp/2003/10", ["9", "8"]) in _block_record


def test_the_inserted_family_is_handed_once_per_run(_block_record):
    log = [{"tool": "made_under", "source": mu.SECTION_FAMILY_SOURCE, "act_id": ACT,
            "family": "33"}]
    assert asyncio.run(agent_shared.made_under_sections_note(
        "search_legislation_sections", _search(INSERTING), log)) == ("", [])


def test_an_unresolved_amended_act_adds_nothing(_block_record, monkeypatch):
    async def none(*a):
        return None
    monkeypatch.setattr(store, "amended_act_id", none)
    assert asyncio.run(agent_shared.made_under_sections_note(
        "search_legislation_sections", _search(INSERTING), [])) == ("", [])


def test_the_returned_sections_block_is_unchanged_without_inserted():
    rows = [ORDER, DECISIONS]
    assert mu.section_families_block(ACT, ["33"], rows, {}) == \
        mu.section_families_block(ACT, ["33"], rows, {}, inserted=None)
    assert mu.section_families_block(ACT, ["33"], rows, {})[0].startswith(
        f"\n\n[{mu.SECTION_FAMILY_HEAD} of the {ACT_T} ({ACT}) and the lettered sections beside "
        "them: instruments whose own preamble")


def test_amended_act_id_touches_no_database_until_the_record_is_loaded(monkeypatch):
    monkeypatch.setitem(store._STATE, "available", False)
    import src.database as db
    touched = []

    def boom(*a, **k):
        touched.append(1)
        raise AssertionError("database touched")
    monkeypatch.setattr(db, "async_session_maker", boom)
    assert asyncio.run(store.amended_act_id("year", "1987", "section/33A")) is None
    assert touched == []
    monkeypatch.setitem(store._STATE, "available", True)
    assert asyncio.run(store.amended_act_id("year", "1987", "nonsense")) is None
    assert asyncio.run(store.amended_act_id("year", "1987", "section/33A")) is None  # fails soft
