# AILA — Claude Code Context

## What This Project Is
AILA (AI Legal Assistant) is an AI-powered legal research assistant for a **UK government organisation**. Users are qualified lawyers querying UK legislation and case law. The system uses a Manager-Worker agent architecture — the Manager handles conversation, the Worker performs deep research via the LEX API.

## Tech Stack
- **Frontend**: React 19 + Vite + Tailwind CSS (`client/`)
- **Backend**: Python 3.11 + FastAPI + uvicorn (`server_py/`)
- **Database**: PostgreSQL 15 (`lexuser`/`lexpassword`/`lexchat`)
- **AI Engine**: Ollama (proxies to Ollama-hosted cloud models) **or** OpenRouter — switchable at runtime via Admin Portal
- **Model**: Configured per-provider in Admin Portal → Developer tab; defaults to `mistral-large-3:675b-cloud` (Ollama)

## Deployment Target
- **OS**: Windows Server 2022, **internet-restricted** (outbound access limited to whitelisted addresses only — not fully air-gapped)
- **No Docker, no WSL** — everything runs natively
- **HTTPS on port 443** using organisational certificates at `deployment/certs/lexchat.crt` and `deployment/certs/lexchat.key`
- PostgreSQL runs as a Windows service; Ollama and uvicorn are started by the launch scripts
- OpenRouter requires outbound internet to `openrouter.ai` — works on the target if that address is whitelisted

## Active Branch
`main` — the federation feature has been merged and is the active deployment branch.

## Key Architectural Decisions

### LLM Provider System
- Two providers supported: **Ollama** (Ollama-hosted cloud models, accessed via the local Ollama process as a proxy) and **OpenRouter** (internet, OpenAI-compatible API)
- Active provider and all per-provider settings are stored in the `AppSetting` DB table — no restart required to switch
- Per-provider settings: `base_url`, `api_key`, `model`, `summarisation_model`, `temperature`, `max_concurrent_requests`, `max_summarise_concurrency`
- Settings stored as JSON blobs: `AppSetting(key="provider.ollama")` and `AppSetting(key="provider.openrouter")`
- `.env` values are startup defaults/fallbacks; DB overrides at request time
- A `ContextVar` in `provider_factory.py` carries the resolved config through the entire async call chain (chat_loop, worker agent, summarisation) without changing function signatures
- Per-provider `RequestQueue` and summarisation `asyncio.Semaphore` cached by `(provider, concurrency)` — recreated automatically if settings change

### Model Selection
- Model is no longer hardcoded in the frontend — `App.jsx` calls `GET /api/models` on load
- `/api/models` returns the active provider's model list with `active: true` marking the configured default
- `FIXED_MODEL` constant has been removed from `App.jsx`
- Curated model lists in `config.py`: `MODEL_LIST` (Ollama) and `OPENROUTER_MODEL_LIST` (OpenRouter)

### Provenance
- `Chat.model` and `Chat.provider` — set at chat creation (frontend state at time of first message)
- `Message.model` and `Message.provider` — set on every **assistant** message from the backend result; authoritative record of what was actually used at inference time

### Worker Agent Optimisations
The Worker's research pipeline has been tuned to minimise unnecessary LLM calls and summarisation overhead. Key decisions:

- **`search_legislation` response slimming** — `_slim_search_results` in `tools.py` strips the API response to `legislation_id`, `title`, `url`, `status`, `year`, and `extent` only. The `description` field is intentionally excluded — it is verbose and redundant once Phase 2 retrieves actual section text. This keeps Phase 1 results under the summarisation threshold (~1–2K per result vs 10–16K with description), eliminating Phase 1 summarisation entirely.
- **One call per `legislation_id` in Phase 2** — The Worker system prompt instructs the model to make exactly one `search_legislation_sections` call per `legislation_id`, combining all aspects into a single query (e.g. `"procedure, confirmation, compensation, definition of acquiring authority"`). This prevents duplicate calls to the same Act, which were previously the dominant source of unnecessary summarisation.
- **Dual-model support** — Each provider can be configured with a separate `summarisation_model` (Admin Portal → Developer tab). If set, this model is used exclusively for document summarisation; the main `model` is used for all Manager and Worker agent calls. If blank, both roles use the same model. Recommended: on OpenRouter, set `summarisation_model` to `google/gemini-2.0-flash` for fast, cheap summarisation while keeping a capable model for reasoning.
- **Summarisation concurrency** — Controlled per-provider via `max_summarise_concurrency` in the Admin Portal. Ollama should be set to **1** — concurrent calls to the Ollama cloud endpoint cause HTTP 500 errors. OpenRouter can handle **5+** without errors and processes summaries in parallel significantly faster. The right value depends on the model and endpoint capacity.
- **Model quality is the dominant variable** — A capable instruction-following model (e.g. Gemini Flash on OpenRouter) will correctly batch Phase 2 calls, use combined queries, and complete an 8-Act research query in ~90 seconds. A weaker model (e.g. free-tier Nemotron) ignores batching instructions, makes sequential single calls with duplicate `legislation_id`s, and produces bloated context — with the same infrastructure but ~10× worse performance.
- **Phase 2 nudge** — After each `search_legislation` result is processed, a `[NEXT STEP: Call search_legislation_sections...]` instruction with extracted `legislation_id`s is appended to the tool result. This ensures the model proceeds to Phase 2 even if the system prompt instruction is not followed precisely.

