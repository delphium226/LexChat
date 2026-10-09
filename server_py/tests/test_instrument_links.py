"""FIX_PLAN P4.23 (B8): the conversational Manager names an instrument in words
and drops the link its Worker report gave it.

`citation_links.link_named_instruments`, at the conversational Manager's answer
seam (after P3.13's and P3.12's restores, before P1.6's enforcement and lever
R), wraps the answer's first plain-word mention of an instrument a report
linked, and the answer links nowhere, with the report's own URL: its
instrument-level URL, or a provision URL only where the answer names that
provision beside the mention. Guards, each pinned here: quotations and code
spans, [...] blocks, emphasis pairs, nested-bracket case labels, restored
notes, the longer-title head, two instruments at one mention, two provisions
beside one mention.

Synthetic text only ("Widget Order 1901", `ssi/1901/3`).
"""
import pytest

from src.agent.provider_factory import set_request_provider_config
from src.utils import source_naming as sn
from src.utils.citation_links import (
    PROVISION_MARKER,
    instrument_key,
    link_named_instruments,
    plan_instrument_links,
)

LEG = "https://www.legislation.gov.uk/"
ORDER = "http://www.legislation.gov.uk/id/ssi/1901/3"          # LEX's own spelling
ACT = LEG + "ukpga/1901/1"
S5 = LEG + "ukpga/1901/1/section/5"
S7 = LEG + "ukpga/1901/1/section/7"
SRC = [
    {"_lid": "ssi/1901/3", "kind": "SI", "title": "The Widget Order 1901", "url": ORDER},
    {"_lid": "ukpga/1901/1", "kind": "Act", "title": "Widget Act 1901", "url": ACT},
]
REPORT = f"The [Widget Order 1901]({ORDER}) applies."


def _link(answer, reports=(REPORT,), sources=SRC, titles=None):
    return link_named_instruments(answer, list(reports), sources, titles)


def _drops(answer, reports=(REPORT,), sources=SRC, titles=None):
    return [(lid, why) for lid, why, _s, _e in
            plan_instrument_links(answer, list(reports), sources, titles)[1]]


# --- instrument_key ------------------------------------------------------------------

@pytest.mark.parametrize("url,key", [
    (ORDER, "ssi/1901/3"),
    ("https://legislation.gov.uk/ssi/1901/3/", "ssi/1901/3"),
    (S5, "ukpga/1901/1"),
    (LEG + "ukpga/1901/1/schedule/2/paragraph/3", "ukpga/1901/1"),
    (LEG + "asp/1901/2/contents", "asp/1901/2"),
    (LEG + "ssi/1901/3/made", "ssi/1901/3"),
    (LEG + "ukpga/1901/1/section/5/1902-01-01", "ukpga/1901/1"),
    (LEG + "eur/1901/5/annex/ii", "eur/1901/5"),
    (LEG + "ukpga/Edw7/1/12/section/3", "ukpga/edw7/1/12"),
    (LEG + "ukpga/1-2edw7/12", "ukpga/1-2edw7/12"),
    ("https://example.com/ssi/1901/3", ""),
    (LEG + "search?text=widget", ""),
    ("", ""),
])
def test_the_instrument_a_url_is_for(url, key):
    assert instrument_key(url) == key


# --- class A: the report's instrument URL ----------------------------------------------

def test_the_first_plain_word_mention_gets_the_reports_url_verbatim():
    out, n = _link("The Widget Order 1901 applies. The Widget Order 1901 is in force.")
    assert n == 1
    assert out == (f"The [Widget Order 1901]({ORDER}) applies. "
                   "The Widget Order 1901 is in force.")


def test_it_is_idempotent():
    once, _ = _link("The Widget Order 1901 applies.")
    assert _link(once) == (once, 0)


def test_the_leading_the_stays_outside_the_label():
    out, _ = _link("the Widget Order 1901 applies.")
    assert out.startswith("the [Widget Order 1901](")


