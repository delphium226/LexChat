# Wave 5 — the external questions, drafted and ready to send

**Status 2026-09-15: P5.1 and P5.3 LARGELY ANSWERED HERE** by reading the API's own OpenAPI spec, `/api/stats` and `/healthcheck`, and by sampling coverage directly. **P5.2's facts are established too** — the National Archives gap is verified as total, and LEX holds case-law collections its API does not expose, so ask before buying. What remains is a short, specific list for the LEX team under each row, plus one product decision. NOT YET SENT. These need a human to send them;
nothing in the codebase can. They have been idle across five sessions, and the plan says to
open them early precisely because they block nothing and have unknown lead time.

Ledger rows: **P5.1** (LEX relationships), **P5.2** (Scottish case-law corpus), **P5.3**
(corpus currency). Each row's acceptance is *a recorded answer in `SESSION_LOG.md`* — so when
a reply arrives, paste it into the log and tick the row.

Why it matters that these go out now, rather than when the code work reaches them:

- **P5.1 determines whether the largest bucket is buildable at all.** B3 is "AILA asserts a
  relationship between instruments it never retrieved" — what commences what, what amends
  what, what was made under which enabling power. If LEX exposes those relations, B3 gets a
  retrieval fix. If it does not, B3 is **permanently a disclosure**, and P2.3 stops being a
  holding fix and becomes the answer. That is a different piece of work, and the answer
  changes which one gets built.
- **P5.2 is procurement, not engineering.** No amount of code puts the Court of Session in a
  corpus that does not contain it.
- **P5.3 changes what B5's negative is allowed to *say*.** "Not found in the index" is only
  honest if we know what the index covers and how often it refreshes. Invariant 1 requires the
  negative to be true, not merely cautious.

---

## P5.1 — are instrument relationships retrievable? **MOSTLY ANSWERED HERE, 2026-09-15**

**Four of the five questions are answered, and we answered them ourselves.** The API
publishes an OpenAPI spec at `/openapi.json` documenting **13 endpoints. We call 3.**
Nobody had looked. Re-run the evidence with `python -m tools.lex_probe`.

| | endpoint | we call it |
|---|---|---|
| | `POST /legislation/search` | **yes** |
| | `POST /legislation/section/search` | **yes** |
| | `POST /legislation/text` | **yes** |
| **1** | `POST /amendment/search` | no |
| **2** | `POST /amendment/section/search` | no |
| 3 | `POST /legislation/lookup` | no |
| 4 | `POST /legislation/section/lookup` | no |
| 5 | `GET /legislation/proxy/{legislation_id}` | no |
| 6 | `POST /explanatory_note/legislation/lookup` | no |
| 7 | `POST /explanatory_note/section/lookup` | no |
| 8 | `POST /explanatory_note/section/search` | no |
| 9 | `GET /api/stats`, `GET /healthcheck` | no |

### What is answered

**Q2 — amendment relations: YES, fully.** `/amendment/search` takes a `legislation_id`
and a **`search_amended` flag that is the direction of the relation** — `True` returns
amendments made *to* it, `False` amendments it *makes*. `/amendment/section/search` does
the same at provision level from a `provision_id`. Each row is provision-to-provision
with a resolvable URL on **both** sides:

```jsonc
{ "changed_legislation": "asp/2018/9",   "changed_provision": "sch. 5 para. 7",
  "changed_provision_url":   "…/asp/2018/9/schedule/5",
  "affecting_legislation": "ssi/2020/295", "affecting_provision": "reg. 2(c)",
  "affecting_provision_url": "…/ssi/2020/295/regulation/2/c",
  "type_of_effect": "coming into force" }
```

**Q3 — commencement: YES**, as `type_of_effect`. Over 1,358 rows sampled from five
instruments: **246 "coming into force"** and **43 "Commencement Order"**.

**Q4 — repeal / revocation: YES**, same field: 62 "repealed", 30 "words repealed",
6 "revoked", 3 "words revoked", 3 "repealed in part".

**Q5 — the route:** `/openapi.json`. There was never a hidden route; there was a
published spec we had not read.

**Q1 — enabling power ("made under s.X"): NO structured route found**, and this is the
one to actually ask about. Not in `/legislation/lookup`'s fields, and explanatory notes
are an **Act-level** resource here — `/explanatory_note/legislation/lookup` returns notes
for `asp/2018/9` and **404 for `ssi/2020/295`** — so they cannot say what an SI was made
under. Commencement rows relate a commencement SSI to the Act it commences, which is a
species of the relation but not the general case: a substantive SSI made under s.95 need
not appear in the amendment data at all.

