"""FIX_PLAN P3.12, the answer seam (user decision 2026-10-09, parallel batch 12 A).

P3.12's route hands the Worker the schedule paragraphs a section search asked
for, cut verbatim. In every stored live answer whose Worker had them, at least
one was left out, and two Worker-facing levers did not move the live runs. So,
on P3.13's pattern, code puts back a paragraph it handed over that the answer
names nowhere, as one line of the paragraph's own words
(`utils/paragraph_restore.py`).

Every block here is built by the product's own builders
(`schedule_units.cut_pieces`, `matched_pieces`, `fetched_block`) on synthetic
text, so the reader is tested against what the route really writes.
"""
import pytest

from src.utils import paragraph_restore as pr
from src.utils.schedule_units import (
    CUT, FROM_TEXT, MATCHED, SUMMARY, WHOLE, ScheduleUnit, cut_pieces, fetched_block,
    matched_numbers, matched_pieces,
)

LID = "ssi/1901/3"
URL = "http://www.legislation.gov.uk/ssi/1901/3/schedule/5"

SCHED = (
    "Section 1) **Widget licences**\n\n"
    "1) This paragraph applies to a widget dealer. \n"
    "2) No widget may be sold without a licence. \n"
    "3) A licence lasts one year. \n\n"
    "Section 2) **Widget fees**\n\n"
    "1) This paragraph applies where a licence is sought and— \n"
    "\ta) the dealer is new, or \n"
    "\tb) the licence has lapsed. \n"
    "2) The fee is set by the Minister. \n\n"
    "Section 3) **Widget inspections**\n\n"
    "1) An inspector may enter a widget shop at any reasonable hour. \n"
    "2) An inspector may take samples of widgets. \n\n"
    "Section 4) **Gadget registers**\n\n"
    "1) The Minister keeps a register of gadget makers. \n\n"
    "Section 5) **Gadget appeals**\n\n"
    "1) A gadget maker may appeal to the sheriff. \n\n"
    "Section 6) **Interpretation**\n\n"
    "In this Schedule “widget” includes a part of a widget. \n"
)


def _cut_block(paras=("1", "2", "3"), unit_label="5", url=URL, source=None, text=SCHED):
    unit = ScheduleUnit("schedule", unit_label, paragraphs=tuple(paras))
    pieces, how, reason = cut_pieces(unit, text)
    assert how == CUT, how
    kw = {"source": source} if source else {}
    return fetched_block(LID, unit, url, pieces, how, reason=reason, **kw)


def _matched_block(query, unit_label="5", text=SCHED):
    unit = ScheduleUnit("schedule", unit_label)
    pieces = matched_pieces(unit, text, query, 12_000)
    assert pieces is not None
    return fetched_block(LID, unit, URL, pieces, MATCHED, total_chars=len(text),
                         matched=matched_numbers(unit, text, query))


def _restore(answer, *results):
    recs = [r for res in results for r in pr.handed_paragraphs(res)]
    return pr.restore_dropped_paragraphs(answer, recs)


ANSWER = ("Under paragraph 2 of Schedule 5 to the Widget Order 1901, the fee is set by the "
          "Minister.\n\nIn case law, Widget Co v Example Ltd held the fee lawful.")


# --- reading the route's own blocks -------------------------------------------


def test_a_cut_block_hands_over_each_named_paragraph_exactly():
    recs = pr.handed_paragraphs("search rows..." + _cut_block())
    assert [(r["para"], r["heading"], r["how"]) for r in recs] == [
        ("1", "Widget licences", "cut"), ("2", "Widget fees", "cut"),
        ("3", "Widget inspections", "cut")]
    r = recs[1]
    assert (r["lid"], r["unit"], r["url"]) == (LID, "Schedule 5", URL)
    assert r["text"].startswith("1) This paragraph applies where a licence is sought")
    assert "Section 3)" not in r["text"]


def test_a_matched_block_hands_over_its_matched_paragraphs_and_not_its_heading_list():
    recs = pr.handed_paragraphs(_matched_block("licences inspections"))
    assert [(r["para"], r["how"]) for r in recs] == [("1", "matched"), ("3", "matched")]


