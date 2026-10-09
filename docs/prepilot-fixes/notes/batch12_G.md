# Batch 12, agent G: P3.41, P3.28, P3.32, P3.33, P3.42 with P3.26, P3.30 measured

**Session 44, 2026-10-09. Measurement only: no product code, no test, no model call.** Data-improvement
batch 1's agents B and D (without D's items 3 and 5, which are batch 12's agents A and D here).

**Base.** The worktree came up on `main` (`a6b4a76`) with no commits; I ran `git reset --hard a99e4d4` (the
integrator HEAD) before anything else. This note is based on `a99e4d4`. No unexpected commit appeared on the
branch while I worked.

**Spend and calls.** $0 model spend. **47 LEX calls** (cap 60): 27 `POST /amendment/section/search`, 20
`POST /amendment/search`, all 200, every one at least 0.5 s after the last (`lex_g12.py`: cap, gap and host
enforced in code, each call logged with method, URL, payload, status, bytes, and its body saved).
**155 legislation.gov.uk attempts** (cap 200), direct to `www.legislation.gov.uk` through `madeunder_probe`'s
`PacedClient` and User-Agent (`lgu_g12.py`: cap counted from the log, 0.6 s gap within a run and from the log's
mtime across runs, host fixed, bodies saved): 149 answered 200, 4 answered with a second-hop 307 the transport
does not follow, 1 answered 404, and **1 timed out at 60 s** (the UK-SI-wide affected feed). `PacedClient` logs
only after a reply, so that attempt was missing from the log: I appended it by hand (log line 91, marked so)
and changed the door to log a failed attempt itself. Agent A was reading the same site; at a gap of at least 0.6 s my
reads cannot exceed 500 in 5 minutes even run continuously (a third of the site's 1,500), and they came in
bursts of at most 60.

**Corpus.** 66 replay directories (counted), 559 run files, 2,235 turns, 1,709 stored `get_legislation_changes`
calls. Every change-record call that reached the API stores its full rows in `api_calls[].response`
(1,377 of 1,377 match their own `rows_returned`; the other 332 were memo or cache hits), so the instrument-level
rows are available offline: 190 distinct (id, direction) records, 71,040 rows.

**Labels.** Instruments and Acts from sessions are named here by role or by label (P1-P20, A1-A25); the key is
the gitignored `evidence/seam/batch12/G/g12_keys.md`. Effect-type strings are the public vocabulary of the two
feeds and are quoted as they are.

**Commands.** Every script is in the gitignored `evidence/seam/batch12/G/` and is run from that directory with
`PYTHONIOENCODING=utf-8`; each one imports the product code from this worktree and asserts that it does. A
script reading a live body reuses the saved body on a re-run, so re-running costs no call.

---

## 1. P3.41: amendments at provision level. **No-go.**

**Demand: 0 of 196 user turns ask what amended, repealed or commenced a specific provision.** Read in full:
the 28 turns with a change word (`p341_candidates.py`), then all 36 turns naming a provision whatever their
verbs (`p341_provturns.py`). The nearest is 6409 t6 ("which sections have been commenced by regulation"),
an instrument-level question P3.5 answers.

**What answers state anyway.** 52 distinct (session, turn) answers in the stored runs carry a sentence stating
a provision-level change ("s.N was inserted / substituted / omitted / commenced by ...") (`p341_claims.py`; read
in full: a handful are false hits, e.g. a provision that limits proceedings "commenced" by leave of the court).
I took 20 provisions from those claims (P1-P20: 15 sections or subsections, 3 regulations, 1 schedule paragraph,
1 EU article; 2 commencement claims, 18 amendment claims).

**Live comparison (`p341_live.py --live`; 18 live, 2 reuse batch 4 D's recorded responses).**
`/amendment/section/search` on each exact address, against the instrument-level rows held for the same Act:

| | provisions |
|---|---|
| section-level rows the instrument-level record lacks (adds) | **0 of 20** |
| same relation with a different effect (contradicts) | **0 of 20** |
| instrument-level rows at the exact address that section-level missed (loses) | **0 of 20** |

The endpoint is a strict subset of the instrument-level record. What it **cannot reach** at the exact address,
on **9 of the 20** provisions: 21 relations filed one level down (on subsections of the queried section; 4
provisions), 11 relations whose `changed_provision_url` is null (4 provisions; every EU-article change in the
sample is one), and 2 relations of a schedule paragraph filed under **the schedule's** URL (1 provision: the
paragraph address returns nothing, and the schedule address returns all 20 of that schedule's relations). Three
more (a whole section's own commencement or partial repeal) sit at the parent section's address and need a
second call. **A new trap for the skill:** a schedule paragraph's change carries `.../schedule/N`, not
`.../schedule/N/paragraph/M`.

**Did the product's slimmed record already show the Worker each provision's relation?** Yes: in every stored
call on the 18 provisions that have a relation (`p341_window.py`), no window cut hid one. **The other 2 have no
relation at any level**, in LEX or in legislation.gov.uk's affected feed (`p341_lgu_check.py`, 2 reads; that
feed's record for one of the Acts has exactly LEX's 142 relations): the answers' claims about them came from
text, and no change-record endpoint can verify them. **A shape trap I hit and fixed:** for 14 of the 20
provisions every stored call is the pre-P3.19 shape (`changed_provisions`, not `changes`), and for the other 6
most are; a reader of `changes` alone read every one of them as "not listed".

**Verdict.** No turn asks; the endpoint adds nothing the instrument-level record (already fetched, complete to
20,000 rows) does not hold, and loses 34 relations by exact matching. **No-go** (decision 1).

## 2. P3.28: removals counted by effect type. **Go, deterministic: lever "both".**

**Vocabulary (`p328_vocab.py`, `p328_read.py`, `p328_class.py`).** Every stored effects feed (batch 8 D: 67
affected and 172 affecting feeds, direct; batch 9 C: 6 affected feeds through the proxy; 239 parsed with the
product's `parse_effects_feed`): **713 distinct types over 20,637 distinct effects.** Every stored LEX row:
**2,063 distinct types over 48,056 distinct relations.** I read every type in both lists and wrote the reading
as a rule (`p328_class.classify`: a removal family, a qualifier, and the not-the-subject exclusions), which
reproduces my reading on every type.

**The feed is not a separate signal.** Over the 33 subjects with both an affected feed and LEX rows stored,
**18,926 of 18,926 matched relations carry the identical type string** (`p328_match.py`; 0 differ). Removal
relations present on one side only: 3 and 4, label-rendering differences. So "effect type" and "wording" are
the same string; the lever is how the product classifies the strings it already receives, and **the feed route
noted on the row adds nothing and costs a call** (decision 4).

**Removal types the product's `_REPEAL_EFFECT_TOKENS` misses (LEX side; feed side in brackets):**

| family | types | relations |
|---|---|---|
| "omitted", "words omitted", "word omitted", "entry omitted", "omitted by virtue of ... (as substituted)", "omitted (temp.)", "omitted (cond.)", "omitted for specified purposes", "Form omitted", "words and comma omitted" | 90 (69) | 3,387 (1,043) |
| "removed", "words removed", "word removed" | 3 (3) | 16 (16) |
| "ceases to have effect", "cease to have effect", "ceased to have effect" | 3 (2) | 12 (7) |
| "deleted", "words deleted" | 2 (2) | 3 (3) |
| "rev (saving)", "rev. (saving)", "rev in pt (...)" | 3 (0) | 4 (0) |

**Types the product counts that remove nothing from the subject (its false positives), 7 relations:** "power to
repeal conferred" (3), "power to amend or revoke conferred" (2), "repeal of earlier affecting provision ..." (1),
"revocation of earlier commencing SSI ..." (1). **Also not removals of the subject, correctly uncounted today,
and caught by a naive "omit" or "expiry" widening:** "(words) omitted in earlier amending provision ..." (14 LEX
types, 5 feed), "expiry of earlier affecting provision ..." and "saving for expiry ..." (65 LEX types, 43 feed,
almost all from one temporary-measures Act), "functions cease to be exercisable concurrently", "disapplied". Nothing removal-like sits outside the
candidate set (the rest are substitutions, insertions, modifications, applications).

**Counts per stored call (`p328_count.py`), 1,709 calls, 190 distinct records:**
- the product's count differs from the count by type in **876 calls** (89 of 190 records);
- **product 0, a removal by type present: 268 calls, 30 records** (29 direction "to"); of those, **182 "to"
  calls (23 records) hold a whole-provision or in-part removal**, not only words;
- summed over the 190 records: product 2,025 relations; by type 5,440 = **whole provision 2,762, in part 215,
  words only 2,366, qualified 97** (prospective, temporary, conditional, for specified purposes). Of the product's
  2,025, **540 are words-only** ("words repealed"), **23 qualified** ("repealed (prosp.)") and **7 false
  positives**;
- the other direction: **2 records (9 "to" calls)** have a product count above 0 and no whole or in-part
  provision removal (one words-only, one "power to amend or revoke conferred").

**The wording this count feeds is wrong in both directions today.** `search_scope` writes "N relation(s) are
repeals or revocations: those establish that the named provision is no longer in force". For a counted "words
repealed" or "repealed (prosp.)" relation that is untrue, and for an uncounted "omitted" whole provision the
instrument is left out of `_currency_limb`'s repeal list and the footer's sources.

**What the answers said (`p328_answers.py`, `p328_negs.py`, `p328_rels.py`, `p328_ctx.py`).** In the 83 run-turns
where a "to" record's count moves from 0 for a whole or in-part removal, I read all **61 sentences that deny a
removal**, against the record's own removal rows: **12 sentences in 9 runs over 3 turns are false negatives**
("no repeal or revocation relations were retrieved" for an instrument whose record holds a whole-provision
"omitted": 6375 t2, 10 sentences in 7 runs, on two instruments; scripted 6406 t1, 1; scripted 6383 t1, 1);
**2 unclear** (a sentence about "these instruments" as a group); **1 hinges on the words-only decision**
(decision 3); **the other 46 are true or about another instrument** (e.g. "no repeal of regulation N recorded"
where the record removes a different regulation).

**Lever (proposed, decision 2):** classify by type (`p328_class`'s families and qualifiers, with the
not-the-subject exclusions), and split the count into whole-or-part provision removals (the only class the "no
longer in force" sentence may claim), words-only removals (a text amendment), and qualified removals (stated
with the qualifier). **What it moves, from the stored inputs** (the build's dry run must redo this with the
built slimmer): 23 records and 182 calls gain a provision removal; 2 records and 9 calls lose the "no longer in
force" claim; 540 words-only and 23 qualified relations change class; the 3 false-negative turns would have
been handed the omissions. **Graders:** `replay_report currency` reads the stored count, so no stored verdict
moves until a re-slimmed run; `negcurrency`'s `_nc_is_removal` already counts "omitted" and "ceases" and
excludes "words omitted", which is the same line as the proposed whole/words split.
**P3.33 should reuse this classification:** "revocation of earlier commencing SSI" is not a revocation of the
subject.

## 3. P3.32 and P3.33: the "shared harvest". **P3.32 no-go now; P3.33 go, as a stored flag with its date.**

**The premise is only partly true.** P3.32's fields come from `/introduction/made/data.xml`, the file P3.31's
harvester already reads. P3.33's revocation does not: the introduction file carries only *unapplied* effects
(11 of 60 files; "revoked" in 5), legislation.gov.uk's editorial backlog, not the record. And extent is in
neither (below). So there is no single pass serving all three.

**P3.32: what the introduction file carries (`p332_sample.py --live`, `p332_elements.py`, `p332_fields.py`).**
A seeded stratified sample of 60 held instruments, 10 in each of SSI 1999-2006 / 2007-2016 / 2017-2026 and
UK SI 1987-1999 / 2000-2012 / 2013-2026; 60 of 60 answered 200 (521 KB):

| field | element | carried |
|---|---|---|
| PDF-only record (no prelims, a `ukm:Alternative` PDF link) | — | 10 of 60 (census: 15,981 of 86,744 held, 18%; 5 of 10 recent SSIs) |
| made date | `ukm:Made@Date` (ISO) and `<MadeDate><DateText>` | 50 of 50 with XML |
| laid date | `ukm:Laid@Date`, `@Class` (`ScottishParliament` 16, `UnitedKingdomParliament` 13) | 29 of 50 |
| coming into force | `ukm:ComingIntoForce/ukm:DateTime@Date` (ISO, one date each) | 39 of 50; 5 more say only "in accordance with article/regulation N" |
| procedure | the preamble's words; an `<Approved>` element once | **affirmative wording 9** ("a draft ... laid before and approved by resolution", 8; "Approved by the Scottish Parliament", 1); **a laid date only 28** (negative procedure is then an inference, not a statement); **neither 13** (commencement and local orders) |
| consultation | the preamble ("consulted", "after consultation with") | 8 of 50 (one false hit on an Act's title removed by hand) |
| extent | `RestrictExtent` | **0 of 60** (not in this file; an SI's `/contents/data.xml` carries it, root and per provision, 2 of 2 probed) |

Every procedure call was read by hand; my first regex missed the `<Approved>` form. **Demand: 0 of 196 turns ask
an SI's procedure or its own coming-into-force date** (`p332_turns.py`, 17 hits read); the nearest are three
6409 turns about a commencing SSI, P3.21's ground. **If built**, the pass is the P3.31 harvester's own file:
86,744 reads (70,762 with XML), median 132 ms and 7.5 KB a read, so about 10-18 hours at a 0.3-0.6 s gap and
about 0.65 GB; procedure stated only in the record's words, never as "negative procedure" (decision 5).

**P3.33: what a revocation flag needs (`p333_revoked.py --live`, `p333_s95.py --live`).**
- **Signal.** A whole-instrument revocation is a removal type with no qualifier on the instrument itself: in LEX
  `changed_provision_url` is the instrument's URL and the label has no number ("Regulations", "Order",
  "Instrument", even "Act" on an SI); in the feed `AffectedProvisions` has no number. 20 of the sample (both
  sources, 20 reads and 20 LEX calls): 3 whole (2 revoked by another instrument, 1 "ceases to have effect" by its
  own provision), 1 with partial removals, 16 none; **the two sources agree on 20 of 20**.
- **Value on P3.33's acceptance set.** The record's 37 instruments made under the provision P3.31's acceptance
  used (37 reads): **1 wholly revoked (dated), 9 with partial removals, 27 none**; LEX's stored records agree on
  24 of the 24 that overlap.
- **The date is the feed's, not LEX's.** A feed effect carries `ukm:InForce@Date` and `@Qualification` for a
  revocation exactly as for a commencement (P3.21's parser reads them), plus `Created`/`Modified`; LEX rows carry
  no date. One revocation in the sample was recorded about three years after it was made: a stored flag must be
  refreshed, and "not recorded as revoked" is not "in force" (B4's rules hold).
- **Calls for a pass.** Per instrument: one affected-feed read each (every one of the 59 per-instrument or
  per-Act feeds read fits one page; median 60 ms, 1.3 KB), 86,744 reads, about 8-15 hours. Type-wide: SSIs 64,459 effects = 129 pages of 500 (page 1:
  1.04 MB, 6.4 s); UK SIs by affected year 18,016 (1995), 22,674 (2005), 23,802 (2015), so about 860,000 effects
  and 1,700 pages if every year is like those three (an estimate; the UK-SI-wide request timed out at 60 s), about
  1,850 page reads in all, every effect type included. The feed's own `first` link names `sort=modified`, but the
  Modified values on the pages I read were not in order, so a modified-since daily delta is **not established**.

## 4. P3.42 with P3.26: extent per provision. **P3.42 no-go now; P3.26 go, with one addition.**

**Source.** `/<id>/contents/data.xml` carries `RestrictExtent` on every part, chapter, section and schedule
(one read an Act; median 55 KB, largest 1.08 MB).

**The 20 UK Acts most worked on in stored turns** (`p342_acts.py`: distinct sessions, then turns; only 6 recur
across sessions), plus the probe Act (`p342_read.py --live`): **13 of the 20 carry per-provision extent; 7 do
not** (repealed older Acts held only as enacted metadata or PDF: four reached through a second-hop redirect,
one 404). Over the 14 with extent (A1-A7, A9, A15, A17-A21), **2,718 of 5,277 sections (52%) differ from their
Act's extent, in 8 of the 14 Acts** (from 2 of 382 to 1,034 of 1,161 sections). LEX's instrument-level extent
equals legislation.gov.uk's Act-level extent for 11 of the 13; for the other 2 LEX has none (`[]`).

**Vocabulary (P3.26's).** legislation.gov.uk's provision codes over every contents file read (18 Acts, 10,846
extents): `E+W+S+N.I.` 2,907, `E+W` 4,016, `E+W+S` 1,753, `S` 1,435, `N.I.` 735. LEX's stored rows: 39,133 rows,
9 values, **0 unrecognised tokens** (re-counted over all 66 directories with the built `_extent_tokens`).
**Dry run with the built `_matches_jurisdiction`:** fed legislation.gov.uk's codes, it maps `N.I.` to an
unrecognised token, so a Northern Ireland filter drops `E+W+S+N.I.` and `N.I.` and a UK-wide filter drops
`E+W+S+N.I.`. P3.26's trap is latent on LEX's data and would bite at once on these codes.

**Turns whose jurisdiction would have turned on it: 0.** Every UK Act cited at section level in a turn that ran
under a jurisdiction filter (48 turns, all `scotland`) was read (4 more contents reads; `p342_filtered.py`):
**199 section citations, 0 outside Scotland's territory.** Without the filter condition (`p342_turns.py`), 14
turns cite a section whose extent differs from its Act's; in 6 (one session and its scripted variant) the
section is England and Wales only and my heuristic called the jurisdiction Scotland from the answer's own words.
By hand: that session ran with no filter, asks what a UK Act's term means, and the lawyer marked jurisdiction
"yes"; **none turned on the extent**, though 0 of 31 runs say those sections are England and Wales only
(`p342_read_answers.py`).

## 5. P3.30: search-result rows as the only route to a derivation. **No-go: superseded by P3.31.**

`p330_routes.py`, every stored run: **1,274 answer citations of a secondary instrument** (run x turn x
instrument). Route by which it reached the Worker in that turn: text read, section search, lookup or the
made-under tool **1,163 (91%)** (1,101 covered by the record's parsed powers); **a search-result row only: 30
(2.4%)** (28 covered by the record), in 4 turns and 5 runs; no tool in that turn 81 (cited from earlier turns).
**Derivation claims naming an instrument (`replay_report.derivation_claims`): 21, all through a deep route.**
Of the 30 row-only citations, **0 rows quote a recital and 0 carry a derivation claim**; checked the other way,
the 5 answers concerned assert 0 and filter 0 derivation sentences of any kind.

---

## What I did not do

- No product code, no test, no seam draw, no server, no replay. Rule 5 does not bite.
- D's item 3 (P3.12's paragraph route) and item 5 (P4.24): agents A and D.
- Not established: whether legislation.gov.uk's `sort=modified` gives a usable daily delta (P3.33's refresh);
  whether an SI's *current* introduction file carries extent; per-instrument recording lag beyond one example.
- Not graded: whether the 21 derivation claims (P3.30) or the provision-level claims (P3.41) are true; only
  their route.
- P3.28's acceptance steps (`replay_report currency` before and after, unit tests at the counter) belong to the
  build.

## Decisions for the user

1. **P3.41 (provision-level amendments).**
   (a) **Recommended:** drop it (`[-]`): 0 of 196 turns ask; on 20 of 20 provisions the endpoint added,
   contradicted and lost nothing against the record already fetched, and it cannot reach 34 relations on 9 of
   them. (b) Park it at the bottom of the queue until pilot traffic shows a provision-level question.
   (c) Rebook it as a code filter of the instrument-level record by provision, for when such a question arrives.
2. **P3.28's lever.**
   (a) **Recommended: both.** Classify by effect type (families, qualifiers, the not-the-subject exclusions) and
   split the count, so "no longer in force" is said only of whole or in-part provision removals; deterministic,
   with unit tests at the counter and a dry run over the 1,709 stored calls. (b) Widen the families only, wording
   unchanged: fixes the 23 missed records but keeps the over-claim on 540 words-only and 23 qualified relations.
   (c) Leave it: the 3 false-negative turns stand.
3. **Words-only removals ("words omitted", "words repealed").**
   (a) **Recommended:** a class of their own, stated as text amended, never as "no longer in force".
   (b) Count them as removals, as "words repealed" is today. (c) Leave them out entirely, as the
   `negcurrency` grader does.
4. **P3.28's data route (legislation.gov.uk's effect types).**
   (a) **Recommended:** strike it from the row: the type strings are LEX's, 18,926 of 18,926. (b) Keep the feed
   as a cross-check where P3.21 already reads it.
5. **P3.32 (an SI's own dates, procedure, consultation).**
   (a) **Recommended:** park it: 0 turns ask. If built: P3.31's harvester extended over the file it already
   reads (about 10-18 hours), procedure only in the record's words. (b) Build it now with P3.33.
6. **P3.33 (revocation flag).**
   (a) **Recommended:** go, after P3.28: a stored flag per instrument from the affected feed (the date and
   qualification with it), reusing P3.28's classification, refreshed with the record; the one-time pass
   per instrument (about 86,744 reads) unless a type-wide delta is shown to work. (b) A live check per listed
   instrument (about 40 proxy reads a made-under question, at P3.21's slow-read rate). (c) Park: on the
   acceptance set it would change 1 instrument wholly and 9 in part.
7. **P3.42 and P3.26.**
   (a) **Recommended:** park P3.42 (0 turns turned on it); build P3.26 now (P3, deterministic), treating an
   unrecognised token as unknown **and** adding `N.I.` as Northern Ireland, so a later P3.42 can feed
   legislation.gov.uk's codes. (b) Build both. (c) Park both.
8. **P3.30.**
   (a) **Recommended:** drop it (`[-]`), superseded by P3.31: 30 row-only citations, 0 with a recital or a
   derivation claim. (b) Park it.
9. **Re-slotting G's rows by measured value** (within the by-severity order): (a) **Recommended:** P3.28 first
   (a measured defect, deterministic, $0), then P3.26, then P3.33; P3.32 and P3.42 parked; P3.41 and P3.30 dropped.
   (b) Keep them where the order line has them and annotate only.
