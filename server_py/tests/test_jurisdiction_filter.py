"""P1.1 — the jurisdiction filter (bucket B2).

`_matches_jurisdiction` used to discard almost every legislation search result
whenever a jurisdiction filter was set. It split `extent` on "+" and tested
single-letter tokens; the LEX API returns full territory names.

The part worth keeping in mind while reading these tests is **how it failed**,
because it shapes what they assert. The old code opened `if not extent: return
True`, so it did not fail closed. Rows with a *missing* extent passed and every
row with a *stated* extent was dropped — the filter returned a plausible,
non-empty, wrong result set. Measured over the P0.3 baseline: of 1,009 rows that
survived a jurisdiction filter, all 1,009 had `extent: []`, and a
`jurisdiction=scotland` search returned the Building Materials and Housing Act
1945. A filter that returns nothing looks broken; this one looked fine, which is
why 13 pre-pilot sessions ran with it and nobody reported it.

So two classes of test here, and the second is the one that would have caught it:

* `test_live_vocabulary_*` pins the real API vocabulary as a fixture, so a
  vocabulary change breaks the test rather than the product.
* `test_does_not_silently_*` asserts the property the old code violated — that
  rows whose territory is *stated* and matching are never dropped.
"""

import pytest

from src.agent.tools.lex import (
    _ID_PREFIX_JURISDICTION,
    _JURISDICTION_ACCEPTS,
    _extent_tokens,
    _matches_jurisdiction,
)

# ---------------------------------------------------------------------------
# The complete `extent` vocabulary the LEX API emitted across 17,560 result rows
# in the P0.3 baseline, with counts. This is the fixture the plan asks for: if
# the API starts emitting something else, these tests fail and the product does
# not silently start discarding results again.
# ---------------------------------------------------------------------------
LIVE_EXTENT_VOCABULARY = {
    ("",): 6668,
    ("United Kingdom",): 3289,
    ("Scotland",): 2765,
    (): 2662,
    ("England", "Wales"): 918,
    ("Northern Ireland",): 761,
    ("England", "Wales", "Scotland"): 484,
    ("England",): 10,
    ("England", "Wales", "Northern Ireland"): 2,
    ("Wales",): 1,
}

ALL_FILTERS = ["england_and_wales", "scotland", "northern_ireland", "wales", "uk_wide"]


# --- The regression itself --------------------------------------------------


@pytest.mark.parametrize("extent,jurisdiction", [
    (["Scotland"], "scotland"),
    (["England", "Wales", "Scotland"], "scotland"),
    (["United Kingdom"], "scotland"),
    (["England", "Wales"], "england_and_wales"),
    (["England"], "england_and_wales"),
    (["Wales"], "wales"),
    (["England", "Wales"], "wales"),
    (["Northern Ireland"], "northern_ireland"),
    (["England", "Wales", "Northern Ireland"], "northern_ireland"),
    (["United Kingdom"], "uk_wide"),
])
def test_live_vocabulary_matches_its_own_territory(extent, jurisdiction):
    """Every real extent value must satisfy a filter for a territory it names.

    This is the assertion the shipped code failed for all ten pairs.
    """
    assert _matches_jurisdiction(extent, jurisdiction) is True


@pytest.mark.parametrize("extent,jurisdiction", [
    (["Scotland"], "england_and_wales"),
    (["Scotland"], "northern_ireland"),
    (["Scotland"], "wales"),
    (["England", "Wales"], "scotland"),
    (["England", "Wales"], "northern_ireland"),
    (["England"], "wales"),
    (["Northern Ireland"], "scotland"),
    (["Wales"], "scotland"),
])
def test_a_stated_extent_excludes_other_territories(extent, jurisdiction):
    assert _matches_jurisdiction(extent, jurisdiction) is False


def test_does_not_silently_discard_the_whole_vocabulary():
    """The shape of the original defect, stated as a property.

    For every filter value, at least one live extent value must survive — and
    across the vocabulary as a whole, the rows that survive must not be only the
    unknown-extent ones. That second clause is the specific thing that made the
    bug invisible in the pre-pilot.
    """
    for jurisdiction in ALL_FILTERS:
        survivors = [
            extent for extent in LIVE_EXTENT_VOCABULARY
            if _matches_jurisdiction(list(extent), jurisdiction)
        ]
        assert survivors, f"{jurisdiction} discards the entire live vocabulary"
        stated = [e for e in survivors if any(t.strip() for t in e)]
        assert stated, (
            f"{jurisdiction} admits only unknown-extent rows — this is the "
            "original defect, which returned a plausible but wrong result set "
            "rather than an empty one"
        )


def test_the_old_single_letter_form_still_works():
    """If the API ever reverts to "E+W+S+NI", the filter must not break again."""
    assert _matches_jurisdiction(["E+W+S+NI"], "scotland") is True
    assert _matches_jurisdiction(["E+W"], "scotland") is False
    assert _matches_jurisdiction(["S"], "scotland") is True


