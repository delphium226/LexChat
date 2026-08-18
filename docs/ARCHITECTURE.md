# AILA — Architecture Reference

AILA (product name for the codebase historically called *LexChat*) is a family of AI
legal-research assistants for a UK government organisation. This document is the architectural
reference: it presents the system through a series of complementary **views**, each with a Mermaid
diagram.

For narrative product detail see [SPECIFICATION.md](SPECIFICATION.md); for low-level schema/flow
detail see [DESIGN.md](DESIGN.md); for the authoritative endpoint list see
[api/ServerAPISpec.md](api/ServerAPISpec.md); for firewall/allowlist detail see
[NETWORK_AND_DEPENDENCIES.md](NETWORK_AND_DEPENDENCIES.md).

> **Guiding principle: one codebase, many bots.** There is a single backend (`server_py/`) and a
> single frontend (`client/`). Every bot — the legislation assistant, the Scottish Parliament
> (Holyrood) bot, the Westminster bot, and any future bot — runs the *same* `uvicorn src.main:app`,
> differentiated by **configuration, not forked code**.

**The fleet as built:** legislation (`legislation_only`), Holyrood parliament
(`parliamentary_records`) and Westminster (`westminster_records`) are live. A legislative-drafting
bot (`drafting`) is in build on the long-lived `feature/drafting-bot` branch and is deliberately
*not* on `main` — see [drafting/BUILD_PLAN.md](drafting/BUILD_PLAN.md).

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
        parlbot["Holyrood bot<br/>uvicorn + PostgreSQL(lexchat_parliament)"]
        westbot["Westminster bot<br/>uvicorn + PostgreSQL(lexchat_westminster)"]
        user --> legbot
        user --> parlbot
        user --> westbot
        legbot <-->|"POST /api/consult<br/>(federation)"| parlbot
        legbot <-->|federation| westbot
        parlbot <-->|federation| westbot
    end

    subgraph llm["LLM providers (one active at a time)"]
        ollama["Ollama<br/>(local proxy to :cloud models)"]
        openrouter["OpenRouter<br/>openrouter.ai"]
    end

    subgraph research["External research APIs"]
        lex["LEX API<br/>lex.lab.i.ai.gov.uk"]
        tna["National Archives<br/>caselaw.nationalarchives.gov.uk"]
        twfy["TheyWorkForYou<br/>(SP plenary excerpts + MSPs)"]
        spor["SP Official Report<br/>parliament.scot"]
        spbills["SP Bills<br/>data.parliament.scot"]
        sptv["SP TV<br/>scottishparliament.tv (opt-in)"]
        hans["Hansard API<br/>hansard-api.parliament.uk"]
        ukmem["Members + Bills APIs<br/>members-api / bills-api.parliament.uk"]
    end

    legbot --> ollama
    legbot --> openrouter
    parlbot --> ollama
    parlbot --> openrouter
    westbot --> ollama
    westbot --> openrouter
    legbot --> lex
    legbot --> tna
    parlbot --> twfy
    parlbot --> spor
    parlbot --> spbills
    parlbot -.->|ENABLE_VIDEO_DEEPLINKS| sptv
    westbot --> hans
    westbot --> ukmem