def test_a_span_or_a_to_the_end_piece_is_never_handed_paragraph():
    # Paragraph 6 is the last headed paragraph: cut "to the end", not exactly.
    recs = pr.handed_paragraphs(_cut_block(paras=("5", "6")))
    assert [r["para"] for r in recs] == ["5"]
    # ... and the paragraph before it stops at the span's own label.
    assert recs[0]["text"] == "1) A gadget maker may appeal to the sheriff."


def test_a_matched_paragraph_stops_at_the_next_label():
    recs = pr.handed_paragraphs(_matched_block("licences inspections"))
    assert "Paragraph 3 of" not in recs[0]["text"] and "Section 3)" not in recs[0]["text"]
    assert recs[0]["text"].endswith("3) A licence lasts one year.")


def test_a_block_that_is_neither_cut_nor_matched_is_not_read_whatever_it_holds():
    unit = ScheduleUnit("schedule", "5")
    pieces, _how, _ = cut_pieces(ScheduleUnit("schedule", "5", paragraphs=("1",)), SCHED)
    assert pr.handed_paragraphs(fetched_block(LID, unit, URL, pieces, WHOLE)) == []


def test_a_label_naming_another_unit_is_not_read_as_this_ones():
    block = _cut_block().replace("Paragraph 2 of Schedule 5,", "Paragraph 2 of Schedule 7,")
    assert [r["para"] for r in pr.handed_paragraphs(block)] == ["1", "3"]


@pytest.mark.parametrize("how", [WHOLE, SUMMARY])
def test_a_whole_or_summarised_unit_hands_over_no_paragraph(how):
    unit = ScheduleUnit("schedule", "5")
    block = fetched_block(LID, unit, URL, [("", SCHED)], how, total_chars=len(SCHED))
    assert pr.handed_paragraphs(block) == []


def test_an_annex_chapter_hands_over_no_paragraph():
    annex = "CHAPTER I\nWidgets\nArticle 1\nText.\nCHAPTER II\nGadgets\nArticle 2\nMore."
    unit = ScheduleUnit("annex", "IV", chapter="II")
    pieces, how, _ = cut_pieces(unit, annex)
    assert how == CUT
    assert pr.handed_paragraphs(fetched_block(LID, unit, URL, pieces, how)) == []


def test_the_text_fallback_block_is_read_and_carries_no_url():
    recs = pr.handed_paragraphs(_cut_block(source=FROM_TEXT))
    assert recs and all(r["url"] == "" for r in recs)
    assert pr.render_line(recs[0]).startswith("Also in Schedule 5, paragraph 1 ")


def test_an_unlabelled_schedule_is_read():
    unit = ScheduleUnit("schedule", "", paragraphs=("1", "3"))
    pieces, how, _ = cut_pieces(unit, SCHED)
    recs = pr.handed_paragraphs(fetched_block(LID, unit, URL, pieces, how))
    assert [(r["unit"], r["para"]) for r in recs] == [("the Schedule", "1"), ("the Schedule", "3")]
    assert pr.render_line(recs[0]).startswith(f"Also in [The Schedule]({URL}), paragraph 1 ")


def test_a_piece_that_does_not_open_with_its_own_heading_is_skipped():
    block = _cut_block().replace("Section 2) **Widget fees**", "Section 9) **Widget fees**")
    assert [r["para"] for r in pr.handed_paragraphs(block)] == ["1", "3"]


def test_reading_is_fail_soft():
    assert pr.handed_paragraphs(None) == []
    assert pr.handed_paragraphs("[PROVISION FETCHED BY CODE — garbled") == []


# --- the excerpt ----------------------------------------------------------------


def test_the_excerpt_skips_a_bare_application_line_and_keeps_whole_subparagraphs():
    p1 = pr.handed_paragraphs(_cut_block())[0]
    assert pr.excerpt(p1["text"]) == (
        "(2) No widget may be sold without a licence. (3) A licence lasts one year.")


def test_an_application_line_with_limbs_is_operative_and_kept_with_its_items():
    p2 = pr.handed_paragraphs(_cut_block())[1]
    assert pr.excerpt(p2["text"]) == (
        "(1) This paragraph applies where a licence is sought and— (a) the dealer is new, "
        "or (b) the licence has lapsed. (2) The fee is set by the Minister.")


