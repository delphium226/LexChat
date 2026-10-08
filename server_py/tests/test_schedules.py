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
    # The plural without a label, and a section query, name nothing.
    for q in ("schedules to the Widget Order", "section 5 widgets", "Schedules", ""):
        assert su.named_units(q) == [], q


@pytest.mark.parametrize("query, want", [
    ("Schedule A1 paragraphs 12 13 14 widgets", ("12", "13", "14")),
    ("Schedule A1 paragraph 12 13 14", ("12", "13", "14")),
    ("Schedule 2 para 12 13 to 15", ("12", "13", "14", "15")),
    ("Schedule 2 paragraphs 12(1) 13(2) widgets", ("12", "13")),
    ("Schedule 2 paras 1 2A 3", ("1", "2A", "3")),
    ("Schedule 2 paragraphs 2 3 4 5 6 7", ("2", "3", "4", "5")),      # the cap
])
def test_a_paragraph_run_joined_by_spaces_is_read(query, want):
    """Batch 8 A2 (the integrator's sweep): the Worker wrote a schedule's
    paragraphs as "paragraphs 12 13 14", the parser read only the first, and
    the route cut only that one."""
    assert su.named_units(query)[0].paragraphs == want


@pytest.mark.parametrize("query, want", [
    ("Schedule 2 paragraph 3 1901 widgets", ("3",)),          # a year
    ("Schedule 2 paragraph 3 1901/12", ("3",)),               # a citation
    ("Schedule 2 paragraph 3 Part 2", ("3",)),
    ("Schedule 2 paragraph 4 1 April 1901", ("4",)),          # a date
    ("Schedule 2 paragraph 3 12 March", ("3",)),              # a date, ascending
    ("Schedule 2 paragraph 5 14 days", ("5",)),               # a count
    ("Schedule 2 paragraph 3 5 per cent", ("3",)),
    ("Schedule 2 paragraph 3 5% widgets", ("3",)),
    ("Schedule 2 paragraph 3 4.5 widgets", ("3",)),
    ("Schedule 2 paragraph 4 2 widgets", ("4",)),             # not ascending
    ("Schedule 2 paragraph 4 5 6 3 widgets", ("4", "5", "6")),
])
def test_a_number_after_a_paragraph_that_is_not_one_is_not_read(query, want):
    assert su.named_units(query)[0].paragraphs == want


def test_the_route_cuts_every_paragraph_of_a_run_joined_by_spaces(monkeypatch):
    _route_lex(monkeypatch)
    out = _route("Schedule 2 paragraphs 1 4 widgets", monkeypatch=monkeypatch)
    assert "Paragraph 1 of Schedule 2, cut at its own heading and the next one:" in out
    assert "Paragraph 4 of Schedule 2, cut at its own heading and the next one:" in out
    assert "one shilling" in out and "A fee may be refunded." in out
    assert "sixpence" not in out and "waive" not in out


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
    # Batch 10 A: the tail says the unit was retrieved and the summary is a
    # condensed reading of that retrieved text.
    assert (f"Code retrieved the whole of Schedule 3, {len(SCHED_3_TEXT)} characters, and "
            "below is a summary of that retrieved text, condensed for this research "
            "question.") in big
    assert "SUMMARY." in big
    assert "Form B." not in big and seen == [len(SCHED_3_TEXT)]


def test_the_context_budget_also_sends_the_unit_to_the_summariser(monkeypatch):
    _route_lex(monkeypatch)
    seen = []
    out = _route("Schedule 3", summary=seen, monkeypatch=monkeypatch,
                 budget={"used": 100, "limit": 110})
    assert "a summary of that retrieved text, condensed for this research question" in out
    assert seen


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


# --- decision 1 (user, 2026-10-06): "the Schedule" with no label ---------------

def test_the_unlabelled_schedule_is_read_and_the_plural_is_not():
    u = su.named_units("the Schedule to the Widget Order")
    assert len(u) == 1 and (u[0].kind, u[0].label) == ("schedule", "")
    assert u[0].display() == "the Schedule"
    assert su.named_units("schedule of widget fees")[0].label == ""
    assert su.named_units("schedules to the Widget Order") == []
    # A labelled schedule in the query: no extra unlabelled unit.
    assert [x.label for x in su.named_units("Schedule 2 and the schedule")] == ["2"]


def test_the_unlabelled_schedule_is_present_when_any_schedule_row_is():
    u = su.ScheduleUnit("schedule", "")
    assert su.unit_in_results(_search_result("schedule/3"), u) is True
    assert su.unit_in_results(_search_result("schedule"), u) is True
    assert su.unit_in_results(_search_result("article/1", "annex/II"), u) is False


def test_unlabelled_with_none_held_says_so(monkeypatch):
    asked = _route_lex(monkeypatch, provisions=(200, PROVISIONS[:1] + PROVISIONS[2:3]))
    out = _route("the Schedule widgets", monkeypatch=monkeypatch)
    assert out == ("\n\n[PROVISION FETCHED BY CODE — the index holds 2 provisions for "
                   "ssi/1901/3, and none of them is a schedule or an annex: the Schedule is "
                   "not one of them. This search's results left it out for that reason.]")
    assert asked and asked[0][0] == "/section/lookup"


