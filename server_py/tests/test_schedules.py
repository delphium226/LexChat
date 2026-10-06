"""P3.27 (`get_legislation_text` never returned a schedule or annex) and P3.12
(the code route to a named schedule or annex unit).

Every instrument, title and text below is synthetic ("Widget Order 1901",
`ssi/1901/3`). The detector screen for every wording here is in
`test_search_scope.py::test_footer_trips_no_detector`.
"""

import asyncio
import json

import httpx
import pytest

from src.agent.provider_factory import set_request_provider_config
from src.agent.tools import executor
from src.utils import schedule_units as su
from src.utils.search_scope import strip_scope_blocks

LID = "ssi/1901/3"
SECTIONS = (
    "Section 1) **Citation**\nThis Order may be cited as the Widget Order 1901.\n\n"
    "Section 2) **Widgets**\nA widget must be registered in accordance with Schedule 1."
)
SCHED_1 = (
    "SCHEDULE 1 REGISTRATION OF WIDGETS Article 2 \n\nSection 1) **Application**\n"
    "1) An application is made to the registrar.\n"
)
SCHED_2 = "SCHEDULE 2 Fees Article 3 \n1) The fee is one shilling.\n"


def _record(full_text, **extra):
    rec = {"legislation": {"id": f"http://www.legislation.gov.uk/id/{LID}",
                           "title": "Widget Order 1901", "valid_date": "1901-01-01"},
           "full_text": full_text}
    rec.update(extra)
    return rec


# --- P3.27: the executor sends the flag and makes the unflagged call ----------

def _text_lex(monkeypatch, flagged, unflagged):
    """Stub `_request_with_retry` for `/legislation/text`: (status, body) for
    the flagged and the unflagged call; an Exception raises. Records payloads."""
    asked = []

    async def fake(client, method, url, *, name="", **kwargs):
        payload = kwargs.get("json")
        asked.append(payload)
        status, body = flagged if payload.get("include_schedules") else unflagged
        if isinstance(status, Exception):
            raise status
        return httpx.Response(status, json=body, request=httpx.Request(method, url))

    monkeypatch.setattr(executor, "_request_with_retry", fake)
    return asked


def _get_text():
    return asyncio.run(executor.execute_worker_tool(
        "get_legislation_text", {"legislation_id": LID}))


def test_the_flag_is_sent_and_the_unflagged_call_is_made(monkeypatch):
    whole = SECTIONS + " \n\n" + SCHED_1 + "\n\n" + SCHED_2
    asked = _text_lex(monkeypatch, (200, _record(whole)), (200, _record(SECTIONS)))
    out = json.loads(_get_text())
    assert asked == [{"legislation_id": LID, "include_schedules": True},
                     {"legislation_id": LID}]
    # The text passed on is the flagged text, with the exact boundary stamped.
    assert out["full_text"] == whole
    assert out["schedule_text_starts_at"] == len(SECTIONS)
    assert out["include_schedules"] is True
    assert out["legislation"]["title"] == "Widget Order 1901"


@pytest.mark.parametrize("failure", [
    (503, {"detail": "unavailable"}),
    (httpx.ConnectTimeout("slow"), None),
])
def test_a_failed_unflagged_call_keeps_the_flagged_text_and_says_less(monkeypatch, failure):
    whole = SECTIONS + " \n\n" + SCHED_1
    _text_lex(monkeypatch, (200, _record(whole)), failure)
    raw = _get_text()
    out = json.loads(raw)
    assert out["full_text"] == whole
    assert out["schedule_text_starts_at"] is None
    line = su.schedules_note({"legislation_id": LID}, raw)
    assert "was not checked" in line
    assert "Schedule 1" not in line          # never more than was established


def test_a_failed_flagged_call_fails_as_before_with_no_second_call(monkeypatch):
    asked = _text_lex(monkeypatch, (404, {"detail": "Legislation not found: ssi 1901 No. 3"}),
                      (200, _record(SECTIONS)))
    raw = _get_text()
    assert raw.startswith("Error executing tool:") and "Legislation not found" in raw
    assert len(asked) == 1
    assert su.schedules_note({"legislation_id": LID}, raw) == ""


# --- P3.27: the line's cases ---------------------------------------------------

def _line(sections, appended, start="exact"):
    full = sections + appended
    rec = _record(full, include_schedules=True,
                  schedule_text_starts_at=len(sections) if start == "exact" else start)
    return su.schedules_note({"legislation_id": LID}, json.dumps(rec))


def test_schedules_named_by_number():
    line = _line(SECTIONS, " \n\n" + SCHED_1 + "\n\n" + SCHED_2)
    assert line.startswith("\n\n[SCHEDULES AND ANNEXES — ")
    assert "under these headings: Schedule 1 and Schedule 2." in line
    # Only labels: nothing about what the schedules say.
    assert "REGISTRATION" not in line and "Fees" not in line


def test_ordinal_unnumbered_and_annex_headings():
    ordinal = _line(SECTIONS, "\n\nSECOND SCHEDULE referred to in the foregoing Act.\n\nx\n\n"
                              "FIRST SCHEDULE referred to in the foregoing Act.")
    assert "the Second Schedule and the First Schedule" in ordinal
    sole = _line(SECTIONS, " \n\nSCHEDULE APPEARANCE OF WIDGET STAMPS regulation 4")
    assert "under this heading: the Schedule." in sole
    # A title word is never read as a label: a label carries a digit.
    titled = _line(SECTIONS, " \n\nSCHEDULE FORM OF WIDGET REGISTER regulation 5")
    assert "under this heading: the Schedule." in titled
    annex = _line(SECTIONS, " \n\nANNEX XII WIDGET PRODUCTS text\n\nANNEX V MORE text\n\nANNEX table")
    assert "Annex XII, Annex V and the Annex" in annex