def test_the_excerpt_stops_at_a_whole_subparagraph_within_the_cap():
    p1 = pr.handed_paragraphs(_cut_block())[0]
    assert pr.excerpt(p1["text"], cap=50) == "(2) No widget may be sold without a licence."


def test_a_first_subparagraph_over_the_cap_gives_the_heading_alone():
    p1 = dict(pr.handed_paragraphs(_cut_block())[0])
    assert pr.excerpt(p1["text"], cap=20) == ""
    p1["text"] = "1) A dealer must " + "keep records " * 60 + "\n"
    assert pr.render_line(p1) == f"Also in [Schedule 5]({URL}), paragraph 1 (Widget licences)."


def test_a_paragraph_with_no_subparagraphs_is_quoted_whole():
    recs = pr.handed_paragraphs(_cut_block(paras=("4", "5")))
    assert pr.excerpt(recs[1]["text"]) == "(1) A gadget maker may appeal to the sheriff."
    assert pr.excerpt("A person may not be a widget dealer twice. \n") == (
        "A person may not be a widget dealer twice.")


def test_square_brackets_in_the_statutory_text_are_made_round():
    assert pr.excerpt("1) The [amended] fee is due. \n") == "(1) The (amended) fee is due."


# --- restoring ------------------------------------------------------------------


def test_a_sibling_the_answer_left_out_goes_back_after_the_citing_paragraph():
    new, n = _restore(ANSWER, _cut_block())
    assert n == 2
    first, rest = new.split("\n\nIn case law", 1)
    assert first == (
        "Under paragraph 2 of Schedule 5 to the Widget Order 1901, the fee is set by the Minister."
        f"\n\nAlso in [Schedule 5]({URL}), paragraph 1 (Widget licences): \"(2) No widget may be "
        "sold without a licence. (3) A licence lasts one year.\""
        f"\n\nAlso in [Schedule 5]({URL}), paragraph 3 (Widget inspections): \"(1) An inspector "
        "may enter a widget shop at any reasonable hour. (2) An inspector may take samples of "
        "widgets.\"")
    assert rest == ", Widget Co v Example Ltd held the fee lawful."


def test_nothing_is_added_unless_the_answer_mentions_the_unit():
    answer = ANSWER.replace(" of Schedule 5", "")
    assert _restore(answer, _cut_block()) == (answer, 0)


def test_the_unit_may_be_named_by_its_link_alone():
    answer = f"Under [paragraph 2]({URL}), the fee is set by the Minister."
    assert _restore(answer, _cut_block())[1] == 2


def test_nothing_is_added_unless_the_answer_cites_a_sibling():
    answer = "Schedule 5 to the Widget Order 1901 sets fees (paragraph 9)."
    assert _restore(answer, _cut_block()) == (answer, 0)


@pytest.mark.parametrize("cites", [
    "paragraphs 1, 2 and 3", "paragraphs 1 to 3", "paras 1-3", "para 1(2), para 2 and para 3",
    "paragraph 2 and paragraph 1 and paragraph 3",
])
def test_a_paragraph_the_answer_cites_in_any_form_is_not_repeated(cites):
    answer = f"Under {cites} of Schedule 5, fees and licences apply."
    assert _restore(answer, _cut_block()) == (answer, 0)


def test_a_paragraph_the_answer_already_states_is_not_repeated():
    answer = ANSWER.replace(
        "Minister.\n\n",
        "Minister. No widget may be sold without a licence, and a licence lasts one year.\n\n")
    new, n = _restore(answer, _cut_block())
    assert n == 1 and "paragraph 1 (" not in new and "paragraph 3 (" in new


def test_in_a_matched_block_only_a_paragraph_whose_heading_shares_a_word_is_a_sibling():
    # Matched on "widget" (1, 2, 3) and "gadget" (4, 5): the answer cites 2.
    block = _matched_block("widget gadget")
    assert [r["para"] for r in pr.handed_paragraphs(block)] == ["1", "2", "3", "4", "5"]
    new, n = _restore(ANSWER, block)
    assert n == 2 and "paragraph 1 (" in new and "paragraph 3 (" in new
    assert "paragraph 4 (" not in new and "paragraph 5 (" not in new


def test_a_paragraph_handed_in_two_blocks_is_restored_once():
    new, n = _restore(ANSWER, _cut_block(), _matched_block("widget"), _cut_block())
    assert n == 2 and new.count("paragraph 1 (Widget licences)") == 1