```

**Notes**
- The target is *internet-restricted* (whitelist-only outbound), not air-gapped. Each external host
  above must be whitelisted for the corresponding bot — see [NETWORK_AND_DEPENDENCIES.md](NETWORK_AND_DEPENDENCIES.md).
- The Holyrood bot is **Scotland-only**; Westminster/Hansard coverage moved to its own bot rather
  than back into the Holyrood toolset.
- `ENABLE_WESTMINSTER_VIDEO_DEEPLINKS` / `PLIVE_BASE_URL` exist as settings, but parliamentlive.tv
  deep links are **not implemented** — see [parliament/WESTMINSTER_VIDEO_IMPLEMENTATION_PLAN.md](parliament/WESTMINSTER_VIDEO_IMPLEMENTATION_PLAN.md).

---

## 2. Container / component view (a single bot process)

One uvicorn process serves both the pre-built React UI (static files) and the `/api` backend. The
agent pipeline is provider-agnostic: a `ContextVar` carries the resolved provider config through the
whole async call chain.

```mermaid
graph TB
    subgraph client["Frontend — client/ (React 19 + Vite + Tailwind)"]
        app["App.jsx<br/>chat UI, SSE consumer,<br/>dynamic branding & model fetch"]
        hooks["hooks/<br/>useChat · useChatRuns (3 concurrent, in-tab)<br/>useFilters · useMatters"]
        admin["AdminPortal.jsx + pages/admin/*<br/>Developer · Federation · Efficiency ·<br/>Cache · Coverage · Restore"]
        sources["SourcesRail · ChatMessage ·<br/>DeepResearchPlan · SuggestedQuestions"]
    end

    subgraph backend["Backend — server_py/ (FastAPI + uvicorn)"]
        static["Static file serving<br/>client/dist/"]
        subgraph routers["routers/"]
            r_req["agent_request.py<br/>shared request models +<br/>build_request_config()"]
            r_ai["ai.py  /api/chat, /api/models"]
            r_res["research.py  /api/research/plan"]
            r_sys["system.py  /api/system/chat (eval)"]
            r_auth["auth.py"]
            r_chats["chats.py / documents.py / matters.py"]
            r_admin["users · stats · learning ·<br/>developer · feedback · health"]
            r_fed["federation.py / peers.py / identity.py"]
        end
        subgraph agent["agent/"]
            pf["provider_factory.py<br/>ContextVar config,<br/>queue + semaphore caches"]
            core["agent_core.py<br/>process_user_request,<br/>run_worker_agent,<br/>draft_research_plan,<br/>run_deep_research"]
            oc["ollama_client.py"]
            orc["openrouter_client.py"]
            shared["agent_shared.py + summarisation.py<br/>run_worker_tool, nudges,<br/>budgets, summarise pipeline"]
            tools["tools/ package<br/>schemas · lex · caselaw ·<br/>parliament · westminster · executor"]
            learn["learning.py (RAG feedback)"]
            fedc["federation_client.py"]
        end
        subgraph svc["services/"]
            crawler["parliament_crawler.py<br/>(Holyrood bot only)"]
            sptvc["sptv_client.py + caption_match.py"]
            lpc["local_prompt_cache.py"]
            bkp["backup_restore.py"]
            hs["health_service.py"]
        end
        util["utils/<br/>stopwatch (timings) · audit_trace ·<br/>suggestions · redact · queue"]
        models["models.py (SQLAlchemy)"]
    end

    db[("PostgreSQL 15")]
    provider["Active LLM provider<br/>(Ollama | OpenRouter)"]
    extapi["Research APIs<br/>(LEX / TNA / SP / Hansard)"]

    app -->|"SSE / REST"| routers
    hooks --> app
    admin --> routers
    sources --> app
    static --- app

    r_ai --> r_req
    r_res --> r_req
    r_sys --> r_req
    r_req --> pf
    r_ai --> core
    r_res --> core
    r_sys --> core
    core --> pf
    pf --> oc
    pf --> orc
    oc --> shared
    orc --> shared
    core --> shared
    shared --> tools
    shared --> lpc
    tools --> extapi
    core --> learn
    r_fed --> fedc
    routers --> models
    core --> util
    models --> db
    crawler --> db
    crawler --> extapi
    tools --> sptvc
    lpc --> db
    bkp --> db
    oc --> provider
    orc --> provider
```

**Key design points**
- **Provider abstraction** — `ollama_client.py` and `openrouter_client.py` each implement the same
  ReAct `chat_loop`; `agent_shared.py` + `summarisation.py` hold the shared tool-execution and
  summarisation pipeline. The active provider is resolved per request from the `app_settings` table
  and carried by a `ContextVar` — no function signatures change when the provider switches.
- **One request-config seam** — `routers/agent_request.py` defines `AgentRequestBase` → `ChatRequest`
  → `SystemChatRequest` (a *subclass*, so a field added to `/api/chat` is accepted by the eval
  endpoint automatically) plus the single `build_request_config()` all three entry routers use.
  Duplicating that config block is what previously caused `/api/system/chat` to silently drop
  `chat_mode`, filters and Deep Research.
- **Per-provider concurrency** — a `RequestQueue` (`max_concurrent_requests`) and a summarisation
  `asyncio.Semaphore` (`max_summarise_concurrency`) are cached per `(provider, concurrency)` and
  recreated automatically when settings change.
- **No global auth middleware** — every protected route declares `Depends(get_current_user)`
  explicitly. Public routes: `/api/auth/login`, `/api/health`, and the identity endpoints.
- **Log redaction** — user content and PII are redacted at INFO (`utils/redact.py` renders
  `<N chars, sha1:…, 'prefix…'>`) and appear in full only at DEBUG. `redact_args` is
  allowlist-based, so a new free-text tool parameter loses log fidelity rather than confidentiality.

---

## 3. One codebase, many bots

Behaviour is switched at runtime by configuration under `bots/<id>/`, not by branching code.

```mermaid
graph LR
    code["Shared code<br/>server_py/ + client/"]

    subgraph cfgL["bots/legislation/"]
        eL[".env + bot_config.json<br/>DB=lexchat · PORT=8000<br/>RESEARCH_MODE=(blank)"]
    end
    subgraph cfgP["bots/parliament/"]
        eP[".env + bot_config.json<br/>DB=lexchat_parliament · PORT=8001<br/>RESEARCH_MODE=parliamentary_records"]
    end
    subgraph cfgW["bots/westminster/"]
        eW[".env + bot_config.json<br/>DB=lexchat_westminster · PORT=8002<br/>RESEARCH_MODE=westminster_records"]
    end

    code --> procL["Legislation bot<br/>LEX + case-law toolset"]
    code --> procP["Holyrood bot<br/>SP transcripts toolset"]
    code --> procW["Westminster bot<br/>Hansard toolset"]
    cfgL --> procL
    cfgP --> procP
    cfgW --> procW
    procL <-->|federation| procP
    procL <-->|federation| procW
    procP <-->|federation| procW
