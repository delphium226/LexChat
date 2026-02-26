# LexChat — Network Access & Dependency Reference

This document lists all external websites, files, and network endpoints that LexChat
requires during **installation/build** and during **runtime operation**, along with
the ports used. It is intended for corporate proxy and firewall administrators who
need to configure allowlist rules.

---

## Part 1: Installation & Build — Downloads and External Access

These are the websites and resources the installation scripts and build process
must be able to reach. Access is only required during setup, not at runtime
(unless performing an update).

### 1.1 Docker Deployment (`setup_server.ps1` / `rebuild_docker.ps1`)

| Website / URL | What is Downloaded | Script / File |
|---|---|---|
| `https://community.chocolatey.org/install.ps1` | Chocolatey package manager installer script | `deployment/setup_server.ps1` |
| `https://community.chocolatey.org/` (NuGet feed) | Chocolatey packages: `git`, `docker-desktop` | `deployment/setup_server.ps1` |
| `https://registry-1.docker.io`, `https://auth.docker.io`, `https://production.cloudflare.docker.com` | Docker base images: `postgres:15`, `ollama/ollama`, `curlimages/curl`, `python:3.11-slim`, `node:20-slim`, `nginx:alpine` | `docker-compose.yml`, `server_py/Dockerfile`, `client/Dockerfile` |
| `https://deb.debian.org/`, `https://security.debian.org/` | Debian apt packages (`build-essential`, `libpq-dev`, `curl`) installed inside `python:3.11-slim` container during build | `server_py/Dockerfile` (`apt-get install`) |
| `https://pypi.org/`, `https://files.pythonhosted.org/` | Python packages listed in `server_py/requirements.txt` (fastapi, uvicorn, sqlalchemy, httpx, passlib, bcrypt, python-jose, pydantic-settings, asyncpg, python-multipart, python-dotenv, faker, pytest, pytest-asyncio) | `server_py/Dockerfile` (runs `pip install`) |
| `https://registry.npmjs.org/` | Node.js packages listed in `client/package.json` (react, react-dom, react-router-dom, axios, marked, react-markdown, recharts, remark-gfm, vite, tailwindcss, eslint, etc.) | `client/Dockerfile` (runs `npm install`) |
| `https://github.com/<repo>`, `https://objects.githubusercontent.com/` | Git repository clone (e.g. `https://github.com/delphium226/LexChat.git`) | `deployment/setup_server.ps1` |
| `https://registry.ollama.ai/`, `https://ollama.com/` | AI cloud model registrations: `mistral-large-3:675b-cloud`, `cogito-2.1:671b-cloud`, `kimi-k2-thinking:cloud`, `minimax-m2:cloud`, `deepseek-v3.2:cloud`, `glm-4.6:cloud` | `docker-compose.yml` (ollama-puller service) |

### 1.2 Native Windows Deployment (`install_native.ps1`)

| Website / URL | What is Downloaded | Script / File |
|---|---|---|
| `https://community.chocolatey.org/install.ps1` | Chocolatey package manager installer script | `deployment/install_native.ps1` |
| `https://community.chocolatey.org/` (NuGet feed) | Chocolatey packages: `python` (3.11.9), `nodejs-lts`, `postgresql15` | `deployment/install_native.ps1` |
| `https://ollama.com/download/OllamaSetup.exe` | Ollama Windows installer executable | `deployment/install_native.ps1` |
| `https://pypi.org/`, `https://files.pythonhosted.org/` | Python packages from `server_py/requirements.txt` | `deployment/install_native.ps1` (runs `pip install`) |
| `https://registry.npmjs.org/` | Node.js packages from `client/package.json` | `deployment/install_native.ps1` (runs `npm install`) |
| `https://registry.ollama.ai/`, `https://ollama.com/` | AI model: `mistral-large` (pulled via `ollama pull`) | `deployment/install_native.ps1` |

### 1.3 Update Scripts

| Website / URL | What is Downloaded | Script / File |
|---|---|---|
| `https://github.com/<repo>`, `https://objects.githubusercontent.com/` | Latest code changes via `git pull` | `deployment/deploy_update.ps1`, `deployment/update_native.ps1` |
| `https://pypi.org/`, `https://files.pythonhosted.org/` | Updated Python packages | `deployment/update_native.ps1` |
| `https://registry.npmjs.org/` | Updated Node.js packages + `serve` package (via `npx -y serve`) | `deployment/update_native.ps1`, `deployment/start_native.cmd` |