def test_unlabelled_with_one_schedule_hands_it_over_whole(monkeypatch):
    rows = [PROVISIONS[0], _prow("schedule", SCHED_2_TEXT.replace("SCHEDULE 2", "SCHEDULE"))]
    _route_lex(monkeypatch, provisions=(200, rows))
    out = _route("the Schedule widgets", monkeypatch=monkeypatch)
    assert "the index holds the Schedule of ssi/1901/3 as one provision" in out
    assert "Below is the whole of the Schedule. It is the only schedule the index holds " \
           "for ssi/1901/3." in out
    assert "A fee may be refunded." in out and "one shilling" in out    # cut nothing
    numbered = [PROVISIONS[0], _prow("schedule/3", SCHED_3_TEXT), PROVISIONS[4]]
    _route_lex(monkeypatch, provisions=(200, numbered))
    out3 = _route("schedule of forms", monkeypatch=monkeypatch)
    assert "Below is the whole of Schedule 3. It is the only schedule" in out3


def test_unlabelled_with_two_or_more_schedules_does_nothing(monkeypatch):
    asked = _route_lex(monkeypatch)                     # Schedules 2, 3 and 4
    assert _route("the Schedule widgets", monkeypatch=monkeypatch) == ""
    assert asked and asked[0][0] == "/section/lookup"   # fetched, then nothing said
    _route_lex(monkeypatch, provisions=(200, [PROVISIONS[0], PROVISIONS[4]]))
    assert _route("the Schedule", monkeypatch=monkeypatch) == ""   # annexes, no schedule


def test_unlabelled_does_not_fire_when_a_schedule_row_is_in_the_results(monkeypatch):
    asked = _route_lex(monkeypatch)
    assert _route("the Schedule widgets", results=_search_result("schedule/2"),
                  monkeypatch=monkeypatch) == ""
    assert _route("schedules to the Widget Order", monkeypatch=monkeypatch) == ""
    assert asked == []


def test_unlabelled_on_a_failed_or_short_list_says_nothing(monkeypatch):
    asked = _route_lex(monkeypatch, provisions=(503, {"detail": "busy"}))
    assert _route("the Schedule", monkeypatch=monkeypatch) == ""
    assert [p for p, _ in asked] == ["/section/lookup"]        # no text fallback
    monkeypatch.setattr(executor, "PROVISION_LIST_LIMIT", 1)
    _route_lex(monkeypatch, provisions=(200, PROVISIONS[:1]))
    assert _route("the Schedule", monkeypatch=monkeypatch) == ""


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


# --- batch 9 A: the per-run slot is reserved before the fetch's await ---------
#
# `chat_loop` runs one round's tool calls as concurrent tasks. The route used
# to check its bound and its one-fetch-per-instrument memo before the fetch's
# await and write the result after it, so every call of a batched round passed
# the check (Session 40's sweep: 6 list reads against a bound of 5).

def _slow_lex(monkeypatch, provisions=(200, PROVISIONS), text=(200, None), gate=None):
    """`_route_lex`, except that every call yields before it answers, as a
    real fetch does, so the calls of one gathered round overlap. With `gate`
    (a dict), every answer waits for `gate["ev"]`, an asyncio.Event the test
    makes inside its running loop."""
    asked = []

    async def fake(client, method, url, *, name="", **kwargs):
        path = url.split("/legislation", 1)[-1]
        asked.append(path)
        if gate is not None:
            await gate["ev"].wait()
        else:
            await asyncio.sleep(0.01)
        status, body = provisions if path == "/section/lookup" else text
        return httpx.Response(status, json=body, request=httpx.Request(method, url))

    monkeypatch.setattr(executor, "_request_with_retry", fake)
    return asked


def _route_env(monkeypatch, threshold=8000):
    """The patches `_route` makes, for tests that build their own round."""
    from src.agent import provider_factory
    monkeypatch.setattr(provider_factory, "get_summarise_threshold", lambda *a, **k: threshold)

    async def fake_summarise(text, q, model, **kw):
        return "SUMMARY.", False
    monkeypatch.setattr(agent_shared, "summarise_for_query", fake_summarise)


def _route_coro(query, fetches, lid=LID):
    return agent_shared.schedule_route_block(
        "search_legislation_sections", {"legislation_id": lid, "query": query},
        _search_result("article/1"), "q", fetches)


def _run(main, seconds=10):
    """`asyncio.run` with a deadline, so a call left waiting on a slot that
    is never resolved fails the test instead of hanging it."""
    return asyncio.run(asyncio.wait_for(main(), seconds))


def _gathered(*coros):
    async def main():
        return await asyncio.gather(*coros)
    return _run(main)


