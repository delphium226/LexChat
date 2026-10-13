# Low-Level Design Document

Describes the code on `main` as of release v2026.10.4. For the component and deployment view see
`ARCHITECTURE.md`; for endpoint detail see `docs/api/ServerAPISpec.md`; for the reasons behind the
design decisions summarised here see `CLAUDE.md` at the repository root.

## 1. Database Schema (PostgreSQL)

Each bot process has its own database (set by `DATABASE_URL`). At startup `init_db`
(`server_py/src/database.py`) runs `Base.metadata.create_all` over the models in
`server_py/src/models.py`, then an idempotent migration list (`CREATE TABLE IF NOT EXISTS`,
`ALTER TABLE … ADD COLUMN IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`) that brings an existing
database up to the current schema. Every column added after a table was first created is
**additive** (nullable or defaulted) and nothing is backfilled, so older rows read NULL or 0. The two
made-under tables are defined only in that migration list, not in `models.py`. `init_db` finally
seeds a default `admin` user and the `active_provider` setting (`ollama`) if they are absent.

Every bot creates the full schema; which tables fill depends on the bot (the Scottish Parliament
tables on the parliament bot, the made-under tables on the legislation bots). JSON columns are
declared `JSON` in the models; on a database that predates a column, the migration added it as
`JSONB`.

### 1.1 Core conversational tables

#### `users`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | SERIAL | PRIMARY KEY | Unique user identifier |
| `username` | VARCHAR(255) | UNIQUE, NOT NULL | Login username |
| `password_hash` | VARCHAR(255) | NOT NULL | Bcrypt hashed password |
| `email` | VARCHAR(255) | UNIQUE | Contact email |
| `role` | VARCHAR(50) | DEFAULT 'user' | 'admin' or 'user' |
| `dark_mode` | BOOLEAN | DEFAULT FALSE | UI preference |
| `research_mode` | VARCHAR(50) | DEFAULT 'legislation_only' | Saved research type preference |
| `chat_mode` | VARCHAR(50) | DEFAULT 'research' | Saved chat mode preference |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Account creation time |

#### `chats`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | SERIAL | PRIMARY KEY | Unique chat identifier |
| `user_id` | INTEGER | FK -> users(id) ON DELETE CASCADE, NOT NULL | Owner of the chat |
| `title` | TEXT | | Chat title (auto-generated or user set) |
| `model` | VARCHAR(255) | | LLM model selected at chat creation |
| `provider` | VARCHAR(50) | | LLM provider at chat creation (`ollama`/`openrouter`) |
| `matter_id` | INTEGER | FK -> matters(id) ON DELETE SET NULL | Optional owning matter (workspace) |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Chat creation time |

#### `messages`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | SERIAL | PRIMARY KEY | Unique message identifier |
| `chat_id` | INTEGER | FK -> chats(id) ON DELETE CASCADE, NOT NULL | Parent chat |
| `role` | VARCHAR(50) | NOT NULL | 'user' or 'assistant' |
| `content` | TEXT | NOT NULL | The message text |
| `model` | VARCHAR(255) | | Model actually used at inference time (assistant messages) |
| `provider` | VARCHAR(50) | | Provider actually used at inference time (assistant messages) |
| `cost_usd` | FLOAT | | Inference cost of the request that produced the message |
| `sources` | JSON | | The Sources-rail entries returned with an assistant message |
| `research_plan` | JSON | | Deep Research: the approved plan this answer executed (`{scope_note, steps: [{id, title, detail}]}`) |
| `research_mode` | VARCHAR(50) | | Research type the assistant message ran under |
| `chat_mode` | VARCHAR(50) | | Chat mode the assistant message ran under |
| `rating` | INTEGER | CHECK (1-5) | User feedback score; the UI writes 5 (thumbs up) or 1 (thumbs down) |
| `feedback_comment`| TEXT | | User feedback text |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Timestamp |

Messages are written by the client through `POST /api/chats/{chat_id}/messages`, the user turn
before the agent call and the assistant reply after it; the agent endpoints do not write this
table. The server echoes `research_mode` / `chat_mode` on its `result` event, the client stamps them
on the saved reply and sends them back with the history, and the backend compares them with the
current request to detect a mode change (§3.2). Indexes: `(user_id, created_at)` on `chats`,
`(chat_id, created_at)` on `messages`, a partial index on rated messages, and a GIN full-text index
on `messages.content`, which the learning loop queries (§3.6).

### 1.2 Configuration and federation

