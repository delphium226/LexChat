# LexChat — Network Access & Dependency Reference

This document lists all external websites, files, and network endpoints that LexChat
requires during **installation/build** and during **runtime operation**, along with
the ports used.

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
| `https://hub.docker.com/` / `registry-1.docker.io` | Docker base images: `postgres:15`, `ollama/ollama`, `curlimages/curl`, `python:3.11-slim`, `node:20-slim`, `nginx:alpine` | `docker-compose.yml`, `server_py/Dockerfile`, `client/Dockerfile` |
| `https://pypi.org/` | Python packages listed in `server_py/requirements.txt` (fastapi, uvicorn, sqlalchemy, httpx, passlib, bcrypt, python-jose, pydantic-settings, asyncpg, python-multipart, python-dotenv, faker, pytest, pytest-asyncio) | `server_py/Dockerfile` (runs `pip install`) |
| `https://registry.npmjs.org/` | Node.js packages listed in `client/package.json` (react, react-dom, react-router-dom, axios, marked, react-markdown, recharts, remark-gfm, vite, tailwindcss, eslint, etc.) | `client/Dockerfile` (runs `npm install`) |
| `https://github.com/<repo>` | Git repository clone (e.g. `https://github.com/delphium226/LexChat.git`) | `deployment/setup_server.ps1` |
| Ollama model registry (`https://registry.ollama.ai/`) | AI model weights: `mistral-large-3:675b-cloud`, `cogito-2.1:671b-cloud`, `kimi-k2-thinking:cloud`, `minimax-m2:cloud`, `deepseek-v3.2:cloud`, `glm-4.6:cloud` | `docker-compose.yml` (ollama-puller service) |

### 1.2 Native Windows Deployment (`install_native.ps1`)

| Website / URL | What is Downloaded | Script / File |
|---|---|---|
| `https://community.chocolatey.org/install.ps1` | Chocolatey package manager installer script | `deployment/install_native.ps1` |
| `https://community.chocolatey.org/` (NuGet feed) | Chocolatey packages: `python` (3.11.9), `nodejs-lts`, `postgresql15` | `deployment/install_native.ps1` |
| `https://ollama.com/download/OllamaSetup.exe` | Ollama Windows installer executable | `deployment/install_native.ps1` |
| `https://pypi.org/` | Python packages from `server_py/requirements.txt` | `deployment/install_native.ps1` (runs `pip install`) |
| `https://registry.npmjs.org/` | Node.js packages from `client/package.json` | `deployment/install_native.ps1` (runs `npm install`) |
| Ollama model registry (`https://registry.ollama.ai/`) | AI model: `mistral-large` (pulled via `ollama pull`) | `deployment/install_native.ps1` |

### 1.3 Update Scripts

| Website / URL | What is Downloaded | Script / File |
|---|---|---|
| `https://github.com/<repo>` | Latest code changes via `git pull` | `deployment/deploy_update.ps1`, `deployment/update_native.ps1` |
| `https://pypi.org/` | Updated Python packages | `deployment/update_native.ps1` |
| `https://registry.npmjs.org/` | Updated Node.js packages + `serve` package (via `npx -y serve`) | `deployment/update_native.ps1`, `deployment/start_native.cmd` |

### 1.4 Summary of Files Downloaded During Installation

| File / Artifact | Source | Approx. Size |
|---|---|---|
| Chocolatey installer (`install.ps1`) | community.chocolatey.org | ~100 KB |
| Python 3.11.9 (via Chocolatey) | community.chocolatey.org | ~30 MB |
| Node.js LTS (via Chocolatey) | community.chocolatey.org | ~30 MB |
| PostgreSQL 15 (via Chocolatey) | community.chocolatey.org | ~200 MB |
| Git (via Chocolatey) | community.chocolatey.org | ~50 MB |
| Docker Desktop (via Chocolatey) | community.chocolatey.org | ~500 MB |
| `OllamaSetup.exe` | ollama.com | ~100 MB |
| Docker image: `postgres:15` | Docker Hub | ~380 MB |
| Docker image: `ollama/ollama` | Docker Hub | ~1 GB |
| Docker image: `curlimages/curl` | Docker Hub | ~10 MB |
| Docker image: `python:3.11-slim` | Docker Hub | ~150 MB |
| Docker image: `node:20-slim` | Docker Hub | ~200 MB |
| Docker image: `nginx:alpine` | Docker Hub | ~40 MB |
| Python pip packages | PyPI | ~50 MB |
| Node.js npm packages | npm registry | ~200 MB |
| Ollama cloud model registrations | registry.ollama.ai | Minimal (cloud-routed models) |

---

## Part 2: Runtime — Network Traffic & Ports

These are the websites and services accessed while the application is running
and serving users.

### 2.1 Inbound Ports (Listening Services)

