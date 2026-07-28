"""Unit tests for the Westminster (Hansard API) response shaping.

Pure functions over the debate JSON document, so no network is needed. The focus
is _flatten_debate's contribution cap: a whole day of departmental oral questions
flattens (via ChildDebates) into several hundred contributions, and an uncapped
result stacks with its siblings into a prefill large enough to stall the provider.
"""

from src.agent.tools.westminster import _MAX_RETURNED_CONTRIBUTIONS, _flatten_debate


def _debate(n_contributions: int, in_child: int = 0) -> dict:
    """A Hansard debate document with n contributions in the root section."""
    def items(start, count):
        return [
            {
                "ItemType": "Contribution",
                "AttributedTo": f"Member {i}",
                "Value": f"Contribution number {i}.",
                "MemberId": i,
                "OrderInSection": i,
            }
            for i in range(start, start + count)
        ]

    return {
        "Overview": {
            "ExtId": "ABC123",
            "Title": "Oral Answers to Questions",
            "House": "Commons",
            "Date": "2026-06-02T00:00:00",
            "Location": "Commons Chamber",
        },
        "Items": items(0, n_contributions),
        "ChildDebates": (
            [{"Items": items(n_contributions, in_child), "ChildDebates": []}]
            if in_child else []
        ),
    }


def test_flatten_keeps_identity_and_contributions():
    out = _flatten_debate(_debate(3))
    assert out["debate_ext_id"] == "ABC123"
    assert out["house"] == "Commons"
    assert out["date"] == "2026-06-02"
    assert out["total_contributions"] == 3
    assert out["contributions"][0]["speaker"] == "Member 0"
    assert "truncated" not in out


def test_flatten_walks_child_debates_in_order():
    out = _flatten_debate(_debate(2, in_child=2))
    assert out["total_contributions"] == 4
    assert [c["member_id"] for c in out["contributions"]] == [0, 1, 2, 3]


def test_flatten_skips_non_contribution_items():
    data = _debate(1)
    data["Items"].insert(0, {"ItemType": "Timestamp", "Value": "14:05"})
    out = _flatten_debate(data)
    assert out["total_contributions"] == 1


def test_flatten_caps_long_debate_and_flags_it():
    n = _MAX_RETURNED_CONTRIBUTIONS + 25
    out = _flatten_debate(_debate(n))
    assert len(out["contributions"]) == _MAX_RETURNED_CONTRIBUTIONS
    assert out["truncated"] is True
    # The true count survives so the model can see what it is missing.
    assert out["total_contributions"] == n
    assert str(n) in out["note"]
    assert out["contributions"][0]["member_id"] == 0  # kept from the start


def test_flatten_caps_across_child_debates():
    """The cap applies to the flattened total, not per section."""
    half = _MAX_RETURNED_CONTRIBUTIONS
    out = _flatten_debate(_debate(half, in_child=half))
    assert len(out["contributions"]) == _MAX_RETURNED_CONTRIBUTIONS
    assert out["total_contributions"] == half * 2
