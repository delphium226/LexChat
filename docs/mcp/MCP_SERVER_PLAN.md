# MCP server for the AILA bots — plan

**Status:** proposed, not built (2026-10-19).

**Goal.** Make the three released bots — **AILA** (legislation and case law), **ParliChat** (Holyrood)
and **HansardChat** (Westminster) — callable as MCP servers by outside AI clients (Claude, Copilot and
others), so a lawyer can use them from inside those tools.

**Out of scope for now (user decision, 2026-10-19): network reachability.** Whether a given client's
requests can reach the target (client-side vs vendor-cloud origin, firewall rules, published vendor IP
ranges) is deferred. This plan assumes a client that can reach the bot's HTTPS URL. The auth design
below is the part most entangled with that question and is phased accordingly (§4).

---

## 1. Shape: one module, one endpoint per bot

Each bot serves `/mcp` itself (MCP Streamable HTTP), from one shared module
(`server_py/src/routers/mcp_server.py`); the tool list is selected by `RESEARCH_MODE` exactly as
`get_worker_tools` is. Not a gateway on AILA that forwards to its peers:

- the codebase gives every bot an endpoint for free, with its own users, quotas, timing rows and audit;
- a gateway would ride `/api/consult`, which today drops the sources, skips the request queue and
  timing rows, and uses a never-expiring admin token (§4) — all things this plan would have to fix twice;
- a client handles several MCP servers fine; a single combined connector can come later if wanted.

Public URLs follow hosting: AILA at `/mcp`, ParliChat at `/parlichat/mcp` under the co-hosting plan
(`docs/deployment/PARLICHAT_COHOSTING_PLAN.md`). HansardChat has no deployment on the target yet.

**Never on the drafting bot.** Its input is unpublished legislative text. `RESEARCH_MODE=drafting`
refuses to mount `/mcp` **in code**, the same way the local prompt cache is forced off there
(`build_request_config`), not by an admin toggle. Pinned by a test next to `test_drafting_security.py`.

## 2. Tools

### Tier 1 — ask the bot (built first)

One tool per bot, running the bot's full Manager → Worker pipeline, so every guard we have built
(scope blocks, P2.3's enabling-power rule, the answer-seam restores, the rail filter, P3.45/P3.47's
citation checks) applies to what the outside client receives.

