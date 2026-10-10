# Parallel batch 13: the two P1 rows, P3.38's build and the measured P2/P3 rows

**Set up on 2026-10-09 for Session 45, at the end of Session 44 (the user's request: "provide a prompt to kick off
the next piece of work in the plan").** One session works the branch at a time. It follows batches 1-12: agents in
git worktrees, the main session integrating, nothing merged that the integrator has not re-checked. **Every agent is
$0 in model spend.** Live reads only where an agent's section says so and the user agrees at launch. **The paid
steps are the integrator's alone, each priced to the user first and run only on the user's go-ahead.**

**Each agent is given its own section, plus, verbatim from `PARALLEL_BATCH_11.md`, its sections "Rules for every
agent", "Lessons from batches 1-10" and "Shared setup", with these substitutions:** "batch 11" reads "batch 13";
notes go to `docs/prepilot-fixes/notes/batch13_<A-G>.md`; scratch to the gitignored
`docs/prepilot-fixes/evidence/seam/batch13/<letter>/`; test databases `lexchat_test_<a-g>` (all seven exist); rule 1's
reading runs from "Session 44 — 2026-10-09" to the end of `SESSION_LOG.md`, and the batch 12 notes the agent's
section names. **Plus "Lessons added since batch 11" from `PARALLEL_BATCH_12.md` and the lessons below, verbatim.**
Session 44 generated exactly this set for batch 12 with `evidence/seam/batch12/scratchpad_s44/mkcommon.py` (it
writes the files to `evidence/seam/batch12/briefs/`, which each agent then read in full): copy it, change the
substitutions and the output folder to `batch13`, and keep the agents' prompts short (own section inline, the rest by
file path).

## Lessons added since batch 12 (give these verbatim with each brief)

- **Draw a Worker-facing lever at `seam_replay worker --as-sent --at-rev recorded --date recorded --max-tokens
  32000`.** In batch 12 the default composition seam did not reproduce P3.12's live shortfall (0 of 4 payloads);
  `--as-sent` did (2 of 3). Identical payloads can return byte-identical draws (provider reuse): count distinct
  answers, not draws.
- **A mutant harness that names a test file that does not exist reports every mutant CAUGHT** (pytest exits
  non-zero on the missing path). Run the control first and check it passes before reading any verdict.
- **`get_legislation_text` keeps the body in `full_text`; `legislation.text` is always empty.** A grader or scan that
  reads `text` sees every stored read as empty (batch 12 F's first pass).
- **Two agents wrapped the same call in batch 12** (A's handed-paragraph recorder and D's lookup-title wrapper,
  both around `run_worker_tool` in `run_worker_agent`). Name every function you change in your note, and keep your
  change out of a function another agent's section names unless the brief says otherwise.
- **A dropped FIX_PLAN row in a bucket keeps the bucket open** (`plan_status.bucket_state`); the integrator moves it
  to the no-bucket line. Agents never edit FIX_PLAN.
- **The answer seam now runs, in order: P3.13's `restore_dropped_siblings`, P3.12's `restore_dropped_paragraphs`
  (with `misattributed_paragraphs` logging), then P4.3's lever R (`readmit_answer_sources`) and P4.24's
  `title_rail_sources`.** A change at the answer seam lists where it sits in that order and what each step before
  and after it reads.

**What the user has already decided (do not re-open):**
1. **By severity**, unless a dependency prevents it. FIX_PLAN's top order line ("end of Session 44") is the order.
2. **P3.45 (P1):** a new row; its first lever is code that drops or flags a case citation a summary carries and its
   raw source does not. Measure first.
3. **P3.12 (P1):** the lever is code lines at the answer seam (P3.13's pattern; option B, the heading and opening
   operative sub-paragraphs within 450 characters, at most 3 lines; the "Also in ..." template; a wrong pinpoint
   logged only; the conversational Manager seam only). Next, in order: skip an application line that carries
   conditions (the 44(1) case) as well as a bare one; then the sub-paragraph line for a partly cited paragraph,
   measured first; hand over the paragraphs that cut when another named one fails (the "para 43, 130" misread);
   widen `depth`'s paragraph-42 pattern to "wind up"; then 6335 n=3. The Worker-prompt sentence W1 was not taken.
4. **P3.38 (P2), GO:** trigger on not held, held without text and an empty text read; read through LEX's
   `/legislation/proxy` (no whitelist entry); live, never cached. Its acceptance turns are on its row.
5. **P4.23 (P2):** link a plain-words instrument mention to the report's instrument URL, and a provision URL only
   where the answer names that provision beside the title, with batch 12 D's guards.
6. **P3.46 (P2):** a code note in `search_case_law`'s result when a case the query names is not returned (wording
   to the user); teach `replay_report authorities` the first-statement rule and the "this principle" back-reference.
