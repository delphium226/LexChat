"""FIX_PLAN P3.13 (B10): the conversational Manager drops a sibling subsection
its own Worker had written.

6348's lawyer: the answer *"did not initially elaborate on the full provision,
only referring to s36(1) and not s36(2)"*. After P3.11 the quick-lookup Worker
states s.36(2) in 3 of 3 turn-1 reports, and the conversational Manager
deleted it from 2 of those 3 answers. Every time, the sibling was the one
provision in the report written without a link — both subsections share the
section's URL — and the Manager's CITATION PRESERVATION rule protects each
provision "with its link".

Measured over every replayed run before building (Session 22, 35
directories): when the conversational answer kept one subsection of a section,
it kept a sibling it had been handed as a link 58 times in 60 and one handed
as plain text 70 in 104. The fix is two pieces of code, and these tests pin
both:

1. **Linking** (`link_sibling_pinpoints`, called by `worker_result_for_manager`):
   the sibling is linked to the section URL the same paragraph already
   carries, so it reaches the Manager as a citation. Never builds a URL; never
   links a pinpoint to a different instrument's section (Invariant 1: a real
   page for the wrong Act reads as a verified citation).
2. **Restoring** (`restore_dropped_siblings`, at the answer seam; user decision
   2026-09-23): the Manager also edits a sibling out as off-topic ("legal
   advice privilege" is s.36(1)), linked or not, so where it still drops one
   the Worker's own words go back under the citation.

A prompt clause was built between the two and taken out again; see
`test_the_conversational_manager_prompt_carries_no_sibling_clause`.
"""

import pytest

from src import prompts
from src.agent.agent_core import worker_result_for_manager
from src.utils.citation_links import link_sibling_pinpoints

S36 = "http://www.legislation.gov.uk/id/asp/2002/13/section/36"
S50 = "http://www.legislation.gov.uk/id/asp/2002/13/section/50"
DPA36 = "http://www.legislation.gov.uk/ukpga/2018/12/section/36"
RETRIEVED = {S36, S50}

# The three shapes the Worker wrote the sibling in, verbatim from the run files
# (wave3_p311_conv reps 1 and 2, wave0_conv_6348 rep 3).
PARENTHETICAL = (
    f"Under [s.36(1) of the Freedom of Information (Scotland) Act 2002]({S36}), "
    "information is exempt from disclosure if a claim to confidentiality of "
    "communications could be maintained in legal proceedings (while s.36(2) "
    "exempts information obtained from another person where disclosure would "
    "constitute an actionable breach of confidence)."
)
SENTENCE = (
    f"Under [s.36(1) of the Freedom of Information (Scotland) Act 2002]({S36}), "
    "information is exempt if a claim to confidentiality of communications "
    "could be maintained. A related exemption in s.36(2) applies to "
    "information obtained from another person."
)
REMAINDER = (
    f"Under [s.36(1)]({S36}) of the Freedom of Information (Scotland) Act 2002, "
    "information is exempt if a claim to confidentiality of communications "
    "could be maintained. The remainder of the section, s.36(2), provides a "
    "separate exemption for information obtained from a third party."
)


@pytest.mark.parametrize("report", [PARENTHETICAL, SENTENCE, REMAINDER])
def test_the_sibling_is_linked_to_the_section_the_report_already_links(report):
    out, n = link_sibling_pinpoints(report, RETRIEVED)
    assert n == 1
    assert f"[s.36(2)]({S36})" in out
    # Nothing else changed.
    assert out.replace(f"[s.36(2)]({S36})", "s.36(2)") == report


def test_it_is_idempotent():
    once, _ = link_sibling_pinpoints(PARENTHETICAL, RETRIEVED)
    twice, n = link_sibling_pinpoints(once, RETRIEVED)
    assert twice == once and n == 0


def test_a_bare_section_is_not_a_sibling():
    text = f"Under [s.36(1)]({S36}), information is exempt; see also s.36 generally."
    assert link_sibling_pinpoints(text, RETRIEVED) == (text, 0)


