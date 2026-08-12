# Server-side run durability — deferred design

**Status: NOT BUILT.** Recorded so it can be picked up deliberately.

## What shipped, and what it does not cover

Concurrent per-chat research runs are **in-tab only**. A lawyer can launch a query in one chat, switch to any other chat (new or historic) and work there, with up to `MAX_CONCURRENT_RUNS = 3` running at once (`client/src/hooks/useChatRuns.js`). That works because the `fetch` in `services/api.js` lives in JS and is entirely independent of what React renders — the fix was to stop aborting on chat switch and to route each run's output into its own bucket.

**A page refresh, a tab close, or a browser crash still destroys the run**, for two independent reasons:

1. `_watch_disconnect` (`server_py/src/routers/ai.py:364-374`) polls `request.is_disconnected()` and sets `cancel_event`; the generator's `finally` (`ai.py:234-236`) sets it unconditionally. The agent checks `cancel_event` throughout, so a disconnect actively kills in-flight research.
2. `/api/chat` **never writes a `Message` row**. The only assistant-message persistence in the whole system is the frontend calling `POST /api/chats/{id}/messages` after the `result` SSE event (`client/src/hooks/useChat.js`, in `runExchange`). If the tab dies, the answer is gone — money and queue time already spent.

A `beforeunload` warning now fires while any run is active, which is a mitigation, not a fix.

## What building it would take

**1. A client-supplied run id.** No such identifier exists today. `chat_id` is the only one on the request and it is `Optional` (`routers/agent_request.py`, `AgentRequestBase`). The server's `request_id` (`ai.py:78`) is generated server-side and only ever reaches the client buried in the `timing` event. Add a client-generated `run_id` to `AgentRequestBase` so it is accepted by `/api/chat` and `/api/system/chat` alike (the latter subclasses `ChatRequest`, so this is free).

**2. Detach the work from the connection.** Today `run_agent_task` is launched with `asyncio.create_task` but is still awaited by the generator, which is the only thing holding it (`ai.py:174-176`, `:209`). It would move into a process-level registry — the shape already exists in `services/parliament_crawler.py` (`_refresh_status` + `get_refresh_status()`, driven by the fire-and-forget task in `routers/developer.py`), but that is a single-slot dict and would need to become a keyed store with a janitor task owned by the lifespan (`main.py:143-189`, alongside `background_health_loop`).

**3. Stop cancelling on disconnect.** `_watch_disconnect` becomes "detach", not "cancel". Note the queue-slot accounting caveat: `RequestQueue.enqueue` (`utils/queue.py:56-74`) frees its semaphore slot correctly, but a client that disconnects **while still waiting in `_queue`** stays in the list and inflates every other waiter's reported position — that becomes more visible once disconnects are routine rather than terminal.

**4. Persist server-side.** The assistant message must be written by the backend when the run completes, whether or not anyone is watching. `Message.content` is `nullable=False` (`models.py:70-98`) and there is no status column anywhere, so a placeholder row needs either a new nullable column or a separate `chat_runs` table. Moving persistence server-side also has to preserve the live-only `suggestions` (no DB column at all today — the frontend keeps them in `liveExtrasRef`), which is arguably the moment to give them one.

**5. A re-attach endpoint.** `GET /api/chat/stream/{run_id}` with a replay buffer, so a reconnecting client gets the tokens it missed and then continues live. Auth is not a blocker: the token is a same-origin HttpOnly cookie (`dependencies.py:38-45`, `routers/auth.py:101-114`), so a real `EventSource` would carry credentials with no plumbing. The current POST + `ReadableStream` shape cannot itself be resumed, which is why this needs to be a separate GET.

**6. `/api/system/chat`.** `routers/system.py:103-256` is a near-copy of the same generator (same `_watch_disconnect`, same pump, same `finally`). Either share the machinery or apply the same treatment — the drift that produced the audit-trace bug started exactly this way.

## Why it was deferred

The in-tab version delivers the actual request (switch chats without interrupting research) as a frontend-only change with no schema migration and no new failure modes on an internet-restricted production server. The durable version touches the request lifecycle, the queue, the schema, and two SSE endpoints. It is worth doing if lawyers start losing long Deep Research runs to accidental refreshes — that is the signal to watch for.
