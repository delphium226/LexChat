"""FIX_PLAN P3.48: recorded revocations marked at the answer seam
(`utils/revocation_marks.py`), the facts `record_made_under` and the
section-family route keep for it, and the wiring in `process_user_request`."""
from __future__ import annotations

import pytest

from src.utils import revocation_marks as rm
from src.utils.made_under import section_families_block
from src.utils.search_scope import record_made_under

PART = "recorded on legislation.gov.uk as revoked in part"
WHOLE = ("recorded on legislation.gov.uk as revoked in whole by SSI 1905/9, "
         "with effect from 1906-01-01")

T1 = "The Widget Licensing (Scotland) Regulations 1901"
T2 = "The Widget Fees (Scotland) Regulations 1902"
T3 = "The Widget Inspection (Scotland) Order 1903"
T4 = "The Widget Appeals (Scotland) Regulations 1904"


def _inst(lid, title, status, line):
    return {"legislation_id": lid, "title": title, "url": f"https://www.legislation.gov.uk/{lid}",
            "revocation": line, "revocation_status": status}


def _result(*insts, checked="1910-10-10"):
    return {"tool": "find_instruments_made_under", "status": "found",
            "matched_act": "Widget (Scotland) Act 1900", "provision": "section/9",
            "count": len(insts), "instruments": list(insts),
            "coverage": {"label": "Scottish statutory instruments 1999 to 2026"},
            "revocations": {"revoked": 1, "partly": 2, "none": 1, "checked": checked}}


RESULT = _result(
    _inst("ssi/1901/1", T1, "partly", "recorded as revoked in part: 2 provisions revoked or omitted, by ssi/1905/9"),
    _inst("ssi/1902/2", T2, "revoked", "recorded as revoked in whole by ssi/1905/9, with effect from 1906-01-01"),
    _inst("ssi/1903/3", T3, "none", "no revocation recorded"),
    _inst("ssi/1904/4", T4, "partly", "recorded as revoked in part: 1 provision revoked or omitted, by ssi/1905/9"),
)


def _log(result=RESULT):
    log: list = []
    record_made_under(log, result)
    return log


def mark(answer, log=None):
    return rm.mark_revoked_instruments(answer, _log() if log is None else log)


# --- the facts -----------------------------------------------------------------


def test_record_made_under_keeps_each_revoked_listed_instrument():
    entry = [e for e in _log() if e.get("tool") == "made_under"][0]
    assert sorted(entry["revoked"]) == ["ssi/1901/1", "ssi/1902/2", "ssi/1904/4"]
    assert entry["revoked"]["ssi/1902/2"]["status"] == "revoked"
    assert entry["revoked"]["ssi/1901/1"]["title"] == T1
    assert entry["revoked"]["ssi/1901/1"]["checked"] == "1910-10-10"


def test_no_revocations_checked_keeps_no_facts():
    result = dict(RESULT, revocations=None)
    assert rm.revocation_facts(_log(result)) == {}
    answer = f"See {T1} (SSI 1901/1)."
    assert mark(answer, _log(result)) == (answer, 0)


def test_a_section_family_entry_carries_its_partly_revoked_instruments():
    rows = [("section/9", "ssi/1901/1", T1, "Widget (Scotland) Act 1900",
             '{"state": "partly", "partial": {"count": 1}}', "1910-10-10"),
            ("section/9", "ssi/1903/3", T3, "Widget (Scotland) Act 1900", None, "1910-10-10")]
    _block, entries = section_families_block("asp/1900/1", ["9"], rows, {"label": "x"})
    fam = [e for e in entries if e.get("tool") == "made_under"][0]
    assert list(fam["revoked"]) == ["ssi/1901/1"]
    # No made-under entry with revocations: the footer states no date, so the mark does.
    assert mark(f"* {T1}", entries)[0] == f"* {T1} ({PART}, as checked on 1910-10-10)"


# --- detection and wording -----------------------------------------------------


def test_a_partly_revoked_instrument_named_by_number_is_marked():
    out, n = mark("* SSI 1901/1 sets a fee.")
    assert (out, n) == (f"* SSI 1901/1 ({PART}) sets a fee.", 1)


def test_a_wholly_revoked_instrument_gets_its_revoking_instrument_and_date():
    out, n = mark(f"* {T2} sets a fee.")
    assert out == f"* {T2} ({WHOLE}) sets a fee."


def test_a_whole_revocation_with_no_date_says_so():
    res = _result(_inst("ssi/1902/2", T2, "revoked_undated",
                        "recorded as revoked in whole by ssi/1905/9, no date recorded"))
    assert mark("* SSI 1902/2.", _log(res))[0] == (
        "* SSI 1902/2 (recorded on legislation.gov.uk as revoked in whole by SSI 1905/9, "
        "no date recorded).")