def test_it_never_builds_a_url():
    """s.50(5) with no s.50 link in the paragraph stays plain text, even though
    the report holds a FOISA link and s.50's URL is predictable."""
    text = f"Under [s.36(1)]({S36}), information is exempt. And s.50(5) protects advice."
    assert link_sibling_pinpoints(text, RETRIEVED) == (text, 0)


def test_the_link_must_be_in_the_same_paragraph():
    text = f"Under [s.36(1)]({S36}), information is exempt.\n\nSeparately, s.36(2) covers confidences."
    assert link_sibling_pinpoints(text, RETRIEVED) == (text, 0)


def test_two_urls_for_the_section_is_ambiguous_and_left_alone():
    text = (f"[FOISA s.36(1)]({S36}) and [DPA 2018 s.36(1)]({DPA36}) differ; "
            "s.36(2) is narrower.")
    assert link_sibling_pinpoints(text, RETRIEVED | {DPA36}) == (text, 0)


def test_a_pinpoint_of_another_named_instrument_is_not_given_this_ones_url():
    """The one wrong link the first draft made over the corpus (`wave2_p25`,
    6341): a list of Use Classes Orders, where the 1963 Order's s.2(2) was
    handed the 1950 Order's s.2 URL."""
    s2 = "http://www.legislation.gov.uk/id/si/1950/1131/section/2"
    text = (f"* [The Town and Country Planning (Use Classes) Order 1950 - s. 2]({s2})\n"
            "* **The Town and Country Planning (Use Classes) Order 1963 - s. 2(2)**")
    assert link_sibling_pinpoints(text, {s2}) == (text, 0)


def test_a_pinpoint_that_names_its_own_act_after_it_is_left_alone():
    text = (f"Under [s.36(1) of FOISA]({S36}), information is exempt, and "
            "s.36(2) of the Data Protection Act 2018 is different.")
    assert link_sibling_pinpoints(text, RETRIEVED) == (text, 0)


def test_a_title_written_straight_after_the_link_names_the_same_act():
    """"[s.36(1)](...) of the Freedom of Information (Scotland) Act 2002" —
    the plain title is the link's own Act, so it does not block the sibling
    (the REMAINDER shape above relies on this)."""
    out, n = link_sibling_pinpoints(REMAINDER, RETRIEVED)
    assert n == 1


def test_a_plain_title_between_link_and_pinpoint_blocks_it():
    text = (f"Under [s.36(1)]({S36}), information is exempt. The Data Protection "
            "Act 2018 also has rules, and s.36(2) is narrower.")
    assert link_sibling_pinpoints(text, RETRIEVED) == (text, 0)


def test_an_unretrieved_url_is_never_propagated():
    assert link_sibling_pinpoints(PARENTHETICAL, {S50}) == (PARENTHETICAL, 0)


def test_the_search_scope_block_is_never_touched():
    report = PARENTHETICAL + (
        "\n\n[SEARCH SCOPE — what this research step actually did]\n"
        f"Searched within [s.36(1)]({S36}); s.36(2) was in the results.\n[/SEARCH SCOPE]")
    out, n = link_sibling_pinpoints(report, RETRIEVED)
    assert n == 1
    assert out.split("\n\n[SEARCH SCOPE")[1] == report.split("\n\n[SEARCH SCOPE")[1]


def test_regulations_and_articles_are_linked_by_their_own_segment():
    reg = "http://www.legislation.gov.uk/id/uksi/2004/3391/regulation/12"
    text = f"[Regulation 12(4)(e)]({reg}) covers internal communications; regulation 12(8) defines them."
    out, n = link_sibling_pinpoints(text, {reg})
    assert n == 1 and f"[regulation 12(8)]({reg})" in out
    # A section pinpoint is never given a regulation URL.
    text = f"[Regulation 12(4)]({reg}) applies, and s.12(8) is elsewhere."
    assert link_sibling_pinpoints(text, {reg}) == (text, 0)


