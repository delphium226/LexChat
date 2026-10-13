# Local Multi-Bot Development Setup

This guide explains how to run several federation bots at once on a dev machine.

## Overview

Each bot is the same FastAPI app (`uvicorn src.main:app`, run from `server_py/`) started with its own
identity, database, port and research mode. Bots consult each other by calling each other's
`/api/consult` endpoint.

| Bot | `BOT_ID` | Name | Port | Database | `RESEARCH_MODE` | Config |
|---|---|---|---|---|---|---|
| Legislation | `legislation_bot` | AILA | 8000 | `lexchat` | *(blank)* | `bots/legislation/bot_config.json` |
| Parliament (Holyrood) | `parliament_bot` | ParliChat | 8001 | `lexchat_parliament` | `parliamentary_records` | `bots/parliament/bot_config.json`, `bots/parliament/.env` |
| Westminster | `westminster_bot` | HansardChat | 8002 | `lexchat_westminster` | `westminster_records` | `bots/westminster/bot_config.json`, `bots/westminster/.env` |

Every bot serves the same pre-built frontend (`client/dist`) and brands it from its own
`/api/bot-info`, so `http://localhost:8000`, `:8001` and `:8002` each show their own bot.

## Prerequisites

- PostgreSQL running locally, with the `lexuser`/`lexpassword` role able to create databases
- Python dependencies installed globally (`pip install -r server_py/requirements.txt`)
- Portable Node.js on PATH, only if you are rebuilding the frontend

## Quick start

### 1. Create the per-bot `.env` files

`bots/parliament/.env` and `bots/westminster/.env` are gitignored, so each machine creates its own.
They hold what makes the bot different from the legislation bot. One `KEY=value` per line, with
upper-case keys and nothing between the key and the `=`; the start script skips anything else.

`bots/parliament/.env`:

```
RESEARCH_MODE=parliamentary_records
DATABASE_URL=postgresql://lexuser:lexpassword@localhost:5432/lexchat_parliament
TWFY_API_KEY=<your TheyWorkForYou key>
```

Add `ENABLE_VIDEO_DEEPLINKS=true` to switch on the SP TV video deep links (off by default).

`bots/westminster/.env`:

```
RESEARCH_MODE=westminster_records
DATABASE_URL=postgresql://lexuser:lexpassword@localhost:5432/lexchat_westminster
```

Without its own `DATABASE_URL`, a bot falls back to `server_py/.env` and shares the legislation
bot's `lexchat` database. Every bot reads `server_py/.env` for everything its own `.env` does not
set (JWT secret, provider defaults and so on), because uvicorn runs from `server_py/`.

### 2. Start all three bots

```powershell
.\deployment\start_federation_dev.ps1
```

The script:

1. Creates `lexchat_parliament` and `lexchat_westminster` if they do not exist (connecting with
   `psql` as `lexuser`).
2. Stops whatever is listening on ports 8000, 8001 and 8002 (including a `start_native.cmd`
   instance on 8000), then opens one console window per bot running
   `python -m uvicorn src.main:app --reload --no-access-log` on its port. A bot's `.env` is loaded
   first, then `BOT_ID` and an absolute `BOT_CONFIG_PATH` are set over it.
3. Waits up to 60 seconds for each port to answer.
4. Wires the federation as a full mesh: it logs in to each bot as `admin`/`admin`, mints a
   non-expiring federation token on each (`POST /api/auth/federation-token`), and registers every
   other bot as an enabled peer, using the peer's own token as its `api_key`. A peer that is already
   registered is skipped (HTTP 409), so re-running the script is safe.

Step 4 needs the seeded `admin`/`admin` login. If you have changed that password, the script stops
there; register the peers in Admin Portal → **Federation** instead (see below).

On first start against an empty `lexchat_parliament`, the parliament bot begins backfilling the
Scottish Parliament Official Report from Session 6 in the background. This takes many hours; the
bot is usable meanwhile, and later restarts only re-scan recent weeks. See
[PARLIAMENTARY_DATA.md](../parliament/PARLIAMENTARY_DATA.md).

Each bot writes its own log files, prefixed with its `BOT_ID`, under `server_py/logs/`
(e.g. `parliament_bot_app.log`, `parliament_bot_error.log`).

## Running a bot by hand

Use a separate PowerShell window per bot (the variables stay set for that session):

```powershell
cd server_py
$env:BOT_ID = "parliament_bot"
$env:BOT_CONFIG_PATH = (Resolve-Path ..\bots\parliament\bot_config.json).Path
$env:DATABASE_URL = "postgresql://lexuser:lexpassword@localhost:5432/lexchat_parliament"
$env:RESEARCH_MODE = "parliamentary_records"
$env:TWFY_API_KEY = "<your TheyWorkForYou key>"
python -m uvicorn src.main:app --host 0.0.0.0 --port 8001 --reload
```

