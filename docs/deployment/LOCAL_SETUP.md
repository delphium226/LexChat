# Local Multi-Bot Development Setup

This guide explains how to run multiple federation bots simultaneously on a dev machine.

## Overview

Each bot is a separate FastAPI process with its own PostgreSQL database, running on a different port.
They communicate by calling each other's `/api/consult` endpoint.

`deployment/local/` holds machine-specific runtime files that are **never committed**:
- `active_bots.txt` — list of bots currently running (managed by `new_bot.ps1`)
- `shared.env` — shared secrets (e.g. `JWT_SECRET`) provisioned once per machine

## Prerequisites

- PostgreSQL running locally (default: `lexuser`/`lexpassword`)
- Python dependencies installed globally (`pip install -r server_py/requirements.txt`)
- Portable Node.js on PATH (for frontend builds)

## Quick Start

### 1. Create the local directory

```powershell
New-Item -ItemType Directory -Force deployment\local
```

### 2. Create shared.env

```
JWT_SECRET=your_local_jwt_secret_here
```

### 3. Provision a new bot

```powershell
.\shared\scripts\new_bot.ps1 -BotId case_law_bot -Name "Case Law Bot" -Tagline "UK Court Judgments" -Port 8002
```

This copies `bots/legislation/` as a template, updates `bot_config.json`, and appends the start
command to `deployment/local/active_bots.txt`.

### 4. Register a peer

Once both bots are running, tell Bot A about Bot B:

```powershell
.\shared\scripts\register_peer.ps1 `
  -CallerBotUrl http://localhost:8001 `
  -CallerApiKey <bot-a-jwt-token> `
  -PeerId case_law_bot `
  -PeerName "Case Law Bot" `
  -PeerBaseUrl http://localhost:8002 `
  -PeerApiKey <bot-b-api-key> `
  -Description "Searches UK court judgments and case law"
```

### 5. Start bots

Run each bot in a separate terminal:

```powershell
# Bot 1 — Legislation Bot (default, port 8000)
cd server_py
$env:BOT_ID = "legislation_bot"
$env:BOT_CONFIG_PATH = "bots/legislation/bot_config.json"
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

# Bot 2 — Parliament Bot (port 8001)
cd server_py
$env:BOT_ID = "parliament_bot"
$env:BOT_CONFIG_PATH = "bots/parliament/bot_config.json"
$env:DATABASE_URL = "postgresql://lexuser:lexpassword@localhost:5432/parliament_bot"
uvicorn src.main:app --host 0.0.0.0 --port 8001 --reload
```

Each bot uses its own database (set via `DATABASE_URL`). The default `lexchat` DB remains unchanged.

## Bot Configuration

Each bot has a `bot_config.json` with:
- `bot_identity` — `bot_id`, `name`, `tagline`, `logo_path`
- `peer_registry_seed` — initial peer list loaded into the DB on startup (insert-or-ignore by peer_id)

Seed entries do **not** overwrite existing DB rows — safe to restart.

## Federation Depth Limit

Peer calls are limited to depth 2. A bot receiving a `/api/consult` request at depth ≥ 2
returns HTTP 422 immediately. This prevents A→B→C cascade loops.

## API Key Security

The `api_key` field in peer records is stored encrypted in the DB and **never returned** by the
admin API. When updating a peer, omitting `api_key` in the PUT body preserves the existing value.