| Port | Protocol | Service | Description |
|---|---|---|---|
| **80** | HTTP | Nginx (Docker) | Frontend web server. Serves the React SPA and proxies `/api` requests to the backend. |
| **3000** | HTTP | `npx serve` (Native) | Frontend static file server in native Windows deployment. |
| **8000** | HTTP | FastAPI / Uvicorn | Backend API server. Handles authentication, chat, user management, and agent orchestration. |
| **11434** | HTTP | Ollama | AI model inference server. Exposed on `11434` in Docker; `localhost:11434` in native. |
| **5432** | TCP | PostgreSQL | Database. Only accessible within the Docker network or on `localhost` in native deployment. |

### 2.2 Outbound Traffic — External Services

| Destination | URL / Host | Port | Protocol | Traffic Description |
|---|---|---|---|---|
| **Ollama Cloud Models** | `https://registry.ollama.ai/` and Ollama's cloud inference endpoints | 443 | HTTPS | The Ollama server routes requests for cloud-tagged models (e.g. `mistral-large-3:675b-cloud`) to remote inference providers. Traffic includes the full chat context (system prompt + conversation history) sent as JSON, and streamed model responses back. Authenticated via Ollama API key or SSH keypair. This is the primary and most frequent outbound traffic. |
| **LEX API** (Legislation) | `https://lex.lab.i.ai.gov.uk/` (default) or `https://lex-api.victoriousdesert-f8e685e0.uksouth.azurecontainerapps.io` (native) | 443 | HTTPS | The Worker agent calls this API to search UK legislation and retrieve legislation text. Sends JSON POST requests with search queries and legislation IDs. Receives JSON responses with legislation metadata and content. Called on-demand when the AI agent invokes `search_legislation` or `get_legislation_text` tools. |
| **Google Search** | `https://www.google.com/search` | 443 | HTTPS | The Deep Research agent's `search_web` tool performs Google web searches. Sends HTTP GET requests with query parameters. Receives HTML search result pages which are parsed for titles and links. Only triggered when a user activates Deep Research mode. |
| **Gmail SMTP** | `smtp.gmail.com` | 465 | SMTPS (SSL) | Welcome emails and password reset emails are sent via Gmail's SMTP server. Sends authenticated SMTP traffic containing HTML email bodies. Only active if `EMAIL_USER` and `EMAIL_PASS` environment variables are configured. |

### 2.3 Internal Traffic (Docker Network Only)

These connections stay within the Docker bridge network and do not leave the host.

| Source | Destination | Port | Description |
|---|---|---|---|
| Frontend (Nginx) | Backend (FastAPI) | 8000 | Nginx reverse-proxies all `/api` requests to the backend container. |
| Backend (FastAPI) | Ollama | 11434 | Backend sends chat/inference requests to the Ollama container. |
| Backend (FastAPI) | PostgreSQL | 5432 | Backend reads/writes user data, chat history, messages, and learning data. |
| ollama-puller (curl) | Ollama | 11434 | One-time model pull requests at container startup. |

---

## Part 3: Firewall & Network Policy Summary

### Minimum Required Outbound Access (Runtime)

| Rule | Destination | Port | Required? |
|---|---|---|---|
| Ollama Cloud Inference | `*.ollama.ai` / Ollama cloud endpoints | 443 | **Yes** — Core functionality. Without this, AI chat does not work (unless using local models). |
| LEX Legislation API | `lex.lab.i.ai.gov.uk` or configured `LEX_API_URL` | 443 | **Yes** — Required for legislation search and retrieval. |
| Google Web Search | `www.google.com` | 443 | **Optional** — Only needed if Deep Research mode is enabled (`ENABLE_DEEP_RESEARCH=true`). |
| Gmail SMTP | `smtp.gmail.com` | 465 | **Optional** — Only needed if email notifications are configured. |

### Minimum Required Outbound Access (Installation Only)

| Rule | Destination | Port | Required? |
|---|---|---|---|
| Chocolatey | `community.chocolatey.org`, `*.chocolatey.org` | 443 | Yes (Windows automated install) |
| Docker Hub | `registry-1.docker.io`, `auth.docker.io`, `production.cloudflare.docker.com` | 443 | Yes (Docker deployment) |
| PyPI | `pypi.org`, `files.pythonhosted.org` | 443 | Yes (Python dependencies) |
| npm Registry | `registry.npmjs.org` | 443 | Yes (Node.js dependencies) |
| Ollama Downloads | `ollama.com`, `registry.ollama.ai` | 443 | Yes (Ollama installer + models) |
| GitHub | `github.com` | 443 | Yes (git clone/pull) |

### Minimum Required Inbound Access

| Rule | Port | Required? |
|---|---|---|
| HTTP (Frontend) | 80 (Docker) or 3000 (Native) | **Yes** — User access to the web application. |
| Backend API | 8000 | Only if accessed directly (normally proxied via Nginx on port 80). |

---

## Part 4: Configuration File Reference

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