7. **P3.28 then P3.26 then P3.33:** P3.28 classifies by effect type and says "no longer in force" only of whole or
   partial provision removals; words-only removals are their own class, stated as "text amended"; qualified ones
   apart; the feed route is struck. P3.26 treats an unrecognised extent token as unknown and adds "N.I.". P3.33
   waits for P3.28.
8. **P3.34:** re-scoped to definition-list questions; measure a corpus-wide definition search first.
9. **Agents propose; the integrator applies; the user approves anything not mechanical**, including any wording a
   lawyer or the Worker will read. Never merge or push to `main`. The Fix Tracker only when the user asks.

---

## Where things stand (verified 2026-10-09, evening, end of Session 44)

- Branch `fix/prepilot-defects` at this file's commit or later, pushed; `main` at `a6b4a76` (`v2026.09.3`).
- `plan_status`: **67 of 101 rows, 1 in progress (P3.12), 9 of 14 buckets**; `plan_lint` 0 errors, 0 warnings.
- **3,379 tests**; **70 replay directories** (batch 12 added `wave4_b12_p310`, `_p320`, `_p34r`, `_p312`).
- Fix Tracker **v48** (published at the end of Session 44).
- Machine: no server, no pin file, no replay running; the dev `server_py/.env` has no `SCTS_CASELAW_ENABLED` (P3.20
  is off); the seven batch 12 worktrees under `.claude/worktrees/` are merged (removable).
- Batch 12's material: notes `docs/prepilot-fixes/notes/batch12_{A..G}.md`; scratch
  `evidence/seam/batch12/{A..G}/`; the integrator's draws and grades `evidence/seam/batch12/integrator/`; its scripts
  (mutants, fold, tracker, decision record `s44_decisions.md`) `evidence/seam/batch12/scratchpad_s44/`; the hand-reads
  behind every Session 44 number `evidence/rubrics/handread_batch12.md` (all gitignored).

---

## The batch

| Agent | Row (tracker severity) | Work | Kind | Live calls | Main files |
|---|---|---|---|---|---|
| **A** | **P3.45** (P1) | Measure the invented case citations over every stored summary, then build the code check | measurement, then product | none | `summarisation.py` (the summary return seam), a new util, tests |
| **B** | **P3.12** (P1) | The excerpt's application-line rule; the sub-paragraph line (measured first); the cut-what-cuts fix; `depth`'s pattern | product + grader | none | `utils/paragraph_restore.py`, `utils/schedule_units.py`, `tools/replay_report.py` (`depth` only), tests |
| **C** | **P3.38** (P2) | Read a not-held or text-less instrument from legislation.gov.uk through LEX's proxy | product | up to 40 LEX proxy calls, if agreed | a new tool module or `agent/tools/lex.py`, `executor.py`, `schemas.py`, the scope wording, tests |
| **D** | **P4.23** (P2) | The answer-seam linker, as decided | product | none | `citation_links.py`, `agent_core.process_user_request`'s answer seam, tests |
| **E** | **P3.46** (P2) | The not-returned-case note in `search_case_law`; the `authorities` grader | product + grader | none | `agent/tools/caselaw.py` (not `scts.py`), `tools/replay_report.py` (`authorities` only), tests |
| **F** | **P3.28** then **P3.26** (P3) | Removals classified by effect type, with the wording; the extent filter's unknown token and "N.I." | product | none | `agent/tools/lex.py` (`_slim_amendment_results`), `utils/search_scope.py` (`_currency_limb`, the extent rule), tests |
| **G** | **P3.34** (P2) | Measure a corpus-wide definition search (notes only) | measurement | up to 30 LEX calls, if agreed | the export, replays, live LEX |