### Parliamentary Research Worker Optimisations
When `research_mode == "parliamentary_records"` (set via `RESEARCH_MODE` env var for the parliament bot), the Worker uses `PARLIAMENT_TOOLS` instead of `WORKER_TOOLS`. **The parliament bot is Scotland-only (Scottish Parliament / Holyrood)** — all UK Parliament (Westminster) search and retrieval was removed. Key design decisions:

- **Parliament tool set** — `search_scottish_plenary`, `get_scottish_plenary_debate`, `search_scottish_parliament`, `search_scottish_committee_transcripts`, `get_scottish_committee_transcript`, `get_member_info` (MSPs only), `search_bills` (Holyrood only). Wired via `get_worker_tools("parliamentary_records")` in `schemas.py`. The Westminster tools `search_hansard` and `get_hansard_debate` were removed; `get_member_info` and `search_bills` no longer take a `parliament` param (always Scotland).
- **SP plenary full-text (DB-backed)** — plenary (chamber) debates are now fully searchable and retrievable via a DB pipeline that mirrors the committee one: `search_scottish_plenary` runs GIN FTS over the local `sp_plenary_items` table, and `get_scottish_plenary_debate` live-fetches + parses the verbatim speeches for a specific agenda item (`meeting_id`+`slug`+`iob_id`). This closes the *Pepper v Hart* gap (retrieving a minister's full statement of statutory purpose). Parsing is done by `_parse_sp_plenary_transcript`: each contribution is a `<p id="orscontributions_...">` element whose speaker is the first `/msps/` anchor. **Committee pages use the same markup**, so this one parser now serves both plenary and committee (the former committee-specific `_parse_sp_transcript_page` was deleted — see the video-deep-link section). The parser optionally scopes to one agenda item via its `<h2 class="h3">` heading; `get_scottish_plenary_debate` looks the stored `agenda_item_title` up from `sp_plenary_items` to pass as the scope.
- **SP plenary excerpt fallback** — `search_scottish_parliament` (TWFY `getHansard`, no `type=sp` — broken; post-filtered by `/sp/` listurl in `_slim_hansard_results`) remains as an **excerpt-only breadth/older-session fallback** for plenary content not yet crawled into `sp_plenary_items`, and is the route for **written answers**. Prefer `search_scottish_plenary` for full text.
- **FTS retrieval-quality wins (2026-07-13, no pgvector)** — a measured go/no-go gate (33-query hit-rate, `docs/parliament/SEMANTIC_RETRIEVAL_PLAN.md` is DEFERRED/NO-GO) found FTS-only was ~85% raw / ~97%+ with Worker reformulation, so two cheap wins were shipped instead of embeddings. **(Win 1 — OR-fallback)** `plainto_tsquery` ANDs every term, so one absent term (colloquial/US, e.g. "unhoused" vs "homeless") returns 0 rows. Both `_search_plenary_db` and `_search_committee_transcripts_db` keep the exact `plainto` path byte-for-byte (precision) and, **only when it returns zero rows**, re-run the same query (same date/committee filters, same `ts_rank` ORDER BY) with an OR-combined `to_tsquery` built by `_or_tsquery` (lowercase → tokenise `[a-z0-9]+` → drop ≤2-char + stopword tokens → dedup → join with ` | `), setting `note: "No exact (all-terms) match; broadened to any-term search."`. It is deliberately **not** always-OR (that would broaden every query and risk precision on the ~85% that already work); an empty/stopword-only token set skips the fallback (never `to_tsquery('english','')`). **(Win 2 — query wording, prompt-only)** `PARLIAMENT_WORKER_SYSTEM_PROMPT` PHASE 1 has a QUERY WORDING block (use the official Holyrood term not colloquial/US variants — quango→public body, unhoused→homeless, neurodiversity→additional support needs, poll tax→council tax/community charge; distinctive nouns first; no procedural boilerplate like "stage 1"/"debate"/"bill" that dilutes `ts_rank`), and the STOP-SEARCH rule permits one retry on ZERO **or** off-topic results, reformulated to the official term (`search_budget` unchanged). Re-measured: raw ~85% → ~88% (Win 1 removes the 0-result cliff); with reformulation all residual misses recover; no reformulation-resistant miss survived.
- **Filter enforcement** — `_apply_parliament_filters` in `parliament.py` maps the frontend **Record type** filter (`debates` / `written_answers` / `committee`) and **Date range** onto the Scottish tools: `debates` redirects `search_scottish_parliament` → `search_scottish_plenary` (the full-text route); `written_answers` sets `debate_type='written_answers'` on `search_scottish_parliament`; `committee` short-circuits `search_scottish_parliament`/`search_scottish_plenary` with a redirect to `search_scottish_committee_transcripts`; the date range is merged into all three SP search tools. There is no longer a "Legislature" filter.
- **Search budget** — `run_worker_agent` creates `search_budget = {"remaining": 3}` for `parliamentary_records` mode and passes it to every `run_worker_tool` call. When the budget hits 0, `run_worker_tool` returns a hard-stop JSON message instead of calling the API, forcing the model to proceed to Phase 2. The budget covers `search_scottish_plenary`, `search_scottish_parliament`, and `search_scottish_committee_transcripts`. Without this cap, weaker models loop on search tools indefinitely.
- **Debate title extraction** — `_slim_hansard_results` extracts debate titles from `speech.parent.body` (not `speech.debate`, which is always empty). The `parent.body` field is HTML so it is run through `_strip_html` (which calls `html.unescape`).
- **Phase 2 nudges** — After each `search_scottish_plenary` result, a nudge lists `meeting_id`, `slug`, and `iob_id` values for `get_scottish_plenary_debate`. After each `search_scottish_committee_transcripts` result, a nudge lists the same for `get_scottish_committee_transcript`. After each `search_scottish_parliament` result, an excerpt-only nudge tells the model not to attempt full-text retrieval and to synthesise from the excerpts. All reinforce the search budget stop.
- **TWFY API key** — Set via `TWFY_API_KEY` env var (free key from theyworkforyou.com/api/key). Required for `search_scottish_parliament` and `get_member_info` (both use TWFY). If missing, `search_scottish_parliament` returns a clear error.
- **SP committee transcript database** — `search_scottish_committee_transcripts` queries the local `sp_committee_items` PostgreSQL table via GIN full-text search rather than scraping parliament.scot live. The table is populated by `parliament_crawler.py` which runs two background tasks on startup (when `RESEARCH_MODE=parliamentary_records`): a one-shot `backfill_sessions()` and a daily `background_crawl_loop()`. Rate-limited to ~1.5 req/s. **The crawl is incremental (see the "Incremental crawl model" note below):** `backfill_sessions()` walks from Session 6 start only on an empty DB (high-water-mark start otherwise), and the daily loop is a trailing-window delta, not a full re-crawl. If the table is empty the tool returns a graceful message telling the model to try `search_scottish_parliament` instead. The old `list_scottish_committee_meetings` tool (live scrape, ~2-week window, no keyword search) has been removed and replaced entirely by this DB-backed tool.
- **Incremental crawl model** — the crawler avoids re-walking the full back-catalogue on every restart. (1) **Adaptive backfill start** (`_backfill_window_start`): full Session-6 backfill only when the target table is empty; on a populated DB it starts ~2 weeks (`_HIGH_WATER_OVERLAP_DAYS`) before the newest stored `meeting_date`, so a restart re-scans only recent windows (~minutes, not ~17h). (2) **Trailing-window daily delta**: `crawl_sp_new_meetings`/`crawl_sp_new_plenary` re-scan the last `_DELTA_WINDOW_DAYS` (30) and *reprocess* every meeting in that window — catching new sittings **and** late-published transcripts / newly-added agenda items on already-seen meetings. Per-item `(meeting_id, iob_id)` existence checks keep completed transcripts from being re-fetched; committee & plenary both **skip empty (not-yet-published) items** so they retry until the Official Report publishes them. This recency-window re-scan is necessary because the source sends **no `Last-Modified`/`ETag`** (Cloudflare `no-cache, no-store`) — there is no cheap HTTP "has this changed?" signal, so change detection is driven by our own stored state. Not yet covered: revisions to *finalised* transcripts outside the 30-day window (add a `full_text` content hash + bounded re-fetch if that becomes important).
- **SP plenary transcript database** — `search_scottish_plenary` queries the local `sp_plenary_items` PostgreSQL table via GIN FTS (same schema/mechanism as `sp_committee_items`, unique constraint `uq_sp_plenary_meeting_iob`, one row per agenda item keyed `(meeting_id, iob_id)`). Populated by `parliament_crawler.py`'s `backfill_plenary()` (one-shot, `showPlenary=true&dateSelect=custom` date-windowed listing) and `background_plenary_crawl_loop()` (daily rolling; self-staggered 5 min after startup so it doesn't hit the origin concurrently with the committee crawl). Uses `_parse_sp_plenary_meetings` (includes `meeting-of-parliament-*` slugs the committee parser excludes) and `_parse_sp_plenary_transcript`. Plenary item pages are large (200–700 KB) and the origin intermittently serves an ~8 KB Cloudflare **524** error page, so transcript fetches use `_fetch_sp_page_with_retry` (4 attempts, exponential backoff, rejects <20 KB responses, forces UTF-8 to avoid replacement chars). If the table is empty `search_scottish_plenary` returns a graceful note telling the model to use `search_scottish_parliament`. **Note:** `main.py` runs `backfill_sessions()` then `backfill_plenary()` sequentially so the two one-shot backfills don't hammer the origin.
- **Import-depth note (regression fixed)** — DB-access functions in `agent/tools/parliament.py` import `from ...database import async_session_maker` (three dots → `src.database`). When this code was split out of the former single-file `src/agent/tools.py` into the `src/agent/tools/` package it moved one level deeper, but the committee function's import was left at two dots (`..database` → the non-existent `src.agent.database`), silently breaking `search_scottish_committee_transcripts` under `uvicorn src.main:app`. Fixed to three dots for all DB imports in this module.
- **SP TV video deep links (dark-launched behind `ENABLE_VIDEO_DEEPLINKS`)** — when a plenary citation is retrieved via `get_scottish_plenary_debate`, each speech that matches the video captions gets a `video_deeplink` (`?clip_start=HH:MM:SS&clip_end=…`) attached, turning an Official Report citation into a timestamped SP TV link. Fully additive and fail-soft — off by default, and any resolution failure just omits the link. Pipeline: `sptv_client.py` resolves meeting date → SP TV slug (`meeting-of-the-parliament-{month}-{day}-{year}`, **different** from the Official Report slug) → `eventId` → `/Player/PlaybackModel/` → HLS master → WebVTT caption playlist, and builds a cached `(transcript, offset_index)` stored in `sp_video_captions` (one row per event, keyed to plenary meetings by `meeting_id`). `caption_match.py` does the text→time match at render time. `parliament_crawler.backfill_captions()` caches captions for all crawled plenary meetings (staggered after `backfill_plenary()`); the rolling plenary crawl caches new meetings via `_capture_meeting_captions()`.
  - **Timing = segment ordinal × 6s, using the TRUE HLS playlist index — NOT caption-stream MPEGTS transitions.** Each WebVTT segment is `EXTINF:6`; the single `#EXT-X-PROGRAM-DATE-TIME` value anchors the timeline. **Gotcha the PoC got wrong:** ~7% of segments carry no captions (171 of 2317 in the validation sitting), so counting *caption-stream* MPEGTS transitions as the ordinal (what `poc_final2.js` did) undercounts and puts speeches minutes too early. `sptv_client` uses each segment's real index in the playlist (`seg_index`), verified against the Official Report's own embedded time markers. (The PoC's reported `14:56:52` for the 2 June 2026 "Phone-free Classrooms" statement was ~6 min early; the correct value is `15:02:46`, matching the OR's `15:02` marker.)
  - **Rarest-phrase match, anchored to the agenda item.** For each speech, pick the caption phrase with the fewest occurrences and only accept matches at/after the item's first distinctive speech — boilerplate openings recur all afternoon and cause false matches to earlier occurrences. `clip_start` is real Europe/London wall-clock (DST-correct via `zoneinfo`; the PoC hard-coded a fixed +1h BST offset).
  - **Plenary (v1) + committee (v2).** Plenary slug derives from the date; committees can't (several meet the same day), so `sptv_client.resolve_committee_event` queries the **SP TV archive date-filter** (`/archive?DateFrom=DD/MM/YYYY&DateTo=…`), which lists each event with the committee name in the link text, and matches on `committee_name` to disambiguate → meeting page → eventId. Everything downstream of eventId is shared with plenary. Committee captions are cached by `parliament_crawler.backfill_committee_captions()` (+ the rolling committee crawl hook, via `_capture_meeting_captions(..., committee_name=...)`) and `get_scottish_committee_transcript` attaches the links. YouTube-hosted events (`is_youtube`) have no caption track in practice, so they get no link.
  - **Committee parser unified with plenary (`_parse_sp_transcript_page` deleted).** The old committee transcript parser returned a single unnamed blob on current committee pages (the whole meeting → one row, `speaker=""`, ~1 "speech"/item), because committee pages now use the same `<p id="orscontributions_...">` markup as plenary. **Both** the retrieval tool (`get_scottish_committee_transcript`) **and** the crawler (`_process_meeting`) now parse committee pages with `_parse_sp_plenary_transcript`; `_parse_sp_transcript_page` was removed entirely (def + import + re-export). Session 6+7 committee data was deleted and re-crawled under the fixed parser — attribution went from ~1 speech/item to ~13 (max ~290), all with named speakers. This also fixes committee FTS quality (`full_text` now contains real per-speaker speeches).
  - **Empirical coverage (full Session 6+7 backfill, Jul 2026).** ~2,400 committee + ~3,600 plenary agenda items crawled across Session 6+7 (2021→2026). ~1,140 SP TV events cached in `sp_video_captions`; **~540 (~47%) have a usable caption track** (`caption_ok=true`) and can produce video links — the rest are older sittings with no subtitle track (`caption_ok=false`, fail-soft, no link). Caption availability skews strongly toward more recent sittings; many pre-2024 events lack captions.

