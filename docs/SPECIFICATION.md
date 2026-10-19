# AILA — Product Specification

*The repository and its directories are still named LexChat for historical reasons; the product is
AILA. Last updated 13 October 2026, for release 2026.10.4.*

## 1. Executive Summary
AILA (AI Legal Assistant) is an AI legal research assistant for UK government legal departments,
built as a proof of concept. Its users are qualified legal professionals researching UK legislation, case law and
parliamentary proceedings. It uses a Manager-Worker agent architecture: the Manager holds the
conversation, and a Worker performs the research against official sources and writes it up with
citations.

AILA is a **fleet of three bots run from one codebase**, differentiated by configuration only:

| Bot | Identity | Research sources |
|---|---|---|
| Legislation | **AILA** | The LEX index of UK legislation, legislation.gov.uk's own records (read through LEX), the National Archives' Find Case Law, and Scottish judgments from the Scottish Courts and Tribunals Service (built, switched off until the network allows it) |
| Scottish Parliament | **ParliChat** | The Holyrood Official Report (plenary and committee, crawled into a local full-text database), TheyWorkForYou, the Scottish Parliament Bills API, SP TV |
| UK Parliament | **HansardChat** | The UK Parliament Hansard, Members and Bills APIs, searched live |

Bots can consult each other through **federation**. The system prioritises:
- **Grounded answers** — every substantive answer is built from retrieved text and cited, with
  provision links checked in code against what was actually retrieved.
- **Honest disclosure of limits** — what was searched, what the indexes do not hold, and what a
  record does or does not establish (in-force status above all) are stated in code-written text, not
  left to the model.
- **Data handling** — the application, its databases and chat history are self-hosted; the LLM is an
  external service configured by administrators, and users acknowledge a pre-use notice about what may
  not be entered.
- **Measured improvement** — the product is improved against a frozen analysis of the pre-pilot
  (August 2026) and released in calendar-versioned cuts (section 4.3).

## 2. Core Architecture

