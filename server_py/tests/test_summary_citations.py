"""P3.45: a case citation the summariser wrote that its source does not hold.

Batch 12 E found stored summaries carrying case citations their raw source
never held; batch 13 A measured it over every stored summary (37 of 5,808 move
under this check) and built the check at the summary seam. What this file pins:

1. the citation forms read, and that a citation the source holds in ANOTHER
   written form is held (the detector validated in both directions);
2. a number is never held by a longer one (no prefix match);
3. what goes: the citation alone where the source names the case; the list
   item, heading block or sentence where it does not (and the list a removed
   sentence introduces); the citation alone where no name can be read;
4. what stays: everything else, byte for byte; a citation the research
   question carries; the product's own appended blocks;
5. the tidy-up: no empty brackets, no broken emphasis, no doubled blank line;
6. fail-soft and idempotent;
7. the wiring: every summary `summarise_for_query` returns, and a local-cache
   hit in `run_worker_tool`.

Fixtures are synthetic ("Widget Co v Example Ltd", ssi/1901/3).
"""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agent import summarisation as summ  # noqa: E402
from src.agent.agent_shared import run_worker_tool  # noqa: E402
from src.agent.provider_factory import set_request_provider_config  # noqa: E402
from src.services import local_prompt_cache as lpc  # noqa: E402
from src.utils import summary_citations as sc  # noqa: E402
from src.utils.summary_citations import (  # noqa: E402
    find_citations,
    name_before,
    name_held,
    SourceIndex,
    strip_unsourced_citations,
    unsourced_citations,
)


def _raw(*texts) -> str:
    """A case-law search result as the executor returns it (JSON)."""
    return json.dumps({"results": [{"title": t, "ncn": "", "url": ""} for t in texts]})


def _strip(summary, raw, query=""):
    return strip_unsourced_citations(summary, raw, query)


# ---------------------------------------------------------------------------
# 1. forms read; another written form of a held citation is held
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,kind", [
    ("[1901] UKSC 1", "ncn"),
    ("[1901] EWCA Civ 2", "ncn"),
    ("[1901] EWHC 3 (Admin)", "ncn"),
    ("[1901] CSIH 4", "ncn"),
    ("[1901] AC 5", "report"),
    ("[1901] 2 QB 6", "report"),
    ("[1901] 1 W.L.R. 7", "report"),
    ("[1901] ECR I-8", "report"),
    ("(1901) 15 Ch D 9", "report"),
    ("1901 SC 10", "scot"),
    ("1901 S.L.T. 11", "scot"),
    ("1901 SC (HL) 12", "scot"),
    ("https://caselaw.nationalarchives.gov.uk/uksc/1901/13", "url"),
])
def test_each_form_is_read(text, kind):
    found = find_citations(f"See Widget Co v Example Ltd {text} on this.")
    assert [c.kind for c in found] == [kind]
    assert found[0].text == text


@pytest.mark.parametrize("summary_cite,raw_text", [
    ("[1901] UKSC 1", "Widget Co v Example Ltd [1901] UKSC 1"),
    ("[1901] UKSC 1", "Widget Co v Example Ltd\n[1901] UKSC 1"),
    ("[1901] UKSC 1", "https://caselaw.nationalarchives.gov.uk/uksc/1901/1"),
    ("[1901] UKSC 1", "Widget Co v Example Ltd [1901] UKSC1"),                # no space
    ("[1901] EWCA Civ 2", "Widget Co v Example Ltd [1901] EWCA Civ. 2"),        # Civ.
    ("[1901] EWCA Civ 2", "Widget Co v Example Ltd [1901] EWCA (Civ) 2"),       # (Civ)
    ("[1901] EWHC 3 (Comm)", "Widget Co v Example Ltd [1901] EWHC [3 (Comm)."),  # stray [
    ("[1901] EWHC 3 (Admin)", "Widget Co v Example Ltd [1901] EWHC 3"),         # division left out
    ("[1901] UKSC 4", 'a search for "Widget Co" "1901] UKSC 4"'),              # a query's own text
    ("[1901] AC 5", "Widget Co v Example Ltd [1901] A.C. 5"),
    ("[1901] AC 5", "Widget Co v Example Ltd [1901] AC per Lord Gadget at 5 (HL)"),
    ("[1901] 2 All ER 6", "Widget Co v Example Ltd [1901] 2 All 6."),           # series abbreviated
    ("(1901) 15 Ch D 9", "Widget Co v Example Ltd 15 Ch D 9"),                 # no year
    ("1901 SLT 11", "Widget Co v Example Ltd 1901 S.L.T. 11"),
])
def test_a_citation_the_source_holds_in_another_form_is_held(summary_cite, raw_text):
    summary = f"* **Widget Co v Example Ltd {summary_cite}:** the rule."
    out, recs = _strip(summary, json.dumps({"text": raw_text}))
    assert recs == [] and out == summary