@pytest.mark.parametrize("bare_first", [True, False])
def test_the_reports_first_instrument_url_in_report_order(bare_first):
    """A bare URL and a markdown link count alike; the earlier one wins."""
    other = LEG + "ssi/1901/3"
    report = (f"See {other} and later [the Order]({ORDER})." if bare_first
              else f"See [the Order]({ORDER}) and later {other}.")
    out, _ = _link("The Widget Order 1901 applies.", reports=[report])
    assert f"[Widget Order 1901]({other if bare_first else ORDER})" in out


def test_trailing_punctuation_on_a_bare_report_url_is_dropped():
    report = f"The Order is at {ORDER}."
    out, _ = _link("The Widget Order 1901 applies.", reports=[report])
    assert f"[Widget Order 1901]({ORDER})" in out


@pytest.mark.parametrize("answer", [
    f"The Order applies ([reg 2]({ORDER}/regulation/2)). The Widget Order 1901 applies.",
    f"The Widget Order 1901 applies ({LEG}ssi/1901/3).",
    "The Widget Order 1901 applies ([text](https://legislation.gov.uk/ssi/1901/3/)).",
])
def test_an_instrument_the_answer_links_in_any_spelling_is_left_alone(answer):
    assert _link(answer) == (answer, 0)


def test_an_instrument_no_report_linked_is_left_alone():
    answer = "The Widget Order 1901 applies."
    assert _link(answer, reports=["The Widget Order 1901 applies."]) == (answer, 0)


def test_a_url_only_in_the_reports_scope_block_is_not_the_reports_link():
    report = "Findings.\n\n[SEARCH SCOPE - searched: " + ORDER + "]"
    answer = "The Widget Order 1901 applies."
    assert _link(answer, reports=[report]) == (answer, 0)


def test_another_host_is_never_linked():
    report = "See [the Order](https://example.com/ssi/1901/3)."
    answer = "The Widget Order 1901 applies."
    assert _link(answer, reports=[report]) == (answer, 0)


# --- how a mention is found ----------------------------------------------------------

@pytest.mark.parametrize("answer,label", [
    ("Made as SSI 1901/3.", "SSI 1901/3"),
    ("Made as 1901/3.", "1901/3"),
    ("Made as 1901 No. 3.", "1901 No. 3"),
    ("The **Widget Order 1901** applies.", "Widget Order 1901"),
    ("The widget order 1901 applies.", "widget order 1901"),
])
def test_every_naming_form_is_a_mention(answer, label):
    out, n = _link(answer)
    assert n == 1 and f"[{label}]({ORDER})" in out


def test_a_longer_number_is_not_a_mention():
    answer = "Made as SSI 1901/31."
    assert _link(answer) == (answer, 0)


def test_an_eu_number_is_a_mention():
    eu = LEG + "eur/1901/5"
    out, n = _link("Under Regulation (EU) No 5/1901 widgets are listed.",
                   reports=[f"[Reg 5/1901]({eu})"], sources=[])
    assert n == 1 and f"[Regulation (EU) No 5/1901]({eu})" in out


def test_a_title_with_a_hyphen_or_either_apostrophe_is_found():
    url = LEG + "ssi/1901/9"
    src = [{"_lid": "ssi/1901/9", "title": "Anti-widget (Children's) Order 1901", "url": url}]
    for answer in ("The Anti-widget (Children's) Order 1901 applies.",
                   "The Anti-widget (Children’s) Order 1901 applies."):
        out, n = _link(answer, reports=[f"[it]({url})"], sources=src)
        assert n == 1 and out.startswith("The [Anti-widget"), answer


@pytest.mark.parametrize("answer", ["The NonWidget Order 1901 applies.",
                                    "The Widget Order 1901s apply."])
def test_a_title_inside_a_longer_word_run_is_not_a_mention(answer):
    assert _link(answer) == (answer, 0)


def test_the_longest_title_at_one_place_is_the_label():
    src = SRC + [{"_lid": "ssi/1901/3", "title": "Widget Order", "url": ORDER}]
    out, n = _link("The Widget Order 1901 applies.", sources=src)
    assert n == 1 and out == f"The [Widget Order 1901]({ORDER}) applies."


