# Parallel batch 12: Session 43's next steps and the data-improvement measurements, in one session

**Set up on 2026-10-09 for Session 44, at the user's request** ("merge this session's next steps with session 43's
upcoming batch 12 next steps, so we can go back to working in single consecutive sessions"). On 8-9 October two
sessions worked the same branch in one checkout: Session 43 ran batch 11, and a second session built P3.31 (the
made-under record, raised to P1) and booked the data improvements P3.32 to P3.44. **From Session 44, one session
works the branch at a time.** This brief carries both strands: Session 43's handover ("Session 43 — handover for
Session 44") and `DATA_IMPROVEMENT_BATCH_1.md` (now merged here as agents F and G; do not run it separately).

It follows batches 1-11: agents in git worktrees, the main session integrating, nothing merged that the
integrator has not re-checked. **Every agent is $0 in model spend.** Live reads only where an agent's section
says so and the user agrees at launch. **The paid steps are the integrator's alone, each priced to the user first
and run only on the user's go-ahead:** (1) P3.12's seam draws at the start (about $0.20; the default Worker seam is
uncapped, so price at the runaway case, about $2.30 a draw); (2) P3.10's 6374 n=3 (about $3.20); (3) P3.20's
acceptance (6375 n=3 and 6370, 6380 n=1: about $4.90 to $8, and about 135 SCTS calls). Nothing is authorised yet.

**Each agent is given its own section, plus, verbatim from `PARALLEL_BATCH_11.md`, its sections "Rules for every
agent", "Lessons from batches 1-10" and "Shared setup", with these substitutions:** "batch 11" reads "batch 12";
notes go to `docs/prepilot-fixes/notes/batch12_<A-G>.md`; scratch to the gitignored
`docs/prepilot-fixes/evidence/seam/batch12/<letter>/`; test databases `lexchat_test_<a-g>` (create f and g if
missing); rule 1's reading runs from "Session 43 — 2026-10-08/09" to the end of `SESSION_LOG.md`, including the
merged handover. **Plus the lessons below**, verbatim.

## Lessons added since batch 11 (give these verbatim with each brief)

- **Only one session works the branch now.** If `git log` shows a commit you did not expect, stop and tell the
  integrator; do not reconcile it yourself.
- **The made-under record is a census.** `docs/prepilot-fixes/evidence/madeunder/*_snap.jsonl` lists every SSI
  (1999-2026) and UK SI (1987-2026) number legislation.gov.uk was asked for, held or `absent`, with its recital and
  parsed powers. For "does legislation.gov.uk publish X with text" in those two series, read it; do not call out.
- **An offline re-parse must keep what the fetch resolved** (`madeunder_probe.reparse_context`): re-parsing a
  stored recital without the preamble before it once threw away 1,200 resolved anaphors.
- **legislation.gov.uk's `/introduction/made/data.xml`** carries an instrument's whole preamble at a fraction of
  the full XML's size (the same recital on 50 of 50 sampled); LEX's `/legislation/proxy` returns legislation.gov.uk
  XML byte for byte, so a route through it needs no whitelist entry.
- **A bash heredoc mangles backslashes** (`\b` became a backspace byte twice on 8-9 October): write Python that
  holds a regex to a file, or use the Edit tool.

**What the user has already decided (do not re-open):** everything in `PARALLEL_BATCH_11.md`'s list that its
Session 43 entry did not change, and:
1. **By severity**, unless a dependency prevents it. FIX_PLAN's top order line ("end of Session 43", annotated
   2026-10-09) is the order.
