# AILA — AI Legal Research Assistants

A locally-hosted, multi-bot AI research platform for UK government legal departments. Users are qualified lawyers; every answer is grounded in retrieved primary sources with citations.

The product name is **AILA (AI Legal Assistant)**; the repository and its directories are still named *LexChat* for historical reasons. The current release is in [`VERSION`](VERSION); what each release changed is in [`CHANGELOG.md`](CHANGELOG.md).

> **One codebase, many bots.** There is a single backend (`server_py/`) and a single frontend (`client/`). Each bot is the *same* `uvicorn src.main:app` process differentiated by **configuration, not forked code** — its own identity, database, port, research toolset and system prompts. Bots can consult each other over **federation**.

## The bot fleet

| Bot | Identity | `RESEARCH_MODE` | Research sources | Database | Port (dev) |
|---|---|---|---|---|---|
| **Legislation** | AILA | *(blank)* — the research type comes with each request: `legislation_only` (default), `case_law_only` or `legislation_and_case_law` | LEX API (UK legislation), legislation.gov.uk records read through LEX, the made-under record, National Archives Find Case Law; Scottish judgments (SCTS) behind a switch | `lexchat` | 8000 |
| **Parliament (Holyrood)** | ParliChat | `parliamentary_records` | Scottish Parliament plenary & committee Official Report (locally crawled full-text index), SP Bills, TheyWorkForYou, SP TV video | `lexchat_parliament` | 8001 |
| **Westminster** | HansardChat | `westminster_records` | UK Parliament Hansard API, Members API, Bills API | `lexchat_westminster` | 8002 |

Each bot's config lives in `bots/<id>/` — a `bot_config.json` (identity, logo, brand colour, optional peer-registry seed) and a `.env` (its own `DATABASE_URL`, `PORT`, `RESEARCH_MODE`, feature flags). Provision a new bot by copying `bots/legislation/` as a template (`shared/scripts/new_bot.ps1`); see [docs/deployment/LOCAL_SETUP.md](docs/deployment/LOCAL_SETUP.md) for running several bots on one machine.

## Features

### In every bot

**Asking questions**
- **Three chat modes** (sidebar **Mode** menu):
  - **Conversational** — quick answers; the Manager delegates a narrow lookup when it needs a source.
  - **Research** — a full Worker research run per question, with a structured report (summary first, then the detail and references).
  - **Deep Research** — the bot drafts an **editable research plan**; the lawyer adds, removes, reorders or edits the steps, and on approval each step is run in code (one Worker per step, each handed what the earlier steps found) and composed into one integrated report. The approved plan is saved on the answer as an audit record.
- **Manager-Worker agents** — the Manager handles the conversation, triage and clarifying questions, and delegates a self-contained brief to a Worker that retrieves from that bot's sources. The Worker has no chat history, so the brief must stand alone.
- **Research filters** (the **Filters** button) — scope a query by that bot's own dimensions (listed per bot below). Filters are enforced in code on the Worker's tools, not left to the prompt.
- **Suggested question buttons** — follow-up questions and clarification options appear as one-click buttons rather than prose. A button never offers to change a setting, since it can only send text.
- **Mode-change awareness** — when the user changes the chat mode (or, on the legislation bot, the research type) mid-conversation, the next turn is told so.
- **Document upload** — attach PDF, DOCX, TXT or Markdown files to a chat; the extracted text is given to the bot as context.
- **Federation** — with at least one enabled peer registered, the Manager can consult a sibling bot and fold its answer in (who consults whom is listed per bot below). A consulted bot never asks the user a question back. With no peers the tool is simply absent.

**Answers and sources**
- **Sources rail** — a per-answer panel of the sources the answer relies on, each by its title, with an excerpt and a direct link to the authoritative source (legislation.gov.uk, the National Archives, parliament.scot, hansard.parliament.uk).
- **Graceful failure** — if a research step fails, stops at its step limit or loses its reply, the answer says so rather than reporting that nothing was found; provider timeouts and empty replies are retried within bounds.
- **Copy and export** — copy an answer, or export a whole conversation to the clipboard.