#### `app_settings`
Key/value store (`key` VARCHAR(255) PRIMARY KEY, `value` TEXT). Keys in use:
-   `active_provider` — `ollama` or `openrouter`.
-   `provider.ollama`, `provider.openrouter` — JSON per-provider config (`base_url`, `api_key`,
    `model`, `summarisation_model`, `temperature`, `max_concurrent_requests`,
    `max_summarise_concurrency`), merged over the `.env` defaults at request time, so a change takes
    effect without a restart.
-   `features` — JSON of the feature flags on the Developer tab: `matters_enabled`,
    `research_mode_enabled`, `deep_research_mode_enabled`, `suggested_questions_enabled`,
    `session_feedback_enabled`, `weekly_survey_enabled`, `scts_caselaw_enabled`,
    `prompt_caching_enabled`, `tool_memo_enabled`, `local_prompt_cache_enabled`. A flag missing
    from the saved JSON reads as its default (`routers/developer.py`).
-   `made_under.snapshot` — the version of the made-under snapshot loaded into the made-under
    tables (§1.5).

#### `peer_bots`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | SERIAL | PRIMARY KEY | Row id (not used in the API) |
| `peer_id` | VARCHAR(64) | UNIQUE, NOT NULL | String id used by `/api/peers/{peer_id}` and `consult_peer` |
| `name` | VARCHAR(128) | NOT NULL | Display name |
| `base_url` | VARCHAR(256) | NOT NULL | Peer's base URL |
| `api_key` | VARCHAR(256) | | Bearer token for the peer; write-only, never returned by the API |
| `description` | TEXT | NOT NULL | Shown to the Manager in the `consult_peer` tool description |
| `enabled` | BOOLEAN | DEFAULT TRUE | Only enabled peers are offered to the Manager |
| `created_at` | TIMESTAMP | DEFAULT NOW() | |

Seeded at startup from `bot_config.json`'s `peer_registry_seed` (insert-or-ignore on `peer_id`, so
a seed never updates an existing row).

### 1.3 Matters and documents

-   **`matters`** — `id`, `user_id` (FK users, CASCADE), `title` VARCHAR(255) NOT NULL,
    `description`, `status` (DEFAULT 'open'), `jurisdiction`, `legislation_type`, `created_at`,
    `updated_at`. A chat assigned to a matter gets a MATTER CONTEXT block (title, description,
    jurisdiction, legislation type) in the Manager's system prompt.
-   **`matter_notes`** — `id`, `matter_id` (FK matters, CASCADE), `content`, `message_id` (FK
    messages, SET NULL: the assistant message a note was pinned from), `created_at`.
-   **`documents`** — `id`, `chat_id` (FK chats, CASCADE), `user_id` (FK users, CASCADE),
    `filename`, `content_text`, `size_bytes`, `created_at`. Text is extracted at upload from
    `.pdf`, `.docx`, `.txt` and `.md` files (20 MB limit, 50,000 characters kept per file), and
    every document on a chat is injected into the Manager's system prompt on each request, capped
    at 80,000 characters in total.

### 1.4 Telemetry, feedback and activity

#### `request_timings`
One row per `/api/chat` or `/api/system/chat` request that reached the provider queue
(`/api/research/plan` writes none). Populated by `utils/stopwatch.py`'s `TimingCollector` and read by
the Admin Portal's Performance, Cost, Efficiency and Cache tabs.

| Group | Columns |
| :--- | :--- |
| Identity | `id`, `request_id`, `created_at`, `research_mode`, `chat_mode`, `provider`, `model`, `source` (`eval` for `/api/system/chat`; NULL, read as app traffic, otherwise) |
| Latency | `total_ms`, `queue_wait_ms`, `learning_db_ms`, `llm_calls`, `llm_total_ms`, `llm_ttft_first_ms`, `lex_api_calls`, `lex_api_total_ms` |
| Cost and caching | `total_cost_usd`, `cached_prompt_tokens`, `cache_discount_usd`, `memo_hits`, `local_cache_hits`, `local_cache_chars_saved` |
| Agent-loop behaviour | `manager_delegations`, `peer_consults`, `worker_tool_calls`, `react_turns_max`, `max_turns_halted`, `phase1_search_calls`, `phase2_retrieval_calls`, `distinct_legislation_ids_seen`, `distinct_legislation_ids_retrieved`, `redundant_tool_calls`, `search_budget_blocked`, `report_reformat_retries` |
| Summarisation and sources | `summarisation_calls`, `summarisation_chars_in`, `summarisation_chars_out`, `summarisation_chunks`, `truncation_events`, `sources_extracted`, `sources_kept`, `source_filter_fallback` |

#### Feedback
-   **`product_feedback`** — the weekly user survey (`weekly_survey_enabled`): `user_id`, `message`,
    `time_saved_hours`, `time_without_aila_hours`, `research_success`, `confidence`, `usability`,
    `verification_hours`, `created_at`.
