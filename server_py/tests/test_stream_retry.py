"""Unit tests for the chat-loop stream retry (openrouter_client / ollama_client).

A provider that stalls before sending response headers raises httpx.ReadTimeout;
unretried it killed the entire SSE request, discarding every tool result already
gathered. These cover that a pre-output stall is replayed with bounded backoff,
that a stall *after* output has been emitted is NOT replayed (replaying would
duplicate tokens already streamed to the user), and that a persistent stall
eventually surfaces. asyncio.sleep is stubbed so the tests run instantly.
"""
import httpx
import pytest

from src.agent import ollama_client, openrouter_client


# --- harness --------------------------------------------------------------------

def _sse(*chunks: str) -> str:
    """Build an OpenAI-style SSE body from raw JSON chunk strings."""
    return "".join(f"data: {c}\n\n" for c in chunks) + "data: [DONE]\n\n"


_OR_CONTENT = _sse('{"choices":[{"delta":{"content":"hello"}}]}')
_OLLAMA_CONTENT = '{"message":{"content":"hello"},"done":true}\n'


class _RaisingStream(httpx.AsyncByteStream):
    """A response body that yields some bytes and then stalls.

    Used to reach the "partial output already emitted" branch, which a plain
    MockTransport exception cannot produce (it raises before any bytes arrive).
    """

    def __init__(self, payload: bytes, request: httpx.Request):
        self._payload = payload
        self._request = request

    async def __aiter__(self):
        yield self._payload
        raise httpx.ReadTimeout("stalled mid-stream", request=self._request)


@pytest.fixture
def _no_sleep(monkeypatch):
    """Replace asyncio.sleep in both clients with a recorder — no real waiting."""
    delays = []

    async def fake_sleep(d):
        delays.append(d)

    monkeypatch.setattr(openrouter_client.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(ollama_client.asyncio, "sleep", fake_sleep)
    return delays


@pytest.fixture
def _mock_http(monkeypatch):
    """Route both clients' httpx.AsyncClient through a MockTransport handler.

    chat_loop constructs its own client, so the class is swapped for a factory
    that drops the real-network kwargs and injects the mock transport.
    """
    real = httpx.AsyncClient

    def install(handler):
        def factory(*args, **kwargs):
            kwargs.pop("verify", None)
            kwargs.pop("proxy", None)
            return real(transport=httpx.MockTransport(handler), **kwargs)

        monkeypatch.setattr(httpx, "AsyncClient", factory)

    return install


def _sequence_handler(responses):
    """Yield the given responses/exceptions in order, repeating the last one.

    A callable entry is invoked with the request (so it can raise, or build a
    response that needs the request object).
    """
    state = {"i": 0}

    def handler(request):
        i = min(state["i"], len(responses) - 1)
        state["i"] += 1
        item = responses[i]
        return item(request) if callable(item) else item

    return handler


def _timeout(request):
    raise httpx.ReadTimeout("no response headers", request=request)


async def _or_chat_loop(**kw):
    return await openrouter_client.chat_loop(
        messages=[{"role": "user", "content": "q"}],
        model="test/model",
        cancel_event=None,
        num_ctx=0,
        tools=[],
        tool_executor=None,
        **kw,
    )


async def _ollama_chat_loop(**kw):
    return await ollama_client.chat_loop(
        messages=[{"role": "user", "content": "q"}],
        model="test-model",
        cancel_event=None,
        num_ctx=0,
        tools=[],
        tool_executor=None,
        **kw,
    )


# --- OpenRouter -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_or_retries_after_header_timeout(_no_sleep, _mock_http):
    _mock_http(_sequence_handler([_timeout, httpx.Response(200, text=_OR_CONTENT)]))
    result = await _or_chat_loop()
    assert result["content"] == "hello"
    assert _no_sleep == [openrouter_client._STREAM_RETRY_BASE_S]


@pytest.mark.asyncio
async def test_or_backoff_is_exponential(_no_sleep, _mock_http):
    _mock_http(_sequence_handler([_timeout, _timeout, httpx.Response(200, text=_OR_CONTENT)]))
    result = await _or_chat_loop()
    assert result["content"] == "hello"
    base = openrouter_client._STREAM_RETRY_BASE_S
    assert _no_sleep == [base, base * 2]


@pytest.mark.asyncio
async def test_or_persistent_timeout_raises(_no_sleep, _mock_http):
    _mock_http(_sequence_handler([_timeout]))
    with pytest.raises(httpx.ReadTimeout):
        await _or_chat_loop()
    # One fewer sleep than attempts: the last failure raises instead of waiting.
    assert len(_no_sleep) == openrouter_client._MAX_STREAM_ATTEMPTS - 1


@pytest.mark.asyncio
async def test_or_no_retry_once_tokens_emitted(_no_sleep, _mock_http):
    """A mid-stream stall must NOT replay — the tokens are already downstream."""
    emitted = []

    def handler(request):
        # No trailing [DONE]: the loop must still be iterating when the stall hits.
        body = b'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n'
        return httpx.Response(200, stream=_RaisingStream(body, request))

    _mock_http(handler)

    async def on_chunk(evt):
        emitted.append(evt)

    with pytest.raises(httpx.ReadTimeout):
        await _or_chat_loop(on_chunk=on_chunk)
    assert _no_sleep == []  # no retry attempted
    assert any(e.get("content") == "partial" for e in emitted)


@pytest.mark.asyncio
async def test_or_success_first_try_no_sleep(_no_sleep, _mock_http):
    _mock_http(_sequence_handler([httpx.Response(200, text=_OR_CONTENT)]))
    result = await _or_chat_loop()
    assert result["content"] == "hello"
    assert _no_sleep == []


@pytest.mark.asyncio
async def test_or_http_error_is_not_retried(_no_sleep, _mock_http):
    _mock_http(_sequence_handler([httpx.Response(400, json={"error": "bad"})]))
    with pytest.raises(httpx.HTTPStatusError):
        await _or_chat_loop()
    assert _no_sleep == []


# --- Ollama ---------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ollama_retries_after_header_timeout(_no_sleep, _mock_http):
    _mock_http(_sequence_handler([_timeout, httpx.Response(200, text=_OLLAMA_CONTENT)]))
    result = await _ollama_chat_loop()
    assert result["content"] == "hello"
    assert _no_sleep == [ollama_client._STREAM_RETRY_BASE_S]


@pytest.mark.asyncio
async def test_ollama_persistent_timeout_raises(_no_sleep, _mock_http):
    _mock_http(_sequence_handler([_timeout]))
    with pytest.raises(httpx.ReadTimeout):
        await _ollama_chat_loop()
    assert len(_no_sleep) == ollama_client._MAX_STREAM_ATTEMPTS - 1
