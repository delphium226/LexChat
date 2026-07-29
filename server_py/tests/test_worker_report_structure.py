"""Unit tests for the A4 worker-report structure validation (agent_core).

Pure functions over the report Markdown — no network, DB, or LLM. They decide
whether a returned worker report is malformed enough to warrant the single
no-tools reformat retry.
"""

import asyncio

import pytest

from src.agent.agent_core import (
    _extract_section_headers,
    _report_needs_reformat,
    run_worker_agent,
)
from src.agent.provider_factory import set_request_provider_config


_WELL_FORMED = """1. **Summary Answer (BLUF):** XL Bully ownership without exemption is an offence.
2. **Statutory Framework:** The designation is under [Dangerous Dogs Act 1991 - s.1](http://www.legislation.gov.uk/ukpga/1991/65/section/1).
3. **Key Cases:** See [R (Coulthard) v SSEFRA [2025] EWCA Civ 1671](https://caselaw.nationalarchives.gov.uk/ewca/civ/2025/1671).
4. **Jurisdiction & Status:** Scotland; in force from 31 July 2024.
5. **References:**
   - [Dangerous Dogs Act 1991 - s.1](http://www.legislation.gov.uk/ukpga/1991/65/section/1)
   - [R (Coulthard) v SSEFRA [2025] EWCA Civ 1671](https://caselaw.nationalarchives.gov.uk/ewca/civ/2025/1671)
"""


def test_extract_headers_from_numbered_bold_labels():
    headers = _extract_section_headers(_WELL_FORMED)
    assert "summary answer (bluf)" in headers
    assert "references" in headers
    assert "statutory framework" in headers


def test_extract_headers_from_atx():
    md = "## Summary\nsome text\n### References\n- [x](http://y)"
    headers = _extract_section_headers(md)
    assert "summary" in headers
    assert "references" in headers


def test_well_formed_report_passes():
    assert _report_needs_reformat(_WELL_FORMED, has_sources=True) is False


def test_flat_blob_needs_reformat():
    # No section headers at all — the observed regression (headers all lost).
    blob = (
        "XL Bully ownership without a certificate of exemption is a criminal offence "
        "in Scotland from 31 July 2024 under the Dangerous Dogs Act 1991. Penalties "
        "include up to six months' imprisonment and a level 5 fine."
    )
    assert _report_needs_reformat(blob, has_sources=True) is True


def test_missing_references_section_needs_reformat():
    md = (
        "1. **Summary Answer (BLUF):** Answer here with a [link](http://legislation.gov.uk/x).\n"
        "2. **Detailed Analysis:** More analysis with the same [link](http://legislation.gov.uk/x)."
    )
    assert _report_needs_reformat(md, has_sources=True) is True


def test_references_present_but_no_link_with_sources_needs_reformat():
    md = (
        "1. **Summary Answer (BLUF):** Answer.\n"
        "2. **Detailed Analysis:** Analysis.\n"
        "3. **References:** Dangerous Dogs Act 1991 (no link provided)."
    )
    assert _report_needs_reformat(md, has_sources=True) is True


def test_no_link_but_no_sources_passes():
    # A legitimate "nothing found" answer with structure but no citations must not
    # be forced into a pointless reformat.
    md = (
        "1. **Summary Answer (BLUF):** No reported case law directly addresses this.\n"
        "2. **References:** None found."
    )
    assert _report_needs_reformat(md, has_sources=False) is False


def test_short_or_empty_content_is_skipped():
    assert _report_needs_reformat("", has_sources=True) is False
    assert _report_needs_reformat("Too short.", has_sources=True) is False


# --- retry wiring inside run_worker_agent --------------------------------------

@pytest.fixture
def _worker_config():
    set_request_provider_config({
        "_provider": "ollama",
        "_chat_mode": "research",
        "_research_mode": "legislation_only",
        "model": "test-model",
    })
    yield
    set_request_provider_config({})


def _chat_loop_returning(*contents):
    """Stub chat_loop that returns the given contents in order, one per call."""
    seq = list(contents)
    calls = []

    async def chat_loop(messages, model, cancel_event, num_ctx, tools, tool_executor,
                        on_chunk, emit_tool_details=False, timing_collector=None):
        calls.append({"messages": messages, "tools": tools})
        return {"content": seq[len(calls) - 1]}

    chat_loop.calls = calls
    return chat_loop


def test_malformed_report_triggers_one_reformat(_worker_config):
    flat = (
        "XL Bully ownership without a certificate of exemption is a criminal offence "
        "in Scotland from 31 July 2024 under the Dangerous Dogs Act 1991."
    )
    fixed = "1. **Summary Answer (BLUF):** Answer.\n2. **References:** None found."
    chat_loop = _chat_loop_returning(flat, fixed)

    result = asyncio.run(run_worker_agent(
        chat_loop, lambda *a, **k: None, "q", "test-model", None, 0,
    ))

    assert len(chat_loop.calls) == 2  # original + one reformat
    assert chat_loop.calls[1]["tools"] == []  # reformat call has no tools
    assert result["content"] == fixed


def test_well_formed_report_no_reformat(_worker_config):
    chat_loop = _chat_loop_returning(_WELL_FORMED)

    result = asyncio.run(run_worker_agent(
        chat_loop, lambda *a, **k: None, "q", "test-model", None, 0,
    ))

    assert len(chat_loop.calls) == 1  # no retry
    assert result["content"] == _WELL_FORMED


# --- reformat is counted, so the rate is measurable per model ------------------

def test_reformat_is_recorded_on_the_timing_collector(_worker_config):
    """The retry must increment report_reformat_retries — the counter backing the
    Efficiency tab's prompt-adherence rate. A counter wired to nothing would read
    as perfect adherence forever."""
    from src.utils.stopwatch import TimingCollector

    tc = TimingCollector("req")
    flat = (
        "XL Bully ownership without a certificate of exemption is a criminal offence "
        "in Scotland from 31 July 2024 under the Dangerous Dogs Act 1991."
    )
    fixed = "1. **Summary Answer (BLUF):** Answer.\n2. **References:** None found."
    chat_loop = _chat_loop_returning(flat, fixed)

    asyncio.run(run_worker_agent(
        chat_loop, lambda *a, **k: None, "q", "test-model", None, 0,
        timing_collector=tc,
    ))

    assert tc.report_reformat_retries == 1


def test_no_reformat_recorded_for_a_well_formed_report(_worker_config):
    from src.utils.stopwatch import TimingCollector

    tc = TimingCollector("req")
    chat_loop = _chat_loop_returning(_WELL_FORMED)

    asyncio.run(run_worker_agent(
        chat_loop, lambda *a, **k: None, "q", "test-model", None, 0,
        timing_collector=tc,
    ))

    assert tc.report_reformat_retries == 0


def test_conversational_mode_skips_validation():
    set_request_provider_config({
        "_provider": "ollama",
        "_chat_mode": "conversational",
        "_research_mode": "legislation_only",
        "model": "test-model",
    })
    try:
        flat = "A short conversational answer with no structure whatsoever here."
        chat_loop = _chat_loop_returning(flat)
        result = asyncio.run(run_worker_agent(
            chat_loop, lambda *a, **k: None, "q", "test-model", None, 0,
        ))
        assert len(chat_loop.calls) == 1  # not validated, not reformatted
        assert result["content"] == flat
    finally:
        set_request_provider_config({})
