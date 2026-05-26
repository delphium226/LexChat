# Native Windows Deployment Guide

This guide explains how to run LexChat natively on Windows Server 2022 without using Docker or WSL.

## Quick Start

We provide automated scripts to handle the entire process.

### 1. Installation
> [!WARNING]
> This native installer requires an **active internet connection** to download dependencies (Python, Node.js, PostgreSQL, Ollama). If you are deploying to a secure, air-gapped environment without internet access, follow the **Air-Gapped Deployment** section below instead.

Run the installer script as Administrator. This will install Python, Node.js, PostgreSQL, and Ollama, and set up the application.

```powershell
# Open PowerShell as Administrator
cd deployment
.\install_native.ps1
```

### 2. Configure SSL Certificates
To run over HTTPS, place your organisational certificate files in the `deployment\certs` folder:
*   **Certificate file**: `deployment\certs\lexchat.crt` (or `.pem`)
*   **Private key file**: `deployment\certs\lexchat.key`

### 3. Start the App
```cmd
deployment\start_native.cmd
```
This script will automatically:
1. Start **Ollama** (skips if already running)
2. Start the **FastAPI backend** (uvicorn) on port 443 with HTTPS

*   **Application URL**: https://localhost
*   *On an internal network, access via your machine's FQDN (e.g. `https://your-server-name`), matching your certificate.*

### 4. Stop the App
```cmd
deployment\stop_native.cmd
```
This gracefully stops the FastAPI backend, Ollama, and the PostgreSQL service.

### 5. Auto-Start at Boot (Recommended for Production)

By default the app only starts when you run `start_native.cmd` after logging in. To have LexChat start automatically every time the server boots — without requiring a login — run the autostart installer once:

```powershell
# Open PowerShell as Administrator
cd C:\Projects\LexChat
.\deployment\install_autostart.ps1
```

This will:
1. Detect the Python and Ollama executable paths on this machine and write them to `deployment\autostart_config.ps1` (machine-specific, not committed to the repo).
2. Create `deployment\logs\` if it does not exist.
3. Register a **"LexChat Autostart"** Task Scheduler task that runs `start_background.ps1` as the SYSTEM account on every boot.

After installation, LexChat starts automatically on every reboot. To trigger it immediately without rebooting:

```powershell
Start-ScheduledTask -TaskName "LexChat Autostart"
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

### 6. Updating (Internet-Connected)
To pull the latest code and rebuild:

```powershell
cd deployment
.\update_native.ps1
```

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
    deployment\start_native_offline.cmd
    ```

### Applying Frontend Updates (Air-Gapped)

When only the frontend (UI) has changed, use the lightweight update scripts instead of repackaging everything.

**On the online dev machine:**

1. Ensure Node.js is available. If not, run:
    ```powershell
    .\install_node.ps1
    ```
2. Build the frontend:
    ```powershell
    cd client
    npm install
    npm run build
    ```
3. Package the built frontend:
    ```powershell
    cd deployment
    .\package_frontend_update.ps1
    ```
4. Transfer `frontend_update.zip` to the repo root on the target server.

**On the offline target server:**

5. Apply the update:
    ```powershell
    cd deployment
    .\apply_frontend_update.ps1
    ```
6. Restart the application:
    ```cmd
    deployment\stop_native.cmd
    deployment\start_native_offline.cmd
    ```

---

## Script Reference

| Script | Description |
|---|---|
| `install_native.ps1` | Full installation (internet-connected) |
| `install_native_offline.ps1` | Full installation (air-gapped) |
| `install_node.ps1` | Install portable Node.js v22 on dev machine |
| `package_offline_native.ps1` | Package all deps + pre-build frontend for air-gap transfer |
| `package_frontend_update.ps1` | Package only the built frontend for a lightweight update |
| `apply_frontend_update.ps1` | Apply a frontend update zip on the target server |
| `compress_and_chunk.ps1` | Chunk binaries into <50MB parts for transfer |
| `reconstruct_binaries.ps1` | Reconstruct chunks back into binaries on target |
| `update_native.ps1` | Pull latest code and rebuild (internet-connected) |
| `start_native.cmd` | Start Ollama + backend (internet-connected, interactive) |
| `start_native_offline.cmd` | Start Ollama + backend (air-gapped, interactive) |
| `stop_native.cmd` | Gracefully stop all services |
| `start_background.ps1` | Headless startup called by Task Scheduler at boot |
| `install_autostart.ps1` | One-time setup: register boot-time Task Scheduler task |
| `uninstall_autostart.ps1` | Remove the Task Scheduler task (revert to manual startup) |

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

3.  **Configuration**:
    *   The app uses a `.env.native` file in `server_py/` to configure `localhost` connections.
    *   Add `OPENROUTER_API_KEY=sk-or-...` to `.env.native` to enable OpenRouter as a provider option.

4.  **Build**:
    *   Backend: `pip install -r requirements.txt` in `server_py/`
    *   Frontend: `npm run build` in `client/` — generates static files served by the backend.