### 2.1 Technology Stack
-   **Frontend**: React 19 + Vite + Tailwind CSS. Pre-built on the dev machine and committed; served as static files by the FastAPI backend (no runtime Node.js, no separate web server). Branding is fetched at load (`GET /api/bot-info`, `GET /api/bot/logo`), so one bundle serves every bot.
-   **Backend**: Python 3.11 + FastAPI + uvicorn. PostgreSQL 15 for persistence, one database per bot. Async throughout (SQLAlchemy asyncpg, httpx, asyncio).
-   **AI Core**: dual LLM provider — **Ollama** (local process proxying cloud-hosted models) or **OpenRouter** (OpenAI-compatible API) — switchable at runtime via the Admin Portal; per-provider settings (model, optional separate summarisation model, temperature, concurrency) persisted in the DB.
-   **External Data**:
    -   *Legislation bot*: the **LEX API** (i.AI's search service over legislation.gov.uk data: search, section search, text, lookup, and amendment relations), and legislation.gov.uk's own records (commencement dates, made and enacted texts, instrument preambles) read through LEX's proxy endpoint; the **National Archives** Find Case Law feed; the **Scottish Courts and Tribunals Service** judgments search, behind a feature flag that is off.
    -   *Parliament bot*: the SP Official Report (crawled), TheyWorkForYou, the SP Bills API and SP TV.
    -   *Westminster bot*: the UK Parliament Hansard, Members and Bills APIs.
    -   Every host must be whitelisted on the internet-restricted target; `docs/NETWORK_AND_DEPENDENCIES.md` lists them and `server_py/test_apis.ps1` checks most of them.
-   **Deployment**: native Windows Server 2022 (no Docker/WSL), HTTPS on port 443; git-pull update workflow.
-   **Multi-bot**: one shared `server_py/` codebase runs every bot; per-bot identity and config live in `bots/<id>/`, and `RESEARCH_MODE` selects the toolset, prompts and efficiency profile. See "How one codebase behaves as different bots" in the README.

### 2.2 Manager-Worker Agent System

Both agents share the same underlying ReAct (Reason + Act) loop. Two provider clients implement it — `ollama_client.py` and `openrouter_client.py` — over a shared orchestration layer (`agent_core.py`) and tool-execution and summarisation pipeline (`agent_shared.py`, `agent/tools/`); the active provider is resolved per request and carried through the call chain via a `ContextVar`. The two agents differ in their system prompts, toolsets, and position in the call chain.

#### The shared engine: `chat_loop`

`chat_loop` is a recursive async function. Each iteration:
1. Sends the current message history to the LLM and streams the response
2. If the model emits tool calls, executes them (concurrently via `asyncio.gather`)
3. Appends the tool results to the message history and recurses
4. When the model produces a plain text response with no tool calls, returns it

The loop is capped at 20 rounds. A Worker that reaches the cap gets one further call with no tools, so the material already retrieved becomes a partial report; the halt is still disclosed to the legal professional as a limit, not a finding. A streaming request that fails before anything has been emitted is retried a bounded number of times. Worker and Manager calls carry an output cap on OpenRouter, and a Worker reply that comes back empty after heavy reasoning is not retried: it is reported to the Manager as lost, so the Manager can re-delegate.

---

#### Step 1 — Request arrives

`POST /api/chat` (`routers/ai.py`, SSE) is the user-facing entry point. Three siblings share its request model and config builder (`routers/agent_request.py::build_request_config`): `POST /api/research/plan` (Deep Research planning, JSON), `POST /api/system/chat` (the evaluation endpoint, which adds a structured audit trace) and `POST /api/consult` (federation, synchronous JSON). The request's provider config, chat mode, research type and filters are resolved and the request queued through a per-provider `RequestQueue` that enforces `max_concurrent_requests`. Once a slot is free, `process_user_request()` is called — the Manager's entry point.

---

#### Step 2 — Manager Agent (`process_user_request`)

**Toolset:** `delegate_research`, plus `consult_peer` when at least one enabled peer is registered.

**What it does:**

The Manager's system prompt depends on the bot and the chat mode. On the legislation bot, **Conversational** mode uses a short-answer prompt that delegates narrow, single-question briefs; **Research** mode delegates fuller briefs and presents a structured report. The parliamentary bots use one prompt in both modes. Appended to it, where they apply: uploaded document text, the chat's matter context, and the learning injection (section 3.6). A mode-change marker is prefixed to the user's turn when the chat mode or research type differs from the one the previous reply ran under.

The Manager then receives the conversation history and decides:

- **Conversational input** — responds directly without delegating
- **Ambiguous legal query** — asks a clarifying question before delegating, offering only options grounded in the conversation or in tool results
- **Clear legal query** — constructs a self-contained research brief and calls `delegate_research`

The research brief is deliberately richer than the user's raw message: the precise legal question, any Act names or SI numbers mentioned anywhere in the conversation, the jurisdiction, and context from prior turns. Where the question names no jurisdiction, the legislation bot researches and answers for Scotland and says so; a UK question is answered for each of the four nations. The Worker has no access to conversation history, so the brief must stand alone.

The Manager streams its tokens to the client in real time and may end with a `<suggestions>` block, which code strips from the answer and attaches as one-click follow-up buttons.

---

#### Step 3 — The handoff, and the answer seam

The Manager's `delegate_research` call is handled by `manager_tool_executor` in `agent_core.py`. This emits a `tool_start` SSE event (the UI shows a "Research Agent" status indicator), then calls `run_worker_agent()` with the brief. A Worker that fails returns a contained `[Research Agent Error]` tool result rather than killing the request. When the Worker returns, a `tool_end` event names the outcome (complete, stopped at the step limit, or reply lost) and the report is passed back to the Manager as a `tool` message prefixed `[Research Agent Result]`.

The Manager composes its reply around that report. Code then works on the reply before it reaches the user (the citation and footer steps concern legislation; the parliamentary bots keep a simpler sources filter):
- removes an unscoped agreement opener ("You are absolutely right ...");
- in Conversational mode, where the Manager rewrites the report in its own words: restores a sibling subsection or schedule paragraph the report contained and the reply dropped, verbatim, and links an instrument the reply names in words to the URL the research found for it;
- checks every legislation.gov.uk provision link against the URLs the tools returned, retargeting an unreturned provision link to its Act (marked) or removing it;
- builds the sources list from the sources the answer relies on, by title, rather than every search result;
- appends the search-scope footer: what was searched, its limits, and what the records consulted can and cannot establish.

---

#### Step 4 — Worker Agent (`run_worker_agent`)

**Toolset (varies by `research_mode`, wired in `tools/schemas.py::get_worker_tools`):**

| Research mode | Tools |
|---|---|
| `legislation_only` | `search_legislation`, `lookup_legislation`, `find_instruments_made_under`, `search_legislation_sections`, `get_legislation_changes`, `get_legislation_text` |
| `case_law_only` | `search_case_law`, `get_case_law_text` |
| `legislation_and_case_law` | both of the above |
| `parliamentary_records` | `search_scottish_plenary`, `get_scottish_plenary_debate`, `search_scottish_committee_transcripts`, `get_scottish_committee_transcript`, `search_scottish_parliament`, `get_member_info`, `search_bills` |
| `westminster_records` | `search_hansard`, `get_hansard_debate`, `get_member_info`, `search_bills` |

The quick-lookup Worker (Conversational mode on the legislation bot) is not offered `get_legislation_text`. With the Scottish judgments flag on, the case-law tools also search and read SCTS judgments.

The Worker starts with a fresh message history (system prompt + the research brief only) and does **not** stream tokens to the client. The legislation Worker follows a prescribed process; the case-law and parliamentary flows are analogous (discover → retrieve full text → synthesise):

| Phase | Action |
|---|---|
| 1 — Discover | `search_legislation` maps Act and SI names to `legislation_id`s, batched in one turn. Results are slimmed to id, title, url, text version, year, extent and the instrument's own description (cut to 600 characters). |
| 2 — Retrieve provisions | `search_legislation_sections` per instrument, starting with one combined query; the same instrument may be searched again only for an aspect not yet returned (at most 3 rounds per instrument). This is the primary retrieval step. |
| 2b — Relationships | `get_legislation_changes` for anything about commencement, amendment, repeal or revocation: the only source of those relations. Commencement dates are added in code from legislation.gov.uk's record; removals are classified by kind (provision, words only, or qualified). |
| 3 — Fallback | `get_legislation_text` only if Phase 2 is insufficient; it returns the text with schedules and annexes. |
| 4 — Iterate | Retry Phase 2 with alternative terms, within the per-instrument limit. |
| 5 — Synthesise | A structured markdown report: Summary Answer (BLUF), Detailed Analysis, Jurisdiction & Status, References, with pinpoint citations to the provision URLs the tools returned. |

Code acts around the model at fixed points:
- **Before the first search**, every instrument the brief names by number is looked up (`lookup_legislation`): held, held without text, or not held.
- **Not held, or no text**: the instrument's made or enacted text is read from legislation.gov.uk and handed over in a code-marked block; the answer says where it came from.
- **A schedule or annex** a section search names but does not return is fetched by its provision URI and cut to the part named.
- **The reverse made-under question** ("which instruments were made under s.N of Act X") is answered from a stored record of instrument preambles: Scottish SIs from 1999 and UK SIs from 1987 (86,744 instruments), with each instrument's revocation status as recorded by legislation.gov.uk. The forward question (what one instrument was made under) is stated only from the instrument's own recital.
- **Nudges** after each discovery result tell the model the next retrieval step and list the ids to use.
- **Budgets**: 8 ReAct rounds in which `search_legislation` may run and 3 section-search rounds per instrument (a refused legislation search is recorded and disclosed to the legal professional as a limit), and a search budget of 3 calls per Worker run on the parliamentary bots, after which searches are hard-stopped so the Worker moves on to retrieval.
- **Case law**: results are requested most relevant first, date ranges are applied, the true match count is reported, a case named in the query but not returned is flagged so its holding is not stated as read, and where a case and its appeal both appear the Worker is nudged to retrieve the higher-court decision.

After the Worker writes, its report is checked for structure (one no-tools reformat retry if malformed), and a code-written scope block is appended for the Manager and the Deep Research synthesis to read.

---

#### Step 5 — Summarisation pipeline

Large tool results are summarised before being fed back to the model. The threshold scales with the main model's context window (10% of its context in characters, clamped to 10,000–200,000); where the context length cannot be resolved, it falls back to **8,000 chars**. Below the threshold the raw result is passed through unchanged.

Above the threshold, the result is sent to the LLM with a focused prompt: retain only the sections, provisions, definitions, and legal thresholds relevant to the research question, and add nothing the source does not contain. This produces a query-focused extract rather than a raw compression. A case citation in a summary that the source does not hold is removed in code.

For very large results (> 150,000 chars), the text is split into chunks, each summarised independently, then combined. If the combined summaries are still large, one final consolidation pass is run.

Two further limits apply. The **context budget** (250,000 chars of tool output per Worker run) summarises any result that would take the run over it, whatever its own size. After summarisation, each result is capped at the threshold plus 4,000 chars.

Summarisation calls are bounded by a per-provider semaphore (`max_summarise_concurrency`; by default 1 for Ollama, whose cloud endpoint errors under concurrent large jobs, and 5 for OpenRouter). A separate, cheaper summarisation model can be configured per provider.

**Key design point:** summarisation is a quality decision, not just a size decision. A 50k char section result focused down to the query-relevant provisions is *better* input for the Worker's synthesis step than the raw 50k, regardless of whether the model could technically hold the larger payload.

---

#### A typical Research-mode legislation query

```
Manager turn 1    — triages the query, calls delegate_research with a self-contained brief
Worker (code)     — looks up every instrument the brief names by number
Worker turn 1     — parallel search_legislation calls (Phase 1); results arrive slimmed
Worker turn 2     — parallel search_legislation_sections calls, one combined query per instrument
                    (plus get_legislation_changes where the question is about change or commencement)
                    → large results summarised for the question
Worker turn 3     — further section searches if needed, then synthesises the report
Manager turn 2    — presents the findings, preserving citations and links
Answer seam       — checks provision links, filters the sources list, appends the scope footer
```

Elapsed time depends mainly on the model and on how much text is summarised. Over the pre-pilot (August 2026) the median turn took 45 seconds and the 90th percentile about 5 minutes; Deep Research runs take longer.

---

#### Key design decisions

| Decision | Rationale |
|---|---|
| Worker has no conversation history | Forces the Manager to craft a complete brief; prevents the Worker from hallucinating context it hasn't been given |
| Worker does not stream | Its output is intermediate research reasoning — only the Manager's answer is shown to the user |
| Limits enforced in code, not prompts | Filters, search budgets, the step cap and link checks hold even when a model ignores an instruction |
| Disclosure written by code | What was searched, what is not held, and what a record does not establish (in-force status above all) come from code-written blocks, so a model cannot turn an absence into a finding |
| Phase 2 nudge appended after summarisation | Ensures the navigation hint survives the summarisation step and is visible in the message the model reasons over |
| Tool results capped after summarisation | A ceiling of the summarisation threshold + 4,000 chars, plus a per-run context budget, prevents context overflow regardless of summarisation outcome |
| Parallel tool execution within a turn | All tool calls in a single turn run via `asyncio.gather` |
| Summarisation concurrency bounded per provider | The Ollama cloud endpoint cannot reliably handle concurrent large-context jobs; the semaphore prevents HTTP 500s |
| Failures contained | A failed or lost research step is reported as such to the Manager and the legal professional, never as a search that found nothing |

## 3. Key Features

### 3.1 Legislation research (AILA)
-   **Discovery and retrieval** over the LEX index: Act and SI search, section-level retrieval (preferred to whole-Act download), and whole-text reads that include schedules and annexes.
-   **Held or not held**: a deterministic lookup of every instrument cited by number. "Not held" is reported as a gap in the index, not as a wrong citation, and the text is read from legislation.gov.uk where possible.
-   **The record of changes**: amendment, commencement, repeal and revocation relations per provision, with commencement dates and qualifications from legislation.gov.uk where recorded. In-force status is stated only from the record, never from the text version held.
-   **The made-under record**: which instruments were made under a given section, with totals, coverage and revocation status; listed instruments lead with those not revoked in whole when more than 40 are found.
-   **Pinpoint citations**: labels name the subsection or schedule paragraph; links go to the provision URL the tool returned.
-   **Jurisdiction**: the jurisdiction filter keeps results by where legislation applies; a question naming no jurisdiction is answered for Scotland.

### 3.2 Case law
-   **Find Case Law** (National Archives): Atom search and full judgment text (LegalDocML), most relevant first, with date ranges, true match counts, appellate-decision detection and a note when a named case is not returned.
-   **Scottish judgments (SCTS)**: built behind the `scts_caselaw_enabled` feature flag, default off, to be switched on once both SCTS hosts are reachable from the target.
-   Coverage gaps (lower courts, first-tier tribunals, Scottish and Northern Irish courts while SCTS is off) are disclosed on every turn that searched case law.

### 3.3 Parliamentary research
-   **ParliChat (Holyrood)**: full-text search and verbatim retrieval of plenary and committee transcripts from a locally crawled PostgreSQL full-text database (comprehensive from Session 6, 2021; refreshed daily), written answers and older material as excerpts via TheyWorkForYou, MSP lookup and Scottish bill search. Optional SP TV video deep links (off unless `ENABLE_VIDEO_DEEPLINKS` is set) turn an Official Report citation into a timestamped video link where captions exist.
-   **HansardChat (Westminster)**: live Hansard search and verbatim retrieval across the Commons, Lords, Westminster Hall, Public Bill Committees, written statements and written answers, plus member lookup and UK bill search.

### 3.4 Shared platform
-   **Chat modes**: Conversational (always available), Research and Deep Research (each behind a feature flag).
-   **Deep Research**: a planner drafts an editable plan of up to 8 steps (or asks a clarifying question); on approval, code runs one Worker per step, hands each later step the instruments earlier steps cited, and composes an integrated report in one tool-free synthesis call. The approved plan is stored on the assistant message.
-   **Research filters** per bot: research type, jurisdiction, legislation type and year range (legislation); record type, session and date range (Holyrood); House, record type, Parliament and date range (Westminster). Enforced in code on the Worker's tools.
-   **Federation**: with peers registered, the Manager gains `consult_peer` to ask a sibling bot via `POST /api/consult` (synchronous; depth limited to prevent cascades). A consulted bot never asks the caller a question back.
-   **Suggested question buttons**: follow-up questions and clarification options as one-click buttons; a button never offers to change a mode or filter.
-   **Sources list**: the sources the answer relies on, by title, with links to the official source.
-   **Matters**: chats grouped into a matter with notes; the matter's details reach the Manager as context, and an AI research summary or research-gaps analysis can be generated and saved as a note.
-   **Document upload**: PDF, DOCX, plain text and Markdown attached to a chat; extracted text is injected as context.
-   **Concurrent runs**: switching chats does not interrupt a run; a refresh or closed tab still ends it.
-   **In-app reference**: Settings → Data Sources (what each bot searches, and its limits) and Settings → Release notes (changes since the pre-pilot, with the server's version and build).
-   **Strict citation**: answers cite `legislation.gov.uk`, the official case-law repositories, `parliament.scot` or `hansard.parliament.uk`.

### 3.5 Caching and cost
Three layers, additive and fail-soft, each behind a flag on the Admin Portal's Cache tab:
-   **Provider prompt caching** (`cache_control` on Anthropic models via OpenRouter).
-   **A per-request tool memo**: exact repeat tool calls within one request are served from memory.
-   **A local prompt cache**: document summaries reused across users and providers, keyed on the exact source text and the canonicalised question; public-source tools only.

A LEX/case-law response cache was measured and not built (LLM time dominates API time).

### 3.6 Feedback and learning
-   **Ratings**: thumbs up (helpful) or thumbs down with an optional comment on each answer.
-   **Learning injection**: on every Manager call, past answers rated helpful and comments on unhelpful ones are retrieved by keyword match across **all users'** questions and injected into the Manager's system prompt as examples and warnings. It has no feature flag. Its future is **parked** pending a decision (docs/TODO.md D21): known issues include question/answer mis-pairing, cross-user exposure and treating unverified comments as ground truth.
-   **Session feedback form** and **weekly productivity survey**, each behind a feature flag (default off).

### 3.7 Security & Administration
-   **Auth**: JWT-based authentication with bcrypt password hashing. No public sign-up: accounts are created by an administrator.
-   **Pre-use notice**: before first use, users acknowledge that queries go to third-party LLM services, what must not be entered (above OFFICIAL, personal data, privileged or confidential material, and so on), and that queries and responses are logged.
-   **Log redaction**: legislation and case-law Worker tool arguments are redacted at INFO by an allowlist (identifiers, dates and filter values in the clear; every other string as length and hash) and appear in full only at DEBUG. Still logged in full at INFO: the Worker's research brief (`agent_core.py`, "[Worker] Starting research on"), the parliamentary and Westminster tool arguments (`parliament.py`, `westminster.py`) and the learning injection's keywords (`learning.py`). Log files rotate daily and are kept for 14 days.
-   **Admin Portal** (admin role): User Management, Usage Stats, Performance, Efficiency, Cost, Cache, Data Coverage, Learning Monitor, Developer, Federation, Service Health, User Feedback (weekly survey responses), Session Feedback. Efficiency, Cache, Data Coverage (the Holyrood crawl's coverage), Developer and Federation are shown only to the built-in `admin` account.
    -   **Developer tab**: Configuration (LLM provider and model for both providers; feature flags: Matters, Research mode, Deep Research mode, Suggested question buttons, Session feedback form, Weekly user survey, Scottish judgments), Operations (parliamentary data refresh, activity log), Exports (users, session transcripts with feedback), and Backup & Restore (backup status, danger-zone data clear, scoped restore).
    -   **Efficiency tab**: per-bot efficiency profiles (breach rules and indicator bands chosen by research mode), including report-structure adherence by model.
    -   **Federation tab**: peer-registry CRUD (`api_key` write-only, never returned).
-   **Evaluation endpoint**: `/api/system/chat` mirrors `/api/chat` and emits a structured `audit` event (schema v6: delegations, tools, API calls, raw and summarised results) for the external eval harness.

## 4. Deployment & Infrastructure

### 4.1 Environment
-   **Target**: Windows Server 2022, internet-restricted (whitelist-only outbound), no Docker/WSL — everything runs natively. HTTPS on port 443 with organisational certificates. PostgreSQL runs as a Windows service; Ollama and uvicorn are started by the launch scripts.
-   **Automation**: PowerShell scripts (`deployment/install_native_offline.ps1`, `start_native.cmd`/`stop_native.cmd`); an offline wheel bundle for the restricted install; `server_py/test_apis.ps1` checks that the main external hosts are reachable (what it does and does not cover is in `docs/NETWORK_AND_DEPENDENCIES.md`).
-   **Updates**: the target does a `git pull` from `origin/main` — the frontend is pre-built and committed (`client/dist/`); there is no zip/file-transfer deployment.

### 4.2 Backup and restore
Nightly `pg_dump` of every bot database with two-stage verification (a full read, not only a table-of-contents check) and grandfather-father-son retention, plus a Developer-tab scoped restore through a staging database. **The scheduled backup task has not yet been installed on the target**, and an off-box backup destination is blocked on the server owner (docs/TODO.md D14, D15).

### 4.3 Releases
Calendar versions, `vYYYY.MM.N`: each release is an annotated tag on `main`, a dated section in `CHANGELOG.md`, and the `VERSION` file. The running version and build appear in Settings → Release notes, `GET /api/bot-info` and the first startup log line. Seven releases have been cut since the pre-pilot, from `v2026.09.1` (22 September 2026) to `v2026.10.4` (12 October 2026). Pre-pilot defect fixes are built on a branch and merged to `main` when the product owner decides to cut a release.

## 5. Status and Roadmap

**Status.** Proof of concept. The pre-pilot ran in August 2026; every session was re-analysed and the resulting fix plan (`docs/prepilot-fixes/FIX_PLAN.md`) is being worked through, its fixes reaching `main` in the releases above.

**Open work**, from `docs/TODO.md`:
-   **Scottish judgments** — switch on once both SCTS hosts are reachable from the target (built; FIX_PLAN P3.20). A feasibility study of caching SCTS results comes first if it is wanted (D24).
-   **National Archives case-law licence** — apply for the free licence covering AI use of Find Case Law (D23; an organisational action).
-   **Learning injection** — decide whether to put it behind a flag, fix it, or remove it (D21). Related idea: per-user standing instructions (D22).
-   **Research-step progress in the chat UI** (D20) and **runs that survive a refresh** (D12).
-   **Worker limits as startup settings** (D18), **per-request efficiency profiles** for the legislation bot (D1), and re-tuning the parliamentary efficiency bands (D2).
-   **Release follow-ups** — deploy by tag rather than the head of `main`, and stamp the version on the audit event and timing rows (D19).
-   **Evaluation** — live-verify the audit trace end to end (E1); a golden-question eval harness (A3); streaming the Worker's report verbatim in research mode (A1).
-   **Westminster video deep links** — spike GO, not built (D11).
-   **Per-message filter history** (D13), and surfacing silent client-side errors (B1).
-   **Operations** — install the nightly backup task, arrange off-box backups (D15), regenerate the offline bundle (T3), and credential hardening (T4).

**Decided against for now**: semantic (embedding) retrieval for the parliament bot (full-text search with an any-term fallback and query reformulation proved sufficient; `docs/parliament/SEMANTIC_RETRIEVAL_PLAN.md`); a YouTube caption fetcher for SP TV video links (D10); a LEX/case-law response cache (A5, unless target traffic shows the shared rate limit binding).

**Ideas from the original draft, not scheduled**: a "Barrister Agent" tier for court strategy; voice input.

*(Delivered since the original draft: dual-provider support, case-law mode, the Scottish Parliament and Westminster bots with federation, Deep Research, suggested question buttons, the caching stack, document upload, the Matters workspace, backup and scoped restore, the evaluation endpoint and audit trace, release versioning, and the pre-pilot fixes listed in `CHANGELOG.md`.)*