def test_the_head_of_a_longer_instrument_title_is_not_a_mention():
    report = f"Under [the Act]({ACT})."
    answer = "The Widget Act 1901 (Commencement No. 1) Order 1902 commenced it."
    assert _link(answer, reports=[report]) == (answer, 0)


def test_a_bare_id_or_short_title_never_names_an_instrument():
    src = [{"_lid": "ukpga/1901/1", "title": "ukpga/1901/1", "url": ACT},
           {"_lid": "ukpga/1901/1", "title": "W Act", "url": ACT}]
    for answer in ("Under ukpga/1901/1 widgets are taxed.", "Under the W Act widgets are taxed."):
        assert _link(answer, reports=[f"[Act]({ACT})"], sources=src) == (answer, 0)
    assert not sn.nameable_title("ukpga/1901/1")
    assert not sn.nameable_title("The W Act")
    assert sn.nameable_title("The Widget Act")


def test_a_lookups_title_names_the_instrument():
    record = LEG + "id/asp/1901/2"
    src = [{"_lid": "asp/1901/2", "title": "asp/1901/2", "url": record}]
    answer = "It brings the Widget (Scotland) Act 1901 into force."
    out, n = _link(answer, reports=[f"Commences [asp/1901/2]({record})."], sources=src,
                   titles={"asp/1901/2": "Widget (Scotland) Act 1901"})
    assert n == 1 and f"[Widget (Scotland) Act 1901]({record})" in out
    assert _link(answer, reports=[f"Commences [asp/1901/2]({record})."], sources=src)[1] == 0


def test_a_source_with_no_id_is_keyed_by_its_url():
    src = [{"title": "Widget Order 1901", "url": ORDER}]
    assert _link("The Widget Order 1901 applies.", sources=src)[1] == 1


def test_a_mention_inside_a_link_label_is_skipped_for_the_next_plain_one():
    answer = (f"See [the Widget Order 1901 page](https://example.com/w). "
              "The Widget Order 1901 applies.")
    out, n = _link(answer)
    assert n == 1 and out.endswith(f"The [Widget Order 1901]({ORDER}) applies.")


def test_a_title_inside_a_nested_bracket_case_label_is_not_a_mention():
    case = "https://caselaw.nationalarchives.gov.uk/ewhc/1902/1"
    answer = (f"In [*Widget Co v Example Ltd, Re Widget Order 1901* [1902] EWHC 1]({case}) "
              "the court held so. The Widget Order 1901 applies.")
    out, n = _link(answer)
    assert n == 1 and out.endswith(f"The [Widget Order 1901]({ORDER}) applies.")


def test_a_restored_note_is_the_workers_words_and_never_linked():
    answer = f"Answer.\n\nAlso in s.5: the Widget Order 1901 also applies [s.5(2)]({S5})."
    assert _link(answer) == (answer, 0)


def test_a_restored_schedule_paragraph_line_is_never_linked():
    """P3.12's line, as `paragraph_restore` renders and inserts it. Pinned so a
    change to its opening shows here (the mask reads "\\n\\nAlso in ")."""
    from src.utils.paragraph_restore import render_line
    line = render_line({"unit": "schedule 2", "url": S5.replace("section/5", "schedule/2"),
                        "para": "3", "heading": "Widget Order 1901",
                        "text": "(1) The Widget Order 1901 applies to every widget."})
    answer = "Answer on Schedule 2.\n\n" + line
    assert _link(answer, reports=[REPORT]) == (answer, 0)


# --- the guards ----------------------------------------------------------------------

@pytest.mark.parametrize("answer", [
    'You searched "Widget Order 1901" and found it.',
    "You searched “Widget Order 1901” and found it.",
    "The search `Widget Order 1901` found it.",
    "Searched:\n```\nWidget Order 1901\n```\n",
])
def test_nothing_is_linked_inside_a_quotation_or_code(answer):
    assert _link(answer) == (answer, 0)
    assert _drops(answer) == [("ssi/1901/3", "quoted")]