### The finding that costs us nothing to fix

`description` on a search or lookup result **states the relationship in prose, with the
date** — and `_slim_search_results` strips it deliberately, so the model never sees it:

> *"These Regulations bring sections 31 and 36 and schedules 5 and 10 of the Social
> Security (Scotland) Act 2018 into force on 8 October 2020."*

**5 of 10 sampled results** carried commencement, amendment or enabling-power language
there. The comment in `lex.py` calls the field "verbose and redundant once Phase 2
retrieves actual section text" — true for the *text*, false for the *relationships*,
which no section text states. This is now **P3.6**.

### Corrections to what this file first said

- ~~"`/legislation/text` returns a record for `ssi/2025/119` with an **empty `text`
  field**… a stub record is indistinguishable from absence at the tool boundary."~~
  **Wrong, twice over.** (a) The response is `{legislation, full_text}` — the `text` key
  is on the nested object and is empty for *everything*, including Acts held in full, so
  reading it as the text says the whole corpus is a stub. (b) A genuine stub is
  **explicitly signalled**: `full_text` is the literal sentence *"No text content
  available for this legislation."* (47 chars), and `/legislation/section/lookup` returns
  **404** where a held instrument returns 200. Absent is different again —
  `/legislation/lookup` for `ukpga/1962/47` is a flat 404. Three states, all
  distinguishable.

### What is left to ask the LEX team — much narrower

> We have read `/openapi.json` and probed `/amendment/search`, so this is a short list.
>
> 1. **Enabling power.** Is there any route to "this instrument was made under section X
>    of that Act", or the reverse, "list the instruments made under this power"? It is the
>    one relation we cannot find, and it is the single largest class of error in our
>    pre-pilot — the model infers it from search-result adjacency and is confidently wrong.
> 2. **The commencement date.** `/amendment/search` gives us *which* SSI commenced *which*
>    provision, with no date on the row. We can retrieve the SSI and read the date from its
>    text, but is the date available directly?
> 3. **`type_of_effect: null` on 19%** of the rows we sampled (261 of 1,358). Is that
>    "effect not classified", "data not yet loaded", or something we should filter out?
> 4. **Completeness and paging.** Is `/amendment/search` authoritative and complete for an
>    instrument, and is `size` the only control — is there paging beyond it?
> 5. **Is the `"No text content available for this legislation."` sentinel a stable
>    contract** we can detect on, or an implementation detail? We would rather branch on a
>    field than a magic string.

## P5.2 — the Scottish case-law corpus **FACTS ESTABLISHED 2026-09-15; the decision is yours**

This row's acceptance is *a recorded decision*, which is not mine to make. What follows is
the decision brief: the gap is now measured rather than asserted, and it has changed shape.

### The gap is total, and it is verified

| probe | result |
|---|---|
| `atom.xml?court=csoh` (Outer House) | **HTTP 400** — *"csoh is not one of the available choices"* |
| `atom.xml?court=csih` (Inner House) | **HTTP 400**, same |
| `atom.xml?query=Court of Session` | 200, 50 results — **not one of them a Scottish judgment**: 20 EWHC, 11 UKFTT, 5 EWFC, 4 UKSC, 3 UKUT, 3 EWCA, 2 EWCOP, 1 EAT |

The Court of Session is not a court in the National Archives' taxonomy. The full facet
lists **42 court codes — 17 England & Wales, the rest UK-wide tribunals — and not one
Scottish or Northern Irish.**

**But the blunt version of this is false, and saying it would be its own error.** Scottish
appeals that reached the **UK Supreme Court are indexed**: `court=uksc` returns *Daly v His
Majesty's Advocate (Scotland)*, *ABC v Principal Reporter and another (Scotland)* and *X v
Lord Advocate*. What is missing is everything below that — **Court of Session (Inner and
Outer House), Sheriff Appeal Court, Sheriff Courts and the High Court of Justiciary** —
which is where the overwhelming majority of Scots law is made. Told "Scottish courts are
not indexed", a lawyer would distrust a sound UKSC result; told the precise version, they
also learn where the one real Scottish route is.

### The failure mode is a wrong answer, not an empty one

That middle row is the whole problem. A Scots-law case-law question does not come back
empty — it comes back with **fifty English judgments that happen to mention Scotland**, and
the model answers from them. That is 6375 exactly: English common-interest privilege
analysed as Scots law. An empty result is a disclosure; a full one of the wrong
jurisdiction is a trap, and it is why **P2.4 matters more than a coverage gap normally
would.**