def test_a_json_escaped_line_break_inside_a_citation_is_held():
    raw = json.dumps({"full_text": "applied in Widget Co v Example Ltd [1901] EWCA\nCiv\n2."})
    assert "\\n" in raw
    summary = "Widget Co v Example Ltd [1901] EWCA Civ 2 is applied."
    assert _strip(summary, raw) == (summary, [])


# ---------------------------------------------------------------------------
# 2. no prefix match
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("summary_cite,raw_text", [
    ("[1901] UKSC 1", "Widget Co v Example Ltd [1901] UKSC 12"),
    ("[1901] AC 1", "Widget Co v Example Ltd [1901] AC 12"),
    ("1901 SC 1", "Widget Co v Example Ltd 1901 SC 12"),
])
def test_a_number_is_not_held_by_a_longer_one(summary_cite, raw_text):
    summary = f"Widget Co v Example Ltd {summary_cite} applies."
    out, recs = _strip(summary, json.dumps({"text": raw_text}))
    assert [r["citation"] for r in recs] == [summary_cite]
    assert summary_cite not in out


# ---------------------------------------------------------------------------
# 3. what goes
# ---------------------------------------------------------------------------

def test_the_source_names_the_case_so_only_the_citation_goes():
    raw = _raw("Widget Co Ltd v Example Ltd", "[1901] UKSC 12")
    summary = ("### Authorities\n"
               "*   **Widget Co Ltd v Example Ltd [1901] UKSC 7:** Cited on the meaning of widget.\n"
               "*   **Other Ltd v Thing Ltd [1901] UKSC 12:** held.")
    out, recs = _strip(summary, json.dumps({"text": "Widget Co Ltd v Example Ltd [1901] AC 3; "
                                                     "Other Ltd v Thing Ltd [1901] UKSC 12"}))
    assert [r["action"] for r in recs] == ["citation"]
    assert out == ("### Authorities\n"
                   "*   **Widget Co Ltd v Example Ltd:** Cited on the meaning of widget.\n"
                   "*   **Other Ltd v Thing Ltd [1901] UKSC 12:** held.")
    assert raw  # the helper is used elsewhere


def test_one_side_of_the_name_held_whole_is_enough():
    """A judgment names a case by one party ("Widgetco at [35]")."""
    raw = json.dumps({"text": "the widget rule: Widgetco at [35]."})
    summary = "*   **Widgetco Ltd v Smallbody [1901] UKSC 33:** Cited on the widget rule."
    out, recs = _strip(summary, raw)
    assert recs[0]["action"] == "citation"
    assert out == "*   **Widgetco Ltd v Smallbody:** Cited on the widget rule."


def test_every_word_of_a_side_is_needed():
    """One common word ("Bank") does not vouch for a case."""
    raw = json.dumps({"text": "Gadget Bank N.V. v Other Ltd [1901] EWHC 5 (Ch)"})
    summary = "*   **Widgetland Bank Plc v Smallbody [1901] EAT 43:** reinforces the approach."
    out, recs = _strip(summary, raw)
    assert recs[0]["action"] == "item" and out == ""


