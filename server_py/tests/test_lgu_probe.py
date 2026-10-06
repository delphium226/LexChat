"""P3.21 / P5.4 (c): `tools/lgu_probe` reads legislation.gov.uk's effects feed
and the commencement date(s) a LEX description states. Synthetic payloads only
(instrument ids and titles are invented: "Widget Order 1901", `ssi/1901/3`)."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import lgu_probe as lp  # noqa: E402


def _effect(typ="coming into force", affected="asp/1901/1", affecting="ssi/1901/3",
            aprov="s. 2", fprov="reg. 2", applied="true", req="true", in_force="",
            aclass="ScottishAct"):
    return (
        f'<entry><content type="text/xml"><ukm:Effect Type="{typ}" EffectId="k{affected}{aprov}" '
        f'AffectedURI="http://www.legislation.gov.uk/id/{affected}" AffectedClass="{aclass}" '
        f'AffectedProvisions="{aprov}" AffectingURI="http://www.legislation.gov.uk/id/{affecting}" '
        f'AffectingClass="ScottishStatutoryInstrument" AffectingProvisions="{fprov}" '
        f'Applied="{applied}" RequiresApplied="{req}" Modified="1901-01-01T00:00:00Z">'
        f'<ukm:InForceDates>{in_force}</ukm:InForceDates></ukm:Effect></content></entry>'
    )


def _feed(*entries, total=None, page=1, pages=1):
    total = len(entries) if total is None else total
    return (
        '<?xml version="1.0" encoding="utf-8"?><feed xmlns="http://www.w3.org/2005/Atom" '
        'xmlns:leg="http://www.legislation.gov.uk/namespaces/legislation" '
        'xmlns:ukm="http://www.legislation.gov.uk/namespaces/metadata" '
        'xmlns:openSearch="http://a9.com/-/spec/opensearch/1.1/">'
        f'<openSearch:itemsPerPage>50</openSearch:itemsPerPage><leg:page>{page}</leg:page>'
        f'<leg:totalPages>{pages}</leg:totalPages><openSearch:totalResults>{total}'
        '</openSearch:totalResults>' + "".join(entries) + "</feed>"
    )


DATED = '<ukm:InForce Applied="true" Date="1901-10-08" Qualification="wholly in force"/>'
PROSPECTIVE = '<ukm:InForce Applied="false" Prospective="true" Qualification=""/>'


# ---- the feed -------------------------------------------------------------

def test_a_dated_commencement_effect_keeps_its_date_and_both_sides():
    f = lp.parse_effects_feed(_feed(_effect(in_force=DATED)))
    assert f["total"] == 1 and f["total_pages"] == 1
    e = f["effects"][0]
    assert (e["affected"], e["affected_provisions"], e["affecting"], e["affecting_provisions"]) == (
        "asp/1901/1", "s. 2", "ssi/1901/3", "reg. 2")
    assert lp.is_commencement(e) and lp.effect_dates(e) == ["1901-10-08"]
    assert e["in_force"][0]["qualification"] == "wholly in force"


def test_a_prospective_effect_has_no_date_and_is_not_given_one():
    e = lp.parse_effects_feed(_feed(_effect(in_force=PROSPECTIVE, applied="false")))["effects"][0]
    assert lp.effect_dates(e) == [] and e["in_force"][0]["prospective"] is True
    assert e["applied"] is False and e["requires_applied"] is True


def test_an_error_page_is_not_read_as_no_effects():
    with pytest.raises(ValueError):
        lp.parse_effects_feed("<html><body>502 Bad Gateway</body></html>")
    with pytest.raises(ValueError):
        lp.parse_effects_feed("not xml at all")


def test_summary_counts_dates_self_commencement_and_outstanding_by_jurisdiction():
    effects = lp.parse_effects_feed(_feed(
        _effect(in_force=DATED),                                   # other, dated, Scottish
        _effect(aprov="s. 3", in_force=PROSPECTIVE, applied="false"),  # other, prospective, outstanding
        _effect(affecting="asp/1901/1", aprov="s. 9", in_force=DATED),  # self: excluded
        _effect(typ="words substituted", aprov="s. 4", applied="false", aclass="UnitedKingdomPublicGeneralAct",
                affected="ukpga/1901/7"),
        # not applied, but nothing to apply: not outstanding
        _effect(typ="modified", aprov="s. 6", applied="false", req="false"),
    ))["effects"]
    s = lp.summarise_effects(effects)
    assert s["commencements"] == 3 and s["commencements_self"] == 1
    assert s["commencements_other"] == 2 and s["commencements_other_dated"] == 1
    assert s["commencements_other_prospective"] == 1
    assert s["outstanding"] == 2 and s["commencements_other_outstanding"] == 1
    assert s["scottish"]["effects"] == 4 and s["other_jurisdictions"]["outstanding"] == 1


def test_paths_direct_and_through_the_lex_proxy():
    p = lp.feed_path("affecting", "http://www.legislation.gov.uk/id/ssi/1901/3", page=2, per_page=500)
    assert p == "/changes/affecting/ssi/1901/3/data.feed?results-count=500&page=2"
    assert lp.feed_path("affected", "ssi/1901/3", per_page=50).endswith("?results-count=50")
    assert lp.proxy_path(p) == (
        "/legislation/proxy/changes%2Faffecting%2Fssi%2F1901%2F3%2Fdata.feed"
        "%3Fresults-count%3D500%26page%3D2")
    with pytest.raises(ValueError):
        lp.feed_path("sideways", "ssi/1901/3")


# ---- descriptions -----------------------------------------------------------

def test_a_single_stated_date_is_read():
    d = lp.description_dates("These Regulations bring sections 1 and 2 of the Widget "
                             "(Scotland) Act 1901 into force on 8 October 1901.")
    assert d["class"] == "dated" and d["dates"] == ["1901-10-08"]
    assert d["first_date_at"] > 0 and len(d["matches"]) == 1


def test_a_date_list_takes_the_next_month_and_the_final_year():
    d = lp.description_dates("This Order appoints 20th June and 1st July 1901 for the coming "
                             "into force of certain provisions of the Widget Act 1901.")
    assert d["dates"] == ["1901-06-20", "1901-07-01"]
    d = lp.description_dates("Article 2 brings into force further provisions of the Widget "
                             "Services etc. (Scotland) Act 1901 on 1st and 22nd April 1902.")
    assert d["dates"] == ["1902-04-01", "1902-04-22"]  # "etc. (Scotland)" does not split


def test_a_missing_space_after_the_ordinal_is_read():
    d = lp.description_dates("This Order brings section 5 fully into force on 1stNovember 1902.")
    assert d["dates"] == ["1902-11-01"]


def test_the_appointed_day_is_undated_not_guessed():
    for text in ("These Regulations bring sections in Part 1 of the Widget Act 1901 into force "
                 "on the appointed day.",
                 "This Order appoints various days for the coming into force of the Widget Act 1901.",
                 "These Regulations are the third commencement regulations made under the Widget Act 1901."):
        d = lp.description_dates(text)
        assert d["class"] == "undated" and d["dates"] == [] and d["first_date_at"] is None


def test_an_earlier_commencement_in_the_past_tense_is_dropped():
    d = lp.description_dates(
        "This Order brings section 5 into force on 1st November 1902. Section 5 was commenced "
        "by the Widget Act 1901 (Commencement No. 2) Order 1901 (S.S.I. 1901/3) on 1st October "
        "1901 for limited purposes.")
    assert d["dates"] == ["1902-11-01"]
    assert [x["why"] for x in d["drops"]] == ["an earlier commencement (past tense)"]
    d = lp.description_dates("The Widget Act 1901 (Commencement No. 1) Order 1901 brought other "
                             "provisions into force on 1st July 1901.")
    assert d["class"] == "undated" and len(d["drops"]) == 1


def test_a_bracketed_earlier_date_does_not_take_the_main_date_with_it():
    d = lp.description_dates("These Regulations bring Part 2 (with the exception of section 5 "
                             "which came into force on 15 January 1901) into force on 14 January 1902.")
    assert d["dates"] == ["1902-01-14"]
    assert d["drops"][0]["span"] == "15 January 1901"


def test_passive_present_is_this_instruments_date():
    d = lp.description_dates("So far as not already in force, that Act is brought into force "
                             "at 5.00 a.m. on 1st September 1903 (article 3).")
    assert d["dates"] == ["1903-09-01"]


def test_negation_until_and_period_anchors():
    d = lp.description_dates("Schedules 1 and 2 will not come into force on 1st December 1901.")
    assert d["dates"] == [] and d["drops"][0]["why"] == "a negated commencement"
    d = lp.description_dates("The insertion of section 7 is not commenced until 1st April 1902.")
    assert d["dates"] == ["1902-04-01"]
    d = lp.description_dates("These Regulations bring Part 2 into force from 3rd July 1901 until "
                             "the end of the 3rd January 1902 in the areas listed.")
    assert d["dates"] == ["1901-07-03"] and d["drops"][0]["why"] == "an end date (until)"
    d = lp.description_dates("Section 9 is commenced except where it would cease to have effect "
                             "at the end of the period of six months beginning with 25th March 1902.")
    assert d["dates"] == [] and "anchor" in d["drops"][0]["why"]


def test_a_date_with_no_commencement_language_is_dropped_and_empty_is_empty():
    d = lp.description_dates("These Regulations give effect to the Widget Agreement made on "
                             "30th October 1901.")
    assert d["class"] == "no_statement" and d["drops"][0]["why"].startswith("no commencement")
    assert lp.description_dates("")["class"] == "empty"
    assert lp.description_dates(None)["class"] == "empty"


def test_first_date_at_is_the_offset_of_the_first_taken_date():
    text = "x" * 10 + ". This Order brings section 1 into force on 2nd May 1901."
    d = lp.description_dates(text)
    assert text[d["first_date_at"]:].startswith("2nd May 1901")


# ---- LEX rows against the feed ------------------------------------------------

def _row(ch_prov, af="ssi/1901/3", af_prov="reg. 2", scheme="http", eff="coming into force",
         ch="asp/1901/1"):
    return {"changed_legislation": ch, "changed_provision": ch_prov,
            "affecting_legislation": af, "affecting_provision": af_prov,
            "changed_url": f"{scheme}://www.legislation.gov.uk/id/{ch}", "type_of_effect": eff}


def test_compare_collapses_scheme_twins_drops_self_and_counts_dated_matches():
    lex = [_row("s. 2"), _row("s. 2", scheme="https"), _row("s. 3"),
           _row("s. 9", af="asp/1901/1", af_prov="s. 30"),        # self
           _row("s. 4", eff="words substituted")]                 # not a commencement
    effects = lp.parse_effects_feed(_feed(
        _effect(aprov="s. 2", in_force=DATED),
        _effect(aprov="s. 5", in_force=PROSPECTIVE),
    ))["effects"]
    c = lp.compare_commencements(lex, effects, "asp/1901/1")
    assert (c["lex"], c["lgu"], c["matched"], c["lex_only"], c["lgu_only"]) == (2, 2, 1, 1, 1)
    assert c["matched_dated"] == 1 and c["lgu_dated"] == 1


# ---- the client ---------------------------------------------------------------

def test_the_cap_counts_calls_already_in_the_log_and_refuses_the_next(tmp_path):
    log = tmp_path / "log.jsonl"
    log.write_text(json.dumps({"n": 1}) + "\n" + json.dumps({"n": 2}) + "\n", encoding="utf-8")
    calls = []
    c = lp.PacedClient(cap=3, log=log, min_gap=0, echo=False,
                       transport=lambda m, u, p: (calls.append(u) or (200, b"ok")))
    assert c.request("GET", lp.LGU + "/changes/affected/ssi/1901/3/data.feed")[0] == 200
    with pytest.raises(RuntimeError):
        c.request("GET", lp.LGU + "/x")
    assert len(calls) == 1
    assert len(log.read_text(encoding="utf-8").splitlines()) == 3


def test_only_the_two_agreed_hosts_are_called():
    c = lp.PacedClient(cap=5, min_gap=0, echo=False, transport=lambda m, u, p: (200, b""))
    with pytest.raises(ValueError):
        c.request("GET", "https://example.com/feed")


def test_fetch_feed_walks_every_page_and_raises_on_a_gateway_error():
    pages = {1: _feed(_effect(aprov="s. 1"), total=2, page=1, pages=2),
             2: _feed(_effect(aprov="s. 2"), total=2, page=2, pages=2)}

    def transport(m, u, p):
        return 200, pages[2 if "page%3D2" in u or "page=2" in u else 1].encode()

    c = lp.PacedClient(cap=5, min_gap=0, echo=False, transport=transport)
    f = lp.fetch_feed(c, "affected", "asp/1901/1", via="lex")
    assert f["total"] == 2 and f["pages"] == 2 and len(f["effects"]) == 2
    bad = lp.PacedClient(cap=5, min_gap=0, echo=False, transport=lambda m, u, p: (504, b"timeout"))
    with pytest.raises(RuntimeError):
        lp.fetch_feed(bad, "affected", "asp/1901/1")
