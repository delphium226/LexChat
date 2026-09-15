"""P1.2 — the `current_only` filter is gone (bucket B4).

The filter tested the LEX `status` field for `{repealed, revoked, spent,
expired, not in force}`. That field's vocabulary is `final` and `revised` only:
it records **which text version is held**, not in-force status. So the filter
excluded nothing, and could not be repaired by extending the word list — there
is no in-force signal anywhere in the tool surface.

Two things made that worse than a dead control, and both are what these tests
pin:

* The UI pill read **"In force as at <today>"**, an affirmative claim about
  currency made on the strength of a check that never ran.
* `build_filter_constraint_block` injected **"Status: In-force legislation only.
  Do not cite or rely on repealed or not-yet-in-force legislation."** into the
  system prompt. The model then reported currency because the system told it the
  results were current. 42 of 62 pre-pilot sessions ran with this on, and in
  6341 the answer stated every provision cited was in force — ss.38-39 Shops Act
  are repealed.

The request field survives as an accepted-and-ignored no-op so an existing
client or the eval harness does not start failing validation. Nothing reads it.
"""

from src.routers.agent_request import ChatRequest, build_request_config

_PROVIDER = {"model": "m", "max_concurrent_requests": 1}
_FEATURES = {}


def _config(**body_kwargs):
    body = ChatRequest(messages=[{"role": "user", "content": "q"}], model="m",
                       **body_kwargs)
    return build_request_config(
        body, dict(_PROVIDER), "openrouter", dict(_FEATURES), chat_mode="research"
    )


def test_current_only_is_gone_from_the_request_model():
    """Removed outright, not deprecated in place.

    Safe for existing clients because `AgentRequestBase` does not set
    `extra="forbid"`: pydantic ignores an unknown key rather than rejecting the
    request, so a client still sending `current_only` gets the same 200 it got
    before and the value goes nowhere.
    """
    body = ChatRequest(
        messages=[{"role": "user", "content": "q"}], model="m", current_only=True
    )
    assert not hasattr(body, "current_only"), "the field must not exist"
    assert "current_only" not in body.model_dump()


def test_sending_current_only_is_ignored_not_rejected():
    """The compatibility guarantee, asserted rather than assumed. If anyone adds
    `extra="forbid"` to this model later, this test says what it will break."""
    assert ChatRequest.model_config.get("extra") in (None, "ignore")
    assert "_current_only" not in _config(current_only=True)


def test_other_filters_still_reach_the_config():
    """A guard on the removal: it must not have taken its neighbours with it."""
    cfg = _config(jurisdiction="scotland", legislation_type="secondary", year_to=2026)
    assert cfg["_jurisdiction"] == "scotland"
    assert cfg["_legislation_type"] == "secondary"
    assert cfg["_year_to"] == 2026


def test_the_prompt_never_claims_in_force_status():
    """The specific string that caused bucket B4."""
    from src.prompts import build_filter_constraint_block

    for cfg in (
        {"_current_only": True},                       # a stale key, if one survived
        {"_current_only": True, "_jurisdiction": "scotland"},
        {"_jurisdiction": "scotland", "_legislation_type": "primary"},
        {},
    ):
        block = build_filter_constraint_block(cfg)
        assert "In-force legislation only" not in block
        assert "not-yet-in-force" not in block


def test_a_stale_current_only_key_does_not_resurrect_the_block():
    """Belt and braces: even if something sets `_current_only` again, it must
    not be enough on its own to emit a filter-constraint block."""
    from src.prompts import build_filter_constraint_block

    assert build_filter_constraint_block({"_current_only": True}) == ""


def test_the_no_op_post_filter_is_gone_from_the_executor():
    """`_INACTIVE` tested a vocabulary the API never emits. Its presence would
    mean the dead filter had been reinstated."""
    import inspect

    from src.agent.tools import executor

    source = inspect.getsource(executor)
    assert "_INACTIVE" not in source
    assert "not in force" not in source


def test_the_filter_block_still_works_for_filters_that_do_something():
    from src.prompts import build_filter_constraint_block

    block = build_filter_constraint_block(
        {"_jurisdiction": "scotland", "_legislation_type": "secondary"}
    )
    assert "ACTIVE RESEARCH FILTERS" in block
    assert "Scotland" in block