-   **`session_feedback`** — the end-of-session form behind the "Finished session" button
    (`session_feedback_enabled`): `user_id`, `chat_id` (FK chats, SET NULL, so deleting a thread
    keeps its feedback), `message_count`, `manual_time_hours`, `time_saved_hours`,
    `verification_hours`, `session_continuity`, `found_right_law(_notes)`,
    `right_jurisdiction(_notes)`, `references_accurate`, `references_notes`,
    `refers_incorrectly(_notes)`, `confidence`, `ease_of_use`, `ease_of_use_reason`,
    `other_comments`, `filters` (JSON snapshot of the filter panel when the form was submitted),
    `finished_at`, `created_at`. The older `stated_law_correctly` / `stated_law_notes` columns remain
    on existing databases with their original answers but are no longer read or written.

#### Monitoring and activity
-   **`service_health_logs`** — `service_name`, `is_healthy`, `error_message`, `latency_ms`,
    `checked_at`; written by the background health loop every 5 minutes.
-   **`activity_log`** — `event_type`, `username`, `description`, `created_at`. Only `LOGIN`,
    `EFFICIENCY` (a per-request efficiency breach) and `RESTORE` rows are stored. The admin
    activity feed (`GET /api/developer/activity-log`) adds `QUERY`, `RESPONSE`, `FEEDBACK`,
    `SURVEY` and `ERROR` events, synthesised at query time by a `UNION ALL` over `messages`,
    `product_feedback`, `session_feedback` and `service_health_logs`.

### 1.5 Caches and the made-under record

-   **`local_prompt_cache`** — cross-user, cross-provider cache of Worker document summaries:
    `content_hash`, `query_hash` (UNIQUE together), `query_text`, `summary`, `summarise_model`
    (provenance only, not part of the key), `doc_name`, `chars_in`, `hit_count`, `last_hit_at`,
    `created_at`. Keyed on exact hashes of the raw tool result and the canonicalised query, so
    amended source text misses. Only results of tools in `CACHEABLE_TOOLS`
    (`services/local_prompt_cache.py`) are stored; rows are pruned by sampling once the table passes
    20,000 rows.