2. **P3.12 (P1):** measure first at the seam on A's `evidence/seam/batch11/A/seam_b11_rep1_r2brief.json` and
   `wave4_b11_sweep/6335_rep{1,2,3}.json` turn 7, to separate the brief, the block and the quick-lookup Worker's
   2-5-sentence budget, and to size the wrong-pinpoint rate. Candidate levers, not decided: code-written paragraph
   lines at the answer seam (P3.13's pattern); the concision rule relaxed for a code-fetched unit; **the exact
   paragraph fetched from legislation.gov.uk through the proxy** (the 2026-10-09 note on the row).
3. **P3.10 (P2):** the line on every step 2+ (no longer the regex gate), then 6374 n=3.
4. **P3.20 (P2):** the design on its row (two lists in `search_case_law`, the any-term fallback, `AdditionalDate`
   as the date of decision, a per-request cap and concurrency limit, no pypdf, the acceptance with controls, the
   grader in the build). The whitelist request and SCTS's written confirmation are the user's, carried.
5. **P4.3 (P2):** lever R next for (iii), measured first. **P4.23** measure first. **P4.22 raised to P2**
   (P3.31 makes enabling-power blocks common).
6. **Data improvements are measured, not built, in this batch** (F and G): each go row is re-slotted by measured
   value after the fold. P3.35, P3.36 (Blocked) and P3.37 (not recommended) are not in it.
7. **Agents propose; the integrator applies; the user approves anything not mechanical**, including any wording a
   lawyer or the Worker will read. Never merge or push to `main`. The Fix Tracker only when the user asks.

---

## Where things stand (verified 2026-10-09, afternoon)

- Branch `fix/prepilot-defects` at this file's commit or later, pushed; `main` at `a6b4a76`.
- `plan_status`: 61 of 97 rows, 4 in progress (P3.12, P3.22, P3.10, P4.3), 9 of 14 buckets; `plan_lint` exit 0.
- **3,017 tests** (Session 43's 3,007 plus P3.31's UK SI work).
- **66 replay directories** (Session 43's `wave4_b11_sweep`; the other session's `wave4_p331`).
- **The made-under record** (P3.31, done): `server_py/data/made_under/` snapshot `2026-10-09.1`, 86,744
  instruments, 68,780 with parsed powers; the Worker tool `find_instruments_made_under`; the forward fallback in
  `agent_shared.stored_enabling_note`; `tools/madeunder_probe.py`, `tools/madeunder_grade.py`.
- **Fix Tracker v47** (Type column; every row through P3.44 and P4.25; P5.4 Fixed, P4.22 at P2; Next = this
  batch).
- Machine: no server, no pin file, no replay running, no worktree but the main checkout.

---

## The batch

| Agent | Row (tracker severity) | Work | Kind | Live calls | Main files |
|---|---|---|---|---|---|
| **A** | **P3.12** (P1) | The seam results relayed; compare the payloads; probe the exact-paragraph route; build the one candidate the integrator's seam result points at (unmerged until the user approves its wording) | measurement, then a candidate | up to 20 legislation.gov.uk / LEX proxy, if agreed | `utils/schedule_units.py`, `agent_shared.schedule_route_block`, the answer seam if chosen, tests |
| **B** | **P3.10** (P2) | The line on every step 2+; the dry run; the 6374 sweep priced | product | none | `agent_core._build_step_brief`, tests |
| **C** | **P3.20** (P2) | The build to its decided design, with its grader | product + tooling | up to 40 SCTS, if agreed (only to confirm shapes) | `agent/tools/caselaw.py`, the gated wording sites, tests, `replay_report` (its own subcommand only) |
| **D** | **P4.3** (P2), **P4.23** (P2), **P4.24** (P3), the `lookup --routing` fix (P3) | Lever R measured, then built if it meets its bar; P4.23 and P4.24 measured (P4.24's titles from the made-under record); the routing fix | measurement + product | none | `agent_core.run_worker_agent`'s filter, `_source_is_used`, `tools/replay_report.py` (`rail`, `lookup`) |
| **E** | **P3.22** item 3 (P2), **P3.4**'s research-mode follow-up (P2), **P4.22** (P2) | Measure first, each; P4.22 built if its measurement is clean | measurement + product | none | `caselaw.py` (read), `search_scope` strip, tests |
| **F** | **P3.38**, **P3.39** (P2), **P3.34** (P2), **P3.43** (P3) | Data-improvement measurements: `DATA_IMPROVEMENT_BATCH_1.md` agents A and C, verbatim | notes only | none | the export, replays, the census |
| **G** | **P3.41** (P2), **P3.28** (P3), **P3.32**, **P3.33**, **P3.42** + **P3.26**, **P3.30** | Data-improvement measurements: `DATA_IMPROVEMENT_BATCH_1.md` agents B and D, verbatim, **except D's item 3 (P3.12's route), which is agent A's here, and D's item 5 (P4.24), which is agent D's** | notes only | up to 60 LEX and 200 legislation.gov.uk, if agreed | the replays, live samples, the census |

**Why these seven.** By severity: P3.12 is the only open P1 work not Blocked; the P2 rows with decided next steps
are P3.10, P3.20, P4.3, P4.23, P3.22's item 3, P3.4's follow-up and the newly raised P4.22; the data improvements
are measured beside them at $0 because they touch no product code. **Not in this batch:** the other P3 rows, and
anything Blocked.

**Merge order: B, then A (if a candidate is built and approved), then E, then C, then D (after any sweep: its rail
filter changes `sources_kept`, Invariant 3), then F and G (notes only).** **Never commit while a replay runs.**

**Collision points.**
- **`agent_core.py`** is touched by B (`_build_step_brief`) and D (`run_worker_agent`'s filter): different
  functions; each agent names the functions it changed.
- **`tools/replay_report.py`** is touched by C (its own subcommand) and D (`rail`, `lookup`): different
  subcommands; the integrator merges C before D and re-runs both.
- **A's, B's and E's wording is Worker- or lawyer-facing:** put to the user before merge, screened with the BUILT
  code against every detector, rendered for every value class.
- **G's live reads and A's share legislation.gov.uk:** keep the combined rate under the site's fair-use limit
  (1,500 requests per 5 minutes); each at least 0.5 s apart.

---

## Agent A: P3.12 (P1)

**Read first:** P3.12's row in full (Sessions 42-43 and the 2026-10-09 note); `notes/batch11_A.md`; the gitignored
`evidence/rubrics/handread_wave4_b11_sweep.md`; `schedule_units.py`, `agent_shared.schedule_route_block`;
`citation_links.py` (P3.13's answer-seam pattern); `DEPTH_TRUTH["6335"]`.

**Measure first ($0):** the integrator draws the seam at the start and relays the result; until then, compare the
three `wave4_b11_sweep` turn-7 payloads with A's r2-brief payload (the brief, the block, the rounds after it, the
Worker's output budget), and size the wrong-pinpoint rate across every stored 6335 turn 7 (by hand). **Probe the
exact-paragraph route (if live reads were agreed, up to 20, at least 0.5 s apart, logged):** does legislation.gov.uk
serve the row's schedule paragraphs singly (`.../schedule/<n>/paragraph/<m>/data.xml`), with their own numbers and
text, and does LEX's proxy return them unchanged? On how many stored schedule-paragraph requests would the route
hand over exactly the paragraphs asked for? **Build** only the candidate the seam result points at; its wording to
the user before merge; tests and mutants as the rules require.

## Agent B: P3.10 (P2)

**Read first:** P3.10's row in full (Session 43's result and decision); `notes/batch11_E.md`; `_build_step_brief`;
batch 11 E's `dryrun_p310`, grading script and scripts `evidence/scripts/p310_*.json`.

**Build:** the line on every step 2+ (drop the regex gate; keep the lookup exclusion and the caps). Dry-run it over
every stored step 2+ with the BUILT code and list every brief that moves (ids only). Tests and mutants for the
removed gate's replacement. **Price** 6374 n=3 from `wave4_b11_sweep` (stored reps cost about 1.35 times their
stored turn 4; the per-command `--max-spend` stops a command between reps).

## Agent C: P3.20 (P2)

**Read first:** P3.20's and P5.2's rows in full (the design decided in Session 43); `notes/batch11_D.md` section 5;
`docs/LEGAL_DATA_SOURCES.md` section 3; `caselaw.py`; `test_case_law_gap.py` and every gated wording site; the
`external-apis` skill; `CACHEABLE_TOOLS`.

**Build** to the design on the row: two lists in `search_case_law`, the any-term fallback, `AdditionalDate` as the
date of decision, the per-request cap and concurrency limit, the PDF text without pypdf, the gated wording (screened
against every detector, keeping what SCTS does not hold), the grader as its own `replay_report` subcommand.
**Live SCTS calls only to confirm response shapes, if agreed: up to 40, at least 1 s apart, logged.** Do not edit
`NETWORK_AND_DEPENDENCIES.md` or `test_apis.ps1` (the integrator does, when the whitelist is in place). **Price**
the acceptance (6375 n=3 and 6370, 6380 n=1).

## Agent D: P4.3's lever R, P4.23, P4.24 and the routing fix

**Read first:** P4.3's, P4.23's, P4.24's and P4.25's rows in full; `notes/batch11_C.md`; `run_worker_agent`'s
filter and `_source_is_used`; `replay_report rail` and `lookup`; Session 43's decision on `lookup --routing`
(read through `without_handover_line`).

**Measure first ($0):** P4.3's lever R against (iii) over every stored post-P2.1 report turn (0 sources the answer
names removed from the rail), and build it only if the measurement meets the bar; P4.23's code linker (how many
instruments the Manager names without the link the research gave, and what a linker would restore); **P4.24's
bare-id rail entries, and how many are SSIs or UK SIs whose titles the made-under record holds**
(`made_under_instruments.title`, or the census). **Build** the `lookup --routing` fix (deterministic).

