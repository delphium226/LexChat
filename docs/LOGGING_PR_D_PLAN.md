# Logging PR D — Request IDs (Item 5) + uvicorn access-log alignment (Item 7b)

**STATUS: BUILT 2026-07-19.** Items 5 + 7b implemented; efficiency-id reconciliation
(Item 5 step 5) skipped as low-value (the efficiency line now carries `[<rid>]` via the
format, so the two ids are joinable). 150 tests green. See `docs/TODO.md` D9.

**Self-contained implementation plan for a fresh session.** Parent review:
`docs/LOGGING_IMPROVEMENTS_PLAN.md`. Prior slices PR A + PR B already shipped
(commit `346457c` on `main`, 2026-07-19): `LOG_LEVEL`/`CONSOLE_LOG_LEVEL` runtime
control, the `sptv` logger, HTTP middleware try/finally + 5xx→ERROR, `error.log` on
the `http` logger, and `exc_info=True` on genuine-fault handlers.

Item 6 (JSON/structured output) is **deferred separately** — do NOT build it here.

Both items are backend-only. No `client/dist` rebuild. Deploy = target `git pull` +
`stop_native.cmd` / `start_native.cmd`.

---

## Context a cold session needs

- Backend: Python 3.11 + FastAPI, `server_py/`, run via `uvicorn src.main:app` (CWD
  is `server_py/`). Logging bootstraps in `src/main.py` before routers load.
- **Logging is centralised** in `server_py/src/utils/logger.py::setup_logging()`.
  Five named loggers: `app`, `agent`, `http`, `crawler`, `sptv`. Current format
  (as shipped by PR A):
  ```python
  LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
  ```
  Handlers are built by `_create_file_handler()` / `_create_console_handler()` and
  attached per-logger inside `setup_logging()`. Third-party loggers
  (`httpx`, `httpcore`, `sqlalchemy.engine`) are pinned to WARNING at the end.
- **The ContextVar precedent to copy is already in the repo:**
  `server_py/src/agent/provider_factory.py`
  ```python
  from contextvars import ContextVar
  _provider_config_ctx: ContextVar[dict] = ContextVar("provider_config", default={})
  def set_provider_config(config): _provider_config_ctx.set(config)
  ```
  It is set once per request in `routers/ai.py` and read all the way down
  (`chat_loop` → `run_worker_agent` → summarisation) with **no signature changes** —
  because a ContextVar set inside an `async def` request handler propagates to every
  coroutine awaited from it. Item 5's request-id var rides the exact same mechanism.
- **The HTTP middleware** (already try/finally after PR A) is in
  `server_py/src/main.py`:
  ```python
  @app.middleware("http")
  async def log_requests(request: Request, call_next):
      start = time.time()
      status = 500
      try:
          response = await call_next(request)
          status = response.status_code
          return response
      finally:
          duration_ms = int((time.time() - start) * 1000)
          if status >= 500:   log = http_logger.error
          elif status >= 400: log = http_logger.warning
          else:               log = http_logger.info
          log(f"{request.method} {request.url.path} {status} {duration_ms}ms")
  ```
- **The efficiency line already carries a request_id** —
  `routers/ai.py` ~line 316 logs `[Efficiency] req=%s ...` with
  `metrics["request_id"]`. That id is the `RequestTiming` row id / timing id, NOT the
  HTTP-request id introduced here. Reconciling them is optional (see Item 5, step 5).
- Launch scripts that start uvicorn (Item 7b touches these):
  - `deployment/start_native.cmd` (line ~97): `python -m uvicorn src.main:app --host 0.0.0.0 !SSL_ARGS!`
  - `deployment/start_background.ps1` (lines ~90 & ~96): `$uvicornArgs = @("-m","uvicorn","src.main:app", ...)`
  - `deployment/start_federation_dev.ps1` (lines ~82 & ~99): two `python -m uvicorn ... --reload` invocations (legislation :8000, parliament :8001)

