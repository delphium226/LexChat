"""P4.3 (B8), V4: the Worker seam's Sources-rail filter.

`agent_core.filter_worker_sources` / `_source_is_used` and `utils/source_naming`.
Before P4.3 the filter kept a source on an excerpt or an exact token, and when
that kept nothing it fell back to the WHOLE accumulator (batch 10 C: 67% of the
unused sources on report turns). Now: no fall-back on the legislation bot; a
source the report names in words is kept; a legislation source's `sub` (a
section heading) is no longer a token; and every token must stand alone.

Every input form here is one batch 10 C listed (`notes/batch10_C.md` section 4)
or batch 11 C found, in synthetic text only: an id that prefixes another, a short
form, a case by party name alone (and its appeal), a Welsh title, a comma before
the year, the three number forms, a title inside a longer title.
"""
import json

import pytest

from src.agent.agent_core import (
    _source_is_used,
    filter_worker_sources,
    run_worker_agent,
)
from src.agent.provider_factory import set_request_provider_config
from src.utils import source_naming as sn


def _leg(lid, title, **kw):
    """A legislation source as `_extract_sources_inner` builds a search hit."""
    return {"_lid": lid, "kind": kw.pop("kind", "SI"), "title": title,
            "url": f"https://www.legislation.gov.uk/{lid}", "cite": lid, **kw}


def _case(title, ncn, path):
    return {"kind": "Case", "title": title, "sub": ncn, "cite": ncn,
            "url": f"https://caselaw.nationalarchives.gov.uk/{path}"}


# --- an id that prefixes another ------------------------------------------------

def test_an_id_that_prefixes_another_is_not_cited_by_it():
    src = _leg("ssi/1901/3", "Widget Order 1901")
    report = "See [reg 2](https://www.legislation.gov.uk/ssi/1901/31/regulation/2)."
    assert not _source_is_used(src, report)
    assert _source_is_used(src, report.replace("1901/31/", "1901/3/"))


def test_a_neutral_citation_that_prefixes_another_is_not_cited_by_it():
    src = _case("Widget Co v Example Ltd", "[1901] UKSC 1", "uksc/1901/1")
    assert not _source_is_used(src, "As held in Gadget Ltd v Other [1901] UKSC 12.")
    assert _source_is_used(src, "As held in [1901] UKSC 1, the duty is strict.")


def test_token_guards_apply_only_on_a_side_that_ends_in_a_letter_or_digit():
    assert sn.token_in("[1901] UKSC 1", "x[1901] UKSC 1 y")      # "[" needs no guard
    assert not sn.token_in("ssi/1901/3", "wssi/1901/3 y")          # lead guard
    assert not sn.token_in("ssi/1901/3", "ssi/1901/3a")            # trail guard
    assert sn.token_in("ssi/1901/3", "ssi/1901/3a ssi/1901/3.")    # a later occurrence counts
    assert not sn.token_in("abcde", "abcde")                       # under the 6-char floor
    assert sn.token_in("abcdef", "abcdef")
    assert not sn.token_in("ssi/1901/3", "")
    assert not sn.token_in("ssi/1901/3", None)
    assert not sn.token_in(None, "ssi/1901/3")


# --- a legislation source's `sub` is not a token ---------------------------------

def test_a_section_heading_does_not_keep_a_legislation_source():
    src = _leg("ssi/1901/3", "Widget Order 1901", sub="Interpretation")
    assert not _source_is_used(src, "Interpretation of the term is a matter for the court.")


def test_a_case_sub_is_still_its_neutral_citation():
    src = _case("Widget Co v Example Ltd", "[1901] EWHC 5 (Ch)", "ewhc/ch/1901/5")
    src["cite"] = ""   # only `sub` can match
    assert _source_is_used(src, "The point was decided in [1901] EWHC 5 (Ch).")


def test_a_parliamentary_source_keeps_its_sub_token():
    src = {"kind": "Committee", "title": "Widget Committee", "sub": "Widget Bill: Stage 1",
           "cite": "Widget Committee, 1901-01-01", "url": ""}
    assert _source_is_used(src, "Evidence was taken at Widget Bill: Stage 1.")
    assert not sn.named_in(src, "Widget Committee")     # no naming test for these kinds


# --- the report names the source in words -----------------------------------------

def test_a_title_named_in_words_keeps_the_source():
    src = _leg("ssi/1901/3", "The Widget Order 1901")
    assert _source_is_used(src, "The **Widget Order 1901** makes provision for this.")
    assert not _source_is_used(src, "The Gadget Order 1901 makes provision for this.")


def test_emphasis_inside_a_title_and_a_leading_the_are_normalised():
    src = _leg("ssi/1901/3", "The Widget Order 1901")
    assert _source_is_used(src, "The Widget *Order* 1901 applies.")
    assert _source_is_used(src, "Under Widget Order 1901, the duty is owed.")