def test_a_public_office_does_not_vouch_for_a_case():
    raw = json.dumps({"text": "the Widget Environs Agency must be consulted"})
    summary = ("1.  **Widgetson v Minister for the Environs [1901] ECR I-11:** projects are broad.\n"
               "2.  **Gadgetson v Secretary of State for the Environs [1901] 2 AC 13:** strict.")
    out, recs = _strip(summary, raw)
    assert [r["action"] for r in recs] == ["item", "item"] and out == ""


def test_an_acronym_is_held_by_the_initials_of_the_source_name():
    """The other party is not in the source: the acronym alone holds the name."""
    raw = json.dumps({"text": "Widget Components Limited (Appellant)"})
    summary = "3.  **WCL v Gadgetry [1901] UKSC 39:** the intersection of the two codes."
    out, recs = _strip(summary, raw)
    assert recs[0]["action"] == "citation"
    assert out == "3.  **WCL v Gadgetry:** the intersection of the two codes."
    assert _strip(summary, json.dumps({"text": "Widget Holdings Limited"}))[0] == ""


def test_a_case_the_source_never_names_takes_its_list_item_and_nested_lines():
    raw = _raw("Other Ltd v Thing Ltd")
    summary = ("Relevant authorities:\n"
               "1.  **Widget Co v Example Ltd [1901] UKSC 33**\n"
               "    *   **Threshold:** the widget rule governs.\n"
               "\n"
               "    *   **Application:** written terms may be disregarded.\n"
               "2.  **Other Ltd v Thing Ltd:** a held case.")
    out, recs = _strip(summary, raw)
    assert [r["action"] for r in recs] == ["item"]
    assert out == "Relevant authorities:\n2.  **Other Ltd v Thing Ltd:** a held case."


def test_a_later_sentence_of_a_list_item_goes_alone():
    """The item's own first sentence is the source's; only the sentence that
    carries the summariser's case goes, not the whole item."""
    raw = _raw("Other Ltd v Thing Ltd")
    summary = ("*   **Widget duty:** Section 5 imposes the duty. It follows "
               "Gadgetry v Smallbody [1902] UKSC 2 on the test.\n"
               "*   Held.")
    out, recs = _strip(summary, raw)
    assert [r["action"] for r in recs] == ["sentence"]
    assert out == "*   **Widget duty:** Section 5 imposes the duty.\n*   Held."


def test_a_heading_that_is_the_case_takes_its_block():
    raw = _raw("Other Ltd v Thing Ltd")
    summary = ("Intro.\n\n"
               "**1. Widget Co v Example Ltd [1901] ICR 15**\n"
               "This case establishes that the tribunal must:\n"
               "*   Look at the written agreement.\n"
               "\n"
               "**2. The Threshold**\n"
               "Held text.")
    out, recs = _strip(summary, raw)
    assert [r["action"] for r in recs] == ["block"]
    assert out == "Intro.\n\n**2. The Threshold**\nHeld text."


def test_in_prose_the_sentence_goes_and_the_rest_of_the_paragraph_stays():
    raw = _raw("Other Ltd v Thing Ltd")
    summary = ("**Case Law Note:** Searches yield limited results. Research should focus on "
               "*Widget Co v Example Ltd [1901] UKSC 35* regarding standing. The rest is held.")
    out, recs = _strip(summary, raw)
    assert [r["action"] for r in recs] == ["sentence"]
    assert out == "**Case Law Note:** Searches yield limited results. The rest is held."


def test_a_removed_sentence_takes_the_list_it_introduces():
    raw = json.dumps({"text": "Section 5: the duty of care for widgets."})
    summary = ("Note: this is determined by common law. Courts apply the test derived from "
               "*Widget Co v Example (Engineers) Ltd [1901] FSR 17*:\n"
               "1.  The widget must be sound.\n"
               "2.  It must be delivered.\n"
               "\n"
               "Section 5 imposes the duty.")
    out, recs = _strip(summary, raw)
    assert [r["action"] for r in recs] == ["sentence"]
    assert out == "Note: this is determined by common law.\n\nSection 5 imposes the duty."