def test_a_round_of_searches_on_one_instrument_makes_one_fetch(monkeypatch):
    asked = _slow_lex(monkeypatch)
    _route_env(monkeypatch)
    seq_4 = _route("Schedule 2 paragraph 4", monkeypatch=monkeypatch)
    seq_3 = _route("Schedule 3", monkeypatch=monkeypatch)
    asked.clear()
    fetches = {}
    outs = _gathered(_route_coro("Schedule 2 paragraph 4", fetches),
                     _route_coro("Schedule 3", fetches),
                     _route_coro("Schedule 2 paragraph 4", fetches))
    assert asked == ["/section/lookup"]
    # Every call reads what it would have read alone.
    assert outs == [seq_4, seq_3, seq_4] and "A fee may be refunded." in seq_4
    # The slot holds the outcome once the round is over, never the in-flight marker.
    assert list(fetches) == [LID] and fetches[LID]["status"] == "ok"


def test_a_round_on_more_instruments_than_the_bound_fetches_only_the_bound(monkeypatch):
    asked = _slow_lex(monkeypatch)
    _route_env(monkeypatch)
    n = agent_shared.MAX_PROVISION_FETCHES
    lids = [f"ssi/1901/{k}" for k in range(10, 11 + n)]           # n + 1 instruments
    fetches = {}
    outs = _gathered(*[_route_coro("Schedule 2 paragraph 4", fetches, lid=x) for x in lids])
    assert asked == ["/section/lookup"] * n
    # The first n to reach the route are fetched; the last is refused as today.
    assert [bool(o) for o in outs] == [True] * n + [False]
    assert len(fetches) == n and lids[-1] not in fetches


def test_a_round_on_six_instruments_reads_all_six(monkeypatch):
    """Batch 9 A (user decision, 2026-10-06): the provision-list bound is its
    own constant, 8, so the shape Session 40's sweep met (six instruments in
    one Deep Research round, the most any stored run holds) reads every list,
    as it did live. P3.7's own bounds stay at 5."""
    from src.utils import instrument_lookup
    assert agent_shared.MAX_PROVISION_FETCHES == 8
    assert instrument_lookup.MAX_ROUTED_LOOKUPS == 5 == instrument_lookup.MAX_SECTION_LOOKUPS
    asked = _slow_lex(monkeypatch)
    _route_env(monkeypatch)
    fetches = {}
    outs = _gathered(*[_route_coro("Schedule 2 paragraph 4", fetches, lid=f"ssi/1901/{k}")
                       for k in range(10, 16)])
    assert asked == ["/section/lookup"] * 6
    assert all("Paragraph 4 of Schedule 2, cut at its own heading" in o for o in outs)


def test_a_failed_list_and_its_fallback_text_are_fetched_once_for_a_round(monkeypatch):
    whole = SECTIONS + "\n\n" + SCHED_1 + "\n\n" + SCHED_2_TEXT + "\n\nSCHEDULE 3 FORMS\n1) A."
    asked = _slow_lex(monkeypatch, provisions=(503, {"detail": "busy"}), text=(200, _record(whole)))
    _route_env(monkeypatch)
    seq = _route("Schedule 2 paragraph 4", monkeypatch=monkeypatch)
    assert "did not come back, so code cut Schedule 2" in seq
    asked.clear()
    fetches = {}
    outs = _gathered(_route_coro("Schedule 2 paragraph 4", fetches),
                     _route_coro("Schedule 2 paragraph 4", fetches),
                     _route_coro("Schedule 3", fetches))
    assert asked == ["/section/lookup", "/text"]
    assert outs[0] == outs[1] == seq and "1) A." in outs[2]
    # A failed list is recorded in its slot, as before: it counts against the
    # bound, is not fetched again, and establishes nothing for P3.1's cap.
    assert fetches[LID]["status"] == "failed" and isinstance(fetches[LID]["text"], str)
    assert agent_shared.held_provision_list(fetches, {"legislation_id": LID}) is None
    fetches.update({f"ssi/1901/{k}": {"status": "failed", "text": None}
                    for k in range(10, 9 + agent_shared.MAX_PROVISION_FETCHES)})
    assert asyncio.run(_route_coro("Schedule 2", fetches, lid="ssi/1901/99")) == ""
    assert asked == ["/section/lookup", "/text"]


