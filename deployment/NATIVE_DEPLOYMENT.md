# Native Windows Deployment Guide

This guide explains how to run AILA natively on Windows Server 2022 without using Docker or WSL.

## Quick Start

We provide automated scripts to handle the entire process.

### 1. Installation

Installation on the internet-restricted target uses the offline installer — follow the **Air-Gapped Deployment** section below. (The old internet-connected installer, `install_native.ps1`, has been removed; the git-pull deployment workflow replaced it.)

### 2. Configure SSL Certificates
To run over HTTPS, place your organisational certificate files in the `deployment\certs` folder:
*   **Certificate file**: `deployment\certs\lexchat.crt` (or `.pem`)
*   **Private key file**: `deployment\certs\lexchat.key`

### 3. Start the App
```cmd
deployment\start_native.cmd
```
The script detects which mode to use automatically:

| Condition | Mode | URL |
|---|---|---|
| SSL certs present in `deployment\certs\` | HTTPS on port 443 | `https://localhost` |
| No certs, no `--nginx` flag | HTTP on port 8000 | `http://localhost:8000` |
| `--nginx` flag passed | nginx reverse proxy on port 80 | `http://localhost` |

*   *On an internal network, access via your machine's FQDN (e.g. `https://your-server-name`), matching your certificate.*

### 4. Stop the App
```cmd
deployment\stop_native.cmd
```
This gracefully stops nginx (if running), the FastAPI backend, Ollama, and the PostgreSQL service.

### 5. Demo / Home Server Mode (nginx Reverse Proxy)

For hosting a demo on a home server or local VM, `start_native.cmd --nginx` starts the app behind an nginx reverse proxy on port 80 — no SSL certificates needed.

#### Prerequisites