### Federation System
Multiple specialised bots (each a separate FastAPI process + DB) can consult each other via `POST /api/consult`. The calling Manager agent gets a `consult_peer` tool injected alongside `delegate_research` — but only when at least one enabled peer is registered. With zero peers, behaviour is identical to today.

Key design decisions:
- **`peer_bots` DB table** — stores peer registry; managed via Admin Portal → Federation tab or `POST/PUT/DELETE /api/peers`
- **`bot_config.json`** — each bot has an identity file (`bot_id`, `name`, `tagline`, `logo_path`) and an optional `peer_registry_seed` list loaded on startup (insert-or-ignore by `peer_id`). Path set via `BOT_CONFIG_PATH` env var.
- **`get_manager_tools(peer_descriptions)`** in `tools.py` — builds the manager tool list dynamically. Returns the same list as the old hardcoded `MANAGER_TOOLS` when `peer_descriptions` is empty; appends `consult_peer` when peers exist.
- **Depth limit** — `ConsultRequest.depth` is incremented by the caller. Any request arriving with `depth >= 2` gets HTTP 422 immediately — prevents A→B→C cascade loops.
- **`api_key` is write-only** — stored in `peer_bots.api_key`; never returned by any API response (treat like a password).
- **`/api/consult` is synchronous JSON** (not SSE) — the calling Manager blocks until the full peer answer is returned before synthesising its response.
- **Identity endpoints** — `GET /api/bot-info` (no auth) returns `bot_id`, `name`, `tagline`; `GET /api/bot/logo` streams the logo file. Frontend fetches these on mount and uses them for dynamic branding.
- **Local dev** — see `docs/deployment/LOCAL_SETUP.md` for running multiple bots on one machine. `deployment/local/` is gitignored (holds per-machine `active_bots.txt` and `shared.env`).
- **Parliament bot DB** — `lexchat_parliament` (set in `bots/parliament/.env`). `start_federation_dev.ps1` creates this DB automatically. The script loads `bots/parliament/.env` first, then overrides `BOT_ID` and `BOT_CONFIG_PATH` with absolute paths so the relative path in the `.env` file doesn't win.
- **`BOT_CONFIG_PATH` note** — uvicorn runs from `server_py/`, so `os.path.abspath(path)` resolves relative paths relative to `server_py/`. The federation dev script sets this to an absolute path to avoid the ambiguity.
- **Cross-bot routing in manager prompts** — `MANAGER_SYSTEM_PROMPT` (legislation bot) has a SCOPE block instructing the manager to use `consult_peer` for parliamentary debate questions (Hansard, committee scrutiny, bill progress) rather than deflecting the user. `PARLIAMENT_MANAGER_SYSTEM_PROMPT` has a matching SCOPE block instructing the parliament manager to use `consult_peer` for legislation text questions (Act provisions, definitions, commencement dates) rather than refusing. Both prompts only mention `consult_peer` — the tool is silently absent when no peer is registered, so the instructions are harmless in single-bot deployments.
- **"No results" vs "unavailable" distinction** — the legislation manager SCOPE explicitly instructs: if `consult_peer` was called but the Parliament Bot returned no records, tell the user "the Parliament Bot found no records of debate on this topic" — do NOT say parliamentary research is "unavailable in this session" (that phrase is reserved for when no parliament peer is registered at all).
- **`PUT /api/peers/{peer_id}` uses the string peer_id** — e.g. `PUT /api/peers/parliament_bot`, NOT `PUT /api/peers/1` (the numeric DB row ID returns 404). The peer registry seed in `bot_config.json` uses 409-skip logic — it does NOT update existing records, so if a peer was seeded with `enabled: false`, you must PUT to enable it manually.