@pytest.mark.parametrize("text_ok", [True, False])
def test_a_failed_list_is_not_read_again_in_a_later_round(monkeypatch, text_ok):
    """A failed list read stays recorded for the run, as batch 8 A's "fetch
    failed" case always had it: a later round's calls on the same instrument
    make no further list or text read and get the same output, whether the
    fallback text came back or not. (The integrator's mutant: a finished
    failed slot not treated as memoised, so it was read again.)"""
    whole = SECTIONS + "\n\n" + SCHED_1 + "\n\n" + SCHED_2_TEXT + "\n\nSCHEDULE 3 FORMS\n1) A."
    text = (200, _record(whole)) if text_ok else (503, {"detail": "busy"})
    asked = _slow_lex(monkeypatch, provisions=(503, {"detail": "busy"}), text=text)
    _route_env(monkeypatch)
    fetches = {}
    (first,) = _gathered(_route_coro("Schedule 2 paragraph 4", fetches))         # round 1
    assert asked == ["/section/lookup", "/text"]
    if text_ok:
        assert "did not come back, so code cut Schedule 2" in first
    else:
        assert "could fetch Schedule 2 neither from it nor from the whole text" in first
    later = _gathered(_route_coro("Schedule 2 paragraph 4", fetches),            # round 2
                      _route_coro("Schedule 2 paragraph 4", fetches))
    assert asked == ["/section/lookup", "/text"]
    assert later == [first, first]
    assert fetches[LID]["status"] == "failed" and len(fetches) == 1


def test_an_in_flight_slot_is_counted_and_is_never_a_complete_list(monkeypatch):
    """Batch 8 A2's reader (P3.1's cap text) states a list only from a slot
    holding a complete outcome; a slot reserved for a read still in flight
    must read as no list at all, and the refusal stay exactly as before."""
    from src.utils.discovery_budget import new_search_budget, section_stop_message, set_react_round
    gate = {}
    three = [{"uri": f"{URI}/article/{i}", "text": f"Section {i}) x"} for i in (1, 2, 3)]
    _slow_lex(monkeypatch, provisions=(200, three), gate=gate)
    _route_env(monkeypatch)
    set_request_provider_config({"_provider": "openrouter", "model": "test-model"})
    args = {"legislation_id": LID}

    async def main():
        gate["ev"] = asyncio.Event()
        fetches = {}
        task = asyncio.create_task(_route_coro("the Schedule", fetches))
        await asyncio.sleep(0.02)                     # the route now awaits its read
        assert list(fetches) == [LID]                 # reserved, so the bound counts it
        assert agent_shared.held_provision_list(fetches, args) is None
        assert su.provision_list_facts(fetches[LID]) is None
        budget = new_search_budget("legislation_only")
        budget["section_rounds"][LID] = {0, 1, 2}
        set_react_round(3)
        stop = await agent_shared.run_worker_tool(
            "search_legislation_sections", {"legislation_id": LID, "query": "widgets"},
            "q", None, "m", search_budget=budget, search_log=[], provision_fetches=fetches)
        assert stop == section_stop_message(budget, {"legislation_id": LID})
        assert "provision_list" not in json.loads(stop)
        gate["ev"].set()
        out = await task
        assert "none of them is a schedule or an annex" in out
        assert agent_shared.held_provision_list(fetches, args) == {"provisions": 3, "units": []}

    try:
        _run(main)
    finally:
        set_request_provider_config({})


def test_a_cancelled_read_releases_its_slot_and_its_waiters_get_nothing(monkeypatch):
    gate = {}
    asked = _slow_lex(monkeypatch, gate=gate)
    _route_env(monkeypatch)

    async def main():
        gate["ev"] = asyncio.Event()
        fetches = {}
        owner = asyncio.create_task(_route_coro("Schedule 2 paragraph 4", fetches))
        await asyncio.sleep(0.02)
        waiter = asyncio.create_task(_route_coro("Schedule 2 paragraph 4", fetches))
        await asyncio.sleep(0.02)
        owner.cancel()
        with pytest.raises(asyncio.CancelledError):
            await owner
        # The read it waited on was abandoned: nothing appended, and no hang.
        assert await asyncio.wait_for(waiter, 1) == ""
        # Released: nothing established, nothing counted against the bound.
        assert fetches == {}
        assert agent_shared.held_provision_list(fetches, {"legislation_id": LID}) is None
        gate["ev"].set()
        again = await _route_coro("Schedule 2 paragraph 4", fetches)
        assert "Paragraph 4 of Schedule 2, cut at its own heading" in again
        assert fetches[LID]["status"] == "ok"

    _run(main)
    assert asked == ["/section/lookup", "/section/lookup"]


def test_a_waiter_cancelled_mid_read_costs_no_other_call_its_result(monkeypatch):
    gate = {}
    asked = _slow_lex(monkeypatch, gate=gate)
    _route_env(monkeypatch)

    async def main():
        gate["ev"] = asyncio.Event()
        fetches = {}
        owner = asyncio.create_task(_route_coro("Schedule 2 paragraph 4", fetches))
        await asyncio.sleep(0.02)
        gone = asyncio.create_task(_route_coro("Schedule 2 paragraph 4", fetches))
        other = asyncio.create_task(_route_coro("Schedule 3", fetches))
        await asyncio.sleep(0.02)
        gone.cancel()
        gate["ev"].set()
        outs = await asyncio.gather(owner, other)
        assert gone.cancelled()
        assert "Paragraph 4 of Schedule 2, cut at its own heading" in outs[0]
        assert "Below is the whole of Schedule 3" in outs[1]
        assert fetches[LID]["status"] == "ok"

    _run(main)
    assert asked == ["/section/lookup"]


