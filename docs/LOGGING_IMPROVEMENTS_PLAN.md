# Logging Improvements — Implementation Plan

Status: proposed (2026-07-19). Derived from a review of the backend logging strategy.
All work is in `server_py/`. Changes are additive and fail-soft; no DB schema changes.

## Summary of items

| # | Item | Impact | Effort | Risk |
|---|---|---|---|---|
| 1 | Configure the `sptv` logger (currently logs to nowhere) | High | XS | None |
| 2 | Add stack traces on caught exceptions (`exc_info`) | High | S | None |
| 3 | Runtime log-level control via env (`LOG_LEVEL`) | High | XS | None |
| 4 | Redact sensitive data (queries, emails) from logs | High | S | Low |
| 5 | Correlation / request IDs across all loggers | Medium | M | Low |
| 6 | Optional JSON/structured output | Medium | S | None |
| 7a | HTTP middleware misses exceptions | Low | XS | None |
| 7b | Align/disable uvicorn's own access logger | Low | S | Low |
| 7c | Route true HTTP 5xx into `error.log` | Low | XS | None |

Recommended order: **3 → 1 → 7a/7c → 2 → 4 → 5 → 6 → 7b** (quick wins and shared
infrastructure first; #5 depends on the request-id ContextVar; #4 benefits from the
redaction helper landing before #5 widens what is logged).

---

## Item 1 — Configure the `sptv` logger

**Problem.** `sptv_client.py` and `caption_match.py` call `logging.getLogger("sptv")`,
but `setup_logging()` never configures an `sptv` logger. It propagates to the root
logger (no handlers) → `lastResort` drops INFO and dumps WARNING+ to bare stderr.
SP TV video-deeplink diagnostics never reach any log file.

**Change.** In `server_py/src/utils/logger.py`, add an `sptv` logger inside
`setup_logging()`, mirroring the `crawler` block (own file + shared `error.log` +
console). It is parliament-bot-only and `delay=True` means no file is created until
the first line is written.

```python
# SP TV video deep-link resolver (sptv_client, caption_match). Parliament-bot only,
# fail-soft feature; give it its own file so caption diagnostics are recoverable.
sptv_logger = logging.getLogger("sptv")
sptv_logger.setLevel(LOG_LEVEL)  # see Item 3
sptv_logger.addHandler(_create_file_handler(f"{prefix}sptv.log"))
sptv_logger.addHandler(_create_file_handler(f"{prefix}error.log", logging.ERROR))
sptv_logger.addHandler(_create_console_handler())
```

**Files.** `server_py/src/utils/logger.py`.
**Verify.** With `ENABLE_VIDEO_DEEPLINKS=true`, run a plenary retrieval; confirm
`logs/<bot>_sptv.log` is created and populated.
**Alternative (smaller).** Repoint both modules to `getLogger("agent")` and delete
the `sptv` name entirely. Chosen approach keeps them separable; note in review.

---

## Item 2 — Stack traces on caught exceptions

**Problem.** ~90 `except Exception` sites, **zero** use of `exc_info`/`logger.exception`.
The universal `logger.error(f"...: {e}")` records only `str(e)` — no traceback, no
line. Many exceptions stringify to empty. On an internet-restricted box with no
debugger, this is the biggest operational gap.

**Change.** For `except` blocks representing genuine faults (not expected/fail-soft
control flow), switch to one of:
- `logger.exception("[X] message")` — inside an `except`, captures the traceback automatically; or
- `logger.error("[X] message", exc_info=True)` where the log level must stay ERROR conditionally.

Keep the terse `f"...: {e}"` form only where the exception is *expected* and handled
(e.g. cache miss, optional email not configured, fail-soft SP TV resolution).

**Scope — triage, do not blanket-replace.** Prioritise these hot spots (highest
diagnostic value):
- `agent/agent_core.py`, `agent/agent_shared.py`, `agent/ollama_client.py`,
  `agent/openrouter_client.py`, `agent/provider_factory.py` — provider/LLM failures.
- `services/parliament_crawler.py` (18 except sites) — the crawler is long-running
  and its failures are currently near-opaque.
- `services/sptv_client.py`, `services/caption_match.py` — pairs with Item 1.
- `routers/ai.py`, `routers/research.py` — request-path 500s.
- `database.py`, `services/health_service.py`.

**Files.** The modules above (grep `except Exception` per file, edit case-by-case).
**Verify.** Force a provider error (bad base_url); confirm a full traceback lands in
`agent.log` + `error.log`.
**Guardrail.** Do **not** add `exc_info` to fail-soft paths that fire routinely — it
would flood `error.log`. This is a judgement pass, not a sed script.

---

## Item 3 — Runtime log-level control

**Problem.** Levels are hardcoded to `INFO` in `setup_logging()`. No way to enable
DEBUG on the target without a code change → commit → push → pull cycle.

**Change.**
1. `config.py` `Settings`: add
   ```python
   # Logging
   log_level: str = "INFO"           # root level for app/agent/http/crawler/sptv
   console_log_level: str = ""       # optional override for console only; blank = log_level
   ```
2. `utils/logger.py`: resolve at top of `setup_logging()`:
   ```python
   LOG_LEVEL = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
   ```
   (read the env directly to avoid importing `settings` into the logging util and
   creating an import cycle — `setup_logging` runs before most imports). Use
   `LOG_LEVEL` for every `setLevel(...)` and both handler factories' defaults.
3. Document `LOG_LEVEL` in `CLAUDE.md`'s env-var table and `.env.example`.

**Files.** `server_py/src/utils/logger.py`, `server_py/src/config.py`, `CLAUDE.md`,
`.env` example.
**Verify.** `LOG_LEVEL=DEBUG` → DEBUG lines appear; unset → INFO baseline unchanged.
**Note.** Keep the `httpx`/`httpcore`/`sqlalchemy.engine` WARNING suppression as-is
(don't let DEBUG un-mute those unless separately requested).

---

## Item 4 — Redact sensitive data

**Problem.** For OFFICIAL-SENSITIVE / government-lawyer users, several INFO lines write
user content and PII to disk (14-day retention):
- `agent/agent_core.py:58` — full user `query`.
- `routers/learning.py:145` — full `body.query`.
- `routers/auth.py:174` — user **email address**; `services/email_service.py` INFO
  lines log recipient emails.

**Change.**
1. Add helpers to `utils/logger.py` (or a small `utils/redact.py`):
   ```python
   def redact_text(s: str, keep: int = 24) -> str:
       """Log-safe: length + short prefix + sha1[:8], never the full body."""
       if not s:
           return "<empty>"
       import hashlib
       h = hashlib.sha1(s.encode("utf-8", "replace")).hexdigest()[:8]
       head = s[:keep].replace("\n", " ")
       return f"<{len(s)} chars, sha1:{h}, '{head}…'>"

   def redact_email(e: str) -> str:
       if not e or "@" not in e:
           return "<email>"
       name, _, dom = e.partition("@")
       return f"{name[:2]}***@{dom}"
   ```
2. Replace the offending call sites: log `redact_text(query)` / `redact_email(user.email)`
   at INFO. Full text may still be emitted at **DEBUG** if useful (gated by Item 3).
3. Keep the existing `user id=`/`id=` style in `auth.py:187,192` and `chats.py:249`
   — those are already correct; make the flagged lines consistent with them.

**Files.** `utils/logger.py` (helpers), `agent/agent_core.py`, `routers/learning.py`,
`routers/auth.py`, `services/email_service.py`.
**Decision to confirm with the deploying org.** Whether query text may appear even at
DEBUG. Default here: redacted at INFO, full only at DEBUG. Record the decision in
`CLAUDE.md`.
**Verify.** Submit a query; confirm `agent.log` shows `<N chars, sha1:…>` not the text.

---

## Item 5 — Correlation / request IDs across loggers

**Problem.** The HTTP middleware logs method/path/status/duration with no request id;
the rich `[Efficiency]` line in `ai.py:316` has a `request_id` that appears nowhere
else. You cannot currently stitch one request's HTTP + agent + worker + efficiency
lines together across the three log files.

**Change.**
1. New `utils/log_context.py`:
   ```python
   import contextvars, uuid, logging
   request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

   class RequestIdFilter(logging.Filter):
       def filter(self, record):
           record.request_id = request_id_var.get()
           return True
   ```
2. `utils/logger.py`: add `%(request_id)s` to `LOG_FORMAT`, and attach
   `RequestIdFilter()` to every handler (or to each logger).
3. `main.py` `log_requests` middleware: at entry,
   `token = request_id_var.set(request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12])`;
   reset in a `finally`. Add the id to the response header `X-Request-ID`.
4. Ensure `run_worker_agent` / deep-research paths inherit it — they run in the same
   task context, so the ContextVar propagates automatically (same pattern as the
   existing provider-config ContextVar). Confirm no `run_in_executor`/new-thread hop
   loses it; if so, pass it explicitly.
5. Align the efficiency line's `request_id` with this id where practical (or log both).

**Files.** new `utils/log_context.py`, `utils/logger.py`, `main.py`; spot-checks in
`agent/agent_core.py`.
**Verify.** One request → same id in `http.log`, `agent.log`, and the efficiency line.
**Risk.** If any logging happens before the middleware sets the var (startup), the
default `-` shows — acceptable.

---

## Item 6 — Optional JSON/structured output — DEFERRED (2026-07-19)

> Parked by decision. Split out of PR D; build only if the deployment gains a central
> log aggregator / SIEM. Depends on Item 5 so `request_id` is a first-class JSON field.


**Problem.** All output is human-formatted text; not machine-parseable for a SIEM /
log aggregator (plausible for a government deployment).

**Change.**
1. Add a `JsonFormatter(logging.Formatter)` in `utils/logger.py` emitting
   `{ts, level, logger, request_id, message}` (+ `exc_info` when present).
2. Gate via env: `LOG_FORMAT_JSON=true` (`config.py` `log_json: bool = False`) selects
   the JSON formatter for **file** handlers; console stays colourised for humans.
3. No new dependency required (hand-rolled formatter); avoids adding
   `python-json-logger` to the offline/global-install target.

**Files.** `utils/logger.py`, `config.py`, `CLAUDE.md` env table.
**Verify.** `LOG_FORMAT_JSON=true` → each file line is valid JSON (`jq . < app.log`).
**Note.** Do after Item 5 so `request_id` is a first-class field.

---

## Item 7 — Smaller fixes

### 7a — HTTP middleware misses exceptions
`main.py` `log_requests`: if `call_next` raises, the log line never runs → unhandled
500s aren't logged by the middleware. Wrap in try/finally so the access line (and
duration) always emit, and log 5xx at ERROR.

```python
start = time.time()
status = 500
try:
    response = await call_next(request)
    status = response.status_code
    return response
finally:
    duration_ms = int((time.time() - start) * 1000)
    lvl = http_logger.error if status >= 500 else http_logger.warning if status >= 400 else http_logger.info
    lvl(f"{request.method} {request.url.path} {status} {duration_ms}ms")
```

### 7b — Align/disable uvicorn's own access logger
`uvicorn.access` / `uvicorn.error` aren't configured here, so depending on launch
flags you may get duplicate/unformatted access logs alongside the custom `http`
logger. Options: pass `--no-access-log` in the launch scripts (`deployment/start_native.cmd`,
`start_background.ps1`, `start_federation_dev.ps1`) since the middleware already
covers access logging; **or** attach the same handlers to `uvicorn.error` so uvicorn
lifecycle errors land in `error.log`. Recommended: `--no-access-log` + adopt
`uvicorn.error` into the app handler set. Verify no access-log regression.

### 7c — Route true HTTP 5xx into `error.log`
The `http` logger has no `error.log` handler, so server errors logged via it never
reach the shared error file. Either add an `error.log` handler to the `http` logger
in `setup_logging()`, or rely on 7a logging 5xx at ERROR **and** give `http` the
`error.log` handler. Pick one; simplest is to add the handler to the `http` block.

**Files.** `main.py`, `utils/logger.py`, `deployment/*.cmd`/`*.ps1`.

---

## Cross-cutting verification & rollout

- **Regression baseline.** Before/after, run the app locally (HTTP 8000), submit one
  standard query and (parliament bot) one plenary retrieval; diff the resulting log
  files for format changes and confirm no duplicate lines.
- **Tests.** Existing suite is green (46 passed per project notes). Add focused unit
  tests: `redact_text`/`redact_email` output shape (Item 4); `RequestIdFilter` injects
  the var (Item 5); JSON formatter emits parseable lines (Item 6). No integration
  tests needed for handler wiring.
- **Docs.** Update `CLAUDE.md` env-var table with `LOG_LEVEL`, `CONSOLE_LOG_LEVEL`,
  `LOG_FORMAT_JSON`, and record the Item-4 sensitivity decision.
- **Deploy.** Standard workflow — commit (no `client/dist` changes here), push,
  `git pull` + restart on target. All items are backend-only.

## Suggested PR slicing
1. **PR A (quick wins) — DONE (2026-07-19):** Items 3, 1, 7a, 7c. `LOG_LEVEL`/
   `CONSOLE_LOG_LEVEL` env control, `sptv` logger configured, HTTP middleware
   try/finally + 5xx→ERROR, `error.log` handler on the `http` logger. Verified via
   smoke test (loggers configured, DEBUG honoured, sptv + error files written).
   Files: `utils/logger.py`, `config.py`, `main.py`, `CLAUDE.md`.
2. **PR B (diagnostics) — DONE (2026-07-19):** Item 2 (traceback pass). Added
   `exc_info=True` to genuine-fault handlers across the agent layer
   (`agent_core`, `executor`, `parliament` tools incl. video enrichment, `learning`,
   `provider_factory`, `federation_client`), services (`email_service`,
   `health_service`, `parliament_crawler` loop-level catch-alls), `database.py`, and
   the request-path routers (`ai.py` ×5, `research.py` ×2). Deliberately left terse:
   per-window/meeting crawler retries, summarisation chunk fallbacks, sptv/caption
   fail-soft warnings, and "credentials not configured" (expected, high-volume, or
   fail-soft by design). Verified traceback reaches console + `error.log`.
3. **PR C (privacy):** Item 4 — needs the org sign-off decision recorded.
4. **PR D (observability):** Items 5, 7b — request IDs + uvicorn alignment.
   (Item 6, JSON output, split out and deferred separately — build only on a SIEM need.)
