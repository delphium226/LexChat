# Data-improvement batch 1: size every "measure first" data improvement in one pass

> **MERGED INTO `PARALLEL_BATCH_12.md` (2026-10-09, user decision): do not run this file on its own.** Its agents A and C are batch 12's agent F; its agents B and D are batch 12's agent G (D's item 3 is batch 12's agent A, D's item 5 batch 12's agent D). Its sections are given verbatim from here.

**Set up on 2026-10-09, at the user's request** ("is it worth re-planning with the data improvements in mind?"
... "yes"), after P3.31 (the made-under record) was built and the data-improvement rows P3.32 to P3.44 were
booked. It follows the parallel-batch pattern (`PARALLEL_BATCH_1.md` to `_11.md`): agents in git worktrees, the
main session integrating. **It is a measurement batch: no agent writes product code, every agent writes a note,
and the integrator folds the results into the rows.** So it touches nothing a defect batch builds, and can run
beside one.

**Every agent is $0 in model spend.** Two agents (B and D) may make free, bounded live reads **only if the user
agrees at launch**: B up to 60 LEX calls, D up to 200 legislation.gov.uk reads. Nothing else calls out.

This file is the brief. The integrator reads it whole. Each agent is given its own section, plus, **verbatim from
`PARALLEL_BATCH_11.md`**, its sections **Rules for every agent**, **Lessons from batches 1-10** and **Shared
setup**, with these substitutions: notes go to `docs/prepilot-fixes/notes/dibatch1_<A|B|C|D>.md`; scratch to the
gitignored `docs/prepilot-fixes/evidence/seam/dibatch1/<letter>/`; test databases `lexchat_test_<a|b|c|d>`;
"batch 11" reads "data-improvement batch 1" throughout. Matter-specific detail stays in the gitignored evidence.