def test_calls_one_at_a_time_read_what_they_read_before(monkeypatch):
    """The sequential case, unchanged: each call finds its slot either empty
    or holding an outcome, and every slot ends as a plain outcome. (This
    passes on the code before batch 9 A too, by design: the sequential
    behaviour is the specification. The dry run's sequential mode is the
    evidence over the stored runs.)"""
    asked = _slow_lex(monkeypatch)
    _route_env(monkeypatch)
    fetches = {}
    outs = [asyncio.run(_route_coro(q, fetches, lid=x)) for q, x in (
        ("Schedule 2 paragraph 4", LID), ("Schedule 3", LID), ("Schedule 7", LID),
        ("Annex II Chapter II", "ssi/1901/4"), ("Schedule 2", "ssi/1901/5"))]
    assert asked == ["/section/lookup"] * 3
    assert "Paragraph 4 of Schedule 2, cut at its own heading" in outs[0]
    assert "Below is the whole of Schedule 3" in outs[1]
    assert "Schedule 7 is not one of them" in outs[2]
    assert "Chapter II of Annex II, cut at its heading" in outs[3]
    assert list(fetches) == [LID, "ssi/1901/4", "ssi/1901/5"]
    assert all(isinstance(v, dict) and v["status"] == "ok" for v in fetches.values())


@pytest.mark.asyncio
async def test_a_gathered_round_through_run_worker_tool_reads_one_list(monkeypatch):
    """The real path: two section searches of one round, run as `chat_loop`
    runs them, through `run_worker_tool`."""
    asked = _slow_lex(monkeypatch)
    _route_env(monkeypatch)

    async def fake_exec(name, args, on_chunk=None, timing_collector=None, worker_call=False):
        await asyncio.sleep(0)
        return _search_result("article/1")

    set_request_provider_config({"_provider": "openrouter", "model": "test-model"})
    try:
        monkeypatch.setattr(agent_shared, "execute_worker_tool", fake_exec)
        fetches = {}
        outs = await asyncio.wait_for(asyncio.gather(*[agent_shared.run_worker_tool(
            "search_legislation_sections", {"legislation_id": LID, "query": q}, "q", None, "m",
            provision_fetches=fetches) for q in ("Schedule 2 paragraph 4", "Schedule 3")]), 10)
    finally:
        set_request_provider_config({})
    assert asked == ["/section/lookup"]
    assert "A fee may be refunded." in outs[0] and "Below is the whole of Schedule 3" in outs[1]


# --- batch 10 A: a schedule too large to hand over whole, no paragraph named --
#
# Session 41's sweep: every Worker query named the Schedule alone, so the route
# summarised the whole of it, and the summary kept some paragraphs and dropped
# others. Now such a schedule goes over as its paragraph headings and the
# paragraphs whose headings share a distinctive word with the section search's
# query, cut by `cut_schedule_paragraph`'s rules; the summary stays where
# nothing matches, a match cannot be cut, or the cuts exceed the bound.

SCHED_5_TEXT = (
    "SCHEDULE 5 WIDGET LICENSING Article 4\n\n"
    "Section 1) **Registration**\n1) A widget is registered by the registrar.\n"
    "2) A registration lasts a year.\n"
    "Section 3) **Licences**\n1) A licence is required to sell a widget.\n"
    "Section 4) **Suspension of licences**\n1) The registrar may suspend a licence.\n"
    "Section 5) **Revocation of  licences**\n1) The registrar may revoke a licence.\n"
    "Section 6) **Appeal against revocation**\n1) An appeal lies to the sheriff.\n"
    "Section 7) ****\n1) Untitled words.\n"
    "Section 8) **Fees for licences**\n1) The fee is a crown.\n"
    "Section 9) **Ox carts [repealed]**\n1) Carts drawn by oxen are exempt.\n"
)
SCHED_5 = [_prow("article/1", "Section 1) **Citation**\ntext", "section"),
           _prow("schedule/5", SCHED_5_TEXT)]
_MATCHED_TAIL = ("Schedule 5 runs to {n:,} characters, longer than one result hands over whole, "
                 "so below are its paragraph headings, in order, and then each paragraph whose "
                 "heading shares a word with this search's query, cut from the retrieved text "
                 "and labelled. To read another headed paragraph in its own words, name "
                 "Schedule 5 and its number from the list below in a section search: code cuts it "
                 "out the same way.")


def _route5(monkeypatch, query, threshold=50, text=SCHED_5_TEXT, budget=None, seen=None):
    _route_lex(monkeypatch, provisions=(200, [SCHED_5[0], _prow("schedule/5", text)]))
    return _route(query, threshold=threshold, summary=seen if seen is not None else [],
                  monkeypatch=monkeypatch, budget=budget)