def test_a_schedule_url_is_never_a_section_url():
    sch = "http://www.legislation.gov.uk/id/asp/2002/13/schedule/1"
    text = f"[Schedule 1]({sch}) lists authorities; s.1(2) is general."
    assert link_sibling_pinpoints(text, {sch}) == (text, 0)


def test_it_is_fail_soft_on_nothing():
    assert link_sibling_pinpoints("", RETRIEVED) == ("", 0)
    assert link_sibling_pinpoints(None, RETRIEVED) == (None, 0)


# --- the seam: only the conversational Manager is handed the linked report ---


def test_the_conversational_manager_gets_the_linked_report():
    out = worker_result_for_manager(PARENTHETICAL, {"_chat_mode": "conversational"}, RETRIEVED)
    assert out.startswith("[Research Agent Result]\n")
    assert f"[s.36(2)]({S36})" in out


@pytest.mark.parametrize("mode", ["research", "deep_research", None])
def test_every_other_manager_gets_the_report_unchanged(mode):
    """The research Manager passes the report through (it kept 441 of 441
    pinpoints over the corpus, linked or not), so nothing it shows the lawyer
    changes."""
    out = worker_result_for_manager(PARENTHETICAL, {"_chat_mode": mode}, RETRIEVED)
    assert out == f"[Research Agent Result]\n{PARENTHETICAL}"


@pytest.fixture
def _conversational_cfg():
    from src.agent.provider_factory import set_request_provider_config
    set_request_provider_config({
        "_provider": "openrouter", "_research_mode": "legislation_only",
        "_chat_mode": "conversational", "model": "test-model",
        "_tool_memo_enabled": False,
    })
    yield
    set_request_provider_config({})


async def test_process_user_request_hands_the_manager_the_linked_report(_conversational_cfg):
    """Wired at the one place the Manager receives a worker report."""
    from src.agent.agent_core import process_user_request

    async def worker(query, model, cancel_event, num_ctx, on_chunk, **kw):
        # The real worker harvests every URL its tools returned into this set.
        kw["retrieved_urls"].update(RETRIEVED)
        return {"content": PARENTHETICAL, "sources": [], "searches": []}

    seen = {}

    async def manager(messages, model, cancel_event, num_ctx, tools,
                      tool_executor, on_chunk=None, **kw):
        seen["result"] = await tool_executor("delegate_research", {"query": "q"})
        return {"role": "assistant", "content": "Answer."}

    await process_user_request(manager, worker, [{"role": "user", "content": "q"}],
                               "test-model", None, None, 0)
    assert f"[s.36(2)]({S36})" in seen["result"]


# --- the prompt: left as it was ------------------------------------------------


def test_the_conversational_manager_prompt_carries_no_sibling_clause():
    """The clause was built (`778d30a`) and taken out again (Session 22,
    continued). Once the restore made keeping the sibling code's job, the
    clause's only measured effect was on the Manager's FIRST delegation
    brief, written before any tool result: with it, 2 of 4 briefs for 6348
    t1 no longer named FOI, against 4 of 4 without; and the verbatim brief
    that sent `wave3_p313b` rep 1 to the Economic Crime and Corporate
    Transparency Act 2023 appeared in 3 of 6 runs with it, 0 of 10 before
    and 0 of 3 after it was removed. Invariant 2: the code does the job, the
    prompt is left as it was."""
    body = prompts._MANAGER_CONV_BODY
    rules = body.split("CRITICAL RULES:")[1].split("YOUR APPROACH:")[0]
    bullet = [ln for ln in rules.splitlines() if ln.startswith("- CITATION PRESERVATION")]
    assert len(bullet) == 1
    assert "other subsections provide" not in body
    assert bullet[0].endswith("never reduce a provision to the instrument's name alone.")
    assert len([ln for ln in rules.splitlines() if ln.startswith("- ")]) == 4