-   **`made_under_instruments`** — one row per statutory instrument in the made-under record:
    `legislation_id` (PRIMARY KEY), `title`, `recital` (the preamble's enabling-power wording),
    `version` (the text the recital was read from, `made`), `source` (`snapshot` or `refresh`),
    `harvested_at`, `revocation` (JSON flag from legislation.gov.uk's Changes to Legislation
    record; NULL when no removal is recorded) and `revocation_checked` (DATE; NULL when not
    checked).
-   **`made_under_powers`** — one row per provision a recital names: `legislation_id`,
    `act_title`, `act_norm` (normalised title), `act_id`, `provision` (e.g. `section/95`), `role`
    (`power`, or a qualified relation such as `as applied by`). Indexed on `(act_norm, provision)`,
    `(act_id, provision)` and `legislation_id`.

On the legislation bots, `services/made_under_store.py` loads a committed snapshot
(`server_py/data/made_under/`) into these tables at startup when its manifest version is newer
than `made_under.snapshot`, then adds newly published instruments daily from legislation.gov.uk's
new-legislation feeds, read through LEX's `/legislation/proxy`.

### 1.6 Scottish Parliament tables (parliament bot)

Populated by `services/parliament_crawler.py` when `RESEARCH_MODE=parliamentary_records`.
-   **`sp_committee_items`** and **`sp_plenary_items`** — one row per agenda item, same shape:
    `meeting_id`, `slug`, `iob_id` (UNIQUE `(meeting_id, iob_id)`), `committee_code`,
    `committee_name`, `meeting_date`, `agenda_item_title`, `url` (UNIQUE), `speeches` (JSON,
    per-speaker contributions), `full_text`, `fetched_at`. Each has a GIN full-text index on
    `full_text`, which the search tools query.
-   **`sp_video_captions`** — one row per SP TV event: `meeting_id`, `event_id` (UNIQUE), `slug`
    (TEXT), `meeting_date`, `start_time_utc`, `is_youtube`, `youtube_url`, `transcript`,
    `offset_index` (JSON `[[char_offset, wall_clock_ms], …]`), `caption_ok`, `fetched_at`. Used to
    attach timestamped video links to plenary and committee citations when
    `ENABLE_VIDEO_DEEPLINKS` is on.

---

## 2. API Specification (REST)

> This is a high-level sketch. **`docs/api/ServerAPISpec.md` is the authoritative, up-to-date
> endpoint reference** (auth rules, request/response shapes, and the federation, peers,
> identity, matters, documents, and activity-log endpoints).

Every API route requires a valid JWT, supplied as the HTTP-only `token` cookie set on login or an
`Authorization: Bearer <token>` header, except `POST /api/auth/login`,
`POST /api/auth/reset-password-request`, the `/api/health/*` endpoints and the identity endpoints
(`/api/bot-info`, `/api/bot/logo`). There is no global auth middleware: each route declares its own
dependency (`get_current_user` or `get_admin_user` in `dependencies.py`). There is **no public
signup** — the seeded `admin` account creates users via the Admin Portal.

| Prefix / route | Purpose |
| :--- | :--- |
| `/api/auth` | `POST /login`, `POST /logout`, `GET /me`, `POST /change-password`, `PUT /preferences`, `POST /reset-password-request`; `POST /federation-token` (admin) mints a non-expiring token for a peer bot |
| `/api/users` | Admin user management (list, create, update, delete) |
| `/api/chats` | List, create, rename, delete chats; `GET/POST /{chat_id}/messages` reads and **saves** messages (posting does not run the agent); `PUT /messages/{message_id}/rating`; `POST /{chat_id}/matter` assigns a chat to a matter |
| `/api/chats/{chat_id}/documents`, `/api/documents/{doc_id}` | Upload, list, delete chat documents |
| `/api/matters` | Matters CRUD, `/{matter_id}/notes`, `POST /{matter_id}/brief` |
| `GET /api/models` | The active provider's model list, the configured default marked `active` |
| `POST /api/chat` | **The agent endpoint** (SSE): standard research and conversational turns, and Deep Research execution when a `deep_research_plan` is sent |
| `POST /api/research/plan` | Deep Research planning (plain JSON): a plan, or a clarifying question with options |
| `POST /api/system/chat` | Machine-to-machine variant of `/api/chat` for evaluation harnesses (same body; detailed tool events plus an `audit` trace) |
| `POST /api/consult` | Federation: answer a peer bot's question (synchronous JSON; depth ≥ 2 rejected) |
| `/api/peers` | Admin peer registry, keyed on the string `peer_id` |
| `/api/learning` | Admin: rated messages, rating stats, `POST /test` of the learning-loop retrieval |
| `/api/stats` | Admin dashboards: `usage`, `performance`, `cost`, `efficiency`, `cache` (and `DELETE /cache/local`), `parliament-coverage` |
| `/api/feedback` | Weekly survey (`POST`/`GET`), session feedback (`/session`, `/session/transcripts`, `/session/durations`, `/session/compliance`), `/message-ratings`, `/compliance` |
| `/api/developer` | `GET /features` and `GET /activity-log` (any user); admin: `POST /features`, provider config, active provider, OpenRouter model list, users export, data counts, clear data, backups and scoped restore, parliament refresh |
| `/api/health` | `GET /status`, `GET /history`, `POST /trigger` |

**SSE events on `/api/chat`:** `queue` (position in the provider queue), `token` (answer text),
`tool_start` / `tool_end` (progress labels for the Research Agent, each Deep Research step and each
Worker tool), `warning` (after five minutes), `timing`, then `result` (the final message: content,
sources, suggestions, model, provider, the modes it ran under, and incomplete-research flags) or
`error`. `/api/system/chat` also relays `tool_call` / `tool_result` and emits one `audit` event before
`result` (`docs/api/AUDIT_TRACE.md`).

---

## 3. Agent Architecture (Server-Side)

The backend implements a **Manager-Worker** pattern to handle complex queries. The logic lives once
in `server_py/src/agent/agent_core.py` (orchestration) and `agent_shared.py` (tool execution);
`openrouter_client.py` and `ollama_client.py` supply the provider-specific `chat_loop` and
summarisation call and bind them to that shared logic.

### 3.1 Request path and provider layer
1.  **`routers/ai.py` `/api/chat`** resolves the active provider and its config
    (`provider_factory.py`, from `app_settings`) and the feature flags, loads the chat's documents
    and matter context, and builds the per-request config with `build_request_config`
    (`routers/agent_request.py`). That dict is set on a **ContextVar**, which carries the provider,
    model settings, `_research_mode`, `_chat_mode`, every filter and every flag through the whole
    async call chain without changing function signatures. A bot whose `RESEARCH_MODE` is set
    always uses it, whatever research type the request body sends.
2.  The request waits for a slot on the provider's **`RequestQueue`** (`max_concurrent_requests`,
    cached per provider and concurrency), emitting `queue` events while it waits.
3.  It dispatches to `process_user_request` (the Manager) or, for an approved plan,
    `run_deep_research`.
4.  It emits `timing` and `result`, then writes a `request_timings` row and an `EFFICIENCY`
    `activity_log` row for any breach of the bot's efficiency profile.

