"""Tests for `tools/reasoning_probe.py` (P4.10's lever probe): the lines it
prints are read into the ledger, so their fields must be the response's."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tools.reasoning_probe as rp  # noqa: E402


def test_the_outcome_line_reads_usage_and_the_answer():
    body = {"usage": {"completion_tokens": 768, "cost": 0.0093,
                      "completion_tokens_details": {"reasoning_tokens": 766}},
            "choices": [{"finish_reason": "stop", "native_finish_reason": "STOP",
                         "message": {"content": " 16 "}}]}
    line, cost = rp.outcome_line("max_tokens=800", 6.5, body)
    assert cost == pytest.approx(0.0093)
    for part in ("finish=stop/STOP", "completion=768", "reasoning=766",
                 "content=2ch", "answer='16'"):
        assert part in line


def test_an_upstream_error_is_printed_not_read_as_an_answer():
    body = {"usage": {"completion_tokens": 0, "cost": 0},
            "choices": [{"finish_reason": "error", "message": {"content": None},
                         "error": {"code": 429, "message": "temporarily rate-limited upstream"}}]}
    line, cost = rp.outcome_line("x", 1.0, body)
    assert cost == 0 and "content=0ch" in line and "rate-limited" in line


def test_the_limits_lines_carry_the_ceiling_and_the_reasoning_rule():
    m = {"id": "google/gemini-3.1-pro-preview", "context_length": 1048576,
         "top_provider": {"max_completion_tokens": 65536},
         "reasoning": {"mandatory": True, "supported_efforts": ["high", "medium", "low"]},
         "pricing": {"prompt": "0.000002", "completion": "0.000012"},
         "supported_parameters": ["max_tokens", "reasoning"]}
    text = "\n".join(rp.limits_line(m))
    assert "max_completion_tokens 65536" in text
    assert '"mandatory": true' in text and "completion 0.000012" in text


def test_an_unknown_config_is_refused():
    with pytest.raises(SystemExit):
        rp.main(["effort=extreme"])
