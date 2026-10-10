"""FIX_PLAN P3.33: whether each instrument in the made-under record is recorded as revoked.

Every case below is a shape found in Session 46's probe crawls (`evidence/seam/s46/`): the
Welsh/NI filing, the schedule label, the words-only temporary omission, the date in the label,
the revocation dated after the day it was read, the effect listed twice.
"""
from __future__ import annotations

import pytest

from src.utils import revocation_record as R


def feed(effects, total=None, generated="2026-10-10T08:52:02.623636+01:00"):
    """A Changes to Legislation Atom page with the given effects."""
    rows = []
    for e in effects:
        inf = "".join(
            f'<ukm:InForce Date="{d}" Qualification="{q}"/>' if d else f'<ukm:InForce Qualification="{q}"/>'
            for d, q in e.get("in_force", []))
        mod = f' Modified="{e["modified"]}"' if e.get("modified") else ""
        rows.append(
            f'<entry><id>x</id><content type="text/xml">'
            f'<ukm:Effect EffectId="{e["eid"]}" Type="{e["type"]}"{mod}'
            f' AffectedURI="http://www.legislation.gov.uk/id/{e["affected"]}"'
            f' AffectedProvisions="{e.get("provisions", "")}"'
            f' AffectingURI="http://www.legislation.gov.uk/id/{e["by"]}">'
            f'<ukm:InForceDates>{inf}</ukm:InForceDates></ukm:Effect></content>'
            f'<updated>{e.get("updated", "2026-01-01T00:00:00Z")}</updated></entry>')
    return (
        '<?xml version="1.0" encoding="utf-8"?><feed xmlns="http://www.w3.org/2005/Atom" '
        'xmlns:leg="http://www.legislation.gov.uk/namespaces/legislation" '
        'xmlns:ukm="http://www.legislation.gov.uk/namespaces/metadata" '
        'xmlns:openSearch="http://a9.com/-/spec/opensearch/1.1/">'
        f'<updated>{generated}</updated><leg:page>1</leg:page><leg:totalPages>1</leg:totalPages>'
        f'<openSearch:totalResults>{total if total is not None else len(effects)}</openSearch:totalResults>'
        + "".join(rows) + "</feed>")


def eff(eid, typ, affected, provisions, by, in_force=(), **kw):
    return dict(eid=eid, type=typ, affected=affected, provisions=provisions, by=by,
                in_force=list(in_force), **kw)


def parsed(*effects):
    return R.parse_feed(feed(list(effects)))["effects"]


# --- the feed ---------------------------------------------------------------

def test_parse_feed_reads_totals_dates_and_ids():
    p = R.parse_feed(feed([eff("k1", "revoked", "ssi/2022/217", "Regulations", "ssi/2024/311",
                               [("2025-03-21", "wholly in force")], modified="2025-03-01T10:00:00Z")]))
    assert p["total"] == 1 and p["total_pages"] == 1
    assert R.timestamp(p["generated"]).isoformat() == "2026-10-10T07:52:02.623636+00:00"
    e = p["effects"][0]
    assert (e["eid"], e["affected"], e["by"], e["provisions"]) == (
        "k1", "ssi/2022/217", "ssi/2024/311", "Regulations")
    assert e["in_force"] == [{"date": "2025-03-21", "qualification": "wholly in force"}]


@pytest.mark.parametrize("text", ["", "<html>error</html>",
                                  '<!DOCTYPE x [<!ENTITY a "b">]><feed/>'])
def test_parse_feed_refuses_what_is_not_a_feed(text):
    with pytest.raises(ValueError):
        R.parse_feed(text)


def test_an_effect_listed_twice_is_read_once_the_later_version():
    old = eff("k1", "revoked", "ssi/2005/329", "Regulations", "ssi/2010/1", updated="2023-11-02T12:10:01Z")
    new = eff("k1", "revoked", "ssi/2005/329", "Regulations", "ssi/2010/1",
              [("2010-04-01", "wholly in force")], modified="2025-11-04T08:29:43Z")
    merged = R.merge_effects({}, parsed(new, old))
    assert list(merged) == ["k1"] and merged["k1"]["in_force"][0]["date"] == "2010-04-01"
    merged = R.merge_effects({}, parsed(old, new))
    assert merged["k1"]["in_force"][0]["date"] == "2010-04-01"


# --- which instrument --------------------------------------------------------

