"""P3.31: `tools/madeunder_probe` cuts the enabling-power recital out of an SI
preamble and parses its powers. Synthetic preambles only: the Act titles are
invented ("Widget (Scotland) Act 1901"), but each shape is one found on a real
instrument in the feasibility study, named in the test."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import madeunder_probe as mp  # noqa: E402


def _xml(preamble_body: str, title: str = "The Widget Regulations 1901") -> str:
    return (f"<Legislation><ukm:Metadata><dc:title>{title}</dc:title></ukm:Metadata>"
            f"<Secondary><SecondaryPreamble><EnactingText><Para><Text>{preamble_body}"
            f"</Text></Para></EnactingText></SecondaryPreamble><Body/></Secondary></Legislation>")


def _powers(text: str) -> list:
    return [(p["role"], p["act"], p["provisions"])
            for p in mp.parse_powers(mp.recital_window(text))]


def test_two_acts_with_pinpoints():
    # SSI 2007/174's shape.
    t = ("The Scottish Ministers, in exercise of the powers conferred by section 2(2) of the "
         "Widget Act 1901, section 56(1) of the Gadget Act 1902 and of all other powers "
         "enabling them in that behalf, hereby make the following Regulations:")
    assert _powers(t) == [("power", "Widget Act 1901", ["section/2"]),
                          ("power", "Gadget Act 1902", ["section/56"])]


def test_consultation_duty_is_not_a_power():
    # UKSI 2013/1046's shape: s.413 is who was consulted, not a power.
    t = ("The Lord Chancellor, in exercise of the powers conferred by section 411 of the "
         "Widget Act 1901 and section 159(3) of the Gadget Act 1902 as applied by section 96 "
         "of the Gizmo Act 1903, with the concurrence of the Secretary of State, and after "
         "consulting the committee existing for that purpose under section 413 of the Widget "
         "Act 1901, makes the following Rules:")
    assert _powers(t) == [("power", "Widget Act 1901", ["section/411"]),
                          ("power", "Gadget Act 1902", ["section/159"]),
                          ("as applied by", "Gizmo Act 1903", ["section/96"])]


def test_parenthesised_title_and_section_list():
    # SSI 2024/100's shape: Lex Graph's finder returned two sections and no Act.
    t = ("The Scottish Ministers make the following Regulations in exercise of the powers "
         "conferred by sections 1(2)(a), 2 and 23(4) of the Widget and Gadget (Scotland) Act "
         "1901 and all other powers enabling them to do so.")
    assert _powers(t) == [("power", "Widget and Gadget (Scotland) Act 1901",
                           ["section/1", "section/2", "section/23"])]


def test_schedule_paragraph_and_comma_before_the_title():
    t = ("The Secretary of State, in exercise of the powers conferred by section 2(2) of, and "
         "paragraph 1A of Schedule 2 to, the Widget Act 1901, makes the following Regulations:")
    (role, act, provs), = _powers(t)
    assert act == "Widget Act 1901"
    assert provs == ["section/2", "schedule/2/paragraph/1A"]


def test_anaphora_resolve_to_the_earlier_title():
    t = ("In exercise of the powers conferred by section 7 of the Widget (Scotland) Act 1901 "
         "and section 9 of that Act, and section 3 of the 1901 Act, and of all other powers "
         "enabling them, the Scottish Ministers make the following Order:")
    assert [p[1:] for p in _powers(t)] == [("Widget (Scotland) Act 1901", ["section/7"]),
                                           ("Widget (Scotland) Act 1901", ["section/9"]),
                                           ("Widget (Scotland) Act 1901", ["section/3"])]


def test_old_style_recital():
    # The 1960s Scottish Education Department form.
    t = ("In exercise of the powers conferred upon me by section 117 of the Widget "
         "(Scotland) Act 1901, and of all other powers enabling me in that behalf, I hereby "
         "make the following regulations:")
    assert _powers(t) == [("power", "Widget (Scotland) Act 1901", ["section/117"])]


def test_record_states_an_elided_preamble():
    # A revoked SI's revised XML: the preamble is dotted out.
    rec = mp.record_from_xml("ssi/1901/1", _xml(". . . . . . . . ."), "current")
    assert rec["preamble"] == "elided" and rec["powers"] == []


def test_record_flags_a_window_it_cannot_parse():
    rec = mp.record_from_xml("ssi/1901/2", _xml(
        "The Scottish Ministers, in exercise of the powers conferred on them by the Widget "
        "Directive, make the following Regulations:"), "made")
    assert rec["preamble"] == "ok" and rec["powers"] == []
    assert "window_unparsed" in rec["flags"]


def test_reverse_matches_by_title_or_resolved_id():
    recs = [mp.record_from_xml("ssi/1901/3", _xml(
        "The Scottish Ministers, in exercise of the powers conferred by section 95 of the "
        "Widget (Scotland) Act 1901 and all other powers enabling them to do so, make the "
        "following Regulations."), "made"),
        mp.record_from_xml("ssi/1901/4", _xml(
            "The Scottish Ministers, in exercise of the powers conferred by section 9 of the "
            "Widget (Scotland) Act 1901 and all other powers enabling them to do so, make the "
            "following Regulations."), "made")]
    titles = {"Widget (Scotland) Act 1901": "asp/1901/1"}
    assert [r["id"] for r in mp.reverse(recs, titles, "asp/1901/1", "95")] == ["ssi/1901/3"]
    assert [r["id"] for r in mp.reverse(recs, {}, "Widget (Scotland) Act 1901", "95")] == ["ssi/1901/3"]
    # Section 9 does not match section 95, and 95 does not match 9.
    assert [r["id"] for r in mp.reverse(recs, titles, "asp/1901/1", "9")] == ["ssi/1901/4"]


def test_client_refuses_other_hosts_and_the_cap():
    calls = []
    c = mp.PacedClient(cap=1, min_gap=0, transport=lambda m, u, p: (calls.append(u) or (200, b"<x/>")),
                       echo=False)
    c.request("GET", mp.LGU + "/ssi/1901/1/made/data.xml")
    try:
        c.request("GET", mp.LGU + "/ssi/1901/2/made/data.xml")
        raise AssertionError("cap not enforced")
    except RuntimeError:
        pass
    try:
        mp.PacedClient(cap=5, min_gap=0, transport=lambda *a: (200, b""), echo=False).request(
            "GET", "https://example.org/x")
        raise AssertionError("host not refused")
    except ValueError:
        pass


def test_bare_pinpoint_and_comma_and_in_a_section_list():
    # ssi/2021/178 and ssi/2026/170's shapes: s.95 was dropped from both.
    t = ("The Scottish Ministers make the following Regulations in exercise of the powers "
         "conferred by sections 85(2)(g) and (5) and 95 of the Widget (Scotland) Act 1901 and "
         "all other powers enabling them to do so.")
    assert _powers(t) == [("power", "Widget (Scotland) Act 1901", ["section/85", "section/95"])]
    t = ("The Scottish Ministers make the following Regulations in exercise of the powers "
         "conferred by sections 28(2), 79(1), and 95 of the Widget (Scotland) Act 1901 and "
         "all other powers enabling them to do so.")
    assert _powers(t)[0][2] == ["section/28", "section/79", "section/95"]


def test_title_with_dots_and_lower_case_schedule():
    t = ("The Scottish Ministers make the following Regulations in exercise of the powers "
         "conferred on them by sections 2 and 7, and paragraph 7(3) of schedule 1, of the "
         "Widget etc. (Scotland) (No. 2) Act 1901 and all other powers enabling them to do so.")
    (role, act, provs), = _powers(t)
    assert act == "Widget etc. (Scotland) (No. 2) Act 1901"
    assert provs == ["section/2", "section/7", "schedule/1/paragraph/7"]


def test_act_of_sederunt_and_order_in_council_openings():
    t = ("In accordance with section 4 of the Gadget Act 1902, the Court of Session has "
         "approved draft rules. The Court of Session therefore makes this Act of Sederunt "
         "under the powers conferred by section 104(1) of the Widget (Scotland) Act 1901.")
    assert _powers(t) == [("power", "Widget (Scotland) Act 1901", ["section/104"])]
    t = ("His Majesty, in pursuance of the power in section 179(1)(a) of the Widget Act 1901 "
         "and all other powers enabling Him to do so, is pleased to order as follows:")
    assert _powers(t) == [("power", "Widget Act 1901", ["section/179"])]


def test_pdf_ocr_text_is_cleaned():
    # The 1962 scan's shape: line-end hyphenation and a footnote marker.
    state, text = mp.pdf_preamble(
        "STATUTORY INSTRUMENTS\n1901 No. 3\nIn exercise of the powers conferred on me by "
        "section 1 of the Widget and Miscellaneous Govern-\nment Provisions (Scotland) Act "
        "1958(a), with the consent of the Treasury, I hereby make the following order:")
    assert state == "ok"
    assert _powers(text) == [("power",
                              "Widget and Miscellaneous Government Provisions (Scotland) Act 1958",
                              ["section/1"])]


def test_act_cited_after_another_instrument_keeps_its_own_title():
    # The shape of four of the 350 titles that did not resolve.
    t = ("The Scottish Ministers make the following Regulations in exercise of the powers "
         "conferred by regulation 7 of the Widget Contracts (Scotland) Regulations 2016, "
         "sections 1(1) and 4(1) of the Gadget Act 1902 and all other powers enabling them.")
    powers = _powers(t)
    assert [p[1] for p in powers] == ["Gadget Act 1902"]
    assert "regulation/2016" not in powers[0][2]
    assert "section/1" in powers[0][2] and "section/4" in powers[0][2]


def test_anaphor_resolves_to_an_act_named_before_the_recital():
    # ssi/1999/40's shape: the antecedent sits before "in exercise of".
    pre = ("The Scottish Ministers, being designated for the purposes of the Widget Act 1901 "
           "(\"the said Act\"), in exercise of the powers conferred on them by section 14 of the "
           "said Act and of all other powers enabling them in that behalf, hereby make:")
    w = mp.recital_window(pre)
    assert [(p["act"], p["provisions"]) for p in mp.parse_powers(w, mp.text_before_window(pre))] == [
        ("Widget Act 1901", ["section/14"])]
    # Without the preamble before the window it stays unresolved, never guessed.
    assert mp.parse_powers(w)[0]["act"] is None


def test_a_title_may_begin_with_a_provision_word():
    t = ("The Scottish Ministers, in exercise of the powers conferred by section 22 of the "
         "Regulation of Widget Powers Act 1901 and all other powers enabling them, make:")
    assert _powers(t) == [("power", "Regulation of Widget Powers Act 1901", ["section/22"])]


def test_part_and_schedule_with_roman_numerals_are_not_titles():
    t = ("The Scottish Ministers, in exercise of the powers conferred by section 2 of, and "
         "Part I of Schedule 1 to, the Widget Prevention Act 1901, make the following Regulations:")
    (role, act, provs), = _powers(t)
    assert act == "Widget Prevention Act 1901"
    assert "section/2" in provs


def test_unnumbered_and_ordinal_schedules_are_not_titles():
    for sched in ("the Schedule", "the First Schedule"):
        t = (f"The Scottish Ministers, in exercise of the powers conferred by paragraph 3 of "
             f"{sched} to the Widget (Scotland) Act 1901, make the following Regulations:")
        (role, act, provs), = _powers(t)
        assert act == "Widget (Scotland) Act 1901", sched


def test_that_section_points_back_before_the_recital():
    # uksi/2005/556's shape: the EC Act designation names the provision first.
    pre = ("The Secretary of State, being a Minister designated for the purposes of section 2(2) "
           "of the Widget Act 1901 in relation to measures in the veterinary field, in exercise "
           "of the powers conferred on him by that section, after consultation, makes:")
    w = mp.recital_window(pre)
    assert [(p["act"], p["provisions"]) for p in mp.parse_powers(w, mp.text_before_window(pre))] == [
        ("Widget Act 1901", ["section/2"])]
    pre2 = ("The Secretary of State, being designated for the purposes of section 2(2) of the "
            "Widget Act 1901, in exercise of the powers conferred on him by the said section 2(2) "
            "and of all other powers enabling him, hereby makes:")
    w2 = mp.recital_window(pre2)
    assert mp.parse_powers(w2, mp.text_before_window(pre2))[0]["act"] == "Widget Act 1901"


def test_modern_and_older_openings():
    # uksi/2016/612, uksi/2021/1048, uksi/1991/2592 and uksi/2001/2792's shapes.
    cases = [
        ("The Lord Chancellor, with the concurrence of the Lord Chief Justice, makes the following "
         "Order under section 32(1) of the Widget Act 1901. In accordance with section 58(4) of "
         "that Act, a draft of this Order was laid.", [("Widget Act 1901", ["section/32"])]),
        ("The Treasury, under section 118 of the Widget Act 1901, and the Secretary of State, "
         "under section 277 of the Gadget Act 1902 make the following Order.",
         [("Widget Act 1901", ["section/118"]), ("Gadget Act 1902", ["section/277"])]),
        ("In pursuance of paragraph 3 of Schedule 5 to the Widget Act 1901, I hereby make the "
         "following Order:", [("Widget Act 1901", ["schedule/5/paragraph/3"])]),
        ("The Rule Committee, having power under section 2 of the Widget Act 1901 to make rules, "
         "after consulting, make the following Rules:", [("Widget Act 1901", ["section/2"])]),
    ]
    for pre, want in cases:
        w = mp.recital_window(pre)
        got = [(p["act"], p["provisions"]) for p in mp.parse_powers(w, mp.text_before_window(pre))]
        assert got[: len(want)] == want, (pre[:60], got)


def test_the_act_and_source_spacing_and_subsections():
    # uksi/2000/3106's shape: "the Act" defined before the recital opens.
    pre = ("Whereas a draft of these Regulations has been approved under the Widget Act 1901 "
           "(\"the Act\"); now, therefore, the Secretary of State, in exercise of the powers "
           "conferred by sections 2(1), (3) and (4) and 5(4) of the Act, hereby makes:")
    w = mp.recital_window(pre)
    got = mp.parse_powers(w, mp.text_before_window(pre))
    assert [(p["act"], p["provisions"]) for p in got] == [
        ("Widget Act 1901", ["section/2", "section/5"])]
    assert _powers("In exercise of the powers conferred on them by section2(3) and 191of the "
                   "Widget Act 1901 and all other powers, hereby make:")[0][2] == [
        "section/2", "section/191"]
    assert _powers("In exercise of the powers conferred by subsection (4) of section 17 of the "
                   "Widget Act 1901, hereby make:")[0][2] == ["section/17"]


def test_a_dot_inside_a_title_does_not_end_the_recital():
    t = ("The Scottish Ministers, in exercise of the powers conferred by section 7(1) of the "
         "Widget, Nicotine etc. and Care (Scotland) Act 1901. A draft has been laid.")
    assert _powers(t) == [("power", "Widget, Nicotine etc. and Care (Scotland) Act 1901", ["section/7"])]


def test_an_offline_reparse_keeps_the_acts_the_fetch_resolved():
    # The stored record has no preamble before its recital, so "that Act" can
    # only resolve to what the fetch resolved; losing it lost 67 SSIs once.
    rec = {"id": "uksi/1901/1", "window": "conferred by section 2(2) of that Act",
           "powers": [{"act": "Widget Act 1901", "provisions": ["section/2"], "role": "power"}]}
    got = mp.parse_powers(rec["window"], mp.reparse_context(rec))
    assert [(p["act"], p["provisions"]) for p in got] == [("Widget Act 1901", ["section/2"])]
    assert mp.parse_powers(rec["window"])[0]["act"] is None


def test_source_spacing_inside_a_section_list():
    # uksi/2025/1147 and uksi/2024/796: sections lost in the 2009-2026 hand-check.
    assert mp.parse_powers("conferred by sections 4, 84 (2) and 86 (5) of the Widget Act 1901")[0][
        "provisions"] == ["section/4", "section/84", "section/86"]
    assert mp.parse_powers("conferred by sections 114, 115, 120, 122 123 and 140 of the Widget Act 1901")[0][
        "provisions"] == ["section/114", "section/115", "section/120", "section/122", "section/123",
                          "section/140"]


def test_a_lettered_schedule_is_not_a_title():
    # uksi/2009/783's shape: "Schedule A1 to, the ... Act" was read as a title.
    got = mp.parse_powers("conferred by section 65 of, and paragraphs 31 and 33 of Schedule A1 to, "
                          "the Widget Capacity Act 1901")
    assert [p["act"] for p in got] == ["Widget Capacity Act 1901"]


def test_an_offline_reparse_keeps_that_section():
    rec = {"id": "uksi/1901/2", "window": "conferred by that section",
           "powers": [{"act": "Widget Act 1901", "provisions": ["section/2"], "role": "power"}]}
    got = mp.parse_powers(rec["window"], mp.reparse_context(rec))
    assert [(p["act"], p["provisions"]) for p in got] == [("Widget Act 1901", ["section/2"])]


def test_numbers_that_start_with_a_letter():
    got = mp.parse_powers("conferred by section A1(1) of, and paragraphs 31 and 33 of Schedule A1 to, "
                          "the Widget Act 1901")
    assert got[0]["provisions"] == ["section/A1", "schedule/A1/paragraph/31", "schedule/A1/paragraph/33"]
