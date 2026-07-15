# LexChat UK - Project Specification

## 1. Executive Summary
LexChat (product name **AILA — AI Legal Assistant**) is a specialised, locally-hosted AI legal research assistant for UK government legal departments. It uses a Manager-Worker agent architecture to provide precise, legally-grounded answers about UK legislation and case law. Sibling deployments (e.g. the Scottish Parliament bot) run the **same codebase** with different configuration, and bots can consult each other via **federation**. The system prioritises data privacy (local hosting), accuracy (LEX API + RAG), and continuous improvement (few-shot learning from user feedback).

## 2. Core Architecture

### 2.1 Technology Stack
-   **Frontend**: React 19 + Vite + Tailwind CSS. Pre-built on the dev machine and committed; served as static files by the FastAPI backend (no runtime Node.js, no separate web server).
-   **Backend**: Python 3.11 + FastAPI + uvicorn. PostgreSQL 15 for persistence. Async throughout (SQLAlchemy asyncpg, httpx, asyncio).
-   **AI Core**: dual LLM provider — **Ollama** (local process proxying cloud-hosted models) or **OpenRouter** (OpenAI-compatible API) — switchable at runtime via the Admin Portal; per-provider settings persisted in the DB.
-   **External Data**: **LEX API** (UK legislation), **National Archives** caselaw.nationalarchives.gov.uk (UK case law), and Scottish Parliament sources (TheyWorkForYou, SP Official Report crawler, SP Bills) for the parliament bot.
-   **Deployment**: native Windows Server 2022 (no Docker/WSL), HTTPS on port 443; git-pull update workflow.
-   **Multi-bot**: one shared `server_py/` codebase runs every bot; per-bot identity and config live in `bots/<id>/`. See the "Architecture: one codebase, many bots" section of the README.

### 2.2 Manager-Worker Agent System

Both agents share the same underlying ReAct (Reason + Act) loop. Two provider clients implement it — `ollama_client.py` and `openrouter_client.py` — over a shared tool-execution and summarisation pipeline in `agent_shared.py`; the active provider is resolved per request and carried through the call chain via a `ContextVar`. The two agents differ in their system prompts, toolsets, and position in the call chain.

#### The shared engine: `chat_loop`

`chat_loop` is a recursive async function. Each iteration:
1. Sends the current message history to the LLM and streams the response
2. If the model emits tool calls, executes them (concurrently via `asyncio.gather`)
3. Appends the tool results to the message history and recurses
4. When the model produces a plain text response with no tool calls, returns it

This loop is capped at 20 turns to prevent runaway recursion.

---

#### Step 1 — Request arrives at `POST /api/chat`

`routers/ai.py` receives the request, resolves the active LLM provider config from the database, and queues the request through a `RequestQueue` that enforces the configured `max_concurrent_requests` limit. Once a slot is free, `process_user_request()` is called — the Manager's entry point.

---

#### Step 2 — Manager Agent (`process_user_request`)

**Toolset:** one tool — `delegate_research`

**What it does:**

Before calling the LLM, the learning system (`agent/learning.py`) runs a keyword search against past user feedback stored in the database. If relevant high- or low-rated examples are found, they are injected into the Manager's system prompt as guidance for this query.

The Manager then receives the full conversation history and decides:

- **Conversational input** — responds directly without delegating
- **Ambiguous legal query** — asks a clarifying question (e.g. "which Act are you referring to?") before delegating
- **Clear legal query** — constructs a self-contained research brief and calls `delegate_research`

The research brief is deliberately richer than the user's raw message. The Manager is instructed to include the precise legal question, any Act names or SI numbers mentioned anywhere in the conversation, jurisdiction constraints, and context from prior turns. The Worker has no access to conversation history, so the brief must stand alone.

The Manager streams its tokens to the client in real time. When it calls `delegate_research`, streaming pauses and control passes to the Worker.

---

#### Step 3 — The handoff