def test_a_comma_before_the_year_still_names_the_title():
    src = _leg("ukpga/1901/3", "Widget Act 1901", kind="Act")
    assert _source_is_used(src, "Under the Widget Act, 1901, the duty is owed.")


def test_a_left_curly_quote_is_normalised():
    src = _leg("ssi/1901/3", "The 'Widget' Order 1901")
    assert _source_is_used(src, "the \u2018widget' order 1901 applies")


def test_curly_quotes_and_hard_spaces_are_normalised():
    src = _leg("ssi/1901/3", "The Widget\u2019s Order 1901")
    assert _source_is_used(src, "the widget's\u00a0order  1901 applies")


def test_a_title_inside_a_longer_title_does_not_name_it():
    act = _leg("asp/1901/3", "Widget (Scotland) Act 1901", kind="Act")
    order = _leg("ssi/1902/9", "The Widget (Scotland) Act 1901 (Commencement No. 1) Order 1902")
    report = ("The Widget (Scotland) Act 1901 (Commencement No. 1) Order 1902 "
              "brought section 2 into force.")
    assert not _source_is_used(act, report)
    assert _source_is_used(order, report)
    # Named on its own as well, the Act is kept.
    assert _source_is_used(act, report + " Section 2 of the Widget (Scotland) Act 1901 applies.")


def test_each_instrument_word_of_the_longer_title_guard():
    act = _leg("asp/1901/3", "Widget (Scotland) Act 1901", kind="Act")
    for word in ("Regulations", "Order", "Rules", "Scheme"):
        text = f"the Widget (Scotland) Act 1901 (Transitional Provisions) {word} 1902"
        assert not _source_is_used(act, text), word
    assert _source_is_used(act, "the Widget (Scotland) Act 1901 (asp 3) applies")


def test_a_title_must_not_run_on_into_a_longer_word():
    src = _leg("ssi/1901/3", "Widget Order 1901")
    assert not _source_is_used(src, "the widget order 19012 is different")
    assert not _source_is_used(src, "the megawidget order 1901 is different")


def test_a_welsh_title_is_named_and_not_as_the_head_of_a_longer_welsh_title():
    deddf = _leg("anaw/1901/3", "Deddf Teclynnau (Cymru) 1901", kind="Act")
    gorch = _leg("wsi/1901/7", "Gorchymyn Ŵyn a Theclynnau (Cymru) 1901")
    assert _source_is_used(gorch, "Mae Gorchymyn Ŵyn a Theclynnau (Cymru) 1901 yn gymwys.")
    longer = "Gorchymyn Deddf Teclynnau (Cymru) 1901 (Cychwyn Rhif 1) 1902"
    assert not _source_is_used(deddf, f"Daeth {longer} i rym.")
    assert _source_is_used(deddf, "Mae Deddf Teclynnau (Cymru) 1901 yn gymwys.")


def test_a_short_form_is_not_a_naming():
    """16 of 21 short-form candidates in the stored replays were "the YYYY Act"
    matching a commencement instrument's title, which names the parent Act."""
    src = _leg("asp/1901/3", "Widget (Scotland) Act 1901", kind="Act")
    assert not _source_is_used(src, "Section 2 of the 1901 Act applies.")


def test_a_short_title_or_a_bare_id_title_is_never_a_naming():
    assert not sn.title_named("widget", "a widget here")             # under 8 characters
    assert sn.title_named("widget o", "a widget o here")
    assert not sn.title_named("ssi/1901/3", "see ssi/1901/3 here")    # a bare id is a token


# --- the three number forms -------------------------------------------------------

def test_an_si_number_names_an_si():
    src = _leg("ssi/1901/3", "ssi/1901/3", kind="Statute")   # a change-record entry
    assert _source_is_used(src, "Section 2 was commenced by SSI 1901/3.")
    assert not _source_is_used(src, "Section 2 was commenced by SSI 1901/31.")
    assert not _source_is_used(src, "Directive 1901/3/EC applies.")
    assert not _source_is_used(src, "see 21901/3 above")


def test_an_si_number_does_not_name_an_act():
    act = _leg("asp/1901/3", "asp/1901/3", kind="Act")
    assert not _source_is_used(act, "commenced by SSI 1901/3")


def test_an_eu_number_names_an_eu_instrument():
    src = _leg("eur/1901/3", "eur/1901/3", kind="Statute")
    assert _source_is_used(src, "Regulation (EC) No 3/1901 governs the scheme.")
    assert not _source_is_used(src, "Regulation (EC) No 3/19012 governs the scheme.")
    assert not _source_is_used(src, "SSI 1901/3 governs the scheme.")