def test_the_lines_are_capped():
    new, n = pr.restore_dropped_paragraphs(
        ANSWER, pr.handed_paragraphs(_cut_block()), max_lines=1)
    assert n == 1 and new.count("Also in ") == 1


def test_paragraphs_of_another_instrument_or_unit_are_not_siblings():
    # The answer cites paragraph 2 of Schedule 5; Schedule 7's paragraphs are
    # not its siblings, and the answer never names Schedule 7.
    recs = pr.handed_paragraphs(_cut_block(unit_label="7"))
    assert recs and all(r["unit"] == "Schedule 7" for r in recs)
    assert pr.restore_dropped_paragraphs(ANSWER, recs) == (ANSWER, 0)


def test_a_lettered_paragraph_is_read_and_restored():
    text = SCHED.replace("Section 3) **Widget inspections**",
                         "Section 2A) **Widget stamps**\n\n1) A widget bears a stamp. \n\n"
                         "Section 3) **Widget inspections**")
    block = _cut_block(paras=("2", "2A"), text=text)
    recs = pr.handed_paragraphs(block)
    assert [r["para"] for r in recs] == ["2", "2A"]
    new, n = pr.restore_dropped_paragraphs(ANSWER, recs)
    assert n == 1 and "paragraph 2A (Widget stamps): \"(1) A widget bears a stamp.\"" in new


def test_a_headed_line_with_no_heading_words_gives_a_line_without_one():
    text = SCHED.replace("Section 3) **Widget inspections**", "Section 3) ")
    recs = pr.handed_paragraphs(_cut_block(paras=("2", "3"), text=text))
    assert recs[1]["heading"] == ""
    new, n = pr.restore_dropped_paragraphs(ANSWER, recs)
    assert n == 1 and f"Also in [Schedule 5]({URL}), paragraph 3: \"(1) An inspector" in new


def test_a_subparagraph_pinpoint_in_the_answer_counts_its_paragraph_as_cited():
    answer = ANSWER.replace("paragraph 2 of", "paragraph 2(2) of") + " See also para 1(3)."
    new, n = _restore(answer, _cut_block())
    assert n == 1 and "paragraph 3 (" in new


def test_a_bare_application_line_alone_is_quoted():
    assert pr.excerpt("1) This paragraph applies to a widget dealer. \n") == (
        "(1) This paragraph applies to a widget dealer.")


def test_an_answer_sharing_some_words_is_not_a_restatement():
    # Shares "widget" and "licence" (2 of the excerpt's 6 content words).
    answer = ANSWER.replace("Minister.\n\n", "Minister for each widget licence.\n\n")
    new, n = _restore(answer, _cut_block())
    assert n == 2 and "paragraph 1 (Widget licences)" in new


@pytest.mark.parametrize("sentence,blocked", [
    # 4 of the excerpt's 6 content words (widget, sold, licence, lasts): 67%.
    ("Each widget sold needs a licence that lasts.", True),
    # 2 of 6 (widget, licence): 33%.
    ("A widget licence costs money.", False),
])
def test_the_restatement_threshold_sits_between_a_third_and_two_thirds(sentence, blocked):
    """Paragraph 1's excerpt is "(2) No widget may be sold without a licence. (3) A
    licence lasts one year.": six content words. The guard blocks a line when one
    answer sentence holds 60% of them."""
    answer = ANSWER.replace("Minister.\n\n", f"Minister. {sentence}\n\n")
    new, n = _restore(answer, _cut_block())
    assert ("paragraph 1 (Widget licences)" in new) is (not blocked)
    assert "paragraph 3 (Widget inspections)" in new
    assert n == (1 if blocked else 2)


def test_a_line_is_never_the_answers_first_sentence():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools.replay_report import first_sentence
    for answer in (ANSWER, ANSWER.replace("\n\n", " "), "Paragraph 2 of Schedule 5 sets fees."):
        new, n = _restore(answer, _cut_block())
        assert n and first_sentence(new) == first_sentence(answer)


