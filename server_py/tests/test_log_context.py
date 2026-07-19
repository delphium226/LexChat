"""Tests for Item 5 (correlation / request IDs) — the RequestIdFilter, the default
placeholder, and that the LOG_FORMAT actually renders %(request_id)s (guards the
KeyError-if-attribute-missing trap called out in docs/LOGGING_PR_D_PLAN.md)."""
import logging

from src.utils.log_context import RequestIdFilter, request_id_var
from src.utils.logger import LOG_FORMAT, DATE_FORMAT


def _make_record() -> logging.LogRecord:
    return logging.LogRecord(
        name="agent",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )


def test_filter_sets_request_id_from_var():
    token = request_id_var.set("abc123def456")
    try:
        record = _make_record()
        assert RequestIdFilter().filter(record) is True
        assert record.request_id == "abc123def456"
    finally:
        request_id_var.reset(token)


def test_filter_default_placeholder_when_unset():
    # Outside any request the var carries its "-" default (startup / crawler lines).
    record = _make_record()
    RequestIdFilter().filter(record)
    assert record.request_id == "-"


def test_log_format_renders_request_id():
    """The format references %(request_id)s, so a record lacking the attribute would
    raise KeyError at format time. Confirm the filter-populated attribute renders."""
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    record = _make_record()
    RequestIdFilter().filter(record)
    rendered = formatter.format(record)
    assert "[-]" in rendered
    assert "agent" in rendered
    assert "hello" in rendered


def test_log_format_renders_set_id():
    token = request_id_var.set("deadbeef0001")
    try:
        formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
        record = _make_record()
        RequestIdFilter().filter(record)
        assert "[deadbeef0001]" in formatter.format(record)
    finally:
        request_id_var.reset(token)


def test_handler_factories_attach_the_filter():
    """Both handler factories must carry a RequestIdFilter, else a record without the
    attribute reaches the format string and raises KeyError at emit time."""
    from src.utils.logger import _create_console_handler, _create_file_handler

    console = _create_console_handler()
    file_handler = _create_file_handler("test_pr_d.log")
    try:
        assert any(isinstance(f, RequestIdFilter) for f in console.filters)
        assert any(isinstance(f, RequestIdFilter) for f in file_handler.filters)
    finally:
        console.close()
        file_handler.close()
