# Release Notes — Legislation Bot

## 2026-07 release (changes since 30 June 2026)

For users researching UK legislation and case law. This release adds a plan-first
research workflow, makes research answers more complete and reliable, and reduces
running costs — alongside a round of security and platform hardening.

Delivered to the target via `git pull origin main` + a bot restart.

---

### Highlights

- **Deep Research mode** — an opt-in, plan-first workflow: the bot drafts an editable
  multi-step research plan, you approve or edit it, and it then executes the plan
  autonomously and returns an integrated report with an auditable record of the approved
  plan.
- **More complete case-law answers** — when a case and its appeal both appear in the
  results, the bot now retrieves and cites the higher-court decision rather than stopping
  at first instance.
- **More reliable retrieval** — legislation lookups now recover automatically from
  rate-limiting and transient errors, so a momentary hiccup no longer produces a silently
  incomplete answer.

---

### Research capabilities

- **Deep Research mode.** A new chat mode alongside Conversational and Research. The bot
  proposes a step-by-step plan; you can add, remove, reorder, and edit steps before
  approving. On approval it works through the plan and composes a single integrated
  report — a summary up top with key findings and any material gaps called out. The
  approved plan is saved with the answer for audit.

### Answer quality

- **Appellate-decision detection.** When case-law search results contain both a case and
  its appeal (e.g. High Court and Court of Appeal), the bot is prompted to retrieve and
  cite the appellate decision, not just the first-instance judgment. (This also corrected
  a parsing fault where neutral citations and court levels were read from the wrong fields
  in the case-law feed, so citations and court information are now populated correctly.)
- **Report-structure validation.** After a research report is produced, its structure is
  checked and, if needed, tidied once (without re-running research) so section headings
  and a References list are reliably present.
- **Resilient legislation lookups.** Legislation search, section, and full-text calls now
  retry on rate-limiting and transient errors with sensible backoff, so answers stay
  complete under load.
- **Answer completeness.** Restored completeness in research answers — operative statutory
  instruments, penalties quoted verbatim, appeals, and mandatory References — that had
  regressed during earlier tuning.

### Cross-bot research

- If a Parliament Bot is registered as a peer, the bot can consult it for Scottish
  Parliament questions (debates, committee scrutiny, bill progress) instead of deflecting
  — and clearly distinguishes "no records found" from "parliamentary research is
  unavailable in this session".

### Cost & performance

- **Provider prompt caching** — repeated context in the research loop is billed at the
  cached rate on supported models.
- **Repeat-work caching** — identical lookups within a single request (common in Deep
  Research) are served from memory rather than fetched and summarised again.
- **Cross-user summary cache** — a shared cache of document summaries means that when a
  second user asks the same question of the same public source, the summarisation step is
  skipped. Exact-match only, so amended text is never served stale.

### Administration (admin users)

- **Cache monitoring** — a new **Cache** tab shows cache activity, daily trends, recent
  hits, and current settings, with a purge control.
- **Efficiency monitoring** — per-request efficiency metrics and breach alerts, tuned to
  this bot's research profile. The Efficiency tab is admin-only.
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
- **Observability** — request-ID correlation across logs, runtime log-level control, and
  fuller error diagnostics make production issues easier to trace.
- **Under the hood** — substantial backend and frontend restructuring, a design-token
  migration, isolated test databases, and broader automated test coverage improve
  maintainability with no change to behaviour.

---

### Deployment notes

- Pull `origin/main` and restart the bot — several changes are backend logic that require
  a process restart to take effect.
- New feature flags default to **on**, so behaviour is unchanged until an admin opts in.