def test_the_closing_emphasis_of_a_line_stays_when_its_last_sentence_goes():
    raw = _raw("Other Ltd v Thing Ltd")
    summary = ("*Note: the offence is common law. The thresholds come from precedent "
               "(notably R v Widget's Reference (No 3 of 1901) [1901] EWCA Crim 19).*")
    out, recs = _strip(summary, raw)
    assert recs[0]["action"] == "sentence"
    assert out == "*Note: the offence is common law.*"


def test_a_section_left_empty_takes_its_heading_and_italic_note_but_not_the_product_block():
    raw = json.dumps({"rows": [{"provision": "section 2", "text": "words substituted"}]})
    summary = ("Changes: section 2 amended.\n\n"
               "---\n\n"
               "### **Case Law Search Results**\n"
               "*Keywords: \"Widget Act 1901\"*\n"
               "\n"
               "1.  **Widget Co v Example Ltd [1901] UKSC 27:** limits of widgetry.\n"
               "2.  **Reference by the Gadget Advocate respecting the Widget Bill [1901] UKSC 29:** "
               "limits of section 9.\n"
               "\n"
               "[CHANGE RECORD — 3 recorded relation(s) for ssi/1901/3: changes made TO it.]")
    out, recs = _strip(summary, raw)
    assert [r["action"] for r in recs] == ["item", "item"]
    assert "Case Law Search Results" not in out and "Keywords" not in out
    assert out.endswith("[CHANGE RECORD — 3 recorded relation(s) for ssi/1901/3: changes made TO it.]")
    assert out.startswith("Changes: section 2 amended.\n\n---\n\n")
    assert "\n\n\n" not in out


def test_where_no_name_can_be_read_only_the_citation_goes():
    raw = json.dumps({"text": "Widget Co v Example Ltd [1901] EWHC 51 (QB)"})
    summary = ("*   *Widget Co v Example Ltd* [1901] EWHC 51 (QB) / [1902] EWHC 51 (QB)\n"
               "*   **URL:** https://caselaw.nationalarchives.gov.uk/ukca/crim/1901/53\n"
               "*   **Date:** 1901-01-01")
    out, recs = _strip(summary, raw)
    assert [r["action"] for r in recs] == ["citation", "citation"]
    assert out == ("*   *Widget Co v Example Ltd* [1901] EWHC 51 (QB)\n"
                   "*   **Date:** 1901-01-01")


def test_in_a_list_of_authorities_only_the_summarisers_case_goes():
    """Forms no stored summary has: the rest of the line is the source's."""
    raw = json.dumps({"text": "Widget Co v Example Ltd"})
    for summary in ("- **Widgets:** *Widget Co v Example Ltd* [1901] UKSC 1; *Gadgetry v Smallbody* [1902] UKSC 2.",
                    "- **Widgets:** *Gadgetry v Smallbody* [1902] UKSC 2; *Widget Co v Example Ltd* [1901] UKSC 1."):
        out, recs = _strip(summary, raw)
        assert sorted(r["action"] for r in recs) == ["case", "citation"]
        assert out == "- **Widgets:** *Widget Co v Example Ltd*."
    out, recs = _strip("Widget Co v Example Ltd [1901] UKSC 1 (Gadgetry v Smallbody [1902] UKSC 2) applies.",
                       raw)
    assert out == "Widget Co v Example Ltd applies."


def test_inside_a_sentence_the_case_is_not_cut_out_of_it():
    raw = json.dumps({"text": "Widget Co v Example Ltd"})
    out, recs = _strip("Intro. The test from Gadgetry v Smallbody [1902] UKSC 2 applies, "
                       "as in Widget Co v Example Ltd [1901] UKSC 1.", raw)
    assert out == "Intro." and recs[0]["action"] == "sentence"
    # the case stands before a comma, but prose runs into it from the left
    out, recs = _strip("Intro. Courts follow Gadgetry v Smallbody [1902] UKSC 2, "
                       "as in Widget Co v Example Ltd [1901] UKSC 1.", raw)
    assert out == "Intro." and recs[0]["action"] == "sentence"


def test_a_long_bold_line_is_a_sentence_not_a_heading():
    raw = _raw("Other Ltd v Thing Ltd")
    out, recs = _strip("Intro.\n**Gadgetry v Smallbody [1902] UKSC 2 is the leading authority on all "
                       "widget questions in this field**\nNext para.", raw)
    assert recs[0]["action"] == "sentence" and out == "Intro.\nNext para."


