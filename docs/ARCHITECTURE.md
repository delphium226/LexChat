# AILA — Architecture Reference

AILA (product name for the codebase historically called *LexChat*) is an AI legal-research
assistant for a UK government organisation. This document is the architectural reference: it
presents the system through a series of complementary **views**, each with a Mermaid diagram.

For narrative product detail see [SPECIFICATION.md](SPECIFICATION.md); for low-level schema/flow
detail see [DESIGN.md](DESIGN.md); for the authoritative endpoint list see
[api/ServerAPISpec.md](api/ServerAPISpec.md); for firewall/allowlist detail see
[NETWORK_AND_DEPENDENCIES.md](NETWORK_AND_DEPENDENCIES.md).

> **Guiding principle: one codebase, many bots.** There is a single backend (`server_py/`) and a
> single frontend (`client/`). Every bot — the legislation assistant, the Scottish Parliament bot,
> and any future bot — runs the *same* `uvicorn src.main:app`, differentiated by **configuration,
> not forked code**.

---

## 1. System context

Who and what the system talks to. The organisation runs one or more **bot processes**; each serves
qualified-lawyer users and reaches out to LLM providers and research APIs. Bots can consult each
other via federation.

```mermaid
graph TB
    subgraph org["UK Gov organisation (internet-restricted Windows Server 2022)"]
        user["Qualified lawyer<br/>(browser, HTTPS:443)"]
        legbot["Legislation bot<br/>uvicorn + PostgreSQL(lexchat)"]
        parlbot["Parliament bot<br/>uvicorn + PostgreSQL(lexchat_parliament)"]
        user --> legbot
        user --> parlbot
        legbot <-->|"POST /api/consult<br/>(federation)"| parlbot
    end

    subgraph llm["LLM providers (one active at a time)"]
        ollama["Ollama<br/>(local proxy to :cloud models)"]
        openrouter["OpenRouter<br/>openrouter.ai"]
    end

    subgraph research["External research APIs"]
        lex["LEX API<br/>lex.lab.i.ai.gov.uk"]
        tna["National Archives<br/>caselaw.nationalarchives.gov.uk"]
        twfy["TheyWorkForYou<br/>(Scottish plenary + MSPs)"]
        spor["SP Official Report<br/>parliament.scot"]
        spbills["SP Bills<br/>data.parliament.scot"]
        sptv["SP TV<br/>scottishparliament.tv (opt-in)"]
    end

    legbot --> ollama
    legbot --> openrouter
    parlbot --> ollama
    parlbot --> openrouter
    legbot --> lex
    legbot --> tna
    parlbot --> twfy
    parlbot --> spor
    parlbot --> spbills
    parlbot -.->|ENABLE_VIDEO_DEEPLINKS| sptv
```

**Notes**
- The target is *internet-restricted* (whitelist-only outbound), not air-gapped. Each external host
  above must be whitelisted for the corresponding bot — see [NETWORK_AND_DEPENDENCIES.md](NETWORK_AND_DEPENDENCIES.md).
- The parliament bot is **Scotland-only** (Holyrood). Westminster/Hansard sources were removed.

---

## 2. Container / component view (a single bot process)

One uvicorn process serves both the pre-built React UI (static files) and the `/api` backend. The
agent pipeline is provider-agnostic: a `ContextVar` carries the resolved provider config through the
whole async call chain.

