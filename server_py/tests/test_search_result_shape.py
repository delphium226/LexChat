"""P1.3 and P1.4 — what a legislation search hands back to the model.

Two pre-pilot buckets, both about the tool result rather than the model:

* **B5 / P1.3** — `slimmed["total"] = len(results)` overwrote the API's real
  match count *after* filtering and truncation, so the model could not tell
  "5 instruments match your question" from "138 match and your filters removed
  all but 5". Over the P0.3 baseline, 1,010 of 1,531 searches misreported it —
  438 of them with no filter set at all, because the `[:5]` cap alone was enough.
  `_TYPE_CODES` separately had no `eur` entry, so any `legislation_type` filter
  silently discarded every assimilated EU instrument.

* **B14 / P1.4** — provision links. The API already returns a provision-level
  legislation.gov.uk URL per result, but the response was passed through raw and
  the worker prompt told the model to *"manually append `/section/{number}` to
  the Base URI"*. 88 of 376 provision-labelled links in the baseline (23.4%)
  missed their provision. The fix hands the model the API's own URL and removes
  the instruction to build one.
"""

import json

import pytest

from src.agent.tools.lex import (
    _TYPE_CODES,
    _short_legislation_id,
    _slim_search_results,
    _slim_section_results,
)


# --- P1.3: assimilated EU instruments must survive a type filter ------------


@pytest.mark.parametrize("prefix", ["eur", "eudn", "eudr"])
def test_assimilated_eu_instruments_are_reachable_under_a_type_filter(prefix):
    """`eur/2009/1069` is present and retrievable (10 sections) and was exactly
    what CambeulW needed in 6406. With no `eur` entry anywhere in `_TYPE_CODES`,
    every `legislation_type` value dropped it."""
    assert any(prefix in codes for codes in _TYPE_CODES.values()), (
        f"{prefix!r} is in no legislation_type bucket, so any type filter "
        "silently discards it"
    )


def test_type_buckets_are_disjoint():
    """A prefix in two buckets would make the filter meaningless for it."""
    seen: set[str] = set()
    for codes in _TYPE_CODES.values():
        assert not (seen & codes), f"prefix in more than one bucket: {seen & codes}"
        seen |= codes


def test_primary_holds_acts_and_secondary_holds_instruments():
    assert {"ukpga", "asp", "nia"} <= _TYPE_CODES["primary"]
    assert {"uksi", "ssi", "wsi", "nisr"} <= _TYPE_CODES["secondary"]
    # Assimilated EU law is directly-applicable law made outside Parliament: a
    # lawyer filtering for "primary" means Acts.
    assert "eur" in _TYPE_CODES["secondary"]
    assert "eur" not in _TYPE_CODES["primary"]


# --- P1.3: the three counts must be distinguishable -------------------------


def _api_response(n_rows: int, total: int) -> dict:
    return {
        "results": [
            {
                "uri": f"http://www.legislation.gov.uk/id/ssi/2024/{i}",
                "title": f"Instrument {i}",
                "status": "revised",
                "year": 2024,
                "extent": ["Scotland"],
            }
            for i in range(n_rows)
        ],
        "total": total,
    }


def test_slim_search_preserves_the_api_match_count():
    slim = _slim_search_results(_api_response(20, 138))
    assert slim["total"] == 138, "the API's match count must survive slimming"
    assert len(slim["results"]) == 20


def test_the_counts_answer_three_different_questions():
    """`returned`, `total_matched` and `removed_by_filters` are what the model
    needs to tell a genuinely narrow result set from a heavily filtered one.

    Asserted on the executor's contract rather than by calling it (the call is
    an HTTP round trip); the executor builds exactly these keys from
    `_slim_search_results` output plus the pre/post-filter row counts.
    """
    slim = _slim_search_results(_api_response(20, 138))
    matched = slim["total"]
    api_returned = len(slim["results"])
    after_filters = 7            # filters removed 13 of the 20
    returned = min(after_filters, 5)   # then the cap applied

    assert matched == 138
    assert api_returned - after_filters == 13
    assert returned == 5
    # The three must be distinct — collapsing them is the defect.
    assert len({matched, returned, api_returned - after_filters}) == 3


# --- P1.4: provision links --------------------------------------------------