def test_a_link_and_a_comma_left_behind_are_tidied():
    raw = json.dumps({"text": "Widget Co v Example Ltd"})
    assert _strip("See [Widget Co v Example Ltd](https://caselaw.nationalarchives.gov.uk/uksc/1901/1) "
                  "on this.", raw)[0] == "See Widget Co v Example Ltd on this."
    assert _strip("Held in Widget Co v Example Ltd, 1901 SC 340, and applied.", raw)[0] == \
        "Held in Widget Co v Example Ltd, and applied."


def test_prose_before_a_name_is_not_read_as_part_of_it():
    def nb(text):
        return name_before(text, find_citations(text)[-1])
    assert nb("Held in Widget Co v Example Ltd, 1901 SC 340") == "Widget Co v Example Ltd"
    assert nb("R (on the application of Widget) v Gadget [1901] UKSC 3") == \
        "R (on the application of Widget) v Gadget"
    assert nb("relied on Widget v Gadget [1901] UKSC 3") == "Widget v Gadget"
    assert nb("*   **Gadget plc v Widgetry Ltd [1901] UKSC 9:**") == "Gadget plc v Widgetry Ltd"


def test_a_reference_the_source_does_not_name_takes_its_item():
    raw = json.dumps({"text": "the Widget Bill was referred"})
    summary = ("1.  **Reference by the Gadget Advocate respecting the Widget Bill [1901] UKSC 29:** "
               "the limits.\n2.  Held.")
    out, recs = _strip(summary, raw)
    assert recs[0]["name"].startswith("Reference by the Gadget Advocate")
    assert recs[0]["action"] == "item" and out == "2.  Held."


def test_the_name_read_before_a_citation():
    def nb(text):
        return name_before(text, find_citations(text)[-1])
    assert nb("1. **Widget (South East) Ltd v Minister of Gadgets [1901] 2 QB 45**") == \
        "Widget (South East) Ltd v Minister of Gadgets"
    assert nb("4. **Relevant to Widgetland: Widget City Council v Gadget [1901] CSIH 37**") == \
        "Widget City Council v Gadget"
    assert nb("principles established in *Widget v Gadget Ministers [1901] UKSC 35*") == \
        "Widget v Gadget Ministers"
    assert nb("**R (Widget) v Secretary of State for Gadgets [1901] UKSC 5:**") == \
        "R (Widget) v Secretary of State for Gadgets"
    assert nb("(as applied in Widget v Gadget [1901] UKSC 1 and [1902] UKSC 2)") == ""
    assert nb("the court said in 1901 [1901] UKSC 3") == ""


def test_a_lower_case_common_word_does_not_vouch_for_a_party():
    """A party's word counts only as the source writes a name: capitalised
    (or in capitals), not as a common word in its prose."""
    idx = SourceIndex(json.dumps({"text": "the widget bank was dissolved"}))
    assert name_held("Widget Bank v Smallbody", idx) is False
    idx = SourceIndex(json.dumps({"text": "WIDGET BANK v OTHER"}))
    assert name_held("Widget Bank v Smallbody", idx) is True


def test_prose_after_the_v_is_not_a_name():
    def nb(text):
        return name_before(text, find_citations(text)[-1])
    assert nb("Widget v Gadget regarding standing [1901] UKSC 3") == ""


def test_an_abbreviation_does_not_end_a_sentence():
    raw = _raw("Other Ltd v Thing Ltd")
    out, recs = _strip("Intro. Gadgetry Co. Ltd v Smallbody [1902] UKSC 2 applies here. Rest.", raw)
    assert recs[0]["action"] == "sentence" and out == "Intro. Rest."
    assert recs[0]["name"] == "Gadgetry Co. Ltd v Smallbody"       # "Intro." ends a sentence


def test_an_emphasis_left_empty_goes():
    raw = _raw("Other Ltd v Thing Ltd")
    assert _strip("Held **[1902] UKSC 2** here.", raw)[0] == "Held here."


