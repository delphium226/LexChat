# Deep Research Mode — Implementation Plan (handoff)

**Status:** Not started. This is a build spec for a fresh session.
**Author of spec:** design session 2026-07-16.
**Scope:** Add a new **Deep Research** chat mode that drafts an editable research plan,
lets the user add/remove/reorder/edit steps, and — on approval — executes the plan
autonomously and synthesises a report. This is the **L2** design agreed in discussion
(plan → approve → run-to-completion). **L3 (pause-and-review between every step) is
explicitly OUT of scope.**

---

## 1. Context you need before starting

Read these first — the design leans on how they already work:

- **`server_py/src/agent/agent_core.py`** — the provider-agnostic orchestration. `run_worker_agent(...)`
  and `process_user_request(...)` are already parameterised by injected `chat_loop_fn` /
  `run_worker_agent_fn` / `summarise_chunk_fn`. **This is the seam we extend** — Deep Research is a
  new orchestration alongside the existing two, not a fork of the provider clients.
- **`server_py/src/agent/ollama_client.py` / `openrouter_client.py`** — thin per-provider wrappers that
  bind their wire-format `chat_loop` into `agent_core`. Each has its own `chat_loop` + `run_worker_agent`.
  **`chat_loop` is duplicated across the two** — so keep Deep Research logic in `agent_core` (single
  source); only add small binding wrappers in each client.
- **`server_py/src/agent/provider_factory.py`** — resolves the active provider and exposes bound
  functions via a `ContextVar` (`get_process_user_request_from_context()` etc.). We add equivalents for
  the planner and executor.
- **`server_py/src/routers/ai.py`** — `POST /api/chat`: SSE streaming, request queue, disconnect watch,
  `TimingCollector`, efficiency persistence. **Execution reuses this endpoint**; planning gets a new,
  simpler JSON endpoint.
- **`server_py/src/prompts.py`** — all system prompts + `get_manager_system_prompt` /
  `get_worker_system_prompt` (mode-aware: `legislation_only` / `case_law_only` /
  `legislation_and_case_law` / `parliamentary_records`, and `_chat_mode` = `research` / `conversational`).
- **`server_py/src/models.py`** — `Chat`, `Message` (note `Message.sources` is already `JSON`; ratings
  drive the learning mechanism). `RequestTiming` holds efficiency metrics.
- **`server_py/src/utils/stopwatch.py`** — `TimingCollector` with `to_dict()`; collects delegations,
  phase counts, distinct-retrieved, cost, etc.
- **`client/src/services/api.js`** — `sendMessage(...)` builds the `/api/chat` body and parses SSE
  (`timing` → captured, `result` → resolve, else → `onUpdate`).
- **`client/src/App.jsx`** — chat UI + mode selector. `chatMode` (`research`/`conversational`) and
  `researchMode` come from `usePreferences`; changes persist via `updatePreferences({chat_mode})` /
  `updatePreferences({research_mode})`. Mode selector rendering is around lines 348 / 511 / 681.
- **`docs/frontend/design-system.md`** — **read before writing any UI.** Use design tokens
  (`bg-brand` for primary CTAs, `bg-accent` only for focus/active, `text-ink-*`, `font-ui`). Do not use
  raw Tailwind palette classes.

**Users:** qualified UK government lawyers. High-stakes, audit-sensitive. The plan step is a feature
*because* it makes research steerable and the approved plan is a defensible artifact.

**Provider note:** everything must work for **both** Ollama and OpenRouter (bind both `chat_loop`s).
For local dev/testing use OpenRouter + a fast model (e.g. Gemini Flash) — it's quicker to iterate.

---

## 2. The flow (two-phase request cycle)

```
User (Deep Research mode) types a query
        │
        ▼
[Phase A: PLAN]  POST /api/research/plan   (JSON, non-streaming)
        │        → Planner agent drafts a structured plan
        │          (or asks ONE clarifying question if ambiguous)
        ▼
Frontend renders editable Plan card
   • edit step text   • delete step   • add step   • reorder
   • [Run research] (primary)   • [Cancel] (secondary)
        │
        ▼  (user approves)
[Phase B: EXECUTE]  POST /api/chat  (SSE, existing endpoint)
        │            body includes chat_mode="deep_research" + approved plan
        │            → run_deep_research orchestrator:
        │                for each approved step → run_worker_agent(step brief)
        │                dedup sources across steps
        │                final synthesis LLM call → integrated report
        ▼
Streamed progress (per-step tool_start/tool_end) → final result + sources
        │
        ▼
Persist approved plan on the Message (audit)
```