---

## Item 5 — Correlation / request IDs across all loggers

**Goal.** Every log line (HTTP, agent, crawler, sptv, app) for one request shares a
short id so `grep <id> logs/*.log` reconstructs the whole request. No function
signatures change.

### Step 1 — New `server_py/src/utils/log_context.py`
```python
import contextvars
import logging

# Default "-" so lines emitted outside a request (startup, background crawler that
# runs its own tasks) render a stable placeholder rather than raising.
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)


class RequestIdFilter(logging.Filter):
    """Inject the current request id into every LogRecord as `request_id`."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True
```

### Step 2 — Wire the id into the format + all handlers (`utils/logger.py`)
1. Add the field to the format string:
   ```python
   LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s [%(request_id)s]: %(message)s"
   ```
2. Attach `RequestIdFilter()` to **every handler** created (simplest: add
   `handler.addFilter(RequestIdFilter())` inside both `_create_file_handler` and
   `_create_console_handler`). A filter on the handler covers records from any logger
   routed through it. Import the filter at top of `logger.py`.
   - **Gotcha:** because `LOG_FORMAT` now references `%(request_id)s`, EVERY record
     formatted by these handlers must have the attribute. Attaching the filter to the
     handlers (not the loggers) guarantees it, including records that propagate up from
     third-party child loggers. If any handler lacks the filter, `KeyError:
     'request_id'` at format time — verify all handler factories get it.
   - The third-party loggers (`httpx` etc.) are pinned to WARNING and have **no**
     handlers of their own; if they propagate to root (no root handler configured
     here) they never format, so they are unaffected. If a future change routes them
     through these handlers, the filter still covers them.

### Step 3 — Set the id in the middleware (`main.py`)
```python
import uuid
from .utils.log_context import request_id_var

@app.middleware("http")
async def log_requests(request: Request, call_next):
    rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
    token = request_id_var.set(rid)
    start = time.time()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-ID"] = rid   # echo for client correlation
        return response
    finally:
        duration_ms = int((time.time() - start) * 1000)
        ...  # existing level selection + log line, unchanged
        request_id_var.reset(token)
```
- Accepting an inbound `X-Request-ID` lets a future reverse proxy / federation caller
  supply its own id (federation `POST /api/consult` could forward the caller's id —
  optional follow-up, not required here).
- `reset(token)` in `finally` avoids leaking the id across reused worker tasks.

### Step 4 — Confirm propagation into the agent pipeline
No code needed IF the work stays on the request's async task (it does: `run_worker_agent`,
summarisation, deep-research steps are all awaited from the `/api/chat` handler, same
as the provider-config ContextVar). **Verify** the id shows on `agent.log` lines during
a live query. Watch for any `asyncio.to_thread` / `run_in_executor` / `loop.run_in_executor`
hop or a **new** `asyncio.create_task` spawned per request — those start a fresh context
copy at creation time, so a task created *before* `request_id_var.set()` would miss it.
(The background crawler tasks are created at startup, outside any request — correct that
they show `-`.) If a gap is found, capture `rid` and set it at the top of the spawned
coroutine.