`/api/system/chat` and `/api/research/plan` build their config through the same
`build_request_config`, so the three endpoints accept the same fields. `/api/consult` sets a
minimal config of its own (the bot's research mode, plus `_consulted`, which tells the Manager it is
answering another bot and must not ask questions).

`chat_loop` runs a streaming ReAct loop over the provider's API: at most **20 rounds**, a bounded
retry of the streaming request (3 attempts, only while nothing has been emitted), a 180-second read
timeout, and, at the round cap, one tool-free write-up round. On OpenRouter it marks the system
prompt and last message with `cache_control` for `anthropic/*` models (`prompt_caching_enabled`).

### 3.2 Manager Agent
-   **System Prompt**: Defined in `server_py/src/prompts.py` and assembled by
    `get_manager_system_prompt(research_mode, cfg)` from today's date, one of four bases —
    `MANAGER_SYSTEM_PROMPT` (Research chat mode), `MANAGER_SYSTEM_PROMPT_CONVERSATIONAL`,
    `PARLIAMENT_MANAGER_SYSTEM_PROMPT` or `WESTMINSTER_MANAGER_SYSTEM_PROMPT` (the parliamentary
    bots use theirs in every chat mode) — each ending in the `<suggestions>` rules, or prose
    follow-up rules when `suggested_questions_enabled` is off, and the active filters (on the
    legislation bot inside a research-type note placed before the base). `CONSULTED_PEER_BLOCK` is
    appended when the request came through `/api/consult`. `process_user_request` then appends the
    uploaded documents, the matter context and the learning-loop examples (§3.6).
-   **Tools**:
    -   `delegate_research(query)`: Hand off legal queries to the Worker. The `query` parameter must be a self-contained research brief including Act names, years, jurisdiction constraints, and any relevant conversational context — the Worker has no access to conversation history.
    -   `consult_peer(peer_id, question)`: Ask a federated bot. Offered only when at least one
        enabled peer is registered.
-   **Flow**:
    1.  Receives the conversation and builds the system prompt.
    2.  If the research type or chat mode differs from the one stamped on the previous assistant
        message, prefixes a `[SYSTEM NOTICE …]` mode-change marker to the user's turn
        (`utils/mode_change.py`).
    3.  Triages: general conversation (answer directly) vs. legal query (delegate). Each
        `delegate_research` call is one Worker run; the runs of one request share a tool memo and
        the set of URLs the tools returned. A failed Worker comes back as a `[Research Agent Error]`
        tool result rather than ending the request.
    4.  In Research chat mode it presents the Worker's report verbatim, preserving all citations;
        in Conversational mode it answers in its own words.
    5.  **Answer seam** — code then post-processes the answer, in order: falls back to the Worker
        reports if the Manager's reply came back empty; strips the `<suggestions>` block (attached
        as `suggestions` when the flag is on); in Conversational mode restores sibling subsections
        and schedule paragraphs the answer dropped and, on the legislation bot, links instruments
        named in words; demotes or unlinks provision URLs no tool returned; strips the Worker's
        scope blocks; discloses halted or lost research; re-admits retrieved sources the answer
        names and titles bare-id rail entries; and appends a code-written footer stating what was
        searched.
    6.  Returns the answer with `sources`, `suggestions`, the modes it ran under and any
        incomplete-research flags.

### 3.3 Worker Agent
-   **System Prompt**: Assembled by `get_worker_system_prompt(research_mode, cfg)` in `prompts.py`
    from today's date, one base per research type — `WORKER_SYSTEM_PROMPT` (legislation),
    `WORKER_SYSTEM_PROMPT_CASE_LAW`, `WORKER_SYSTEM_PROMPT_HYBRID`,
    `PARLIAMENT_WORKER_SYSTEM_PROMPT`, `WESTMINSTER_WORKER_SYSTEM_PROMPT`, or
    `WORKER_SYSTEM_PROMPT_CONVERSATIONAL` (the quick-lookup Worker, used in Conversational mode on
    the legislation bot) — and the filter-constraint block. Strict citation and source-grounding
    rules; ephemeral context (no conversation history).