### 1.4 Summary of Files Downloaded During Installation

| Artefact | Source | Filename | File Extension |
|---|---|---|---|
| Chocolatey installer | community.chocolatey.org | install | `.ps1` |
| Python 3.11.9 (via Chocolatey) | community.chocolatey.org | python3 | `.nupkg` |
| Node.js LTS (via Chocolatey) | community.chocolatey.org | nodejs-lts | `.nupkg` |
| PostgreSQL 15 (via Chocolatey) | community.chocolatey.org | postgresql15 | `.nupkg` |
| Git (via Chocolatey) | community.chocolatey.org | git | `.nupkg` |
| Docker Desktop (via Chocolatey) | community.chocolatey.org | docker-desktop | `.nupkg` |
| Ollama Windows installer | ollama.com | OllamaSetup | `.exe` |
| Docker image: `postgres:15` | registry-1.docker.io | postgres:15 | `.tar.gz` (layers), `.json` (manifest) |
| Docker image: `ollama/ollama` | registry-1.docker.io | ollama/ollama | `.tar.gz` (layers), `.json` (manifest) |
| Docker image: `curlimages/curl` | registry-1.docker.io | curlimages/curl | `.tar.gz` (layers), `.json` (manifest) |
| Docker image: `python:3.11-slim` | registry-1.docker.io | python:3.11-slim | `.tar.gz` (layers), `.json` (manifest) |
| Docker image: `node:20-slim` | registry-1.docker.io | node:20-slim | `.tar.gz` (layers), `.json` (manifest) |
| Docker image: `nginx:alpine` | registry-1.docker.io | nginx:alpine | `.tar.gz` (layers), `.json` (manifest) |
| Debian apt packages | deb.debian.org | build-essential, libpq-dev, curl | `.deb` |
| Python pip packages | pypi.org | (per requirements.txt) | `.whl` / `.tar.gz` |
| Node.js npm packages | registry.npmjs.org | (per package.json) | `.tgz` |
| Ollama cloud model registrations | registry.ollama.ai | (model manifests) | `.json` (manifest) |

---

## Part 2: Runtime — Network Traffic & Ports

These are the websites and services accessed while the application is running
and serving users.

### 2.1 Inbound Ports (Listening Services)

| Port | Protocol | Service | Description |
|---|---|---|---|
| **80** | HTTP | Nginx (Docker) | Frontend web server. Serves the React SPA and proxies `/api` requests to the backend. |
| **8080** | HTTP | FastAPI (Native) | Backend API server and static frontend file server in native Windows deployment. |
| **8000** | HTTP | FastAPI (Docker) | Backend API server. Handles authentication, chat, user management, and agent orchestration. |
| **11434** | HTTP | Ollama | AI model inference server. Exposed on `11434` in Docker; `localhost:11434` in native. |
| **5432** | TCP | PostgreSQL | Database. Only accessible within the Docker network or on `localhost` in native deployment. |

### 2.2 Outbound Traffic — External Services

| Destination | URL / Host | Port | Protocol | HTTP Method | Traffic Description |
|---|---|---|---|---|---|
| **Ollama Cloud Models** | `https://registry.ollama.ai/` and third-party cloud inference endpoints (see note below) | 443 | HTTPS | POST (streaming) | The Ollama server routes requests for cloud-tagged models (e.g. `mistral-large-3:675b-cloud`) to remote inference providers. Traffic includes the full chat context (system prompt + conversation history) sent as JSON, and **long-lived streaming responses** back (chunked transfer encoding, connections may last 60–300+ seconds). Authenticated via Ollama API key or SSH keypair (`Authorization: Bearer` header). This is the primary and most frequent outbound traffic. |
| **LEX API** (Legislation) | `https://lex.lab.i.ai.gov.uk/` (default Docker) **and** `https://lex-api.victoriousdesert-f8e685e0.uksouth.azurecontainerapps.io` (native/.env.native) | 443 | HTTPS | POST | The Worker agent calls this API to search UK legislation and retrieve legislation text. Sends JSON POST requests with search queries and legislation IDs. Receives JSON responses with legislation metadata and content. Called on-demand when the AI agent invokes `search_legislation` or `get_legislation_text` tools. |
| **Google Search** | `https://www.google.com/search` | 443 | HTTPS | GET | The Deep Research agent's `search_web` tool performs Google web searches. Sends HTTP GET requests with query parameters. **Note:** Requests use a spoofed Chrome User-Agent string (`Mozilla/5.0 ... Chrome/120.0.0.0`). Receives HTML search result pages which are parsed for titles and links. Only triggered when a user activates Deep Research mode. |
| **Gmail SMTP** | `smtp.gmail.com` | 465 | SMTPS (SSL) | N/A (SMTP) | Welcome emails and password reset emails are sent via Gmail's SMTP server. Sends authenticated SMTP traffic containing HTML email bodies. Only active if `EMAIL_USER` and `EMAIL_PASS` environment variables are configured. |