def test_name_held_is_none_without_a_distinctive_word():
    idx = SourceIndex(json.dumps({"text": "nothing"}))
    assert name_held("", idx) is None
    assert name_held("R v Secretary of State for the Home Department", idx) is None


# ---------------------------------------------------------------------------
# 4. what stays
# ---------------------------------------------------------------------------

def test_a_summary_with_nothing_unheld_comes_back_byte_for_byte():
    raw = json.dumps({"text": "Widget Co v Example Ltd [1901] UKSC 1"})
    summary = ("Intro.\n\n\n\n*   **Widget Co v Example Ltd [1901] UKSC 1** \n"
               "( see )  ** **  odd   spacing\n")
    assert _strip(summary, raw) == (summary, [])


def test_a_summary_with_no_citation_comes_back_unchanged():
    summary = "Section 5 imposes a duty (see s.6)."
    assert _strip(summary, json.dumps({"text": ""})) == (summary, [])


def test_a_citation_the_research_question_carries_is_kept():
    raw = _raw("Other Ltd v Thing Ltd")
    summary = "*(Note: the text does not discuss Widget Co v Example Ltd [1901] AC 49.)*"
    assert _strip(summary, raw, query="the effect of Widget Co v Example Ltd [1901] AC 49") == \
        (summary, [])
    assert _strip(summary, raw, query="the effect of Widget Co [1901] UKSC 47")[1] != []


def test_a_neutral_citation_the_research_question_carries_is_kept():
    raw = _raw("Other Ltd v Thing Ltd")
    summary = "*   **Widget Co v Example Ltd [1901] UKSC 47:** the question's own case."
    assert _strip(summary, raw, query="does Widget Co v Example Ltd [1901] UKSC 47 apply") == \
        (summary, [])


def test_a_heading_with_more_left_under_it_stays():
    raw = _raw("Other Ltd v Thing Ltd")
    summary = ("### Authorities\n"
               "*Keywords: widgets*\n"
               "1.  **Gadgetry v Smallbody [1902] UKSC 2:** invented.\n"
               "Section 5 imposes the duty.\n"
               "Section 6 qualifies it.")
    out, _ = _strip(summary, raw)
    assert out == ("### Authorities\n*Keywords: widgets*\n"
                   "Section 5 imposes the duty.\nSection 6 qualifies it.")


def test_only_the_line_with_the_unheld_citation_changes():
    raw = _raw("Other Ltd v Thing Ltd [1901] UKSC 3")
    lines = ["# Summary", "", "Para one  with  double spaces.", "",
             "*   **Other Ltd v Thing Ltd [1901] UKSC 3:** held.",
             "*   **Gadget plc v Widgetry [1901] UKSC 9:** invented.", "", "Last."]
    out, _ = _strip("\n".join(lines), raw)
    assert out.split("\n") == lines[:5] + lines[6:]


# ---------------------------------------------------------------------------
# 5. the tidy-up
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("before,after", [
    ("in the case of **Widget Co v Example Ltd [1901] EWHC 21 (TCC)**.",
     "in the case of **Widget Co v Example Ltd**."),
    ("a judgment (*Widget Co v Example Ltd* [1901] EWHC 21 (TCC)) about widgets",
     "a judgment (*Widget Co v Example Ltd*) about widgets"),
    ("(specifically *Widget Co v Example Ltd [1901] CSIH 7*) concerning",
     "(specifically *Widget Co v Example Ltd*) concerning"),
    ("*   **Gadgets:** *Widget Co v Example Ltd (No.6)* [1901] 1 WLR 23; *Other v Thing* [1901] 1 WLR 35.",
     "*   **Gadgets:** *Widget Co v Example Ltd (No.6)*; *Other v Thing* [1901] 1 WLR 35."),
    ("**Widget Co v Example Ltd** (also cited as [1901] AC 9) is held.",
     "**Widget Co v Example Ltd** is held."),
])
def test_what_a_removed_citation_leaves_is_tidied(before, after):
    raw = json.dumps({"text": "Widget Co v Example Ltd; Other v Thing [1901] 1 WLR 35"})
    out, recs = _strip(before, raw)
    assert recs and out == after


