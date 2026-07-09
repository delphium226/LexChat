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

from src.services.caption_match import annotate_speeches, build_deeplink, match_speech

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
    """annotate_speeches links a substantial share of speeches, all monotonic."""
    row = caption_fixture["caption_row"]
    speeches = [dict(s) for s in caption_fixture["speeches"]]  # copy — annotate mutates

    n = annotate_speeches(row, speeches)
    assert n >= len(speeches) // 2, f"only {n}/{len(speeches)} speeches linked"

    starts = [s["video_deeplink"]["clip_start"] for s in speeches if s.get("video_deeplink")]
    assert starts == sorted(starts), f"linked timestamps not monotonic: {starts}"
    # every attached link clears the confidence threshold
    confs = [s["video_deeplink"]["confidence"] for s in speeches if s.get("video_deeplink")]
    assert all(c >= 0.8 for c in confs)


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