# --- Unknown extent: the half that needed a product decision ----------------


@pytest.mark.parametrize("extent", [[], [""], ["", ""], None])
def test_unknown_extent_is_included(extent):
    """53% of live rows carry `['']` or `[]`, including 2,009 Scottish SIs.

    Excluding unknowns would drop 40% of Scottish material — swapping one trap
    for another — so they are admitted.
    """
    assert _matches_jurisdiction(extent, "scotland") is True


@pytest.mark.parametrize("legislation_id,jurisdiction,expected", [
    ("ssi/2022/356", "scotland", True),
    ("asp/2014/18", "scotland", True),
    ("uksi/1980/1647", "scotland", True),     # UK-level: could apply anywhere
    ("ukpga/1998/46", "scotland", True),
    ("nisr/2019/1", "scotland", False),       # Northern Irish, whatever extent says
    ("wsi/2020/1", "scotland", False),
    ("nisro/1972/1", "scotland", False),
    ("wsi/2020/1", "england_and_wales", True),   # Welsh SI is in scope for E&W
    ("ssi/2022/356", "england_and_wales", False),
    ("nisr/2019/1", "northern_ireland", True),
])
def test_unknown_extent_is_rejected_by_an_other_jurisdiction_id(
    legislation_id, jurisdiction, expected
):
    """The id prefix is the tie-break that lets unknowns in without letting
    Northern Irish and Welsh instruments in alongside them."""
    assert _matches_jurisdiction([], jurisdiction, legislation_id) is expected


def test_a_stated_extent_beats_the_id_prefix():
    """An `ssi/` instrument whose extent says England & Wales is not Scottish.

    The id is a fallback for unknown extents only; it must never override a
    value the API actually stated.
    """
    assert _matches_jurisdiction(["England", "Wales"], "scotland", "ssi/2022/1") is False
    assert _matches_jurisdiction(["Scotland"], "scotland", "nisr/2019/1") is True


def test_uk_wide_does_not_admit_unknown_extents():
    """"UK-wide only" is an explicit narrowing: a row that does not say it is
    UK-wide does not satisfy it."""
    assert _matches_jurisdiction([], "uk_wide") is False
    assert _matches_jurisdiction([""], "uk_wide", "uksi/2020/1") is False
    assert _matches_jurisdiction(["United Kingdom"], "uk_wide") is True
    assert _matches_jurisdiction(["England", "Wales", "Scotland"], "uk_wide") is False


def test_uk_wide_is_reachable_at_all():
    """The old implementation required tokens >= {E,W,S,NI}, which no live value
    ever produced, so "UK-wide only" returned nothing under every condition."""
    assert any(
        _matches_jurisdiction(list(extent), "uk_wide")
        for extent in LIVE_EXTENT_VOCABULARY
    )


# --- Decisions this row took, pinned so they are not reverted by accident ----


def test_uk_wide_instruments_are_in_scope_for_a_devolved_filter():
    """Decided 2026-09-14: the control means "applies in", not "made for".

    CambeulW's session 6406 needed assimilated EU regulations (`eur/…`, which
    carry `['United Kingdom']`) under a Scotland filter. Reverting this would
    reintroduce a false negative, which Invariant 1 treats as the worse error.
    """
    for jurisdiction in ("scotland", "england_and_wales", "northern_ireland", "wales"):
        assert _matches_jurisdiction(["United Kingdom"], jurisdiction) is True


def test_an_unrecognised_filter_value_never_narrows():
    """Fail open, not closed: an unknown filter value must not discard results."""
    assert _matches_jurisdiction(["Scotland"], "atlantis") is True
    assert _matches_jurisdiction([], "") is True


# --- Internals --------------------------------------------------------------


def test_extent_tokens_normalisation():
    assert _extent_tokens(["Scotland"]) == {"S"}
    assert _extent_tokens(["England", "Wales"]) == {"E", "W"}
    assert _extent_tokens(["United Kingdom"]) == {"UK"}
    assert _extent_tokens([""]) == set()
    assert _extent_tokens([]) == set()
    assert _extent_tokens(["E+W+S"]) == {"E", "W", "S"}
    assert _extent_tokens(["  Northern Ireland  "]) == {"NI"}


def test_every_filter_value_the_frontend_offers_is_handled():
    """`JURISDICTION_OPTIONS` in client/src/constants/research.js. A value the
    UI can send but the backend does not know would silently stop filtering."""
    assert set(_JURISDICTION_ACCEPTS) == set(ALL_FILTERS)


def test_id_prefix_map_only_names_devolved_jurisdictions():
    """A UK-level prefix in this map would wrongly reject unknown-extent rows."""
    assert set(_ID_PREFIX_JURISDICTION.values()) <= {
        "scotland", "northern_ireland", "wales",
    }
    for uk_level in ("ukpga", "uksi", "ukla", "eur", "ukdsi"):
        assert uk_level not in _ID_PREFIX_JURISDICTION
