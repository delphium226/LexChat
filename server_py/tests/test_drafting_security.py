"""S0 security prerequisites for the drafting bot.

Three of these guard properties that are invisible in normal operation and
would fail silently if regressed — a cookie sent over plain HTTP, a draft
clause written to a shared table, a draft clause written to a log file. The
fourth pins the new feature flag.

See `docs/drafting/BUILD_PLAN.md` (S0) for why each one matters.
"""

import json

import pytest

from src.routers.agent_request import ChatRequest, build_request_config
from src.utils.redact import (
    SAFE_ARG_KEYS,
    redact_args,
    redact_email,
    redact_text,
)

# A distinctive string standing in for pre-publication legislative text.
DRAFT = (
    "(1) The Scottish Ministers may by regulations make provision about "
    "ZZQXMARKER, and such regulations may make different provision for "
    "different purposes."
)


def _config(research_mode, features=None, chat_mode="research"):
    body = ChatRequest(
        messages=[{"role": "user", "content": DRAFT}],
        model="test-model",
        research_mode=research_mode,
    )
    return build_request_config(
        body,
        provider_config={},
        active_provider="openrouter",
        features=features if features is not None else {},
        chat_mode=chat_mode,
    )


# ---------------------------------------------------------------------------
# 1. Local prompt cache is forced off for the drafting bot
# ---------------------------------------------------------------------------

def test_local_cache_forced_off_for_drafting():
    """The cache key query is the raw user question — on this bot, the draft."""
    cfg = _config("drafting", features={"local_prompt_cache_enabled": True})
    assert cfg["_local_prompt_cache_enabled"] is False


@pytest.mark.parametrize(
    "mode",
    ["legislation_only", "case_law_only", "hybrid", "parliamentary_records",
     "westminster_records"],
)
def test_local_cache_untouched_for_every_other_mode(mode):
    cfg = _config(mode, features={"local_prompt_cache_enabled": True})
    assert cfg["_local_prompt_cache_enabled"] is True


def test_admin_flag_still_wins_when_off():
    """The drafting override ANDs with the flag; it must not re-enable it."""
    for mode in ("drafting", "legislation_only"):
        cfg = _config(mode, features={"local_prompt_cache_enabled": False})
        assert cfg["_local_prompt_cache_enabled"] is False


def test_drafting_override_holds_for_deep_research_too():
    """Deep Research keys on plan text, but the draft still reaches the worker."""
    cfg = _config("drafting", features={"local_prompt_cache_enabled": True},
                  chat_mode="deep_research")
    assert cfg["_local_prompt_cache_enabled"] is False


def test_search_drafting_guidance_absent_from_cacheable_tools():
    """The one-line change most likely to introduce a real leak here."""
    from src.services.local_prompt_cache import CACHEABLE_TOOLS

    assert "search_drafting_guidance" not in CACHEABLE_TOOLS


# ---------------------------------------------------------------------------
# 2. drafting_mode_enabled feature flag
# ---------------------------------------------------------------------------

def test_drafting_flag_threaded_onto_request_config():
    assert _config("drafting", features={"drafting_mode_enabled": False})[
        "_drafting_mode_enabled"
    ] is False


def test_drafting_flag_absent_reads_as_enabled():
    """The repo-wide `.get(key, True)` convention: an absent key means ON."""
    assert _config("drafting", features={})["_drafting_mode_enabled"] is True


def test_drafting_flag_in_developer_defaults():
    from src.routers.developer import _DEFAULT_FEATURES, FeaturesUpdate

    assert _DEFAULT_FEATURES["drafting_mode_enabled"] is True
    assert "drafting_mode_enabled" in FeaturesUpdate.model_fields


# ---------------------------------------------------------------------------
# 3. Redaction
# ---------------------------------------------------------------------------

def test_redact_text_hides_the_body_but_keeps_a_handle():
    out = redact_text(DRAFT)
    assert "ZZQXMARKER" not in out
    assert "different provision" not in out
    assert f"{len(DRAFT)} chars" in out
    assert "sha1:" in out


