# Parallel batch 1 — four agents on the open rows, one integrator

**Decided by the user, 2026-09-29 (end of Session 32).** The next piece of the fix plan is run by
parallel coding agents, each in its own git worktree, with the main session as the integrator. The
principle is **parallelise the free and cheap work, serialise the expensive work**: unit tests,
graders over stored runs and dry runs are free; seam draws cost cents; a replay after-column costs
$15-20 and needs the one server and the one pinned configuration, so only the integrator runs one.

This file is the brief. The integrator reads it whole; each agent is given its own section plus
**Rules for every agent**, verbatim. Nothing here should need re-deriving. If something does, the
agent says so in its note rather than guessing.

---

## The batch

| Agent | Rows | Kind | Budget (paid calls) | Main files |
|---|---|---|---|---|
| **A** | P4.13, P4.14 | deterministic code | $0 | `src/utils/openers.py`, `src/utils/search_scope.py`, `src/agent/agent_core.py` |
| **B** | the grader gaps found in Session 32 | tooling + the gitignored rubrics | $0 | `tools/replay_report.py`, `evidence/rubrics/p32.json`, `p33.json` |
| **C** | P3.16 (the summariser's glosses) | measure free, then seam | $3, stop at $3 | `tools/summary_probe.py`, `src/agent/summarisation.py`, `src/services/local_prompt_cache.py` |
| **D** | P3.18 (the Deep Research synthesis) | seam | $4, stop at $4 | `src/prompts.py` (synthesis prompt; research Worker if needed) |

**Not in this batch:** P3.17 (waits on P3.16: both concern how retrieved text reaches the Worker);
P4.15 (a decision for the user, on its row); P3.2 and P3.3 themselves (they are re-measured by the
integrator's combined after-column, below).

**Budget:** agents at most $7 in all; the integrator's combined after-column about $17-20, **put
to the user with a figure before it is spent**. Session total about $27.

---

## Shared setup (verified 2026-09-29, Session 32)

- **Branch:** `fix/prepilot-defects`, head `20f7b79` or later, pushed; `main` untouched at
  `b2a3fd8`. Never push or merge to `main`.
- **Worktrees:** each agent works in its own worktree (the Agent tool's `isolation: "worktree"`),
  branched from the integrator's HEAD. A worktree has **no `server_py/.env`** and that is fine:
  tests, graders and seam draws were all run from a scratch worktree without one.
- **The evidence is gitignored and exists only in the main checkout**
  (`C:/Projects/LexChat/docs/prepilot-fixes/evidence`: 54 replay directories, `rubrics/`,
  `seam/`, `replay_set.json`). In a worktree, set
  `PREPILOT_EVIDENCE=C:/Projects/LexChat/docs/prepilot-fixes/evidence` on every tool command;
  `replay_report`, `seam_sweep`, `summary_probe` and `replay_set` honour it (unset, they behave
  as before). Pass `--run`, `--dir` and `--also` paths under `$PREPILOT_EVIDENCE/replay/`.
- **Each agent has its own test database.** `tests/conftest.py` drops every table at teardown,
  so two suites on one database break each other. Use
  `TEST_DATABASE_URL=postgresql://lexuser:lexpassword@localhost:5432/lexchat_test_<a|b|c|d>`
  (plain `postgresql://`, not `+asyncpg`; conftest adds the driver). All four exist; two full
  suites ran concurrently on `_a` and `_b` and passed (1983).
- **Seam draws read the OpenRouter key from the dev database** (`app_settings`, read-only) and
  need no server, so agents can draw in parallel. They use the dev box's current model settings
  (`google/gemini-3.1-pro-preview`, summariser `google/gemini-3-flash-preview`), the same the
  replays pin. **No agent starts uvicorn, runs `replay pin`, `replay run` or `replay restore`.**
- **Where draws go:** `$PREPILOT_EVIDENCE/seam/batch1/<agent>/<before|after>/<slot>/`
  (gitignored: draws contain lawyers' matters). Grade composition draws with
  `python -m tools.replay_report --dir <side> interpret --drafts --session <id>`
  (and `--rubric $PREPILOT_EVIDENCE/rubrics/p33.json`).
- **Commands (run from `server_py/`, with `PYTHONIOENCODING=utf-8`; the console is cp1252):**
  `python -m tools.plan_status`; `replay_report` subcommands `interpret [--drafts|--export]`,
  `stance`, `hedges`, `openers [--strip]`, `caselaw`, `negatives`, `modes`, `drgaps`;
  `summary_probe count|redraw|panel`; `seam_replay synthesis|worker|manager --run F --turn N
  [--reps N] [--out D] [--dry-run] [--without-fix --rev SHA]`. `psycopg2` is not installed;
  use `asyncpg` (as `seam_replay` does) if a script needs the database.

---

## Rules for every agent (give these verbatim with each brief)

1. **Read first:** `docs/prepilot-fixes/FIX_PLAN.md` (Invariants 1-6, "Data handling", your
   rows in full), and in `docs/prepilot-fixes/SESSION_LOG.md` the entries "Session 32, continued",
   "Session 32 — handover for Session 33" and the addendum after it. Do not re-derive what they
   establish.
2. **Stay in your worktree and on your files.** Do not edit `FIX_PLAN.md`, `SESSION_LOG.md`,
   `summary-table.html`, `CLAUDE.md` or any memory file: the integrator folds your results in.
   Commit on your worktree's branch; **do not push, do not merge, never touch `main`.**
3. **Write your note** as `docs/prepilot-fixes/notes/batch1_<A|B|C|D>.md` and commit it: what you
   changed and why, every number with the exact command that produces it, every dry-run edit or
   match you read (counts only in the note if the text names a matter), what you did NOT do, and
   anything the integrator must decide. **Before any claim of "fixed", state the row's
   acceptance and whether it is met.**
4. **Measure before building, and list what a change moves.** For any grader or detector, list
   every match and every drop before quoting a rate. For any code rewrite of text, dry-run it over
   every stored answer and read every edit (the P3.13 and Session 32 opener-strip precedent).
5. **Tests:** each product change gets a unit test at its seam, and each test is proven to FAIL
   with the change reverted on a scratch copy (say so in the note). Run the full suite on your
   own test database before your last commit; report the count.
6. **Data handling:** never commit lawyers' question or answer text, search terms, case names, or
   instrument ids and titles from a session. Tests and fixtures use synthetic text ("Widget
   Order 1901"). Grep your staged diff for session ids, instrument ids and matter words before
   every commit. Rubric patterns and draws stay in the gitignored evidence.
7. **Line endings:** tracked files are CRLF in the working tree. The Write tool writes LF;
   Python edits over multi-line text must normalise CRLF to LF before matching and restore CRLF
   on write. **Never run Python with backslashes from a bash heredoc** (it mangles them): use the
   Edit tool, or write the script to a file first. Commit messages go in a file
   (`git commit -F`), ending with the attribution line the harness gives.
8. **Budget:** stop at your figure. `--max-spend` does not exist for seam draws; count the
   printed costs. Temperature 0 is not byte-deterministic: redraw a flagged payload 2-3 times a
   side and draw both sides of an A/B **the same day**.
9. **When you finish, reply with:** your branch name, the commit list, the test count, the
   spend, and the path of your note.

---

## Agent A — P4.13 and P4.14 (deterministic code, $0)

**P4.13, the opener strip's coverage** (`src/utils/openers.py`, `_FORMULAS`). The `bare`
formula's object list covers `this|that|me|the point` after "right/correct to challenge"; a
Manager answer in `wave4_p33_post` p32_6406 r1 (run-file turn 8) opened with the formula whose
object was "my earlier statement", and the strip left it. Widen it to "my (earlier, previous,
last, original) (statement, answer, response, reply, position, assessment)", and consider the
same objects after the `thanks` formula ("Thank you for challenging my earlier answer").
Scoped agreement ("You are correct that X") and a plain "Yes, that is correct." stay untouched
(the module docstring says why). **Measure:**
`python -m tools.replay_report --dir $PREPILOT_EVIDENCE/replay/baseline openers --all-dirs --export --strip`
before and after (46 edits and 8 left as written at `20f7b79`); list and read every NEW edit.
**Acceptance (the row):** deterministic; every new edit read and correct, a test per new form,
each failing with the change reverted.

**P4.14, a footer the model echoed is not stripped when P1.6's link note follows it.** In the
Manager path of `src/agent/agent_core.py`: `enforce_provision_links(clean, retrieved_urls)`
(near line 966) can append a "† No provision-level URL was returned ..." note AFTER the model's
text; later `final["content"] = strip_answer_footer(...) + _footer` (near line 1086).
`strip_answer_footer` (`src/utils/search_scope.py`, `_ECHOED_FOOTER` near line 1936) removes
only a TRAILING echoed `*Search scope:*` line, so an echo followed by the † note survives and
the lawyer sees two scope lines. Seen in `wave4_p33_post` 6338_rep2 turn 2 and 6345_rep1 turn 2
(`replay_report --dir .../wave4_p33_post caselaw` reports `TWO_LINES 2`; every other directory
0). The Deep Research path (near lines 1337-1410) has the same shape; check it. **Constraints
already pinned by tests (`tests/test_case_law_gap.py`):** exactly ONE scope line reaches the
lawyer; P2.8's `_earlier_footers` parses only the LAST line of the trailing footer block; the
case-law clause stays last. **Measure first:** count answers with two or more `*Search scope:`
lines over every stored directory, then dry-run your fix over every stored answer and list
every answer it changes. **Acceptance (the row):** deterministic; `TWO_LINES` 0 when the two
recorded answers are passed through the fixed code, a test, and no other stored answer changed
unexpectedly.

---

## Agent B — the grader gaps ($0)

**Why now:** these must be closed BEFORE the next after-column, never during one (Session 29's
rule; Session 32's handover). The specifics quote lawyers' matters, so they are in the
gitignored `$PREPILOT_EVIDENCE/rubrics/batch1_B_rubric_gaps.md`: six items (three in
`p33.json`, one in `INTERP_HEDGE` in code, two in `p32.json`, and one explicitly NOT to fix).
**You are the only agent that edits the rubric files**, which live in the main checkout and are
shared: copy both to `$PREPILOT_EVIDENCE/rubrics/backup_batch1/` before your first edit.
**For each change:** run the grader over every directory named in that file's "Check after
every change" section, before and after, and record every verdict that moves and every sentence
that starts or stops counting (the rubric files are gitignored, so the note records counts and
file/rep/turn locations, not the sentences). The booked before-columns must still FAIL
(`wave4_p33_pre` 9 of 9; `wave4_p32_pre` 3 of 3 plus 6345's 3). Code changes to
`tools/replay_report.py` get synthetic tests in `tests/test_replay_interpret.py` /
`tests/test_replay_stance.py`. **Deliver:** the code commit(s), the note, and a one-line
statement per item: closed, or why not.

---

## Agent C — P3.16, the summariser still adds its own interpretation ($3)

**The row (FIX_PLAN P3.16) in full, then this.** The source rule `SUMMARY_SOURCE_RULE`
(`src/agent/summarisation.py`) stopped the summariser adding an ACT (0 of 42 summarised 6338
results after, 10 before: `python -m tools.summary_probe count`) but not a GLOSS. **The known
instance:** `$PREPILOT_EVIDENCE/replay/wave4_p33_post/p32_6406_rep1.json`, run-file turn 6
(export turn 7), tool `search_legislation_sections`: its `final_result` carries a parenthetical
interpretation that is not in its `raw_result` (nor anywhere in either regulation, checked in LEX
over every provision), and the same turn's answer quoted it to the lawyer as the Annex's text.
Also evidence (SESSION_LOG Session 32 addendum, item 5): change-record summaries that expand an
id to the wrong title or year.

**Step 1, free: a detector.** Add a `glosses` command to `tools/summary_probe.py` (or equivalent)
that, over every stored audit (`delegations[].tools[]` with both `raw_result` and
`final_result`), lists summary text not supported by the raw text: parenthetical asides, and
"by definition" / "which means" / "i.e." / "that is," clauses, whose content words are absent
from the raw. **An instrument title that expands an id present in the raw is legitimate** (the
raw section results carry ids and URIs, not titles) and must not count. List every match, read
them all, count by session and directory, and report the false-positive shape before any rate.
Tests with synthetic fixtures (`tests/test_summary_probe.py` shows the pattern).

**Step 2, paid, only if step 1 finds a real rate: a lever.** Either a refined
`SUMMARY_SOURCE_RULE` or a code-side check. Measure with `summary_probe redraw` (extend it to
count glosses) and `summary_probe panel` (the no-loss check on 24 other sessions' results).
**History you must not repeat** (SESSION_LOG Session 32 addendum, item 2): wording A ("say that
it does not") took additions to 0 but multiplied "the text does not contain" statements about
sixfold and collapsed change-record summaries; B left 4 of 27; the shipped C is 0 of 27. Watch
the negatives count as closely as the additions (Invariant 1). **If `summarise_prompt` changes,
bump `_CANON_VERSION` in `src/services/local_prompt_cache.py` to `v3`** (its rows are that
prompt's output and are shared across users) and update `tests/test_summary_source_rule.py`.
**Acceptance (the row):** the detector's count is 0 on a fresh sweep of 6406 and 6338 (n=3;
that sweep is the integrator's), and `panel` keeps at least as many provisions with no rise in
negatives. Say in the note whether the seam evidence supports putting it in the after-column.

---

## Agent D — P3.18, the Deep Research synthesis asserts a doctrine for a jurisdiction ($4)

**The row (FIX_PLAN P3.18) in full, then this.** Session 32 put a rule into the conversational
Manager and the quick-lookup Worker only: give an interpretive point as a reading, and never say
a general rule (an interpretation Act, a common-law doctrine) applies to an instrument or in a
jurisdiction unless the provision or source applying it there was retrieved. The Deep Research
synthesis (`get_deep_research_synthesis_prompt`, `src/prompts.py` near line 1399; body
`_SYNTHESIS_BODY` near line 1361) did not get it, and `wave4_p33_post` 6375 r3's report asserted
that English authority applies across the UK jurisdictions (15 of 15 stored reports did the same
before any change). The code line `CASE_LAW_DOCTRINE_SENTENCE` already sits in the footer; the
report body must not contradict it. The research Workers (`WORKER_SYSTEM_PROMPT_HYBRID`, near
line 366) feed the synthesis; change them only if the seam shows the claim originates there.

**How:** the synthesis seam, same day both sides, on the six stored 6375 Deep Research payloads
(`wave4_p33_pre` and `wave4_p33_post`, `6375_rep1..3.json`, `--turn 2`), 2 draws a side
(about $0.11 a draw, 24 draws, about $2.60):
`python -m tools.seam_replay synthesis --run $PREPILOT_EVIDENCE/replay/<dir>/6375_repN.json --turn 2 --reps 2 --out $PREPILOT_EVIDENCE/seam/batch1/D/<side>/<dir>_r<N>`,
the before side with `--without-fix --rev 20f7b79` (for the synthesis seam this rebuilds the
prompt from that revision for the turn's research type; verified at P4.7) or with `prompts.py`
at HEAD. Grade: `python -m tools.replay_report --dir $PREPILOT_EVIDENCE/seam/batch1/D/<side> interpret --drafts --session 6375 --rubric $PREPILOT_EVIDENCE/rubrics/p33.json`,
and read every match and drop by hand. **Guards, before and after, in the note:** P4.7's
per-research-type headings and the "Key findings" label unchanged (tests exist); links per
report not lower (count markdown links in the drafts); no hedge added to a retrieval statement
and no blanket caveat (`replay_report.hedge_counts` over each draft, in a small script written
to a file); the Deep Research synthesis prompt's other rules (enabling power, in-force) intact.
This edit is not to a Manager or Worker prompt, so the first-delegation drift probe does not
apply; if you do edit a Worker prompt, run it (`seam_replay manager --first-round --date
recorded`, SESSION_LOG Session 32 addendum item 4) before and after. **Acceptance (the row):**
P3.3's 6375 criteria, n=3, with no alignment assertion in any rep: that is the integrator's
after-column; your seam result decides whether the change goes into it.

---

## The integrator (the main session)

1. **Check the state:** `git status` clean on `fix/prepilot-defects`, head as above; `python -m
   tools.plan_status` (38 of 59, 8 of 14 buckets); `ls docs/prepilot-fixes/evidence/replay | wc
   -l` (54) and both rubrics present; the four test databases exist.
2. **Launch A, B, C and D** as background agents with `isolation: "worktree"`, each given its
   section above plus **Rules for every agent**, verbatim, and the `PREPILOT_EVIDENCE` and
   `TEST_DATABASE_URL` values for its letter. Do nothing expensive while they run.
3. **Review each result as it lands, before merging:** read the note; read the diff; grep the
   staged diff for session ids, instrument ids and matter words; run the full suite on the
   integrator's own test database (`lexchat_test`, the default); confirm each new test fails
   with its change reverted where the note claims so. Do not merge a red branch.
4. **Merge in the order B, A, C, D** (graders first, so every later grade uses the fixed
   graders), each with `git merge --no-ff`, the full suite after each. Push the branch after
   each clean merge.
5. **Fold the notes into `FIX_PLAN.md` and `SESSION_LOG.md`** (one-line ledger rows, an even
   `**` count, no `|` in a cell, a byte script that asserts the row is found once;
   `plan_status` must still count 59 unless a row is booked). Tick P4.13 and P4.14 only if their
   deterministic acceptance is met.
6. **The combined after-column**, only for levers the seam evidence supports and **only after
   putting the plan and a figure to the user.** Same shape as `wave4_p33_post` (6338, 6370,
   6375 and 6345 x3 with `--session`, then the `p32_6406` script x3 with `--script`, into a NEW
   `--out-dir`, e.g. `wave4_b1_post`), about $17-20. Pin, start uvicorn fresh, never commit
   while it runs, keep the machine awake (Session 32's run stalled when it slept; re-run the SAME
   command to resume), then `replay restore` and stop the server by PID. Grade with `interpret`
   (every match and drop hand-read), `stance` (every "none" hand-read), `hedges`, the exit-1 set
   plus `drgaps`, `caselaw` (TWO_LINES 0 for P4.14), `openers`, `summary_probe count` and C's
   gloss detector.
7. **Hand over:** a Session 33 entry and a handover for Session 34 in `SESSION_LOG.md`; update
   the memory entry `project_prepilot_freeze.md` and its `MEMORY.md` line; update the Fix
   Tracker only if the user asks (procedure: FIX_PLAN "How to use this file" step 7, and read
   the live artifact and every line of the saved file first).

**Open with the user, carried (do not act on the target yourself):** the legal readings behind
the rubrics (to be confirmed by a lawyer); release tags and deploy by tag (TODO D19); which rows
go in the next cut (v2026.10.1); deploying both cuts (`pg_dump` first; note the local prompt
cache version is now v2 on the branch, so every cached summary becomes unreachable when it
reaches the target, which is intended); telling the eval-harness owner (schema v6 etc., see the
Session 32 handover); P4.12; P4.15's decision; D20; D21/D22; P5.2; Thomas's document.