# ---------------------------------------------------------------------------
# 6. fail-soft and idempotent
# ---------------------------------------------------------------------------

def test_an_error_returns_the_summary_unchanged(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("x")
    monkeypatch.setattr(sc, "_strip", boom)
    summary = "Widget Co v Example Ltd [1901] UKSC 33."
    assert strip_unsourced_citations(summary, "{}") == (summary, [])


def test_the_check_is_idempotent():
    raw = _raw("Other Ltd v Thing Ltd")
    summary = ("1.  **Widget Co v Example Ltd [1901] UKSC 33:** invented.\n"
               "2.  **Other Ltd v Thing Ltd [1901] UKSC 7:** named, citation invented.\n"
               "3.  Held.")
    once, _ = _strip(summary, raw)
    assert once == "2.  **Other Ltd v Thing Ltd:** named, citation invented.\n3.  Held."
    assert _strip(once, raw) == (once, [])


def test_unsourced_citations_reports_the_name_and_whether_it_is_held():
    raw = _raw("Other Ltd v Thing Ltd")
    got = unsourced_citations("Other Ltd v Thing Ltd [1901] UKSC 7; Widget Co v Example [1901] UKSC 8",
                              raw)
    assert [(u.citation.text, u.name, u.name_held) for u in got] == [
        ("[1901] UKSC 7", "Other Ltd v Thing Ltd", True),
        ("[1901] UKSC 8", "Widget Co v Example", False)]


# ---------------------------------------------------------------------------
# 7. the wiring
# ---------------------------------------------------------------------------

INVENTED = "*   **Widget Co v Example Ltd [1901] AC 25:** the leading case on widgets."
HELD = "Section 5 of the Widget Act 1901 defines a widget."
SOURCE = json.dumps({"results": [{"text": "Section 5 defines widget.", "url": "x"}]})


def _chunk_returning(text):
    async def chunk_fn(t, q, m, timing_collector=None):
        return text
    return chunk_fn


def test_a_single_chunk_summary_is_checked():
    out, degraded = asyncio.run(summ.summarise_for_query(
        SOURCE, "widget", "m", chunk_fn=_chunk_returning(HELD + "\n" + INVENTED)))
    assert out == HELD and degraded is False


def test_a_multi_chunk_summary_is_checked_against_the_whole_text(monkeypatch):
    monkeypatch.setattr(summ, "SUMMARISE_CHUNK_CHARS", 40)
    text = "Section 5 defines widget. " + "x" * 30 + " Widget Co v Example Ltd [1901] UKSC 3"
    calls = []

    async def chunk_fn(t, q, m, timing_collector=None):
        calls.append(t)
        # each partial cites a case; only one of them is in the whole text
        return "Widget Co v Example Ltd [1901] UKSC 3 held.\n" + INVENTED
    out, _ = asyncio.run(summ.summarise_for_query(text, "widget", "m", chunk_fn=chunk_fn))
    assert "[1901] UKSC 3" in out and "[1901] AC 25" not in out and len(calls) >= 2


def test_combined_partials_are_checked(monkeypatch):
    """Two chunks whose partials fit one chunk: no consolidation pass."""
    monkeypatch.setattr(summ, "SUMMARISE_CHUNK_CHARS", 40)
    text = "Section 5 defines widget. " + "y" * 30

    async def chunk_fn(t, q, m, timing_collector=None):
        return "S5 [1901] AC 25"
    out, degraded = asyncio.run(summ.summarise_for_query(text, "q", "m", chunk_fn=chunk_fn))
    assert "[1901] AC 25" not in out and "S5" in out and degraded is False


def test_a_failed_consolidation_returns_the_partials_checked(monkeypatch):
    monkeypatch.setattr(summ, "SUMMARISE_CHUNK_CHARS", 40)
    text = "Section 5 defines widget. " + "y" * 60
    calls = []

    async def chunk_fn(t, q, m, timing_collector=None):
        calls.append(t)
        return None if len(calls) > 3 else "Section 5 applies here. Gadgetry v Smallbody [1901] AC 25 too."
    out, degraded = asyncio.run(summ.summarise_for_query(text, "q", "m", chunk_fn=chunk_fn))
    assert len(calls) == 4 and degraded is True
    assert "[1901] AC 25" not in out and "Section 5 applies here." in out


def test_the_wrapper_is_fail_soft_when_the_check_raises(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("x")
    monkeypatch.setattr(sc, "strip_unsourced_citations", boom)
    summary = HELD + "\n" + INVENTED
    assert summ.check_summary_citations(summary, SOURCE, "q") == summary


def test_a_failed_summary_returns_the_raw_text_untouched():
    async def failing(t, q, m, timing_collector=None):
        return None
    raw = "Widget Co v Example Ltd [1901] UKSC 3"
    assert asyncio.run(summ.summarise_for_query(raw, "q", "m", chunk_fn=failing)) == (raw, True)


def test_the_probe_counts_what_the_check_removes_and_keeps():
    """`summary_probe redraw --citations` reads each fresh draw through the
    product's check: unheld before and after, held before and after."""
    import tools.summary_probe as sp
    raw = _raw("Other Ltd v Thing Ltd [1901] UKSC 7")
    draw = ("*   **Other Ltd v Thing Ltd [1901] UKSC 7:** held.\n"
            "*   **Gadgetry v Smallbody [1902] UKSC 2:** invented.")
    assert sp.citation_check(summ, raw, draw, "") == {
        "unheld_before": 1, "unheld_after": 0, "held_before": 1, "held_after": 1,
        "drawn_with_unheld": 1}
    assert sp.citation_check(summ, raw, "Nothing cited.", "")["drawn_with_unheld"] == 0


@pytest.fixture
def _worker_config():
    set_request_provider_config({
        "_research_mode": "legislation_only",
        "_tool_memo_enabled": False,
        "_local_prompt_cache_enabled": False,
    })
    yield
    set_request_provider_config({})


async def _noop_chunk(*a, **k):
    return None


def _run_tool(raw, cache_on, chunk_fn=_noop_chunk):
    with patch("src.agent.agent_shared.execute_worker_tool",
               new=AsyncMock(return_value=raw)), \
         patch("src.agent.agent_shared.get_request_provider_config",
               return_value={"_research_mode": "legislation_only",
                             "_local_prompt_cache_enabled": cache_on}), \
         patch("src.agent.provider_factory.get_summarise_threshold", return_value=50):
        return asyncio.run(run_worker_tool(
            "search_case_law", {"query": "widget"}, "widget", chunk_fn, "test-model"))


def test_a_fresh_summary_reaches_the_worker_checked(_worker_config):
    raw = json.dumps({"results": [{"title": "Other Ltd v Thing Ltd", "ncn": "[1901] UKSC 7",
                                   "url": "https://caselaw.nationalarchives.gov.uk/uksc/1901/7"}],
                      "total": 1})
    out = _run_tool(raw, cache_on=False,
                    chunk_fn=_chunk_returning("Results: Other Ltd v Thing Ltd [1901] UKSC 7.\n" + INVENTED))
    assert out.startswith("Results: Other Ltd v Thing Ltd [1901] UKSC 7.")
    assert "[1901] AC 25" not in out and "Widget Co v Example" not in out


def test_a_local_cache_hit_is_checked_too(_worker_config):
    """A row stored before the check (or under another brief) is served checked."""
    raw = json.dumps({"results": [{"title": "Other Ltd v Thing Ltd", "ncn": "[1901] UKSC 7",
                                   "url": "https://caselaw.nationalarchives.gov.uk/uksc/1901/7"}],
                      "total": 1})
    with patch.object(lpc, "lookup", new=AsyncMock(return_value={
            "summary": "Cached: Other Ltd v Thing Ltd [1901] UKSC 7.\n" + INVENTED,
            "chars_in": 3000})):
        out = _run_tool(raw, cache_on=True)
    assert out.startswith("Cached: Other Ltd v Thing Ltd [1901] UKSC 7.")
    assert "[1901] AC 25" not in out