def test_a_large_schedule_named_alone_goes_as_headings_and_matched_paragraphs(monkeypatch):
    seen = []
    urls = set()
    _route_lex(monkeypatch, provisions=(200, SCHED_5))
    out = _route("Schedule 5 revocation of licences", threshold=50, summary=seen,
                 monkeypatch=monkeypatch, urls=urls)
    assert out.startswith("\n\n[PROVISION FETCHED BY CODE — the index holds Schedule 5 of "
                          "ssi/1901/3 as one provision")
    assert _MATCHED_TAIL.format(n=len(SCHED_5_TEXT)) + "]\n" in out
    assert ("The paragraph headings of Schedule 5, in order, each after the number of the "
            "paragraph it opens:\n1: Registration\n3: Licences\n4: Suspension of licences\n"
            "5: Revocation of licences\n6: Appeal against revocation\n7: (untitled)\n"
            "8: Fees for licences\n9: Ox carts (repealed)\n\n") in out
    assert "Paragraph 5 of Schedule 5, cut at its own heading and the next one:\n" in out
    assert "Paragraph 6 of Schedule 5, cut at its own heading and the next one:\n" in out
    assert "may revoke a licence" in out and "appeal lies to the sheriff" in out
    # Only the matched paragraphs' text, never the rest of the schedule.
    for absent in ("may suspend", "lasts a year", "a crown", "oxen", "required to sell"):
        assert absent not in out, absent
    assert seen == []                       # the summariser was not called
    assert out.rstrip().endswith("[/PROVISION FETCHED BY CODE]")
    assert any(u.endswith("ssi/1901/3/schedule/5") for u in urls), urls
    header = out.strip().split("\n", 1)[0]
    assert header.count("[") == 1 and header.count("]") == 1, header
    assert strip_scope_blocks("Answer." + out) == ("Answer.", 1)


def test_a_cross_heading_over_several_paragraphs_is_cut_as_a_labelled_span(monkeypatch):
    out = _route5(monkeypatch, "Schedule 5 registration")
    assert ("The text of Schedule 5 from the heading of paragraph 1 to the next headed "
            "paragraph. It runs through paragraphs 1 to 2, because the paragraphs after 1 in "
            "it carry no heading of their own:\n") in out
    assert "A registration lasts a year." in out and "required to sell" not in out


@pytest.mark.parametrize("query", [
    "Schedule 5 licences",         # in four headings: not distinctive
    "Schedule 5 widgets",          # in no heading
    "Schedule 5 for",              # a stop word, in one heading
    "Schedule 5 ox",               # two letters, in one heading
])
def test_a_query_with_no_distinctive_heading_word_is_summarised(monkeypatch, query):
    seen = []
    out = _route5(monkeypatch, query, seen=seen)
    assert seen == [len(SCHED_5_TEXT)]
    assert (f"Code retrieved the whole of Schedule 5, {len(SCHED_5_TEXT):,} characters, and "
            "below is a summary of that retrieved text") in out
    assert "paragraph headings" not in out and "SUMMARY." in out


def test_a_plural_in_the_query_matches_a_singular_heading(monkeypatch):
    out = _route5(monkeypatch, "Schedule 5 appeals")
    assert "Paragraph 6 of Schedule 5, cut at its own heading" in out
    assert "may revoke" not in out


def test_word_stems_and_distinctiveness():
    assert su._word_stems("Penalties licences class of the OX") == {
        "penalty", "licence", "class"}
    heads = [("1", "Widget fees"), ("2", "Widget forms"), ("3", "Widget seals"),
             ("4", "Gadget fees"), ("5", "Gadget forms"), ("6", "Gadget seals"),
             ("7", "Gadget rates"), ("8", "Abc rules")]
    unit = su.ScheduleUnit("schedule", "5")
    assert su.heading_matches(heads, "widget", unit) == ["1", "2", "3"]     # in three: kept
    assert su.heading_matches(heads, "gadget", unit) == []                 # in four: dropped
    assert su.heading_matches(heads, "gadget seals", unit) == ["3", "6"]
    # The unit's own label is never a query word.
    assert su.heading_matches(heads, "Schedule ABC1", su.ScheduleUnit("schedule", "ABC1")) == []
    assert su.heading_matches(heads, "abc", unit) == ["8"]


def test_a_matched_paragraph_that_cannot_be_cut_sends_the_summary(monkeypatch):
    twice = SCHED_5_TEXT + "Section 6) **Appeal again**\n1) Repeated.\n"
    seen = []
    out = _route5(monkeypatch, "Schedule 5 revocation", text=twice, seen=seen)
    assert seen == [len(twice)] and "paragraph headings" not in out
    assert su.matched_pieces(su.ScheduleUnit("schedule", "5"), twice, "revocation",
                             10_000) is None


