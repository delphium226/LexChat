# LexChat — Network Access & Dependency Reference

This document lists all external websites, network endpoints, and ports that LexChat
requires during installation and at runtime. Intended for corporate proxy and firewall
administrators configuring allowlist rules.

> **Deployment model**: LexChat runs natively on Windows Server 2022. Docker is not used.
> The frontend is pre-built on the developer's machine and committed to the repository.
> The target server requires no Node.js at runtime.

---

## Part 1: Installation — Downloads and External Access

Required only during initial setup or updates; not at runtime.

### 1.1 Native Windows Deployment (dev machine / bundle production)

The internet-connected installer has been removed; the target installs from the offline bundle (see 1.3). These URLs are only needed on the machine that produces the bundle:

| Website / URL | What is Downloaded | Used by |
|---|---|---|
| `https://www.python.org/ftp/python/` | Python 3.11.9 Windows installer | `deployment/package_offline_native.ps1` |
| `https://get.enterprisedb.com/postgresql/` | PostgreSQL 15.7 Windows installer | `deployment/package_offline_native.ps1` |
| `https://ollama.com/download/OllamaSetup.exe` | Ollama Windows installer | `deployment/package_offline_native.ps1`; downloaded by hand before `deployment/chunk_ollama_installer.ps1` (`update_ollama.ps1` downloads nothing: it reassembles the committed chunks) |
| `https://pypi.org/`, `https://files.pythonhosted.org/` | Python packages from `server_py/requirements.txt` (`pip download` of win_amd64 / Python 3.11 wheels) | `deployment/package_offline_native.ps1` |
| `https://github.com/<repo>`, `https://objects.githubusercontent.com/` | Git repository clone/pull | `git clone` / `git pull` |
| `https://registry.ollama.ai/`, `https://ollama.com/` | AI model registration for cloud-routed models | First model request via Ollama |

### 1.2 Frontend Build (Developer Machine Only)

The frontend is **not built on the target server**. It is built on the developer's machine and the output (`client/dist/`) is committed to the repository.

| Website / URL | What is Downloaded | Tool |
|---|---|---|
| `https://registry.npmjs.org/` | Node.js packages from `client/package.json` | `npm install` |
| `https://nodejs.org/dist/` | Portable Node.js v22.15.0 zip | `deployment/install_node.ps1` |

Node.js v22 is used on the dev machine only (portable install via `deployment/install_node.ps1`). Not required on target server.

### 1.3 Air-Gapped Installation (`install_native_offline.ps1`)

No internet required on the target. All dependencies are pre-packaged on the dev machine using `deployment/package_offline_native.ps1` and transferred via USB/secure file share.

### 1.4 Updates

Target server updates via `git pull` from GitHub:
- `https://github.com/<repo>` — code and pre-built `client/dist/` assets
- `https://pypi.org/` — only if Python dependencies have changed (run `pip install -r requirements.txt` after pull). Where the target cannot reach PyPI, new packages come from wheels committed to the repository instead (pdfplumber and python-docx: `deployment/pdf_wheels/`, installed by `deployment/install_pdf_support.ps1` with `pip --no-index`).

---

## Part 2: Runtime — Network Traffic & Ports

### 2.1 Inbound Ports

| Port | Protocol | Service | Description |
|---|---|---|---|
| **443** | HTTPS | FastAPI (uvicorn) | Application entry point — serves both the web UI and the `/api` backend. Uses organisational TLS certificate from `deployment/certs/`. |
| **11434** | HTTP | Ollama | AI inference server. Only accessible on `localhost`; not exposed externally. |
| **5432** | TCP | PostgreSQL | Database. Only accessible on `localhost`. |

### 2.2 Outbound Traffic — External Services

APIs marked **Legislation** are used by the default legislation bot. APIs marked **Parliament** are only required when the Scottish Parliament bot is deployed, and APIs marked **Westminster** only when the Westminster (UK Parliament) bot is deployed. All bots share the same LLM provider traffic.