def test_a_plain_text_citation_counts_when_the_reports_link_one_instrument():
    """`wave3_p311_conv` rep 2 on the seam: the Manager dropped every link and
    wrote "section 36(1) of the ... Act" in plain words."""
    answer = ("The provision is section 36(1) of the Freedom of Information (Scotland) "
              "Act 2002.\n\nAdditionally, section 50(5) protects advice.")
    out, n = restore_dropped_siblings(answer, [_handed(PARENTHETICAL)])
    assert n == 1
    assert out.split("\n\n")[1].startswith(f"Also in s.36: [s.36(2)]({S36})")


def test_a_plain_text_citation_is_never_matched_across_instruments():
    """Two instruments linked in the reports: a plain "s.36(1)" could be
    either Act's, so nothing is added."""
    answer = "The provision is section 36(1) of the Act."
    dpa = f"Under [s.45A(1)]({'http://www.legislation.gov.uk/ukpga/2018/12/section/45A'}) a controller need not comply."
    assert restore_dropped_siblings(answer, [_handed(PARENTHETICAL), dpa]) == (answer, 0)


def test_the_research_manager_is_unchanged():
    assert "other subsections provide" not in prompts._MANAGER_BODY


# --- the answer seam: `restore_dropped_siblings` -------------------------------
#
# Linking (plus, then, a prompt clause) still left the Manager flattening s.36(2) at a rate
# (`wave3_p313` rep 1, with both live). Option (i), user decision 2026-09-23:
# put the Worker's own words back under the citation.

from src.utils.citation_links import restore_dropped_siblings  # noqa: E402

FLAT_ANSWER = (f"The provision is [section 36(1) of the FOISA]({S36}). It exempts "
               "privileged communications.\n\nAdditionally, s.50(5) protects advice.")


def _handed(report):
    return link_sibling_pinpoints(report, RETRIEVED)[0]


@pytest.mark.parametrize("report,words", [
    (PARENTHETICAL, f"[s.36(2)]({S36}) exempts information obtained from another person"),
    (SENTENCE, f"A related exemption in [s.36(2)]({S36}) applies to information"),
    (REMAINDER, f"The remainder of the section, [s.36(2)]({S36}), provides a separate exemption"),
])
def test_the_workers_own_words_go_back_under_the_citation(report, words):
    out, n = restore_dropped_siblings(FLAT_ANSWER, [_handed(report)])
    assert n == 1
    first, note, rest = out.split("\n\n")
    assert first == FLAT_ANSWER.split("\n\n")[0]          # after the citing paragraph
    assert note.startswith("Also in s.36: ") and words in note
    assert note.endswith(".") and "(while" not in note and not note.startswith("Also in s.36: while")
    assert rest == "Additionally, s.50(5) protects advice."


@pytest.mark.parametrize("answer", [
    f"The provision is [s.36(1)]({S36}); [s.36(2)]({S36}) covers confidences.",
    f"The provision is [s.36(1)]({S36}); s.36(2) covers confidences.",
    f"The provision is [s.36(1)]({S36}); subsection (2) covers confidences.",
    f"The provision is [section 36(1) to (2)]({S36}).",
])
def test_a_sibling_the_answer_kept_in_any_form_is_not_repeated(answer):
    assert restore_dropped_siblings(answer, [_handed(PARENTHETICAL)]) == (answer, 0)


def test_nothing_is_added_unless_the_answer_cites_the_section_at_subsection_level():
    """Dropping the whole section is a different failure, not a sibling."""
    for answer in (f"See [section 36]({S36}) generally.", "FOISA has several exemptions."):
        assert restore_dropped_siblings(answer, [_handed(PARENTHETICAL)]) == (answer, 0)


