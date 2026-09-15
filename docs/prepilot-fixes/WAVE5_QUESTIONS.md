# Wave 5 — the external questions, drafted and ready to send

**Status: P5.1 mostly ANSWERED HERE 2026-09-15 by reading the API's own OpenAPI spec — see below. P5.2 and P5.3 drafted, NOT YET SENT.** These need a human to send them;
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

## P5.2 — internal/product: the Scottish case-law corpus

> The National Archives *Find Case Law* corpus does not contain the **Court of Session** or
> the **Sheriff Courts**. For a Scottish Government legal audience this is the top substantive
> content gap of the pre-pilot, and in at least one session it stopped being a coverage gap
> and produced a **wrong answer** (6375) rather than a "not found".
>
> Raised independently by three lawyers during the pre-pilot: AlistairC (*Clark* absent,
> 6359), CambeulW (recency bias in what is returned, 6363) and EmmaM.
>
> The engineering half — disclosing the gap in the answer rather than answering around it —
> is P2.4 and is not blocked on this. The question here is a product/procurement decision:
> **is there a licensable source of Court of Session and Sheriff Court decisions we can
> index, and is anyone willing to buy it?** A decision either way should be recorded; "no"
> is an answer that makes P2.4 permanent rather than interim.

## P5.3 — to the LEX team: coverage rules and refresh cadence

> We need to be able to tell a lawyer accurately why something was not found. At the moment
> we can only say "not found in the index", which is vague enough to be unhelpful and, if the
> index is simply behind, misleading.
>
> Verified absent or incomplete as at September 2026:
>
> | identifier | what we see |
> |---|---|
> | `ukpga/1962/47` (Education (Scotland) Act 1962) | 404 |
> | `ssi/2026/170` | 404 |
> | `ssi/2025/119` | record exists, `text` empty |
> | Education (Scotland) Act 1945 | stub-only provisions |
>
> 1. What are the index's **coverage rules** — is there a date floor, a category exclusion,
>    a repealed-instrument policy?
> 2. What is the **refresh cadence** from legislation.gov.uk, and what is the typical lag for
>    a newly-made SSI?
> 3. Is a 404 distinguishable from "not yet ingested"?
>
> The purpose is narrow: so our "we could not find this" message can name the real reason.

---

## When a reply arrives

1. Paste it verbatim into `SESSION_LOG.md` under the session that received it.
2. Tick the row in `FIX_PLAN.md` and record the consequence, not just the answer — P5.1 in
   particular either spawns a new row (retrieval) or makes **P2.3 permanent** (disclosure).
3. If the answer to P5.1 is "no relationships", say so in P2.3's row explicitly. A later
   session must not re-open the question on the assumption that nobody asked.