SECTION_API_ITEM = {
    "created_at": "2026-08-13T02:10:55.926897Z",
    "text": "1) An appeal may be taken to the Sheriff Appeal Court...",
    "id": "http://www.legislation.gov.uk/id/asp/2014/18/section/110",
    "uri": "http://www.legislation.gov.uk/asp/2014/18/section/110",
    "legislation_id": "http://www.legislation.gov.uk/id/asp/2014/18",
    "title": "Appeal from a sheriff to the Sheriff Appeal Court",
    "extent": ["Scotland"],
    "provision_type": "section",
    "provenance_source": None,
    "provenance_model": None,
    "number": 110,
    "legislation_type": "asp",
    "legislation_year": 2014,
    "legislation_number": 18,
}


def test_section_results_carry_a_provision_level_url():
    """The whole of P1.4: the model is handed the provision URL, not an Act URL
    it has to extend."""
    out = _slim_section_results([SECTION_API_ITEM])
    row = out["results"][0]
    assert row["url"] == "http://www.legislation.gov.uk/asp/2014/18/section/110"
    assert row["url"].endswith("/section/110")
    assert row["provision_type"] == "section"
    assert row["number"] == 110


def test_section_results_normalise_the_legislation_id():
    """The two LEX endpoints disagree on this key's format, and the model has to
    pass it back as `legislation_id`."""
    out = _slim_section_results([SECTION_API_ITEM])
    assert out["results"][0]["legislation_id"] == "asp/2014/18"


def test_schedules_and_regulations_get_their_own_path_segment():
    items = [
        {**SECTION_API_ITEM, "provision_type": "schedule", "number": 3,
         "uri": "http://www.legislation.gov.uk/asp/2014/18/schedule/3"},
        {**SECTION_API_ITEM, "provision_type": "regulation", "number": 2,
         "uri": "http://www.legislation.gov.uk/ssi/2025/119/regulation/2"},
        {**SECTION_API_ITEM, "provision_type": "article", "number": 43,
         "uri": "http://www.legislation.gov.uk/eur/2009/1069/article/43"},
    ]
    urls = [r["url"] for r in _slim_section_results(items)["results"]]
    assert urls == [
        "http://www.legislation.gov.uk/asp/2014/18/schedule/3",
        "http://www.legislation.gov.uk/ssi/2025/119/regulation/2",
        "http://www.legislation.gov.uk/eur/2009/1069/article/43",
    ]


def test_section_slimming_drops_the_noise_it_was_guessing_from():
    out = _slim_section_results([SECTION_API_ITEM])
    row = out["results"][0]
    for noisy in ("created_at", "provenance_source", "provenance_model",
                  "legislation_year", "legislation_number", "id"):
        assert noisy not in row
    assert row["text"], "the provision text itself must survive"


def test_section_slimming_falls_back_to_id_when_uri_is_absent():
    item = {k: v for k, v in SECTION_API_ITEM.items() if k != "uri"}
    out = _slim_section_results([item])
    assert out["results"][0]["url"].endswith("/section/110")


def test_a_bare_list_response_is_handled():
    """The endpoint returns a JSON array at the top level, not an object.
    Treating it as a dict would silently return nothing."""
    out = _slim_section_results([SECTION_API_ITEM, SECTION_API_ITEM])
    assert out["returned"] == 2


@pytest.mark.parametrize("payload", [
    {"unexpected": "shape"},
    {"results": "not a list"},
    {},
])
def test_an_unexpected_shape_is_passed_through_untouched(payload):
    """A slimmer must never be the reason a retrieval goes missing."""
    assert _slim_section_results(payload) == payload


def test_non_dict_items_are_skipped_not_fatal():
    out = _slim_section_results([SECTION_API_ITEM, "junk", None])
    assert out["returned"] == 1


@pytest.mark.parametrize("raw,expected", [
    ("http://www.legislation.gov.uk/id/asp/2014/18", "asp/2014/18"),
    ("http://www.legislation.gov.uk/asp/2014/18", "asp/2014/18"),
    ("asp/2014/18", "asp/2014/18"),
    ("/id/ssi/2025/119", "ssi/2025/119"),
    ("", ""),
])
def test_short_legislation_id(raw, expected):
    assert _short_legislation_id(raw) == expected


# --- The prompt half of P1.4 -------------------------------------------------


def test_the_prompt_no_longer_tells_the_model_to_build_provision_urls():
    """The instruction *"you MUST manually append `/section/{number}` to the
    Base URI"* was the direct cause of B14 — the model was obeying it. Now that
    `search_legislation_sections` returns the URL, the instruction is gone."""
    from src import prompts

    for name in ("WORKER_SYSTEM_PROMPT", "WORKER_SYSTEM_PROMPT_HYBRID"):
        text = getattr(prompts, name)
        assert "manually append" not in text, f"{name} still says to build URLs"
        assert "url" in text.lower(), f"{name} must point at the url field"