```mermaid
graph TB
    subgraph client["Frontend — client/ (React 19 + Vite + Tailwind)"]
        app["App.jsx<br/>chat UI, SSE consumer,<br/>dynamic branding & model fetch"]
        admin["AdminPortal.jsx<br/>Developer / Federation / Efficiency tabs"]
        sources["SourcesRail.jsx / ChatMessage.jsx<br/>citations + markdown"]
    end

    subgraph backend["Backend — server_py/ (FastAPI + uvicorn)"]
        static["Static file serving<br/>client/dist/"]
        subgraph routers["routers/"]
            r_ai["ai.py  /api/chat, /api/models"]
            r_auth["auth.py"]
            r_chats["chats.py / documents.py / matters.py"]
            r_admin["users / stats / learning / developer / feedback / health"]
            r_fed["federation.py / peers.py / identity.py"]
        end
        subgraph agent["agent/"]
            pf["provider_factory.py<br/>ContextVar config,<br/>queue + semaphore caches"]
            oc["ollama_client.py"]
            orc["openrouter_client.py"]
            shared["agent_shared.py<br/>run_worker_tool, nudges,<br/>search-budget, summarisation"]
            tools["tools/ package<br/>schemas · lex · parliament · caselaw · executor"]
            learn["learning.py (RAG feedback)"]
            fedc["federation_client.py"]
        end
        crawler["services/parliament_crawler.py<br/>(parliament bot only)"]
        sptvc["services/sptv_client.py + caption_match.py"]
        models["models.py (SQLAlchemy)"]
    end

    db[("PostgreSQL 15")]
    provider["Active LLM provider<br/>(Ollama | OpenRouter)"]
    extapi["Research APIs<br/>(LEX / TNA / SP sources)"]

    app -->|"SSE / REST"| routers
    admin --> routers
    sources --> app
    static --- app

    r_ai --> pf
    pf --> oc
    pf --> orc
    oc --> shared
    orc --> shared
    shared --> tools
    tools --> extapi
    r_ai --> learn
    r_fed --> fedc
    routers --> models
    models --> db
    crawler --> db
    crawler --> extapi
    tools --> sptvc
    oc --> provider
    orc --> provider
```

**Key design points**
- **Provider abstraction** — `ollama_client.py` and `openrouter_client.py` each implement the same
  ReAct `chat_loop`; `agent_shared.py` holds the shared tool-execution + summarisation pipeline. The
  active provider is resolved per request from the `app_settings` table and carried by a `ContextVar`
  — no function signatures change when the provider switches.
- **Per-provider concurrency** — a `RequestQueue` (`max_concurrent_requests`) and a summarisation
  `asyncio.Semaphore` (`max_summarise_concurrency`) are cached per `(provider, concurrency)` and
  recreated automatically when settings change.
- **No global auth middleware** — every protected route declares `Depends(get_current_user)`
  explicitly. Public routes: `/api/auth/login`, `/api/health`, and the identity endpoints.

---

## 3. One codebase, many bots

Behaviour is switched at runtime by configuration under `bots/<id>/`, not by branching code.

```mermaid
graph LR
    code["Shared code<br/>server_py/ + client/"]

    subgraph cfgL["bots/legislation/"]
        cL["bot_config.json<br/>(identity + peer seed)"]
        eL[".env<br/>DB=lexchat · PORT=8000<br/>RESEARCH_MODE=(blank)"]
    end
    subgraph cfgP["bots/parliament/"]
        cP["bot_config.json"]
        eP[".env<br/>DB=lexchat_parliament · PORT=8001<br/>RESEARCH_MODE=parliamentary_records"]
    end

    code --> procL["Legislation bot process<br/>legislation & case-law toolset"]
    code --> procP["Parliament bot process<br/>Scottish Parliament toolset"]
    cfgL --> procL
    cfgP --> procP
    procL <-->|federation| procP
```

`RESEARCH_MODE` (env) → `research_mode` drives two things:
`tools/schemas.py::get_worker_tools(mode)` selects the Worker toolset, and the matching system
prompt is chosen. Modes: `legislation_only`, `case_law_only`, `legislation_and_case_law`,
`parliamentary_records`. Each bot is an independent process with its **own database and port**.

---

## 4. Request lifecycle — Manager / Worker (sequence)

The Manager handles conversation and delegates deep research to the Worker. The Manager streams
tokens to the browser over SSE; the Worker's intermediate reasoning is not streamed.