**Why these seven.** P3.45 and P3.12 are the two open P1 rows not Blocked. P3.38, P4.23, P3.46 and P3.34 are the P2
rows with decided next steps. P3.28 and P3.26 are P3 on the tracker but were measured and decided in batch 12 and
share no files with the rest. **Not in this batch:** P3.33 (waits for P3.28), the other P3 rows, anything Blocked.

**Merge order: A, B (P1 first), then C, D, E, F, G.** B and D both touch the answer seam in
`process_user_request`: B changes `paragraph_restore.py` only (no wiring change unless its section says so), D adds
its linker after P3.13's restore; the integrator merges B before D and re-runs both suites. **Never commit while a
replay runs.**

**Collision points.**
- **`process_user_request`'s answer seam:** B (no wiring change expected) and D (the linker). D names the exact
  position it chose.
- **`tools/replay_report.py`:** B (`depth`), E (`authorities`): different subcommands.
- **`search_scope.py`:** F (`_currency_limb`, the extent rule) and C (C's scope wording, if any): different functions.
- **`executor.py` / `schemas.py`:** C only.
- **Wording to the user before merge:** A's flag (if any text reaches a lawyer or the Worker), C's tool-result and
  scope wording, E's note, F's "text amended" and removal wording. Screen each with the BUILT code against every
  detector and render it for every value class.

---

## Agent A: P3.45 (P1)

**Read first:** P3.45's row; `notes/batch12_E.md` (the summariser-citation finding); batch 12 E's scripts
`evidence/seam/batch12/E/p322_summariser_citations.py`, `p322_summariser_classify.py`, `p322_summariser_ctx.py` and
their outputs; `summarisation.py` (`summarise_for_query` and where its result is returned); P3.16's row (the
summariser's glosses, the pattern of a code check against the raw text); `CACHEABLE_TOOLS` and the local prompt
cache (a cached summary must not bypass the check).

**Measure first ($0):** every stored summarised result (`summarised: true`, raw against final) over every replay
directory (say how many): each case citation in the summary (neutral citations, report citations, "X v Y" names)
that the raw source lacks; classify by hand a sample and every one that reached an answer (where, which session).
Validate the detector both ways (a citation present in the raw text in another form must not count). **Build** the
code check at the summary seam (drop the citation, or flag it, whichever the measurement supports; your
recommendation and the options to the user), fail-soft; tests, revert proof and a mutant per guard; dry-run it over
every stored summary and list every one that moves. **Price** an acceptance (a seam re-summarise with
`tools.summary_probe` if it can show the effect; otherwise the replay sessions the finding came from).

## Agent B: P3.12 (P1)

**Read first:** P3.12's row in full (Session 44's annotation); `notes/batch12_A.md` (sections 12 and 13);
`evidence/rubrics/handread_batch12.md` (the P3.12 sections); `utils/paragraph_restore.py`, `utils/schedule_units.py`;
batch 12 A's scratch `evidence/seam/batch12/A/` (`proto_subs.py`, the sub-paragraph prototype that took 2 of 4 stored
answers to DELIVERED; `wind_up_grader.py`; `dryrun_restore.py`; `para_requests.py`); `DEPTH_TRUTH["6335"]`.