### Every court AILA can filter on is non-Scottish

The Court filter offered to a **Scottish Government** lawyer has 14 options — UK Supreme
Court, Privy Council, Court of Appeal (Civil and Criminal), Administrative, Chancery,
Family, Commercial, Patents, TCC, Upper Tribunal, Immigration & Asylum, Lands Chamber,
Employment Appeal — and **not one Scottish court**. That is not a defect to fix in the
filter (the codes are correct and the tool schema already warns against inventing others);
it is the product gap stated plainly, and it is visible to every user on every research
query.

### The lead that may change this from procurement to an API request

LEX's own `/healthcheck` reports a case-law corpus in its vector store:

```
caselaw            69,970 points
caselaw_summary    61,107 points
caselaw_section  4,723,735 points
```

and `/openapi.json` exposes **no case-law endpoint**. The conventional names that would
mirror the documented ones — `/caselaw/search`, `/caselaw/lookup`, `/caselaw/text`,
`/caselaw/section/search` — all return **404**. So the corpus exists inside a system we
already call and is not reachable through its published contract.

**But this route is probably closed, and the row's real subject is now finding an
alternative.** The user recalls (2026-09-15) that **LEX used to expose case law and has
since disabled access**, and that **Scottish courts were not represented in that data
anyway**. Recorded as recollection, not verified — though it is consistent with what the
probe found, which cannot tell "disabled" from "never exposed".

So the LEX question shrinks to a one-line confirmation, and even a "yes" would probably not
deliver the Court of Session. **The substantive work is sourcing Scottish case law
elsewhere.**

### The decision, stated so it can be taken

> 1. **To the LEX team — now a confirmation, not an open question:** we understand case-law
>    access was available and has been withdrawn, and that Scottish courts were not in that
>    data. Is that right, is it coming back, and did it ever include the Court of Session?
>    One line either way; it closes the question rather than opening it.
> 2. **The real one — which alternative source?** Three candidates, **none assessed**:
>    **BAILII**, which carries `ScotCS` (Court of Session), `ScotHC` (High Court of
>    Justiciary) and `ScotSC` (Sheriff Court) and is the obvious technical fit — **read its
>    terms of use before designing anything, as they restrict automated access**; the
>    **Scottish Courts and Tribunals Service** (`scotcourts.gov.uk`), which publishes
>    opinions directly and should be checked for a feed or API; and the commercial providers
>    (Westlaw, LexisNexis), which are a licence cost and a procurement decision. Whatever is
>    chosen must clear the **internet-restricted target's whitelist**. Raised independently
>    by three lawyers in the pre-pilot: AlistairC (*Clark* absent, 6359), CambeulW (recency
>    bias, 6363) and EmmaM.
> 3. **To the National Archives, separately: what is the corpus's date coverage?**
>    Judgments exist back to **1965**, but the Atom feed caps at 50 results for every window
>    and the search page exposes no total, so we could not measure density before ~2000 from
>    outside. CambeulW raised recency bias in the pre-pilot (6363) and it may well be sound —
>    it is currently **unmeasured**, and if real it affects English research too, not only
>    Scots. Is the corpus comprehensive from a particular year, with a selected set before it?
> 4. **Either way**, record the answer. A "no" is a decision too — it makes **P2.4**
>    permanent rather than interim, and P2.4 should be built on that footing.

The engineering half is **P2.4** and is **not blocked** by any of this: whatever the corpus
turns out to hold, an answer drawing on English authority for a Scots-law question must say
so, in code, every time. Today AILA discloses it in 6341, 6385 and 6407 — and not in 6375,
where it mattered most.

## P5.3 — coverage rules and refresh cadence **LARGELY ANSWERED HERE, 2026-09-15**

Answered the same way as P5.1: `GET /api/stats` and `GET /healthcheck` are public and
undocumented in our notes, and coverage is directly measurable by sampling
`/legislation/lookup`. Reproduce with `python -m tools.lex_probe --coverage`.

### The corpus, and how fresh it is

```
GET /api/stats   acts_and_sis 220,022 · provisions 2,107,361 · amendments 2,580,915
                 explanatory_sections 93,180 · last_updated "14:05 UTC"
```