def test_welsh_and_ni_instruments_are_matched_on_their_uk_si_number():
    assert R.instrument_key("wsi/2005/1310") == "uksi/2005/1310"
    assert R.instrument_key("nisi/2005/861") == "uksi/2005/861"
    assert R.instrument_key("ssi/2005/861") == "ssi/2005/861"
    assert R.instrument_key("nisr/2005/861") == "nisr/2005/861"  # its own series
    effects = R.merge_effects({}, parsed(
        eff("k1", "revoked", "wsi/2005/1310", "Regulations", "wsi/2018/806", [("2018-07-01", "wholly in force")])))
    assert R.flags_from_effects(effects, {"uksi/2005/1310"})["uksi/2005/1310"]["state"] == R.WHOLLY


def test_scope_of_names_the_feed():
    assert R.scope_of("ssi/2022/217") == "ssi"
    assert R.scope_of("uksi/2005/1310") == "uksi/2005"


# --- the flag ----------------------------------------------------------------

def test_a_removal_of_the_instrument_is_whole():
    f = R.flag_for("ssi/2022/217", parsed(
        eff("k1", "revoked", "ssi/2022/217", "Regulations", "ssi/2024/311", [("2025-03-21", "wholly in force")]),
        eff("k2", "omitted", "ssi/2022/217", "reg. 10(f)", "ssi/2023/346", [("2023-11-20", "wholly in force")])))
    assert f["state"] == R.WHOLLY
    assert f["whole"] == [{"type": "revoked", "by": "ssi/2024/311", "date_source": "feed",
                           "dates": [{"date": "2025-03-21", "qualification": "wholly in force"}]}]
    assert f["partial"]["count"] == 1


@pytest.mark.parametrize("label", ["Sch.", "sch.", "Schedule", "Schs.", "Sch. Notes"])
def test_a_schedule_label_is_not_the_instrument(label):
    f = R.flag_for("ssi/2008/82", parsed(eff("k1", "revoked", "ssi/2008/82", label, "ssi/2014/225")))
    assert f["state"] == R.PARTLY


@pytest.mark.parametrize("label", ["Regulations", "Order", "Rules", "Instrument", "Act of Sederunt",
                                   "Scheme", "Act", "residue", "", "Regualtions", "regulations"])
def test_instrument_nouns_and_the_older_blank_label_are_whole(label):
    f = R.flag_for("ssi/2001/281", parsed(eff("k1", "rev", "ssi/2001/281", label, "ssi/2002/182")))
    assert f["state"] == R.WHOLLY


@pytest.mark.parametrize("typ", ["words omitted", "word revoked", "entry repealed", "words omitted (temp.)"])
def test_a_words_only_removal_is_not_a_revocation(typ):
    assert R.flag_for("ssi/2015/126", parsed(eff("k1", typ, "ssi/2015/126", "reg. 5(3)", "ssi/2020/215"))) is None


@pytest.mark.parametrize("typ", ["rev (prosp)", "cease to have effect (temp.)", "revoked (S)",
                                 "revoked in part for specified purposes"])
def test_a_qualified_removal_is_kept_apart_with_the_feeds_words(typ):
    f = R.flag_for("uksi/2005/1102", parsed(eff("k1", typ, "uksi/2005/1102", "", "uksi/2006/2915")))
    assert f["state"] == R.QUALIFIED_ONLY and f["qualified"][0]["type"] == typ


def test_no_removal_no_flag():
    assert R.flag_for("ssi/2018/275", parsed(
        eff("k1", "coming into force", "ssi/2018/275", "reg. 1", "ssi/2018/275"),
        eff("k2", "words substituted", "ssi/2018/275", "reg. 2", "ssi/2019/1"))) is None


def test_a_date_in_the_label_is_read_when_the_feed_has_none():
    f = R.flag_for("uksi/2005/2016", parsed(eff("k1", "rev (1.1.2007)", "uksi/2005/2016", "", "uksi/2006/1942")))
    assert f["whole"][0]["dates"] == [{"date": "2007-01-01", "qualification": ""}]
    assert f["whole"][0]["date_source"] == "label"


def test_an_instruments_own_sunset_is_marked_self():
    f = R.flag_for("ssi/2026/282", parsed(eff("k1", "ceases to have effect", "ssi/2026/282", "Order",
                                              "ssi/2026/282", [("2026-10-23", "wholly in force")])))
    assert f["whole"][0]["self"] is True


# --- read on a given day -----------------------------------------------------

def _whole(date):
    return R.flag_for("ssi/2012/190", parsed(eff("k1", "revoked", "ssi/2012/190", "Regulations",
                                                 "ssi/2025/417", [(date, "wholly in force")] if date else [])))


