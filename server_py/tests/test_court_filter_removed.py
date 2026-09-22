"""P4.4 — the case-law court filter is gone (bucket B12).

Three reasons, and the third is what made it a defect rather than dead weight.

* **Nobody used it.** Zero of the 41 replayed pre-pilot sessions set a court,
  against `current_only` at 29 and `jurisdiction` at 13. Only 11 of 62 sessions
  touched case law at all.
* **For a Scottish Government audience it was a trap.** All 14 options were
  English, Welsh or UK-wide, because the National Archives corpus holds no
  Scottish courts: `atom.xml?court=csoh` is rejected **400 — "csoh is not one of
  the available choices"** (P5.2). Selecting any option guaranteed a
  non-Scottish result set, narrowing a corpus that was already the wrong
  jurisdiction.
* **It overrode the model.** `executor.py` applied `_court` *after* the model's
  own `court` argument and clobbered it, so a court selected three turns earlier
  silently beat the model's per-query judgement — the same stale-filter failure
  as B2 and B4. The neighbouring date filters *intersect* (`max`/`min`); court
  did not.

**The capability is not removed, only the control.** `search_case_law` keeps its
`court` parameter, so AILA still narrows by court when a question calls for it —
which is the behaviour the filter was standing in front of. These tests pin that
distinction, because deleting the tool parameter too would be the obvious wrong
reading of this change.

The request field follows P1.2's precedent exactly: removed outright, accepted
and ignored by pydantic, with `audit["filters"]["court"]` still emitted as a
permanent null so the trace shape is unchanged for the eval harness.
"""

import inspect

from src.routers.agent_request import ChatRequest, build_request_config

_PROVIDER = {"model": "m", "max_concurrent_requests": 1}


def _config(**body_kwargs):
    body = ChatRequest(messages=[{"role": "user", "content": "q"}], model="m",
                       **body_kwargs)
    return build_request_config(
        body, dict(_PROVIDER), "openrouter", {}, chat_mode="research"
    )


def test_court_is_gone_from_the_request_model():
    body = ChatRequest(
        messages=[{"role": "user", "content": "q"}], model="m", court="uksc"
    )
    assert not hasattr(body, "court"), "the field must not exist"
    assert "court" not in body.model_dump()


def test_sending_court_is_ignored_not_rejected():
    """The compatibility guarantee, asserted rather than assumed — a client or
    harness still sending `court` must get the same 200 it got before."""
    assert ChatRequest.model_config.get("extra") in (None, "ignore")
    assert "_court" not in _config(court="uksc")


def test_other_filters_still_reach_the_config():
    """A guard on the removal: it must not have taken its neighbours with it.
    The case-law DATE filters in particular sit next to it in the same branch."""
    cfg = _config(jurisdiction="scotland", date_from="2020-01-01", date_to="2024-12-31")
    assert cfg["_jurisdiction"] == "scotland"
    assert cfg["_date_from"] == "2020-01-01"
    assert cfg["_date_to"] == "2024-12-31"


def test_the_prompt_never_states_a_court_constraint():
    from src.prompts import build_filter_constraint_block

    for cfg in (
        {"_court": "uksc"},                               # a stale key, if one survived
        {"_court": "uksc", "_jurisdiction": "scotland"},
        {"_jurisdiction": "scotland"},
        {},
    ):
        assert "Case law court" not in build_filter_constraint_block(cfg)


def test_a_stale_court_key_does_not_resurrect_the_block():
    """Belt and braces, mirroring P1.2: even if something sets `_court` again it
    must not be enough on its own to emit a filter-constraint block."""
    from src.prompts import build_filter_constraint_block

    assert build_filter_constraint_block({"_court": "uksc"}) == ""


def test_the_override_is_gone_from_the_executor():
    """The defect itself. `_court` clobbering `params["court"]` after the model
    had chosen one is what made a stale filter beat live judgement."""
    from src.agent.tools import executor

    source = inspect.getsource(executor)
    # Asserted on the CODE, not on the word: the comment above the removal site
    # names `_court` deliberately, so that a future reader adding it back sees
    # why it went.
    assert 'cl_cfg.get("_court")' not in source
    assert 'cl_cfg["_court"]' not in source


def test_the_model_keeps_its_own_court_parameter():
    """The capability, which must survive. Removing this too would be the
    obvious wrong reading of P4.4: the filter was redundant *because* the model
    already had this, not because narrowing by court is undesirable."""
    from src.agent.tools.schemas import get_worker_tools

    tools = get_worker_tools("case_law_only")
    search = next(
        t for t in tools if t["function"]["name"] == "search_case_law"
    )
    params = search["function"]["parameters"]["properties"]
    assert "court" in params
    assert "uksc" in params["court"]["description"]


def test_the_model_supplied_court_still_reaches_the_api():
    """The other half of the capability: the model's argument must still be
    passed through to the National Archives query."""
    from src.agent.tools import executor

    source = inspect.getsource(executor)
    assert 'params["court"] = args["court"]' in source


def test_the_audit_trace_keeps_court_as_a_permanent_null():
    """Shape stability for the external eval harness, as P1.2 did for
    `current_only`. A harness wanting the court should read the tool's `args`,
    where the model's own choice is recorded."""
    from src.utils.audit_trace import AuditCollector

    audit = AuditCollector("req1")
    event = audit.to_event(config={"_court": "uksc", "_jurisdiction": "scotland"},
                           timings={})
    assert "court" in event["filters"]
    assert event["filters"]["court"] is None
    assert event["filters"]["jurisdiction"] == "scotland"