### Step 5 — (Optional) reconcile the efficiency line's id
`routers/ai.py` `[Efficiency] req=%s` uses the timing id. Either leave both (the log
line now also carries `[<rid>]` via the format, so they're joinable), or set the
timing `request_id` from `request_id_var.get()` so the two ids are identical. Low
value; note the decision, don't gold-plate.

### Item 5 tests
- Unit: `RequestIdFilter` sets `record.request_id` from the var; default `-` when unset.
- Unit/format: a `caplog`/manual format check that `%(request_id)s` renders (guards the
  KeyError-if-missing-attribute risk).
- Existing suite (145) must stay green — the format change touches every line but no
  assertions parse log format (verify with a full `pytest -q`).

### Item 5 live verification
1. Run locally (HTTP :8000). Submit one research query.
2. `grep <rid> logs/*.log` (rid from the response `X-Request-ID` header or `http.log`)
   → shows the matching HTTP line AND agent lines AND the efficiency line for that one
   request.
3. Two concurrent queries produce two distinct ids with no cross-contamination.
4. Startup / crawler lines render `[-]` (expected).

---

## Item 7b — Align / disable uvicorn's own access logger

**Problem.** `setup_logging()` never touches uvicorn's own `uvicorn.access` /
`uvicorn.error` loggers. Depending on flags, uvicorn may emit its own access line
alongside our `http` logger's line (duplicate, differently formatted), and uvicorn's
lifecycle/startup errors (`uvicorn.error`) never reach our shared `error.log`.

**Decision (recommended):** disable uvicorn's access log (our middleware already covers
it) AND adopt `uvicorn.error` into our handler set so uvicorn startup/shutdown errors
land in `error.log`.

### Step 1 — Disable uvicorn access logging in the launch scripts
Add `--no-access-log` to every uvicorn invocation:
- `deployment/start_native.cmd` (~line 97): append `--no-access-log` to the command.
- `deployment/start_background.ps1` (~lines 90 & 96): add `"--no-access-log"` to both
  `$uvicornArgs` arrays (SSL and non-SSL branches).
- `deployment/start_federation_dev.ps1` (~lines 82 & 99): add `--no-access-log` to
  both `python -m uvicorn ...` command strings (keep `--reload`).

### Step 2 — Adopt `uvicorn.error` into the app handlers (`utils/logger.py`)
At the end of `setup_logging()`, attach the app file/console handlers (or at least the
`error.log` handler) to `uvicorn.error`, or route it into the `app` logger:
```python
uvicorn_error = logging.getLogger("uvicorn.error")
uvicorn_error.handlers.clear()          # drop uvicorn's default handler
uvicorn_error.setLevel(base_level)
uvicorn_error.addHandler(_create_file_handler(f"{prefix}app.log", base_level))
uvicorn_error.addHandler(_create_file_handler(f"{prefix}error.log", logging.ERROR))
uvicorn_error.addHandler(_create_console_handler(console_level))
uvicorn_error.propagate = False         # avoid double emit if root ever gets handlers
```
- Leave `uvicorn.access` alone — it is silenced at the process level by
  `--no-access-log`. (Alternatively, if you prefer NOT to edit launch scripts, silence
  it in code with `logging.getLogger("uvicorn.access").disabled = True`, but the flag
  is cleaner and self-documenting. Pick one; scripts recommended.)

### Item 7b verification
1. Start via each script path locally (at minimum `start_native.cmd` / dev). Submit a
   request. Confirm **exactly one** access line per request (our `http` logger), no
   uvicorn duplicate.
2. Force a startup error (e.g. bad bind/port) → the uvicorn error appears in
   `logs/<bot>_error.log`.
3. Confirm `--reload` still works in `start_federation_dev.ps1`.

---

## Suggested order & PR shape
1. Item 5 code (log_context + logger format/filter + middleware) → unit tests → live grep check.
2. Item 5 optional efficiency-id reconciliation (decide, likely skip).
3. Item 7b launch-script flags + `uvicorn.error` adoption → live one-line check.
4. Full `pytest -q` green; update `docs/TODO.md` D9 (mark PR D done) and this file's status.
5. Commit backend-only to `main` (no dist rebuild), push, note target needs pull+restart.

## Risks / watch-list
- **KeyError on `%(request_id)s`**: any handler that formats a record without the
  filter throws at emit time. Mitigation: attach the filter inside the handler
  factories so every handler has it. Add the format-render unit test.
- **ContextVar leak across tasks**: always `reset(token)` in `finally`.
- **New per-request `create_task` before `.set()`**: would miss the id — audit for any
  such spawn on the `/api/chat` path (none known today).
- **Launch-script edits are the only cross-cutting deploy change** — verify all three
  scripts; the target runs `start_native.cmd`.
