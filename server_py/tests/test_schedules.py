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


# =============================================================================
# P3.12: the code route to a named schedule or annex unit
# =============================================================================

from src.agent import agent_shared  # noqa: E402
from src.agent.agent_core import run_worker_agent  # noqa: E402

URI = f"http://www.legislation.gov.uk/id/{LID}"
# A schedule whose paragraphs 1-2 are headed, 3 is not, 4-5 are headed, so
# paragraph 2's cut swallows paragraph 3, and 5 is the last headed one.
SCHED_2_TEXT = (
    "SCHEDULE 2 WIDGET FEES Article 3\n\n"
    "Section 1) **Application fee**\n1) The application fee is one shilling.\n"
    "Section 2) **Renewal fee**\n1) The renewal fee is sixpence.\n"
    "3) A fee paid late is doubled.\n"
    "Section 4) **Refunds**\n1) A fee may be refunded.\n"
    "Section 5) **Waiver**\n1) The registrar may waive a fee.\n6) Final words.\n"
)
SCHED_3_TEXT = "SCHEDULE 3 FORMS\n1) Form A.\n2) Form B.\n"   # bare markers only
ANNEX_TEXT = ("ANNEX II WIDGET IMPORTS CHAPTER IGeneral rules for widgets. "
              "CHAPTER IISpecific rules for blue widgets. CHAPTER IIIRules for red widgets.")


def _prow(path, text, ptype="schedule"):
    return {"uri": f"{URI}/{path}", "id": f"{URI}/{path}", "text": text,
            "provision_type": ptype, "legislation_id": URI}


PROVISIONS = [
    _prow("article/1", "Section 1) **Citation**\ntext", "section"),
    _prow("schedule/2", SCHED_2_TEXT),
    _prow("article/2", "Section 2) **Widgets**\ntext", "section"),
    _prow("schedule/3", SCHED_3_TEXT),
    _prow("annex/II", ANNEX_TEXT),
    _prow("schedule/4", ""),
]


def _search_result(*paths):
    return json.dumps({"results": [
        {"legislation_id": LID, "provision_type": "section", "number": 1,
         "title": "t", "url": f"{URI}/{p}", "text": "x"} for p in paths], "returned": len(paths)})


def _route_lex(monkeypatch, provisions=(200, PROVISIONS), text=(200, None)):
    """Stub `_request_with_retry` by endpoint for the route's two calls."""
    asked = []

    async def fake(client, method, url, *, name="", **kwargs):
        path = url.split("/legislation", 1)[-1]
        asked.append((path, kwargs.get("json")))
        status, body = provisions if path == "/section/lookup" else text
        if isinstance(status, Exception):
            raise status
        return httpx.Response(status, json=body, request=httpx.Request(method, url))

    monkeypatch.setattr(executor, "_request_with_retry", fake)
    return asked


def _route(query, results=None, fetches=None, threshold=8000, summary=None, monkeypatch=None,
           budget=None, urls=None):
    if monkeypatch is not None:
        from src.agent import provider_factory
        monkeypatch.setattr(provider_factory, "get_summarise_threshold", lambda *a, **k: threshold)

        async def fake_summarise(text, q, model, **kw):
            summary.append(len(text)) if summary is not None else None
            return "SUMMARY.", False
        monkeypatch.setattr(agent_shared, "summarise_for_query", fake_summarise)
    return asyncio.run(agent_shared.schedule_route_block(
        "search_legislation_sections", {"legislation_id": LID, "query": query},
        results if results is not None else _search_result("article/1"), "q",
        {} if fetches is None else fetches, context_budget=budget, retrieved_urls=urls))


# --- the trigger --------------------------------------------------------------