**Why code-orchestrated execution (recommended), not prompt-driven:** have `run_deep_research` loop
over the approved steps **in Python**, calling `run_worker_agent` once per step, then a single synthesis
call. Do **not** rely on the Manager LLM choosing to call `delegate_research` N times — that depends on
the model obeying and breaks the 1:1 mapping between approved steps and work done. Code orchestration is
deterministic, auditable (each step → one worker run → its sources), and matches the approved plan
exactly. This is the single most important design decision in this doc.

---

## 3. Backend changes

### 3.1 New chat mode
- Treat **`chat_mode = "deep_research"`** as a third value alongside `research` / `conversational`.
  It flows through the existing `_chat_mode` ContextVar (set in `ai.py` from `body.chat_mode`).
- `research_mode` is orthogonal and unchanged — Deep Research works across `legislation_only`,
  `case_law_only`, `legislation_and_case_law`, and (if desired) `parliamentary_records`.

### 3.2 Planner agent — `agent_core.draft_research_plan(...)`
Signature mirrors the injected-function pattern:
```python
async def draft_research_plan(
    chat_loop_fn, messages, model, cancel_event, num_ctx,
    timing_collector=None,
) -> dict:
    """Return {"plan": {"scope_note": str, "steps": [{"id","title","detail"}]}}
       OR {"needs_clarification": True, "question": str}."""
```
- Build a planner-only tool list (`get_planner_tools()` in `schemas.py`) with **two** tools:
  - `submit_research_plan(scope_note, steps)` — `steps` is an array of `{title, detail}`
    (domain/legal terms, e.g. *"Identify the primary Act(s) governing X and their key provisions"*,
    *"Check commencement and any amendments to s.42"*, *"Find case law interpreting the s.42 duty"*).
    2–6 steps. The tool executor **captures** the structured plan and signals completion.
  - `request_clarification(question)` — a single neutral clarifying question when the query is
    ambiguous (mirrors the existing "clarify without speculation" rule in the manager prompts).
- The planner has **no research tools** — it cannot search; it only plans. This keeps Phase A fast/cheap.
- Use `get_planner_system_prompt(research_mode, cfg)` (new, in `prompts.py`) — mode-aware and reusing
  `build_filter_constraint_block` / `build_parliament_filter_constraint_block` so active filters
  (jurisdiction, year, court, record_type) are reflected in the plan.
- Run via the injected `chat_loop_fn` with the planner tools + a tiny executor that stores the
  `submit_research_plan` / `request_clarification` payload and returns a terminating message.

### 3.3 Executor — `agent_core.run_deep_research(...)`
```python
async def run_deep_research(
    chat_loop_fn, run_worker_agent_fn, approved_plan, messages, model,
    on_chunk, cancel_event, num_ctx, db_session=None,
    emit_tool_details=False, timing_collector=None,
) -> dict:
```
- Loop over `approved_plan["steps"]`. For each step:
  - Construct a **self-contained worker brief** from the step `title`+`detail` plus any global context
    (Act names/identifiers mentioned in the conversation, active filters). Reuse the brief-construction
    discipline from `MANAGER_SYSTEM_PROMPT` ("NO SPECULATION" — pass identifiers verbatim).
  - Emit `tool_start` / `tool_end` events (type as `"Research Agent — Step N: {title}"`) so the existing
    frontend progress UI shows per-step activity.
  - Call `run_worker_agent_fn(step_brief, ...)`; collect `result["content"]` + `result["sources"]`.
  - Dedup sources across steps using the existing `_is_duplicate_source` helper in `agent_core.py`.
- After all steps: one **synthesis** `chat_loop_fn` call (no tools) with a
  `DEEP_RESEARCH_SYNTHESIS_PROMPT` that takes the per-step findings and composes an integrated report
  in the same house structure the worker prompts already use (Summary/BLUF → Analysis → Jurisdiction &
  Status → **References** — never drop References). Attach the deduped `sources`.
- Respect `cancel_event` between steps (client disconnect / abort).

### 3.4 Provider binding
- In `ollama_client.py` and `openrouter_client.py`, add thin wrappers binding their `chat_loop` (and
  `run_worker_agent`) into `draft_research_plan` and `run_deep_research`, mirroring how
  `run_worker_agent` / `process_user_request` are already bound.
- In `provider_factory.py`, add `get_draft_research_plan_from_context()` and
  `get_run_deep_research_from_context()` (resolve from the active-provider ContextVar, same pattern as
  `get_process_user_request_from_context`).