-   **Tools** (defined in the `server_py/src/agent/tools/` package — `schemas.py` for the
    definitions and `get_worker_tools`, with `lex.py`, `caselaw.py`, `scts.py`, `parliament.py`,
    `westminster.py`, `commencement_dates.py`, `published_text.py` and `executor.py`). The tool set
    follows the research type:

    | Research type | Worker tools |
    | :--- | :--- |
    | `legislation_only` | `search_legislation`, `lookup_legislation`, `find_instruments_made_under`, `search_legislation_sections`, `get_legislation_changes`, `get_legislation_text` |
    | `case_law_only` | `search_case_law`, `get_case_law_text` |
    | `legislation_and_case_law` | both of the above |
    | `parliamentary_records` | `search_scottish_plenary`, `get_scottish_plenary_debate`, `search_scottish_committee_transcripts`, `get_scottish_committee_transcript`, `search_scottish_parliament`, `get_member_info`, `search_bills` |
    | `westminster_records` | `search_hansard`, `get_hansard_debate`, `get_member_info`, `search_bills` |

    The legislation tools:
    -   `search_legislation(query, year_from?, year_to?)`: Ranked search of UK Acts and SIs by title or content. Returns slimmed metadata rows (id, title, URL, text version, year, extent, description cut to 600 characters); does **not** download full text.
    -   `lookup_legislation(legislation_type, year, number)`: An exact held / held-without-text / not-held test for one instrument named by type, year and number. Code also runs it on every instrument a brief names by number before the Worker's first round.
    -   `find_instruments_made_under(act, section)`: Which instruments' preambles name a given provision as an enabling power, answered from the made-under record (§1.5), with each instrument's recorded revocation status.
    -   `search_legislation_sections(query, legislation_id)`: Search for specific sections within a known Act. **Preferred over `get_legislation_text`** for targeted questions — avoids downloading the entire Act.
    -   `get_legislation_changes(legislation_id, direction?)`: Commencement, amendment, repeal and revocation relations from LEX's `/amendment/search`, with commencement dates added from legislation.gov.uk where it records them.
    -   `get_legislation_text(legislation_id)`: Retrieve the full text of an instrument, schedules included. Fallback only — used when section search returns insufficient results, or when the full structure of an Act is required. Not offered to the quick-lookup Worker.

    With the `scts_caselaw_enabled` flag on, `search_case_law` also searches the Scottish Courts and
    Tribunals Service's judgments (returned as `scottish_results`) and `get_case_law_text` reads
    either source.
-   **Flow**:
    1.  Receives the research brief from the Manager or a Deep Research step (isolated context — no
        chat history), with fresh per-run budgets: legislation Workers may search in at most 8
        ReAct rounds and section-search one instrument in at most 3; parliamentary Workers get 3
        searches; and the run's total tool output is bounded at 250,000 characters before every
        further result is summarised.
    2.  Calls `search_legislation` to identify candidate Acts and obtain `legislation_id`s.
    3.  Calls `search_legislation_sections` scoped to each relevant Act to retrieve matching provisions directly, and the change record, lookup or made-under tools where the question needs them.
    4.  Falls back to `get_legislation_text` only if section search yields nothing useful.
    5.  Iterates with alternative search terms if results are sparse, within the budgets.
    6.  Returns a structured, cited markdown report. The sections per research type are
        `REPORT_SECTIONS` in `prompts.py` (legislation: Summary Answer (BLUF) → Detailed Analysis →
        Jurisdiction & Status → References). Outside Conversational mode a malformed report gets one
        tool-free reformat retry (not for a halted or lost run).
-   **After the loop**: a Worker that reached the round cap returns its write-up labelled as
    partial findings, and one whose final reply came back empty returns a labelled lost report;
    provision links no tool returned are demoted or removed; sources the report does not vouch for
    are dropped from the rail (on the parliamentary bots a report that vouches for none keeps them
    all); and a scope block recording every search the run made is appended for the Manager or the
    synthesis to read (the answer seam strips it).

### 3.4 Tool execution and summarisation
Every Worker tool call goes through `run_worker_tool` (`agent_shared.py`):
1.  **Budgets and memo** — the discovery and section budgets are checked first; then an exact
    repeat of `(tool name, arguments)` within the request is served from the per-request tool memo
    (`tool_memo_enabled`) without an API call or summarisation; then the parliamentary search
    budget.
2.  **Execution** — dispatched by research mode to `execute_westminster_tool`,
    `execute_parliament_tool` or `execute_worker_tool`. LEX calls retry on 429/502/503/504 with
    bounded backoff.
3.  **From the raw result** — sources and legislation.gov.uk URLs are extracted, and code builds the
    notes the model must not lose to summarisation: search-scope blocks, not-held notes,
    enabling-power and change-record blocks, case-law next-step and appellate notes. Where the index lacks an
    instrument or its text, code reads it from legislation.gov.uk through LEX's proxy.