```

`RESEARCH_MODE` (env) → `research_mode` drives three things:

| Driven by mode | Where |
|---|---|
| Worker toolset | `tools/schemas.py::get_worker_tools(mode)` |
| Manager + Worker system prompts | `prompts.py::get_manager_system_prompt` / `get_worker_system_prompt` |
| Efficiency profile (breach rules + dashboard bands) | `config.py::EFFICIENCY_PROFILES` / `get_efficiency_profile()` |

Modes: `legislation_only`, `case_law_only`, `legislation_and_case_law`, `parliamentary_records`,
`westminster_records`. Each bot is an independent process with its **own database and port**;
identity (name, tagline, logo, brand colour) comes from `bot_config.json` and reaches the client via
`GET /api/bot-info` and `GET /api/bot/logo`, so one frontend bundle renders as any bot.

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
        M-->>U: answer or clarifying question (+ option chips)
    else clear legal query
        M->>W: delegate_research(self-contained brief)
        Note over W: fresh history — no chat context
        loop Phase 1..2 (batched, parallel)
            W->>T: search_* / get_* (asyncio.gather)
            T-->>W: raw results
            alt result > threshold, or context budget exceeded
                W->>S: query-focused summarise (semaphore)
                S-->>W: focused extract
            end
            Note over W,T: nudge appended → forces next phase
        end
        opt report structure malformed
            W->>W: one no-tools reformat retry (fail-soft)
        end
        W-->>M: cited markdown answer (BLUF → analysis → refs)
        M-->>U: present findings verbatim (citations preserved)
    end
    Note over M: strip the suggestions tag block → attach as chips
    M-->>U: result event (model, provider, cost_usd, suggestions)
```

**Caps and resilience**
- `chat_loop` is capped at ~20 turns; tool results are hard-capped to `summarise_threshold + 4,000`
  chars *after* summarisation.
- **Summarisation threshold scales with the model** — 10% of the model's context in chars, clamped
  to [10K, 200K] (`get_summarise_threshold()`), so it is not a fixed 8K any more. Because that caps
  each result but never their *sum*, `run_worker_agent` also carries a per-run
  **`WORKER_CONTEXT_BUDGET_CHARS = 250_000`**: once the running total would exceed it, a result is
  summarised regardless of its own size.
- **Graceful failure in three layers** — a failed worker run returns an `[Research Agent Error]`
  *tool result* to the Manager rather than killing the SSE request; `describe_agent_error` gives
  every user-facing failure real text (httpx timeouts stringify to `""`); `/api/chat` wraps that in
  a "try again, or narrow the question" error event. Real user aborts still propagate.
- **Bounded retries** — the provider stream is retried up to 3 times, but **only while nothing has
  been emitted** (replaying would duplicate tokens); LEX calls retry `{429, 502, 503, 504}` with
  exponential backoff honouring `Retry-After`.
- **Suggested-question chips** — the model emits a tagged `<suggestions>` block; it is stripped and
  attached at the **Manager return in `agent_core.py`**, not in the router, because
  `process_user_request` also serves `/api/consult` — so a peer's chips can never leak into the
  calling bot's context. Live only: no DB column, gone after reload. Governed by the
  `suggested_questions_enabled` flag, which *substitutes the instruction out of the prompt* rather
  than overriding it (the strip stays unconditional as belt-and-braces).
- **Concurrent runs are in-tab only** — up to 3 per browser tab (`useChatRuns.js`); a refresh or tab
  close still destroys a run, because `/api/chat` never writes the assistant message itself. The
  durable design is deliberately deferred — see [CONCURRENT_RUNS_DURABILITY.md](CONCURRENT_RUNS_DURABILITY.md).

---

## 5. Worker research pipeline (legislation mode)

The Worker follows a prescribed multi-phase process. Discovery is deliberately slimmed and batched
so that Phase 1 rarely needs summarisation; Phase 2 does the real retrieval.

