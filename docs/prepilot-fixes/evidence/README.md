# Evidence

Frozen inputs for `../FIX_PLAN.md`. Do not edit `classification.json` to reflect a fix —
it records what the pre-pilot found, and the ledger records what was done about it.

## `classification.json`

All 62 pre-pilot sessions (11–21 Aug 2026), classified from the transcripts rather than the
feedback scores. Per session:

| Field | Meaning |
|---|---|
| `verdict` | `FAIL` (wrong, materially incomplete or unusable) · `DEFECT` (right answer, real flaw) · `PASS` |
| `primary` | The bucket the session is allocated to (`B1`–`B14`), blank for PASS |
| `secondary` | Contributing buckets |
| `diag` | One-line diagnosis of what actually went wrong |
| `user`, `q5a`, `q8`, `mode`, `rmode`, `thread` | As recorded in the export |

`q5a` and `q8` are the lawyer's own answers and are a **reading order, not a verdict** —
sessions 6376 and 6361 carry `Q7a = yes` with free text saying the opposite.

## Not committed

The raw transcript export is not in this repo. It contains the lawyers' live research
questions. Regenerate from **Admin Portal → Developer → Session transcripts export** (all
time), or use the local copy at:

```
C:/Temp/aila-prepilot/pre-pilot sessions/session-transcripts-all-time-2026-09-14.csv
```

`replay_set.json` (P0.2) and `replay/` (P0.1 output) are gitignored for the same reason.
See the *Data handling* section of `../FIX_PLAN.md`.