def test_a_revocation_dated_after_today_is_not_yet_in_effect():
    f = _whole("2026-10-31")
    assert R.category(f, "2026-10-10") == "revoked_later"
    assert R.category(f, "2026-10-31") == "revoked"
    line = R.describe(f, "2026-10-10", "2026-10-10")
    assert "a date still to come" in line and "with effect from 2026-10-31" in line


def test_categories():
    assert R.category(_whole("2025-03-21"), "2026-10-10") == "revoked"
    assert R.category(_whole(None), "2026-10-10") == "revoked_undated"
    assert R.category(None) == "none"
    t = R.tally([(_whole("2025-03-21"), "2026-10-10"), (None, "2026-10-10"), (None, None)], "2026-10-10")
    assert (t["revoked"], t["none"], t["unchecked"]) == (1, 1, 1)


def test_describe_says_only_what_the_record_holds():
    assert R.describe(None, None) == "not checked"
    assert R.describe(None, "2026-10-10") == "no revocation recorded"
    line = R.describe(_whole("2025-03-21"), "2026-10-10", "2026-10-10")
    assert line == "recorded as revoked in whole by ssi/2025/417, with effect from 2025-03-21"
    undated = R.describe(_whole(None), "2026-10-10", "2026-10-10")
    assert undated == "recorded as revoked in whole by ssi/2025/417, no date recorded"


def test_describe_quotes_the_records_words_where_they_say_more():
    f = R.flag_for("ssi/2001/433", parsed(eff("k1", "rev (saving)", "ssi/2001/433", "", "ssi/2008/154")))
    assert R.describe(f, "2026-10-10", "2026-10-10") == (
        'recorded as revoked in whole by ssi/2008/154, no date recorded '
        '(the record\'s words: "rev (saving)")')
    own = R.flag_for("ssi/2026/272", parsed(eff("k1", "ceases to have effect", "ssi/2026/272", "Order",
                                                "ssi/2026/272", [("2027-01-01", "wholly in force")])))
    assert R.describe(own, "2026-10-10", "2026-10-10") == (
        "recorded as ceasing to have effect in whole by its own provisions, "
        "with effect from 2027-01-01, a date still to come")


def test_describe_a_partial_and_a_qualified_flag():
    f = R.flag_for("ssi/2021/174", parsed(
        eff("k1", "revoked", "ssi/2021/174", "reg. 40", "ssi/2025/336"),
        eff("k2", "omitted", "ssi/2021/174", "reg. 24(2)(a)(iii)", "ssi/2022/41"),
        eff("k3", "omitted", "ssi/2021/174", "sch. para. 11(1)(d)(i)", "ssi/2021/416")))
    assert R.describe(f, "2026-10-10", "2026-10-10") == (
        "recorded as revoked in part: 3 provisions revoked or omitted, by ssi/2021/416, "
        "ssi/2022/41 and 1 other")
    q = R.flag_for("uksi/2005/1102", parsed(eff("k1", "rev (prosp)", "uksi/2005/1102", "", "uksi/2006/2915")))
    assert R.describe(q, "2026-10-10", "2026-10-10") == (
        'recorded with a qualified removal only: "rev (prosp)" by uksi/2006/2915, no date recorded')


def test_the_instrument_that_made_most_of_the_removals_is_named_first():
    f = R.flag_for("ssi/2021/174", parsed(
        eff("k1", "revoked", "ssi/2021/174", "reg. 40", "ssi/2025/336"),
        eff("k2", "revoked", "ssi/2021/174", "reg. 41", "ssi/2025/336"),
        eff("k3", "omitted", "ssi/2021/174", "reg. 24(2)", "ssi/2022/41"),
        eff("k4", "omitted", "ssi/2021/174", "sch. para. 11", "ssi/2021/416")))
    assert f["partial"]["by"] == ["ssi/2025/336", "ssi/2021/416", "ssi/2022/41"]


def test_a_removal_in_part_of_the_instrument_is_partial():
    f = R.flag_for("ssi/2004/116", parsed(eff("k1", "revoked in part", "ssi/2004/116", "Regulations",
                                              "ssi/2018/67")))
    assert f["state"] == R.PARTLY


def test_a_qualified_date_is_quoted_as_the_records_words():
    f = R.flag_for("uksi/2020/884", parsed(eff("k1", "revoked", "wsi/2020/884", "Regulations",
                                               "wsi/2020/1149", [("2020-10-23", "Other")])))
    assert R.describe(f, "2026-10-10", "2026-10-10") == (
        'recorded as revoked in whole by wsi/2020/1149, with effect from 2020-10-23 '
        '(date qualified in the record as "Other")')