def test_a_clause_that_restates_the_kept_subsection_is_not_added():
    """6348 `wave3_p313` r2 t3's s.2 note would have repeated the answer's own
    s.2(2)(c) sentence with s.2(1) mentioned in passing."""
    s2 = "http://www.legislation.gov.uk/id/asp/2002/13/section/2"
    report = (f"This is an absolute exemption under [s.2(2)(c)]({s2}), meaning it is not "
              f"subject to the public interest test that applies under [s.2(1)]({s2}).")
    answer = f"This is absolute under [section 2(2)(c)]({s2}). The test does not apply."
    assert restore_dropped_siblings(answer, [report]) == (answer, 0)


def test_a_clause_the_answer_already_says_is_not_added():
    """6409: the answer said the remaining provisions come in by appointed day
    and dropped only the pinpoint; a note would repeat the sentence."""
    s27 = "http://www.legislation.gov.uk/id/asp/2025/2/section/27"
    report = (f"Under [s.27(1)]({s27}), sections 24 to 28 came into force. The remaining "
              f"provisions come into force on days appointed by the Scottish Ministers "
              f"by regulations under [s.27(2)]({s27}).")
    answer = (f"Under [section 27(1)]({s27}), sections 24 to 28 came into force. The "
              "remaining provisions come into force on days appointed by the Scottish Ministers.")
    assert restore_dropped_siblings(answer, [report]) == (answer, 0)


def test_a_list_is_never_cut_into_a_fragment():
    """6374's first draft: cutting at ", and" split a parenthesised list and
    left "(the First Minister, Ministers, the Lord Advocate." as a note."""
    s126 = "http://www.legislation.gov.uk/ukpga/1998/46/section/126"
    report = (f"Under [section 126(7)]({s126}), the office-holders comprise members of the "
              "Scottish Government (the First Minister, Ministers, and the Lord Advocate, "
              "and the Solicitor General.")
    answer = f"The definition is in [section 126(6)]({s126}). It covers office-holders."
    out, n = restore_dropped_siblings(answer, [report])
    assert n == 0 and out == answer


def test_the_scope_block_is_never_read():
    report = (f"Under [s.36(1)]({S36}), information is exempt.\n\n[SEARCH SCOPE — x]\n"
              f"While [s.36(2)]({S36}) exempts information obtained from another person "
              "where disclosure is actionable.\n[/SEARCH SCOPE]")
    assert restore_dropped_siblings(FLAT_ANSWER, [report]) == (FLAT_ANSWER, 0)


def test_the_label_is_the_urls_own_and_the_notes_are_capped():
    u = "http://www.legislation.gov.uk/id/ukpga/2018/12/section/45A"
    report = (f"Under [s.45A(1)(a)]({u}) a controller need not comply. [s.45A(2)]({u}) "
              "requires the controller to inform the data subject of the restriction.")
    out, n = restore_dropped_siblings(f"See [section 45A(1)(a)]({u}).", [report])
    assert n == 1 and "Also in s.45A: " in out
    many = [_handed(PARENTHETICAL)] + [report]
    _, n = restore_dropped_siblings(f"[s.36(1)]({S36}); [s.45A(1)]({u}).", many, max_notes=1)
    assert n == 1


def test_restore_is_fail_soft_on_nothing():
    assert restore_dropped_siblings("", [PARENTHETICAL]) == ("", 0)
    assert restore_dropped_siblings(FLAT_ANSWER, []) == (FLAT_ANSWER, 0)


def _flattening_manager(answer):
    async def manager(messages, model, cancel_event, num_ctx, tools,
                      tool_executor, on_chunk=None, **kw):
        await tool_executor("delegate_research", {"query": "q"})
        return {"role": "assistant", "content": answer}
    return manager


async def _worker(query, model, cancel_event, num_ctx, on_chunk, **kw):
    kw["retrieved_urls"].update(RETRIEVED)
    return {"content": PARENTHETICAL, "sources": [], "searches": []}


async def test_process_user_request_restores_for_the_conversational_manager(_conversational_cfg):
    from src.agent.agent_core import process_user_request
    final = await process_user_request(_flattening_manager(FLAT_ANSWER), _worker,
                                       [{"role": "user", "content": "q"}],
                                       "test-model", None, None, 0)
    assert f"Also in s.36: [s.36(2)]({S36}) exempts information" in final["content"]


