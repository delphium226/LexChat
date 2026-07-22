"""Unit tests for the LEX API backoff/retry helper (executor._request_with_retry).

The LEX API is rate limited; these cover that a 429 (or transient 5xx / network
error) is retried with bounded backoff honouring Retry-After, and that
non-retryable responses pass straight through. asyncio.sleep is stubbed so the
tests run instantly, and the recorded delays are asserted instead.
"""
import asyncio

import httpx
import pytest

from src.agent.tools import executor


@pytest.fixture
def _no_sleep(monkeypatch):
    """Replace asyncio.sleep inside the executor with a recorder — no real waiting."""
    delays = []

    async def fake_sleep(d):
        delays.append(d)

    monkeypatch.setattr(executor.asyncio, "sleep", fake_sleep)
    return delays


def _client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _sequence_handler(responses):
    """Return a MockTransport handler that yields the given responses in order,
    repeating the last once exhausted."""
    state = {"i": 0}

    def handler(request):
        i = min(state["i"], len(responses) - 1)
        state["i"] += 1
        return responses[i]

    return handler


# --- Retry-After parsing --------------------------------------------------------

def test_retry_after_integer():
    resp = httpx.Response(429, headers={"Retry-After": "5"})
    assert executor._retry_after_seconds(resp) == 5.0


def test_retry_after_missing():
    assert executor._retry_after_seconds(httpx.Response(429)) is None


def test_retry_after_garbage_returns_none():
    resp = httpx.Response(429, headers={"Retry-After": "soon-ish"})
    assert executor._retry_after_seconds(resp) is None


# --- retry behaviour ------------------------------------------------------------

@pytest.mark.asyncio
async def test_retries_on_429_then_succeeds(_no_sleep):
    handler = _sequence_handler([
        httpx.Response(429, headers={"Retry-After": "2"}),
        httpx.Response(200, json={"ok": True}),
    ])
    async with _client(handler) as client:
        resp = await executor._request_with_retry(client, "POST", "https://lex/x", json={})
    assert resp.status_code == 200
    assert _no_sleep == [2.0]  # honoured the Retry-After value


@pytest.mark.asyncio
async def test_retries_on_transient_503(_no_sleep):
    handler = _sequence_handler([
        httpx.Response(503),
        httpx.Response(200, json={"ok": True}),
    ])
    async with _client(handler) as client:
        resp = await executor._request_with_retry(client, "POST", "https://lex/x", json={})
    assert resp.status_code == 200
    assert len(_no_sleep) == 1  # one computed backoff (no Retry-After header)


@pytest.mark.asyncio
async def test_persistent_429_exhausts_and_returns_last(_no_sleep):
    handler = _sequence_handler([httpx.Response(429)])
    async with _client(handler) as client:
        resp = await executor._request_with_retry(client, "POST", "https://lex/x", json={})
    # Non-successful after all retries: returned to caller (which then raises).
    assert resp.status_code == 429
    assert len(_no_sleep) == executor._MAX_RETRIES  # 3 backoffs, 4 attempts total


@pytest.mark.asyncio
async def test_non_retryable_400_passes_through(_no_sleep):
    handler = _sequence_handler([httpx.Response(400, json={"error": "bad"})])
    async with _client(handler) as client:
        resp = await executor._request_with_retry(client, "GET", "https://lex/x")
    assert resp.status_code == 400
    assert _no_sleep == []  # no retry, no sleep


@pytest.mark.asyncio
async def test_success_first_try_no_sleep(_no_sleep):
    handler = _sequence_handler([httpx.Response(200, json={"ok": True})])
    async with _client(handler) as client:
        resp = await executor._request_with_retry(client, "POST", "https://lex/x", json={})
    assert resp.status_code == 200
    assert _no_sleep == []


@pytest.mark.asyncio
async def test_retries_network_error_then_succeeds(_no_sleep):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectTimeout("boom", request=request)
        return httpx.Response(200, json={"ok": True})

    async with _client(handler) as client:
        resp = await executor._request_with_retry(client, "POST", "https://lex/x", json={})
    assert resp.status_code == 200
    assert len(_no_sleep) == 1


@pytest.mark.asyncio
async def test_retry_after_capped(_no_sleep):
    # A hostile Retry-After is capped so a worker can't stall indefinitely.
    handler = _sequence_handler([
        httpx.Response(429, headers={"Retry-After": "9999"}),
        httpx.Response(200, json={"ok": True}),
    ])
    async with _client(handler) as client:
        resp = await executor._request_with_retry(client, "POST", "https://lex/x", json={})
    assert resp.status_code == 200
    assert _no_sleep == [executor._MAX_RETRY_AFTER_S]
