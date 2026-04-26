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

### 1.1 Native Windows Deployment (`install_native.ps1`)

| Website / URL | What is Downloaded | Script |
|---|---|---|
| `https://community.chocolatey.org/install.ps1` | Chocolatey package manager | `deployment/install_native.ps1` |
| `https://community.chocolatey.org/` (NuGet feed) | Chocolatey packages: `python` (3.11.9), `postgresql15` | `deployment/install_native.ps1` |
| `https://ollama.com/download/OllamaSetup.exe` | Ollama Windows installer | `deployment/install_native.ps1` |
| `https://pypi.org/`, `https://files.pythonhosted.org/` | Python packages from `server_py/requirements.txt` | `deployment/install_native.ps1` |
| `https://github.com/<repo>`, `https://objects.githubusercontent.com/` | Git repository clone/pull | `git clone` / `git pull` |
| `https://registry.ollama.ai/`, `https://ollama.com/` | AI model registration for cloud-routed models | First model request via Ollama |

### 1.2 Frontend Build (Developer Machine Only)

The frontend is **not built on the target server**. It is built on the developer's machine and the output (`client/dist/`) is committed to the repository.

| Website / URL | What is Downloaded | Tool |
|---|---|---|
| `https://registry.npmjs.org/` | Node.js packages from `client/package.json` | `npm install` |