async def test_the_research_manager_answer_is_left_alone():
    from src.agent.agent_core import process_user_request
    from src.agent.provider_factory import set_request_provider_config
    set_request_provider_config({"_provider": "openrouter", "_research_mode": "legislation_only",
                                 "_chat_mode": "research", "model": "test-model",
                                 "_tool_memo_enabled": False})
    try:
        final = await process_user_request(_flattening_manager(FLAT_ANSWER), _worker,
                                           [{"role": "user", "content": "q"}],
                                           "test-model", None, None, 0)
    finally:
        set_request_provider_config({})
    assert "Also in s.36" not in final["content"]


# --- the instrument: `replay_report siblings` ---------------------------------


def _write_run(d, turns):
    import json
    d.mkdir(parents=True, exist_ok=True)
    (d / "6348_rep1.json").write_text(json.dumps(
        {"session_id": "6348", "rep": 1, "turns": turns}), encoding="utf-8")


def _turn(mode, report, answer, step=None):
    return {"turn": 1, "chat_mode": mode, "answer": answer,
            "audit": {"delegations": [{"step": step, "report": report}]}}


def test_siblings_counts_link_and_plain_text_separately_per_mode(tmp_path, capsys):
    import tools.replay_report as rr
    kept_answer = f"Under [s.36(1)]({S36}) and s.36(2)."
    dropped_answer = f"Under [s.36(1)]({S36})."
    _write_run(tmp_path / "a", [
        _turn("conversational", PARENTHETICAL, dropped_answer),          # plain, dropped
        _turn("conversational", f"[s.36(1)]({S36}); [s.36(2)]({S36}).", kept_answer),  # link, kept
        _turn("research", PARENTHETICAL, kept_answer),                   # plain, kept
        _turn("deep_research", PARENTHETICAL, dropped_answer, step=1),   # never counted
    ])
    assert rr.main(["--dir", str(tmp_path / "a"), "siblings", "--list"]) == 0
    out = capsys.readouterr().out
    conv = next(ln for ln in out.splitlines() if ln.strip().startswith("conversational"))
    # The linked turn cites both subsections as links, so each is the other's
    # sibling: 2 of 2. The plain-text one was dropped: 0 of 1.
    assert "2 of 2 kept" in conv and "0 of 1 kept" in conv
    res = next(ln for ln in out.splitlines() if ln.strip().startswith("research"))
    assert "1 of 1 kept" in res
    assert "deep_research" not in out
    assert "dropped, plain text: a 6348 1 1 s.36(2)" in out


def test_siblings_needs_the_answer_to_keep_another_subsection(tmp_path, capsys):
    """An answer that drops the whole section has not dropped a sibling; that
    is a different failure, and counting it here would blur the rate."""
    import tools.replay_report as rr
    _write_run(tmp_path / "a", [_turn("conversational", PARENTHETICAL, "Nothing on s.36.")])
    rr.main(["--dir", str(tmp_path / "a"), "siblings"])
    assert "conversational" not in capsys.readouterr().out.split("mode")[-1]


def test_siblings_pools_and_excludes_directories(tmp_path, capsys):
    import tools.replay_report as rr
    _write_run(tmp_path / "a", [_turn("conversational", PARENTHETICAL, f"[s.36(1)]({S36})")])
    _write_run(tmp_path / "b", [_turn("conversational", PARENTHETICAL, f"[s.36(1)]({S36})")])
    rr.main(["--dir", str(tmp_path / "a"), "siblings", "--all-dirs"])
    assert "0 of 2 kept" in capsys.readouterr().out
    rr.main(["--dir", str(tmp_path / "a"), "siblings", "--all-dirs", "--exclude", "b"])
    assert "0 of 1 kept" in capsys.readouterr().out