| Bot | Tool | Inputs |
|---|---|---|
| AILA | `ask_aila` | `question`; `research_type` (`legislation_only` \| `case_law_only` \| `legislation_and_case_law`, default the bot's); optional `jurisdiction` |
| ParliChat | `ask_parlichat` | `question`; optional `record_type`, `sessions`, `date_from`/`date_to` (the existing filters, `_apply_parliament_filters`) |
| HansardChat | `ask_hansardchat` | `question`; optional date range |

- **Result:** text content is the answer as the UI would show it (markdown, linked citations, the scope
  footer) **followed by a plain References list of the sources and the data-licence attribution lines**
  (§7). `structuredContent` additionally carries `{answer, sources: [{title, url}], bot_id, bot_name,
  model, version, build}` from `result["sources"]` and `version.py`. The References go in the text
  because claude.ai does not list `structuredContent` support and Copilot does not document it (§9).
  The sources are the reason to prefer this over `/api/consult`'s answer-only body.
- **A call outlasts some clients' timeouts.** A research run takes 90 s to 6 min. claude.ai, Desktop
  connectors and mobile cut a tool call at **240 s**; Claude Code gives up after **5 min idle**;
  Copilot Studio and M365 Copilot document no MCP figure (an older Copilot plugin guide says 20 s).
  So `ask_*` waits for the answer up to a per-call budget (default 200 s, sending progress meanwhile).
  If the run is still going at that point, the tool returns a `job_id` and the instruction to call
  **`get_answer(job_id)`**. That tool waits up to the same budget again and returns the answer or "still
  running". The run carries on in the background either way, so a client timeout never throws away a
  run that is half done. Jobs live in memory, keyed to the user, and are kept 1 h. A restart loses them,
  and `get_answer` then says so.
- **One-shot:** runs with `_consulted: True`, so `CONSULTED_PEER_BLOCK` makes the Manager answer the most
  reasonable reading with a stated assumption instead of asking a clarifying question it cannot get
  answered. The `<suggestions>` strip already runs at the manager seam; chips are not attached.
- **Chat mode:** Research (Conversational is cheaper but is the quick-lookup Worker; decide from the
  cost numbers in §5). **No Deep Research over MCP**: its plan-approve step needs the UI, and a run costs
  $3–5.
- **Tool descriptions** are written for an outside model choosing between tools: what the bot covers,
  what it does not (e.g. AILA holds no Scottish case law while SCTS is off), that a call takes minutes,
  and that the answer should be relayed with its citations, not paraphrased away.
- **Input schemas stay flat:** Copilot Studio drops `$ref` inputs, treats enums as plain strings and
  truncates multi-type arrays. Use no `$ref` and one type per field, and validate the enum values on
  the server with a clear error that lists the allowed values.

### Tier 2 — the data only we hold (after Tier 1, if wanted)

No LLM spend on our side; the client's model does the reasoning. Offer only what an outside client
cannot get elsewhere:

| Bot | Tools | Why it is ours |
|---|---|---|
| AILA | `find_instruments_made_under`, `lookup_legislation` | the made-under record (86,744 instruments, P3.31/P3.33) exists nowhere else |
| ParliChat | `search_scottish_plenary`, `get_scottish_plenary_debate`, `search_scottish_committee_transcripts`, `get_scottish_committee_transcript` | the local full-text Official Report archive and video deep links |
| HansardChat | none | it searches UK Parliament's public APIs live; nothing to add |

Trade-off: the code notes appended to these results still go out, but the Worker prompts' rules that
govern how they are read do not. Size: Claude Code's default cap is 25K tokens a result, claude.ai's
about 150,000 characters, so the transcript reads need a cap tighter than `_cap_speeches`' 150 speeches.

Not exposed at all:
- **Raw LEX search and text.** i.AI already publishes its own MCP server at
  `https://lex.lab.i.ai.gov.uk/mcp`: 13 tools, one per LEX endpoint, unauthenticated, rate-limited per
  IP, and labelled experimental. Wrapping it again adds nothing.
- **Case-law search.** See the licence question in §7.

## 3. Call path

Model it on `/api/system/chat` (`routers/system.py`), **not** on `/api/consult`:

1. `build_request_config` with the tool's arguments mapped to the existing fields (one config seam, as
   the eval endpoint's history taught), plus `_consulted: True` and `_mcp: True`.
2. Enqueue on the provider's `RequestQueue` (`/api/consult` bypasses it; outside load must not).
3. `on_chunk` → MCP progress notifications: each `tool_start` becomes a progress message
   ("Searching legislation…", "Reading s.38…"), which also tells the client the call is alive.
4. Client cancellation sets `cancel_event`.
5. `TimingCollector` row persisted with `request_timings.source = "mcp"` (the column exists; `"app"` and
   `"eval"` today). The dashboards do not filter on `source` yet — add the filter with this, or MCP
   traffic moves the headline numbers.
6. Errors render through `describe_agent_error` and return as an MCP tool error (`isError: true`), never
   an empty result.

**SDK:** the official `mcp` package, **v2.x** (2.3.0 as of 2026-10-02). It needs Python 3.11 or later.
v2 broke compatibility with v1: `FastMCP` became `mcp.server.MCPServer`, and examples written for 1.x
no longer apply. v2 serves both the sessionless 2026-07-28 protocol and 2025-era clients from one app.
Mounting traps:
- `Mount(..., app=server.streamable_http_app())` registers the endpoint at `/mcp`.
- **A mounted app's lifespan never runs.** AILA's own `lifespan` must enter
  `async with server.session_manager.run():`, or the first request fails with "Task group is not
  initialized".
- **Behind a real hostname, pass `transport_security=TransportSecuritySettings(allowed_hosts=…,
  allowed_origins=…)`**, or every request gets a 421.
- **Register the mount before the SPA catch-all** (`main.py:290`), which matches every GET path.
- The SDK's own HTTP client trusts the OS certificate store, via `truststore`. It is not used by the
  server side, but it ships in the bundle.

## 4. Auth

Today's only machine credential cannot be reused: `/api/auth/federation-token` mints a **non-expiring
admin JWT**, and `get_current_user` never reads the `scope` claim, so that token works on every admin
route (Danger Zone, API-key settings). A token handed to an outside client must be narrow, expiring and
revocable.

**Phase 1 — personal access tokens** (clients that send a static `Authorization` header):

- `mcp_tokens` table: `user_id`, `sha256(token)`, `label`, `created_at`, `expires_at` (default 90 days),
  `last_used_at`, `revoked_at`. The token itself shown once.
- Minted by the user in Settings, listed and revoked there; an admin can revoke any (Admin Portal).
- `/mcp` accepts only these, checked against the DB on every call (so revocation and a disabled user
  take effect at once). `get_current_user` **rejects** them on every other route.
- Fix alongside: `get_current_user` rejects `scope: "federation"` tokens outside `/api/consult`.

PATs cover **Claude Code** (`--header`), **VS Code Copilot** (`headers`) and **Copilot Studio**, which
takes an API key in a header. On **claude.ai, Desktop connectors and mobile**, static headers are beta
for a limited set of organisations. **M365 Copilot** declarative agents do not take API keys for MCP at
all.

**Phase 2 — OAuth**, for claude.ai and M365 Copilot. Both accept Entra ID. `/mcp` becomes an OAuth 2.1
resource server that validates Entra tokens and maps them to an AILA user. The spec requires:
- an RFC 9728 protected-resource metadata document;
- a 401 that points to it;
- tokens checked for the right audience;
- no tokens in query strings.

Clients register by CIMD, by DCR (now deprecated in the spec), or with a pre-registered client
ID/secret. Entra works through a pre-registered app registration. claude.ai additionally needs the MCP
URL registered as an Application ID URI on a tenant-verified domain. This phase is deferred with
connectivity: the clients that need it are the ones that call from their vendor's cloud. The MCP spec
makes authorization optional, so a PAT in a header is permitted, just non-standard.

## 5. Limits and controls

- **Feature flag `mcp_enabled`**, Developer tab, **default OFF** (unlike the other flags, because this is
  new outside exposure). Off ⇒ `/mcp` returns 404.
- **Per user:** one call in flight; a daily cap on Tier 1 calls (start at 30; Admin Portal setting).
  An outside model can loop on a tool, and every Tier 1 call spends our LLM budget
  (of the order of $0.20 a research run, and ~$0.76 for each Worker attempt that runs away, P4.10).
- **Jobs:** a `job_id` (§2) belongs to its user. `get_answer` on someone else's job returns the same
  "unknown job" as a job that does not exist.
- **Logging:** tool arguments through `redact_args` (`question` is free text, so redacted at INFO).

## 6. Prerequisites (before `/mcp` is reachable by anyone)

1. **Close the SPA path traversal** (`main.py:290-301`, still open on `origin/main`): the catch-all
   joins the request path onto `client/dist` with no containment check and serves the file
   unauthenticated.
2. **Scope checks in `get_current_user`** (§4).
3. **`JWT_SECRET`**: confirm the target does not run the placeholder from the public repo's
   `.env.native`.
4. **Offline wheels** for `mcp` v2 and its dependencies, committed like `deployment/pdf_wheels/`, for
   the target's Python version (needs 3.11 or later; the dev machine is 3.14; confirm the target's).
   The dependencies: anyio, httpx2, jsonschema, mcp-types, opentelemetry-api, pydantic ≥ 2.12 (AILA
   has 2.13), pyjwt[crypto], python-multipart, pywin32, sse-starlette, starlette, uvicorn, truststore.
   Check every pin against FastAPI 0.135's own.