```mermaid
flowchart TD
    brief["Research brief from Manager"] --> p1

    subgraph p1["Phase 1 — Discover"]
        s1["search_legislation (batched, parallel)"]
        s1 --> slim["_slim_search_results<br/>id, title, url, status, year, extent<br/>(description dropped → stays under threshold)"]
    end
    slim --> nudge1["Append [NEXT STEP] nudge<br/>listing legislation_ids"]

    nudge1 --> p2
    subgraph p2["Phase 2 — Retrieve provisions"]
        s2["search_legislation_sections<br/>one call per legislation_id,<br/>combined-aspect query"]
    end

    p2 --> big{"over threshold, or<br/>context budget exceeded?"}
    big -- yes --> sum["Query-focused summarisation<br/>(semaphore; local cache checked first)"]
    big -- no --> keep["pass through"]
    sum --> synth
    keep --> synth

    p2 -. sparse .-> iterate["Phase 4 — retry with<br/>alternative terms"] --> p2
    p2 -. nothing useful .-> fallback["Phase 3 — get_legislation_text<br/>(full Act, fallback only)"] --> synth

    synth["Phase 5 — Synthesise<br/>BLUF → analysis → jurisdiction → references<br/>(legislation.gov.uk URLs)"] --> chk{"structure valid?"}
    chk -- no --> refmt["One no-tools reformat retry<br/>(A4, fail-soft)"] --> out
    chk -- yes --> out["Return to Manager"]
```

**Mode variants of the same discover → retrieve → synthesise shape:**

| Mode | Discovery | Retrieval | Notable enforcement |
|---|---|---|---|
| Legislation / case law | `search_legislation`, `search_case_law` | `search_legislation_sections`, `get_case_law_text`, `get_legislation_text` (fallback) | one call per `legislation_id`; appellate-decision detection nudges the Worker to the higher-court judgment |
| Holyrood (`parliamentary_records`) | `search_scottish_plenary` / `_committee_transcripts` (local FTS), `search_scottish_parliament` (excerpt fallback) | `get_scottish_plenary_debate` / `get_scottish_committee_transcript` (live fetch + parse) | hard **search budget of 3** discovery calls, enforced in `run_worker_tool`; retrieval capped at 150 speeches per item |
| Westminster (`westminster_records`) | `search_hansard` (live API; chamber / Westminster Hall / PBC / written) | `get_hansard_debate` (verbatim contributions) | same search-budget shape; contributions capped at 150 per debate |

Both parliamentary modes exist to answer *Pepper v Hart*-style questions — retrieving a Minister's
exact words on statutory purpose — which is why verbatim retrieval, not excerpts, is the goal and
why the transcript caps report `total_speeches` and tell the model to narrow rather than truncating
silently.

---

## 6. Deep Research (plan → approve → execute)

An opt-in `chat_mode = "deep_research"` that drafts an **editable** plan, lets the lawyer change it,
then executes it autonomously. Plan-first is what makes the run steerable and leaves an auditable
approved-plan artefact. **L2 only** — there is no pause-and-review between steps.

```mermaid
sequenceDiagram
    autonumber
    participant U as Browser
    participant RP as routers/research.py
    participant PL as draft_research_plan<br/>(planner agent, no research tools)
    participant AI as routers/ai.py
    participant DR as run_deep_research<br/>(code-orchestrated)
    participant W as Worker (per step)

    U->>RP: POST /api/research/plan
    RP->>PL: planner LLM call (same RequestQueue slot)
    alt scope unclear
        PL-->>U: { needs_clarification, question, options[] }
    else
        PL-->>U: { plan: { steps[] } } via submit_research_plan
    end
    U->>U: edit / reorder / delete steps
    U->>AI: POST /api/chat (SSE) + deep_research_plan
    AI->>DR: execute approved plan
    loop for each approved step (Python loop, 1:1)
        DR->>W: run_worker_agent(step)
        W-->>DR: findings + sources
        Note over DR: per-request tool memo dedupes<br/>repeat (tool, args) across steps
    end
    DR->>DR: dedupe sources, single tool-free synthesis call
    DR-->>U: integrated report (BLUF + key findings + gaps)
```

- **Code-orchestrated, not prompt-driven** — one `run_worker_agent` call per approved step gives a
  deterministic mapping between what was approved and what was done.
- **Audit column** — `messages.research_plan` (additive JSON) persists the approved plan on the
  assistant message and the UI renders it back.
- **Efficiency carve-out** — a DR run legitimately fans out to N delegations, so it is exempt from
  the fan-out breach rules and excluded from the Efficiency dashboard's baselines.
- Planner clarifications reuse the suggested-question chip render path, under the same
  no-speculation guardrail: only scope choices grounded in the conversation or in tool results.
- Build spec: [deep-research/IMPLEMENTATION_PLAN.md](deep-research/IMPLEMENTATION_PLAN.md).

---

## 7. Provider resolution & concurrency

