"""P3.56: one Sources-rail entry for a provision whose two URLs differ only in form.

Pure function, synthetic rails. The shapes are the stored pairs: a section
search's `http://www.legislation.gov.uk/<id>` entry ("Act 1998, s.126") and
the same provision's `https://www.legislation.gov.uk/id/<id>` entry
("<id>, s.126"), both under one heading.
"""
from src.utils.rail_dedupe import collapse_scheme_duplicates


def _search_hit(path, cite, sub, url_form="http://www.legislation.gov.uk/"):
    return {"kind": "Act", "title": "Widget Act 1901", "url": url_form + path, "cite": cite,
            "sub": sub, "excerpt": "text", "extent": ["Scotland"], "year": 1901}


def _id_entry(path, cite, sub, excerpt="text"):
    s = {"kind": "Statute", "title": "Widget Act 1901",
         "url": "https://www.legislation.gov.uk/id/" + path, "cite": cite, "sub": sub}
    if excerpt:
        s["excerpt"] = excerpt
    return s


def test_one_provision_under_two_url_forms_is_one_entry():
    a = _search_hit("ukpga/1901/3", "Widget Act 1901, s.126", "Interpretation.")
    other = _id_entry("ukpga/1902/1", "ukpga/1902/1, s.1", "Citation")
    b = _id_entry("ukpga/1901/3", "ukpga/1901/3, s.126", "Interpretation.")
    out, n = collapse_scheme_duplicates([a, other, b])
    assert n == 1 and len(out) == 2
    kept = out[0]                                    # the first entry's place
    assert kept["kind"] == "Act" and kept["cite"] == "Widget Act 1901, s.126"   # the richer
    assert kept["url"] == "https://www.legislation.gov.uk/id/ukpga/1901/3"     # the https URL
    assert out[1] is other
    assert a["url"].startswith("http://")           # the inputs are not mutated


def test_the_richer_entry_is_kept_whichever_comes_first():
    a = _id_entry("asp/1901/3", "asp/1901/3, s.36", "Confidentiality", excerpt="")
    b = _search_hit("asp/1901/3", "Widget Act 1901, s.36", "Confidentiality",
                    url_form="http://www.legislation.gov.uk/id/")
    out, n = collapse_scheme_duplicates([a, b])
    assert n == 1 and out[0]["cite"] == "Widget Act 1901, s.36"
    assert out[0]["excerpt"] == "text"
    assert out[0]["url"] == "https://www.legislation.gov.uk/id/asp/1901/3"


def test_a_field_only_the_dropped_entry_has_is_kept():
    a = _search_hit("ukpga/1901/3", "Widget Act 1901, s.2", "Interpretation")
    a.pop("excerpt")
    b = _id_entry("ukpga/1901/3", "ukpga/1901/3", "Interpretation", excerpt="the text")
    out, n = collapse_scheme_duplicates([a, b])
    assert n == 1 and out[0]["excerpt"] == "the text"
    assert out[0]["cite"] == "Widget Act 1901, s.2"


def test_a_cite_without_a_provision_number_matches_one_with_it():
    a = _search_hit("ukpga/1996/18", "Employment Rights Act 1996, s.202", "Sunday working")
    b = _id_entry("ukpga/1996/18", "ukpga/1996/18", "Sunday working")
    assert collapse_scheme_duplicates([a, b])[1] == 1


def test_distinct_provisions_of_one_instrument_stay_apart():
    a = _search_hit("ukpga/1901/3", "Widget Act 1901, s.8", "Modifications of enactments")
    b = _id_entry("ukpga/1901/3", "ukpga/1901/3, s.126", "Interpretation.")
    c = _id_entry("ukpga/1901/3", "ukpga/1901/3, s.51", "The Civil Service.")
    rail = [a, b, c]
    out, n = collapse_scheme_duplicates(rail)
    assert n == 0 and out is rail


def test_one_heading_on_two_numbered_provisions_stays_apart():
    a = _search_hit("ssi/1901/3", "Widget Order 1901, s.2", "Interpretation")
    b = _id_entry("ssi/1901/3", "ssi/1901/3, s.3", "Interpretation")
    rail = [a, b]
    assert collapse_scheme_duplicates(rail) == (rail, 0)


def test_a_change_record_entry_is_not_a_provision_entry():
    a = _id_entry("uksi/1901/3", "uksi/1901/3", "recorded as revoked for provisions of uksi/1950/1",
                  excerpt="")
    b = _id_entry("uksi/1901/3", "uksi/1901/3, s.3", "Use Classes")
    rail = [a, b]
    assert collapse_scheme_duplicates(rail) == (rail, 0)


def test_a_case_or_an_entry_with_no_url_is_untouched():
    case = {"kind": "Case", "title": "Widget Co v Example Ltd", "cite": "[1901] UKSC 1",
            "url": "https://caselaw.nationalarchives.gov.uk/uksc/1901/1"}
    case_http = dict(case, url="http://caselaw.nationalarchives.gov.uk/uksc/1901/1")
    bare = {"kind": "Statute", "title": "ukpga/1901/3", "url": "", "cite": "ukpga/1901/3"}
    rail = [case, case_http, bare, dict(bare)]
    assert collapse_scheme_duplicates(rail) == (rail, 0)


def test_no_duplicate_returns_the_same_list():
    rail = [_search_hit("ukpga/1901/3", "Widget Act 1901, s.1", "Citation"),
            _id_entry("ukpga/1902/3", "ukpga/1902/3, s.1", "Citation")]
    out, n = collapse_scheme_duplicates(rail)
    assert out is rail and n == 0
    assert collapse_scheme_duplicates([]) == ([], 0)


def test_never_raises():
    rail = [None, 3, {"url": None, "sub": None}, {"url": 7}]
    assert collapse_scheme_duplicates(rail) == (rail, 0)


def test_it_is_deterministic():
    rail = [_search_hit("ukpga/1901/3", "Widget Act 1901, s.126", "Interpretation."),
            _id_entry("ukpga/1901/3", "ukpga/1901/3, s.126", "Interpretation.")]
    assert collapse_scheme_duplicates(rail) == collapse_scheme_duplicates(list(rail))
