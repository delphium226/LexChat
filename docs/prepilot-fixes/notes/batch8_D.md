# Parallel batch 8, agent D: P3.21 measured, with P5.4 (c)'s probe

Session 40, 2026-10-06. Branch `worktree-agent-a7b6a07a3f08ab9cf`. **The worktree came up on `main`
(`a6b4a76`), not the integrator's HEAD; with no commits of mine I ran
`git reset --hard 87ceeff1f3478cec38d9edf6d7010b78d16d8436` before any work.** Everything below is
based on `87ceeff`. The run was interrupted once (the integrator's session ended) and resumed; the
call logs were counted before resuming and the live census continued from them, nothing was re-run.

**Spend: $0 in model spend.** No model call, no server, no replay pin/run/restore. **Live calls, as
agreed at launch: 212 LEX calls (cap 300) and 248 legislation.gov.uk calls (cap 300)**, each host
capped and paced (at least 0.6 s apart) in code, every call logged (method, URL, status, bytes) in the
gitignored scratch (`log_lex.jsonl` 207 + `log_cli_lex.jsonl` 5; `log_lgu.jsonl` 248). No other host.
LEX: 157 `POST /legislation/lookup`, 50 `GET /legislation/proxy`, 2 `POST /amendment/search`, 3 more
(the CLI check). legislation.gov.uk: 248 GETs (234 200s, 7 502s, 7 504s).
**Built nothing in the product.** New: `server_py/tools/lgu_probe.py` (a probe tool) and
`server_py/tests/test_lgu_probe.py` (19 tests, synthetic payloads). Full suite on `lexchat_test_d`:
**2358 passed** (2339 + 19).

This note names no session instrument, title or question; where a session's instrument matters it is
named by its role and the FIX_PLAN row that already names it. Commands run from the scratch
`$D = docs/prepilot-fixes/evidence/seam/batch8/D` (gitignored, checked with `git check-ignore -v`)
with `PREPILOT_EVIDENCE=C:/Projects/LexChat/docs/prepilot-fixes/evidence`, `PYTHONIOENCODING=utf-8`,
and `$S` = this worktree's `server_py` (every script that imports product or tool code asserts it is
importing `$S`). **The stored census globs all 58 replay directories** (every `*_rep*.json` and
`*_smoke*.json`, 487 run files), `wave4_b7_p324` included.

## 1. Result in one paragraph