def test_named_units_reads_every_form():
    u = su.named_units('"Schedule 2" "paragraph 4"')[0]
    assert (u.kind, u.label, u.paragraphs) == ("schedule", "2", ("4",))
    assert su.named_units("Sch. B1 paras 42-44 widgets")[0].paragraphs == ("42", "43", "44")
    assert su.named_units("paragraphs 4, 5 and 7 of Schedule 2")[0].paragraphs == ("4", "5", "7")
    a = su.named_units("Chapter II of Annex II widgets")[0]
    assert (a.kind, a.label, a.chapter) == ("annex", "II", "II")
    assert su.named_units("Annex II")[0].chapter == ""
    assert su.named_units("Schedule 2, Part 1")[0].part == "1"
    # Two schedules: no paragraph is attached to either.
    two = su.named_units("Schedule 2 and Schedule 3 paragraph 1")
    assert [x.label for x in two] == ["2", "3"] and all(not x.paragraphs for x in two)
    # The word without a label, and a section query, name nothing.
    for q in ("schedules to the Widget Order", "section 5 widgets", "the schedule of fees", ""):
        assert su.named_units(q) == [], q


def test_unit_in_results():
    u = su.named_units("Schedule 2 paragraph 4")[0]
    assert su.unit_in_results(_search_result("article/1"), u) is False
    assert su.unit_in_results(_search_result("schedule/2"), u) is True
    assert su.unit_in_results(_search_result("schedule/20"), u) is False
    assert su.unit_in_results("Error executing tool: boom", u) is None
    assert su.unit_in_results(json.dumps({"notice": "limit", "searched": False}), u) is None
    # An instrument's only, unnumbered schedule answers "Schedule 1".
    assert su.unit_in_results(_search_result("schedule"), su.named_units("Schedule 1")[0]) is True


def test_the_route_fires_on_a_missing_unit_and_fetches_once_per_run(monkeypatch):
    asked = _route_lex(monkeypatch)
    fetches = {}
    out = _route("Schedule 2 paragraph 4", fetches=fetches, monkeypatch=monkeypatch)
    assert out.startswith("\n\n[PROVISION FETCHED BY CODE — the index holds Schedule 2 of "
                          "ssi/1901/3 as one provision")
    assert asked == [("/section/lookup", {"legislation_id": LID,
                                         "limit": executor.PROVISION_LIST_LIMIT})]
    _route("Schedule 3", fetches=fetches, monkeypatch=monkeypatch)
    assert len(asked) == 1            # memoised for the run


def test_the_route_does_not_fire_on_a_present_unit_or_a_section_query(monkeypatch):
    asked = _route_lex(monkeypatch)
    assert _route("Schedule 2 paragraph 4", results=_search_result("schedule/2"),
                  monkeypatch=monkeypatch) == ""
    assert _route("section 2 widgets", monkeypatch=monkeypatch) == ""
    assert _route("Schedule 2", results="Error executing tool: boom", monkeypatch=monkeypatch) == ""
    assert asyncio.run(agent_shared.schedule_route_block(
        "search_legislation_sections", {"legislation_id": LID, "query": "Schedule 2"},
        _search_result("article/1"), "q", None)) == ""          # route disabled
    assert asyncio.run(agent_shared.schedule_route_block(
        "search_legislation", {"query": "Schedule 2"}, "{}", "q", {})) == ""
    assert asked == []


def test_the_route_is_bounded_per_run(monkeypatch):
    asked = _route_lex(monkeypatch)
    fetches = {f"ssi/1901/{n}": {"status": "failed", "text": None}
               for n in range(10, 10 + agent_shared.MAX_PROVISION_FETCHES)}
    assert _route("Schedule 2", fetches=fetches, monkeypatch=monkeypatch) == ""
    assert asked == []


# --- the cuts -----------------------------------------------------------------

def test_a_clean_paragraph_is_cut_exactly(monkeypatch):
    _route_lex(monkeypatch)
    urls = set()
    out = _route("Schedule 2 paragraph 4", monkeypatch=monkeypatch, urls=urls)
    assert "Paragraph 4 of Schedule 2, cut at its own heading and the next one:" in out
    assert "A fee may be refunded." in out
    assert "waive" not in out and "renewal" not in out.lower()
    assert out.rstrip().endswith("[/PROVISION FETCHED BY CODE]")
    # The unit's URL counts as retrieved, so the answer may link to it.
    assert any(u.endswith("ssi/1901/3/schedule/2") for u in urls), urls