## 7. Open decisions (the user's)

1. **Tier 2 at all**, and which tools.
2. **Chat mode** for Tier 1: Research or Conversational.
3. **History:** save each MCP call as a chat in the user's AILA history (marked "via MCP"), or keep only
   the timing row. Saving it makes it visible in the Activity Log (QUERY rows are derived from messages)
   and lets the lawyer rate it.
4. **Licences.** Each one needs an attribution line in every result (§2). Two of them are larger than
   MCP:
   - **Find Case Law, Open Justice Licence v2.0.** The licence excludes "computational analysis of the
     Information (including indexing by search engines)". That needs a separate licence from TNA
     (caselawlicence@nationalarchives.gov.uk). An agent that searches and summarises judgments
     plausibly falls inside the exclusion, **and that is what AILA already does in the UI, not only over
     MCP**. i.AI has disabled case law in Lex itself "pending TNA licence". Ask TNA before case law goes
     out over MCP, and ask about the product as it stands at the same time. Attribution: "Contains
     information licensed under the Open Justice Licence v2.0".
   - **TheyWorkForYou** (ParliChat's `search_scottish_parliament` and `get_member_info`). The free tier is
     for registered charities and unpaid non-profit projects only. A government organisation needs a
     paid plan (£20 a month for 1,000 calls, up to £300 a month unlimited), and outside clients add
     calls. Attribution: "Data service provided by TheyWorkForYou".
   - **Open Parliament Licence v3.0** (HansardChat): permits reuse in products. Attribution: "Contains
     Parliamentary information licensed under the Open Parliament Licence v3.0".
   - **Scottish Parliament Copyright Licence** (ParliChat): published material may be reproduced. It must
     not imply official status or SPCB endorsement. Attribution: "Contains information licensed under
     the Scottish Parliament Copyright Licence". Legislation itself is Crown copyright under the OGL.
5. **Who may use it:** every user, or users an admin enables.
6. **Data handling:** the question and our answer pass through the outside client's vendor. Whether
   lawyers may do that is the organisation's policy, but exposing the bots makes it easier; the bots'
   OFFICIAL-SENSITIVE guidance (`LOG_LEVEL`, logging plan Item 4) should say so.

## 8. Build order

| Step | What | Done when |
|---|---|---|
| M0 | Prerequisites 1–3 (§6) | traversal and scope tests pass; on `main` regardless of MCP |
| M1 | PATs: table, Settings UI, `/mcp` verifier | a PAT works on `/mcp` only; revocation immediate |
| M2 | `/mcp` mount + `ask_*` and `get_answer` (Tier 1), queue, progress, jobs, timing rows, flag | each bot answers a call from Claude Code and VS Code Copilot on the dev machine, with sources; a run past the per-call budget is collected through `get_answer` |
| M3 | Limits, dashboard `source` filter, docs, offline wheels | target install from the bundle; Efficiency tab separates MCP |
| M4 | Tier 2 tools (if decided) | |
| M5 | OAuth / Entra (with connectivity) | |

## 9. What each client supports (research, 2026-10-19)

Network origin is left out, as deferred above. The figures come from vendor documentation read on
2026-10-19. These products change monthly, so re-check them before building against any one.

| Client | Auth we can use | Tool-call limit | Result size | Beyond plain tools |
|---|---|---|---|---|
| claude.ai, Desktop connectors, mobile | OAuth (DCR, CIMD or pre-registered ID/secret; Entra works); authless; static header beta only | **240 s** | ~150,000 chars | prompts, resources; `structuredContent` and elicitation not listed |
| Claude Code | static header, OAuth, `headersHelper` | 5 min **idle** (`CLAUDE_CODE_MCP_TOOL_IDLE_TIMEOUT`); calls background after 2 min | 25K tokens default (`MAX_MCP_OUTPUT_TOKENS`) | resources, prompts, elicitation, progress |
| Claude Desktop, local config or extension | via a local bridge (e.g. `mcp-remote`, community tool) | not documented | not documented | |
| VS Code GitHub Copilot | `headers`, OAuth incl. Entra | not documented | not documented | prompts, resources, elicitation, sampling |
| Copilot Studio | API key in a header, OAuth 2.0 (Entra as manual IdP), none | not documented | not documented | tools and resources only; drops `$ref`, enums as strings |
| M365 Copilot declarative agents | Entra SSO, OAuth, none; **no API key** | not documented (an older plugin guide says 20 s) | truncated to the token window | tools, citations |

Main sources: support.claude.com/en/articles/11175166 · claude.com/docs/connectors/building ·
code.claude.com/docs/en/mcp · code.visualstudio.com/docs/copilot/customization/mcp-servers ·
learn.microsoft.com/microsoft-copilot-studio/mcp-add-existing-server-to-agent ·
learn.microsoft.com/microsoft-365/copilot/extensibility/plugin-authentication ·
modelcontextprotocol.io/specification/latest/basic/authorization · pypi.org/project/mcp ·
lex.lab.i.ai.gov.uk · caselaw.nationalarchives.gov.uk/open-justice-licence ·
theyworkforyou.com/api/terms · parliament.scot/about/copyright.