def test_an_old_si_number_names_an_si():
    src = _leg("uksi/1901/3", "uksi/1901/3", kind="Statute")
    assert _source_is_used(src, "The Widget Regulations (S.I. 1901 No. 3) apply.")
    assert _source_is_used(src, "made as 1901 no 3")
    assert not _source_is_used(src, "made as 1901 No. 33")


def test_an_old_si_whose_identifier_is_its_printed_number():
    src = {"_lid": "1901 No. 3 (S. 1)", "kind": "Statute", "title": "1901 No. 3 (S. 1)",
           "cite": "1901 No. 3 (S. 1)",
           "url": "https://www.legislation.gov.uk/id/1901 No. 3 (S. 1)"}
    assert sn.named_in(src, "The 1901 No. 3 order applies.")
    assert sn.named_in(src, "The order (S.I. 1901/3) applies.")
    assert not sn.named_in(src, "The order (S.I. 1901/31) applies.")
    src2 = dict(src, _lid="", title="")
    assert sn.named_in(src2, "made as 1901 No. 3")      # the cite carries the number


# --- a case by party name alone, and its appeal -----------------------------------

def test_a_case_named_by_its_parties_alone_is_kept():
    src = _case("Widget Co v Example Ltd", "[1901] EWHC 5 (Ch)", "ewhc/ch/1901/5")
    assert _source_is_used(src, "The leading authority is Widget Co v Example Ltd.")


def test_the_appeal_of_the_same_parties_does_not_keep_the_first_instance():
    first = _case("Widget Co v Example Ltd", "[1901] EWHC 5 (Ch)", "ewhc/ch/1901/5")
    appeal = _case("Widget Co v Example Ltd", "[1902] EWCA Civ 9", "ewca/civ/1902/9")
    report = "In Widget Co v Example Ltd & Anor [1902] EWCA Civ 9 the court held the duty strict."
    assert not _source_is_used(first, report)
    assert _source_is_used(appeal, report)


def test_an_appeal_linked_by_url_does_not_keep_the_first_instance():
    first = _case("Widget Co v Example Ltd", "[1901] EWHC 5 (Ch)", "ewhc/ch/1901/5")
    report = ("In [Widget Co v Example Ltd](https://caselaw.nationalarchives.gov.uk/"
              "ewca/civ/1902/9) the court held the duty strict.")
    assert not sn.named_in(first, report)
    assert sn.named_in(first, report.replace("ewca/civ/1902/9", "ewhc/ch/1901/5"))


def test_a_citation_in_the_next_sentence_does_not_decide_the_judgment():
    first = _case("Widget Co v Example Ltd", "[1901] EWHC 5 (Ch)", "ewhc/ch/1901/5")
    for stop in (". ", "; ", "\n"):
        report = f"See Widget Co v Example Ltd{stop}Gadget v Other [1902] EWCA Civ 9 differs."
        assert sn.named_in(first, report), repr(stop)


def test_a_citation_beyond_the_lookahead_does_not_decide_the_judgment():
    first = _case("Widget Co v Example Ltd", "[1901] EWHC 5 (Ch)", "ewhc/ch/1901/5")
    assert sn.CASE_LOOKAHEAD_CHARS == 100
    assert sn.named_in(first, "Widget Co v Example Ltd " + "x" * 100 + " [1902] EWCA Civ 9")
    assert not sn.named_in(first, "Widget Co v Example Ltd " + "x" * 60 + " [1902] EWCA Civ 9")
    assert not sn.named_in(first, "Widget Co v Example Ltd [1902] EWCA Civ 9")


def test_a_case_with_no_citation_of_its_own_is_kept_by_its_parties():
    src = _case("Widget Co v Example Ltd", "", "")
    assert sn.named_in(src, "Widget Co v Example Ltd [1902] EWCA Civ 9 held it.")
    src["url"] = ""
    assert sn.named_in(src, "[Widget Co v Example Ltd](https://caselaw.nationalarchives.gov.uk/"
                            "ewca/civ/1902/9) held it.")


def test_the_same_judgment_cited_after_the_parties_is_kept():
    src = _case("Widget Co v Example Ltd", "[1901] EWHC 5 (Ch)", "ewhc/ch/1901/5")
    src["cite"] = src["sub"] = "[1901] EWHC 5 (Ch)"
    assert sn.named_in(src, "widget co v example ltd [1901] ewhc 5 (ch) held it")


def test_a_case_title_is_not_guarded_as_a_legislation_title():
    src = _case("Widget Co v Example Ltd", "", "")
    assert sn.named_in(src, "Widget Co v Example Ltd (Costs) Order was made")


# --- excerpt, and an empty report -------------------------------------------------