def test_cuts_over_the_bound_send_the_summary(monkeypatch):
    unit = su.ScheduleUnit("schedule", "5")
    pieces = su.matched_pieces(unit, SCHED_5_TEXT, "revocation", 10_000)
    cut = sum(len(t) for _, t in pieces[1:])
    assert [lbl.split(",")[0] for lbl, _ in pieces[1:]] == ["Paragraph 5 of Schedule 5",
                                                            "Paragraph 6 of Schedule 5"]
    assert su.matched_pieces(unit, SCHED_5_TEXT, "revocation", cut) is not None
    assert su.matched_pieces(unit, SCHED_5_TEXT, "revocation", cut - 1) is None
    # Through the route: the bound is the threshold or MATCHED_CUTS_MIN_CHARS,
    # whichever is larger.
    monkeypatch.setattr(agent_shared, "MATCHED_CUTS_MIN_CHARS", 10)
    seen = []
    out = _route5(monkeypatch, "Schedule 5 revocation", threshold=cut - 1, seen=seen)
    assert seen and "paragraph headings" not in out
    out = _route5(monkeypatch, "Schedule 5 revocation", threshold=cut)
    assert "Paragraph 5 of Schedule 5, cut at its own heading" in out
    monkeypatch.setattr(agent_shared, "MATCHED_CUTS_MIN_CHARS", cut)
    out = _route5(monkeypatch, "Schedule 5 revocation", threshold=10)
    assert "Paragraph 5 of Schedule 5, cut at its own heading" in out


def test_the_matched_block_must_fit_the_context_budget(monkeypatch):
    unit = su.ScheduleUnit("schedule", "5")
    pieces = su.matched_pieces(unit, SCHED_5_TEXT, "revocation", 10_000)
    size = sum(len(lbl) + len(t) for lbl, t in pieces)
    out = _route5(monkeypatch, "Schedule 5 revocation", budget={"used": 0, "limit": size})
    assert "Paragraph 5 of Schedule 5, cut at its own heading" in out
    seen = []
    out = _route5(monkeypatch, "Schedule 5 revocation", budget={"used": 1, "limit": size},
                  seen=seen)
    assert seen and "paragraph headings" not in out


def test_a_schedule_under_the_threshold_but_over_the_budget_is_summarised_as_before(monkeypatch):
    """The lever is for a unit over the verbatim threshold. A smaller unit
    that only the context budget sends to the summariser is summarised as
    before, even where its matched paragraphs alone would fit."""
    unit = su.ScheduleUnit("schedule", "5")
    pieces = su.matched_pieces(unit, SCHED_5_TEXT, "revocation", 10_000)
    size = sum(len(lbl) + len(t) for lbl, t in pieces)
    assert size < len(SCHED_5_TEXT)
    seen = []
    out = _route5(monkeypatch, "Schedule 5 revocation", threshold=8000, seen=seen,
                  budget={"used": 0, "limit": size + 1})
    assert seen == [len(SCHED_5_TEXT)] and "paragraph headings" not in out


def test_a_named_paragraph_an_annex_or_a_chapter_never_takes_the_heading_path(monkeypatch):
    seen = []
    # A named paragraph with no heading of its own: the whole schedule,
    # summarised, with the reason; never the heading list.
    out = _route5(monkeypatch, "Schedule 5 paragraph 2 revocation", seen=seen)
    assert "Paragraph 2 has no single heading of its own in it to cut at." in out
    assert seen and "paragraph headings" not in out
    # An annex whose text carries the same heading lines.
    annex = SCHED_5_TEXT.replace("SCHEDULE 5", "ANNEX III")
    _route_lex(monkeypatch, provisions=(200, [_prow("annex/III", annex)]))
    out = _route("Annex III revocation", threshold=50, summary=[], monkeypatch=monkeypatch)
    assert "a summary of that retrieved text" in out and "paragraph headings" not in out
    for unit in (su.ScheduleUnit("annex", "III"),
                 su.ScheduleUnit("schedule", "5", paragraphs=("2",)),
                 su.ScheduleUnit("schedule", "5", chapter="II")):
        assert su.matched_pieces(unit, SCHED_5_TEXT, "revocation", 10_000) is None, unit
    assert su.matched_pieces(su.ScheduleUnit("schedule", "3"), SCHED_3_TEXT, "forms",
                             10_000) is None          # no heading line at all


def test_the_heading_path_also_serves_the_text_fallback_and_the_sole_schedule(monkeypatch):
    """Two forms no stored run reaches: the unit cut out of the whole text
    after a failed provision list, and "the Schedule" with no label where it
    is the instrument's only one."""
    whole = SECTIONS + "\n\n" + SCHED_5_TEXT
    _route_lex(monkeypatch, provisions=(503, {"detail": "busy"}), text=(200, _record(whole)))
    out = _route("Schedule 5 revocation", threshold=50, summary=[], monkeypatch=monkeypatch)
    assert "did not come back, so code cut Schedule 5 out of the instrument's whole text" in out
    assert "Paragraph 5 of Schedule 5, cut at its own heading" in out
    assert "The paragraph headings of Schedule 5, in order" in out
    _route_lex(monkeypatch, provisions=(200, [SCHED_5[0], _prow("schedule", SCHED_5_TEXT)]))
    out = _route("the Schedule revocation", threshold=50, summary=[], monkeypatch=monkeypatch)
    assert ("The paragraph headings of the Schedule, in order" in out
            and "Paragraph 5 of the Schedule, cut at its own heading" in out)
    assert out.split("\n", 3)[2].endswith(
        "It is the only schedule the index holds for ssi/1901/3.]")