The Manager's `delegate_research` call is intercepted by `manager_tool_executor` in `ollama_client.py`. This emits a `tool_start` SSE event (the UI shows a "Research Agent" status indicator), then calls `run_worker_agent()` with the constructed query. When the Worker returns, a `tool_end` event is emitted and the result is injected back into the Manager's conversation as a `tool` message: `"[Research Agent Result]\n{content}"`.

The Manager then composes its final reply around that result, preserving all citations and URLs.

---

#### Step 4 — Worker Agent (`run_worker_agent`)

**Toolset (varies by `research_mode`, wired in `tools/schemas.py::get_worker_tools`):** the legislation bot uses `search_legislation`, `search_legislation_sections`, `get_legislation_text`; case-law mode adds/swaps `search_case_law` and `get_case_law_text`; the parliament bot uses the Scottish Parliament tool set (`search_scottish_plenary`, `get_scottish_plenary_debate`, `search_scottish_committee_transcripts`, `get_scottish_committee_transcript`, `search_scottish_parliament`, `get_member_info`, `search_bills`). The five-phase process below describes the **legislation** flow; the parliament flow is analogous (discover → retrieve verbatim transcript → synthesise) and is detailed in `CLAUDE.md`.

The Worker starts with a fresh message history (system prompt + the research brief only). It follows a prescribed five-phase research process:

| Phase | Action |
|---|---|
| 1 — Discover | Call `search_legislation` to map Act names to `legislation_id`s. All Phase 1 searches are batched into a single turn and executed in parallel. Results are metadata only — title, id, url, status, year, extent. |
| 2 — Retrieve Provisions | For each `legislation_id`, call `search_legislation_sections` with a query targeting the specific provision needed. Batched and parallel. This is the primary retrieval step — it returns only matching sections rather than the full Act. |
| 3 — Fallback | Call `get_legislation_text` only if Phase 2 returns nothing useful, or if the question genuinely requires the full Act structure. |
| 4 — Iterate | If results are sparse, retry Phase 2 with alternative search terms before concluding nothing exists. |
| 5 — Synthesise | Compose a structured markdown answer: BLUF summary, detailed analysis, jurisdiction and status, references with legislation.gov.uk URLs. |

The Worker does **not** stream tokens to the client — its intermediate reasoning is not shown to the user.

A nudge is appended to every Phase 1 result to prevent the Worker from stopping early: after the tool result is processed, a `[NEXT STEP: Call search_legislation_sections...]` instruction listing the retrieved `legislation_id`s is appended to what the model sees. This ensures Phase 2 always follows Phase 1.

---

#### Step 5 — Summarisation pipeline

Large tool results are summarised before being fed back to the model. The threshold is **8,000 chars** — below this the raw result is passed through unchanged.

Above the threshold, the result is sent to the LLM with a focused prompt: retain only the sections, provisions, definitions, and legal thresholds relevant to the research question; discard preamble and unrelated schedules. This produces a query-focused extract rather than a raw compression.

For very large results (> 150,000 chars), the text is split into chunks, each summarised independently, then combined. If the combined summaries are still large, one final consolidation pass is run.

Summarisation calls are serialised by a semaphore (`max_summarise_concurrency`, default 1) to avoid overwhelming the LLM endpoint with multiple large-context inference jobs simultaneously.

**Key design point:** summarisation is a quality decision, not just a size decision. A 50k char section result focused down to 7k chars of query-relevant provisions is *better* input for the Worker's synthesis step than the raw 50k, regardless of whether the model could technically hold the larger payload.

---

#### What the logs look like for a typical complex query

```
Manager turn 1    — triages query, calls delegate_research
Worker starts     — receives self-contained research brief
Worker turn 1     — 8-11 parallel search_legislation calls (Phase 1)
                    results arrive at 9-16k chars each
                    → summarisation triggered per result (serialised, ~30-45s each)
Worker turn 2     — 9-11 parallel search_legislation_sections calls (Phase 2)
                    results arrive at 20-53k chars each
                    → summarisation triggered per result
Worker turn 3     — synthesises answer from summarised section text
Manager turn 2    — presents findings to user, preserves all citations
```

Total elapsed for a complex multi-Act query is typically 5–12 minutes, dominated by the serialised summarisation calls.