### External API Dependencies

All external APIs called at query time. URLs must be reachable from the deployment target.

| API | Base URL | Used by | Auth | Notes |
|---|---|---|---|---|
| LEX API | `https://lex.lab.i.ai.gov.uk` | Legislation bot | None (internal) | POST endpoints: `/legislation/search`, `/legislation/section/search`, `/legislation/text` |
| National Archives case law | `https://caselaw.nationalarchives.gov.uk` | Legislation bot (case law mode) | None | `search_case_law`: `GET /atom.xml` with `query`, `court`, `date_from`, `date_to` params; returns Atom XML. `get_case_law_text`: `GET /{case-path}/data.xml` to fetch full judgment text (LegalDocML/AKN XML) |
| TheyWorkForYou (TWFY) | `https://www.theyworkforyou.com/api` | Parliament bot | `TWFY_API_KEY` | Endpoints: `getHansard` (Scottish Parliament plenary/written answers — post-filtered to `/sp/` listurls) and `getMSPs` (`get_member_info`). Westminster endpoints are no longer used. |
| Scottish Parliament Bills | `https://data.parliament.scot/api/bills` | Parliament bot | None | `search_bills`; full list fetched, filtered client-side (no server-side search param) |
| SP Official Report | `https://www.parliament.scot/chamber-and-committees/official-report/search-what-was-said-in-parliament` | Parliament bot crawler + `get_scottish_plenary_debate`/`get_scottish_committee_transcript` | None | Crawled by `parliament_crawler.py` at startup and daily; three request types on the same base URL: (1) listing page with `showCommittee=true` (committee) or `showPlenary=true` (plenary), plus `dateSelect=custom&dtDateFrom=X&dtDateTo=Y`; (2) meeting detail pages at `/{slug}?meeting={id}`; (3) individual transcript pages at `/{slug}?meeting={id}&iob={iob_id}`. The two `get_scottish_*` retrieval tools also fetch (3) live at query time |
| OpenRouter | `https://openrouter.ai/api/v1` | Both (optional) | `OPENROUTER_API_KEY` | Only when OpenRouter is set as active provider in Admin Portal |
| SP TV (video deep links) | `https://www.scottishparliament.tv` + `https://scotparl-live.cdn.vustreams.com` | Parliament bot (when `ENABLE_VIDEO_DEEPLINKS=true`) | None | `GET /meeting/{slug}` (eventId), `GET /Player/PlaybackModel/{eventId}` (streams), HLS `.m3u8` + WebVTT caption segments. Both hosts must be whitelisted on the target or the feature auto-disables (fails soft to the plain Official Report citation) |

