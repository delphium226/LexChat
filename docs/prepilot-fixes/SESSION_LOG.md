# Pre-pilot defect fixes — session log

Append-only, newest last. One entry per session. Read `FIX_PLAN.md` first, then this file for
what actually happened.

The **Surprises / deviations** line is the one that matters — it is where a cold-starting
session learns that reality diverged from the plan.

## Entry template

```markdown
## Session N — <date> — <ledger rows attempted>
**Done:** …
**Surprises / deviations from FIX_PLAN:** …
**State of the branch:** <commit sha>, tests <green|N failing>
**Next action:** <the single next thing>
```

---

## Session 1 — 2026-09-14 — Re-analysis and plan

**Done:**
- Re-analysed all **62** pre-pilot sessions (11–21 Aug 2026, 13 lawyers, 377 messages) from the
  all-time transcript export, classifying each on the transcript rather than the feedback score:
  **25 FAIL, 16 DEFECT, 21 PASS**. Derived 14 failure buckets bottom-up, then reconciled against
  the existing P1–P10 list in `docs/TODO.md`.
- Verified the disputed law at source where a lawyer contested an answer: ILRA 2010 s.1(1)(a)
  scope, Education (Scotland) Act 1962 s.117, SSI 2025/119 reg 2 and its appointed day, SSI
  2008/216 and SSI 2022/356 presence and search rank, and all six contested case citations
  against the National Archives feed.
- Committed the pre-existing P1–P10 analysis to `main` (`eaaa4ec`) so this branch has a base to
  reconcile against, then branched `fix/prepilot-defects` from it.
- Wrote `FIX_PLAN.md` (invariants, ledger, verification protocol, re-planning protocol) and
  froze `evidence/classification.json`.
- Published the full analysis:
  <https://claude.ai/code/artifact/43d8e63d-1c9d-4460-907c-2d35c1fa3786>

**Surprises / deviations from FIX_PLAN:**
- **Three of the fourteen buckets are code defects, not model behaviour, and they were found by
  running the shipped functions against the live API rather than by reading transcripts.** The
  largest — `_matches_jurisdiction` — **discards 100% of legislation search results** whenever a
  jurisdiction filter is set. It expects `"E+W+S+NI"` single-letter tokens; the API returns
  `['Scotland']`, `['']`, `['England','Wales','Scotland']`, `['United Kingdom']`. All six live
  extent values return `False` for all five jurisdiction values. 15 of 62 sessions ran with this
  set. **Read the transcripts second; probe the API first** — fourteen sessions of lawyer
  evidence did not identify this and a five-line script did.
- **B2 has zero primary allocations and that is the finding, not an omission.** The bug never
  presents as itself — the lawyer sees "not in the legislation database", a halted report, or a
  wrong Act, and nothing in the answer mentions a filter. Any future bucket with a high
  secondary count and no primary deserves the same suspicion.
- **`current_only` is a total no-op and cannot be fixed by extending the word list.** The
  `status` field it reads means *which text version is held* (`final` / `revised`), not in-force
  status. 42 of 62 sessions ran with this filter on believing it did something. This reframes
  B4 from "tune the filter" to "we have no in-force signal at all", which is why P1.2 and P2.5
  are split.
- **B6 (capitulation under challenge) was not in P1–P10 at all** and I rank it critical. In 6406
  AILA asserts a position over three turns, reverses completely on pushback with a fresh
  citation, and had already reversed once earlier in the same session. For a tool whose users
  are trained to probe, an answer that tracks who pushed hardest is worse than one that is
  simply wrong.
- **B3 is bigger than P1 framed it.** P1 called the confident false negatives the headline; the
  false negatives are a *symptom*. The cause is that no tool exposes *made under* / *commences*
  / *amends*, so the model answers relationship questions from search adjacency. 6340 is the
  proof: three real, correctly-cited SIs asserted to be made under s.117 of an Act that is a
  404 in LEX. Link-checking — the only verification the sources rail supports — cannot catch it.
- **The feedback form's `Q7a` column has false positives.** 6376 and 6361 both answer "referred
  incorrectly: yes" with free text saying the opposite. Classify on transcripts; the scores are
  a reading order, not a verdict.
- **The raw transcript CSV is deliberately not committed** — it contains the lawyers' live
  casework questions. `classification.json` is committed because it matches the precedent
  already set in `docs/TODO.md`, which names the same users and quotes them. **Open question
  for the deploying organisation: whether the verbatim replay set may be committed as a
  regression fixture.** Until answered it is regenerated locally from the Developer-tab export.
  This blocks nothing — P0.2 writes it to a gitignored path.

**Decisions taken before kickoff (user, 2026-09-14):**
- **Replay model pinned to `google/gemini-3.1-pro-preview`.** All 176 pre-pilot assistant
  messages ran on it; the dev box is currently on `moonshotai/kimi-k3`, which would have
  measured a different system. **Confirm it is still served before the first replay** — it is a
  preview model. If withdrawn, stop and re-decide rather than substituting.
- **n=3 on the 25 FAIL sessions, n=1 on the 16 DEFECTs** (~$50 per baseline pass against ~$82).
  Ambiguous DEFECT replays get promoted to n=3.
- Still open, blocking nothing: whether the verbatim replay set may be committed as a fixture.

**Also corrected this session:** the standing memory note saying there is no OpenRouter key on
the dev machine is **wrong** — there is one, in the local DB (`app_settings` →
`provider.openrouter`, `active_provider = openrouter`), not in `.env`. Memory updated.

**State of the branch:** `fix/prepilot-defects` at the plan commit, branched from `main` at
`eaaa4ec`. No code changed yet. Test suite untouched.

**Next action:** P0.1 — build the replay runner against `/api/system/chat` with
`emit_tool_details=True`. Do **not** start Wave 1 before P0.3 has recorded a baseline; three
weeks of commits landed between the pre-pilot and this branch, and some failures will not
reproduce.