@pytest.mark.parametrize("answer", [
    'It said "yes". The Widget Order 1901 applies.',
    'It said "yes\nThe Widget Order 1901 applies.',     # an unclosed quote on an earlier line
])
def test_a_quotation_closed_earlier_or_on_another_line_does_not_block(answer):
    assert _link(answer)[1] == 1


@pytest.mark.parametrize("answer", [
    "[SEARCH SCOPE - searched: Widget Order 1901]",
    "[Note: the Widget Order 1901\nwas searched]",
])
def test_nothing_is_linked_inside_a_bracketed_block(answer):
    assert _link(answer) == (answer, 0)
    assert _drops(answer) == [("ssi/1901/3", "bracketed")]


def test_a_closed_bracket_before_the_mention_does_not_block():
    out, n = _link("[1902] is the year. The Widget Order 1901 applies.")
    assert n == 1


def test_an_emphasis_pair_is_never_cut():
    answer = "The **Widget** Order 1901 applies."
    assert _link(answer) == (answer, 0)
    assert _drops(answer) == [("ssi/1901/3", "emphasis")]


def test_two_instruments_at_one_mention_link_neither():
    src = [{"_lid": "ssi/1901/3", "title": "Widget Order 1901", "url": ORDER},
           {"_lid": "ssi/1901/4", "title": "Widget Order 1901", "url": LEG + "ssi/1901/4"}]
    report = f"[a]({ORDER}) and [b]({LEG}ssi/1901/4)"
    answer = "The Widget Order 1901 applies."
    assert _link(answer, reports=[report], sources=src) == (answer, 0)
    assert sorted(_drops(answer, reports=[report], sources=src)) == [
        ("ssi/1901/3", "two instruments at one mention"),
        ("ssi/1901/4", "two instruments at one mention")]


# --- class B: only provision URLs --------------------------------------------------------

def test_a_provision_url_only_where_the_answer_names_it_beside_the_mention():
    out, n = _link("Under section 5 of the Widget Act 1901 widgets are taxed.",
                   reports=[f"[s.5(2)]({S5})"])
    assert n == 1 and f"[Widget Act 1901]({S5})" in out


def test_never_a_whole_instrument_mention_to_one_provisions_url():
    answer = "The Widget Act 1901 does not define a widget."
    assert _link(answer, reports=[f"[s.5(2)]({S5})"]) == (answer, 0)
    assert _drops(answer, reports=[f"[s.5(2)]({S5})"]) == [
        ("ukpga/1901/1", "provision not named beside it")]


def test_a_longer_provision_number_is_not_the_provision():
    answer = "Section 50 of the Widget Act 1901 applies."
    assert _link(answer, reports=[f"[s.5]({S5})"]) == (answer, 0)


def test_the_provision_named_picks_the_url():
    out, n = _link("Section 7 of the Widget Act 1901 applies.",
                   reports=[f"[s.5]({S5}); [s.7]({S7})"])
    assert n == 1 and f"[Widget Act 1901]({S7})" in out


def test_two_provisions_named_beside_it_is_ambiguous():
    answer = "Sections 5 and section 7 of the Widget Act 1901 apply."
    assert _link(answer, reports=[f"[s.5]({S5}); [s.7]({S7})"]) == (answer, 0)
    assert _drops(answer, reports=[f"[s.5]({S5}); [s.7]({S7})"]) == [
        ("ukpga/1901/1", "two provisions named beside it")]


@pytest.mark.parametrize("gap,linked", [(97, True), (98, False)])
def test_beside_means_within_a_hundred_characters(gap, linked):
    # "s.5" ends exactly 100 characters after the mention at gap 97.
    answer = "The Widget Act 1901" + " " * gap + "s.5 applies."
    assert (_link(answer, reports=[f"[s.5]({S5})"])[1] == 1) is linked