To verify all endpoints are reachable from a deployment target, run `server_py/test_apis.ps1` (reads `TWFY_API_KEY` from `.env`; TWFY tests skip gracefully if the key is absent).

### Per-Bot Efficiency Measurement
The Admin Portal → Efficiency tab and the per-request EFFICIENCY breach alerts are **mode-aware** — the same codebase grades the legislation bot and the parliament bot against different baselines, selected by `RESEARCH_MODE` (`settings.research_mode`).

- **`EFFICIENCY_PROFILES` in `config.py`** replaces the old single `EFFICIENCY_THRESHOLDS` dict. It is keyed by mode (`"legislation"` / `"parliamentary_records"`); `get_efficiency_profile()` selects one from `settings.research_mode` (blank/unknown → `"legislation"`). Each profile holds the per-request breach rules **and** the dashboard indicator bands (`(warn_at, bad_at)` cut-points read by `stats.py:_band()`). The legislation profile's values are byte-for-byte the old thresholds/bands, so a legislation-bot process is numerically unchanged. The parliamentary band values are **unmeasured starting points** — re-tune once real traffic accumulates.
- **Fan-out denominator differs by mode.** Legislation: `phase2_retrieval_calls / sources_kept`. Parliamentary: `phase2_retrieval_calls / distinct_legislation_ids_retrieved` (retrievals per distinct SP transcript ≈ 1). The profile names the column in `fanout_denominator`; `get_efficiency_stats` **allowlist-validates** it (`{"sources_kept", "distinct_legislation_ids_retrieved"}`) before interpolating into its f-string SQL.
- **`search_budget_blocked`** is a new `request_timings` column + `TimingCollector` counter: incremented in `run_worker_tool` when a parliamentary search is hard-stopped because the search budget (3) was already exhausted — the model looped on discovery instead of retrieving. Budget-blocked calls are counted **separately** (not in `worker_tool_calls`/phase counts). On the parliament bot the profile adds a `max_budget_blocked: 0` breach rule, a `budget_exhaustion` dashboard indicator, and makes `search_budget_blocked DESC` the first ORDER BY key in the Worst-Offenders table.
- **Phase classification / distinct-retrieval fixes** (`stopwatch.py`): `search_scottish_plenary` + `search_bills` are Phase-1; `get_scottish_plenary_debate` is Phase-2 (`get_member_info` deliberately unclassified). `distinct_legislation_ids_retrieved` is now a generic "distinct primary resources retrieved" counter (Acts/judgments **or** SP transcripts) — column name kept for back-compat. The redundancy/distinct key for transcripts is the composite `meeting_id:iob_id` (two agenda items of one meeting are legitimate distinct retrievals, **not** redundant).
- **Additive-only, no backfill.** New columns default to 0/NULL via `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`. Existing parliament-bot rows keep their old miscounted phase/redundant values; per-mode trends are only trustworthy from this change onward. `/api/stats/efficiency` gains additive keys only (`kpi.avgBudgetBlocked`, top-level `researchMode`, `worst[].budgetBlocked`) and returns the selected profile in `thresholds`.