### 3.5 Routers
- **New: `POST /api/research/plan`** (put in `routers/ai.py` or a new `routers/research.py`).
  - Auth: `Depends(get_current_user)` — **required** (see the auth-hardening history: every route needs
    an explicit dependency; there is no global middleware).
  - Request body: reuse `ChatRequest`-style fields (`messages`, `model`, `research_mode`, filters,
    `chat_id`). Resolve provider config + `set_request_provider_config` exactly like `/api/chat`, set
    `_chat_mode="deep_research"`, then call the bound `draft_research_plan`.
  - Response: **plain JSON** (not SSE) — `{"plan": {...}}` or `{"needs_clarification": true, "question": ...}`.
    Planning is quick; no need for streaming/queue.
- **Extend: `POST /api/chat`** for execution.
  - Add optional `deep_research_plan: Optional[list[dict]]` to `ChatRequest`.
  - When `chat_mode == "deep_research"` **and** `deep_research_plan` is present, dispatch to
    `run_deep_research` (via a new `get_run_deep_research_from_context()`), instead of
    `process_user_request`. Everything else (SSE, queue, `TimingCollector`, efficiency persistence,
    disconnect handling) is reused unchanged.
  - Persist the approved plan (see 3.6).

### 3.6 Persistence (audit)
- Add a nullable **`research_plan JSON`** column to `Message` (additive; follow the existing
  `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` migration pattern used elsewhere — check how the schema is
  created/migrated on startup and match it). Store the **approved** plan on the assistant result message
  (or the user message — pick one and be consistent). This gives "here is the plan the lawyer approved"
  for compliance.

### 3.7 Prompts (`prompts.py`)
- `PLANNER_SYSTEM_PROMPT` (+ a `get_planner_system_prompt(research_mode, cfg)` builder). Key instructions:
  - Draft a plan of **2–6 steps** as scoped legal sub-questions in **domain terms**, not tool names.
  - Respect active filters (jurisdiction/year/court/record_type) — reuse the constraint blocks.
  - **No speculation** — do not invent case names/holdings from parametric knowledge (reuse the existing
    NO-SPECULATION wording). If the query is ambiguous, call `request_clarification` with ONE neutral
    question instead of guessing.
  - Mode-tailored: legislation-only plans focus on Acts/provisions; case-law plans on issues/authorities;
    hybrid on both; parliamentary on Holyrood plenary/committee/written-answer angles.
- `DEEP_RESEARCH_SYNTHESIS_PROMPT` — compose an integrated report from per-step findings; preserve the
  worker's section structure and the mandatory References list; pass through citations verbatim.

### 3.8 Efficiency / metrics
- Deep Research legitimately issues **N worker runs per request** (one per step). The existing
  per-request efficiency breach rules assume ~1 delegation — so a Deep Research request will look like a
  breach under the current thresholds.
  - Record `chat_mode` on `RequestTiming` (additive column, like `research_mode` already is) so the
    efficiency view can segment Deep Research from standard.
  - Make `evaluate_efficiency_breaches` skip (or use a separate profile for) `chat_mode == "deep_research"`
    — do not fire delegation/fan-out breaches for a mode that is *designed* to fan out. Check
    `config.py` `EFFICIENCY_PROFILES` / `evaluate_efficiency_breaches` and add a deep-research carve-out.
- Ensure the planner LLM call is timed/costed (pass the `TimingCollector` through the plan endpoint, or
  at minimum record its cost).

---

## 4. Frontend changes

### 4.1 Mode selector (`App.jsx`)
- Add **"Deep Research"** as a third option wherever `chatMode` is chosen (near the existing
  Conversational/Research control, ~line 348/511). Persist via `updatePreferences({ chat_mode: 'deep_research' })`.
- Standard `research` / `conversational` behaviour must be **completely unchanged** when Deep Research is
  off. Deep Research is opt-in; do not add a plan step to the other modes.

### 4.2 API layer (`services/api.js`)
- Add `getResearchPlan(messages, model, research_mode, filters, signal)` → `POST /api/research/plan`,
  returns the JSON plan (or clarification object).
- Extend `sendMessage(...)` with an optional `deep_research_plan` argument, added to the `/api/chat` body.

### 4.3 New component `components/DeepResearchPlan.jsx`
- Renders the editable plan: an ordered list of steps, each with editable `title`/`detail`, a delete
  button, an "add step" control, and reorder (up/down or drag). A `scope_note` header. Primary
  **"Run research"** and secondary **"Cancel"** buttons.
- **Use design tokens only** (see `docs/frontend/design-system.md`): primary button `bg-brand
  hover:bg-brand-hover text-white font-ui ...`; secondary `bg-paper border border-ink-200 ...`; icon
  buttons per the icon spec. `font-ui` for chrome. No raw palette classes.