```mermaid
flowchart LR
    req["Incoming request<br/>/api/chat · /api/research/plan · /api/system/chat"] --> cfg["build_request_config()<br/>(routers/agent_request.py)"]
    cfg --> resolve["provider_factory:<br/>read app_settings (DB)<br/>→ active provider + config<br/>+ model context length"]
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
- The resolved model's **context length** rides on the request config and sets the summarisation
  threshold (§4).
- Ollama summarisation concurrency should be **1** (concurrent calls to the cloud endpoint 500);
  OpenRouter tolerates 5+.
- **Model quality dominates**: a capable instruction-follower batches Phase 2 correctly and finishes
  an 8-Act query in ~90s; a weak model ignores batching and is ~10× worse on identical
  infrastructure.

---

## 8. Caching stack

Three cooperating cost-reduction layers, all additive and fail-soft, each behind a feature flag, all
reporting into Admin Portal → **Cache** (`GET /api/stats/cache`, backed by additive
`request_timings` columns).

```mermaid
flowchart TB
    call["Worker tool call"] --> memo{"per-request tool memo<br/>(tool, canonical args)"}
    memo -- hit --> reuse["reuse result:<br/>no API call, no summarise<br/>→ memo_hits"]
    memo -- miss --> api["External API call"]
    api --> big{"needs summarising?"}
    big -- no --> ret["result → Worker"]
    big -- yes --> lpc{"local_prompt_cache<br/>sha256(raw text) + sha256(canonical query)"}
    lpc -- hit --> ret2["cached summary<br/>→ local_cache_hits"]
    lpc -- miss --> sumr["summarise via LLM"]
    sumr --> store{"tool in CACHEABLE_TOOLS<br/>AND output not degraded?"}
    store -- yes --> write[("store in local_prompt_cache")]
    store -- no --> ret3["return, do not cache"]
    write --> ret4["result → Worker"]

    prompt["Provider prompt caching<br/>cache_control on system +<br/>last message (anthropic/* only)"] -.->|"cached_prompt_tokens,<br/>cache_discount_usd"| metrics[("request_timings")]
    reuse -.-> metrics
    ret2 -.-> metrics
```

| Layer | Scope | Key | Flag |
|---|---|---|---|
| Provider prompt caching (D5) | one provider call | provider-side prefix | `prompt_caching_enabled` |
| Per-request tool memo (D5/D8) | one request (dies with it) | `(tool_name, canonical args JSON)` | `tool_memo_enabled` |
| Local prompt cache (D7/D8) | **cross-user, cross-provider**, persistent | `sha256(raw pre-summarisation text)` + `sha256(canonicalised query)` | `local_prompt_cache_enabled` |

**Why the local cache is safe to share:** identical hash ⇒ identical source text, so staleness is
impossible (amended text produces a new hash → a miss). It is **exact-match only, no embeddings** —
semantic near-miss reuse risks silent incompleteness. `summarise_model` is stored for provenance but
kept *out* of the key, which is what makes it cross-provider.

**Guardrails worth knowing before touching it**
- Only tools on the explicit `CACHEABLE_TOOLS` allowlist may be stored — the cache is shared across
  users, so a new tool must be confirmed public-source-only first.
- Degraded/partial summariser output (the raw-text fallback) is **never** stored; one transient
  error would otherwise poison a shared key permanently.
- The key query is the **raw user question** in standard mode (not the Manager's per-model
  paraphrase, which would make cross-user hits luck) and the approved step text in Deep Research.
- The cache is **forced off in code** for `research_mode == "drafting"`, in `build_request_config()`
  — a drafting bot's input is unpublished legislative text and must never reach a shared plaintext
  column. Consequence: a drafting bot's Cache tab shows "Local cache: ON". That is expected.
- Canonicalisation is versioned by a `v1|` hash prefix (bumping it invalidates the whole cache).
- **Not built:** a LEX/case-law response cache — measurement showed LLM time dominates external-API
  time ~16:1. Deferred until traffic says otherwise.
- Plans: [LOCAL_PROMPT_CACHE_PLAN.md](LOCAL_PROMPT_CACHE_PLAN.md),
  [CACHE_REVIEW_FIXES_PLAN.md](CACHE_REVIEW_FIXES_PLAN.md), [CACHE_ADMIN_UI_PLAN.md](CACHE_ADMIN_UI_PLAN.md).

---

## 9. Federation

When at least one enabled peer is registered, the Manager gains a `consult_peer` tool alongside
`delegate_research`. With zero peers the behaviour is identical to a single-bot deployment (the tool
is simply absent).

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant LM as Legislation Manager
    participant PB as Peer bot /api/consult
    participant PW as Peer Worker

    U->>LM: "Was this Act debated at stage 1?"
    Note over LM: SCOPE prompt → use consult_peer<br/>(only present when a peer is registered)
    LM->>PB: POST /api/consult { query, depth: 1 }
    Note over PB: depth >= 2 → 422 (no A→B→C cascades)
    Note over PB: request marked _consulted →<br/>CONSULTED_PEER_BLOCK: answer, never ask
    PB->>PW: run_worker_agent (peer's toolset)
    PW-->>PB: cited answer (synchronous JSON)
    PB-->>LM: { answer, bot_id }
    LM-->>U: synthesised reply<br/>(or "the Parliament Bot found no records")
```

- Peer registry lives in the `peer_bots` table (Admin Portal → Federation tab, or `/api/peers`).
  `api_key` is **write-only** — never returned by any response. `PUT /api/peers/{peer_id}` takes the
  string peer id, not the numeric row id; the `bot_config.json` seed is insert-or-ignore and never
  updates an existing row.