def test_none_held():
    line = _line(SECTIONS, "")
    assert line == (f"\n\n[SCHEDULES AND ANNEXES — the index holds no schedule or annex "
                    f"text for {LID}, so this text is its sections only.]")


def test_schedule_text_with_no_heading():
    line = _line(SECTIONS, "\n\nChapter: 1901 c. 1.\nShort Title: Widget Act 1901.")
    assert "further text that the index holds as schedule or annex text" in line
    assert "It carries no schedule or annex heading." in line


def test_text_before_the_first_heading_is_said():
    line = _line(SECTIONS, "\n\nARRANGEMENT OF PARAGRAPHS\n1. Citation\n\n" + SCHED_1)
    assert "under this heading: Schedule 1." in line
    assert "comes before the first of them" in line


def test_a_mixed_case_heading_needs_its_title():
    # "Schedule 4 Prosecution ..." is a heading; "Schedule 1. " ending a
    # sentence is a cross-reference (both shapes are in the live texts).
    line = _line(SECTIONS, "\n\n" + SCHED_1 + "\nsee paragraph 1 of\n\nSchedule 3. \n2) more"
                           "\n\nSchedule 4 Prosecution and Punishment of Widget Offences\n")
    assert "under these headings: Schedule 1 and Schedule 4." in line


def test_a_heading_inside_the_sections_is_not_named():
    # The boundary is exact: a heading-like line in the sections is not read.
    sections = SECTIONS + "\n\nSCHEDULE 9 quoted in an amendment\n"
    line = _line(sections, "\n\n" + SCHED_1)
    assert "Schedule 9" not in line and "under this heading: Schedule 1." in line


def test_a_repeated_label_is_named_once():
    line = _line(SECTIONS, "\n\n" + SCHED_1 + "\n\nSCHEDULE 1 substituted text\n")
    assert line.count("Schedule 1") == 1


def test_an_unknown_boundary_says_only_that_it_was_requested():
    for start in (None, -1, 10**9):
        line = _line(SECTIONS, "\n\n" + SCHED_1, start=start)
        assert "Which ones it carries was not checked." in line
        assert "Schedule 1" not in line


def test_silent_on_an_error_or_a_result_that_did_not_ask():
    assert su.schedules_note({"legislation_id": LID}, "Error executing tool: boom") == ""
    assert su.schedules_note({"legislation_id": LID}, json.dumps(_record(SECTIONS))) == ""
    assert su.schedules_note({"legislation_id": LID}, json.dumps({"error": "x"})) == ""


def test_every_variant_strips_whole_and_has_no_inner_bracket():
    lines = [
        _line(SECTIONS, " \n\n" + SCHED_1 + "\n\n" + SCHED_2),
        _line(SECTIONS, ""),
        _line(SECTIONS, "\n\nChapter: 1901 c. 1."),
        _line(SECTIONS, "\n\n" + SCHED_1, start=None),
        _line(SECTIONS, "\n\nlead text\n\n" + SCHED_1),
    ]
    for line in lines:
        body = line.strip()
        assert body.count("[") == 1 and body.count("]") == 1 and body.endswith("]")
        out, n = strip_scope_blocks("Answer." + line)
        assert (out, n) == ("Answer.", 1)


def test_a_lawyers_schedule_link_is_not_stripped():
    text = "See [Schedules 1 and 2 to the Widget Order 1901](https://www.legislation.gov.uk/ssi/1901/3)."
    assert strip_scope_blocks(text) == (text, 0)


def test_the_boundary_stamp_is_additive_and_fail_soft():
    flagged = _record(SECTIONS + "\n\n" + SCHED_1)
    got = su.mark_schedule_boundary(dict(flagged), _record(SECTIONS))
    assert got["schedule_text_starts_at"] == len(SECTIONS)
    assert {k: got[k] for k in flagged} == flagged
    # Not a prefix: the boundary is unknown, never guessed.
    assert su.mark_schedule_boundary(dict(flagged), _record("other"))["schedule_text_starts_at"] is None
    assert su.mark_schedule_boundary("not a dict", None) == "not a dict"


# --- P3.27: the line reaches what the Worker receives --------------------------

@pytest.mark.asyncio
async def test_the_line_reaches_the_worker_after_summarisation(monkeypatch):
    """Built from the RAW result and appended after summarisation: the
    summary of a large text keeps neither the boundary nor the headings."""
    from src.agent import agent_shared

    big = SECTIONS + ("\nfiller" * 4000)
    raw = json.dumps(_record(big + "\n\n" + SCHED_1, include_schedules=True,
                             schedule_text_starts_at=len(big)))

    async def fake_exec(name, args, on_chunk=None, timing_collector=None, worker_call=False):
        return raw

    async def fake_summarise(text, query, model, **kw):
        return "A summary that names no schedule.", False

    set_request_provider_config({"_provider": "openrouter", "model": "test-model",
                                 "_local_prompt_cache_enabled": False})
    try:
        monkeypatch.setattr(agent_shared, "execute_worker_tool", fake_exec)
        monkeypatch.setattr(agent_shared, "summarise_for_query", fake_summarise)
        out = await agent_shared.run_worker_tool(
            "get_legislation_text", {"legislation_id": LID}, "q", None, "m")
        assert out.startswith("A summary that names no schedule.")
        assert "[SCHEDULES AND ANNEXES — this text of ssi/1901/3 carries" in out
        assert "under this heading: Schedule 1." in out
    finally:
        set_request_provider_config({})
