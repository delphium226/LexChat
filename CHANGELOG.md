# Changelog

AILA releases use **calendar versions, `vYYYY.MM.N`**: the Nth release cut in
that month (`v2026.09.3` is the third release of September 2026). Each release
is an annotated git tag on `main`, and the `VERSION` file at the repo root
names the last release the code contains. How to cut one is in CLAUDE.md,
*Releases*.

To see which version a server is running, look at any of these:
- the **About** box in the app (Settings → About);
- `GET /api/bot-info`: `version`, plus `build` (`git describe`, for example
  `v2026.09.2-3-gabc1234` three commits past the release);
- the first line the server logs at startup: `[Startup] AILA <version> (build <build>)`.

Row references (P1.1 and so on) are to `docs/prepilot-fixes/FIX_PLAN.md`,
where each row carries its evidence and acceptance.

## Unreleased

On `main`:
- Release versioning: the `VERSION` file, the version in `/api/bot-info`, the
  About box and the startup log, and this changelog.

Fixed on `fix/prepilot-defects` and waiting for the next cut (not yet on `main`):
- Remove prompt wording that says the whole database lacks something (P4.6).
- Test whether an instrument is held, by its number (P3.7).
- Don't say "no case law found" when case law wasn't searched (P4.7).
- Report a lost research step as lost, not "no results", and name each
  step's outcome in the progress events (P4.5).
- The eval-harness audit event moves to **schema v6** (`delegations[].lost`,
  P4.5).
- Replay harness only, no product change: record, rather than assume, which
  research filter twelve pre-pilot sessions used (P0.6).

## 2026.09.2 — 2026-09-23

Second cut of the pre-pilot defect fixes (merge `c77e779`). Tagged
retroactively.

- Stop the chat reply dropping a subsection the research step had already
  written (P3.13).

## 2026.09.1 — 2026-09-22

First cut of the pre-pilot defect fixes (merge `d8fd73b`), and the first
versioned release. It was tagged retroactively. Everything merged to `main`
before it, including federation, Deep Research, the caching stack and the
Westminster bot, is part of this release and is recorded in the git history
rather than here.

Search and retrieval:
- Make the jurisdiction filter work (P1.1).
- Stop the "current only" filter implying in-force status (P1.2).
- Report the search's true match count (P1.3).
- Verify the enabling power (P2.3).
- Cap how long a step may keep searching (P2.7).
- Retrieve amendment and commencement relations (P3.5).
- Stop a step looping on instruments it already has, and write up findings
  at the cap (P3.8).
- Remove the unused case-law court filter (P4.4).

Saying honestly what was and was not found:
- Disclose a research halt as a limit, not a finding (P2.1).
- Explain every "not found": what was searched, and its limits (P2.2).
- Disclose the Scottish case-law corpus gap (P2.4).
- Stop asserting in-force status (P2.5).
- Don't reformat a halted step into an empty report (P2.6).
- Re-qualify a "not found" repeated from an earlier turn, or given by a turn
  that searched nothing (P2.8, with P2.10).
- Record memo-served searches in the search scope (P2.9).
- Never show a blank or lost reply (P4.2).

Citations:
- Link citations to the provision, not the Act (P1.4).
- Enforce provision links in code (P1.6).
- Cite the provision at the subsection asked for, not the whole section (P3.1).
- Say what a cited subsection's sibling subsections provide (P3.11).

Interaction:
- Fix the research-mode dead-end and the mode-switch wording (P4.1).

For the eval harness: the audit event is **schema v5** (`halted`,
`empty_completions[]`, `halted.written_up`, `mode_change`).

Also in this cut, with no product change: the replay harness and baselines
(P0.1, P0.2, P0.3, P0.5, P1.5), and two enquiries about the LEX corpus
(P5.1, P5.3).