```mermaid
sequenceDiagram
    autonumber
    participant U as Browser
    participant AI as routers/ai.py
    participant Q as RequestQueue
    participant M as Manager (chat_loop)
    participant L as learning.py (RAG)
    participant W as Worker (run_worker_agent)
    participant T as tools/ + external API
    participant S as Summariser

    U->>AI: POST /api/chat (SSE)
    AI->>Q: enqueue (max_concurrent_requests)
    Q-->>M: slot free → process_user_request()
    M->>L: fetch relevant past feedback
    L-->>M: gold / warning examples (injected into prompt)
    M-->>U: stream tokens (triage)
    alt conversational / ambiguous
        M-->>U: answer or clarifying question
    else clear legal query
        M->>W: delegate_research(self-contained brief)
        Note over W: fresh history — no chat context
        loop Phase 1..2 (batched, parallel)
            W->>T: search_* / get_* (asyncio.gather)
            T-->>W: raw results
            alt result > 8k chars
                W->>S: query-focused summarise (semaphore)
                S-->>W: focused extract
            end
            Note over W,T: nudge appended → forces next phase
        end
        W-->>M: cited markdown answer (BLUF → analysis → refs)
        M-->>U: present findings verbatim (citations preserved)
    end
    M-->>U: result event (model, provider, cost_usd)
```

Turn caps prevent runaway recursion (`chat_loop` capped at ~20 turns). Tool results are hard-capped
to `summarise_threshold + 4,000` chars after summarisation to protect the context window.

---

## 5. Worker research pipeline (legislation mode)

The Worker follows a prescribed multi-phase process. Discovery is deliberately slimmed and batched
so that Phase 1 rarely needs summarisation; Phase 2 does the real retrieval.

```mermaid
flowchart TD
    brief["Research brief from Manager"] --> p1

    subgraph p1["Phase 1 — Discover"]
        s1["search_legislation (batched, parallel)"]
        s1 --> slim["_slim_search_results<br/>id, title, url, status, year, extent<br/>(description dropped → stays under 8k)"]
    end
    slim --> nudge1["Append [NEXT STEP] nudge<br/>listing legislation_ids"]

    nudge1 --> p2
    subgraph p2["Phase 2 — Retrieve provisions"]
        s2["search_legislation_sections<br/>one call per legislation_id,<br/>combined-aspect query"]
    end

    p2 --> big{"result > 8k chars?"}
    big -- yes --> sum["Query-focused summarisation<br/>(serialised by semaphore)"]
    big -- no --> keep["pass through"]
    sum --> synth
    keep --> synth

    p2 -. sparse .-> iterate["Phase 4 — retry with<br/>alternative terms"] --> p2
    p2 -. nothing useful .-> fallback["Phase 3 — get_legislation_text<br/>(full Act, fallback only)"] --> synth

    synth["Phase 5 — Synthesise<br/>BLUF → analysis → jurisdiction → references<br/>(legislation.gov.uk URLs)"] --> out["Return to Manager"]
```

The **parliament** flow is analogous — *discover → retrieve verbatim transcript → synthesise* — but
adds a hard **search budget** (3 discovery calls) enforced in `run_worker_tool`: once exhausted, the
tool returns a hard-stop message forcing the model into retrieval.

---

## 6. Provider resolution & concurrency

```mermaid
flowchart LR
    req["Incoming /api/chat"] --> resolve["provider_factory:<br/>read app_settings (DB)<br/>→ active provider + config"]
    resolve --> cv[["set ContextVar<br/>(carried through call chain)"]]
    cv --> queue["RequestQueue<br/>keyed (provider, max_concurrent_requests)"]
    queue --> loop["chat_loop (ollama|openrouter)"]
    loop --> sem["Summarise Semaphore<br/>keyed (provider, max_summarise_concurrency)"]
    resolve -. blank/fallback .-> env[".env startup defaults"]
```

- `AppSetting(key="provider.ollama")` and `AppSetting(key="provider.openrouter")` store per-provider
  JSON blobs (`base_url`, `api_key`, `model`, `summarisation_model`, `temperature`, concurrency).
- A separate `summarisation_model` can be configured per provider so a fast/cheap model handles
  document summarisation while a capable model does reasoning.