def test_a_retrieved_source_is_kept_whatever_the_report_says():
    src = _leg("ssi/1901/3", "Widget Order 1901", excerpt="1. This Order may be cited")
    assert _source_is_used(src, "")


def test_named_in_with_no_text_is_false():
    assert not sn.named_in(_leg("ssi/1901/3", "Widget Order 1901"), "")
    assert not sn.named_in(_leg("ssi/1901/3", "Widget Order 1901"), None)
    assert not sn.named_in(_case("Widget Co v Example Ltd", "", ""), None)


# --- the fall-back ----------------------------------------------------------------

def test_a_report_vouching_for_nothing_adds_nothing_to_the_rail():
    acc = [_leg("ssi/1901/3", "Widget Order 1901"), _leg("ssi/1901/4", "Gadget Order 1901")]
    kept, nothing = filter_worker_sources(acc, "No instrument on point was located.",
                                          "legislation_only")
    assert kept == [] and nothing is True
    for mode in ("case_law_only", "legislation_and_case_law"):
        assert filter_worker_sources(acc, "none", mode) == ([], True)


def test_the_parliamentary_bots_keep_their_fall_back():
    """No stored replay ran on either: dropping their fall-back is unmeasured."""
    acc = [{"kind": "Committee", "title": "Widget Committee", "sub": "", "cite": "c",
            "url": "https://example.invalid/1"}]
    for mode in ("parliamentary_records", "westminster_records"):
        kept, nothing = filter_worker_sources(acc, "nothing cited", mode)
        assert kept == acc and kept is not acc and nothing is True


def test_a_named_source_is_kept_beside_a_linked_one():
    linked = _leg("ssi/1901/3", "Widget Order 1901")
    named = _leg("ssi/1901/4", "Gadget Order 1901")
    other = _leg("ssi/1901/5", "Sprocket Order 1901")
    report = ("[Widget Order 1901](https://www.legislation.gov.uk/ssi/1901/3) applies, "
              "as does the Gadget Order 1901.")
    kept, nothing = filter_worker_sources([linked, named, other], report, "legislation_only")
    assert kept == [linked, named] and nothing is False


# --- the wiring in run_worker_agent ------------------------------------------------

class _Timing:
    def __init__(self):
        self.source_stats = []

    def record_source_stats(self, extracted, kept, fallback):
        self.source_stats.append((extracted, kept, fallback))

    def __getattr__(self, name):          # every other counter: a no-op
        return lambda *a, **k: None


def _search(n):
    return {"results": [
        {"legislation_id": f"ssi/1901/{i}", "title": f"Widget Order 1901 No {i}",
         "url": f"https://www.legislation.gov.uk/ssi/1901/{i}", "text_version": "revised",
         "year": 1901, "extent": ["Scotland"]} for i in range(1, n + 1)],
        "returned": n, "total": n, "total_matched": n, "removed_by_filters": 0}


async def _run_worker(monkeypatch, report, research_mode="legislation_only"):
    from src.agent import agent_shared

    set_request_provider_config({
        "_provider": "openrouter", "_research_mode": research_mode,
        "_chat_mode": "conversational", "model": "test-model", "_tool_memo_enabled": False,
    })

    async def fake_exec(name, args, on_chunk=None, timing_collector=None, worker_call=False):
        return json.dumps(_search(3))

    async def chat_loop(messages, model, cancel_event, num_ctx, tools, executor,
                        on_chunk=None, emit_tool_details=False, timing_collector=None,
                        worker_call=False):
        await executor("search_legislation", {"query": "widget"})
        return {"role": "assistant", "content": report}

    monkeypatch.setattr(agent_shared, "execute_worker_tool", fake_exec)
    timing = _Timing()
    try:
        result = await run_worker_agent(chat_loop, lambda *a, **k: None, "q", "test-model",
                                        None, 0, timing_collector=timing)
    finally:
        set_request_provider_config({})
    return result, timing


@pytest.mark.asyncio
async def test_run_worker_agent_shows_no_rail_when_the_report_vouches_for_nothing(monkeypatch):
    result, timing = await _run_worker(monkeypatch, "No instrument on point was located.")
    assert result["sources"] == []
    # The counter keeps its trigger: the Worker vouched for none of its sources.
    assert timing.source_stats == [(3, 0, True)]


@pytest.mark.asyncio
async def test_run_worker_agent_keeps_a_source_its_report_names(monkeypatch):
    result, timing = await _run_worker(monkeypatch, "The Widget Order 1901 No 2 applies.")
    assert [s["title"] for s in result["sources"]] == ["Widget Order 1901 No 2"]
    assert all(not k.startswith("_") for s in result["sources"] for k in s)
    assert timing.source_stats == [(3, 1, False)]