def test_a_paragraph_heading_met_twice_is_not_cut(monkeypatch):
    twice = SCHED_2_TEXT + "Section 4) **Refunds again**\n1) Repeated.\n"
    _route_lex(monkeypatch, provisions=(200, [_prow("schedule/2", twice)]))
    out = _route("Schedule 2 paragraph 4", monkeypatch=monkeypatch)
    assert "Below is the whole of Schedule 2. Paragraph 4 has no single heading of its own" in out
    assert "Repeated." in out and "one shilling" in out


def test_a_paragraph_whose_cut_swallows_the_next_is_labelled(monkeypatch):
    _route_lex(monkeypatch)
    out = _route("Schedule 2 paragraph 2", monkeypatch=monkeypatch)
    assert "It runs through paragraphs 2 to 3, because the paragraphs after 2" in out
    assert "A fee paid late is doubled." in out and "refunded" not in out
    last = _route("Schedule 2 paragraph 5", monkeypatch=monkeypatch)
    assert "from the heading of paragraph 5 to its end" in last and "Final words." in last


def test_an_annex_chapter_is_cut_at_its_heading(monkeypatch):
    _route_lex(monkeypatch)
    out = _route("Annex II Chapter II blue widgets", monkeypatch=monkeypatch)
    assert "Chapter II of Annex II, cut at its heading and the next chapter's heading:" in out
    assert "blue widgets" in out and "red widgets" not in out and "General rules" not in out


def test_no_marker_hands_over_the_whole_unit_verbatim_or_summarised(monkeypatch):
    _route_lex(monkeypatch)
    small = _route("Schedule 3 paragraph 2", monkeypatch=monkeypatch)
    assert "Below is the whole of Schedule 3. Paragraph 2 has no single heading of its own" in small
    assert "Form B." in small
    seen = []
    big = _route("Schedule 3 paragraph 2", threshold=20, summary=seen, monkeypatch=monkeypatch)
    assert "Below is Schedule 3 summarised for this research question" in big
    assert "The summary is not the statutory text" in big and "SUMMARY." in big
    assert "Form B." not in big and seen == [len(SCHED_3_TEXT)]


def test_the_context_budget_also_sends_the_unit_to_the_summariser(monkeypatch):
    _route_lex(monkeypatch)
    seen = []
    out = _route("Schedule 3", summary=seen, monkeypatch=monkeypatch,
                 budget={"used": 100, "limit": 110})
    assert "summarised for this research question" in out and seen


# --- what the list says when it does not give the unit ------------------------

def test_a_unit_the_complete_list_does_not_hold_is_said_in_code(monkeypatch):
    _route_lex(monkeypatch)
    out = _route("Schedule 7 paragraph 1", monkeypatch=monkeypatch)
    assert out == ("\n\n[PROVISION FETCHED BY CODE — the index holds 6 provisions for "
                   "ssi/1901/3, and its schedules and annexes among them are Schedule 2, "
                   "Schedule 3, Annex II and Schedule 4: Schedule 7 is not one of them. "
                   "This search's results left it out for that reason.]")
    _route_lex(monkeypatch, provisions=(200, PROVISIONS[:1]))
    none = _route("Schedule 1", monkeypatch=monkeypatch)
    assert "none of them is a schedule or an annex" in none


def test_a_list_cut_short_leaves_the_question_open(monkeypatch):
    monkeypatch.setattr(executor, "PROVISION_LIST_LIMIT", 3)
    _route_lex(monkeypatch, provisions=(200, PROVISIONS[:3]))
    out = _route("Schedule 7", monkeypatch=monkeypatch)
    assert "whether the index holds Schedule 7 of ssi/1901/3 is open" in out