### Other
- Python deps are installed **globally** (no venv) on the target — the offline installer uses `pip install` directly
- The frontend is **pre-built on the dev machine** and committed including `client/dist/` — the target has no Node.js
- The backend serves the pre-built `client/dist` as static files

## Dev Machine Setup
- Portable Node.js v22.15.0 lives at `C:\Users\rhett\node_portable\node-v22.15.0-win-x64`
- Add to PATH before running npm: `export PATH="/c/Users/rhett/node_portable/node-v22.15.0-win-x64:$PATH"`
- Use bash (Git Bash) for shell commands — not PowerShell or cmd — as the Claude Code shell
- To run `.cmd` scripts from bash: `cmd //c "C:\Projects\LexChat\deployment\start_native.cmd"`
- Locally there are no SSL certs, so the app runs on **HTTP port 8000** (not HTTPS 443)
- The start script emits harmless `find` errors (bash/cmd `find` mismatch) — PostgreSQL still starts correctly
- PostgreSQL credentials are the same locally and on the target: `lexuser`/`lexpassword`/`lexchat`

## Environment Variables (server_py/.env)
| Variable | Purpose | Default |
|---|---|---|
| `OLLAMA_BASE_URL` | Ollama endpoint | `http://localhost:11434` |
| `OLLAMA_API_KEY` | Bearer token for cloud-routed Ollama | *(blank)* |
| `OPENROUTER_API_KEY` | OpenRouter API key | *(blank)* |
| `OPENROUTER_BASE_URL` | OpenRouter endpoint | `https://openrouter.ai/api/v1` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://lexuser:lexpassword@localhost:5432/lexchat` |
| `JWT_SECRET` | Auth token signing key | `dev_secret_key_change_me` |
| `BOT_ID` | This bot's identifier (used by `/api/bot-info` fallback) | `legislation_bot` |
| `BOT_CONFIG_PATH` | Path to `bot_config.json`; resolved relative to CWD (uvicorn runs from `server_py/`) | *(blank — identity not loaded)* |
| `RESEARCH_MODE` | Override research mode for this bot instance; set to `parliamentary_records` for the parliament bot | *(blank — uses frontend value)* |
| `TWFY_API_KEY` | TheyWorkForYou API key for the Scottish Parliament tools; free at theyworkforyou.com/api/key | *(blank)* |
| `ENABLE_VIDEO_DEEPLINKS` | Parliament bot only: enable SP TV video timestamp deep links (caption crawl + link enrichment on plenary citations). Dark-launched — off by default | `false` |
| `SPTV_BASE_URL` | Scottish Parliament TV base URL (meeting pages + playback model) | `https://www.scottishparliament.tv` |

All `.env` values are startup defaults only. Provider-specific settings (base URL, API key, model, temperature, concurrency) can be overridden at runtime via Admin Portal → Developer tab and are persisted in the DB.

## Deployment Workflow
The **only** way to deploy to the target server is via GitHub — the target does a `git pull` from `origin/main`. There is no direct file transfer or zip-based deployment.

1. Make changes to `client/src/`
2. Build: `npm run build` (in `client/`)
3. Commit **including** `client/dist/` (force-add — it is gitignored): `git add -f client/dist/`
4. Push to `origin main`
5. On the target: `git pull`, then restart with `stop_native.cmd` and `start_native.cmd`

Always commit and push together in the same step — uncommitted or unpushed changes are invisible to the target.

## Start / Stop
| Action | Script |
|---|---|
| Start | `deployment\start_native.cmd` |
| Stop | `deployment\stop_native.cmd` |

Start script launches PostgreSQL, then Ollama, then the FastAPI backend. Stop script kills uvicorn, Ollama, and the PostgreSQL Windows service.

## Frontend Design System

The full token/component reference lives at `docs/frontend/design-system.md`. **Read it before writing any new frontend UI.** Key rules:

- Use design token classes — never raw Tailwind palette values (`text-blue-600`, `bg-zinc-800`, `text-gray-500`, etc.)
- **`bg-brand` ≠ `bg-accent`** — `bg-brand` is for primary CTA button backgrounds; `bg-accent` is for focus rings, active indicators, and selected states only. Mixing these up is the most common mistake.
- `bg-brand-navy` / `hover:bg-brand-navy-dark` are **old non-token classes** that no longer exist — replace with `bg-brand` / `hover:bg-brand-hover`.
- Token-backed classes (`text-ink-*`, `bg-paper`, `bg-brand`, etc.) switch for dark mode automatically — no `dark:` variants needed for colour.
- All button labels, inputs, and UI chrome use `font-ui`; legal content uses `font-serif`.

### Button quick-reference

| Variant | Key classes |
|---|---|
| Primary | `bg-brand hover:bg-brand-hover text-white font-ui text-sm font-medium rounded-md px-4 py-2 focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed` |
| Secondary | `bg-paper border border-ink-200 text-ink-900 font-ui text-sm font-medium rounded-md px-4 py-2 hover:bg-ink-50 focus-visible:ring-2 focus-visible:ring-accent` |
| Danger | `bg-danger text-white font-ui text-sm font-medium rounded-md px-4 py-2 hover:opacity-90 focus-visible:ring-2 focus-visible:ring-danger` |
| Icon | `size-[30px] flex items-center justify-center rounded-md text-ink-500 hover:bg-ink-100 hover:text-ink-900 focus-visible:ring-2 focus-visible:ring-accent` |
| Filter pill (active) | `bg-accent text-white border-transparent rounded-full px-3 py-1 font-ui text-xs` |
| Filter pill (inactive) | `border border-ink-200 text-ink-600 rounded-full px-3 py-1 font-ui text-xs hover:bg-ink-50` |

## Key Files
| File | Purpose |
|---|---|
| `client/src/App.jsx` | Main frontend app — chat UI, favicon swap, dynamic model fetch, dynamic bot branding, post-login notice gate |
| `client/src/components/DataSensitivityNotice.jsx` | Post-login splash screen — data sensitivity warning shown on every login session |
| `docs/frontend/design-system.md` | Design token reference — colours, typography, button/component patterns |
| `client/src/pages/AdminPortal.jsx` | Admin portal including Developer tab (provider config) and Federation tab (peer registry CRUD) |
| `client/src/pages/Settings.jsx` | Account settings page — change password form |
| `server_py/src/config.py` | `MODEL_LIST`, `OPENROUTER_MODEL_LIST`, system prompts, app settings; `bot_id`/`bot_config_path` |
| `server_py/src/agent/tools/` | Tools package (split from the former single-file tools.py; `__init__.py` re-exports the full surface): `schemas.py` (tool schemas, `get_manager_tools`, `get_worker_tools`), `lex.py` (`_slim_search_results`, jurisdiction matching), `parliament.py` (`execute_parliament_tool`, `_slim_hansard_results`, `_search_committee_transcripts_db`, `_search_plenary_db`, `_or_tsquery` OR-fallback helper, `_fetch_sp_page_with_retry`, SP HTML parsers incl. `_parse_sp_plenary_transcript`/`_parse_sp_plenary_meetings`), `caselaw.py` (Atom/AKN parsing), `executor.py` (`execute_worker_tool`) |
| `server_py/src/agent/agent_shared.py` | Shared worker tool execution pipeline; `run_worker_tool` (includes `search_budget` enforcement for parliamentary mode, phase 2 nudges for all search tools) |
| `server_py/src/services/parliament_crawler.py` | Background crawler — **incremental** (see "Incremental crawl model"): committee `backfill_sessions()` (one-shot, adaptive start via `_backfill_window_start`) + `crawl_sp_new_meetings()` (daily trailing-window delta, `background_crawl_loop()`); plenary `backfill_plenary()` + `crawl_sp_new_plenary()` (`background_plenary_crawl_loop()`, self-staggered); shared `_fetch_window_meetings()` date-window helper; video: `backfill_captions()`/`backfill_committee_captions()` + `_capture_meeting_captions()` hook (staggered after plenary backfill; gated on `ENABLE_VIDEO_DEEPLINKS`); reuses HTML parsers from the tools package; only runs when `RESEARCH_MODE=parliamentary_records` |
| `server_py/src/agent/ollama_client.py` | Ollama agent implementation (chat_loop, worker, summarisation, federation) |
| `server_py/src/agent/openrouter_client.py` | OpenRouter agent implementation (OpenAI-compatible, federation) |
| `server_py/src/agent/provider_factory.py` | Provider resolution, ContextVar config, queue/semaphore caches; `get_summarise_model()` |
| `server_py/src/agent/federation_client.py` | `load_peer_registry`, `build_peer_descriptions`, `consult_peer`; `ConsultRequest`/`ConsultResponse` |
| `server_py/src/routers/ai.py` | `/api/models` and `/api/chat` endpoints |
| `server_py/src/routers/developer.py` | Developer-only endpoints including provider config GET/POST and `GET /developer/activity-log` |
| `server_py/src/routers/identity.py` | `GET /api/bot-info`, `GET /api/bot/logo` — no auth required |
| `server_py/src/routers/federation.py` | `POST /api/consult` — receives peer consultation requests |
| `server_py/src/routers/peers.py` | Admin CRUD for peer registry — `api_key` never returned |
| `server_py/src/models.py` | SQLAlchemy models — includes `AppSetting`, `Chat.provider`, `Message.model/provider`, `ActivityLog`, `PeerBot`, `SpCommitteeItem` (SP committee transcript DB with GIN FTS index on `full_text`), `SpPlenaryItem` (SP plenary transcript DB, same schema; GIN FTS on `full_text`; unique `uq_sp_plenary_meeting_iob`), `SpVideoCaption` (one row per SP TV event; cached caption `transcript` + `offset_index` for video deep links; unique `event_id`) |
| `server_py/src/services/sptv_client.py` | SP TV client — `plenary_slug_for_date`, `resolve_event` (meeting page → eventId), `get_playback_model`, `fetch_caption_transcript` (HLS → WebVTT → `(transcript, offset_index)` using **segment-ordinal × 6s** timing). All fail-soft |
| `server_py/src/services/caption_match.py` | Caption matcher — `match_speech`, `build_deeplink`, `annotate_speeches`; rarest-phrase match anchored to the agenda item, real Europe/London DST for `clip_start`. Unit-tested against `tests/fixtures/sptv_captions_20164.json.gz` |
| `client/src/components/ActivityLogModal.jsx` | Admin activity log modal — unified feed of logins, queries, feedback, surveys, errors; auto-refreshes every 10 min |
| `bots/legislation/bot_config.json` | Legislation bot identity + peer seed (default/template bot config) |
| `bots/parliament/bot_config.json` | Parliament bot identity; `research_mode: "parliamentary_records"` under `agent` key |
| `bots/parliament/.env` | Parliament bot env overrides — `RESEARCH_MODE`, `TWFY_API_KEY`, `DATABASE_URL` (`lexchat_parliament`), `PORT=8001` |
| `docs/parliament/PARLIAMENTARY_DATA.md` | Parliamentary data model reference — Holyrood sessions, committee-transcript hierarchy (meeting→agenda item→speeches), `sp_committee_items` schema, and a per-data-type availability matrix (search/retrieval/date-filter/session coverage). Note: crawling older sessions requires `dateSelect=custom` |
| `shared/scripts/new_bot.ps1` | Provision a new bot from the legislation template |
| `shared/scripts/register_peer.ps1` | Register a peer bot via the admin API |
| `docs/deployment/LOCAL_SETUP.md` | Multi-bot local dev workflow |
| `docs/deployment/NATIVE_DEPLOYMENT.md` | Full deployment reference |