**Workspace**
- **Matters** — organise chats into named matters with notes, and generate a brief for a matter (switchable).
- **Chat history** — search and reopen past conversations.
- **Ratings and feedback** — mark an answer helpful or unhelpful (with a comment); rated answers are fed back into later prompts as examples to follow or avoid for similar questions. An end-of-session feedback form and a weekly productivity survey can be switched on.
- **Settings → Data Sources** describes exactly what the bot searches and the limits of each source; **Settings → Release notes** lists each release and shows the version and build the server runs.
- **Data sensitivity notice** to acknowledge before use.

**Administration (Admin Portal)**
- **User Management**, **Usage Stats**, **Performance**, **Cost**, **Learning Monitor**, **Service Health**, **User Feedback**, **Session Feedback**.
- Visible to the built-in `admin` account only: **Efficiency** (per-bot research-efficiency measurement and breach alerts), **Cache** (cache hit rates, savings and the caching switches), **Data Coverage** (Holyrood crawl coverage), **Developer** (LLM provider and model settings, feature flags, transcript export, backup status, scoped **restore** from the nightly backup, the Danger Zone) and **Federation** (the peer registry).
- **Dual LLM providers** — Ollama (a local process proxying cloud-hosted models) or OpenRouter, switched at runtime with no restart; per-provider model, summarisation model, temperature and concurrency.
- **Feature flags** — Matters, Research mode, Deep Research mode, Suggested question buttons, Session feedback form, Weekly user survey, Scottish judgments (SCTS); caching switches on the Cache tab.
- **Caching stack** — provider prompt caching, a per-request tool memo, and a cross-user cache of document summaries keyed on the exact source text and question. All additive, fail-soft and individually switchable.
- **Evaluation endpoint** — `/api/system/chat` mirrors `/api/chat` for the external eval harness and emits a structured `audit` trace (delegations → tools → API calls, with pre- and post-summarisation text).
- **Nightly backup tooling** with a full-read verification, and log redaction of user content at `INFO`.

### Legislation bot (AILA)

**Sources**
- **UK legislation** from the LEX API: Acts of the UK and Scottish Parliaments, Acts and Measures of Senedd Cymru, Acts of the Northern Ireland Assembly, UK, Scottish and Welsh statutory instruments, and retained (assimilated) EU law.
- **Records from legislation.gov.uk**, read through LEX: the record of changes and commencement dates, and the text of an instrument the LEX index does not hold.
- **The made-under record** — a stored record of what each statutory instrument's own preamble says it was made under, covering Scottish SIs from 1999 and UK SIs from 1987 (including Welsh SIs and Northern Ireland Orders in Council), about 87,000 instruments, with a revocation flag for each.
- **Case law** from the National Archives' Find Case Law: UK-wide appellate courts, the higher courts of England & Wales, and UK tribunals.
- **Scottish judgments** from the Scottish Courts and Tribunals Service (Court of Session, High Court of Justiciary, Sheriff Appeal Court, published sheriff court decisions, Scottish tribunals, from 1998) — built, behind the **Scottish judgments (SCTS)** switch, which stays off until the server can reach both SCTS hosts.

**Research types** (Filters → Research type): **Legislation only**, **Case law only**, **Legislation & case law**.

**Filters**: Jurisdiction (England & Wales, Scotland, Northern Ireland, Wales, UK-wide only), Legislation type (Acts, SIs & Rules, Draft instruments), Date range.