def test_a_whole_revocation_still_to_come_never_reads_as_done():
    res = _result(_inst("ssi/1902/2", T2, "revoked_later",
                        "recorded as revoked in whole by ssi/1905/9, with effect from 2999-01-01, "
                        "a date still to come"))
    assert "with effect from 2999-01-01, a date still to come)" in mark("* SSI 1902/2.", _log(res))[0]
    # an unparsed line keeps "still to come" and drops the date
    res = _result(_inst("ssi/1902/2", T2, "revoked_later",
                        'recorded as revoked in whole by ssi/1905/9, with effect from 2999-01-01 '
                        '(date qualified in the record as "Other"), a date still to come'))
    assert mark("* SSI 1902/2.", _log(res))[0] == (
        "* SSI 1902/2 (recorded on legislation.gov.uk as revoked in whole by SSI 1905/9, "
        "from a date still to come).")


def test_a_whole_revocation_by_its_own_provisions():
    res = _result(_inst("ssi/1902/2", T2, "revoked",
                        "recorded as ceasing to have effect in whole by its own provisions, "
                        "with effect from 1906-01-01"))
    assert mark("* SSI 1902/2.", _log(res))[0] == (
        "* SSI 1902/2 (recorded on legislation.gov.uk as ceasing to have effect in whole by its "
        "own provisions, with effect from 1906-01-01).")


def test_an_instrument_with_no_revocation_is_never_marked():
    answer = f"* {T3} (SSI 1903/3) sets a fee."
    assert mark(answer) == (answer, 0)


def test_the_mark_never_says_in_force():
    out, _ = mark(f"* {T1}\n* {T2}\n* SSI 1904/4")
    assert "in force" not in out


def test_a_title_mention_followed_by_its_number_marks_inside_the_parenthesis():
    assert mark(f"* {T1} (SSI 1901/1)")[0] == f"* {T1} (SSI 1901/1; {PART})"


def test_a_link_to_the_instrument_is_marked_after_the_link():
    answer = f"* [{T1}](https://www.legislation.gov.uk/ssi/1901/1) sets a fee."
    assert mark(answer)[0] == (
        f"* [{T1}](https://www.legislation.gov.uk/ssi/1901/1) ({PART}) sets a fee.")


def test_a_provision_link_alone_names_the_instrument_in_the_mark():
    answer = "* [regulation 3](http://www.legislation.gov.uk/ssi/1901/1/regulation/3) sets a fee."
    assert mark(answer)[0] == (
        "* [regulation 3](http://www.legislation.gov.uk/ssi/1901/1/regulation/3) "
        f"(SSI 1901/1 is {PART}) sets a fee.")


def test_a_provision_link_labelled_with_the_instrument_counts_as_the_instrument():
    answer = f"* {T1} ([SSI 1901/1](http://www.legislation.gov.uk/ssi/1901/1/regulation/3))."
    assert mark(answer)[0] == (
        f"* {T1} ([SSI 1901/1](http://www.legislation.gov.uk/ssi/1901/1/regulation/3); {PART}).")


def test_bold_closes_before_the_mark():
    assert mark("* **SSI 1901/1** sets a fee.")[0] == f"* **SSI 1901/1** ({PART}) sets a fee."


def test_the_last_of_a_run_of_instruments_is_named_in_its_mark():
    out = mark("Not found in SSI 1903/3, SSI 1905/5 and SSI 1904/4.")[0]
    assert out == f"Not found in SSI 1903/3, SSI 1905/5 and SSI 1904/4 (SSI 1904/4 is {PART})."
    # not last: the bare mark
    out = mark("Not found in SSI 1904/4, SSI 1903/3 and SSI 1905/5.")[0]
    assert out == f"Not found in SSI 1904/4 ({PART}), SSI 1903/3 and SSI 1905/5."


def test_only_the_first_mention_is_marked():
    out, n = mark("* SSI 1901/1 sets a fee.\n\nLater, SSI 1901/1 is amended.")
    assert n == 1 and out.count(PART) == 1


# --- already marked ------------------------------------------------------------


@pytest.mark.parametrize("answer", [
    "* SSI 1901/1 (revoked in part) sets a fee.",
    "* SSI 1901/1 sets a fee. The record shows this instrument as partly revoked.",
    "* SSI 1901/1 sets a fee. (Note that legislation.gov.uk records it as revoked in part).",
    "SSI 1901/1 sets a fee. The index records this instrument as revoked in part.",
    "* SSI 1901/1 sets a fee.\n\nRevocations: SSI 1901/1 is recorded as revoked in part.",
])
def test_an_instrument_already_marked_near_any_mention_is_left(answer):
    assert mark(answer) == (answer, 0)


def test_a_negated_revocation_is_not_a_mark():
    out, n = mark("* SSI 1901/1: no revocation is recorded.")
    assert n == 1


def test_no_longer_in_force_having_been_revoked_is_a_mark():
    answer = "* SSI 1901/1 is no longer in force, having been revoked."
    assert mark(answer) == (answer, 0)