**The index is refreshed daily and is current.** Records carry a `created_at`, and the
newest observed across a 1,162-record sample was **2026-09-15T02:17** — today, this
morning. Ingestion runs land around 02:00–02:30 UTC. `uksi/2026/772` (a Sentencing Act
2026 commencement SI) was created **2026-09-08**. So staleness is *not* the problem.

### The problem is per-instrument gaps, and they are large for 2026

Sampled by `/legislation/lookup`, which is a definitive held/absent test:

| series | held |
|---|---|
| **ASP 2025 and 2026** (Scottish Acts) | **100%** (10/10) |
| SSI 2025 | **85%** (17/20) |
| **SSI 2026** | **~5–27%** — 1/20 random over 1–170; contiguous bands: 1/15, 4/15, 2/15, 0/15 |
| **UK SI 2026** | similarly sparse — 1/15, 2/15, 1/15, 2/15 across four bands spanning 1–774 |
| UK Public General Acts 1962 | **6/16** (a sample around `ukpga/1962/47`) |

Two things follow, and both matter more than the cadence question we set out to ask:

- **2026 secondary legislation is only partially present** — roughly one instrument in
  five — while the index refreshes daily. The gaps are spread evenly across the year, not
  concentrated at either end, so this is not "the last few weeks haven't loaded yet".
- **Old material is patchy per instrument, not cut off by date.** `ukpga/1962/47` is
  absent, but `ukpga/1962/41`, `/42`, `/45`, `/50`, `/51` and `/55` are all held. So the
  absence of the Education (Scotland) Act 1962 is **not** a date rule, and "we don't hold
  pre-19xx" is the wrong story to tell a lawyer.

### What this means for B5's wording — the reason the row exists

**A "not found" for a 2026 SSI is far more likely to be a coverage gap than an absence in
law.** On these numbers, roughly four out of five 2026 SSIs are simply not in the index.
Telling a lawyer "no such instrument was found" without that caveat is close to telling
them it does not exist. P2.2's negative must distinguish *we searched and the index does
not hold it* from *it does not exist*, and for 2026 secondary legislation the honest
default is the former.

### P5.3's original claims, re-verified

| claim | verdict |
|---|---|
| `ukpga/1962/47` → 404 | **confirmed** — and it is a per-instrument gap, not a year cliff |
| `ssi/2026/170` → 404 | **confirmed** — consistent with ~20% coverage of SSI 2026 |
| `ssi/2025/119` record exists, text empty | **confirmed**, and it is an explicit stub — see P5.1's correction |
| stub-only provisions for the Education (Scotland) Act 1945 | not re-tested |

### A method note, because it cost two wrong conclusions

Point lookups are a **bad census instrument** and misled this probe twice. Twelve misses
across `ssi/2026/{1..250}` read as "no 2026 SSIs at all"; a 20-point sample of UK SI 2026
returning 0 read as "nothing from 2026", while `uksi/2026/772` was in the index the whole
time and was created a week ago. In a corpus with ~20% coverage, a sparse sample of
absences proves nothing. **Cross-check a lookup census against `/legislation/search` before
concluding anything about coverage** — the same discipline the rest of this work applies to
detectors.

### What is left to ask the LEX team

> 1. **Why is 2026 only ~20% ingested when the index refreshes daily?** Is a backfill in
>    progress, is there a lag between an instrument being made and being indexed, or is
>    something filtering them out? This is the single fact that most changes what we can
>    honestly tell a lawyer about a "not found".
> 2. **Is the patchiness of older material (6 of 16 sampled 1962 Acts) inherited from
>    legislation.gov.uk, or a LEX-side rule?** We would like to tell users *why* something
>    is missing, and the two have different answers.
> 3. **Is there a published coverage statement** — series covered, date floor, exclusions —
>    that we can point users at?
> 4. **`/healthcheck` reports case-law collections** (`caselaw` 69,970 points,
>    `caselaw_section` 4,723,735, `caselaw_summary` 61,107) **but `/openapi.json` exposes no
>    case-law endpoint.** Is that corpus reachable, and does it include the Court of Session
>    and the Sheriff Courts? **See P5.2 — this may change that question from procurement to
>    an API request.**

## When a reply arrives

1. Paste it verbatim into `SESSION_LOG.md` under the session that received it.
2. Tick the row in `FIX_PLAN.md` and record the consequence, not just the answer — P5.1 in
   particular either spawns a new row (retrieval) or makes **P2.3 permanent** (disclosure).
3. If the answer to P5.1 is "no relationships", say so in P2.3's row explicitly. A later
   session must not re-open the question on the assumption that nobody asked.
