# Release Notes — Parliament Bot

## 2026-07 release (changes since 30 June 2026)

For users researching Scottish Parliament (Holyrood) records — chamber debates,
committee proceedings, and written answers. This release makes chamber debates fully
searchable, adds video-timestamp citations, improves retrieval quality, and brings a
plan-first research workflow — alongside security and platform hardening.

Delivered to the target via `git pull origin main` + a bot restart.

---

### Highlights

- **Video-timestamp citations** — Official Report citations can now carry a
  `▶ watch from HH:MM:SS` deep link into Scottish Parliament TV, for both chamber and
  committee proceedings, so a citation jumps straight to the moment it was said.
- **Full-text chamber (plenary) search** — chamber debates are now fully searchable and
  retrievable as verbatim speeches, closing the gap for finding a minister's exact
  statement of a provision's purpose.
- **Deep Research mode** — an opt-in, plan-first workflow that drafts an editable
  research plan, then executes it and returns an integrated report.

---

### Scottish Parliament research

- **Full-text plenary search & retrieval.** Chamber debates are crawled into a local
  full-text search index; you can search across them and retrieve the verbatim speeches
  for a specific agenda item on demand — not just short excerpts.
- **SP TV video timestamp deep links.** Where a citation can be matched to the broadcast
  captions, the bot attaches a deep link that opens Scottish Parliament TV at the exact
  timestamp. Covers **plenary and committee** proceedings, surfaced both inline and in the
  sources panel. This is additive and fail-soft — if a link can't be resolved, the plain
  citation is shown. **Off by default**, enabled per deployment.
- **Better retrieval quality.** Searches that previously returned nothing because of one
  colloquial or non-Holyrood term are now rescued by an any-term fallback, and the bot is
  guided to use official Holyrood terminology (e.g. "public body" rather than "quango").
  Delivered with no new dependencies.
- **Fresher, faster data.** The background crawler now updates incrementally — restarts
  and daily runs re-scan only a recent window rather than re-walking the full
  back-catalogue, and pick up late-published transcripts on meetings already seen.

### Deep Research mode

- A new chat mode alongside Conversational and Research. The bot proposes a step-by-step
  research plan which you can add to, reorder, and edit before approving; it then works
  through the plan and composes a single integrated report, with the approved plan saved
  for audit.

### Cross-bot research

- If a Legislation Bot is registered as a peer, the bot can consult it for
  legislation-text questions (Act provisions, definitions, commencement dates) rather than
  refusing.

### Cost & performance

- **Provider prompt caching** — repeated context in the research loop is billed at the
  cached rate on supported models.
- **Repeat-work caching** — identical lookups within a single request are served from
  memory rather than fetched and summarised again.
- **Cross-user summary cache** — a shared cache of document summaries means that when a
  second user asks the same question of the same public source, the summarisation step is
  skipped. Exact-match only, so revised records are never served stale.

### Administration (admin users)

- **Cache monitoring** — a new **Cache** tab shows cache activity, daily trends, recent
  hits, and current settings, with a purge control.
- **Efficiency monitoring** — per-request efficiency metrics and breach alerts tuned to
  this bot's research profile, including a check for searches that loop instead of
  retrieving. The Efficiency tab is admin-only.
- **User export** — a Developer-tab button produces a copy-pasteable CSV of all user
  accounts (name, email, role).
- **Chat-mode toggles** — the `Research` and `Deep Research` modes can each be switched on
  or off from Developer → Feature Flags (default on). When a mode is off it is hidden from
  the selector and users on it fall back to Conversational.
- **Weekly feedback** — the periodic feedback form now appears as a modal popup.

### Security, reliability & platform

- **Endpoint hardening** — endpoints that were previously unauthenticated (including
  data-wipe and configuration actions) now require authentication; developer actions
  default to admin-only. The server also warns at startup if the auth secret is left at a
  default, and leaked credentials were removed from the repository.
- **Observability** — request-ID correlation across logs, runtime log-level control, a
  dedicated log for the video-link client, a dedicated crawler log, and fuller error
  diagnostics make production issues easier to trace.
- **Under the hood** — substantial backend and frontend restructuring, parliament-aware
  interface copy, a design-token migration, isolated test databases, and broader
  automated test coverage improve maintainability with no change to behaviour.

---

### Deployment notes

- Pull `origin/main` and restart the bot — several changes are backend logic (crawler,
  parsers, retrieval) that require a process restart to take effect.
- New feature flags default to **on**, so behaviour is unchanged until an admin opts in.
- **Video deep links stay off by default.** Enabling them requires the Scottish
  Parliament TV hosts to be reachable from the target; caption coverage is strongest for
  more recent sittings.