4.  **Summarisation** — a result longer than the threshold, or one that would take the run past its
    context budget, is summarised against the brief (`summarisation.py`): the threshold is 10% of
    the model's context window in characters, clamped to 10,000–200,000, or 8,000 when the context
    length is unknown; texts over 150,000 characters are summarised in chunks; the provider's
    `summarisation_model` is used when set, under a per-provider concurrency semaphore. For tools in
    `CACHEABLE_TOOLS` the local prompt cache is checked first and a clean summary stored after.
    Case citations the source does not hold are removed from every summary. The made-under list is
    never summarised.
5.  **Assembly** — provision URLs and subsection outlines go back after a summary, a schedule unit
    the section search missed is fetched and appended, then the notes and next-step nudges; the
    result is memoised, charged to the context budget and recorded on the audit trace.

### 3.5 Deep Research
-   **Phase A — planning** (`/api/research/plan` → `draft_research_plan`): a planner-only call
    (`PLANNER_SYSTEM_PROMPT`) whose tools are `submit_research_plan` (a scope note and at most 8
    steps) and `request_clarification` (a question with up to 4 options). One corrective retry if
    the model answers in prose. The client renders the plan as an editable card.
-   **Phase B — execution** (`/api/chat` with `deep_research_plan` → `run_deep_research`): Python
    loops over the approved steps, one Worker run per step. Each step's brief carries the original
    question and scope note and, from step 2, a code-written line naming the instruments earlier
    steps cited (`utils/step_handover.py`). Steps share the tool memo and the retrieved-URL set. A
    single tool-free synthesis call (`build_synthesis_messages`) composes the report from the step
    findings; the same link enforcement, disclosures, source handling and scope footer as the
    Manager path follow. The client saves the approved plan on the assistant message
    (`messages.research_plan`).

### 3.6 Learning Loop (RAG)
-   **Ingest**: When a user rates a message 4-5 (the thumbs-up button writes 5), it becomes a "Positive Example".
-   **Critique**: When a user rates a message 1-3 with a comment (the thumbs-down form writes 1), it becomes a "Negative Constraint".
-   **Retrieval**: On each new message, `agent/learning.py` extracts keywords from the user's latest
    message (stop words and words of three letters or fewer removed), OR-combines them into a
    PostgreSQL `to_tsquery`, and matches stored user messages through the full-text index on
    `messages.content`. It takes up to 3 highly rated answers to similar questions (each cut to
    2,000 characters) and up to 3 critiques, and appends them to the Manager's system prompt. It is
    keyword full-text search; there are no embeddings.

---

## 4. Frontend Architecture (React)

A single-page React app built with Vite. The build output (`client/dist/`) is committed and served
by the backend.

### Directory Structure
-   `src/main.jsx`: Mounts `<App>` inside `BrowserRouter`.
-   `src/App.jsx`: Two routes. `/` is the application: the login gate (`LoginModal`), sidebar,
    transcript, composer and Sources rail, with every other screen (Admin Portal, account settings,
    history, matters, filters, release notes) opened as a modal over it. `/systemchat`
    (`pages/SystemChat.jsx`) is a raw event viewer for `/api/system/chat`.
-   `src/context/AuthContext.jsx`: Provides `user` (from `GET /api/auth/me`) and `login/logout`
    app-wide; a global axios interceptor marks the session expired on a 401.
-   `src/hooks/`:
    -   `useChat`: the chat flow — create the chat, save the user turn, stream `/api/chat`, save the
        assistant reply; Deep Research planning, plan approval and execution; loading a chat.
    -   `useChatRuns`: a per-chat run registry, so several chats can research at once and a
        background run keeps streaming while another chat is open.
    -   `useFilters`: research filters, persisted as global defaults and per-chat snapshots in
        localStorage.
    -   `usePreferences`: dark mode, chat mode and research type, synced with
        `PUT /api/auth/preferences`.
    -   `useMatters`: matters state and the feature-flag fetch.
    -   `useModals`, `useBotIdentity` (bot name, branding and favicon from `/api/bot-info`).
-   `src/components/`:
    -   Chat: `Sidebar` (new thread, mode menu, Matters tree, recent threads with a per-chat run
        indicator), `ChatMessage` (rendered answer, rating, copy, pin to a matter, the approved
        Deep Research plan), `Composer` (document attach, Finished session, send/stop),
        `SourcesRail`, `DeepResearchPlan` (editable plan card), `SuggestedQuestions` (one-click
        chips under the latest answer).
    -   Dialogs: `ResearchFiltersModal`, `HistoryModal`, `SettingsMenuModal`, `CreateMatterModal`,
        `AssignMatterModal`, `MatterNotesModal`, `DataSourcesModal`, `ReleaseNotesModal`,
        `AboutModal`, `ActivityLogModal`, `SessionFeedbackModal`, `WeeklyFeedbackBanner`,
        `DataSensitivityNotice` (acknowledged after sign-in on each load).
    -   `ui/`: shared primitives (`Modal`, `Card`, buttons, icons, `Spinner`, `InfoTip`).