- `/api/consult` is **synchronous JSON**, not SSE — the calling Manager blocks for the full answer.
- Manager prompts carry cross-bot SCOPE rules in both directions, and distinguish "the peer found no
  records" from "no parliamentary peer is registered" — the latter is the only case that may be
  reported as unavailable.
- A consulted peer **never asks the user anything**: the consult channel is one-shot and stateless,
  so a clarifying question would come back *as the answer*. The block is appended on all three
  return paths of `get_manager_system_prompt` (the parliament/Westminster branch returns early).

---

## 10. Parliamentary data pipelines

### Holyrood — crawl into local FTS, retrieve verbatim on demand

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
  terms AND-ed) returns zero rows, and **prompt-level query wording** (use the official Holyrood
  term, e.g. *unhoused → homeless*). Raw hit-rate ~85% → ~88%; residual misses recover on the
  single permitted reformulation retry.
- **Incremental crawl** — the source sends no `Last-Modified`/`ETag`, so change detection is driven
  by our own stored state: adaptive backfill start (full Session-6 walk only on an empty table) plus
  a trailing-window daily re-scan that reprocesses recent meetings, catching late-published
  transcripts. Not covered: revisions to finalised transcripts outside the 30-day window.
- **One parser for both** — committee pages now use the same `<p id="orscontributions_…">` markup as
  plenary, so `_parse_sp_plenary_transcript` serves both the retrieval tools and the crawler.
- **Video timing** — segment ordinal × 6s using the *true* HLS playlist index (not caption-stream
  MPEGTS transitions, which undercount because ~7% of segments carry no captions),
  Europe/London DST-correct, anchored to the agenda item by rarest-phrase match. Fully fail-soft.
  Coverage: ~1,140 events cached, ~47% with a usable caption track (skewed to recent sittings).
- Data model detail: [parliament/PARLIAMENTARY_DATA.md](parliament/PARLIAMENTARY_DATA.md).

### Westminster — live API, no crawl

`tools/westminster.py` calls the Hansard API directly: `search_hansard`
(`/search/contributions/{type}.json`, filterable by House, record type and date) then
`get_hansard_debate` (`/debates/debate/{ext_id}.json`) for the full attributed contributions, plus
the Members API and Bills API for member and bill lookups. There is **no local corpus and no
crawler** for Westminster — Hansard search is already full-text and relevance-ranked, so the
retrieval quality problem that motivated the Holyrood crawl does not exist here. Citations link to
`hansard.parliament.uk`.

---

## 11. Data model (core entities)

Selected tables from `server_py/src/models.py`. FTS/crawler, cache and timing tables are described
below the diagram.

```mermaid
erDiagram
    users ||--o{ chats : owns
    users ||--o{ matters : owns
    users ||--o{ session_feedback : submits
    matters ||--o{ chats : groups
    matters ||--o{ matter_notes : has
    chats ||--o{ messages : contains
    chats ||--o{ documents : attaches
    messages ||--o| product_feedback : "rated via"
    messages ||--o| matter_notes : "cited by"

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
        json research_plan
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

- **Parliament FTS / video tables** (Holyrood bot DB): `sp_committee_items` and `sp_plenary_items`
  (one row per agenda item, GIN FTS on `full_text`, keyed `(meeting_id, iob_id)`);
  `sp_video_captions` (one row per SP TV event, cached `transcript` + `offset_index`).
- **`request_timings`** — one row per request: latency phases, token/cost counts, tool and phase
  counters, `chat_mode`, `research_mode`, `model`, cache metrics (`cached_prompt_tokens`,
  `cache_discount_usd`, `memo_hits`, `local_cache_hits`, `local_cache_chars_saved`), efficiency
  counters (`search_budget_blocked`, `report_reformat_retries`) and `source` (`app` / `eval`).
- **`local_prompt_cache`** — the cross-user summary cache (§8): content+query hash, summary,
  `hit_count`, `last_hit_at`; sampled prune above 20K rows, 365-day retention for hit rows.
- **Other tables**: `documents` (uploaded file text), `product_feedback` (per-answer rating),
  `session_feedback` (end-of-session survey), `service_health_logs`, `matters` / `matter_notes`.
- **Runtime config vs provenance** — `app_settings` holds runtime provider config and feature flags
  (DB overrides `.env` at request time). `chats.model/provider` record the selection at chat
  creation; `messages.model/provider` record what was *actually* used at inference time
  (authoritative provenance).
- **Activity Log is mostly synthesised** — only `LOGIN` rows are written to `activity_log`; `QUERY`,
  `FEEDBACK`, `SURVEY` and `ERROR` events are derived at query time by UNION ALL over `messages`,
  `product_feedback` and `service_health_logs`, with filters applied inside each branch so `limit`
  reflects the filtered set.

---

## 12. Measurement & observability

Two audiences: operators watching a live bot (Admin Portal) and the external eval harness.

```mermaid
flowchart LR
    req["Request"] --> sw["utils/stopwatch.py<br/>TimingCollector"]
    sw --> rt[("request_timings")]
    sw --> breach{"evaluate_efficiency_breaches()<br/>per-mode profile"}
    breach -- breach --> al[("activity_log<br/>event_type=EFFICIENCY")]
    rt --> dash["Admin Portal<br/>Usage · Performance · Cost ·<br/>Efficiency · Cache · Coverage"]

    sysreq["/api/system/chat<br/>(eval harness)"] --> at["utils/audit_trace.py<br/>collector in a ContextVar"]
    at --> ev["audit SSE event<br/>delegations[] → tools[] → api_calls[]<br/>raw_result + final_result"]
    sysreq --> rt