legislation.gov.uk is not called directly: the legislation bot reads it (commencement dates, published texts, the daily made-under refresh) only through LEX's `/legislation/proxy`, so it needs no entry of its own.

| Destination | URL / Host | Port | Protocol | Bot | Description |
|---|---|---|---|---|---|
| **Ollama Cloud Models** | `https://registry.ollama.ai/` and third-party inference endpoints | 443 | HTTPS | All | When using cloud-tagged models (e.g. `mistral-large-3:675b-cloud`), Ollama routes requests to remote inference providers. Traffic includes the full chat context sent as JSON with **long-lived streaming responses** (60–300+ seconds per request). Authenticated via Ollama API key (`Authorization: Bearer` header). |
| **OpenRouter** | `https://openrouter.ai/api/v1` | 443 | HTTPS | All | Alternative LLM provider. If OpenRouter is set as the active provider in the Admin Portal, all AI requests route here instead of Ollama. Also a long-lived streaming connection. Requires an OpenRouter API key (Admin Portal → Developer tab, stored in the database; `OPENROUTER_API_KEY` is only the startup default). Only needed if OpenRouter provider is used. |
| **LEX API** | `https://lex.lab.i.ai.gov.uk` | 443 | HTTPS | Legislation | Worker agent calls this API to search UK legislation and retrieve text. JSON POST to `/legislation/search`, `/legislation/section/search`, `/legislation/text`, `/amendment/search`, `/legislation/lookup` and `/legislation/section/lookup` (tools `search_legislation`, `search_legislation_sections`, `get_legislation_text`, `get_legislation_changes`, `lookup_legislation`); GET `/legislation/proxy/…` to read legislation.gov.uk (commencement dates, published texts, and the made-under record's daily refresh, a background task on the legislation bot). Responses can be large (full Act text). |
| **National Archives case law** | `https://caselaw.nationalarchives.gov.uk` | 443 | HTTPS | Legislation | Searched when research mode includes case law (`legislation_and_case_law` or `case_law_only`). GET requests to `/atom.xml` with query, court, date and order params return an Atom XML feed of judgment metadata; a judgment's text is a GET of its `/data.xml`. |
| **SCTS Scottish judgments** | `https://api.pa.web.scotcourts.gov.uk` (search) + `https://www.scotcourts.gov.uk` (judgment PDFs) | 443 | HTTPS | Legislation | **Only when Scottish judgments are switched on** (Admin Portal → Developer → Configuration → Feature Flags, "Scottish judgments (SCTS)"; off by default; FIX_PLAN P3.20). Searched beside the National Archives in the case-law research modes: POST `/web/search` returns JSON judgment metadata; a judgment's text is a GET of its PDF from `www.scotcourts.gov.uk` (read with pdfplumber). Capped per request (60 searches, 20 PDFs, 2 in flight). No authentication; use agreed with SCTS. |
| **TheyWorkForYou (TWFY)** | `https://www.theyworkforyou.com/api` | 443 | HTTPS | Parliament | **Scotland only.** `getHansard` (Scottish Parliament plenary + written answers; post-filtered to `/sp/` listurls) and `getMSPs` (`get_member_info` — MSP lookup). Requires `TWFY_API_KEY`. Westminster endpoints are no longer used. GET requests, JSON output. |
| **SP Official Report** | `https://www.parliament.scot` | 443 | HTTPS | Parliament | Scottish Parliament plenary & committee transcripts. Crawled at startup and daily by `parliament_crawler.py` (listing/meeting/transcript pages) and fetched live at query time by `get_scottish_plenary_debate` / `get_scottish_committee_transcript`. No authentication. |
| **Scottish Parliament Bills** | `https://data.parliament.scot` | 443 | HTTPS | Parliament | Scottish Parliament (Holyrood) bill search (`search_bills` tool). GET request to `/api/bills` returns all bills; filtering is done client-side. No authentication required. |
| **Scottish Parliament TV** | `https://www.scottishparliament.tv` + `https://scotparl-live.cdn.vustreams.com` | 443 | HTTPS | Parliament | Video deep links — only when `ENABLE_VIDEO_DEEPLINKS=true`. Meeting pages → eventId → HLS `.m3u8` + WebVTT caption segments. Fails soft (feature auto-disables) if unreachable. No authentication. |
| **UK Parliament Hansard API** | `https://hansard-api.parliament.uk` | 443 | HTTPS | Westminster | `search_hansard` (`/search/contributions/{type}.json`) and `get_hansard_debate` (`/debates/debate/{id}.json`): Commons and Lords debates, Westminster Hall, written statements. GET requests, JSON. No authentication. |
| **UK Parliament Members API** | `https://members-api.parliament.uk` | 443 | HTTPS | Westminster | `get_member_info` (`/api/Members/Search`): MP and peer lookup. GET request, JSON. No authentication. |
| **UK Parliament Bills API** | `https://bills-api.parliament.uk` | 443 | HTTPS | Westminster | `search_bills` (`/api/v1/Bills`): UK Parliament bill search. GET request, JSON. No authentication. |
| **Peer bots (federation)** | Each enabled peer's registered base URL | Peer's port | HTTPS / HTTP | All | Only when peers are registered (Admin Portal → Federation tab). The calling bot POSTs to the peer's `/api/consult` and waits for a synchronous JSON answer (300 s timeout), with the peer's API key, if one is set, as `Authorization: Bearer`. |
| **Gmail SMTP** | `smtp.gmail.com` | 465 | SMTPS | All | Password reset emails (if `EMAIL_USER` and `EMAIL_PASS` are configured). Not configured by default in government deployment. |

> **Ollama Cloud Inference note:** When using `:cloud` models, Ollama proxies to third-party AI inference providers whose exact hostnames are managed by Ollama and not statically defined in LexChat. Allowlisting `*.ollama.ai` covers the Ollama registry; actual inference traffic may route to additional provider-specific endpoints. Monitor initial connections with logging enabled to capture resolved FQDNs, or contact Ollama for their current provider domain list.

> **Users' browsers, not the server:** the web UI's stylesheet loads its fonts (Inter, Source Serif 4, JetBrains Mono) from `fonts.googleapis.com`, which serves the font files from `fonts.gstatic.com`. If users' workstations cannot reach them, the UI falls back to system fonts; nothing else is affected.

### 2.3 Connection Behaviour Notes

| Behaviour | Detail |
|---|---|
| **Long-lived streaming connections** | AI responses stream via HTTP POST with `Transfer-Encoding: chunked`. A single response can take **60–300+ seconds**. Proxies with default idle timeouts (typically 60s) will prematurely terminate these connections. **Set proxy read/idle timeout to at least 300 seconds** for traffic to Ollama and OpenRouter endpoints. |
| **Authorization headers** | Requests to Ollama cloud endpoints and OpenRouter carry `Authorization: Bearer <token>`. Ensure the proxy does not strip or modify `Authorization` headers on outbound HTTPS requests. |
| **No WebSocket traffic** | All traffic uses standard HTTP/HTTPS. No WebSocket connections are established. |

---

## Part 3: Firewall & Proxy Allowlist Summary

### 3.1 Installation — FQDNs Required (One-time)

| Service | FQDNs to Allow |
|---|---|
| Python installer | `www.python.org` |
| PostgreSQL installer | `get.enterprisedb.com` |
| PyPI | `pypi.org`, `files.pythonhosted.org` |
| npm (dev machine only) | `registry.npmjs.org` |
| Node.js (dev machine only) | `nodejs.org` |
| GitHub | `github.com`, `objects.githubusercontent.com` |
| Ollama installer | `ollama.com`, `registry.ollama.ai` |

### 3.2 Runtime — FQDNs Required

| Service | FQDNs to Allow | Port | Required? |
|---|---|---|---|
| Ollama Cloud Inference | `*.ollama.ai` + third-party inference endpoints | 443 | **Yes** — if using Ollama provider. Core AI functionality. |
| OpenRouter | `openrouter.ai` | 443 | **Yes** — if using OpenRouter provider. Core AI functionality. |
| LEX Legislation API | `lex.lab.i.ai.gov.uk` | 443 | **Yes** — required for all legislation research (legislation bot). |
| National Archives case law | `caselaw.nationalarchives.gov.uk` | 443 | **Yes** — required for case law research modes (legislation bot). |
| SCTS Scottish judgments | `api.pa.web.scotcourts.gov.uk`, `www.scotcourts.gov.uk` | 443 | **Optional** — only if Scottish judgments are switched on (Developer tab feature flag; legislation bot). Both hosts are needed: the first answers the search, the second serves the judgment PDFs. |
| TheyWorkForYou (TWFY) | `www.theyworkforyou.com` | 443 | **Yes** — required for SP plenary/written-answer search & MSP lookup (parliament bot). |
| SP Official Report | `www.parliament.scot` | 443 | **Yes** — required for SP transcript crawl & retrieval (parliament bot). |
| Scottish Parliament Bills | `data.parliament.scot` | 443 | **Yes** — required for Scottish bill search (parliament bot). |
| Scottish Parliament TV | `www.scottishparliament.tv`, `scotparl-live.cdn.vustreams.com` | 443 | **Optional** — only if `ENABLE_VIDEO_DEEPLINKS=true` (parliament bot). |
| UK Parliament Hansard API | `hansard-api.parliament.uk` | 443 | **Yes** — required for Westminster debate search & retrieval (Westminster bot). |
| UK Parliament Members API | `members-api.parliament.uk` | 443 | **Yes** — required for MP and peer lookup (Westminster bot). |
| UK Parliament Bills API | `bills-api.parliament.uk` | 443 | **Yes** — required for UK bill search (Westminster bot). |
| Peer bots (federation) | Each registered peer's host | Peer's port | **Optional** — only if peers are registered (Admin Portal → Federation tab). |
| Gmail SMTP | `smtp.gmail.com` | 465 | **Optional** — only if email notifications are configured. |

### 3.3 Minimum Required Inbound Access

| Rule | Port |
|---|---|
| HTTPS — user access to web application | 443 |

---

## Part 4: SSL/TLS Inspection Considerations

| Component | Impact | Recommendation |
|---|---|---|
| **pip (Python packages)** | pip verifies PyPI certificates. TLS interception causes SSL errors unless the corporate CA is trusted. | Bypass for `pypi.org`, `files.pythonhosted.org`, OR `pip install --cert /path/to/corporate-ca.crt`. |
| **npm (dev machine)** | npm verifies registry certificates. | Bypass for `registry.npmjs.org`, OR `npm config set cafile /path/to/corporate-ca.crt`. |
| **Git (GitHub)** | Git verifies HTTPS certificates on clone/pull. | Bypass for `github.com`, OR `git config --global http.sslCAInfo /path/to/corporate-ca.crt`. |
| **Ollama cloud connections** | Ollama uses key-pair authentication alongside HTTPS. TLS interception may interfere. | Bypass TLS inspection for `*.ollama.ai` and Ollama cloud provider domains. |
| **OpenRouter** | Standard HTTPS REST API. | Bypass TLS inspection for `openrouter.ai`. |
| **LEX API** | Standard HTTPS REST API. | Bypass TLS inspection for `lex.lab.i.ai.gov.uk`. |
| **National Archives case law** | Standard HTTPS GET; returns Atom XML. | Bypass TLS inspection for `caselaw.nationalarchives.gov.uk`. |
| **SCTS Scottish judgments** | HTTPS JSON POST (search) and PDF GET. Only when Scottish judgments are switched on (Developer tab feature flag). | Bypass TLS inspection for `api.pa.web.scotcourts.gov.uk` and `www.scotcourts.gov.uk`. |
| **TheyWorkForYou (TWFY)** | Standard HTTPS REST API. Carries `TWFY_API_KEY` as a query parameter. | Bypass TLS inspection for `www.theyworkforyou.com`. |
| **SP Official Report** | HTML pages (crawler + live retrieval). Cloudflare-fronted; no `Last-Modified`/`ETag`. | Bypass TLS inspection for `www.parliament.scot`. |
| **Scottish Parliament Bills** | Standard HTTPS REST API. No authentication. | Bypass TLS inspection for `data.parliament.scot`. |
| **Scottish Parliament TV** | HTML + HLS `.m3u8`/WebVTT. Only when video deep links are enabled. | Bypass TLS inspection for `www.scottishparliament.tv` and `scotparl-live.cdn.vustreams.com`. |
| **UK Parliament APIs** | Standard HTTPS REST APIs (JSON). No authentication. Westminster bot only. | Bypass TLS inspection for `hansard-api.parliament.uk`, `members-api.parliament.uk` and `bills-api.parliament.uk`. |

---

## Part 5: Configuration File Reference

| File | Purpose |
|---|---|
| `server_py/.env` | Startup defaults: `DATABASE_URL`, `JWT_SECRET`, `OLLAMA_BASE_URL`, `OLLAMA_API_KEY`, `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`, `TWFY_API_KEY` |
| `server_py/src/config.py` | Application settings, model lists, system prompts, LEX API URL |
| `server_py/src/agent/provider_factory.py` | Provider resolution, ContextVar, queue/semaphore caching |
| `server_py/src/agent/tools/` | Tool clients: LEX API and case law (National Archives, SCTS) for the legislation bot; TWFY and Scottish Parliament for the parliament bot; UK Parliament APIs for the Westminster bot (`westminster.py`) |
| `server_py/src/services/email_service.py` | Gmail SMTP email sender (optional) |
| `server_py/test_apis.ps1` | Connectivity test script — checks the LEX API, the National Archives and SCTS (tests 8a and 8b are the two SCTS hosts), TheyWorkForYou, `data.parliament.scot` and the SP Official Report. It does not test Ollama, OpenRouter, SP TV or the Westminster bot's UK Parliament APIs. |
| Scottish judgments switch (Admin Portal → Developer → Configuration → Feature Flags, **"Scottish judgments (SCTS)"**) | Switches on Scottish judgments from SCTS (default off; takes effect on the next question, no restart). Switch it on only after `test_apis.ps1` tests 8a and 8b pass on this server. Needs pdfplumber installed (check: `python -c "import pdfplumber"`); without it searches work but judgment texts cannot be read. If it is missing, install it offline with `deployment\install_pdf_support.ps1` (wheels committed in `deployment\pdf_wheels\`). The environment variable `SCTS_CASELAW_ENABLED` is only the flag's default until the flag is first saved on the Developer tab; after that the tab decides, so do not set it. If it is ever used, set it as a Windows machine environment variable, never in `.env.native` (`start_native.cmd` copies that over `.env` on every start). |
| `deployment/certs/lexchat.crt` | TLS certificate for HTTPS on port 443 |
| `deployment/certs/lexchat.key` | TLS private key |
| `deployment/install_native_offline.ps1` | Air-gapped native installer |
| `deployment/start_native.cmd` | Start script: PostgreSQL → Ollama → FastAPI (uvicorn) |
| `deployment/start_parliament.cmd` | The same for the parliament bot on its own server (loads `bots\parliament\.env` over `.env.native`) |
| `deployment/stop_native.cmd` | Stop script: kills uvicorn, Ollama, PostgreSQL service |
| `deployment/package_offline_native.ps1` | Packages all deps + pre-built frontend for air-gap transfer |
