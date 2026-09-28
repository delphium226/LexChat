"""P3.2 candidate lever: the dry run of "the lawyer's challenge is a retrieval
hint" (`tools/provision_hints.py`).

Nothing here is product code. These pin the parts the dry run's counts rest
on, above all the resolution rule, whose failure mode is Invariant 1's worst
case: handing one instrument's text over under another's name. Every sentence
and provision text below is synthetic.
"""

import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import provision_hints as ph  # noqa: E402


def labels(text):
    return [r.label() for r in ph.extract_provision_refs(text)]


def test_extracts_each_kind_and_lists():
    assert labels("Articles 38 and 39 apply, and Article 24(4).") == [
        "article 38", "article 39", "article 24(4)"]
    assert labels("see s.35(1)(b) and ss.35A and 35ZA") == [
        "section 35(1)(b)", "section 35A", "section 35ZA"]
    assert labels("under regulation 3(2)(a)") == ["regulation 3(2)(a)"]
    assert labels("Schedule B1 applies") == ["schedule B1"]


def test_annex_forms_and_no_double_count():
    assert labels("Chapter V of Annex XIV") == ["Annex XIV Ch V"]
    assert labels("Section 3 of Chapter II of Annex X") == ["Annex X Ch II s.3"]
    assert labels("Annex XIII, Chapter XI") == ["Annex XIII Ch XI"]


def test_an_instrument_number_is_not_a_regulation_reference():
    assert labels("Regulation (EC) No 555/2008 and Regulation 555/2008") == []


def test_eu_and_url_mentions():
    got = [lid for _, lid in ph.instrument_mentions(
        "Regulation (EU) No 777/2012 and http://www.legislation.gov.uk/id/asp/2003/77", None)]
    assert "eur/2012/777" in got and "asp/2003/77" in got


def _ref(text, i=0):
    return ph.extract_provision_refs(text)[i]


def test_link_is_of_the_right_after_the_reference():
    text = "section 4 of the Example Act 2013 and section 9 of the Other Act 2014"
    mentions = [(text.index("Example"), "asp/2013/1"), (text.index("Other"), "asp/2014/9")]
    assert ph.linked_instrument(text, _ref(text, 0), mentions) == "asp/2013/1"
    assert ph.linked_instrument(text, _ref(text, 1), mentions) == "asp/2014/9"
    loose = "Regulation 3(2)(a) says a thing about the Other Act 2014"
    assert ph.linked_instrument(loose, _ref(loose), [(loose.index("Other"), "x/1/1")]) is None


def test_an_instrument_named_inside_quotes_is_not_the_owner():
    text = 'Regulation 3(2)(a) exempts a project that "is development to which the Other Regulations 2017 apply".'
    mentions = [(text.index("Other"), "ssi/2003/88")]
    assert ph._unquoted(mentions, text) == []


def test_paragraph_cut_and_a_missing_level_is_reported():
    item = {"text": "Section 36) **Power**\n\n1) The court may—\n\ta) one,\n\tb) two.\n"
                    "2) Further—\n\ta) three,\n\ti) four.\n"}
    cut, how = ph.slice_provision(item, _ref("section 36(1)(i)"))
    assert cut.startswith("1) The court") and "2) Further" not in cut
    assert how == "paragraph cut, (i) not present"
    cut, how = ph.slice_provision(item, _ref("section 36(2)"))
    assert cut.startswith("2) Further") and how == "paragraph cut"


def test_annex_chapter_cut_only_on_a_heading():
    item = {"text": "ANNEX IX intro CHAPTER IV rules four CHAPTER V RULES FOR X list CHAPTER VI six"}
    cut, how = ph.slice_provision(item, _ref("Chapter V of Annex IX"))
    assert cut == "CHAPTER V RULES FOR X list " and how == "chapter cut"
    item = {"text": "ANNEX IX no chapter headings survive here"}
    _, how = ph.slice_provision(item, _ref("Annex IX, Chapter V"))
    assert how == "chapter heading absent"


def test_definitions_cut_for_quoted_terms():
    text = ("For this Regulation: ‘blood’ means whole blood;‘red fats’ means fats "
            "from processing;‘sea oil’ means oil from krill;‘guano’ means guano;")
    cut, how = ph.slice_provision({"text": text}, _ref("Annex I"), ["red fats", "sea oil"])
    assert how == "definitions cut"
    assert "red fats" in cut and "sea oil" in cut and "blood" not in cut and "guano" not in cut


def test_concordance_only_defined_terms_and_never_a_nested_pair():
    items = [{"uri": "u/annex/I", "text": "‘red fat’ means x; ‘sea oil’ means y;"},
             {"uri": "u/annex/X", "text": "Derivatives from red fats or sea oil shall be made."}]
    hits = ph.concordance(items, ["red fat", "sea oil", "apply"])
    assert any("red fats or sea oil" in ex for _, ex in hits)
    assert ph.concordance(items, ["apply", "made"]) == []
    nested = [{"uri": "u", "text": "‘plan’ means a; ‘XY plan’ means b; an XY plan"}]
    assert ph.concordance(nested, ["plan", "XY plan"]) == []


class _FakeLex:
    def __init__(self, titles):
        self.titles = titles

    def title_of(self, lid):
        return self.titles[lid]


def test_nickname_breaks_a_tie_only_when_one_title_matches():
    lex = _FakeLex({"eur/2011/1": "Commission Regulation implementing Regulation 9/2009",
                    "eur/2009/9": "Regulation laying down health rules"})
    holders = [("eur/2009/9", {}), ("eur/2011/1", {})]
    text = "Article 25(4) of the Implementing Regulation says so"
    assert ph.nickname_pick(text, _ref(text), holders, lex)[0] == "eur/2011/1"
    text = "Article 43(3) of the Control Regulation says so"
    assert ph.nickname_pick(text, _ref(text), holders, lex) is None