def test_restore_is_fail_soft():
    assert pr.restore_dropped_paragraphs("", pr.handed_paragraphs(_cut_block())) == ("", 0)
    assert pr.restore_dropped_paragraphs(ANSWER, []) == (ANSWER, 0)
    assert pr.restore_dropped_paragraphs(ANSWER, [{"bad": 1}]) == (ANSWER, 0)


# --- the wrong pinpoint (reported, not changed) --------------------------------


def test_a_sentence_citing_one_paragraph_in_anothers_words_is_reported():
    recs = pr.handed_paragraphs(_cut_block())
    answer = ("Under paragraph 2 of Schedule 5, an inspector may enter a widget shop at any "
              "reasonable hour and take samples.")
    found = pr.misattributed_paragraphs(answer, recs)
    assert [(c, m) for c, m, _ in found] == [("2", "3")]


def test_a_sentence_in_its_own_paragraphs_words_is_not_reported():
    recs = pr.handed_paragraphs(_cut_block())
    assert pr.misattributed_paragraphs(ANSWER, recs) == []
    mixed = ("Under paragraph 2 of Schedule 5, the Minister sets the fee and an inspector may "
             "enter a widget shop and take samples.")
    assert pr.misattributed_paragraphs(mixed, recs) == []


def test_two_shared_words_are_not_enough():
    recs = pr.handed_paragraphs(_cut_block())
    answer = "Under paragraph 2 of Schedule 5, an inspector may take samples."
    assert pr.misattributed_paragraphs(answer, recs) == []


def test_a_sentence_citing_two_paragraphs_is_not_judged():
    recs = pr.handed_paragraphs(_cut_block())
    answer = ("Under paragraphs 2 and 1 of Schedule 5, an inspector may enter a widget shop at "
              "any reasonable hour and take samples.")
    assert pr.misattributed_paragraphs(answer, recs) == []


def test_a_word_in_two_paragraphs_is_not_distinctive():
    # "inspector" also in paragraph 2's text: no longer paragraph 3's alone.
    text = SCHED.replace("2) The fee is set by the Minister.",
                         "2) The fee is set by the Minister and paid to an inspector who may enter "
                         "a widget shop at any reasonable hour.")
    recs = pr.handed_paragraphs(_cut_block(text=text))
    answer = ("Under paragraph 1 of Schedule 5, an inspector may enter a widget shop at any "
              "reasonable hour.")
    assert pr.misattributed_paragraphs(answer, recs) == []


def test_a_single_handed_paragraph_reports_nothing():
    recs = pr.handed_paragraphs(_cut_block(paras=("3",)))
    answer = "Under paragraph 3 of Schedule 5, an inspector may enter a widget shop and take samples."
    assert pr.misattributed_paragraphs(answer, recs) == []


# --- wiring ---------------------------------------------------------------------


@pytest.fixture
def _cfg():
    from src.agent.provider_factory import set_request_provider_config

    def set_(chat_mode):
        set_request_provider_config({
            "_provider": "openrouter", "_research_mode": "legislation_only",
            "_chat_mode": chat_mode, "model": "test-model", "_tool_memo_enabled": False})
    yield set_
    set_request_provider_config({})


@pytest.mark.asyncio
async def test_the_worker_run_records_every_paragraph_its_tools_were_handed(monkeypatch, _cfg):
    from src.agent import agent_core
    _cfg("conversational")
    block = _cut_block()

    async def fake_tool(name, args, query, *a, **kw):
        return "rows" + block if name == "search_legislation_sections" else "{}"

    async def loop(messages, model, cancel_event, num_ctx, tools, executor, on_chunk=None, **kw):
        await executor("search_legislation_sections", {"legislation_id": LID, "query": "x"})
        await executor("search_legislation", {"query": "q"})
        return {"role": "assistant", "content": "Report."}

    monkeypatch.setattr(agent_core, "run_worker_tool", fake_tool)
    result = await agent_core.run_worker_agent(loop, lambda *a, **k: None, "q", "test-model", None, 0)
    assert [r["para"] for r in result["handed_paragraphs"]] == ["1", "2", "3"]


def _manager(answer):
    async def manager(messages, model, cancel_event, num_ctx, tools, tool_executor,
                      on_chunk=None, **kw):
        await tool_executor("delegate_research", {"query": "q"})
        return {"role": "assistant", "content": answer}
    return manager


