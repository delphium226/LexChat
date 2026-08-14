# deployment/ — Script Index

Every script in this directory, what it does, and where it runs. Full walkthroughs: [NATIVE_DEPLOYMENT.md](NATIVE_DEPLOYMENT.md) (target server) and [LOCAL_SETUP.md](LOCAL_SETUP.md) (multi-bot local dev).

## Start / stop (target server and dev machine)

| Script | Runs on | Purpose |
|---|---|---|
| `start_native.cmd` | Target / dev | Start PostgreSQL, Ollama, and the FastAPI backend. Auto-detects HTTPS (certs present), plain HTTP, or `--nginx` reverse-proxy mode. Copies `server_py/.env.native` → `.env`. |
| `stop_native.cmd` | Target / dev | Gracefully stop nginx (if running), uvicorn, Ollama, and the PostgreSQL service. |
| `start_federation_dev.ps1` | Dev | Start multiple bots locally (legislation + parliament) for federation development. Creates the `lexchat_parliament` DB if missing. |
| `start_background.ps1` | Target | Headless startup invoked by the Task Scheduler autostart task at boot. |

## Installation (air-gapped target)

| Script | Runs on | Purpose |
|---|---|---|
| `install_native_offline.ps1` | Target | Full air-gapped installation from the reconstructed offline bundle. `-SkipSystemInstall` skips Python/PostgreSQL/Ollama reinstall. |
| `reconstruct_binaries.ps1` | Target | Reassemble `binaries/offline_dependencies.zip.part*` into the offline bundle. |
| `setup_server.ps1` | Target | Server environment setup. |
| `install_node.ps1` | Dev | Install portable Node.js v22 (frontend builds happen on the dev machine only). |

## Offline bundle production (dev machine)

| Script | Runs on | Purpose |
|---|---|---|
| `package_offline_native.ps1` | Dev | Package all Python/system dependencies + pre-built frontend for air-gap transfer. |
| `compress_and_chunk.ps1` | Dev | Split the offline bundle into <50MB parts (committed under `binaries/`). |
| `chunk_ollama_installer.ps1` | Dev | Chunk the Ollama installer for transfer. |

## Updates

| Script | Runs on | Purpose |
|---|---|---|
| `update_native.ps1` | Target (internet-connected only) | Pull latest code and rebuild. On the restricted target the normal path is `git pull` + restart. |
| `update_ollama.ps1` | Target | Update the Ollama binary (pinned version) and restore cloud model manifests from `ollama_models/`. |

## Autostart (target)

| Script | Purpose |
|---|---|
| `install_autostart.ps1` | Register the "AILA Autostart" Task Scheduler task (runs `start_background.ps1` at boot). Writes machine-specific `autostart_config.ps1` (not committed). |
| `install_ollama_autostart.ps1` | Ensure Ollama starts at boot (service or scheduled task). |
| `uninstall_autostart.ps1` | Remove the autostart task (revert to manual startup). |

## Backup / restore (target)

Procedure and troubleshooting: [BACKUP_RUNBOOK.md](BACKUP_RUNBOOK.md).

| Script | Runs on | Purpose |
|---|---|---|
| `backup_databases.ps1` | Target / dev | Nightly `pg_dump -Fc` of every `lexchat%` database (enumerated, not hardcoded; `lexchat_test` excluded). Two-stage verify, `manifest.json` with the commit SHA, GFS retention. Safe against a live system. |
| `install_backup_task.ps1` | Target | One-time, elevated: create and ACL-lock the backup directory, register the event log source, schedule the nightly run as SYSTEM. |
| `restore_database.ps1` | Target / dev | Console restore of one database: verify → stop app (not PostgreSQL) → safety-dump current → drop/recreate/restore → row-count comparison. Also runs the monthly restore drill via `-TargetDatabase`/`-CompareWith`. |

## Network / security

| Script | Purpose |
|---|---|
| `harden_firewall.ps1` | Lock Windows Defender Firewall to ports 80 + 3389 (demo/home-server mode). Idempotent. |
| `check_firewall.ps1` | Inspect current firewall rules. |
| `extract_pfx.py` | Extract `.crt`/`.key` from an organisational `.pfx` certificate into `certs/`. |
| `gen_keys.cmd` | Generate the SSH key pair for cloud-routed Ollama auth (keys live in `ollama_auth/`, which is gitignored — never commit them). |

## Data / config directories

| Path | Purpose |
|---|---|
| `certs/` | Organisational TLS certificates (`lexchat.crt` / `lexchat.key`); presence switches `start_native.cmd` to HTTPS on 443. |
| `nginx/lexchat.conf` | Reverse-proxy config for `--nginx` mode (port 80 → uvicorn 8000, SSE buffering disabled). |
| `ollama_models/` | Committed cloud-model manifests (tiny JSON pointers, no weights) restored by `update_ollama.ps1`. |
| `local/` | Gitignored per-machine multi-bot dev config (`active_bots.txt`, `shared.env`). |

## Removed scripts (June 2026 tidy-up)

`install_native.ps1` (online installer), `package_frontend_update.ps1` / `apply_frontend_update.ps1` (zip-based frontend updates — superseded by committing `client/dist/` and deploying via `git pull`), `temp_pkg.ps1` (debug leftover), `start_federation_dev.cmd` (duplicate of the `.ps1`). Recoverable from git history if ever needed.