```

- **Per-bot efficiency profiles** — the same code grades each bot against different baselines,
  selected by `research_mode`. Fan-out denominator differs by mode (legislation: retrievals per kept
  source; parliamentary/Westminster: retrievals per distinct transcript/debate) and is
  allowlist-validated before it is interpolated into SQL. Parliamentary and Westminster band values
  are **unmeasured starting points**; the `reformat` band is unmeasured on every profile.
- **Prompt-adherence measurement** — `report_reformat_retries` + `model` answer "how often does this
  model ignore the OUTPUT STRUCTURE rules", surfaced as a rate and a per-model table. Per-model is
  the point: a rate high across all models indicts the prompt, one concentrated in a single model is
  a model-selection question. Indicator only, no breach rule (the retry is fail-soft).
- **Audit trace** — a structured trace emitted once before `result`, replacing the harness's
  reconstruction of a UI-shaped stream (which matched on *display labels* and was already silently
  broken for Deep Research). Nesting comes from the call graph, not event order: delegations open in
  `run_worker_agent`, tool records in `run_worker_tool` (handed their delegation explicitly, so
  nesting survives future parallelism), API calls by sniffing `on_chunk` inside the tool's scope.
  `raw_result` alongside `final_result` is the analytical addition — it separates a bad retrieval
  from a bad summary. Off unless requested, and every collector method swallows its own errors.
- **Eval traffic is tagged, not filtered** — `request_timings.source` separates `app` from `eval`,
  but the dashboards do not filter on it yet, so a large sweep moves the headline numbers. Eval runs
  write no EFFICIENCY breach rows.
- Spec: [api/AUDIT_TRACE.md](api/AUDIT_TRACE.md); plans:
  [planning/EFFICIENCY_PER_BOT_PLAN.md](planning/EFFICIENCY_PER_BOT_PLAN.md),
  [planning/PER_REQUEST_EFFICIENCY_PROFILE_PLAN.md](planning/PER_REQUEST_EFFICIENCY_PROFILE_PLAN.md).

---

## 13. Backup & scoped restore

Nightly `pg_dump -Fc` per database, plus a Developer-tab restore that is the inverse of the Danger
Zone: it puts back one scope at a time rather than restoring a whole server.

```mermaid
flowchart LR
    pgdbs[("all databases<br/>(enumerated from pg_database)")] --> dump["deployment/backup_databases.ps1<br/>pg_dump -Fc per DB, GFS 14/8/12"]
    dump --> verify{"two-stage verify"}
    verify --> v1["pg_restore --list<br/>(TOC only — misses truncation)"]
    verify --> v2["pg_restore -f NUL<br/>(full read — catches truncation)"]
    dump --> files[("BACKUP_ROOT<br/>+ manifest.json")]

    files --> restore["services/backup_restore.py"]
    restore --> stage[("lexchat_restore_staging<br/>(pg_restore -t: only the scoped tables)")]
    stage --> copy["Python row copy<br/>text bind → CAST back to column type"]
    copy --> live[("live DB, scope by scope")]