## Admin Portal — Developer Tab
Available to the `admin` user only. Contains:
- **LLM Provider panel** — configure both providers (base URL, API key, model, temperature, max concurrent requests, max concurrent summarisations); separate Save Settings and Set as Active buttons
- **Activity Log** — unified feed of user logins, queries submitted, feedback ratings, survey responses, and service health errors; filterable by time range; auto-refreshes every 10 minutes; powered by `GET /developer/activity-log`
- **Synthetic Data Generation** — seed 100 test users with 6 months of chat history
- **Danger Zone** — wipe all data except the admin account

## Admin Portal — Federation Tab
Available to the `admin` user only. Contains:
- **Peer table** — lists all registered peers with name, peer_id, base URL, description, API key indicator, and enable/disable toggle
- **Delete** — removes a peer from the registry immediately
- **Add Peer form** — `peer_id`, `name`, `base_url`, `api_key` (password field, write-only), `description`, `enabled` checkbox
- API key is **never displayed** after save — `has_api_key: true/false` indicator only

## Activity Log
- DB table: `activity_log` (columns: `id`, `event_type`, `username`, `description`, `created_at`); index on `created_at`
- Model: `ActivityLog` in `server_py/src/models.py`
- Currently only `LOGIN` events are written explicitly (in `auth.py` on successful login); `QUERY`, `FEEDBACK`, `SURVEY`, and `ERROR` events are synthesised at query time via UNION ALL from `messages`, `product_feedback`, and `service_health_logs`
- Endpoint: `GET /developer/activity-log?days=7&limit=500` — admin only; `days=all` disables the date filter
- Frontend: `ActivityLogModal.jsx` opened from the Developer tab

## Post-Login Splash Screen
- Shown on every login session, before the main app renders
- Warns users not to enter information above OFFICIAL-SENSITIVE, personal data, privileged communications, ongoing proceedings, information under confidence, or commercially sensitive data
- Explains that queries are processed by third-party LLM services outside the organisation's secure network
- User must click "I understand — proceed to AILA" to dismiss; cannot be bypassed
- State (`noticeAcknowledged`) resets to `false` on logout, ensuring the notice reappears on the next login
- Component: `client/src/components/DataSensitivityNotice.jsx`

## Favicon Behaviour
- On mount: attempts `GET /api/bot/logo` — if the file exists, swaps favicon to it; falls back to `/favicon.svg` silently
- While AI is generating: swaps to animated canvas spinner driven by `requestAnimationFrame`
- On load complete: reverts to `/favicon.svg` (or bot logo on next mount)
- Logic is in two `useEffect`s in `App.jsx` — one watching `loading`, one running once on mount

## Bot Identity & Branding
- `GET /api/bot-info` (no auth) — returns `bot_id`, `name`, `tagline` from `bot_config.json` loaded at startup
- `App.jsx` fetches bot info on mount: sets `document.title` and `botInfo` state; all "AILA" labels in the UI use `{botInfo.name}` (default `'AILA'` if the request fails)
- `GET /api/bot/logo` — streams `bot_identity.logo_path`; 404 if not configured or file missing
- `BOT_CONFIG_PATH` env var → path to `bot_config.json` relative to repo root; if unset, identity is not loaded and defaults apply