- Ollama summarisation concurrency should be **1** (concurrent calls to the cloud endpoint 500);
  OpenRouter tolerates 5+.

---

## 7. Federation

When at least one enabled peer is registered, the Manager gains a `consult_peer` tool alongside
`delegate_research`. With zero peers the behaviour is identical to a single-bot deployment (the tool
is simply absent).

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant LM as Legislation Manager
    participant PB as Parliament bot /api/consult
    participant PW as Parliament Worker

    U->>LM: "Was this Act debated at stage 1?"
    Note over LM: SCOPE prompt → use consult_peer<br/>(only present when a peer is registered)
    LM->>PB: POST /api/consult { query, depth: 1 }
    Note over PB: depth >= 2 → 422 (no A→B→C cascades)
    PB->>PW: run_worker_agent (Scottish Parliament tools)
    PW-->>PB: cited transcript answer (synchronous JSON)
    PB-->>LM: { answer, bot_id }
    LM-->>U: synthesised reply<br/>(or "the Parliament Bot found no records")
```

- Peer registry lives in the `peer_bots` table (Admin Portal → Federation tab). `api_key` is
  **write-only** — never returned by any response.
- `/api/consult` is **synchronous JSON**, not SSE — the calling Manager blocks for the full answer.

---

## 8. Parliament data pipeline (parliament bot only)

Scottish Parliament transcripts are crawled into local Postgres FTS tables and retrieved verbatim on
demand. Video deep links are an opt-in enrichment layer.

```mermaid
graph TB
    subgraph ingest["Ingestion — parliament_crawler.py (startup + daily)"]
        bf["backfill_sessions() / backfill_plenary()<br/>(one-shot, adaptive high-water-mark start)"]
        delta["crawl_sp_new_* (daily trailing 30-day window,<br/>reprocess recent meetings)"]
        bf --> tables
        delta --> tables
    end
    spor["SP Official Report<br/>parliament.scot"] --> bf
    spor --> delta

    tables[("sp_committee_items · sp_plenary_items<br/>(GIN FTS on full_text)")]

    subgraph retrieval["Query time — tools/parliament.py"]
        search["search_scottish_plenary / _committee_transcripts<br/>plainto_tsquery → OR-fallback (_or_tsquery)"]
        get["get_scottish_plenary_debate / _committee_transcript<br/>live fetch + _parse_sp_plenary_transcript"]
    end
    tables --> search
    spor --> get

    twfy["TWFY getHansard (excerpt fallback,<br/>written answers)"] --> search

    subgraph video["Video deep links (ENABLE_VIDEO_DEEPLINKS)"]
        sptv["sptv_client.py<br/>date/committee → eventId → HLS → WebVTT"]
        capdb[("sp_video_captions")]
        match["caption_match.py<br/>rarest-phrase match → clip_start/clip_end"]
        sptv --> capdb --> match
    end
    get --> match
    sptvhost["scottishparliament.tv"] --> sptv