```

- **`--list` is not the check that works.** In a custom-format archive the TOC precedes the data, so
  a dump truncated to half its length still lists every entry and exits 0. `pg_restore -f NUL` (a
  full read) is what catches truncation. Both stages run in the backup script and on restore.
- **Never restore over live tables.** Staging is a database the app never connects to, and only the
  tables the selected scopes need are staged (0.13s vs 33s for the whole parliament dump; the SP
  corpus is never copied).
- **The copy is Python, not SQL** — `postgres_fdw`/`dblink` need `CREATE EXTENSION` and `lexuser` is
  `NOSUPERUSER`. Values cross as text and are cast back, which requires
  `CAST(CAST(:p AS text) AS <type>)` — asyncpg types a bind parameter from its surrounding cast, so
  a single cast makes it reject the text being sent deliberately.
- **`feedback` is the scope that silently does nothing if you get it wrong** — clearing feedback
  nulls `messages.rating` in place, so the rows survive and an `INSERT … ON CONFLICT DO NOTHING`
  restores nothing while reporting success. That component is an `UPDATE`. Restoring `chats` *and*
  `feedback` together masks the bug.
- Restore order is `list(reversed(_CLEAR_ORDER))`, asserted at import; sequences are `setval`'d
  afterwards; `matter_notes.message_id` links are repaired as part of the `chats` scope.
- **The `cache` scope can never be restored** — `local_prompt_cache` rows are excluded from every
  dump by design, and that is reported as unavailable with the reason. Not a bug.
- **`BACKUP_ROOT` must match the scheduled task's `-BackupRoot`**, or the Developer tab reads an
  empty directory while backups run fine elsewhere. Both default to `C:\LexChatBackups`.
- Design: [BACKUP_RESTORE_PLAN.md](BACKUP_RESTORE_PLAN.md); procedure:
  [deployment/BACKUP_RUNBOOK.md](deployment/BACKUP_RUNBOOK.md).

---

## 14. Deployment view

Native Windows Server 2022 — **no Docker, no WSL, no nginx.** One uvicorn process per bot is the
entire web tier; PostgreSQL runs as a Windows service; Ollama runs locally only when it is the
active provider.

```mermaid
graph TB
    subgraph target["Windows Server 2022 (internet-restricted)"]
        uvicorn["uvicorn src.main:app (one per bot)<br/>HTTPS :443 (org TLS certs)<br/>serves client/dist + /api"]
        pg[("PostgreSQL 15<br/>Windows service, localhost:5432<br/>one database per bot")]
        ollama["Ollama<br/>localhost:11434 (proxy)"]
        task["Scheduled task<br/>backup_databases.ps1 (nightly)"]
        uvicorn --> pg
        task --> pg
        uvicorn -.->|if active provider| ollama
    end

    dev["Dev machine"] -->|"git push origin/main<br/>(incl. pre-built client/dist)"| gh["GitHub"]
    gh -->|"git pull"| uvicorn
    ollama -.->|":cloud models"| cloud["Remote inference"]
    uvicorn -.-> openrouter["openrouter.ai (if active)"]
    uvicorn --> research["LEX / TNA / SP / Hansard research APIs"]

    user["Lawyer (browser)"] -->|HTTPS :443| uvicorn
```

**Lifecycle**
- **Start/stop** — `deployment/start_native.cmd` (PostgreSQL → Ollama → uvicorn) and
  `deployment/stop_native.cmd`. Note `start_native.cmd` copies `.env.native` over `.env` on every
  start, so `.env.native` is the *live* target config and must not carry tracked per-machine edits.
- **Updates** — the *only* deployment path is `git pull` from `origin/main`. The frontend is
  pre-built on the dev machine and committed (`client/dist/`, force-added); the target needs no
  Node.js. See [deployment/NATIVE_DEPLOYMENT.md](deployment/NATIVE_DEPLOYMENT.md).
- **Backups** — `deployment/install_backup_task.ps1` registers the nightly task (needs elevation).
  Off-box copy of the dumps is still outstanding.
- **Local dev** — HTTP on port 8000 (no TLS certs locally); multiple bots via
  `deployment/start_federation_dev.ps1` per [deployment/LOCAL_SETUP.md](deployment/LOCAL_SETUP.md).

---

## Cross-references

| Concern | Document |
|---|---|
| Product spec, features, agent narrative | [SPECIFICATION.md](SPECIFICATION.md) |
| Schema & low-level flow | [DESIGN.md](DESIGN.md) |
| REST/SSE endpoint reference | [api/ServerAPISpec.md](api/ServerAPISpec.md) |
| Eval endpoint + audit trace | [api/AUDIT_TRACE.md](api/AUDIT_TRACE.md) |
| External LEX API | [api/LexAPISpec.md](api/LexAPISpec.md) |
| Firewall / allowlist / ports | [NETWORK_AND_DEPENDENCIES.md](NETWORK_AND_DEPENDENCIES.md) |
| Deployment (target + local) + backup runbook | [deployment/](deployment/) |
| Deep Research build spec | [deep-research/IMPLEMENTATION_PLAN.md](deep-research/IMPLEMENTATION_PLAN.md) |
| Caching stack design | [LOCAL_PROMPT_CACHE_PLAN.md](LOCAL_PROMPT_CACHE_PLAN.md), [CACHE_REVIEW_FIXES_PLAN.md](CACHE_REVIEW_FIXES_PLAN.md) |
| Backup & scoped restore design | [BACKUP_RESTORE_PLAN.md](BACKUP_RESTORE_PLAN.md) |
| Holyrood data model | [parliament/PARLIAMENTARY_DATA.md](parliament/PARLIAMENTARY_DATA.md) |
| Drafting bot (in build, off `main`) | [drafting/BUILD_PLAN.md](drafting/BUILD_PLAN.md) |
| Deferred run durability | [CONCURRENT_RUNS_DURABILITY.md](CONCURRENT_RUNS_DURABILITY.md) |
| Frontend design tokens | [frontend/design-system.md](frontend/design-system.md) |
| Canonical todo list | [TODO.md](TODO.md) |
| Agent/contributor context (canonical) | `../CLAUDE.md` |