---

#### Key design decisions

| Decision | Rationale |
|---|---|
| Worker has no conversation history | Forces the Manager to craft a complete brief; prevents the Worker from hallucinating context it hasn't been given |
| Worker does not stream | Its output is intermediate research reasoning — only the Manager's polished answer is shown to the user |
| Phase 2 nudge appended after summarisation | Ensures the navigation hint survives the summarisation step and is visible in the message the model reasons over |
| Tool results capped after summarisation | Hard ceiling of `summarise_threshold + 4,000` chars (default ~12K) applied after summarisation, to prevent context-window overflow regardless of summarisation outcome |
| Parallel tool execution within a turn | All tool calls in a single turn run via `asyncio.gather` — important when the Worker issues 8–11 searches simultaneously |
| Summarisation serialised | The cloud-routed LLM endpoint cannot reliably handle concurrent large-context inference jobs; the semaphore prevents HTTP 500s |

## 3. Key Features

### 3.1 Legal Research Engine
-   **Deep Research**: iterative, multi-phase retrieval over the LEX API (Act discovery → section-level retrieval → full-text fallback), with query-focused summarisation of large results. No web scraping — the former `google-sr`/`web_search`/`deep_research` web-search path has been removed.
-   **LEX API Integration**: direct retrieval of UK statutes; **case-law mode** retrieves judgments from the National Archives (Atom search + LegalDocML/AKN full text).
-   **Parliamentary research** (parliament bot): full-text search and verbatim retrieval of Scottish Parliament plenary and committee transcripts, backed by a local crawler-populated DB.
-   **Federation**: when peers are registered, the Manager gains a `consult_peer` tool to ask a sibling bot (e.g. legislation ↔ parliament) via `POST /api/consult`.
-   **Strict Citation**: all answers must include URLs to `legislation.gov.uk`, official case-law repositories, or parliament.scot.
-   **Document upload**: users can attach PDFs/DOCX to a chat; extracted text is injected as context.

### 3.2 Self-Improvement (Learning Mode)
-   **Feedback Loop**: Users rate answers (1-5 stars) and add comments.
-   **RAG Injection**:
    -   **Positive Memory**: High-rated Q&A pairs are injected as "Gold Standard" examples for similar future queries.
    -   **Negative Memory**: Low-rated comments are injected as "Warnings" to avoid repeating mistakes.

### 3.3 Security & Administration
-   **Auth**: JWT-based authentication with bcrypt password hashing.
-   **Admin Portal** (admin user only):
    -   User management.
    -   **Usage / Performance / Cost analytics**: query volume, latency, and per-query cost tracking.
    -   **Activity Log**: unified feed of logins, queries, feedback, surveys, and service-health errors.
    -   **Developer tab**: LLM provider/model configuration (both providers), synthetic-data generation, danger-zone data wipe.
    -   **Federation tab**: peer-registry CRUD (`api_key` write-only, never returned).

## 4. Deployment & Infrastructure
-   **Target Environment**: Windows Server 2022, internet-restricted (whitelist-only outbound), no Docker/WSL — everything runs natively. HTTPS on port 443 with organisational certs.
-   **Automation**: PowerShell scripts (`deployment/install_native_offline.ps1`, `start_native.cmd`/`stop_native.cmd`); offline wheel bundle for air-gapped install.
-   **Updates**: the target does a `git pull` from `origin/main` — the frontend is pre-built and committed (`client/dist/`); there is no zip/file-transfer deployment.

## 5. Future Roadmap
-   **Barrister Agent**: a third tier for specialised court strategy.
-   **Voice Mode**: speech-to-text input.
-   **Semantic (embedding) retrieval** for the parliament bot — currently **deferred/NO-GO** (FTS-only hit-rate + cheap OR-fallback/reformulation wins proved sufficient; see `docs/parliament/SEMANTIC_RETRIEVAL_PLAN.md`).

*(Delivered since the original draft: dual-provider support, case-law mode, the Scottish Parliament bot + federation, document upload, and the Matters workspace.)*