`BOT_CONFIG_PATH` must be absolute, or relative to `server_py/`: a path relative to the repo root
does not resolve, and the bot then starts with the default AILA identity and logs
`bot_config_path set but file not found`. The database must already exist.

On a server, the parliament bot is started by `deployment\start_parliament.cmd`, which loads the
same `bots\parliament\.env`.

## Registering peers by hand

In the Admin Portal → **Federation** tab (shown to the `admin` account), or with the script:

```powershell
.\shared\scripts\register_peer.ps1 `
  -CallerBotUrl http://localhost:8000 `
  -CallerApiKey <admin JWT for the caller bot> `
  -PeerId parliament_bot `
  -PeerName "Parliament Bot" `
  -PeerBaseUrl http://localhost:8001 `
  -PeerApiKey <federation token minted on the peer bot> `
  -Description "Searches Scottish Parliament (Holyrood) plenary and committee proceedings"
```

- `-CallerApiKey` is an admin login token for the bot that is learning about the peer.
- `-PeerApiKey` is what the caller will present to the peer. Mint it on the **peer** with
  `POST /api/auth/federation-token` (admin only): it never expires, whereas a login token expires
  after a day and the peer link then stops working.
- `-Description` is what the Manager sees as the peer's description in its `consult_peer` tool, so
  say what the peer can answer.

To change an existing peer use `PUT /api/peers/{peer_id}` with the string `peer_id`
(e.g. `PUT /api/peers/parliament_bot`), not the numeric row id.

## Provisioning a new bot

```powershell
.\shared\scripts\new_bot.ps1 -BotId case_law_bot -Name "Case Law Bot" -Tagline "UK Court Judgments" -Port 8003
```

This copies `bots/legislation/` to `bots/<BotId>/`, writes the new identity into its
`bot_config.json`, writes a `.env` holding only `BOT_ID` and `BOT_CONFIG_PATH`, and appends a start
command to `deployment/local/active_bots.txt` (`deployment/local/` is gitignored). Then:

- **Create the database and point the bot at it.** Add `DATABASE_URL` (and `RESEARCH_MODE`, if the
  bot is not a legislation bot) to `bots/<BotId>/.env`. Name the database `lexchat_<something>`:
  the nightly backup only picks up databases whose names start with `lexchat`
  (see [BACKUP_RUNBOOK.md](BACKUP_RUNBOOK.md)). The script's own suggestion uses the bot id as the
  database name, which the backup would miss.
- **Fix the logo path.** The script sets `logo_path` to `bots/<BotId>/assets/logo.png`, but the
  template's logo is `logo.svg`. Add a `logo.png` or point `logo_path` at the SVG.
- **Start it.** `start_federation_dev.ps1` starts only the bots in its `$bots` list; add an entry
  there, or run the bot by hand as above. Treat the line in `active_bots.txt` as a note rather than
  a script: its `BOT_CONFIG_PATH` is relative to the repo root, and it joins commands with `&&`,
  which Windows PowerShell 5.1 does not accept.
- **Register it** with its peers as above.

## Bot configuration

Each bot's `bot_config.json` has:

- `bot_identity` — `bot_id`, `name`, `tagline`, `logo_path` (relative to the repo root), and
  optionally `logo_emoji` (used in the UI and as the favicon in preference to the logo file) and
  `brand_color` (used in the About box). Served by `GET /api/bot-info` and `GET /api/bot/logo`.
- `peer_registry_seed` — an optional list of peers (`peer_id`, `name`, `base_url`, `api_key`,
  `description`) inserted into the `peer_bots` table on startup as enabled peers. Insert-or-ignore
  by `peer_id`: a seed never overwrites an existing row, so restarts are safe, and a change to a
  seeded peer has to be made in the Federation tab or through the API.

The research mode comes from the `RESEARCH_MODE` environment variable, not from the config file.
The `agent.research_mode` key in the shipped configs is not read.

## Federation depth limit

Peer calls are limited to depth 2. A bot receiving a `/api/consult` request at depth ≥ 2
returns HTTP 422 immediately. This prevents A→B→C cascade loops.

## API key security

A peer's `api_key` is stored as plain text in the `peer_bots` table and is **never returned** by the
admin API: responses carry `has_api_key` instead. When updating a peer, omitting `api_key` in the
PUT body keeps the existing value. The keys are in every database dump, so treat the database and
its backups accordingly.