def test_a_revocation_word_in_a_title_is_not_a_mark():
    answer = ("* SSI 1901/1 and the Widget (Consequential Amendment, Revocation and Saving) "
              "(Scotland) Regulations 1906.")
    assert mark(answer)[1] == 1


# --- guards --------------------------------------------------------------------


@pytest.mark.parametrize("answer", [
    'It provides "SSI 1901/1 applies" to shops.',
    "Use `SSI 1901/1` here.",
    "```\nSSI 1901/1\n```",
    "## SSI 1901/1",
    "See [the note on SSI 1901/1](https://example.org/x).",
])
def test_no_mark_inside_a_quote_code_heading_or_label(answer):
    assert mark(answer) == (answer, 0)


def test_a_guarded_first_mention_moves_the_mark_to_the_next():
    out = mark("## SSI 1901/1\n\n* SSI 1901/1 sets a fee.")[0]
    assert out == f"## SSI 1901/1\n\n* SSI 1901/1 ({PART}) sets a fee."


def test_a_restored_note_is_not_read_or_marked():
    answer = "Answer.\n\nAlso in s.9: SSI 1901/1 sets a fee."
    assert mark(answer) == (answer, 0)


def test_the_head_of_a_longer_title_is_not_a_mention():
    answer = f"* {T1} (Amendment) Regulations 1907 set a fee."
    assert mark(answer) == (answer, 0)


def test_a_truncated_title_is_never_matched():
    res = _result(_inst("ssi/1901/1", "The Widget Licensing (Scotland…", "partly", "recorded as revoked in part"))
    answer = "* The Widget Licensing (Scotland) Regulations 1901 set a fee."
    assert mark(answer, _log(res)) == (answer, 0)


def test_a_longer_number_is_not_a_mention():
    answer = "* SSI 1901/12 and ssi/1901/1234 set fees."
    assert mark(answer) == (answer, 0)


# --- identity, idempotence, cap ------------------------------------------------


def test_nothing_to_mark_is_byte_identical():
    answer = "No instrument named here.\n\n*Search scope: x.*"
    assert mark(answer) == (answer, 0)
    assert rm.mark_revoked_instruments(answer, []) == (answer, 0)
    assert rm.mark_revoked_instruments("", _log()) == ("", 0)


def test_running_twice_adds_nothing():
    once, n = mark(f"* {T1}\n* {T2} (SSI 1902/2)\n* SSI 1904/4 and SSI 1903/3")
    assert n == 3
    assert mark(once) == (once, 0)


def test_at_most_eight_marks_a_class():
    insts = [_inst(f"ssi/1920/{i}", f"The Widget Number {i} (Scotland) Regulations 1920",
                   "partly", "recorded as revoked in part") for i in range(1, 11)]
    log = _log(_result(*insts))
    answer = "\n".join(f"* SSI 1920/{i}" for i in range(1, 11))
    out, n = mark(answer, log)
    assert n == rm.MARK_PER_CLASS == 8
    assert "* SSI 1920/9\n* SSI 1920/10" in out


def test_never_raises(monkeypatch):
    monkeypatch.setattr(rm, "plan_revocation_marks", lambda *a: 1 / 0)
    answer = "* SSI 1901/1"
    assert mark(answer) == (answer, 0)


# --- wiring --------------------------------------------------------------------


@pytest.fixture
def _cfg():
    from src.agent.provider_factory import set_request_provider_config

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
    return {"content": "Report.", "sources": [], "searches": _log()}


ANSWER = "Two instruments contain the symbol:\n\n* SSI 1901/1 sets a fee.\n* SSI 1903/3 sets another."


@pytest.mark.asyncio
async def test_the_conversational_answer_is_marked(_cfg):
    from src.agent.agent_core import process_user_request
    _cfg("conversational")
    final = await process_user_request(_manager(ANSWER), _worker,
                                       [{"role": "user", "content": "q"}], "test-model", None, None, 0)
    assert f"* SSI 1901/1 ({PART}) sets a fee." in final["content"]
    assert "* SSI 1903/3 sets another." in final["content"]


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["research", "deep_research"])
async def test_every_other_chat_mode_is_left_alone(_cfg, mode):
    from src.agent.agent_core import process_user_request
    _cfg(mode)
    final = await process_user_request(_manager(ANSWER), _worker,
                                       [{"role": "user", "content": "q"}], "test-model", None, None, 0)
    assert PART not in final["content"]


@pytest.mark.asyncio
async def test_the_parliamentary_bots_are_left_alone(_cfg):
    from src.agent.agent_core import process_user_request
    _cfg("conversational", "parliamentary_records")
    final = await process_user_request(_manager(ANSWER), _worker,
                                       [{"role": "user", "content": "q"}], "test-model", None, None, 0)
    assert PART not in final["content"]