def test_a_schedule_paragraph_needs_both_named():
    url = LEG + "ukpga/1901/1/schedule/2/paragraph/3"
    both = "Paragraph 3 of Schedule 2 to the Widget Act 1901 applies."
    one = "Schedule 2 to the Widget Act 1901 applies."
    assert _link(both, reports=[f"[para 3]({url})"])[1] == 1
    assert _link(one, reports=[f"[para 3]({url})"]) == (one, 0)


def test_a_provision_an_answer_cannot_name_is_never_beside():
    url = LEG + "ukpga/1901/1/part/2"
    answer = "Part 2 of the Widget Act 1901 applies."
    assert _link(answer, reports=[f"[Part 2]({url})"]) == (answer, 0)
    url = LEG + "ukpga/1901/1/schedule/2/part/1"
    answer = "Schedule 2 to the Widget Act 1901 applies."
    assert _link(answer, reports=[f"[Sch 2 Pt 1]({url})"]) == (answer, 0)
    eu = LEG + "eur/1901/5/annex/ii"
    answer = "Annex II to Regulation (EU) No 5/1901 lists widgets."
    assert _link(answer, reports=[f"[Annex II]({eu})"], sources=[]) == (answer, 0)


def test_a_provision_url_is_never_the_instrument_url():
    """With an instrument URL and a provision URL in the report, the mention
    takes the instrument's."""
    out, _ = _link("The Widget Act 1901 applies.", reports=[f"[s.5]({S5}) of [the Act]({ACT})"])
    assert f"[Widget Act 1901]({ACT})" in out


# --- several instruments, fail-soft ---------------------------------------------------

def test_two_instruments_are_linked_in_one_answer_with_offsets_kept():
    report = f"[Order]({ORDER}); [Act]({ACT})"
    out, n = _link("The Widget Act 1901 and the Widget Order 1901 apply.", reports=[report])
    assert n == 2
    assert out == f"The [Widget Act 1901]({ACT}) and the [Widget Order 1901]({ORDER}) apply."


@pytest.mark.parametrize("answer,reports,sources", [
    ("", [REPORT], SRC), ("The Widget Order 1901 applies.", [], SRC),
    ("The Widget Order 1901 applies.", None, SRC),
    ("The Widget Order 1901 applies.", [None, 3], [None, "x", {"title": None}]),
])
def test_it_is_fail_soft(answer, reports, sources):
    out, n = link_named_instruments(answer, reports, sources, None)
    assert n == 0 and out == answer


def test_an_error_returns_the_answer_unchanged(monkeypatch):
    import src.utils.citation_links as cl

    def boom(*a, **k):
        raise ValueError("synthetic")
    monkeypatch.setattr(cl, "plan_instrument_links", boom)
    answer = "The Widget Order 1901 applies."
    assert cl.link_named_instruments(answer, [REPORT], SRC) == (answer, 0)


# --- the wiring ------------------------------------------------------------------------

def _cfg(chat_mode="conversational", research_mode="legislation_only"):
    set_request_provider_config({
        "_provider": "openrouter", "_research_mode": research_mode, "model": "test-model",
        "_tool_memo_enabled": False, "_chat_mode": chat_mode,
    })


async def _turn(answer, report, retrieved=(), urls=(), titles=None, **cfg):
    from src.agent.agent_core import process_user_request
    _cfg(**cfg)

    async def worker(*a, **kw):
        kw["retrieved_urls"].update(urls)
        return {"content": report, "searches": [], "sources": [],
                "retrieved_sources": list(retrieved), "retrieved_titles": titles or {}}

    async def manager(messages, model, cancel_event, num_ctx, tools, tool_executor,
                      on_chunk=None, **kw):
        await tool_executor("delegate_research", {"query": "q"})
        return {"role": "assistant", "content": answer}

    try:
        return await process_user_request(manager, worker, [{"role": "user", "content": "q"}],
                                          "test-model", None, None, 0)
    finally:
        set_request_provider_config({})


def _src(lid, title, url, kept=False):
    return {"_lid": lid, "kind": "SI", "title": title, "url": url, "cite": lid, "_kept": kept}