**Legislation research**
- Act and SI discovery by search (results carry each instrument's own short summary), then section-level retrieval, with the full text as a fallback. Full-text reads include every schedule and annex; a schedule paragraph asked for by number is fetched directly.
- **Held or not held** — an instrument the question names by number is checked directly in the index (held, held without text, or not held). An instrument the index lacks is read from legislation.gov.uk where possible, and the answer says so; one it cannot read is reported as not held, never as a wrong citation.
- **The record of changes** — which later legislation amended, brought into force, repealed or revoked a provision, with each change kept with the provision that made it. Removals are read by kind: a provision repealed, words removed from a provision that stays, or a repeal that is prospective, temporary or partial.
- **Commencement dates** — where legislation.gov.uk records the date a provision was brought into force, it is given with any qualification (for example "for specified purposes").
- **In-force status only from the record** — never inferred from the version of the text held; "not recorded as commenced" only where the record is complete.
- **What was made under a section** — "which regulations were made under section N of this Act?" returns the full list from the made-under record: the total, each instrument with a link, and whether legislation.gov.uk records it as revoked in whole (by what, and from when), in part, or not at all. No recorded revocation is never presented as "in force".
- **What an instrument was made under** — stated only where the instrument's own words, or the made-under record, say so.
- **Jurisdiction** — the filter applies the "applies in" rule to each result's stated extent. A question that names no jurisdiction is answered for Scotland, and the answer says so; a question about the UK is answered nation by nation.

**Case-law research**
- Results most relevant first, with the true number of matches and working date ranges; the Worker chooses the courts to search for each query.
- **Appellate-decision detection** — where a search returns a case and its appeal, the Worker is pointed to the higher court's decision.
- **A named case the search did not return** is flagged, so its holding is not described as though the judgment had been read.

**Answers**
- **Pinpoint citations** — the subsection or schedule paragraph relied on, linked to that provision. Related subsections and schedule paragraphs the research found are restored to the answer verbatim if the reply drops them, and instruments the answer names carry the links the research found.
- **A search-scope line under every answer** — what was searched and its limits, so a gap in the database is not presented as proof that the law does not exist.
- **Summaries kept to their source** — a long document condensed for the Worker cannot gain case citations the source does not contain.
- **Points of interpretation** are given as a reading, not settled law, unless the provision that applies a general rule was found.
- For questions about what was said in Parliament it consults the parliament bot, when that peer is registered.

### Parliament bot (ParliChat) — the Scottish Parliament

**Sources**
- **Plenary (chamber) debates** — Meetings of the Parliament, by agenda item: debates, ministerial statements, question times, stage proceedings on bills.
- **Committee transcripts** — Holyrood committee meetings, by agenda item.
- Both come from a **locally crawled full-text index** of the Official Report: comprehensive from Session 6 (2021) onwards, kept current by an incremental daily crawl that re-checks recent meetings for late-published transcripts.
- **Written answers** in excerpt form, and **MSP details**, via TheyWorkForYou.
- **Bills** — title, current stage and progress from the Scottish Parliament Bills API.

**Filters**: Record type (Chamber debates, Written answers, Committee transcripts), Session (multiselect, Session 1 to Session 7; defaults to the current session), Date range.

**Research**
- Full-text search with a broadened any-term retry when an exact all-terms search finds nothing, and prompts that steer the Worker to the official Holyrood term (for example "public body", not "quango").
- **Verbatim retrieval** of a whole agenda item with every contribution attributed to its speaker, so a minister's exact words (for example a statement of statutory purpose) can be quoted.
- A capped search budget per research run, and a cap on contributions returned per retrieval so very long items cannot overload the model.
- **SP TV video deep links** (opt-in, `ENABLE_VIDEO_DEEPLINKS`) — a plenary or committee citation gains a timestamped link to the moment in the Scottish Parliament TV recording, where captions exist.
- **Data Coverage** tab in the Admin Portal reports crawl coverage per session.
- Scotland only: questions about Westminster are declined as out of scope. For the text of legislation it consults the legislation bot, when that peer is registered.

### Westminster bot (HansardChat) — the UK Parliament

**Sources**
- **Hansard**, live from the UK Parliament Hansard API: House of Commons and House of Lords chamber debates, statements and questions; Westminster Hall; Public Bill Committees; written statements and written answers.
- **Members** — name, party, constituency and House, from the UK Parliament Members API.
- **Bills** — title, current House and stage, from the UK Parliament Bills API.

**Filters**: House (Both, Commons, Lords), Record type (Chamber debates, Westminster Hall, Public Bill Committees, Written statements, Written answers), Parliament (2005–2010 to the 2024 Parliament; defaults to the current one), Date range.

**Research**
- Relevance-ranked full-text search, then **verbatim retrieval** of a debate section with every contribution attributed, for quoting a Minister's or Member's exact words.
- No local crawl: retrieval is live from the API, so there is no corpus to maintain.
- The same search budget and per-retrieval contribution cap as the Holyrood bot.
- Westminster only: select committee oral evidence is not covered. For Holyrood proceedings it consults the parliament bot, and for the text of legislation the legislation bot, when those peers are registered.

## Coming soon

### The bots as MCP servers

AILA, ParliChat and HansardChat will be callable from outside AI clients such as Claude and Microsoft Copilot over the **Model Context Protocol (MCP)**, so a lawyer can put a question to them from inside those tools. Proposed, not built; the plan is [docs/mcp/MCP_SERVER_PLAN.md](docs/mcp/MCP_SERVER_PLAN.md).

- **One endpoint per bot.** Each bot serves `/mcp` from one shared module, with its tools chosen by `RESEARCH_MODE`. The drafting bot never serves one: its input is unpublished legislative text.
- **Ask the bot.** `ask_aila`, `ask_parlichat` and `ask_hansardchat` run the bot's full research pipeline, so every guard the product applies also applies to the outside client. Each returns the cited answer, a References list and the data-licence attributions. A run that outlasts the client's tool timeout returns a job id, which the client collects with `get_answer`. Deep Research is not offered.
- **Later, if wanted:** direct tools for the data only these bots hold, namely the made-under record and ParliChat's full-text Official Report archive. They need no LLM spend on our side.
- **Auth:** personal access tokens first, scoped to `/mcp` only, expiring and revocable. They work in Claude Code, VS Code Copilot and Copilot Studio. Entra ID OAuth follows for claude.ai and Microsoft 365 Copilot.
- **Controls:** off by default behind a Developer-tab feature flag, with per-user limits. Calls go through the same request queue as the UI and are logged as `source = "mcp"`.
- **Before it ships:** the path-traversal fix and token scope checks; licence questions to TNA (case law) and TheyWorkForYou; network reachability from each client, deferred for now.

## Documents

All project documentation lives under [`docs/`](docs/). `CLAUDE.md` (agent/contributor context), `CHANGELOG.md` and this `README.md` remain at the repository root.

| Document | Purpose |
|---|---|
| [docs/OVERVIEW.md](docs/OVERVIEW.md) | Plain-English overview of the assistants and their features — for non-technical readers and new users |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture reference — context, container, multi-bot, agent-pipeline, Deep Research, caching, federation, data-model, measurement and deployment views (with Mermaid diagrams) |
| [docs/SPECIFICATION.md](docs/SPECIFICATION.md) | Product specification — executive summary, Manager-Worker agent system, features, deployment, roadmap |
| [docs/DESIGN.md](docs/DESIGN.md) | Low-level design — database schema, agent flow, frontend structure |
| [docs/LEGAL_DATA_SOURCES.md](docs/LEGAL_DATA_SOURCES.md) | Legislation and case-law data: what we hold, each gap, and where it could be filled from |
| [docs/NETWORK_AND_DEPENDENCIES.md](docs/NETWORK_AND_DEPENDENCIES.md) | Network access & dependency reference for firewall/proxy allowlisting (installation + runtime endpoints and ports) |
| [CHANGELOG.md](CHANGELOG.md) | What each release changed |
| [docs/TODO.md](docs/TODO.md) | Canonical project todo list — deferred work and open chores |
| [docs/CONCURRENT_RUNS_DURABILITY.md](docs/CONCURRENT_RUNS_DURABILITY.md) | Server-side run durability — deferred design (concurrent runs are in-tab only) |
| **API** | |
| [docs/api/ServerAPISpec.md](docs/api/ServerAPISpec.md) | Server REST/SSE API reference — every `/api` endpoint, request/response shapes, auth |
| [docs/api/AUDIT_TRACE.md](docs/api/AUDIT_TRACE.md) | `/api/system/chat` eval endpoint and the `audit` SSE trace (harness handover spec) |
| [docs/api/LexAPISpec.md](docs/api/LexAPISpec.md) | External LEX API specification (the legislation endpoints AILA calls) |
| **Deployment & operations** | |
| [docs/deployment/NATIVE_DEPLOYMENT.md](docs/deployment/NATIVE_DEPLOYMENT.md) | Native Windows Server 2022 deployment guide — offline install + git-pull updates |
| [docs/deployment/LOCAL_SETUP.md](docs/deployment/LOCAL_SETUP.md) | Local multi-bot (federation) development setup |
| [docs/deployment/BACKUP_RUNBOOK.md](docs/deployment/BACKUP_RUNBOOK.md) | Nightly backup + scoped-restore operating procedure |
| [docs/deployment/README.md](docs/deployment/README.md) | Index of every script in the `deployment/` directory |
| [docs/BACKUP_RESTORE_PLAN.md](docs/BACKUP_RESTORE_PLAN.md) | Backup & scoped-restore design (D14) |
| **Frontend** | |
| [docs/frontend/design-system.md](docs/frontend/design-system.md) | Design-token & component reference — read before writing new UI |
| [docs/frontend/README.md](docs/frontend/README.md) | Guide to the React client |
| **Modes & features** | |
| [docs/deep-research/IMPLEMENTATION_PLAN.md](docs/deep-research/IMPLEMENTATION_PLAN.md) | Deep Research (plan → approve → execute) build spec |
| [docs/LOCAL_PROMPT_CACHE_PLAN.md](docs/LOCAL_PROMPT_CACHE_PLAN.md) | Cross-user local summary cache design (D7) |
| [docs/CACHE_REVIEW_FIXES_PLAN.md](docs/CACHE_REVIEW_FIXES_PLAN.md) | Cache review fixes (D8) — key-query source, cross-user safety, hygiene |
| [docs/CACHE_ADMIN_UI_PLAN.md](docs/CACHE_ADMIN_UI_PLAN.md) | Feature flags + Admin Portal Cache tab (D6) |
| [docs/LOGGING_IMPROVEMENTS_PLAN.md](docs/LOGGING_IMPROVEMENTS_PLAN.md) | Logging & log-redaction plan (PII at INFO vs DEBUG) |
| [docs/LOGGING_PR_D_PLAN.md](docs/LOGGING_PR_D_PLAN.md) | Logging PR D — remaining log work |
| [docs/mcp/MCP_SERVER_PLAN.md](docs/mcp/MCP_SERVER_PLAN.md) | The bots as MCP servers for outside AI clients (Claude, Copilot) — proposed, not built |
| **Pre-pilot defect fixes** | |
| [docs/prepilot-fixes/FIX_PLAN.md](docs/prepilot-fixes/FIX_PLAN.md) | The fix plan, invariants and tickable ledger for the defects found in the pre-pilot sessions |
| [docs/prepilot-fixes/SESSION_LOG.md](docs/prepilot-fixes/SESSION_LOG.md) | What each fix session actually did |
| [docs/prepilot-fixes/BASELINE.md](docs/prepilot-fixes/BASELINE.md) | The measured baseline the fixes are graded against |
| **Parliament bots** | |
| [docs/parliament/PARLIAMENTARY_DATA.md](docs/parliament/PARLIAMENTARY_DATA.md) | Scottish Parliament data model — sessions, transcript hierarchy, availability matrix |
| [docs/parliament/SEMANTIC_RETRIEVAL_PLAN.md](docs/parliament/SEMANTIC_RETRIEVAL_PLAN.md) | Semantic (embedding) retrieval plan — **deferred / NO-GO** |
| [docs/parliament/VIDEO_DEEPLINK_PLAN.md](docs/parliament/VIDEO_DEEPLINK_PLAN.md) | SP TV video deep-link implementation brief (plenary v1) |
| [docs/parliament/VIDEO_COMMITTEE_SPIKE.md](docs/parliament/VIDEO_COMMITTEE_SPIKE.md) | SP TV video deep-links v2 — committee spike brief |
| [docs/parliament/WESTMINSTER_VIDEO_SPIKE_PLAN.md](docs/parliament/WESTMINSTER_VIDEO_SPIKE_PLAN.md) | parliamentlive.tv deep-link feasibility spike |
| [docs/parliament/WESTMINSTER_VIDEO_IMPLEMENTATION_PLAN.md](docs/parliament/WESTMINSTER_VIDEO_IMPLEMENTATION_PLAN.md) | parliamentlive.tv deep-link implementation plan (not built) |
| **Evaluation** | |
| [docs/evals/GOLDEN_QUESTIONS_LEGISLATION.md](docs/evals/GOLDEN_QUESTIONS_LEGISLATION.md) | Golden-question eval set for the legislation bot (DRAFT) |
| [docs/evals/GOLDEN_QUESTIONS_PARLIAMENT.md](docs/evals/GOLDEN_QUESTIONS_PARLIAMENT.md) | Golden-question eval set for the parliament bot (DRAFT) |
| **Planning & releases** | |
| [docs/planning/EFFICIENCY_PER_BOT_PLAN.md](docs/planning/EFFICIENCY_PER_BOT_PLAN.md) | Per-bot efficiency measurement plan (shipped) |
| [docs/planning/PER_REQUEST_EFFICIENCY_PROFILE_PLAN.md](docs/planning/PER_REQUEST_EFFICIENCY_PROFILE_PLAN.md) | Per-request efficiency profiles follow-up (scoped) |
| [docs/planning/agent_performance_analysis.md](docs/planning/agent_performance_analysis.md) | Prompt for generating comparative agent performance tables from logs |
| [docs/releases/2026-07-legislation-bot.md](docs/releases/2026-07-legislation-bot.md) | Release notes, July 2026 — legislation bot (before calendar versioning; later releases are in `CHANGELOG.md`) |
| [docs/releases/2026-07-parliament-bot.md](docs/releases/2026-07-parliament-bot.md) | Release notes, July 2026 — parliament bot |

## Architecture

### Frontend (`client/`)
- React 19 + Vite + Tailwind CSS
- Pre-built and served as static files by the FastAPI backend (no separate Node.js server at runtime)
- Branding is **dynamic** — the client fetches `GET /api/bot-info` and `GET /api/bot/logo` on mount, so the same bundle renders as any bot in the fleet, with that bot's filters, Data Sources screen and notices
- Key components: `App.jsx` (chat UI + SSE consumer), `SourcesRail.jsx` (citations), `DeepResearchPlan.jsx` (editable plan card), `SuggestedQuestions.jsx` (chips), `ResearchFiltersModal.jsx`, `ChatMessage.jsx` (markdown + citations), `DataSourcesModal.jsx` and `ReleaseNotesModal.jsx` (Settings menu), `AdminPortal.jsx` + `pages/admin/*` (per-tab panels)

### Backend (`server_py/`)
- Python 3.11 + FastAPI + uvicorn
- PostgreSQL for persistence (one database per bot)
- Async throughout (SQLAlchemy asyncpg, httpx, asyncio)
- Agent pipeline: `routers/agent_request.py` (shared request models + config) → `provider_factory.py` → `ollama_client.py` / `openrouter_client.py` → `agent_core.py` + `agent_shared.py` → `agent/tools/` package (`lex`, `commencement_dates`, `published_text`, `caselaw`, `scts`, `parliament`, `westminster`, `executor`, `schemas`)
- Answer-seam and research helpers in `utils/` (citation links and restores, search-scope footer, discovery budgets, made-under parsing, revocation and removal classification, schedule units, audit trace, mode-change marker, suggestions)
- Services: `parliament_crawler.py` (Holyrood corpus), `sptv_client.py` + `caption_match.py` (video deep links), `made_under_store.py` (the made-under record), `local_prompt_cache.py`, `backup_restore.py`, `health_service.py`
- `version.py` reads `VERSION` and `git describe` for the version and build shown in the app

### LLM Providers
| Provider | How it works |
|---|---|
| **Ollama** | Local Ollama process acts as a proxy to cloud-hosted models (e.g. `mistral-large-3:675b-cloud`). Models are identified by a `:cloud` suffix. |
| **OpenRouter** | Direct HTTPS to `openrouter.ai` via an OpenAI-compatible API. Requires outbound internet to `openrouter.ai`. |

Active provider and all per-provider settings (base URL, API key, model, summarisation model, temperature, concurrency) are stored in the database and configurable at runtime via Admin Portal → Developer tab. `.env` values are startup defaults only.

### How one codebase behaves as different bots

**Shared (common code):** the entire backend and frontend — agent pipeline (`agent/`), tools, routers, DB models, and the React app. No bot has its own copy.

**Bot-specific (config, not code):** each bot has a directory under `bots/<id>/` holding only config:
- `bot_config.json` — identity (`bot_id`, `name`, `tagline`, `logo_path`, `brand_color`) plus an optional `peer_registry_seed`. Loaded at startup via the `BOT_CONFIG_PATH` env var; drives dynamic branding through `GET /api/bot-info` and `GET /api/bot/logo`.
- `.env` — per-bot overrides: its own `DATABASE_URL` (**separate database per bot**), `PORT`, `RESEARCH_MODE`, feature flags, and any API keys.

Behaviour is then switched at runtime:
- `research_mode` selects the Worker's toolset (`tools/schemas.py::get_worker_tools`) **and** the matching Manager/Worker system prompts. Modes: `legislation_only`, `case_law_only`, `legislation_and_case_law`, `parliamentary_records`, `westminster_records`. A bot's `RESEARCH_MODE` (env) fixes it absolutely (the parliament bots set it); left blank, as on the legislation bot, it comes from the request's research type.
- The same mode decides which background tasks start: the Holyrood bot runs the Official Report crawler; the legislation bot loads and refreshes the made-under record.
- The same mode also selects the bot's **efficiency profile** (`config.py::EFFICIENCY_PROFILES`) — the breach rules and dashboard bands the Admin Portal grades that bot against, since a legislation query and a transcript retrieval have different healthy shapes.
- Each bot is an **independent process** with its own DB and port, and can consult siblings via federation (`POST /api/consult`). The peer registry is per-bot (`peer_bots` table / Admin Portal → Federation tab).

For the full picture — diagrams of the request lifecycle, Deep Research, the caching stack, the parliament data pipeline and the deployment topology — see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Releases

Releases use calendar versions, **`vYYYY.MM.N`** (the Nth release cut in that month). Each is an annotated tag on `main` with a dated section in [`CHANGELOG.md`](CHANGELOG.md); `VERSION` names the last release the code contains. The running version and exact build (`git describe`) appear in **Settings → Release notes**, in `GET /api/bot-info` (`version`, `build`) and in the first line the server logs. The cutting procedure is in `CLAUDE.md` (*Releases*).

## Deployment

The application runs natively on **Windows Server 2022** (no Docker, no WSL, no nginx). The frontend is pre-built on the dev machine and committed to the repository; the target server requires only Python and PostgreSQL. The target is *internet-restricted* — every external host used by the deployed bots must be whitelisted (see [docs/NETWORK_AND_DEPENDENCIES.md](docs/NETWORK_AND_DEPENDENCIES.md)).

See [docs/deployment/NATIVE_DEPLOYMENT.md](docs/deployment/NATIVE_DEPLOYMENT.md) for full deployment instructions (offline installation and the git-pull update workflow), and [docs/deployment/README.md](docs/deployment/README.md) for an index of every deployment script.

### Quick start

Install on the target using the offline bundle (see the offline-install section of NATIVE_DEPLOYMENT.md), then start:
```cmd
deployment\start_native.cmd
```

Then check that pdfplumber is installed:
```cmd
python -c "import pdfplumber"
```
It should print nothing. The current offline bundle does not include pdfplumber, which AILA needs to read uploaded PDFs and Scottish judgments. If the check prints `ModuleNotFoundError`, run `.\deployment\install_pdf_support.ps1` as Administrator, which installs it from wheels committed in the repo, then restart. Details: *Checking pdfplumber is installed* in NATIVE_DEPLOYMENT.md.

The application is served over **HTTPS on port 443**.

Backups are a nightly `pg_dump -Fc` per database (`deployment/backup_databases.ps1`, GFS retention), verified by a full `pg_restore -f NUL` read; restore is done scope-by-scope from the Admin Portal → Developer tab. The scheduled task is installed by `deployment/install_backup_task.ps1`, which needs elevation and has not yet been run on the target. See [docs/deployment/BACKUP_RUNBOOK.md](docs/deployment/BACKUP_RUNBOOK.md).

## Local Development Setup

### Prerequisites
- Python 3.11
- PostgreSQL (`lexuser` / `lexpassword` / `lexchat`); `start_native.cmd` and `stop_native.cmd` expect the Windows service `postgresql-x64-18`
- Ollama running locally, or an OpenRouter API key
- Node.js v22 (a portable install is fine — `deployment/install_node.ps1` sets one up; dev-machine specifics live in `CLAUDE.md`)

### Run the backend

```bash
cd server_py
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8000
```

The backend runs on `http://localhost:8000` (HTTP locally — there are no TLS certs on a dev machine) and serves the pre-built frontend from `client/dist/`.

To run more than one bot locally (and exercise federation), use `deployment/start_federation_dev.ps1` — see [docs/deployment/LOCAL_SETUP.md](docs/deployment/LOCAL_SETUP.md).

### Build the frontend (after source changes)

```bash
# Ensure Node.js v22 is on PATH (see CLAUDE.md for the dev-machine portable install)
cd client
npm install
npm run build
```

Force-add the built dist before committing (it is gitignored):

```bash
git add -f client/dist/
```

### Environment variables (`server_py/.env`, or `bots/<id>/.env` per bot)

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string (one database per bot) | `postgresql://lexuser:lexpassword@localhost:5432/lexchat` |
| `PORT` | Listening port for this bot process | `8000` |
| `JWT_SECRET` | Auth token signing key | `dev_secret_key_change_me` |
| `BOT_ID` | Bot identity key | `legislation_bot` |
| `BOT_CONFIG_PATH` | Path to this bot's `bot_config.json` (relative paths resolve from `server_py/`) | *(blank)* |
| `RESEARCH_MODE` | Fixes this bot's research domain; overrides the per-request value | *(blank → legislation)* |
| `OLLAMA_BASE_URL` | Ollama endpoint | `http://localhost:11434` |
| `OLLAMA_API_KEY` | Bearer token for cloud-routed Ollama | *(blank)* |
| `OPENROUTER_API_KEY` | OpenRouter API key | *(blank)* |
| `OPENROUTER_BASE_URL` | OpenRouter endpoint | `https://openrouter.ai/api/v1` |
| `LEX_API_URL` | LEX legislation API base URL | `https://lex.lab.i.ai.gov.uk/` |
| `TWFY_API_KEY` | TheyWorkForYou key — required by the parliament bot for SP plenary/written-answer search and MSP lookup | *(blank)* |
| `ENABLE_VIDEO_DEEPLINKS` | Opt-in SP TV video deep links (parliament bot) | `false` |
| `ENABLE_WESTMINSTER_VIDEO_DEEPLINKS` | Reserved for parliamentlive.tv deep links (not implemented) | `false` |
| `SCTS_CASELAW_ENABLED` | Default for the **Scottish judgments (SCTS)** feature flag until it is first saved in the Admin Portal; after that the saved flag wins, so this need not be set | `false` |
| `HTTPS_PROXY` | Outbound proxy, where the network requires one | *(blank)* |
| `BACKUP_ROOT` | Where the nightly dumps are written/read — must match the scheduled task's `-BackupRoot` | `C:\LexChatBackups` |
| `PG_BIN` | PostgreSQL `bin` directory (`pg_dump`/`pg_restore`); auto-detected when blank | *(blank)* |
| `LOG_LEVEL` | Log level. **User content and PII are redacted at INFO and appear in full only at DEBUG** — do not set DEBUG on a bot handling sensitive material | `INFO` |
| `EMAIL_USER` / `EMAIL_PASS` | Gmail SMTP credentials for password-reset email (optional) | *(blank)* |

All `.env` values are startup defaults only. Provider settings and feature flags can be overridden at runtime via the Admin Portal and are persisted in the database.

> **Do not add settings to `server_py/.env.native`** — `start_native.cmd` copies it over `.env` on every start, so it is the live config on the target and carries per-machine edits. Tracked changes to it cause merge conflicts on `git pull`.

## Default Admin Credentials

On first run, the database is seeded with:
- **Username**: `admin`
- **Password**: `admin`

Change this immediately in production via Admin Portal → Users.

## API Documentation

When running locally, interactive API docs are available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

See [docs/api/ServerAPISpec.md](docs/api/ServerAPISpec.md) for the full endpoint reference, and [docs/api/AUDIT_TRACE.md](docs/api/AUDIT_TRACE.md) for the machine-to-machine `/api/system/chat` variant used by the eval harness.