Node.js v22 portable install used on dev machine (`C:\Users\rhett\node_portable\`). Not required on target server.

### 1.3 Air-Gapped Installation (`install_native_offline.ps1`)

No internet required on the target. All dependencies are pre-packaged on the dev machine using `deployment/package_offline_native.ps1` and transferred via USB/secure file share.

### 1.4 Updates

Target server updates via `git pull` from GitHub:
- `https://github.com/<repo>` — code and pre-built `client/dist/` assets
- `https://pypi.org/` — only if Python dependencies have changed (run `pip install -r requirements.txt` after pull)

---

## Part 2: Runtime — Network Traffic & Ports

### 2.1 Inbound Ports

| Port | Protocol | Service | Description |
|---|---|---|---|
| **443** | HTTPS | FastAPI (uvicorn) | Application entry point — serves both the web UI and the `/api` backend. Uses organisational TLS certificate from `deployment/certs/`. |
| **11434** | HTTP | Ollama | AI inference server. Only accessible on `localhost`; not exposed externally. |
| **5432** | TCP | PostgreSQL | Database. Only accessible on `localhost`. |

### 2.2 Outbound Traffic — External Services

| Destination | URL / Host | Port | Protocol | Description |
|---|---|---|---|---|
| **Ollama Cloud Models** | `https://registry.ollama.ai/` and third-party inference endpoints | 443 | HTTPS | When using cloud-tagged models (e.g. `mistral-large-3:675b-cloud`), Ollama routes requests to remote inference providers. Traffic includes the full chat context sent as JSON with **long-lived streaming responses** (60–300+ seconds per request). Authenticated via Ollama API key (`Authorization: Bearer` header). |
| **OpenRouter** | `https://openrouter.ai/api/v1` | 443 | HTTPS | Alternative LLM provider. If OpenRouter is set as the active provider in the Admin Portal, all AI requests route here instead of Ollama. Also a long-lived streaming connection. Requires `OPENROUTER_API_KEY`. Only needed if OpenRouter provider is used. |
| **LEX API** (Legislation) | `https://lex-api.victoriousdesert-f8e685e0.uksouth.azurecontainerapps.io` | 443 | HTTPS | Worker agent calls this API to search UK legislation and retrieve section text. Called on-demand when the AI agent invokes `search_legislation`, `search_legislation_sections`, or `get_legislation_text` tools. JSON POST requests with search queries and legislation IDs. |
| **Google Search** | `https://www.google.com/search` | 443 | HTTPS | Used by the Deep Research agent's `search_web` tool when research mode includes web search. Requests use a standard browser User-Agent. Only triggered in web-search-enabled research modes. |
| **Gmail SMTP** | `smtp.gmail.com` | 465 | SMTPS | Password reset emails (if `EMAIL_USER` and `EMAIL_PASS` are configured). Not configured by default in government deployment. |

> **Ollama Cloud Inference note:** When using `:cloud` models, Ollama proxies to third-party AI inference providers whose exact hostnames are managed by Ollama and not statically defined in LexChat. Allowlisting `*.ollama.ai` covers the Ollama registry; actual inference traffic may route to additional provider-specific endpoints. Monitor initial connections with logging enabled to capture resolved FQDNs, or contact Ollama for their current provider domain list.

### 2.3 Connection Behaviour Notes

| Behaviour | Detail |
|---|---|
| **Long-lived streaming connections** | AI responses stream via HTTP POST with `Transfer-Encoding: chunked`. A single response can take **60–300+ seconds**. Proxies with default idle timeouts (typically 60s) will prematurely terminate these connections. **Set proxy read/idle timeout to at least 300 seconds** for traffic to Ollama and OpenRouter endpoints. |
| **Authorization headers** | Requests to Ollama cloud endpoints and OpenRouter carry `Authorization: Bearer <token>`. Ensure the proxy does not strip or modify `Authorization` headers on outbound HTTPS requests. |
| **No WebSocket traffic** | All traffic uses standard HTTP/HTTPS. No WebSocket connections are established. |
| **Spoofed User-Agent** | The Deep Research web search feature (`server_py/src/agent/web_search.py`) sends requests to `www.google.com` with a Chrome browser User-Agent string. Proxies enforcing User-Agent policies may flag these. |

---

## Part 3: Firewall & Proxy Allowlist Summary

### 3.1 Installation — FQDNs Required (One-time)

| Service | FQDNs to Allow |
|---|---|
| Chocolatey | `community.chocolatey.org`, `packages.chocolatey.org` |
| PyPI | `pypi.org`, `files.pythonhosted.org` |
| npm (dev machine only) | `registry.npmjs.org` |
| GitHub | `github.com`, `objects.githubusercontent.com` |
| Ollama installer | `ollama.com`, `registry.ollama.ai` |

### 3.2 Runtime — FQDNs Required

| Service | FQDNs to Allow | Port | Required? |
|---|---|---|---|
| Ollama Cloud Inference | `*.ollama.ai` + third-party inference endpoints | 443 | **Yes** — if using Ollama provider. Core AI functionality. |
| OpenRouter | `openrouter.ai` | 443 | **Yes** — if using OpenRouter provider. Core AI functionality. |
| LEX Legislation API | `lex-api.victoriousdesert-f8e685e0.uksouth.azurecontainerapps.io` | 443 | **Yes** — required for all legislation research. |
| Google Web Search | `www.google.com` | 443 | **Optional** — only if Deep Research web search mode is used. |
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
| **LEX API** | Standard HTTPS REST API. | Bypass TLS inspection for the LEX API hostname. |

---

## Part 5: Configuration File Reference

| File | Purpose |
|---|---|
| `server_py/.env` | Startup defaults: `DATABASE_URL`, `JWT_SECRET`, `OLLAMA_BASE_URL`, `OLLAMA_API_KEY`, `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL` |
| `server_py/src/config.py` | Application settings, model lists, system prompts, LEX API URL |
| `server_py/src/agent/provider_factory.py` | Provider resolution, ContextVar, queue/semaphore caching |
| `server_py/src/agent/tools.py` | LEX API client — `search_legislation`, `search_legislation_sections`, `get_legislation_text` |
| `server_py/src/agent/web_search.py` | Google web search for Deep Research mode |
| `server_py/src/services/email_service.py` | Gmail SMTP email sender (optional) |
| `deployment/certs/lexchat.crt` | TLS certificate for HTTPS on port 443 |
| `deployment/certs/lexchat.key` | TLS private key |
| `deployment/install_native.ps1` | Internet-connected native installer |
| `deployment/install_native_offline.ps1` | Air-gapped native installer |
| `deployment/start_native.cmd` | Start script: PostgreSQL → Ollama → FastAPI (uvicorn) |
| `deployment/stop_native.cmd` | Stop script: kills uvicorn, Ollama, PostgreSQL service |
| `deployment/package_offline_native.ps1` | Packages all deps + pre-built frontend for air-gap transfer |
| `deployment/package_frontend_update.ps1` | Packages only the built frontend for a lightweight update |
| `deployment/apply_frontend_update.ps1` | Applies a frontend update zip on the target server |