## Agent E: P3.22's item 3, P3.4's follow-up, P4.22

**Read first:** P3.22's, P3.4's and P4.22's rows in full; `search_scope.strip_scope_blocks` and its tool-block
pattern; P3.31's blocks (`utils/made_under.made_under_note`, `agent_shared.stored_enabling_note`).

**Measure first ($0):** P3.22's item 3 (an answer naming a leading case not in the National Archives' collection
as if read: every stored instance, by hand); P3.4's research-mode follow-up as its row books it; **P4.22**: every
stored report sentence that names the ENABLING POWER note, and what the strip leaves, now counting P3.31's blocks.
Build P4.22's fix if its measurement is clean (deterministic acceptance over every stored report); the others are
notes.

## Agents F and G: the data-improvement measurements (notes only)

Give each its sections from `DATA_IMPROVEMENT_BATCH_1.md` **verbatim**: F gets its agents A and C; G gets its
agents B and D, **without D's items 3 and 5** (here agent A's and agent D's). Their "What the user has already
decided" and "Where things stand" sections apply. Notes to `notes/batch12_F.md` and `notes/batch12_G.md`.

---

## The integrator (the main session)

1. **Check the state** against "Where things stand"; a baseline full suite on `lexchat_test` (3,017). Copy the
   integrator tools from `evidence/seam/batch11/scratchpad_s43/` and repoint them.
