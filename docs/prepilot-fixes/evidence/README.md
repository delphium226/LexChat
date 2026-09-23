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

`rmode` is blank for 20 sessions because the export's filter snapshot predates the column.
Do not fill it in here; the reviewer's reads live in the next file.

## `research_mode_reads.json`

FIX_PLAN P0.6 (2026-09-23): a human read of the research type each turn ran under, for the
twelve replayed sessions whose export value is blank. It covers 50 turns, keyed by session
and 1-based user-turn index. Each read has `value`, `source: reviewer`, `basis` (`answer`,
`lawyer` or `bracketed`) and a one-line neutral `evidence` note. The file's own `note` and
`mechanism` fields define the terms and give the pre-pilot facts the reads rest on.
`replay_set.load_research_reads` validates the file and `replay_set.py` sends each read.

**Never quote a lawyer's question in a note.** `test_replay_research_reads.py` fails if any
five-word run from a session's questions appears in its notes. That rule covers public case
names too, when they are typed the way the lawyer typed them. The file is meant to be
superseded: the target's `request_timings.research_mode` recorded the real value for each
request (FIX_PLAN P0.7).

## Not committed

The raw transcript export is not in this repo. It contains the lawyers' live research
questions. Regenerate from **Admin Portal → Developer → Session transcripts export** (all
time), or use the local copy at:

```
C:/Temp/aila-prepilot/pre-pilot sessions/session-transcripts-all-time-2026-09-14.csv
```

`replay_set.json` (P0.2) and `replay/` (P0.1 output) are gitignored for the same reason.
See the *Data handling* section of `../FIX_PLAN.md`.
