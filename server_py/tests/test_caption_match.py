"""Unit tests for the SP TV caption matcher.

Runs against a saved fixture (a real caption transcript + offset index built from
the 2 June 2026 "Phone-free Classrooms" plenary, meeting_id 20164) so it needs no
network or DB. The minister's statement (speech index 1) resolves to
clip_start=15:02:46 — verified against the Official Report's own embedded 15:02
timestamp. (The original PoC reported 14:56:52; that was ~6 min early because it
counted caption-stream MPEGTS transitions as the segment ordinal, undercounting
the 171 caption-less segments in the sitting. The true segment ordinal — this
build's `seg_index` over the full HLS playlist — is correct.)
"""
import gzip
import json
import os

import pytest

from src.services.caption_match import build_deeplink, match_speech

_FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sptv_captions_20164.json.gz")


@pytest.fixture(scope="module")
def caption_fixture():
    with gzip.open(_FIXTURE, "rt", encoding="utf-8") as f:
        return json.load(f)


def test_minister_resolves_to_official_report_timestamp(caption_fixture):
    """Speech index 1 (the minister) resolves to 15:02:46 (OR marker: 15:02)."""
    row = caption_fixture["caption_row"]
    speeches = caption_fixture["speeches"]

    dl = build_deeplink(row, speeches, cited_index=1)
    assert dl is not None
    assert dl["clip_start"] == "15:02:46"
    assert dl["confidence"] >= 0.9
    assert dl["url"].endswith("?clip_start=15:02:46&clip_end=15:03:46")
    assert "meeting-of-the-parliament-june-2-2026" in dl["url"]


def test_matches_are_monotonic(caption_fixture):
    """Later speeches in the item resolve to later (or equal) wall-clock times."""
    row = caption_fixture["caption_row"]
    speeches = caption_fixture["speeches"]

    prev = None
    for idx in (1, 3, 5):
        dl = build_deeplink(row, speeches, cited_index=idx)
        assert dl is not None, f"no deep link for speech {idx}"
        if prev is not None:
            assert dl["clip_start"] >= prev, f"speech {idx} not monotonic ({dl['clip_start']} < {prev})"
        prev = dl["clip_start"]


def test_no_captions_returns_none(caption_fixture):
    """A row without captions yields no link (fail-soft)."""
    speeches = caption_fixture["speeches"]
    row = {"caption_ok": False, "transcript": "", "offset_index": None}
    assert build_deeplink(row, speeches, 1) is None
    assert match_speech(row, speeches[1]["text"]) is None


def test_out_of_range_index_returns_none(caption_fixture):
    row = caption_fixture["caption_row"]
    speeches = caption_fixture["speeches"]
    assert build_deeplink(row, speeches, 9999) is None
    assert build_deeplink(row, [], 0) is None