### 4.4 Chat flow state machine
- When in Deep Research mode and the user submits: `idle → planning` (call `getResearchPlan`, show a
  spinner/skeleton) → render outcome:
  - `needs_clarification` → render the question as an assistant turn; the user's next message re-triggers
    planning with the added context.
  - `plan` → `plan_review`: render `DeepResearchPlan`. On **Run research**, transition to `executing`:
    call `sendMessage(..., chat_mode='deep_research', deep_research_plan=approvedSteps)` and stream
    progress via the existing `onUpdate` path (per-step `tool_start`/`tool_end` already supported) →
    `done` renders the final report + sources like a normal answer.
  - **Cancel** → back to `idle`, discard the plan.

---

## 5. Out of scope (do NOT build now)
- **L3** step-by-step execution with review/course-correction between each step (stateful resumable
  worker). Excluded by design decision.
- The **offline evaluation harness** (separate track). Note only: once Deep Research exists, "plan-first"
  becomes one of the strategy plugins that harness can A/B against the baseline. Don't build it here.
- Any change to the parliament bot beyond making the planner mode-aware (parliamentary Deep Research is a
  nice-to-have; ship legislation/case-law first).

---

## 6. Suggested implementation order
1. **Prompts + schemas**: `PLANNER_SYSTEM_PROMPT`, `get_planner_system_prompt`, `submit_research_plan` /
   `request_clarification` tools, `get_planner_tools()`. (Pure additions, no wiring.)
2. **Planner core + binding**: `draft_research_plan` in `agent_core`; bind in both clients; expose via
   `provider_factory`. Unit-test it returns a structured plan / clarification for sample queries.
3. **Plan endpoint**: `POST /api/research/plan`. Test with curl against local OpenRouter.
4. **Executor core + binding**: `run_deep_research` (code-orchestrated loop + synthesis); bind + expose.
   Unit-test the step loop and source dedup with a stubbed `run_worker_agent_fn`.
5. **Execution wiring**: `deep_research_plan` on `ChatRequest`; dispatch in `/api/chat`; persist plan
   column; efficiency carve-out + `chat_mode` on `RequestTiming`.
6. **Frontend**: mode option → `getResearchPlan` → `DeepResearchPlan` card → approve → execute → render.
7. **End-to-end verify** (see §7), then build + commit + push (see §8).

Each of 1–5 is independently testable; land them in that order so the backend is provable before any UI.

---

## 7. Testing / verification
- **Backend unit tests** (match the existing `server_py` test suite — currently green): planner output
  shape; clarification path; executor step-loop + dedup with a stubbed worker.
- **Manual E2E** on local dev (HTTP :8000, OpenRouter + fast model):
  1. Toggle Deep Research. Submit a genuinely multi-part query (e.g. a compulsory-purchase question
     touching procedure + compensation + a definition + relevant case law).
  2. Confirm a sensible 3–5 step plan renders; edit a step, delete one, add one, reorder.
  3. Run; confirm per-step progress streams, the final report integrates all steps, References is present,
     and sources are deduped.
  4. Confirm the approved plan is persisted (query the `messages.research_plan` column).
  5. Confirm an ambiguous query yields a single clarifying question, not a hallucinated plan.
  6. Confirm standard `research`/`conversational` modes are byte-for-byte unchanged.
- Use the `/verify` skill if available; drive the real app, not just tests.

## 8. Build & deploy (from `CLAUDE.md`)
- Frontend: `npm run build` in `client/` (portable Node on PATH — see `CLAUDE.md` dev setup), then
  **force-add** `client/dist/` (it's gitignored): `git add -f client/dist/`.
- Commit code **and** built `dist` together; push to `origin main`. The target only sees pushed commits.
- Branch first if on `main`. Do not commit/push unless the user asks.

## 9. Open decisions (defaults chosen — confirm with user if they matter)
- **Execution = code-orchestrated loop** (recommended in §2). If the user prefers prompt-driven Manager
  delegation, that's a different, less deterministic build — flag before starting.
- **Plan storage on `Message`** (additive JSON column) vs a dedicated `ResearchPlan` table. Column is
  simpler and matches their additive-migration habit; use it unless multi-plan-per-chat history is wanted.
- **Clarifying-question step included** (cheap, fits the existing "clarify before delegating" rule). Drop
  it if the user wants planning to always produce a plan.
- **Parliamentary Deep Research**: planner is mode-aware so it's mostly free, but validate separately;
  ship legislation/case-law first.
```