async def test_the_conversational_manager_answer_is_linked():
    final = await _turn("The Widget Order 1901 applies.", REPORT,
                        [_src("ssi/1901/3", "Widget Order 1901", ORDER)], [ORDER])
    assert final["content"].startswith(f"The [Widget Order 1901]({ORDER}) applies.")


@pytest.mark.parametrize("cfg", [
    {"chat_mode": "research"},
    {"research_mode": "parliamentary_records"},
    {"research_mode": "westminster_records"},
])
async def test_every_other_answer_is_left_alone(cfg):
    final = await _turn("The Widget Order 1901 applies.", REPORT,
                        [_src("ssi/1901/3", "Widget Order 1901", ORDER)], [ORDER], **cfg)
    assert final["content"].startswith("The Widget Order 1901 applies.")


async def test_the_added_link_is_checked_by_p16_like_any_other():
    """Above P1.6's enforcement: a provision URL no tool returned is demoted."""
    final = await _turn("Under s.5 of the Widget Act 1901 widgets are taxed.",
                        f"[s.5]({S5})", [_src("ukpga/1901/1", "Widget Act 1901", ACT)], [ACT])
    assert f"[Widget Act 1901 {PROVISION_MARKER}]({LEG}ukpga/1901/1)" in final["content"]


async def test_lever_r_reads_the_linked_answer():
    """After the linker: an instrument known to the rail by its id alone (a
    change record's source) and named in the answer by a lookup's title is
    cited by the link's URL, so R re-admits it."""
    record = "http://www.legislation.gov.uk/id/asp/1901/2"
    final = await _turn("It brings the Widget (Scotland) Act 1901 into force.",
                        f"Commences [asp/1901/2]({record}).",
                        [_src("asp/1901/2", "asp/1901/2", record)], [record],
                        titles={"asp/1901/2": "Widget (Scotland) Act 1901"})
    assert f"[Widget (Scotland) Act 1901]({record})" in final["content"]
    assert [s["cite"] for s in final.get("sources") or []] == ["asp/1901/2"]


async def test_a_restored_sibling_note_is_never_linked():
    """After P3.13's restore: its note is the Worker's verbatim words, so an
    instrument the note names in plain words is not linked there."""
    s36 = LEG + "asp/1901/2/section/36"
    report = (f"Under [s.36(1)]({s36}) a duty applies, while [s.36(2)]({s36}) exempts "
              "information the Widget Order 1901 lists for that purpose. "
              f"The [Widget Order 1901]({ORDER}) is relevant.")
    final = await _turn("Under section 36(1) a duty applies.", report,
                        [_src("ssi/1901/3", "Widget Order 1901", ORDER)], [s36, ORDER])
    content = final["content"]
    assert ("Also in s.36: " f"[s.36(2)]({s36}) exempts information the Widget Order 1901 "
            "lists for that purpose.") in content
    assert f"]({ORDER})" not in content


async def test_a_restored_note_that_links_the_instrument_counts_as_linking_it():
    """After P3.13's restore, so its note is read: where the note carries the
    report's link to the instrument, the answer links it, and the body's plain
    mention is not linked a second time (batch 12 D's measurement read the
    answer this way). Before the restore, the body's mention would be linked."""
    s36 = LEG + "asp/1901/2/section/36"
    act = LEG + "asp/1901/2"
    report = (f"Under [s.36(1)]({s36}) of the [Widget (Scotland) Act 1901]({act}) a duty "
              f"applies, while [s.36(2)]({s36}) exempts information the [Act]({act}) lists "
              "for that purpose.")
    final = await _turn("Under section 36(1) of the Widget (Scotland) Act 1901 a duty applies.",
                        report, [_src("asp/1901/2", "Widget (Scotland) Act 1901", act)], [s36, act])
    content = final["content"]
    assert f"Also in s.36: [s.36(2)]({s36}) exempts information the [Act]({act})" in content
    assert content.startswith("Under section 36(1) of the Widget (Scotland) Act 1901 a duty")