def test_a_unit_listed_without_text_and_an_instrument_without_text(monkeypatch):
    _route_lex(monkeypatch)
    assert "lists Schedule 4 of ssi/1901/3 as a provision and holds no text for it" in \
        _route("Schedule 4", monkeypatch=monkeypatch)
    _route_lex(monkeypatch, provisions=(404, {"detail": "No sections found for legislation ID"}))
    assert "holds ssi/1901/3 without its provision text" in _route("Schedule 2", monkeypatch=monkeypatch)


def test_a_failed_list_falls_back_to_the_whole_text_cut_at_the_heading(monkeypatch):
    whole = SECTIONS + "\n\n" + SCHED_1 + "\n\n" + SCHED_2_TEXT + "\n\nSCHEDULE 3 FORMS\n1) A."
    asked = _route_lex(monkeypatch, provisions=(503, {"detail": "busy"}),
                       text=(200, _record(whole)))
    out = _route("Schedule 2 paragraph 4", monkeypatch=monkeypatch)
    assert "did not come back, so code cut Schedule 2 out of the instrument's whole text" in out
    assert "A fee may be refunded." in out and "Form" not in out
    assert asked[1] == ("/text", {"legislation_id": LID, "include_schedules": True})


def test_a_heading_met_twice_in_the_whole_text_is_not_cut(monkeypatch):
    """The fallback cuts only at a heading met once: a contents line at a
    paragraph start and the schedule itself are two, and cutting at the first
    would hand over the contents line as the unit."""
    contents = "SCHEDULE 2 Widget fees\n\nSCHEDULE 3 Forms"
    whole = (SECTIONS + "\n\nARRANGEMENT\n\n" + contents + "\n\n" + SCHED_1
             + "\n\n" + SCHED_2_TEXT)
    assert su.cut_unit_from_text(whole, su.ScheduleUnit("schedule", "2")) is None
    assert su.cut_unit_from_text(whole, su.ScheduleUnit("schedule", "1")) is not None
    _route_lex(monkeypatch, provisions=(503, {"detail": "busy"}), text=(200, _record(whole)))
    out = _route("Schedule 2 paragraph 4", monkeypatch=monkeypatch)
    assert "Whether the index holds Schedule 2 is open: do not report it as absent." in out
    assert "refunded" not in out


def test_a_bracket_in_the_id_or_url_never_reaches_a_header():
    """`_clean` keeps the header bracket-free, whatever the model passed as
    the legislation_id or LEX returned as the uri, so the strip still removes
    the block whole."""
    lid, url = "ssi/1901/[3]", "http://www.legislation.gov.uk/id/ssi/1901/3/schedule/[2]"
    unit = su.ScheduleUnit("schedule", "2", paragraphs=("4",))
    blocks = [
        su.fetched_block(lid, unit, url, [("", "SCHEDULE 2 text")], su.WHOLE),
        su.fetched_block(lid, unit, url, [("", "x")], su.SUMMARY, total_chars=9,
                         source=su.FROM_TEXT),
        su.unit_absent_line(lid, unit, [{"uri": url}], True),
        su.unit_absent_line(lid, unit, [{"uri": url}], False),
        su.unit_without_text_line(lid, unit),
        su.instrument_without_text_line(lid, unit),
        su.fetch_failed_line(lid, unit),
    ]
    for b in blocks:
        header = b.strip().split("\n", 1)[0]
        assert header.count("[") == 1 and header.count("]") == 1, header
        assert strip_scope_blocks("Answer." + b) == ("Answer.", 1), header


def test_a_failed_list_and_text_say_the_question_is_open(monkeypatch):
    _route_lex(monkeypatch, provisions=(httpx.ConnectTimeout("slow"), None), text=(503, {}))
    out = _route("Schedule 2", monkeypatch=monkeypatch)
    assert "Whether the index holds Schedule 2 is open: do not report it as absent." in out


