# `/api/system/chat` — request contract and audit trace

Integration reference for machine-to-machine consumers of the AILA agent pipeline, principally the [lexchat-eval](https://github.com/tomwilsonsco/lexchat-eval) evaluation harness.

Two changes are documented here: `/api/system/chat` now honours the full request body, and it emits a structured `audit` event describing the run. Both landed together in commit `da3070d`.

---

## 1. Purpose of the endpoint

`/api/system/chat` runs the same agent pipeline as `/api/chat`, with one functional difference: `emit_tool_details=True`. An evaluation harness has to observe what the agent *retrieved*, not only what it answered, and `/api/chat` does not emit `tool_call`, `api_call_start` or `api_call_end` events. That is the sole reason the endpoint exists, and the reason `/api/chat` is not a substitute for it.

---

## 2. Background: the request-parity defect

Prior to this change, `/api/system/chat` declared its own request model:

```python
class SystemChatRequest(BaseModel):
    messages: List[dict]
    model: str
    num_ctx: Optional[int] = None
```

and set only `_provider` on the request ContextVar. Every other field — `chat_mode`, `research_mode`, the entire filter set, Deep Research — was discarded. Pydantic ignores unknown keys unless `extra="forbid"` is configured, so a request carrying those fields was accepted without error and the agent fell through to its defaults: `legislation_only` and `research`, on every request, irrespective of payload.

This was not a regression introduced by a framework migration. The file has imported `from pydantic import BaseModel` since the initial commit; the fields were never present. `/api/chat` accumulated filters, Deep Research, feature flags and cache keying over two years while this endpoint remained frozen, and because no application code path calls it, the divergence produced no visible symptom. The previous API spec statement that `/api/system/chat` took the "same request shape as `/api/chat`" was inaccurate and has been corrected.

### Resolution

`SystemChatRequest` now subclasses `ChatRequest`. Field parity is structural rather than maintained by convention: a field added to `/api/chat` is accepted by `/api/system/chat` automatically, and `tests/test_audit_trace.py` asserts that the set difference between the two models is empty.

All three endpoints that drive the agent pipeline — `/api/chat`, `/api/system/chat` and `/api/research/plan` — now derive their request context from a single `build_request_config()` in `server_py/src/routers/agent_request.py`. The three near-duplicate copies of that translation, which permitted the original divergence, have been removed.

---

## 3. Request contract

`/api/system/chat` accepts the `/api/chat` body in full, plus two audit-only fields.

### Agent controls

| Field | Values | Notes |
|---|---|---|
| `research_mode` | `legislation_only`, `case_law_only`, `legislation_and_case_law`, `parliamentary_records`, `westminster_records` | Selectable per request |
| `chat_mode` | `research`, `conversational`, `deep_research` | |
| `deep_research_plan` | Approved plan object | Required when `chat_mode` is `deep_research` |
| `chat_id` | integer | Loads document and matter context, as on `/api/chat` |

### Filters

`jurisdiction`, `year_from`, `year_to`, `date_from`, `date_to`, `court`, `legislation_type`, and — in parliamentary modes — `record_type`, `sessions`, `house`.

**`current_only` was removed in September 2026 and is no longer a filter.** The control it belonged to excluded nothing: it tested the LEX `status` field for `repealed`/`revoked`/`spent`, but that field's vocabulary is `final` and `revised` only — it records which text version is held, not in-force status. There is no in-force signal anywhere in the tool surface, so the filter could not be repaired by extending the word list, and the UI and system prompt were both asserting currency on the strength of a check that never ran.

The request field is **accepted and ignored** rather than rejected: this model does not set `extra="forbid"`, so a client still sending `current_only` receives the same response it did before and the value goes nowhere. `filters.current_only` is still present in the audit event, **always `null`**, so the trace shape was unchanged and `schema_version` remained `1` at the time (it is `2` as of the v2 note below). Treat a `null` there as "this filter no longer exists", not as "the filter was off".

### Audit controls

| Field | Default | Purpose |
|---|---|---|
| `audit` | `true` | Emit the structured `audit` event |
| `audit_max_field_chars` | `0` | Truncate long strings in the trace; `0` disables truncation |

Raw tool results can reach several hundred kilobytes. No truncation is the appropriate default for an audit; a cap is available where payload size becomes impractical. Truncated values carry an `[audit: truncated N chars]` suffix so a truncated capture is distinguishable from a genuinely short one.

### Constraints on mode selection

- **The `RESEARCH_MODE` environment variable overrides the request body absolutely.** It is blank on the legislation bot, so the body governs. On a parliament-bot process it is set and cannot be overridden by a request — that process's database, tool set and crawler are all mode-specific.
- **`parliamentary_records` and `westminster_records` require their own bot process.** They are not exercisable against the legislation bot regardless of the request body, because the backing tables and API credentials belong to a separate deployment.

### Deep Research is a two-phase flow

`/api/chat` and `/api/system/chat` *execute* an approved plan; neither drafts one.

```
POST /api/research/plan   → {"plan": {"scope_note": ..., "steps": [...]}}
                            or {"needs_clarification": true, "question": ..., "options": [...]}

POST /api/system/chat     chat_mode="deep_research", deep_research_plan=<the plan>
```

`POST /api/research/plan` returns plain JSON rather than SSE and accepts the same filter fields.

Submitting `chat_mode: "deep_research"` without a plan now returns **HTTP 400**. Previously the request fell through and executed a standard research run, which a client checking only status codes would record as a successful Deep Research result. Any results captured under the previous behaviour should be treated as standard research runs.

---

## 4. The `audit` event

### Rationale

The SSE stream is built for a user interface: flat `tool_start` / `tool_end` / `api_call_start` / `api_call_end` events carrying human-readable labels. A machine consumer requiring the run's structure — which tool executed within which delegation, what each external API returned, and what the model saw after summarisation — must otherwise reconstruct it with a push/pop stack, correlate start and end events itself, and classify events by matching display strings such as `"Research Agent"`, `"Extracting the relevant sections from a large document"` and the `[Research Agent Result]` tool-result prefix.

That coupling fails silently. A label change produces incorrect consumer output rather than an error. It is also already incorrect for Deep Research, whose delegations are labelled `f"Research Agent — Step {i}: {title}"` and therefore do not match an exact-equality comparison against `"Research Agent"`.

The server holds this structure and previously discarded it at render time. The `audit` event preserves it.

### Delivery

One event per request, emitted immediately **before** `result`, so a consumer that stops reading at `result` has necessarily already received it. Existing streaming events are unchanged; the trace is purely additive.

### Schema

```jsonc
{
  "type": "audit",
  "schema_version": 3,
  "request_id": "a1b2c3d4",

  "chat_mode": "research",
  "research_mode": "case_law_only",
  "provider": "openrouter",
  "model": "google/gemini-2.0-flash",
  "summarisation_model": null,
  "filters": {
    "jurisdiction": null, "year_from": null, "year_to": null,
    "date_from": null, "date_to": null, "court": "UKSC",
    "legislation_type": null, "current_only": null,   // removed Sept 2026; always null
    "record_type": null, "house": null, "sessions": null
  },

  "answer": "<final answer returned to the user>",
  "suggestions": ["<follow-up question chip>"],
  "sources": [{ "n": 1, "title": "...", "url": "...", "cite": "..." }],

  "delegations": [
    {
      "id": "d1f2a3b4",
      "kind": "delegation",          // or "deep_research_step"
      "step": null,                   // 1-based on deep_research_step
      "title": null,                  // approved step title on deep_research_step
      "brief": "<query the Manager sent the Worker>",
      "report": "<the Worker's research report>",
      "reformatted": false,           // structure-repair retry fired
      "halted": null,                 // v2; {reason, limit, steps} at the step cap
      "error": null,
      "started_at": 0.512,            // seconds from request start
      "duration_s": 41.8,
      "tools": [
        {
          "id": "9f8e7d6c",
          "name": "search_legislation_sections",
          "args": { "legislation_id": "ukpga/1985/68", "query": "..." },
          "raw_result": "<tool output before summarisation>",
          "final_result": "<text that entered the Worker's context>",
          "summarised": true,
          "local_cache_hit": false,
          "memo_hit": false,
          "truncated": false,
          "budget_blocked": false,
          "started_at": 1.204,
          "duration_s": 8.9,
          "api_calls": [
            {
              "id": "c1",
              "url": "https://lex.lab.i.ai.gov.uk/legislation/section/search",
              "method": "POST",
              "request": { "...": "payload sent" },
              "status": 200,
              "response": { "...": "parsed JSON received" },
              "elapsed_ms": 412
            }
          ]
        }
      ]
    }
  ],

  "peer_consults": [
    { "peer_id": "parliament_bot", "peer_name": "...", "question": "...", "answer": "..." }
  ],

  // v3. Empty on a healthy request. One record per provider completion that
  // carried no content and no tool calls, whether or not the retry recovered.
  "empty_completions": [
    {
      "provider": "OpenRouter", "model": "google/gemini-3.1-pro-preview",
      "attempt": 1, "attempts_max": 3, "retried": true,
      "finish_reason": "stop", "native_finish_reason": null,
      "completion_tokens": 0, "reasoning_chars": 0, "stream_error": null,
      "sent_chars": 21421, "react_turn": 4
    }
  ],

  "timings": { "total_ms": 64210, "llm_calls": 7, "total_cost_usd": 0.184 },
  "error": null
}
```

### Field semantics

- **`raw_result` and `final_result`** hold the retrieval as returned by the external API and the text actually placed in the Worker's context respectively. Exposing both allows a defective summary to be distinguished from a defective retrieval — an attribution that post-summarisation text alone cannot support. ~~They differ whenever `summarised` is true.~~ **They also differ whenever the server appends a bracketed instruction block, which is independent of summarisation** (corrected 2026-09-15, FIX_PLAN P2.2). `final_result` is the concatenation of the (possibly summarised) retrieval and any of: the Phase-2 nudge, the citation-URL block (P1.6, summarised results only) and the `[SEARCH SCOPE …]` block (P2.2, on **every** `search_legislation` and `search_legislation_sections` result). A consumer diffing `raw_result` against `final_result` to detect summarisation loss must therefore key on the `summarised` flag, not on the texts being unequal — those two tools' results now always differ. Parse `final_result` with a JSON `raw_decode`, which stops at the end of the leading object and ignores the appended tail; a plain parse raises "Extra data" on exactly the calls that succeeded.
- **`api_calls` are nested within the tool that issued them.** Nesting derives from the server's call graph rather than from event ordering, so attribution remains correct if worker runs are parallelised in future.
- **`summarised`** is true for both a summarisation call and a local prompt-cache hit; **`local_cache_hit`** distinguishes the two. **`memo_hit`** indicates an exact repeat within the same request served from the per-request tool memo, incurring neither an API call nor summarisation.
- **`budget_blocked`** applies to parliamentary modes only, and indicates that the model exhausted its three-call discovery budget and the search was hard-stopped.
- **`error`** is populated at whichever level failed. A failed run still emits the audit event, carrying whatever was captured before the failure; a failed run remains a valid evaluation data point.
- **`halted`** *(v2)* is `null` unless the Worker's ReAct loop stopped at the step cap, in which case it is `{"reason": "step_cap", "limit": 20, "steps": 20}`. Before v2 the only signal was the literal string `[Research halted: exceeded N tool-call steps]` appearing in `report` — which was never reliable and is no longer present. Two reasons it was not reliable: the Manager's **own** loop can halt, producing no delegation at all (so no `report` to match on), and a halted worker's `report` is now replaced with a structured incompleteness statement. A halt is a first-class outcome and should be read from this field; `request_timings.max_turns_halted` remains the request-level flag.
- **`empty_completions`** *(v3)* records provider completions that returned no content **and** no tool calls. It is `[]` on a healthy request, and a non-empty list does **not** imply the request failed — `chat_loop` retries such a completion up to three times, and `retried: true` marks an attempt the retry then recovered from. The fields exist to separate four mechanisms that were previously indistinguishable in the data: the provider returned nothing (`completion_tokens` ~0); the model spent the completion on thinking tokens (`reasoning_chars` > 0); a mid-stream failure arrived as a payload the parser used to ignore (`stream_error` set, and/or `finish_reason: "error"` with the provider's own code in `native_finish_reason`); or the model chose to say nothing. A harness watching for lost answers should treat a record with `retried: false` as one — the answer for that call was empty on every attempt, and the caller fell back to labelled research output or a notice.
- **`schema_version`** is incremented on any change to this shape and should be asserted on by consumers. **v2** (Sept 2026) adds `delegations[].halted`; **v3** (Sept 2026) adds top-level `empty_completions[]`. Both are additive, so an older consumer sees an unknown key and is otherwise unaffected — and in v3's case a key that is almost always `[]`.

### Implementation

Recording sites are confined to the agent call graph:

| Concern | Site |
|---|---|
| Delegation scope | `run_worker_agent` — one delegation per worker run, correct for both a Manager `delegate_research` call and a Deep Research plan step |
| Tool records | `run_worker_tool`, which receives its delegation as an explicit argument rather than through a ContextVar, so nesting survives future parallelism |
| External API calls | Captured by wrapping the `on_chunk` callback within the owning tool's scope, which yields correct attribution without modifying the emission sites in `executor.py` |
| Deep Research step metadata | `run_deep_research` passes `step` and `title` via `set_next_delegation_meta()`; only that loop holds them |

The collector is held in a ContextVar that only `system.py` sets. Every recording site is therefore a null check, and `/api/chat` is unaffected. All collector methods suppress their own exceptions: a degraded trace is acceptable, a failed research run is not.

---

## 5. Consumer migration guidance

The following applies to any client currently reconstructing run structure from the SSE stream.

### Event handling

Retain the SSE line-reading loop. Replace the event dispatch with four cases: `audit` (capture the whole object), `token` (accumulate streamed content), `result` (final message) and `error`.

The following can then be removed entirely: the tool stack, the pending-API-call correlation list, the summarisation state flag, all display-label string comparisons, the end-of-stream leftover flush, and any retroactive-repair pass.

### Field derivation

| Consumer field | Derivation |
|---|---|
| Final answer | `audit["answer"]` |
| Research output | `"\n\n".join(d["report"] for d in audit["delegations"])` |
| Tools called | Flatten `delegations[].tools[]` → `{name, input_parameters: t["args"], output: t["final_result"]}` |
| Tool sequence | `[t["name"] for d in delegations for t in d["tools"]]` |
| Retrieval context | Flatten `t["api_calls"][].response`; existing per-response-shape extraction still applies, keyed off `t["name"]` rather than inferred |
| Case law context | As above, filtered to `t["name"] == "search_case_law"` |
| Fallback used | `any(t["name"] == "get_legislation_text" ...)` |
| Summarisation used | `any(t["summarised"] ...)` |
| Summarisation output | `[t["final_result"] for t in ... if t["summarised"]]` |
| Error state | `audit["error"]`, plus transport-level exceptions |

A client should fail loudly if no `audit` event is received, naming a server predating commit `da3070d` as the likely cause, rather than returning empty results.

### Data captured for the first time

- **Deep Research step attribution** — `delegations[].step` and `.title` support per-step scoring against the approved plan.
- **Retrieval-versus-summarisation attribution** — `raw_result` alongside `final_result` allows assessment of whether summarisation discarded material the retrieval contained.
- **Conversational mode** as a negative control: it should produce no delegations.
- **Per-delegation cost and latency** — `duration_s`, `timings.total_cost_usd`.

Fields worth persisting that were previously unavailable: `chat_mode`, `provider`, `model`, `total_cost_usd`, `total_ms`, `reformatted`, `local_cache_hit`, `memo_hit`, `schema_version`.

### Revalidation of existing results

Results captured before this change under `research_mode` values other than `legislation_only` were executed in legislation mode and labelled otherwise. They are not comparable with results captured after the change and should be regathered rather than reconciled.

---

## 6. Operational considerations

- **Timing rows.** Each `/api/system/chat` run now writes a `request_timings` row tagged `source = "eval"`; the endpoint previously wrote none. Evaluation runs therefore appear in the Admin Portal Efficiency and Cache tabs. **The dashboards do not yet filter on `source`**, so a large sweep will move the headline figures. Filtering is a small change to the stats queries if this becomes material.
- **No efficiency breach alerts.** Evaluation runs deliberately do not write `ActivityLog` EFFICIENCY rows. Those are operator alerts concerning live behaviour, and a sweep would saturate the activity feed.
- **Caching affects repeat runs.** The local prompt cache is cross-user and keyed on the raw tool output hash and canonicalised query hash, so re-running an identical question returns a cached summary and skips summarisation. For clean comparative measurements, clear it via Admin Portal → Cache → "Clear local cache" or disable the feature flag in the Developer tab. `local_cache_hit` in the trace indicates when it applied.
- **Model selection is server-side.** The active model is configured in the Admin Portal and reported by `/api/models`; the request's `model` field is a fallback only. `audit["model"]` records what actually executed.
- **Cost.** Every run is a full research request against the live LEX and National Archives APIs and a billed LLM provider.

---

## 7. Reference

| Component | Path |
|---|---|
| Endpoint | `server_py/src/routers/system.py` |
| Shared request models and config builder | `server_py/src/routers/agent_request.py` |
| Trace implementation | `server_py/src/utils/audit_trace.py` |
| Tests | `server_py/tests/test_audit_trace.py` |
| API specification | `docs/api/ServerAPISpec.md` §4 |