def test_redact_text_is_stable_and_distinguishing():
    assert redact_text(DRAFT) == redact_text(DRAFT)
    assert redact_text(DRAFT) != redact_text(DRAFT + " x")


def test_redact_text_handles_empty_and_newlines():
    assert redact_text("") == "<empty>"
    # A newline in the prefix would break the one-line-per-record log format.
    assert "\n" not in redact_text("first line\nsecond line")


def test_redact_email_keeps_domain_drops_person():
    assert redact_email("alice.smith@gov.scot") == "al***@gov.scot"
    assert redact_email("not-an-email") == "<email>"
    assert redact_email("") == "<email>"


def test_redact_args_redacts_free_text_keeps_structure():
    out = redact_args({
        "query": DRAFT,
        "legislation_id": "asp-2018-1",
        "year_from": 2018,
        "current_only": True,
    })
    assert "ZZQXMARKER" not in json.dumps(out)
    assert out["legislation_id"] == "asp-2018-1"
    assert out["year_from"] == 2018
    assert out["current_only"] is True


def test_redact_args_fails_safe_on_unknown_keys():
    """An allowlist, not a denylist: a tool added later is redacted by default."""
    out = redact_args({"some_future_free_text_param": DRAFT})
    assert "ZZQXMARKER" not in json.dumps(out)


def test_redact_args_redacts_nested_structures():
    out = redact_args({"items": [{"clause": DRAFT}]})
    assert "ZZQXMARKER" not in json.dumps(out)


def test_redact_args_output_is_json_serialisable():
    """It is interpolated via json.dumps at the call site."""
    json.dumps(redact_args({"query": DRAFT, "legislation_id": "asp-2018-1"}))


def test_redact_args_tolerates_a_non_dict():
    assert "ZZQXMARKER" not in json.dumps(redact_args(DRAFT))


def test_query_is_not_a_safe_arg_key():
    assert "query" not in SAFE_ARG_KEYS


@pytest.mark.asyncio
async def test_executor_logs_redacted_args(caplog):
    """End-to-end at the real call site: the draft must not reach the log.

    An unrecognised tool name is used deliberately. The log line is emitted
    before the tool dispatch, so this exercises the same statement a real tool
    would — but returns immediately instead of calling the live LEX API, which
    a unit test must not do (it is rate-limited at 1000 req/hour per IP).
    """
    import src.agent.tools.executor as executor

    with caplog.at_level("INFO", logger="agent"):
        result = await executor.execute_worker_tool(
            "not_a_real_tool",
            {"query": DRAFT, "legislation_id": "asp-2018-1"},
        )

    assert "not found" in result  # confirms we took the no-network path
    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert "[Worker Tool Exec]" in logged  # confirms the line was captured
    assert "ZZQXMARKER" not in logged
    assert "asp-2018-1" in logged


# ---------------------------------------------------------------------------
# 4. Auth cookie
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_login_cookie_is_secure_over_https(client, seed_user):
    """Secure is set when the browser's connection is HTTPS.

    X-Forwarded-Proto is what nginx sends; the test client itself always
    speaks plain http:// to the ASGI app, exactly as uvicorn-behind-nginx does.
    """
    r = await client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "testpassword"},
        headers={"X-Forwarded-Proto": "https"},
    )
    assert r.status_code == 200
    cookie = r.headers.get("set-cookie", "")
    assert "token=" in cookie
    assert "Secure" in cookie
    assert "HttpOnly" in cookie


@pytest.mark.asyncio
async def test_login_cookie_is_not_secure_over_plain_http(client, seed_user):
    """Secure must NOT be set on a plain-HTTP deployment.

    The browser discards a Secure cookie served over http:// without error and
    the frontend has no bearer-token fallback, so a hardcoded Secure made login
    a silent no-op — 200 with no session, then a 401 rendered as "your session
    has expired". HttpOnly is unconditional.
    """
    r = await client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "testpassword"},
    )
    assert r.status_code == 200
    cookie = r.headers.get("set-cookie", "")
    assert "token=" in cookie
    assert "Secure" not in cookie
    assert "HttpOnly" in cookie