**Build, in order, each dry-run with the BUILT code over every stored answer it could touch:**
1. `excerpt`: skip an application line that carries conditions (a sub-paragraph opening "This paragraph applies
   where ..." with lettered conditions) as well as a bare one, so 44's line quotes the operative sub-paragraph
   (44(5)); list every stored line that changes.
2. The sub-paragraph line for a paragraph the answer cites only in part, measured first (how many stored answers it
   moves, and what it adds); bounded like the paragraph line.
3. Hand over the paragraphs that cut when another named one fails (`cut_pieces`' all-or-nothing summary; the "para
   43, 130" misread of a section number as a paragraph).
4. Widen `replay_report depth`'s paragraph-42 pattern to "wind up" (moves 1 of 48 stored texts, to the hand verdict).

Wording (the line's template is unchanged; any new text) to the user before merge. Tests, revert proof, a mutant per
guard. **Price** 6335 n=3 (about $1.80 from `wave4_b12_p312`).

## Agent C: P3.38 (P2)

**Read first:** P3.38's row in full (Session 44's annotation: the trigger, the acceptance turns, the regnal-id 404,
the exact-paragraph route); `notes/batch12_F.md` (P3.38 section) and F's scratch `evidence/seam/batch12/F/`
(`p338_scan.py`, `p338_table.py`, `held_index.py`, `census.py`); P3.7's lookup statuses (`utils/instrument_lookup.py`);
P3.21's proxy route (`agent/tools/commencement_dates.py`: the encoded path, the timeouts, the memo); P3.31's
introduction-file reader (`tools/madeunder_probe.py`) and its census; the `external-apis` skill (legislation.gov.uk
routes); `CACHEABLE_TOOLS`.

**Build** the read: when a lookup says not held or held without text, or a text read comes back empty, fetch the
instrument's text from legislation.gov.uk through `GET /legislation/proxy/<encoded path>` (made version, and its
schedules), live and never cached, bounded (pages, seconds, calls per request), fail-soft, with a code-written line
saying where the text came from and that the index does not hold it. Decide with the user how the text reaches the
Worker (a tool result or a block; size limits). **Live calls only to confirm shapes, if agreed: up to 40, at least
0.5 s apart, logged.** Tests, mutants, the wording screened. **Price** the acceptance on the row's turns with its
controls.

## Agent D: P4.23 (P2)

**Read first:** P4.23's row in full (the decided lever); `notes/batch12_D.md` (the P4.23 measurement and the guards);
D's scratch `evidence/seam/batch12/D/` (`p423.py`, `count423.py`, `show423.py`); `citation_links.py`
(`link_sibling_pinpoints`, `restore_dropped_siblings`, `_MD_LINK`); the answer seam in `process_user_request`.

**Build** the linker as decided, with the guards (quotation and code spans; nested-bracket case labels; never an
instrument mention to one provision's URL), at the conversational Manager's answer seam; say where it sits relative
to P3.13's and P3.12's restores and P4.3's lever R. Dry-run it with the BUILT code over every stored Conversational
report turn: list every link it adds (74 in 67 turns expected from the prototype) and every guard drop. Tests,
mutants. **Price** an acceptance (the sessions with the most restored links, n=3).

## Agent E: P3.46 (P2)

**Read first:** P3.46's row; P3.22's row (items 1, 2 and 4 met); `notes/batch12_E.md` (the item 3 hand-read) and
E's scratch `evidence/seam/batch12/E/` (`p322_item3_dump.py`, `p322_named_case_queries.py`, `p322_provenance*.py`);
`caselaw.py` (`search_case_law`'s result and window notes; `scts.py` is P3.20's and stays untouched);
`replay_report authorities`.

**Build** the note: when a `search_case_law` query names a case (by name or citation) and the results do not return
it, a code-written line in the tool result saying so (that it was not returned, which is not proof it does not exist
or is not in the collection), wording to the user, screened against every detector. **Grader:** teach `authorities`
the first-statement rule and the "this principle" back-reference, validated against E's hand-read (9 of 25 fail by
hand; the grader found 6, wrong both ways). Tests, mutants. **Price** 6359 and 6363 n=3.

## Agent F: P3.28, then P3.26 (P3)

**Read first:** P3.28's and P3.26's rows in full (Session 44's annotations); `notes/batch12_G.md` (P3.28 and P3.26
sections) and G's scratch `evidence/seam/batch12/G/` (`p328_vocab.py` for the effect-type vocabulary,
`p328_class.py`, `p328_count.py`, `p328_negs.py` for the 12 false negatives, `p342_filtered.py` for the "N.I." case);
`lex.py` `_slim_amendment_results`; `search_scope._currency_limb` and P3.24's commencement wording (do not break it);
P1.1's "applies in" rule.

