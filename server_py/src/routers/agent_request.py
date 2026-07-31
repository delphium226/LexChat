"""Shared request models and config building for the agent-driving endpoints.

Three endpoints drive the same agent pipeline — `/api/chat` (the app),
`/api/system/chat` (machine-to-machine / evaluation harnesses) and
`/api/research/plan` (Deep Research Phase A). Each one has to translate its
request body into the `_`-prefixed ContextVar keys the agent core reads.

That translation used to be copy-pasted into all three routers, and it drifted:
`/api/system/chat` was written against the original `/api/chat` body and never
grew `chat_mode`, `research_mode`, the filter set, Deep Research or the cache
keys. Because nothing in the app calls it, the gap was invisible until an
external harness tried to audit a non-default mode and silently got the
defaults (`legislation_only` / `research`) on every request.

So the shape is defined ONCE here:

* `AgentRequestBase` holds every field common to the three endpoints.
* `ChatRequest` adds the chat-mode / Deep Research fields; `/api/system/chat`
  imports it directly rather than declaring its own model, which makes that
  endpoint's field parity structural — it cannot drift again.
* `build_request_config` produces the full ContextVar dict for all three.

Adding a request field now means adding it in one place.
"""

from typing import List, Optional

from pydantic import BaseModel, Field

from ..config import settings


class ResearchPlanStep(BaseModel):
    """One approved Deep Research plan step (user-editable, so validated here)."""
    id: Optional[int] = None
    title: str = Field(..., min_length=1, max_length=500)
    detail: str = Field("", max_length=4000)


class DeepResearchPlan(BaseModel):
    """The approved plan sent back for execution. Each step is a full worker
    run (real cost), so the step count is hard-capped server-side."""
    scope_note: str = Field("", max_length=2000)
    steps: List[ResearchPlanStep] = Field(..., min_length=1, max_length=8)


class AgentRequestBase(BaseModel):
    """Fields common to every endpoint that drives the agent pipeline."""

    messages: List[dict]
    model: str
    num_ctx: Optional[int] = None
    research_mode: Optional[str] = "legislation_only"
    jurisdiction: Optional[str] = None
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    court: Optional[str] = None
    legislation_type: Optional[str] = None
    current_only: Optional[bool] = False
    # Parliamentary-mode filters (parliament / Westminster bots only).
    # record_type and sessions are shared fields whose vocabulary depends on the
    # bot's research mode: Holyrood record types + Sessions 1-7, or Westminster
    # record types + Parliament terms. `house` is Westminster-only (Holyrood is
    # unicameral) and is ignored by every other mode.
    record_type: Optional[str] = None
    sessions: Optional[List[int]] = None
    house: Optional[str] = None
    chat_id: Optional[int] = None


class ChatRequest(AgentRequestBase):
    """Body for `/api/chat` and `/api/system/chat`."""

    chat_mode: Optional[str] = "research"
    # Deep Research execution: the user-approved plan (chat_mode="deep_research")
    deep_research_plan: Optional[DeepResearchPlan] = None


class ResearchPlanRequest(AgentRequestBase):
    """Body for `/api/research/plan`. chat_mode is implicit (deep_research) and
    there is no plan yet — this endpoint is what produces one."""


def resolve_research_mode(body: AgentRequestBase) -> str:
    """Effective research mode: the bot's RESEARCH_MODE override wins, then the
    request body, then the legislation default.

    The env override is deliberately absolute — a parliament-bot process must
    not be talked into legislation mode by a request body, since its DB, tools
    and crawler are all mode-specific.
    """
    return settings.research_mode or body.research_mode or "legislation_only"


def build_request_config(
    body: AgentRequestBase,
    provider_config: dict,
    active_provider: str,
    features: dict,
    *,
    chat_mode: str,
    doc_context: str = "",
    matter_context: str = "",
) -> dict:
    """Build the per-request provider-config dict set on the ContextVar.

    `chat_mode` is passed explicitly rather than read off the body because
    `/api/research/plan` has no chat_mode field — planning is always
    deep_research.
    """
    research_mode = resolve_research_mode(body)

    return {
        **provider_config,
        "_provider": active_provider,
        "_chat_mode": chat_mode,
        "_research_mode": research_mode,
        "_jurisdiction": body.jurisdiction or None,
        "_year_from": body.year_from or None,
        "_year_to": body.year_to or None,
        "_date_from": body.date_from or None,
        "_date_to": body.date_to or None,
        "_court": body.court or None,
        "_legislation_type": body.legislation_type or None,
        "_current_only": body.current_only or False,
        # record_type is routed to the enforcement key matching this bot's
        # mode — the two taxonomies are disjoint, so a Holyrood value must
        # never reach the Westminster filter (or vice versa).
        "_pt_record_type": body.record_type if research_mode != "westminster_records" else None,
        "_wm_record_type": body.record_type if research_mode == "westminster_records" else None,
        "_wm_house": body.house or None,
        "_pt_sessions": body.sessions or None,
        "_doc_context": doc_context,
        "_matter_context": matter_context,
        # Local-cache key source (D8 Phase 5): in standard mode the cache
        # keys on the RAW user query, not the LLM-paraphrased delegation
        # brief (which varies per model/run and makes cross-user hits
        # luck). Deep Research must NOT set this — each step's approved
        # plan text is the right key; steps with different intents must
        # not collide.
        "_cache_key_query": (
            "" if chat_mode == "deep_research"
            else next(
                (m.get("content", "") for m in reversed(body.messages)
                 if m.get("role") == "user"),
                "",
            )
        ),
        "_prompt_caching_enabled": features.get("prompt_caching_enabled", True),
        "_tool_memo_enabled": features.get("tool_memo_enabled", True),
        "_local_prompt_cache_enabled": features.get("local_prompt_cache_enabled", True),
        "_suggested_questions_enabled": features.get("suggested_questions_enabled", True),
    }
