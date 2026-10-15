"""FIX_PLAN P1.7 (Session 50) — a Gemini model is sent each tool result whole.

Through OpenRouter, a Google model receives a tool result as a function
response, and where the content holds a JSON object every other piece of text
in it is dropped. Probed on the pinned model through the product's own payload
path (`evidence/seam/s50/f1_truncation.py`): a note after the JSON, or before
it, seen 0 of 4; the same note alone 2 of 2; wrapped as one JSON string field
2 of 2, on both Google upstreams. Our code appends its notes after the JSON a
tool returns, so 13,031 of 22,236 stored Worker tool results carried text the
Worker never saw; on 6409 t7 the wrap turned "cannot be verified" into the
saving provisions read from the text, 9 of 9.

`_wrap_tool_results` sends a Google model any tool result that is not wholly
JSON as `{"result": <content>}`; a wholly-JSON result and every other model's
payload are unchanged. The seam (`tools/seam_replay.py --as-sent`) follows the
code at `--at-rev`, so a stored payload from before P1.7 redraws as it was sent.
"""
import json

import httpx
import pytest

from src.agent import openrouter_client
from src.agent.openrouter_client import _convert_messages_to_openai, _wrap_tool_results

from .test_stream_retry import (  # noqa: F401  (fixtures are used by name)
    _mock_http,
    _no_sleep,
    _sse,
)

GEMINI = "google/gemini-3.1-pro-preview"
NOTE = "[SEARCH SCOPE — 0 provisions of ssi/1901/3 matched \"£\".]"
MIXED = '{"results": [], "returned": 0}\n\n' + NOTE


def _msgs(content):
    return [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": '{"looks": "like json"} but is the user'},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": "t", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "c1", "name": "t", "content": content},
    ]


def test_a_mixed_result_reaches_a_gemini_model_whole():
    out = _wrap_tool_results(_convert_messages_to_openai(_msgs(MIXED)), GEMINI)
    sent = out[-1]["content"]
    assert json.loads(sent) == {"result": MIXED}
    assert "£" in sent  # not escaped: the model reads the same characters


def test_text_before_the_json_is_kept_too():
    content = NOTE + "\n\n" + '{"results": []}'
    out = _wrap_tool_results(_convert_messages_to_openai(_msgs(content)), GEMINI)
    assert json.loads(out[-1]["content"]) == {"result": content}


def test_plain_text_is_wrapped_and_loses_nothing():
    out = _wrap_tool_results(_convert_messages_to_openai(_msgs("A summary. Reg 3 saves s.49.")), GEMINI)
    assert json.loads(out[-1]["content"]) == {"result": "A summary. Reg 3 saves s.49."}


@pytest.mark.parametrize("content", ['{"results": [], "returned": 0}', '[1, 2]', '"a string"', "  {}  "])
def test_a_wholly_json_result_is_sent_as_it_was(content):
    msgs = _convert_messages_to_openai(_msgs(content))
    out = _wrap_tool_results(msgs, GEMINI)
    assert out[-1] is msgs[-1] and out[-1]["content"] == content


@pytest.mark.parametrize("content", ["", None])
def test_an_empty_result_is_left_alone(content):
    msgs = _convert_messages_to_openai(_msgs(content))
    assert _wrap_tool_results(msgs, GEMINI)[-1] is msgs[-1]


def test_only_tool_messages_change():
    msgs = _convert_messages_to_openai(_msgs(MIXED))
    out = _wrap_tool_results(msgs, GEMINI)
    assert out[:3] == msgs[:3] and all(a is b for a, b in zip(out[:3], msgs[:3]))
    assert out[-1]["tool_call_id"] == "c1" and out[-1]["role"] == "tool"


@pytest.mark.parametrize("model", ["anthropic/claude-sonnet-5-5", "openai/gpt-5", "test/model",
                                   "google-labs/model", "x/google/model"])
def test_every_other_model_gets_the_same_list_back(model):
    msgs = _convert_messages_to_openai(_msgs(MIXED))
    assert _wrap_tool_results(msgs, model) is msgs


@pytest.mark.asyncio
async def test_chat_loop_sends_the_wrapped_result_to_a_gemini_model(_no_sleep, _mock_http):
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, text=_sse('{"choices":[{"delta":{"content":"ok"}}]}'))
    _mock_http(handler)
    for model in (GEMINI, "anthropic/claude-sonnet-5-5"):
        await openrouter_client.chat_loop(
            messages=_msgs(MIXED), model=model, cancel_event=None, num_ctx=0,
            tools=[], tool_executor=None)
    gem, other = seen
    assert json.loads(gem["messages"][-1]["content"]) == {"result": MIXED}
    # Anthropic's last text-bearing message carries its cache marker, as before:
    # the wrap never touched it, so its content is the original text.
    tool = other["messages"][-1]
    text = tool["content"][0]["text"] if isinstance(tool["content"], list) else tool["content"]
    assert text == MIXED


# --- the seam follows the code it rebuilds --------------------------------------

@pytest.mark.asyncio
async def test_the_seam_sends_the_payload_it_reports(_no_sleep, _mock_http):
    from src.agent.provider_factory import set_request_provider_config
    from tools import seam_replay as sr
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, text=_sse('{"choices":[{"delta":{"content":"ok"}}]}'))
    _mock_http(handler)
    cfg = {"_provider": "openrouter", "model": GEMINI, "base_url": "https://or.example/api/v1",
           "api_key": "k"}
    try:
        await sr.run_as_sent(_msgs(MIXED), cfg, [], wrap=True)
        await sr.run_as_sent(_msgs(MIXED), cfg, [], wrap=False)
    finally:
        set_request_provider_config({})
    assert json.loads(seen[0]["messages"][-1]["content"]) == {"result": MIXED}
    assert seen[1]["messages"][-1]["content"] == MIXED


def test_the_seam_wraps_as_the_working_tree_does_and_not_before_p17():
    from tools import seam_replay as sr
    assert sr.rev_wraps_tool_results(None) is True
    assert sr.rev_wraps_tool_results("2473646") is False  # P3.38's acceptance code
    assert sr.as_sent_wrap("auto", "2473646") is False
    assert sr.as_sent_wrap("on", "2473646") is True
    assert sr.as_sent_wrap("off", None) is False