**Build P3.28:** classify every relation by effect type (whole or partial provision removal; words-only, "text
amended"; qualified: prospective, temporary, conditional; non-removal), and word the counts so "no longer in force"
is said only of whole or partial removals. Every other code text about the same instrument checked against it (the
batch 8 lesson). Dry run over every stored change record: every count that moves, and the 12 false-negative
sentences' inputs. **Then P3.26:** an unrecognised extent token is unknown, not dropped; "N.I." is Northern Ireland.
Wording to the user; tests, mutants. **Price** P3.28's acceptance (6375 t2, scripted 6406 t1, scripted 6383 t1).

## Agent G: P3.34 (P2, notes only)

**Read first:** P3.34's row (re-scoped); `notes/batch12_F.md` (P3.34 section) and F's `p334_defs.py`,
`p334_lists.py`; `docs/api/LexAPISpec.md` (section search with `legislation_id` optional); the `external-apis` skill.

**Measure (live LEX calls only if agreed: up to 30, at least 0.5 s apart, logged):** does `search_legislation_sections`
without a `legislation_id` search the corpus; on the 9 definition-list turns (6341 t2-t7, 6384 t1 and t4, 6363 t1),
how many of the defining instruments the stored runs found (29 across 19 runs on 6341 t7) a corpus-wide query returns,
and at what precision. **Propose:** go or no-go, the lever (a tool, a query form, or an index) and its acceptance.

---

## The integrator (the main session)

1. **Check the state** against "Where things stand"; a baseline full suite on `lexchat_test` (3,379). Copy the
   integrator tools from `evidence/seam/batch12/scratchpad_s44/` (`review_branch.sh`, `matter_grep.py`,
   `keep_awake.py`, the `mut*.py` pattern, `fold_s44.py`, `tracker_v48.py`) to the session scratchpad and repoint
   their paths (the scratchpad path and `BASE`).
2. **Ask the user once, before launching** (AskUserQuestion, recommendation first, at most four questions): launch
   A to G as set out? The live reads (C up to 40 LEX proxy, G up to 30 LEX; free)? The merge order, and may the
   branch be pushed after each clean merge?
3. **Launch** the agreed agents (`isolation: "worktree"`, background, one message), each with its section inline, the
   HEAD sha, its test database, whether its live calls were agreed, and the generated common files by path. Every
   worktree has come up on `main`: each agent resets to the HEAD first.
4. **Review each result** as in batches 3-12: base contained; note and diff read; added lines grepped
   (`review_branch.sh`); for product changes, a revert and at least three mutants of your own, one on every guard
   (check the control passes first); new wording screened with the BUILT code; the full suite; a headline number
   re-run; scratch counts compared.
5. **Merge in order**, each `--no-ff`, the suite after each, pushed if agreed. **The paid steps, each priced to the
   user first:** B's 6335 n=3 (about $1.80); C's, D's, E's and F's acceptances as priced; A's if any. Replays:
   `replay check`, `replay pin`, uvicorn by PowerShell `Start-Process -PassThru` (from `server_py/`, `--port 8000`)
   with the keep-awake helper, `replay run --session S --reps N` or `--script <evidence/scripts/...json>` with
   `--max-spend` per command, then `replay restore` and both processes stopped by PID. Grade by hand, write the
   hand-reads to the gitignored `evidence/rubrics/handread_batch13.md`.
6. **Fold** (a byte script like `fold_s44.py`; LF kept, as FIX_PLAN and SESSION_LOG are LF): tick only rows whose
   acceptance is met; annotate every row the batch touched; new rows for new findings; `plan_lint` 0 errors and 0
   warnings (the top line states its rows and buckets counts).
7. **Hand over:** a Session 45 entry and a handover for Session 46; CHANGELOG *Unreleased* and CLAUDE.md's Worker
   notes for every built row; the memory entry `project_prepilot_freeze.md`; the Fix Tracker only if the user asks
   (v48 is the base).

**Carried, the user's:** the SCTS whitelist request (P3.20 built, off until both hosts are whitelisted; then
`NETWORK_AND_DEPENDENCIES.md`, `test_apis.ps1`, the offline bundle's pdfplumber) and SCTS's written confirmation;
the lawyer pack (P3.2, P3.3, P3.17); D23; P5.5; deploying `v2026.09.3`; the eval-harness owner; D19; the next cut
(`v2026.10.1`, which would carry P3.31, P4.12 and batch 12's six rows); Tesseract (P3.35); **P3.12's tracker severity
(P2 on the tracker, P1 in the briefs since batch 11: the user's call)**.