Install nginx for Windows from [nginx.org](https://nginx.org/en/download.html) (download the stable Windows zip and unzip it). The script checks for nginx in:
1. `PATH`
2. `C:\nginx\`
3. `C:\Program Files\nginx\`

#### Start in nginx mode

```cmd
deployment\start_native.cmd --nginx
```

This starts uvicorn on port 8000 (internal only) and launches nginx on port 80 using `deployment\nginx\lexchat.conf`. The config disables response buffering so SSE streaming works correctly.

#### IP Whitelisting (optional)

To restrict access to specific IPs or subnets, add `allow`/`deny` directives to the `location /` block in `deployment\nginx\lexchat.conf`:

```nginx
location / {
    allow 192.168.1.0/24;   # your LAN subnet
    allow 10.0.0.5;         # a specific IP
    deny all;               # block everyone else

    proxy_pass http://lexchat;
    # ... rest of config unchanged
}
```

#### Firewall Hardening

To lock down the Windows Defender Firewall to only the ports needed for the demo, run the hardening script as Administrator:

```powershell
# If scripts are blocked, set the execution policy first:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

.\deployment\harden_firewall.ps1
```

Edit `$RDP_SUBNET` at the top of the script to match your LAN subnet before running. The script:
- Allows inbound TCP port 80 (nginx, all sources)
- Allows inbound TCP port 3389 (RDP, LAN subnet only)
- Disables all other pre-existing inbound Allow rules
- Sets the default inbound policy to Block

The script is idempotent — safe to re-run after changing the subnet or adding rules.

### 6. Auto-Start at Boot (Recommended for Production)

By default the app only starts when you run `start_native.cmd` after logging in. To have AILA start automatically every time the server boots — without requiring a login — run the autostart installer once:

```powershell
# Open PowerShell as Administrator
cd C:\Projects\LexChat
.\deployment\install_autostart.ps1
```

This will:
1. Detect the Python and Ollama executable paths on this machine and write them to `deployment\autostart_config.ps1` (machine-specific, not committed to the repo).
2. Create `deployment\logs\` if it does not exist.
3. Register a **"AILA Autostart"** Task Scheduler task that runs `start_background.ps1` as the SYSTEM account on every boot.

After installation, AILA starts automatically on every reboot. To trigger it immediately without rebooting:

```powershell
Start-ScheduledTask -TaskName "AILA Autostart"
```

Startup and backend logs are written to `deployment\logs\`:

| File | Contents |
|---|---|
| `startup.log` | Each boot: which services were found/started, any errors |
| `backend.log` | uvicorn stdout (access log, startup confirmation) |
| `backend_err.log` | uvicorn stderr (application errors, stack traces) |
| `ollama.log` / `ollama_err.log` | Ollama output (only if not running as a Windows service) |

To remove autostart and revert to manual startup:

```powershell
.\deployment\uninstall_autostart.ps1
```

> **Note:** PostgreSQL already auto-starts as a Windows service and is unaffected by this feature.

### 7. Updating (Internet-Connected)
To pull the latest code and rebuild:

```powershell
cd deployment
.\update_native.ps1
```

### 8. Updating Ollama and Restoring Cloud Model Manifests

Cloud model manifests are committed to `deployment\ollama_models\` — they are tiny JSON pointers (no local weights). If Ollama needs updating or manifests disappear from the server, after `git pull` run:

```powershell
# In an elevated PowerShell session:
cd C:\Projects\LexChat
.\deployment\update_ollama.ps1
```

This stops Ollama, installs the pinned version (`OllamaSetup.exe` from GitHub), copies manifests from the repo into `%USERPROFILE%\.ollama\models\`, and restarts Ollama.

**To update to a newer Ollama version or add/update models (dev machine):**

1. Pull any new models: `ollama pull <model-name>`
2. Copy the updated model store into the repo:
   ```powershell
   Remove-Item -Recurse C:\Projects\LexChat\deployment\ollama_models
   Copy-Item -Recurse "$env:USERPROFILE\.ollama\models" C:\Projects\LexChat\deployment\ollama_models
   ```
3. Update `$OllamaVersion` in `deployment\update_ollama.ps1`.
4. Commit and push. On the target: `git pull` then `.\deployment\update_ollama.ps1`.

---

## Air-Gapped Deployment

For secure environments with no internet access. All steps are split between an **online dev machine** and the **offline target server**.

### Initial Installation

**On the online dev machine:**

1. Package all dependencies and pre-build the frontend:
    ```powershell
    cd deployment
    .\package_offline_native.ps1
    ```
2. Chunk the output for transfer:
    ```powershell
    .\compress_and_chunk.ps1
    ```
3. Transfer the chunked files in `binaries\` to the target server.

**On the offline target server (as Administrator):**

4. Reconstruct the binaries:
    ```powershell
    cd deployment
    .\reconstruct_binaries.ps1
    ```
5. Run the offline installer:
    ```powershell
    .\install_native_offline.ps1
    ```
    > Append `-SkipSystemInstall` to skip reinstalling Python, PostgreSQL, and Ollama if they are already installed.

6. Start the application:
    ```cmd
    deployment\start_native.cmd
    ```

### Applying Updates (Including Frontend)

All updates — backend and frontend — are deployed via git. The frontend is pre-built on the dev machine and committed to the repo (`git add -f client/dist/`), so the target never needs Node.js:

1. On the dev machine: build (`npm run build` in `client/`), force-add `client/dist/`, commit, push.
2. On the target: `git pull`, then restart:
    ```cmd
    deployment\stop_native.cmd
    deployment\start_native.cmd
    ```

---

## Script Reference

See [deployment/README.md](README.md) for the full index of every script in this directory.

---

## Manual Setup Details

If you cannot use the automated scripts:

1.  **Dependencies**:
    *   Python 3.11+
    *   Node.js 22+ (for building frontend on dev machine only)
    *   PostgreSQL 15+ (User: `lexuser`, Pass: `lexpassword`, DB: `lexchat`)
    *   Ollama

2.  **LLM Provider**:
    *   Default provider is **Ollama** using `mistral-large-3:675b-cloud` (cloud-routed).
    *   **OpenRouter** is also supported as an alternative provider. Requires `OPENROUTER_API_KEY` in `.env.native` and outbound internet access to `openrouter.ai` (not available on fully air-gapped deployments).
    *   The active provider and all per-provider settings (model, temperature, concurrency limits, base URL, API key) are configurable at runtime via **Admin Portal → Developer tab** — no restart required.

3.  **Network Requirements (Outbound URL Whitelist)**:

    The target environment restricts outbound internet access. The following URLs must be whitelisted for the application to function. URLs marked **parliament bot only** are not required if only the legislation bot is deployed.

    | URL | Purpose | Bot |
    |---|---|---|
    | `lex.lab.i.ai.gov.uk` | LEX API — legislation search, section search, full text | Legislation |
    | `caselaw.nationalarchives.gov.uk` | National Archives — UK case law (Atom feed) | Legislation (case law mode) |
    | `www.theyworkforyou.com` | TheyWorkForYou — Hansard search, debates, MSP info | Parliament only |
    | `members-api.parliament.uk` | UK Parliament Members API — MP/Lord lookup | Parliament only |
    | `bills-api.parliament.uk` | UK Parliament Bills API — Westminster bill search | Parliament only |
    | `data.parliament.scot` | Scottish Parliament — bill search | Parliament only |
    | `openrouter.ai` | OpenRouter LLM provider (alternative to Ollama) | Both (if OpenRouter active) |

    If using Ollama (default), `openrouter.ai` is not required. If using OpenRouter, `openrouter.ai` must be reachable.

4.  **Configuration**:
    *   The app uses a `.env.native` file in `server_py/` to configure `localhost` connections.
    *   Add `OPENROUTER_API_KEY=sk-or-...` to `.env.native` to enable OpenRouter as a provider option.

4.  **Build**:
    *   Backend: `pip install -r requirements.txt` in `server_py/`
    *   Frontend: `npm run build` in `client/` — generates static files served by the backend.