> **Ollama Cloud Inference — Important Note for Proxy Administrators:**
> When using cloud-tagged models (model names ending in `:cloud`), the Ollama server
> acts as a proxy to third-party AI inference providers. The exact destination hosts
> are managed internally by Ollama and are **not statically defined** in the LexChat
> codebase. Allowlisting `*.ollama.ai` covers the Ollama registry, but the actual
> inference traffic may route to provider-specific endpoints. If strict egress
> filtering is required, monitor initial connections with logging enabled to capture
> the resolved FQDNs, or contact Ollama for a current list of cloud provider domains.

### 2.3 Connection Behaviour Notes for Proxy Configuration

| Behaviour | Detail |
|---|---|
| **Long-lived streaming connections** | AI chat responses are streamed from Ollama using HTTP POST with `Transfer-Encoding: chunked`. A single response can take **60–300+ seconds**. Proxies with default idle timeouts (commonly 60s) will prematurely terminate these connections. **Recommendation:** Set proxy read/idle timeout to at least **300 seconds** for traffic to Ollama endpoints. |
| **Spoofed User-Agent** | The Deep Research web search feature (`server_py/src/agent/web_search.py`) sends requests to `www.google.com` with a Chrome browser User-Agent string. Proxies that enforce User-Agent policies or flag non-browser traffic using browser UAs may block or flag these requests. |
| **Authorization headers** | Requests to Ollama cloud endpoints carry an `Authorization: Bearer <token>` header. Ensure the proxy does not strip or modify `Authorization` headers on outbound HTTPS requests. |
| **No WebSocket traffic** | Despite the Nginx config including WebSocket upgrade headers (`Upgrade`, `Connection`), all external traffic uses standard HTTP/HTTPS. WebSocket headers are only used internally between Nginx and the backend within Docker. |

### 2.4 Internal Traffic (Docker Network Only)

These connections stay within the Docker bridge network and do not leave the host.

| Source | Destination | Port | Description |
|---|---|---|---|
| Frontend (Nginx) | Backend (FastAPI) | 8000 | Nginx reverse-proxies all `/api` requests to the backend container. |
| Backend (FastAPI) | Ollama | 11434 | Backend sends chat/inference requests to the Ollama container. |
| Backend (FastAPI) | PostgreSQL | 5432 | Backend reads/writes user data, chat history, messages, and learning data. |
| ollama-puller (curl) | Ollama | 11434 | One-time model pull requests at container startup. |

---

## Part 3: Firewall & Proxy Allowlist Summary

### 3.1 Complete FQDN Allowlist — Installation

All domains required during installation and build. All traffic is HTTPS on port 443.

| Service | FQDNs to Allow | Notes |
|---|---|---|
| Chocolatey | `community.chocolatey.org`, `packages.chocolatey.org`, `chocolatey.org` | Windows automated install only |
| Docker Hub | `registry-1.docker.io`, `auth.docker.io`, `production.cloudflare.docker.com`, `docker.io` | Docker deployment only |
| Debian Packages | `deb.debian.org`, `security.debian.org` | Accessed inside Docker build (`apt-get install`) |
| PyPI | `pypi.org`, `files.pythonhosted.org` | Python package downloads |
| npm Registry | `registry.npmjs.org` | Node.js package downloads |
| GitHub | `github.com`, `objects.githubusercontent.com` | Git clone/pull and release assets |
| Ollama | `ollama.com`, `registry.ollama.ai` | Installer download + model registration |

### 3.2 Complete FQDN Allowlist — Runtime