async def _worker(query, model, cancel_event, num_ctx, on_chunk, **kw):
    kw["retrieved_urls"].add(URL)
    return {"content": "Report.", "sources": [], "searches": [],
            "handed_paragraphs": pr.handed_paragraphs(_cut_block())}


@pytest.mark.asyncio
async def test_the_conversational_answer_gets_the_dropped_paragraphs(_cfg):
    from src.agent.agent_core import process_user_request
    _cfg("conversational")
    final = await process_user_request(_manager(ANSWER), _worker,
                                       [{"role": "user", "content": "q"}], "test-model", None, None, 0)
    assert f"Also in [Schedule 5]({URL}), paragraph 1 (Widget licences)" in final["content"]
    assert "paragraph 3 (Widget inspections)" in final["content"]


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["research", "deep_research"])
async def test_every_other_chat_mode_is_left_alone(_cfg, mode):
    from src.agent.agent_core import process_user_request
    _cfg(mode)
    final = await process_user_request(_manager(ANSWER), _worker,
                                       [{"role": "user", "content": "q"}], "test-model", None, None, 0)
    assert "Also in [Schedule 5]" not in final["content"]


# --- the wording against every detector -----------------------------------------


def _rendered_variants() -> dict:
    cut = pr.handed_paragraphs(_cut_block())
    unl = pr.handed_paragraphs(fetched_block(
        LID, ScheduleUnit("schedule", "", paragraphs=("1", "3")), URL,
        *cut_pieces(ScheduleUnit("schedule", "", paragraphs=("1", "3")), SCHED)[:2]))
    txt = pr.handed_paragraphs(_cut_block(source=FROM_TEXT))
    head_only = dict(cut[0], text="1) " + "keep records " * 60)
    lettered = dict(cut[2], para="2A")
    no_heading = dict(cut[2], heading="")
    return {
        "labelled, excerpt": pr.render_line(cut[0]),
        "labelled, application line with limbs": pr.render_line(cut[1]),
        "unlabelled unit": pr.render_line(unl[0]),
        "text fallback (no url)": pr.render_line(txt[0]),
        "heading only": pr.render_line(head_only),
        "lettered": pr.render_line(lettered),
        "no heading words": pr.render_line(no_heading),
    }


def test_every_line_variant_trips_no_detector():
    """The line's own words (the template, with synthetic statutory text) are
    read by every answer grader once they are in an answer. The statutory
    text itself varies with the instrument and is screened over the stored
    lines in `notes/batch12_A.md`."""
    import re
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools import replay_report as rr
    unit_rx = re.compile(r"\b(?:schedules?|annex(?:es)?)\b", re.I)
    for where, t in _rendered_variants().items():
        assert t.startswith("Also in "), where
        assert rr.derivation_claims(t)[0] == [], where
        assert rr.caselaw_gap_statements(t) == [], where
        assert rr._without_footer(t) == t.strip(), where
        for name in ("NEG_ASSERTED", "NOT_FOUND", "NEG_TERMS", "NEG_BLAMED_INDEX",
                     "NEG_BLAMED_USER", "NEG_LIMITS", "NEGATIVE_EXPLAINED", "IN_FORCE_CLAIM",
                     "_CUR_DISCLOSED", "_CUR_DATED", "SCOTS_CASELAW_GAP", "HALT_LITERAL",
                     "HALT_PARAPHRASE", "HALT_AS_TIMEOUT", "OPENER_VOCAB", "SCHED_LIMIT",
                     "SCHED_INDEX_NEG", "_P312_NOT_DELIVERED"):
            assert not getattr(rr, name).search(t), (where, name)
        assert not [c for c, _, _ in rr.sched_unit_clauses(t, unit_rx) if c], where
        for s in rr._sentences(t):
            assert not (rr._CMC_CONTEXT.search(s) and rr._CMC_DENIED.search(s)), (where, s)
            assert not rr._currency_asserted(s), (where, s)
            assert rr.negcurrency_claim(s)[0] is None, (where, s)
            assert not rr.sched_clause_class(s), (where, s)
        assert sum(rr._scripted_counts(t).values()) == 0, where
        for word in ("ranked", "cut short"):
            assert word not in t.lower(), (where, word)
        # The only square brackets are the unit's own markdown link.
        assert t.count("[") == t.count("]") <= 1, where