```

- **FTS, not embeddings** — a measured go/no-go gate found FTS-only sufficient (semantic retrieval is
  deferred/NO-GO). Two cheap wins shipped instead: an **OR-fallback** when `plainto_tsquery` (all
  terms AND-ed) returns zero rows, and **prompt-level query wording** (use the official Holyrood term,
  e.g. *unhoused → homeless*).
- **Incremental crawl** — the source sends no `Last-Modified`/`ETag`, so change detection is driven
  by our own stored state: adaptive backfill start + a trailing-window daily re-scan.
- **Video timing** — segment ordinal × 6s using the *true* HLS playlist index (not caption-stream
  MPEGTS transitions), Europe/London DST-correct. Fully fail-soft: any failure just omits the link.

---

## 9. Data model (core entities)

Selected tables from `server_py/src/models.py`. FTS/crawler tables and `request_timings` are shown
separately for clarity.

```mermaid
erDiagram
    users ||--o{ chats : owns
    users ||--o{ matters : owns
    matters ||--o{ chats : groups
    matters ||--o{ matter_notes : has
    chats ||--o{ messages : contains
    chats ||--o{ documents : attaches
    messages ||--o| product_feedback : "rated via"

    users {
        int id PK
        string username
        string role
        bool dark_mode
        string research_mode
    }
    chats {
        int id PK
        int user_id FK
        int matter_id FK
        string model
        string provider
    }
    messages {
        int id PK
        int chat_id FK
        string role
        text content
        string model
        string provider
        numeric cost_usd
        int rating
    }
    app_settings {
        string key PK
        json value
    }
    peer_bots {
        int id PK
        string peer_id
        string base_url
        string api_key "write-only"
        bool enabled
    }
    activity_log {
        int id PK
        string event_type
        string username
        timestamp created_at
    }
```

**Parliament FTS / video tables** (parliament bot DB): `sp_committee_items` and `sp_plenary_items`
(one row per agenda item, GIN FTS on `full_text`, keyed `(meeting_id, iob_id)`); `sp_video_captions`
(one row per SP TV event, cached `transcript` + `offset_index`, unique `event_id`).

**Runtime config vs provenance** — `app_settings` holds runtime provider config (DB overrides `.env`
at request time). `chats.model/provider` record the selection at chat creation; `messages.model/
provider` record what was *actually* used at inference time (authoritative provenance).

---

## 10. Deployment view

Native Windows Server 2022 — **no Docker, no WSL, no nginx.** One uvicorn process is the entire
web tier; PostgreSQL runs as a Windows service; Ollama runs locally only when it is the active
provider.

```mermaid
graph TB
    subgraph target["Windows Server 2022 (internet-restricted)"]
        uvicorn["uvicorn src.main:app<br/>HTTPS :443 (org TLS certs)<br/>serves client/dist + /api"]
        pg[("PostgreSQL 15<br/>Windows service, localhost:5432")]
        ollama["Ollama<br/>localhost:11434 (proxy)"]
        uvicorn --> pg
        uvicorn -.->|if active provider| ollama
    end

    dev["Dev machine"] -->|"git push origin/main<br/>(incl. pre-built client/dist)"| gh["GitHub"]
    gh -->|"git pull"| uvicorn
    ollama -.->|":cloud models"| cloud["Remote inference"]
    uvicorn -.-> openrouter["openrouter.ai (if active)"]
    uvicorn --> research["LEX / TNA / SP research APIs"]

    user["Lawyer (browser)"] -->|HTTPS :443| uvicorn
```

**Lifecycle**
- **Start/stop** — `deployment/start_native.cmd` (PostgreSQL → Ollama → uvicorn) and
  `deployment/stop_native.cmd`.
- **Updates** — the *only* deployment path is `git pull` from `origin/main`. The frontend is
  pre-built on the dev machine and committed (`client/dist/`, force-added); the target needs no
  Node.js. See [deployment/NATIVE_DEPLOYMENT.md](deployment/NATIVE_DEPLOYMENT.md).
- **Local dev** — HTTP on port 8000 (no TLS certs locally); multiple bots per
  [deployment/LOCAL_SETUP.md](deployment/LOCAL_SETUP.md).

---

## Cross-references

| Concern | Document |
|---|---|
| Product spec, features, agent narrative | [SPECIFICATION.md](SPECIFICATION.md) |
| Schema & low-level flow | [DESIGN.md](DESIGN.md) |
| REST/SSE endpoint reference | [api/ServerAPISpec.md](api/ServerAPISpec.md) |
| External LEX API | [api/LexAPISpec.md](api/LexAPISpec.md) |
| Firewall / allowlist / ports | [NETWORK_AND_DEPENDENCIES.md](NETWORK_AND_DEPENDENCIES.md) |
| Deployment (target + local) | [deployment/](deployment/) |
| Parliament data model | [parliament/PARLIAMENTARY_DATA.md](parliament/PARLIAMENTARY_DATA.md) |
| Frontend design tokens | [frontend/design-system.md](frontend/design-system.md) |
| Agent/contributor context (canonical) | `../CLAUDE.md` |