**The date P3.21 wants is in legislation.gov.uk's "Changes to Legislation" feed, provision by
provision, for every stored commencement relation, and the feed is reachable through LEX's own
proxy, so the target needs no new whitelist entry.** LEX's `description` is the weaker source: it
states a readable date for 65 of the 157 commencing instruments (41% of hops), and where it states one
date and the feed dates the same relation, it disagrees on 441 of 3,147 relations (14%), because the
description covers only part of what the instrument commenced (5 instruments; 2 of them read only a
secondary date) and once because the feed is wrong. The feed's relation set equals LEX's (8,144 of
8,180 stored relations match exactly; 35 more differ only in how a provision label is rendered), every
matched relation is dated in it, it also dates the commencing instruments LEX does not hold, and it
carries the qualification ("for specified purposes", "for E.") a bare date would lose. **For 6409 the
feed dates both commencing instruments; the description dates one** (the other is the instrument
LEX 404s on, named on P3.5's row). **For 6411 neither source has anything:** its Act has no `coming
into force` relation by another instrument in LEX or in the feed (both hold only the 29
`Commencement Order` rows P2.5 found), so 6411 can meet the acceptance only on its negative branch.
The feed's cost is latency, not size: median ~0.3 s, but about one call in five takes over 8 s and 14
of 159 first tries returned a gateway error, so a hop must be bounded and fail-soft.

## 2. The stored census ($0, no call)

```
python $D/collect.py $S        # every change-record call and every stored description -> collected.json
python $D/census.py             # -> census.txt, commencing.json
python $D/pairs.py              # every distinct stored commencement relation by another instrument
```

- **Change-record calls:** 1,172 reached the API with rows stored (1,094 `to`, 78 `by`), plus 290 memo
  hits with no rows: 1,462 in all, which is batch 7 A's 1,435 plus `wave4_b7_p324`'s 27. Check passes.
- **Commencing instruments other than the subject** (P3.5's rule on the raw rows: `type_of_effect`
  `coming into force`, `affecting != changed`; P3.24's `self: false`): **157 distinct**, named in 357 of
  the 1,094 `to` calls, on 32 distinct subjects. The built slimmer lists 145 of them (12 are hidden
  by the 40-group cap in every call that names them). The 78 `by` calls add none (their 4 subjects are
  already among the 157). By type: `uksi` 81, `ssi` 59, `wsi` 14, `nisr` 2, `ukpga` 1. This is
  FIX_PLAN P3.21's own 157. Check passes.
- **Stored records of those 157:** `lookup_legislation` 1 (P3.21's row says 1; check passes),
  `get_legislation_text` 8, and, a source the row did not count, **raw `search_legislation`
  responses (whose `description` the slimmer drops but the audit keeps) 61; any stored description 62.**
- **Distinct stored commencement relations by another instrument: 8,180** (157 instruments, 32
  subjects).
- **Hops per turn** (the distinct commencing instruments a turn's `to` records name; 514 turn records
  consulted a change record, 307 name at least one): **993 hops, median 1, p75 2, p90 4, p95 9, max
  33.** A per-instrument cap of 5 makes 74% of the hops and covers 278 of the 307 turns in full; 10
  makes 87% and 293. (These are turn RECORDS over every rep of every directory, so repeated sessions
  weigh more than once.)

**Date census over the 62 stored descriptions** (`python $D/dates.py $S stored`, `dates_stored.txt`):
37 dated, 24 undated, 1 with no commencement statement; 5 state more than one date. The 62 are
byte-identical to the live lookup's descriptions (62 of 62), so the live census below supersedes it.

## 3. LEX `/legislation/lookup` for all 157 (157 LEX calls)

All 157 rather than the 95 with no stored record, so the census reads one source, the one the hop
would call (and checks the stored 62 against it). `python $D/lookups.py`, then
`python $D/dates.py $S live` (`dates_live.txt` holds every description, match and drop).

| class | n |
|---|---|
| dated (a date in a sentence with commencement language, hung on a present-tense verb) | **65** |
| undated ("on the appointed day", "on the days they appoint", "appoints various days", "the Nth commencement order made under ...") | 82 |
| not held (404, `Legislation not found`) | 8 |
| no commencement statement | 1 |
| empty description | 1 |

- **Matches: 73 date spans taken in 65 descriptions; 7 descriptions state more than one date. Drops:
  17**, each listed with its reason in `dates_live.txt`: 10 past tense (an earlier commencement by
  Royal Assent or another order, quoted in this instrument's note), 3 negated (two of them the main
  dates below; one "will not come into force on ..."), 2 a period's anchor ("six months beginning
  with ..."), 1 an end date ("until the end of ..."), 1 no commencement language in its sentence (an
  agreement's made date).
- **Hand-read, every match and every drop** (the pattern was corrected four times on it before the
  numbers above: a sentence split at "etc. (Scotland)" dropped three real dates; past-tense
  commencements by earlier orders were taken as this instrument's; "brings ... fully in force" was
  missed; a period's anchor was taken as a date). On the final pattern: **every taken span is a date
  the description states for this instrument's own commencement**, and two descriptions' taken date is
  only the secondary one (the offence provision's later date; the main date sits in a negated clause
  and is dropped). **Every drop is correctly dropped as "not this instrument's stated commencement
  date" except those two main dates (a miss, the safe direction).** The cross-check in section 4
  confirms the hand-read where it can: 59 of the 65 dated descriptions state exactly the dates the
  feed gives that instrument.
- **The 600-character cap** (`lookup_legislation` keeps 600): 15 descriptions are longer; the first
  taken date lies beyond 600 characters in 1 of 65 (and that is one of the two secondary dates).
- **8 commencing instruments are not held by LEX at all**, and they account for 131 of the 993 hops
  (13%), including the one 6409 turns on.

## 4. P5.4 (c): legislation.gov.uk's dated effects (248 legislation.gov.uk calls)

**What the feed is.** `/changes/affected/<id>/data.feed` (changes TO an instrument) and
`/changes/affecting/<id>/data.feed` (changes it makes), Atom, `results-count` up to at least 1,000 a
page, a `totalResults` and page count (unlike `/amendment/search`). Each `ukm:Effect` is
provision-to-provision with both sides' labels and URIs, the effect type, `Applied` /
`RequiresApplied`, and `ukm:InForceDates`: `<ukm:InForce Date="YYYY-MM-DD" Qualification="wholly in
force"/>`, or `Prospective="true"` with no date. **Commencements are effects of type `coming into
force`, the same vocabulary as LEX's** (LEX's rows are, in effect, this feed without the dates).

```
python $D/lgu_affecting.py $S   # the affecting feed of each of the 157 (159 calls; 14 gateway errors)
python $D/lgu_retry.py $S       # each failed one retried once at 200 a page (27 calls; all 14 recovered)
python $D/lgu_affected.py $S    # the affected feed of the 32 subjects + 6411's Act (59 calls, 0 errors)
python $D/compare.py $S --list  # -> compare.txt
python $D/g2.py $S              # per subject, LEX against the feed -> g2.txt
python $D/disagree.py $S        # every one-date description the feed contradicts -> disagree.txt
python $D/residuals.py $S       # the unmatched relations; self commencements -> residuals.txt
```

- **Per commencing instrument (157 of 157 fetched):** every one has commencement effects in the feed,
  and **every commencement effect by another instrument is dated (8,400 of 8,400 in the affecting
  feeds; 8,185 of 8,185 in the affected feeds).** Against the descriptions: equal 59, description names
  a subset of the feed's dates 5, disjoint 1, feed dated and description not 92.
- **Per relation (the 8,180 stored LEX commencement relations by another instrument):** **8,144
  (99.6%) match a feed effect exactly** on (subject, changed provision, instrument, affecting
  provision), **every one dated**; 35 differ only in label rendering (LEX joins two `Section`
  elements, "para. 13(1)para. 13(2)(b)(i)", where the feed writes "para. 13(1)(2)(b)(i)"; read in
  `residuals.txt`, each has a dated feed twin); 1 has an empty provision in LEX. Per subject the two
  sets are equal or differ by those label twins on all 32, and **the feed is fresher**: it holds one
  relation on 6409's Act made by a 2026 instrument LEX does not yet record.
- **The description route, per relation:** a one-date description covers 3,154 of the 8,180
  relations, a several-date one 320 (which needs the instrument's own text to attribute), and 4,706
  get nothing (undated, not held, empty). **Where a one-date description and the feed both date a
  relation, they agree on 2,706 and disagree on 441 (14%)**, all on 6 instruments (read in
  `disagree.txt`): 3 descriptions describe only part of the order (one names the provisions its
  article 2 commences on one date and says nothing of the later date on which the feed has it
  commence most of the rest, 409 relations; one omits a second date, 9; one 2), 2 read only the
  secondary date (3 relations and 1), and **1 is the feed's error**: 17
  relations dated two months before the instrument was made (made date read from
  legislation.gov.uk's own XML through the LEX proxy, 1 call). So neither source is infallible, but the
  description's failure is structural (it summarises) and the feed's is a data slip a made-date check
  would catch.
- **Per hop:** of the 993 hops, the description dates 404 (41%); the feed dates all 993.
- **6409 and 6411** (`python $D/acceptance.py $S`, ids in the gitignored output): 6409's stored
  records (152 change-record calls in 24 run files) name two commencing instruments; the description
  dates one, the feed both (the other is not held by LEX). 6411's (7 calls) name none in LEX and the
  feed has 0 `coming into force` effects on that Act (857 effects, 29 `Commencement Order`): nothing to
  hop to in either source.
- **Applied for Scottish material?** Yes, at the same rate as the rest. In the 33 affected feeds,
  effects still to be applied to the revised text (`RequiresApplied` and not `Applied`): Scottish
  subjects 188 of 3,529 (5%), others 847 of 15,756 (5%); commencement effects 1 of 1,813 Scottish, 218
  of 8,238 other. The backlog is per instrument and recent (one Scottish Act 96 of 483; a 2026 Act 223
  of 513), not a jurisdiction gap. A date on an effect does not depend on it being applied.
- **Self commencements:** the feed dates 1,145 of the 1,886 self-referential `coming into force`
  effects on these subjects (61%), the dates P3.21's row puts out of scope ("in the Act's own
  commencement section"). Not acted on; decision 5.
- **A third source, seen once:** legislation.gov.uk's revised XML carries a commencement-information
  note on the provision itself ("S. N in force at D.M.YYYY by S.S.I. YYYY/N, reg. 2(a)"; 1 call). LEX's
  stored texts carry none (0 of 68 distinct stored `get_legislation_text` results), so LEX strips them.

**Routes and the whitelist.** legislation.gov.uk is not on the target's whitelist. **LEX's `GET
/legislation/proxy/{legislation_id}` passes a URL-encoded legislation.gov.uk path through,
`changes/...` feeds included, with the query string encoded into the path** (`results-count`, `page`:
checked, 4 calls). 30 affecting feeds read through the proxy were identical to the direct reads, effect
id for effect id (30 of 30). The proxy is therefore a route that needs no new whitelist entry, with two
caveats: it is an undocumented use of an endpoint the spec calls a metadata proxy, so it depends on the
LEX team leaving it open; and it inherits legislation.gov.uk's latency. **Latency** (the direct log):
median 429 ms over the 234 200s, p90 21 s, 52 over 8 s, unrelated to response size (median 259 ms
under 20 KB, 522 ms over 200 KB); 14 of 159 first tries returned 502/504. Through the proxy, the first
30 timings (median ~110 ms) were a cache artefact (each URL had just been fetched direct), so 15
were re-timed at a page size never requested: 12 under 300 ms, 2 at ~17 s, 1 a 502 after 30 s. If the
direct route is chosen instead, the target must whitelist `https://www.legislation.gov.uk`.

## 5. The hop's cost, which sets its cap

`python $D/cost.py $S` (`cost.txt`).

- **(A) per instrument** (a LEX lookup, or the instrument's affecting feed, per commencing instrument):
  the hop counts in section 2 (median 1, p90 4, p95 9, max 33 a turn). A quoted description line per
  instrument would add median 120, p90 581, max 4,094 characters a turn.
- **(B) per change-record call** (the subject's affected feed, which dates every relation the record
  lists, in one call): **1 page at 500 for the median `to` call, 2 at p90, 9 at the maximum** (1, 1 and
  5 at 1,000 a page). A date on each commencement `changes` entry by another instrument in the built
  slimmer's output (`, "in_force": "YYYY-MM-DD"`, 26 characters) adds median 0, p90 156, p95 208, max
  7,150 characters a call (3.2 entries a call on average; a qualification would add to it).
- On calls, (B) costs one extra call per change-record call however many instruments the record
  names, and returns the date per provision with its qualification, which is the shape the answer
  needs; (A) by description costs one call per instrument and returns a date per instrument.

## 6. The probe tool (`server_py/tools/lgu_probe.py`)

`parse_effects_feed` (raises on a page that is not a feed, so a gateway error page is never read as
"no effects"), `summarise_effects`, `compare_commencements` (scheme-free, self rows out),
`description_dates` (every match and drop with its reason; never infers a date), a `PacedClient` that
enforces the cap (counting calls already in a shared `--log`), the pacing and the two allowed hosts,
and three commands: `--effects affected|affecting <ids> [--via lex]`, `--descriptions <ids>`,
`--compare <ids> [--via lex]`. Checked live: `python -m tools.lgu_probe --compare <6409's Act> --via
lex` reprints section 4's 8 matched of 8, all dated, and the feed's one extra (5 LEX calls in all
across the three commands, logged).

**Tests and reverts** (`python $D/mutants_lgu.py $S`, `mutants_lgu.txt`, on a scratch copy outside
the worktree): 19 tests pass on the built code. **Full revert (the 586-line tool removed): the test
file fails at collection.** Because that proves only the import, **18 single-site mutants**, each
anchor asserted to occur exactly once with CRLF normalised: the feed's date not read; a non-feed page
accepted; self commencements counted as by another instrument; outstanding ignoring
`RequiresApplied`; past tense taken; "came into force" taken; brackets not their own clause; negation
ignored; "until" ignored; a period's anchor taken; list items not taking the next month; the old
sentence split; no ordinal without a space; `compare` keeping self rows; the cap ignoring logged
calls; any host allowed; one page only; a gateway error accepted. **All 18 fail (0 survive)**; the
first run left two alive (the outstanding test had no unapplied effect that needed no applying, and
the ordinal mutant did not change behaviour), and both were fixed before the numbers above.

## 7. What I did NOT do

- No product change, no change to P3.21's wording sites (`search_scope.py`), no grader change.
- Did not compute the hop's effect on any answer, grader or footer: nothing was built to dry-run.
- Did not probe P5.4's leads (a), (b) and (d), or legislation.gov.uk's policy notes; lead (c) only.
- Did not try to match the 35 label-rendering twins in code (read by hand; each has a dated twin).
- Did not measure the uncached proxy latency beyond 15 calls, nor legislation.gov.uk's published rate
  limit (none was hit at 0.6 s pacing).
- The per-turn hop counts are over turn records of every rep; not de-duplicated by session.
- Self-referential relations: counted, not designed for (decision 5).
- Did not edit FIX_PLAN, SESSION_LOG, LEGAL_DATA_SOURCES, the tracker or any memory file.

## 8. Decisions for the user

1. **The commencement date's source.**
   - **(a) legislation.gov.uk's effects feed, read through LEX's proxy (recommended).** It dates every
     stored relation, per provision, with its qualification, covers the instruments LEX does not hold,
     and needs no whitelist change; add a check that a date is not before the commencing instrument's
     made date.
   - (b) The same feed read direct, with `https://www.legislation.gov.uk` added to the target's
     whitelist. Same data, no dependency on the LEX proxy staying open.
   - (c) LEX's description only, as the row booked. Dates 41% of hops, and a one-date description
     contradicts the feed on 14% of the relations both date.
   - (d) Both: the feed first, the description quoted (never attributed per provision) where the feed
     call fails.
2. **The hop's shape and cap.**
   - **(a) One affected-feed fetch per change-record call (recommended),** memoised per request, at
     most 2 pages (1,000 relations; p90 needs 2) with the window stated beyond that, an 8 s timeout and
     fail-soft: on any failure the change record is returned as today and says the date was not
     retrieved. About one call in five will hit that timeout on today's latency.
   - (b) One affecting-feed fetch per commencing instrument, capped at 5 a turn (74% of hops).
   - (c) One LEX lookup per commencing instrument, capped at 5 a turn (the booked shape).
3. **The acceptance to book.**
   - **(a) 6409 n=3 as booked (a commencement question gets the date for both instruments, each with
     its source and qualification), and 6411 n=3 on the negative branch only (no commencement date
     stated, since neither source has one), plus the row's unit tests (recommended).**
   - (b) As booked, unchanged: 6411's positive half cannot pass with either source.
   - (c) Replace 6411 with a session whose Act has commencements by another instrument, keeping 6411
     as a suppression guard.
4. **Does P5.4 (c)'s answer warrant a new row?**
   - **(a) No new row (recommended):** record the answer on P5.4 and in `LEGAL_DATA_SOURCES.md`
     (dated effects exist, match LEX's relations, are applied at the same rate for Scottish material,
     and are reachable through LEX's proxy), and build it as P3.21's date source.
   - (b) A new row for the revised text's commencement-information notes (a per-provision dated
     statement LEX strips), as a second, text-level source.
   - (c) A new row to ask the LEX team whether `/legislation/proxy` may carry feeds (add it to
     `WAVE5_QUESTIONS.md`), before (a) relies on it.
5. **Self-commencing Acts, out of scope on P3.21's row.**
   - **(a) Keep them out for the first build (recommended);** the feed dates 61% of them, so book them
     as a follow-up once the hop is measured.
   - (b) Bring them in now: the same feed call returns them at no extra cost, but P3.24's line treats
     `self: true` relations as permitting nothing, and that rule would have to change with it.

## Scratch

`docs/prepilot-fixes/evidence/seam/batch8/D/` (gitignored): every script above, the two call logs
plus the CLI's, `raw_lex/` (207 bodies) and `raw_lgu/` (248), `collected.json`, `commencing.json`,
`lookups.json`, `lgu_affecting.json`, `lgu_affected.json`, `pairs.json`, and the outputs
(`census.txt`, `dates_*.txt`, `compare.txt`, `g2.txt`, `disagree.txt`, `residuals.txt`, `cost.txt`,
`acceptance.txt`, `mutants_lgu.txt`, `pytest_full.txt`). Copied with `cp -r` to the main checkout's
`docs/prepilot-fixes/evidence/seam/batch8/D/`.