2. **Ask the user once, before launching** (AskUserQuestion, recommendation first, at most four questions): launch
   A to G as set out? The live reads: A up to 20, C up to 40 SCTS, G up to 60 LEX and 200 legislation.gov.uk (all
   free)? P3.12's seam draws now (about $0.20; stop and ask if the first costs over $0.30)? The merge order, and may
   the branch be pushed after each clean merge?
3. **Launch** the agreed agents (`isolation: "worktree"`, one message), each with its section, the verbatim
   sections and lessons, the HEAD sha and whether its live calls were agreed. **P3.12's seam draws right after
   launch**; relay the result to A.
4. **Review each result** as in batches 3-11 (base contained; note and diff read; added lines grepped with
   `review_branch.sh`; for product changes, a revert and at least three mutants of your own, one on a guard; new
   wording screened with the BUILT code; the full suite; a headline number re-run; scratch counts compared).
5. **Merge in order**, each `--no-ff`, the suite after each, pushed if agreed. **The sweeps, each on the user's
   go-ahead and priced first:** P3.10's 6374 n=3 after B; P3.12's 6335 n=3 only if A's candidate is merged; P3.20's
   acceptance after C (and after the target's whitelist only for deployment, not for the dev-machine replay). Grade
   by hand as batch 11 did.
6. **Fold:** tick only rows whose acceptance is met; annotate every row the batch touched (a byte script, each
   anchor once, CRLF kept); **F's and G's results re-slot the data rows on the top order line by measured value**,
   rows failing their drop rule go `[-]` (the user confirms); put every agent's decisions to the user, grouped;
   `plan_lint` 0 errors.
7. **Hand over:** a Session 44 entry and a handover for Session 45 (one session at a time); the memory entry
   `project_prepilot_freeze.md`; the Fix Tracker only if the user asks (v47 is the base).

**Carried, the user's:** SCTS's written confirmation; the SCTS whitelist request; the lawyer pack (P3.2, P3.3,
P3.17); D23; P5.5 (the National Archives' bulk data); deploying `v2026.09.3`; the eval-harness owner (schema v6,
`api_calls`, P4.12's Manager records); D19; the next cut (`v2026.10.1`); Tesseract (P3.35).