def test_a_summarised_cut_says_it_is_the_cut_that_was_summarised(monkeypatch):
    _route_lex(monkeypatch)
    out = _route("Schedule 2 paragraph 4", threshold=20, summary=[], monkeypatch=monkeypatch)
    assert ("Code retrieved the whole of Schedule 2 and cut out the parts of it this search "
            "named,") in out
    assert "below is a summary of those retrieved parts" in out
    assert "paragraph headings" not in out


def test_the_heading_list_is_capped_and_cleaned():
    long_head = "Widget " + "very " * 60 + "long"
    text = "SCHEDULE 7 MANY\n" + "".join(
        f"Section {n}) **{'Gizmo rules' if n == 1 else long_head if n == 2 else f'Heading {n}'}**"
        f"\n1) Words {n}.\n" for n in range(1, 161))
    pieces = su.matched_pieces(su.ScheduleUnit("schedule", "7"), text, "gizmo", 100_000)
    label, body = pieces[0]
    lines = body.split("\n")
    assert len(lines) == 151 and lines[-1] == "and 10 more headings after paragraph 150"
    assert lines[0] == "1: Gizmo rules" and lines[149] == "150: Heading 150"
    assert lines[1].startswith("2: Widget very very") and len(lines[1]) == len("2: ") + 120
    assert [lbl.split(",")[0] for lbl, _ in pieces[1:]] == ["Paragraph 1 of Schedule 7"]


@pytest.mark.asyncio
async def test_the_matched_block_reaches_the_worker_through_run_worker_tool(monkeypatch):
    """The real path: the section search's own query is what the headings are
    matched against (the research question passed beside it is not)."""
    _route_lex(monkeypatch, provisions=(200, SCHED_5))
    from src.agent import provider_factory
    monkeypatch.setattr(provider_factory, "get_summarise_threshold", lambda *a, **k: 300)
    seen = []

    async def fake_summarise(text, q, model, **kw):
        seen.append(len(text))
        return "SUMMARY.", False

    async def fake_exec(name, args, on_chunk=None, timing_collector=None, worker_call=False):
        return _search_result("article/1")

    monkeypatch.setattr(agent_shared, "summarise_for_query", fake_summarise)
    monkeypatch.setattr(agent_shared, "execute_worker_tool", fake_exec)
    set_request_provider_config({"_provider": "openrouter", "model": "test-model"})
    try:
        out = await agent_shared.run_worker_tool(
            "search_legislation_sections",
            {"legislation_id": LID, "query": "Schedule 5 appeal against revocation"},
            "Which fees apply to widget licences?", None, "m", provision_fetches={},
            context_budget={"used": 0, "limit": 250_000})
    finally:
        set_request_provider_config({})
    assert out.startswith(_search_result("article/1"))
    assert _MATCHED_TAIL.format(n=len(SCHED_5_TEXT)) in out
    assert "appeal lies to the sheriff" in out and "a crown" not in out
    assert seen == []


def test_every_matched_variant_reads_as_held_to_the_schedule_grader():
    """`replay_report.sched_unit_clauses` must class no clause of the new
    wording as a negative (INDEX, TEXT, NEG) or a limit or offer: the unit is
    held and was retrieved."""
    import re
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools import replay_report as rr

    unit = su.ScheduleUnit("schedule", "5")
    url = f"{URI}/schedule/5"
    texts = []
    for source in (su.FROM_LIST, su.FROM_TEXT):
        for reason in ("", su.sole_schedule_reason(LID),
                       "Paragraph 2 has no single heading of its own in it to cut at."):
            texts.append(su.fetched_block(LID, unit, url, [("", "")], su.MATCHED,
                                          reason=reason, total_chars=92066, source=source))
            for of in (su.WHOLE, su.CUT):
                texts.append(su.fetched_block(LID, unit, url, [("", "")], su.SUMMARY,
                                              reason=reason, total_chars=92066, source=source,
                                              summary_of=of))
    texts += [su.matched_pieces(unit, SCHED_5_TEXT, "revocation", 10_000)[0][0],
              "and 10 more headings after paragraph 150", "7: (untitled)"]
    unit_rx = re.compile(r"\b(?:schedules?|annex(?:es)?)\b", re.I)
    for text in texts:
        classes = {c for c, _, _ in rr.sched_unit_clauses(text, unit_rx)}
        assert classes <= {""}, (classes, text)
        assert not rr.SCHED_LIMIT.search(text), text
        assert not rr._P312_NOT_DELIVERED.search(text), text
        assert not re.search(r"\bnot\b[^.]{0,40}\bretriev", text, re.I), text
