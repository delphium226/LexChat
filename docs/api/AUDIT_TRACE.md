# `/api/system/chat` — audit trace

Handover spec for the [lexchat-eval](https://github.com/tomwilsonsco/lexchat-eval) harness.

Two changes ship together: the endpoint now honours the full request body (it silently ignored most of it), and it emits a structured `audit` event so the harness no longer has to reconstruct the run by parsing UI events.

---

## Part 1 — the bug you found

You were right. `/api/system/chat` declared its own request model:

```python
class SystemChatRequest(BaseModel):
    messages: List[dict]
    model: str
    num_ctx: Optional[int] = None
```

and set only `_provider` on the request context. Everything else you sent — `chat_mode`, `research_mode`, every filter — was dropped by pydantic (no `extra="forbid"`, so unknown keys are discarded without error), and the agent fell through to its defaults: `legislation_only` + `research`, on every request, regardless of payload.

For the record it was **not** a pydantic-migration regression. `git log --follow` shows the file has imported `from pydantic import BaseModel` since the initial commit; the fields were simply never added. `/api/chat` grew filters, Deep Research, feature flags and cache keying over two years while this endpoint stayed frozen, because nothing in the app calls it. The spec line claiming "Same request shape as `/api/chat`" was wrong and has been corrected.

### What changed

`SystemChatRequest` now **subclasses** `ChatRequest`. Parity is structural rather than remembered — a field added to `/api/chat` is accepted here automatically, and a test asserts the set difference is empty. All three agent endpoints (`/api/chat`, `/api/system/chat`, `/api/research/plan`) now build their request context through one shared `build_request_config()`.

### What you can now audit

| | |
|---|---|
| `research_mode` | `legislation_only`, `case_law_only`, `legislation_and_case_law` — all selectable per request |
| `chat_mode` | `research`, `conversational`, `deep_research` |
| Filters | `jurisdiction`, `year_from`/`year_to`, `date_from`/`date_to`, `court`, `legislation_type`, `current_only` |
| Deep Research | `deep_research_plan` (see below) |
| Documents / matters | `chat_id` now loads document and matter context, as on `/api/chat` |

Two constraints worth knowing:

- **`RESEARCH_MODE` in the server's `.env` overrides the body absolutely.** On the legislation bot it is blank, so your body wins. On a parliament-bot process it is set and cannot be overridden — that's deliberate (its DB, tools and crawler are all mode-specific).
- **`parliamentary_records` / `westminster_records` need their own bot process.** They are not auditable against the legislation bot regardless of what you send, because the backing tables and API keys live in the other deployment.

### Deep Research is two-phase

This is why your Deep Research runs went nowhere. `/api/chat` and `/api/system/chat` **execute** an approved plan; they don't draft one.

```
POST /api/research/plan   → {"plan": {"scope_note": ..., "steps": [...]}}
                            (or {"needs_clarification": true, "question": ..., "options": [...]})
POST /api/system/chat     with chat_mode="deep_research" + deep_research_plan=<that plan>
```

Sending `chat_mode: "deep_research"` without a plan now returns **HTTP 400**. Previously it fell through and ran a normal research request — which your harness would have recorded as a successful Deep Research run. Worth checking whether any banked results were captured that way.

`/api/research/plan` is plain JSON, not SSE, and takes the same filter fields.

---

## Part 2 — the `audit` event

### Why

`audit_capture.py` currently rebuilds the run's structure from the UI event stream: a push/pop `tool_stack`, a `_pending_api_entries` list to pair `api_call_start` with `api_call_end`, and string matching against our display labels —

- `"Extracting the relevant sections from a large document"` (a UI label in `agent_shared.py`)
- `"Research Agent"` (a UI label in `agent_core.py`)
- `"[Research Agent Result]"` (an internal tool-result prefix)

— plus a retroactive-repair pass and a leftover flush for events that never arrive. It works, but it fails *silently* when we change a label: your numbers go quietly wrong rather than erroring.

**It is already broken for Deep Research.** Multi-step runs emit `f"Research Agent — Step {i}: {title}"`, and your checks are exact equality against `"Research Agent"`, so every Deep Research delegation currently falls through to the leftover-flush path and is recorded as `no_completion_event`.

The server already knows the structure — it was only rendering it for a human. Now it sends it.

### The event

One `audit` event per request, emitted immediately **before** `result` (so a consumer that stops reading at `result` has necessarily already seen it). Streaming events are unchanged and still flow — this is purely additive.

```jsonc
{
  "type": "audit",
  "schema_version": 1,
  "request_id": "a1b2c3d4",

  "chat_mode": "research",
  "research_mode": "case_law_only",
  "provider": "openrouter",
  "model": "google/gemini-2.0-flash",
  "summarisation_model": null,
  "filters": {
    "jurisdiction": null, "year_from": null, "year_to": null,
    "date_from": null, "date_to": null, "court": "UKSC",
    "legislation_type": null, "current_only": false,
    "record_type": null, "house": null, "sessions": null
  },

  "answer": "<final answer shown to the user>",
  "suggestions": ["<follow-up chip>", "..."],
  "sources": [{ "n": 1, "title": "...", "url": "...", "cite": "..." }],

  "delegations": [
    {
      "id": "d1f2a3b4",
      "kind": "delegation",          // or "deep_research_step"
      "step": null,                   // 1-based on deep_research_step
      "title": null,                  // approved step title on deep_research_step
      "brief": "<query the Manager sent the Worker>",
      "report": "<the Worker's research report>",
      "reformatted": false,           // A4 structure-repair retry fired
      "error": null,
      "started_at": 0.512,            // seconds from request start
      "duration_s": 41.8,
      "tools": [
        {
          "id": "9f8e7d6c",
          "name": "search_legislation_sections",
          "args": { "legislation_id": "ukpga/1985/68", "query": "..." },
          "raw_result": "<tool output BEFORE summarisation>",
          "final_result": "<what actually entered the Worker's context>",
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
              "request": { "...": "the payload we sent" },
              "status": 200,
              "response": { "...": "the parsed JSON we got back" },
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

  "timings": { "total_ms": 64210, "llm_calls": 7, "total_cost_usd": 0.184, "...": "..." },
  "error": null
}
```

Field notes:

- **`raw_result` vs `final_result`** — the retrieval as it came off the API, and the text the model actually saw. When `summarised` is `true` they differ. You currently only ever see the summarised text, so a bad summary and a bad retrieval look identical in your data; this separates them.
- **`api_calls` nest inside the tool that made them.** Nesting comes from the call graph, not from event ordering, so it stays correct if we ever parallelise worker runs.
- **`summarised`** is true for both a real summarisation call and a local-cache hit; `local_cache_hit` distinguishes them. `memo_hit` means an exact repeat within the same request was served from the per-request memo (no API call, no summarisation).
- **`budget_blocked`** (parliamentary modes only) means the model burned its 3-search discovery budget and the call was hard-stopped.
- **`error`** is set at whichever level failed. On a failed run the audit event is still emitted with whatever was gathered before the failure — a failed run is still an eval data point.
- **`schema_version`** — assert on it. It gets bumped on any breaking change to this shape.

### Controls

| Field | Default | |
|---|---|---|
| `audit` | `true` | set `false` to suppress the event |
| `audit_max_field_chars` | `0` (unlimited) | truncates `brief` / `report` / `raw_result` / `final_result`, appending `[audit: truncated N chars]` |

Raw results can run to several hundred KB. Unlimited is the right default for an audit; set a cap if the DuckDB rows get unwieldy.

---

## Part 3 — what to change in `lexchat-eval`

### `utils/audit_capture.py` — the big one

Almost all of it can go. Keep the SSE line-reading loop; replace everything after `data = json.loads(data_str)` with:

```python
if data.get("type") == "audit":
    audit = data
elif data.get("type") == "token":
    actual_output += data.get("content", "")
elif data.get("type") == "result":
    ...
elif data.get("type") == "error":
    ...
```

Then derive your existing dict from `audit`. Everything maps directly:

| Your field | From the trace |
|---|---|
| `actual_output` | `audit["answer"]` |
| `research_output` | `"\n\n".join(d["report"] for d in audit["delegations"])` — no `[Research Agent Result]` signature match, no retroactive repair |
| `tools_called` | flatten `delegations[].tools[]` → `{name, input_parameters: t["args"], output: t["final_result"]}` |
| `tool_sequence` | `[t["name"] for d in delegations for t in d["tools"]]` — correctly ordered, no `tool_stack` |
| `retrieval_context` | flatten `t["api_calls"][].response` (your existing per-shape extraction logic still applies, but you no longer have to guess which tool a response belonged to — `t["name"]` is right there) |
| `case_law_context` | same, filtered on `t["name"] == "search_case_law"` |
| `fallback_used` | `any(t["name"] == "get_legislation_text" for ...)` |
| `summarisation_used` | `any(t["summarised"] for ...)` — no label match |
| `summarisation_output` | `[t["final_result"] for t in ... if t["summarised"]]` |
| `is_error` / `error_message` | `audit["error"]` |

Delete: `tool_stack`, `_pending_api_entries`, `_in_summarisation`, the `"Extracting the relevant sections…"` and `"Research Agent"` string matches, the leftover flush, and the retroactive-repair block. The verbose logger can stay if you find it useful, but the trace is now self-describing enough that dumping the `audit` event to a file may serve better.

### `utils/lexchat_client.py`

No change needed.

### `gather_responses.py`

`audit_capture(..., research_mode=...)` already threads a mode through and puts it in the payload — that now actually takes effect, so re-gathering will produce genuinely different results for `case_law_only` and `legislation_and_case_law`. **Your existing banked responses for those two modes are all legislation-mode runs mislabelled**; they should be re-gathered rather than compared against new ones.

Also drop `"stream": True` from `chat_payload` — it was always ignored (streaming is unconditional), and once we add `extra="forbid"` it would 422.

### New capabilities worth adding

- **Deep Research suite** — call `/api/research/plan`, then execute. `delegations[].step` / `.title` give you per-step scoring against the approved plan, which is the interesting eval for that mode.
- **`conversational` mode** — now reachable, and a useful negative control (it should *not* delegate; `delegations` should be empty).
- **Retrieval-vs-summarisation attribution** — with `raw_result` you can score whether the summariser dropped something the retrieval actually contained. That's a metric you cannot compute today.
- **Cost/latency per delegation** — `duration_s` and `timings.total_cost_usd`.

### New DuckDB columns to consider

`chat_mode`, `provider`, `model`, `total_cost_usd`, `total_ms`, `reformatted`, `local_cache_hits`, `memo_hits`, `schema_version`.

---

## Part 4 — things to be aware of

- **Timing rows.** Every `/api/system/chat` run now writes a `request_timings` row tagged `source = "eval"`, so your sweeps show up in the Admin Portal → Efficiency and Cache tabs. The dashboards do **not** filter on `source` yet — a large eval sweep will move the headline numbers. If that becomes annoying, filtering is a one-line change to the stats queries.
- **No efficiency breach alerts.** Eval runs deliberately don't write `ActivityLog` EFFICIENCY rows; those are operator alerts about live behaviour and a sweep would flood the feed.
- **Caching affects repeat runs.** The local prompt cache is cross-user and keyed on `(raw tool output hash, canonicalised query hash)`, so re-running the same question skips summarisation and returns a cached summary. For clean A/B numbers either clear it (Admin Portal → Cache → "Clear local cache") or turn the flag off in the Developer tab. `local_cache_hit` in the trace tells you when it fired.
- **The model comes from the server, not your payload.** `/api/models` reports the active one; `resolved_model` in the trace records what actually ran. Your `model` field in the request is only a fallback.
- **Cost is real.** Each run is a full research request against the live LEX / National Archives APIs and a paid LLM.

## Reference

| | |
|---|---|
| Endpoint | `server_py/src/routers/system.py` |
| Shared request models + config builder | `server_py/src/routers/agent_request.py` |
| Trace implementation | `server_py/src/utils/audit_trace.py` |
| Tests | `server_py/tests/test_audit_trace.py` |
| API spec | `docs/api/ServerAPISpec.md` §4 |