-   `src/pages/`:
    -   `AdminPortal.jsx`: Admin-only (opened from the Settings menu). Tabs: User Management, Usage
        Stats, Performance, Cost, Learning Monitor, Service Health, User Feedback, Session Feedback,
        and — for the seeded `admin` account only — Efficiency, Cache, Data Coverage, Developer and
        Federation. The larger tabs live in `pages/admin/`; `DeveloperTab` holds the provider
        configuration, feature flags, transcript export, backup status, scoped restore, the Danger
        Zone and the parliament refresh.
    -   `Settings.jsx`: Account settings (change password).
    -   `SystemChat.jsx`: see above.
-   `src/services/api.js`: Request helpers for every endpoint, using axios with relative `/api` URLs
    (the JWT travels as the HTTP-only cookie). `sendMessage` uses `fetch` and reads the SSE stream
    from `/api/chat`.
-   `src/constants/research.js`: Filter option lists (jurisdictions, legislation types, Holyrood
    sessions, Westminster record types and Parliaments).
-   `src/utils/`: `exportChat.js` (clipboard export of a thread as rich text, and stripping of
    `<suggestions>` and thinking blocks from display), `csv.js` (Admin Portal CSV export),
    `format.js`.

### Key Libraries
-   **State**: React hooks and context (`useState`, `useReducer`, `useContext`); no external store.
-   **Routing**: `react-router-dom`.
-   **HTTP**: `axios`, plus `fetch` for the SSE stream.
-   **Styling**: `tailwindcss` with design tokens (`docs/frontend/design-system.md`) and
    `@tailwindcss/typography`.
-   **Markdown**: `react-markdown` + `remark-gfm` (for tables/citations); `marked` and `dompurify`
    for HTML copy and export.
-   **Rich text**: TipTap (matter notes editor).
-   **Charts**: `recharts` (for Admin visuals).

---

## 5. Deployment Architecture

The application is deployed **natively on Windows Server 2022 — no Docker, no WSL.** Everything
runs as native processes/services. See `docs/deployment/NATIVE_DEPLOYMENT.md` for the full guide
and `ARCHITECTURE.md` for the deployment view.

### 5.1 Processes / services
1.  **FastAPI backend (uvicorn)** — the single application entry point. Serves the pre-built React
    frontend (`client/dist/`) as static files **and** the `/api` backend from one process. Listens
    on **HTTPS port 443** in production (organisational TLS certs in `deployment/certs/`); HTTP
    port 8000 in local dev. In-process background tasks: the service health check every 5 minutes;
    on the legislation bots, the made-under record load and its daily refresh; on the parliament
    bot, the Scottish Parliament crawlers.
2.  **PostgreSQL** — runs as a Windows service (the start/stop scripts manage
    `postgresql-x64-18`); listens on `localhost:5432` only.
3.  **Ollama** — local inference process/proxy on `localhost:11434`; forwards `:cloud`-tagged models
    to remote inference providers. Only used when Ollama is the active provider (OpenRouter calls
    `openrouter.ai` directly).

The frontend is **pre-built on the dev machine and committed** (`client/dist/`); the target server
needs no Node.js. Start/stop is scripted via `deployment/start_native.cmd` /
`deployment/stop_native.cmd` (PostgreSQL → Ollama → uvicorn); `install_autostart.ps1` registers a
boot-time scheduled task that runs `start_background.ps1`. `start_native.cmd` also has an optional
`--nginx` mode (nginx on port 80 in front of uvicorn on 8000); the default is uvicorn terminating
TLS itself.

### 5.2 Traffic flow
1.  **User request** → HTTPS port 443 → **uvicorn**.
2.  **Static asset** → uvicorn serves the file from `client/dist/`.
3.  **API request (`/api/*`)** → handled in-process by FastAPI, which queries PostgreSQL and the
    active LLM provider (Ollama or OpenRouter) plus external research APIs: LEX (including its
    legislation.gov.uk proxy), National Archives Find Case Law, the Scottish Parliament sources
    (Official Report, Bills, TheyWorkForYou, SP TV), the UK Parliament APIs on the Westminster bot,
    and SCTS when its flag is on. The `external-apis` skill lists base URLs and endpoints.

### 5.3 Multi-bot & updates
Each bot is an **independent uvicorn process** with its own database and port, differentiated by
configuration (`bots/<id>/`: `legislation`, `parliament`, `westminster`), not forked code; bots can
consult each other via federation (`POST /api/consult`). Updates are delivered by `git pull` from
`origin/main` (there is no zip/file-transfer deployment).