| Service | FQDNs to Allow | Port | Protocol | Required? |
|---|---|---|---|---|
| Ollama Cloud Inference | `*.ollama.ai` + third-party inference provider domains (see note in 2.2) | 443 | HTTPS | **Yes** — Core functionality. Without this, AI chat does not work (unless using local models). |
| LEX Legislation API | `lex.lab.i.ai.gov.uk`, `lex-api.victoriousdesert-f8e685e0.uksouth.azurecontainerapps.io` | 443 | HTTPS | **Yes** — Required for legislation search and retrieval. Allow both; the active one depends on deployment configuration (`LEX_API_URL` env var). |
| Google Web Search | `www.google.com` | 443 | HTTPS | **Optional** — Only needed if Deep Research mode is enabled (`ENABLE_DEEP_RESEARCH=true`). |
| Gmail SMTP | `smtp.gmail.com` | 465 | SMTPS | **Optional** — Only needed if email notifications are configured (`EMAIL_USER` / `EMAIL_PASS` env vars). |

### 3.3 Minimum Required Inbound Access

| Rule | Port | Required? |
|---|---|---|
| HTTP (Frontend) | 80 (Docker) or 8080 (Native) | **Yes** — User access to the web application. |
| Backend API | 8000 (Docker) | Only if accessed directly (normally proxied via Nginx on port 80). |

---

## Part 4: SSL/TLS Inspection Considerations

Corporate proxies that perform **TLS interception (MITM SSL inspection)** may
cause failures with the following components:

| Component | Impact | Recommendation |
|---|---|---|
| **Docker image pulls** | Docker CLI validates registry certificates. TLS interception will cause `x509: certificate signed by unknown authority` errors. | Bypass TLS inspection for `registry-1.docker.io`, `auth.docker.io`, `production.cloudflare.docker.com`, OR install the corporate CA certificate into the Docker daemon trust store. |
| **Ollama cloud connections** | Ollama uses SSH key-pair authentication alongside HTTPS. TLS interception may interfere with the authentication handshake. | Bypass TLS inspection for `*.ollama.ai` and Ollama cloud inference provider domains. |
| **pip (Python packages)** | pip verifies PyPI certificates. Interception causes SSL errors unless the corporate CA is trusted. | Bypass for `pypi.org`, `files.pythonhosted.org`, OR set `pip install --cert /path/to/corporate-ca.crt`. |
| **npm (Node.js packages)** | npm verifies registry certificates. | Bypass for `registry.npmjs.org`, OR set `npm config set cafile /path/to/corporate-ca.crt`. |
| **Git (GitHub)** | Git verifies HTTPS certificates on clone/pull. | Bypass for `github.com`, OR set `git config --global http.sslCAInfo /path/to/corporate-ca.crt`. |
| **Google Search** | Standard HTTPS GET. Generally tolerant of corporate CA if trusted at OS level. | Usually no special action needed. |
| **Gmail SMTP** | Uses SMTPS (port 465, implicit TLS). Most corporate proxies do not intercept SMTP. | Ensure port 465 outbound is open if email is configured. |

---

## Part 5: Configuration File Reference

| File | Purpose |
|---|---|
| `docker-compose.yml` | Defines all services, Docker images, ports, and environment variables for Docker deployment. |
| `server_py/Dockerfile` | Backend container build: base image (`python:3.11-slim`), apt packages, pip install. |
| `client/Dockerfile` | Frontend container build: base images (`node:20-slim`, `nginx:alpine`), npm install, build. |
| `nginx.conf` | Nginx reverse proxy configuration: serves frontend on port 80, proxies `/api` to backend:8000. |
| `server_py/requirements.txt` | Python package dependencies (14 packages). |
| `client/package.json` | Node.js package dependencies (7 runtime + 12 dev dependencies). |
| `server_py/src/config.py` | Application settings including `LEX_API_URL`, `OLLAMA_BASE_URL`, email config. |
| `deployment/install_native.ps1` | Native Windows installer: downloads Chocolatey, Python, Node.js, PostgreSQL, Ollama. |
| `deployment/setup_server.ps1` | Server bootstrap: downloads Chocolatey, Git, Docker Desktop; clones repo. |
| `deployment/start_native.cmd` | Native launcher: starts backend (uvicorn), frontend (`npx serve`). |
| `deployment/update_native.ps1` | Native updater: `git pull`, `pip install`, `npm install`, `npm run build`. |
| `deployment/deploy_update.ps1` | Docker updater: `git pull`, `rebuild_docker.ps1`. |
| `rebuild_docker.ps1` | Docker rebuild: `docker-compose down` then `docker-compose up --build`. |
| `server_py/src/agent/web_search.py` | Google web search implementation for Deep Research. |
| `server_py/src/agent/tools.py` | LEX API client for legislation search/retrieval. |
| `server_py/src/services/email_service.py` | Gmail SMTP email sender for welcome/reset emails. |