**What the user has already decided (do not re-open):**
1. **Work is taken by severity** unless a dependency prevents it. This batch does not re-order the defect queue:
   it sizes the data-improvement rows so they can be slotted on measured value (FIX_PLAN's current top order line).
2. **Data routes that are levers for open defect rows come in at those rows' severity**, not in the data queue:
   P3.12's exact-paragraph fetch, P3.28's removal count by effect type, P4.24's titles from the made-under record
   (each noted on its row, 2026-10-09). This batch measures them; the defect rows' own batches build them.
3. **P3.32, P3.33 and P3.42 would share one harvest pass** (the introduction and body XML P3.31's harvester reads).
   Whether to build any of them waits on this batch's numbers.
4. **P3.35 and P3.36 are Blocked** (P5.5's bulk data or an OCR decision; a National Archives licence) and **P3.37
   is not recommended now**: none is in this batch.
5. **Agents propose; the integrator applies; the user approves anything not mechanical.** No agent edits FIX_PLAN.md,
   SESSION_LOG.md, `summary-table.html`, `docs/LEGAL_DATA_SOURCES.md`, any batch brief, a rubric or a memory file.
6. **Never merge or push to `main`.** The Fix Tracker is updated only when the user asks.

---

## Where things stand (verified 2026-10-09, afternoon)

- Branch `fix/prepilot-defects`, HEAD `e33ac01` or later (Session 43 commits to the same branch: check `git log`).
- `plan_status`: 61 of 97 rows, 4 in progress, 9 of 14 buckets closed. `plan_lint` exit 0.
- **The made-under record** (P3.31): `server_py/data/made_under/` (snapshot `2026-10-09.1`, 86,744 instruments, SSIs
  1999-2026 and UK SIs 1987-2026, 68,780 with parsed powers). The harvest files are the gitignored
  `docs/prepilot-fixes/evidence/madeunder/*_snap.jsonl` (one JSON line per number tried: `id`, `title`, `version`,
  `preamble`, `window`, `powers`, `flags`, or `absent`), with `.titles.json` caches. **They are a census of which
  SSIs and UK SIs legislation.gov.uk publishes with text**: use them, not live calls, for "does legislation.gov.uk
  hold X" for those two series. The tool is `python -m tools.madeunder_probe` (`--made`, `--reverse`, `--loose`).
- The pre-pilot export (62 sessions, 196 user turns) is at
  `C:/Temp/aila-prepilot/pre-pilot sessions/session-transcripts-all-time-2026-09-14.csv` (never commit its text).
- The stored replays are under `$PREPILOT_EVIDENCE/replay/` (about 70 directories; say which you counted).

---

## The batch

| Agent | Rows | Measures | Live calls | Main inputs |
|---|---|---|---|---|
| **A** | **P3.38**, **P3.39** (P2) | Not-held instruments legislation.gov.uk holds; questions about the law at a past date | none | export, replays, the harvest census |
| **B** | **P3.41** (P2), **P3.28** (P3) | Provision-level amendment questions; removals counted by effect type | up to 60 LEX, if agreed | replays (`get_legislation_changes` raw results, P3.21's stored feeds) |
| **C** | **P3.34** (P2), **P3.43** (P3) | Definition questions (B11); guidance and code-of-practice questions | none | export, replays, B11's sessions |
| **D** | **P3.32**, **P3.33**, **P3.42** + **P3.26** (P2/P3); **P3.12**'s paragraph route; **P3.30**, **P4.24** | The shared harvest's fields; extent per provision; the exact-paragraph route; how often P3.30's and P4.24's gaps occur | up to 200 legislation.gov.uk, if agreed | live samples; replays; the harvest census |

**No merge order is needed: every agent commits only its note** (and gitignored scratch). Check each branch's diff
touches nothing under `server_py/` before folding.

---

## Agent A: P3.38 and P3.39 measured ($0, no external call)

**Read first:** P3.38's, P3.39's, P3.7's, P2.2's and P5.3's rows in full; P5.4's (now ticked) for leads (b) and the
coverage findings; `utils/instrument_lookup.py` (the statuses) and `search_scope`'s not-held clauses.

**Measure:**
1. **P3.38.** Over the export and every stored replay directory (say how many), every turn where the answer or a
   tool said an instrument is not held (a `lookup_legislation` `not_held` / `held_without_text`, a P2.2 "not found"
   about a named instrument, a scope line naming it). For each: the instrument's series and year; **whether
   legislation.gov.uk publishes it with text** (the harvest census for SSIs and UK SIs; for other series, say it is
   unknown, do not call out); and what the lawyer needed from it (its text, a provision, its date, what it was made
   under). Read every one you count. Report: how many turns a legislation.gov.uk read would have changed, and of
   those how many are already met by P3.31's forward route (its recital alone).
2. **P3.39.** Every user turn asking for the law at a past date, before or after an amendment, or "as enacted" /
   "as originally made". For each, what the answer did (current text, a refusal, the change record). Read every one.
3. **Propose:** for each row, the measured count, a go/no-go against the row's drop rule, and the acceptance turns
   if go (from the export or stored runs, ids only).

## Agent B: P3.41 and P3.28 measured ($0; up to 60 LEX calls if agreed)

**Read first:** P3.41's, P3.28's, P3.5's, P3.19's and P3.21's rows in full; `lex.py` `_slim_amendment_results`
and its traps; the `external-apis` skill on `/amendment/section/search` (exact-address matching; null changed
provisions reachable only from the affecting side); `commencement_dates.py` (the effects feed parse).

**Measure:**
1. **P3.41.** Every turn asking what amended, repealed or commenced a *specific provision* (a section or
   subsection, not the Act). For each, what the instrument-level change record returned and what the answer said
   about that provision; read every one.
2. **If live calls were agreed:** for up to 20 of those provisions, `/amendment/section/search` on the exact
   provision addresses (from `fetch_provision_list`'s shapes in the stored runs) against the instrument-level
   rows: does it add, lose or contradict anything? Through a capped, logged door (batch 10 B's `tna_b10.py` is the
   pattern), at least 0.5 s apart.
3. **P3.28.** Over every stored P3.21 effects feed and `get_legislation_changes` raw result: count removals by
   the feed's effect type ("repealed", "revoked", "omitted", "words omitted", "ceases to have effect", and every
   other removal-like type you find: list them) against the product's current wording match; list every disagreement.
4. **Propose:** counts, go/no-go, and P3.28's lever (effect type, wording, or both) with what it moves.

## Agent C: P3.34 and P3.43 measured ($0, no external call)

**Read first:** P3.34's, P3.43's, P3.3's, P3.16's and P3.17's rows in full (P3.3 and P3.17 are Blocked on the
lawyer pack: do not re-litigate their readings); `classification.json`'s B11 sessions.

**Measure:**
1. **P3.34.** Every turn whose question or failure turns on a defined term (a definition in the same instrument,
   one borrowed from another, or an interpretation Act). For each, classify: (a) the definition was retrieved and
   used; (b) retrieved and misread (reasoning, not data); (c) in another instrument retrieval never reached (the
   data case P3.34 serves). Read every one. **The row's drop rule turns on (c).**
2. **P3.43.** Every user turn asking for statutory guidance, a code of practice, directions or a circular made or
   issued under a provision, in the export and the replays. Count, and for each what the answer did.
3. **Propose:** counts, go/no-go for each, and for P3.43 (if go) the candidate source and its terms to be checked
   (no call out).

## Agent D: the shared harvest, extent, the paragraph route, and two record-backed gaps ($0; up to 200 legislation.gov.uk reads if agreed)

**Read first:** P3.32's, P3.33's, P3.42's, P3.26's, P3.12's, P3.30's and P4.24's rows in full (each has a
2026-10-09 note); `tools/madeunder_probe.py` (`fetch_record`, the introduction view, the paced client);
`services/made_under_store.py`; `utils/search_scope.py`'s extent handling (P1.1's "applies in" rule).

**Measure (live reads only if agreed: direct to `www.legislation.gov.uk`, through `madeunder_probe`'s
`PacedClient` with its User-Agent, at least 0.5 s apart, capped in code, every call logged):**
1. **P3.32 / P3.33, the shared pass.** On a stratified sample (say 60: SSIs and UK SIs, three eras), which fields
   the `/introduction/made/data.xml` view carries: made, laid and coming-into-force dates (element names and
   formats), a procedure signal (the preamble's "approved by resolution" / "laid before"), consultation clauses,
   extent; and what P3.33's revocation flag needs (the effects feed, or LEX's change record; how many calls a pass
   over 86,744 instruments would take). Propose the single harvest pass: fields, calls, hours.
2. **P3.42 + P3.26.** For 20 UK Acts often asked about (from the stored turns), per-provision `RestrictExtent`
   from legislation.gov.uk against LEX's instrument-level extent: how often a provision differs from its Act, and
   every extent value seen (P3.26's vocabulary). Count the stored turns whose jurisdiction would have turned on it.
3. **P3.12's paragraph route.** For the schedule in P3.12's row, whether legislation.gov.uk serves single
   paragraphs (`.../schedule/<n>/paragraph/<m>/data.xml`) through LEX's proxy unchanged (one proxy call against
   one direct read), with their own numbers and text; and on how many of the stored schedule-paragraph requests
   (P3.12's dry runs) the route would hand over exactly the paragraphs asked for. **No product code**; the result
   goes on P3.12's row for its next lever choice.
4. **P3.30.** Over the stored runs: how often a search-result row is the only route by which a cited SI's
   derivation reached the Worker, now that the made-under record supplies text reads, section searches and lookups
   (count with the record's coverage, the harvest census).
5. **P4.24.** Over the stored rail entries: how many bare-id entries are SSIs or UK SIs the record titles.
6. **Propose:** for each, the count, go/no-go, and the lever or harvest it supports.

---

## The integrator (the main session)

1. **Check the state** (as above); nothing running; a baseline full suite on `lexchat_test`. Note Session 43's
   last commit: if a defect batch is running, this batch may run beside it (notes only), but **never commit while a
   replay runs**.
2. **Ask the user once, before launching** (AskUserQuestion, recommendation first): launch A, B, C and D? May B
   make up to 60 LEX calls and D up to 200 legislation.gov.uk reads (both free; the alternative is stored evidence
   only, and say what each then cannot check)?
3. **Launch** the agreed agents as background agents with `isolation: "worktree"`, in one message, each with its
   section, the three verbatim sections from `PARALLEL_BATCH_11.md` with this file's substitutions, the HEAD sha,
   and whether its live calls were agreed.
4. **Review each note as it lands:** the branch contains the HEAD; the diff touches only its note; grep the added
   lines for matter text (`review_branch.sh`); re-run one headline count on the main checkout; read every
   classification the go/no-go rests on.
5. **Fold:** annotate each row with its measured count and go/no-go (a byte script, each anchor once, CRLF kept);
   rows that fail their drop rule go `[-]` with the reason (the user confirms); put each go row's proposed acceptance
   and lever to the user (AskUserQuestion, grouped); then **re-slot the go rows on the top order line by measured
   value** within the by-severity order, and record P3.12's, P3.28's and P4.24's routes on those rows for their own
   batches. `plan_lint` 0 errors.
6. **Hand over:** a dated SESSION_LOG entry; update the Fix Tracker only if the user asks.