def test_every_route_block_strips_whole_and_its_header_has_no_inner_bracket(monkeypatch):
    _route_lex(monkeypatch)
    for q in ("Schedule 2 paragraph 4", "Schedule 2 paragraph 2", "Annex II Chapter II",
              "Schedule 3 paragraph 2", "Schedule 7", "Schedule 4"):
        out = _route(q, monkeypatch=monkeypatch)
        header = out.strip().split("\n", 1)[0]
        assert header.count("[") == 1 and header.count("]") == 1, header
        assert strip_scope_blocks("Answer." + out) == ("Answer.", 1), q
    # A bracket in the statutory text does not break the strip.
    rows = [_prow("schedule/2", "SCHEDULE 2 [F1 substituted] text")]
    _route_lex(monkeypatch, provisions=(200, rows))
    out = _route("Schedule 2", monkeypatch=monkeypatch)
    assert strip_scope_blocks("Answer." + out) == ("Answer.", 1)


# --- both Workers reach the route, through run_worker_tool --------------------

@pytest.mark.parametrize("chat_mode", ["conversational", "research"])
def test_both_workers_reach_the_route(monkeypatch, chat_mode):
    set_request_provider_config({"_provider": "openrouter", "model": "test-model",
                                 "_research_mode": "legislation_only",
                                 "_chat_mode": chat_mode,
                                 "_local_prompt_cache_enabled": False})
    asked = []

    async def fake(client, method, url, *, name="", **kwargs):
        path = url.split("/legislation", 1)[-1]
        body = kwargs.get("json") or {}
        asked.append((path, body.get("limit")))
        if path == "/section/search":
            return httpx.Response(200, json=json.loads(_search_result("article/1"))["results"],
                                  request=httpx.Request(method, url))
        if path == "/lookup":
            return httpx.Response(200, json={"uri": URI, "title": "Widget Order 1901"},
                                  request=httpx.Request(method, url))
        return httpx.Response(200, json=PROVISIONS, request=httpx.Request(method, url))

    monkeypatch.setattr(executor, "_request_with_retry", fake)
    seen = []

    async def loop(messages, model, cancel_event, num_ctx, tools, tool_exec, on_chunk=None, **kw):
        seen.append(await tool_exec("search_legislation_sections",
                                    {"legislation_id": LID, "query": "Schedule 2 paragraph 4"}))
        return {"role": "assistant", "content": "Report."}

    try:
        asyncio.run(run_worker_agent(loop, lambda *a, **k: None, "Widgets?", "test-model", None, 0))
    finally:
        set_request_provider_config({})
    assert "[PROVISION FETCHED BY CODE — the index holds Schedule 2" in seen[0]
    assert "A fee may be refunded." in seen[0]
    assert ("/section/lookup", executor.PROVISION_LIST_LIMIT) in asked
    # The quick-lookup path really ran: P3.25's code lookup precedes its search.
    assert (("/lookup", None) in asked) == (chat_mode == "conversational")


@pytest.mark.asyncio
async def test_a_failing_route_leaves_the_section_search_as_it_was(monkeypatch):
    """Fail-soft (Invariant 5): an exception in the route is logged and the
    search result reaches the Worker exactly as it would without the route."""
    async def fake_exec(name, args, on_chunk=None, timing_collector=None, worker_call=False):
        return _search_result("article/1")

    async def boom(*a, **k):
        raise RuntimeError("route broke")

    set_request_provider_config({"_provider": "openrouter", "model": "test-model"})
    try:
        monkeypatch.setattr(agent_shared, "execute_worker_tool", fake_exec)
        monkeypatch.setattr(agent_shared, "schedule_route_block", boom)
        args = {"legislation_id": LID, "query": "Schedule 2 paragraph 4"}
        out = await agent_shared.run_worker_tool(
            "search_legislation_sections", args, "q", None, "m", provision_fetches={})
        assert out.startswith(_search_result("article/1"))
        assert "PROVISION FETCHED BY CODE" not in out
    finally:
        set_request_provider_config({})
