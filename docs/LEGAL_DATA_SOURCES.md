# Legal Data Sources — legislation and case law

Reference for what the legislation bot can and cannot retrieve: the data we hold, the gaps
in it, and where each gap could be filled from. The parliament bot's sources are in
[`parliament/PARLIAMENTARY_DATA.md`](parliament/PARLIAMENTARY_DATA.md); base URLs, auth and
endpoint traps for the APIs we call are in the `external-apis` skill
(`.claude/skills/external-apis/SKILL.md`).

> **Status as of 2026-10-02.** Fix status changes faster than this file. Where a row names a
> FIX_PLAN row, [`prepilot-fixes/FIX_PLAN.md`](prepilot-fixes/FIX_PLAN.md) is authoritative.
> "Potential sources" are leads. The only ones verified live are the LEX endpoints, the
> SCTS judgments API (§3) and the National Archives' published API (§4). Every non-LEX, non-National-Archives source would also need
> adding to the internet-restricted target's whitelist
> ([`NETWORK_AND_DEPENDENCIES.md`](NETWORK_AND_DEPENDENCIES.md)).

---

## 1. What we call today

| Source | What it gives | Called by |
|---|---|---|
| **LEX API** (`lex.lab.i.ai.gov.uk`) | UK legislation: search, section search, full text, amendment/commencement/repeal relations (P3.5), held/absent lookup (P3.7). 6 of its 13 documented endpoints | `search_legislation`, `search_legislation_sections`, `get_legislation_text`, `get_legislation_changes`, `lookup_legislation` |
| **The National Archives — Find Case Law** (`caselaw.nationalarchives.gov.uk`) | England & Wales and UK-wide judgments; Scottish appeals to the UK Supreme Court. 42 court codes, none Scottish or Northern Irish. **Licence question open (§4): TNA requires a free licence for AI/LLM products** | `search_case_law`, `get_case_law_text` |

One older fix shaped every coverage number below. Until **P1.1** (2026-09-14) the
jurisdiction filter dropped every legislation result whose territorial extent was stated, so
351 of 974 filtered searches returned nothing. Any coverage impression formed before then was
based on an arbitrary subset of the data.

---

## 2. The gaps

"Recent work" says what has landed. Unless marked *branch only*, it is live on `main`
(P3.7 since `v2026.09.3`, the rest since `v2026.09.1`). Most of these fixes make the product
honest about a gap. Only the SCTS lead in §3 would actually fill one.

### 2.1 Data that doesn't exist in anything we call

| Gap | What it costs us | Recent work | Potential sources |
|---|---|---|---|
| **Scottish case law below the UK Supreme Court**: Court of Session, Sheriff Appeal Court, Sheriff Courts, High Court of Justiciary (Northern Irish courts also absent) | Wrong answers, not empty ones. A "Court of Session" search returns 50 English or UK-wide judgments and the model answers from them (6375) | **Disclosure fixed, data still missing.** **P2.4** (17 Sep): when an answer draws on case law, code adds a footer naming exactly which Scottish courts aren't covered, and that UK Supreme Court appeals are. **P4.4** removed the court filter, whose options were all non-Scottish. **Source found 2026-10-02** (§3): **P5.2** is now a question of building a tool and whitelisting it, not of buying data. The build is booked as **P3.20** | **SCTS judgments search API (recommended, §3):** 13,213 Scottish judgments from 1998, full-text search, Open Government Licence. **SCTS RSS feed:** the latest 200 only. **Fallbacks:** BAILII (copies SCTS; its terms restrict automated access), Westlaw / LexisNexis / vLex (licence). **Northern Ireland is not in SCTS:** BAILII or Judiciary NI |
| **Commencement dates and in-force status** | "Was s.X in force on date Y?" can't be answered from data. LEX `status` (renamed `text_version`) is the text version held, not currency, and `/amendment/search` rows carry no date | **Partly fixed.** **P3.5** (16 Sep): `get_legislation_changes` retrieves *which* instrument commenced, amended, repealed or revoked *which* provision, but not *when*. **P2.5** (16 Sep) stops the model reading in-force status from `text_version`. **P1.2** stopped the `current_only` filter pretending to filter. **P4.18** (*branch only*, 2 Oct) fixed a footer that said no change record was consulted when one was. ~~Open: P3.6 (the dated `description`), P3.19 (the change tool loses which provision made which change), P3.21 (fetch the commencing instrument's date in code).~~ **P3.19** done; **P3.21 and P3.6 done** (*branch only*, Session 41, 8 Oct): a commencement made by another instrument now carries the date legislation.gov.uk's Changes to Legislation record gives it, with its qualification, read through LEX's proxy (a date earlier than the commencing instrument's made date is refused), and search rows keep a 600-character `description`. **Measured 6 Oct (batch 8 D, P5.4 (c)):** legislation.gov.uk's effects feed dates 8,144 of the 8,180 stored commencement relations exactly, with the qualification, and reads identically through LEX's `/legislation/proxy` (no new whitelist entry); LEX's `description` states a readable date for 65 of 157 commencing instruments and contradicts the feed on 14% of the relations both date. Decided: the feed through the proxy is P3.21's date source | **legislation.gov.uk** "Changes to Legislation" effects data. A second hop into the commencing SSI's text through LEX `/legislation/text`, which works today. LEX `description` (P3.6). The LEX team (question drafted in [`WAVE5_QUESTIONS.md`](prepilot-fixes/WAVE5_QUESTIONS.md)) |
| **Point-in-time versions** of a provision | We seem to get only the one version LEX holds; "as it stood in 2015" can't be answered (not probed in LEX) | **P5.4** booked: probe legislation.gov.uk | **legislation.gov.uk** date-suffixed and `/enacted` URLs. The LEX team |
| **Enabling power** ("made under s.X") | Was the largest error class. LEX recitals exist for 18 of 25 pre-1990 UK SIs and 0 of 28 SSIs (`python -m tools.lex_probe --enabling`) | **Disclosure fixed, data still missing.** **P2.3** (16 Sep): the claim is allowed only where a recital was retrieved, otherwise the product says it couldn't be verified. Turns making an unverified claim fell from 43% to 7%. **P5.4** booked: probe legislation.gov.uk for the recital. **Corrected 8 Oct (batch 9 D):** the 0 of 28 is the `/legislation/text` sample; 212 distinct SSIs among stored search rows carry the recital in their `description`, which search rows now keep (P3.6); a code-built block from it is booked (**P3.30**). **8 Oct: P3.31 booked as an experiment**: a stored made-under table (SI → enabling Act and section) harvested from the as-made XML's recital, the only route to the reverse question ("which SIs were made under s.N"); measure first, dropped if it does not improve the measured turns. **DATA NOW HELD (P3.31, done 8 Oct, UK SIs added 9 Oct):** the made-under record holds 86,744 SSIs (1999-2026) and UK SIs (1987-2026), 68,780 with parsed powers, refreshed daily; the reverse question is answered (37 of 37 on the acceptance) and the forward one for any SI the record holds. **Still missing:** SIs before 1987 (scans; P3.35), the separate Welsh and NI series (P3.44), and instruments made under an EU regulation or another Order | **legislation.gov.uk instrument XML**: the full SSI text should carry the "in exercise of the powers conferred by…" recital that LEX's `description` lacks. ~~Not probed~~ **First look 8 Oct (3 SIs, ad hoc):** the recital is there as plain text with no `<Citation>` markup; a revoked SI's revised XML dots it out, so read `/made/data.xml`. i.AI's Lex Graph holds no enabling-power edge and is a 2025 snapshot (P3.31). The bulk XML and SPARQL routes (`research.legislation.gov.uk/data`, `legislation.gov.uk/sparql`) are invitation-only (401); access is being chased with TNA's Legislation Data Team (**P5.5**). The most promising lead in this group. The LEX team |

### 2.2 Holes in sources we already use

| Gap | What it costs us | Recent work | Potential sources |
|---|---|---|---|
| **2026 secondary legislation** (about 2% of SSI and UK SI 2026 held; SSI 2025 about 87%) and **older Acts missing one by one** (e.g. Education (Scotland) Act 1962; about 60% of 1962 Acts held) | A "not found" is usually our gap, not absence in law; lawyers were asked to recheck correct citations (6409, 6373) | **Fixed for honesty, not coverage.** **P3.7** (24 Sep, `v2026.09.3`): `lookup_legislation` tells, in code, whether each instrument a brief names by number is held, held without text, or not held. **P2.2**: negative answers state what was searched and that 2026 coverage is under 10% (the product's wording, `utils/search_scope.py`) | **legislation.gov.uk** new-legislation feeds and direct lookup. The LEX team: why is so little of 2026 held, and is the older patchiness inherited from legislation.gov.uk? If it is, legislation.gov.uk won't fill it |
| **Case-law searches return the 50 newest matches, with a false total** | We send no `order`, and the feed defaults to newest first, so the model sees the 50 most recent of what can be thousands of matches (~~~26,000~~: read from the `last` link at the wrong page size; "Evans" is 5,193), not the 50 most relevant ("Evans": an unrelated 2026 case first; *Evans v Evans* under relevance). ~~`total` is reported as the count shown.~~ Since P3.23 (2026-10-05) the result reports the shown count and the matching total apart, with a window note saying the list is newest first. A plausible mechanism for 6363's recency-bias complaint | **Booked 2 Oct:** **P3.22** (relevance ordering with `per_page=50`; this resolves the item held from Thomas's review; **built 7 Oct**, *branch only*, its after-column not yet met: the lead and carrier authorities held, two 6363 authorities came back in fewer runs, traced by hand to query choice), **P3.23** (report the real total and the window; **done** 2026-10-05). **P3.9** (**done** 2026-10-05) fixes the date filter, which had never applied | **The National Archives' own feed**: `order=relevance`, `per_page`, and the `last` link (§4) |
| **How far back National Archives case law goes is unmeasured** | Session 6363's recency-bias complaint can be neither confirmed nor ruled out | None. ~~Feed caps at 50, no totals~~: wrong. 50 is only the default page size and the `last` link gives the total, so this is **measurable** (§4), once P3.9's working date form is used | **Our own probe** of the feed (§4). **The National Archives Find Case Law team**: ask for a coverage statement. **BAILII** for older England & Wales material |
| **Schedules and EU Annexes come back as one provision** | Can't fetch a schedule paragraph or Annex chapter by number. 6335 looped 18 times on Sch B1 para 43; an Annex chapter was called "not held" 2 times in 3. Whole-text reads omitted every schedule and annex (`include_schedules` defaults to false) | **Built on the branch (6 Oct, batch 8 A):** **P3.27** sends `include_schedules` and names what the text carries; **P3.12** fetches a named unit by `/legislation/section/lookup` and `uri` and cuts it (annex chapters by `cut_annex`, now in `utils/schedule_units.py`). Their replay is not yet met (the sweep found a parser gap and a contradicting cap note). **P3.27 accepted (8 Oct). P3.12's next lever built (8 Oct, batch 10 A):** a schedule too large to hand over whole, named with no paragraph, goes as its paragraph headings and the paragraphs whose headings match the search, cut at their own headings; on 6335 the route now hands over paragraphs 42-44 verbatim, and the Worker's use of them is the open question (P3.12 stays open). ~~**P3.12** is booked (measure first).~~ The P3.1 cap now stops the looping after 3 rounds. Cutting out Annex chapters works in dev tooling (`tools/provision_hints.py`) but isn't in the product. **P5.4** probes legislation.gov.uk's paragraph-level markup | **legislation.gov.uk XML** (paragraph-level markup). **Cutting locally**, building on `provision_hints.py` |

### 2.3 Data we could have but don't use

| Gap | What it costs us | Recent work | Potential sources |
|---|---|---|---|
| **`description` on search results**: commencement and enabling relationships in prose, with dates | Thrown away by `_slim_search_results` | ~~Open (P3.6). It must be truncated or filtered, not restored wholesale, because the original stripping is what kept Phase 1 under the summarisation threshold~~ **Done (P3.6, *branch only*, Session 41):** kept, cut at a word to 600 characters; Phase-1 summarisation unchanged (0 of 6,521 stored results cross the threshold). **Provenance (batch 9 D):** 1,780 of the 7,189 distinct stored search rows carry `provenance_source: llm_ocr` (`provenance_model: gpt-5-mini`): LEX's text for those instruments was transcribed from print by a model, which bears on how far any LEX text is quoted | **LEX**: already in the responses we receive |
| **Explanatory notes for Acts** | Would have settled 6338: which interpretation regime applies to an amended Act | **Not called.** The underlying defect is being worked through prompts: **P3.3** open; **P3.17** measured with options, not yet accepted | **LEX** `/explanatory_note/legislation/lookup`, `/section/lookup`, `/section/search`. Acts only: an SSI returns 404 |
| **Policy and executive notes for SSIs** | No official statement of purpose for secondary legislation | None | **legislation.gov.uk** associated documents |
| **Amendment relations at provision level** | P3.5 queries at instrument level only | None | **LEX** `/amendment/section/search` |

---

## 3. SCTS judgments API — probed 2026-10-02

The Scottish Courts and Tribunals Service runs a JSON search API behind the judgments search
page on scotcourts.gov.uk. It isn't documented or published as an API. It was found by
reading the page's JavaScript (`/apps/NoResults.min.js` holds the AutoRest client,
`azsdk-js-scts-api-client/1.0.0-beta.1`). Everything below was measured live.

### Endpoints

| Call | Purpose |
|---|---|
| `POST https://api.pa.web.scotcourts.gov.uk/web/search` | Search. JSON body `{"query", "filters": [{"field", "value"}], "page", "limit", "indexType": "Judgments", "category": ""}`. Returns `{results: [...], pagination: {count: {total, start, end}, page: {current, total, limit}}}` |
| `GET https://api.pa.web.scotcourts.gov.uk/web/definition/1414` | The search page's definition: filter fields, court values, result columns |
| `GET https://api.pa.web.scotcourts.gov.uk/web/rss/Judgments` | Published RSS feed: the latest 200 judgments as title, date and PDF link. Other index types: `FatalAccidentInquiryDeterminations`, `PracticeNotesAndDirections`, … |
| `GET https://www.scotcourts.gov.uk{documentLink}` | The judgment PDF |

The `api.dv.` host baked into the client as its default is a development environment; the
page passes the production base URL (`api.pa.`) in `data-base-url`.

### Filters

- `Court`: exact values from the definition, e.g. `Court of Session`, `High Court of Justiciary`, `Sheriff Appeal Court Civil`, `Sheriff Court Civil`, `Upper Tribunal - Housing and Property Chamber`.
- `AdditionalDate` (date of opinion/decision) and `Date` (date published): value `YYYY-MM-DD|YYYY-MM-DD`; either side may be empty.

### Result fields

`title`, `documentLink`, `court[]`, `sheriffdom[]`, `judges[]`, `additionalDate`, `date`,
`tags[]`. **No neutral citation field.** It appears in newer PDF filenames (`2026csoh94-…pdf`)
and in the PDF text from 2005 (when Scotland adopted neutral citations).

### Coverage (2026-10-02)

**13,213 judgments in total.**

| Court | Judgments |
|---|---|
| Court of Session | 7,121 |
| High Court of Justiciary | 2,899 |
| Sheriff Court (civil) | 1,986 |
| Sheriff Appeal Court (civil) | 410 |
| Sheriff Appeal Court (criminal) | 157 |
| National Personal Injury Court | 155 |
| Upper Tribunal, Housing and Property Chamber | 269 |
| Upper Tribunal, Social Security Chamber | 96 |
| Sheriff Court (criminal) | 3 |

By decision year: 1997: 2, 1998: 160, 1999: 590, then roughly 330–590 a year through 2026
(2026 to date: 388). Sheriff Court coverage is only what SCTS chooses to publish ("as a
general rule … published unless there is a requirement, or otherwise good reason, not to"),
so it is a fraction of decisions, and criminal sheriff decisions are almost absent.

**Re-probed 2026-10-08 (FIX_PLAN P3.20's measurement, batch 11 D, 134 calls):** 13,222 judgments; `/web/definition/1414` lists 13 court values, and the table above omits four Upper Tribunal chambers (General Regulatory Chamber 41, Health and Education 23, Local Taxation 48, Tax 5).

### Search behaviour

- **Full text, not titles.** `Wednesbury` returns 528 results, and none of the top three has the word in its title.
- **Quoted phrases work.** `"title to sue"` gives 354; `"Wednesbury unreasonable"` 123; `"Interpretation and Legislative Reform (Scotland) Act 2010"` 27.
- **Unquoted multi-word queries behave like OR.** The unquoted ILRA title matched 12,703 of 13,213. A tool must quote phrases.
- **Paging works:** `limit=500` returned 500 rows, and the total is exact.
- **A leading `+` makes a term or quoted phrase required (AND)** (re-probed 2026-10-08): `+"title to sue" +Wednesbury` gives 16. `AND`/`and` are not operators, a required stopword is ignored, `*` is a prefix wildcard, and `-` broadens rather than excludes.
- **Rows can repeat:** `"title to sue"` paged to 354 rows holds 352 distinct `documentLink`s, so a tool dedupes on it. A query lists by relevance; an empty query lists newest published first. Searching for a neutral citation is not a lookup (the judgment itself came third).

### Text

Judgment text is only in the PDF. Five PDFs sampled across 1999–2026, covering the Court of
Session, High Court of Justiciary and Sheriff Court, all extracted cleanly with `pypdf`
(4–31 pages, 12,000–81,000 characters). `pdfplumber` is already in
`server_py/requirements.txt` but **not in the offline installer bundle**, so the bundle would
need regenerating before the target could parse PDFs.

### Terms

SCTS's [Crown copyright policy](https://www.scotcourts.gov.uk/scts-crown-copyright-policy)
allows reuse of the site's information "free of charge in any format or medium, under the
terms of the Open Government Licence". It excludes only logos, photographs and third-party
material, and says nothing either way about automated use. `robots.txt` disallows only
`/umbraco/` and `/*?query=*`. That is a much cleaner position than BAILII, which republishes
these judgments and restricts automated access.

### Risks

1. **It is not a published contract.** The client is versioned `1.0.0-beta.1`, and SCTS reworked the judgments system in May 2025, telling RSS users to disable their feeds during the change. Ask SCTS (`enquiries@scotcourts.gov.uk`) before building on it. **Asked (8 Oct 2026): SCTS agreed by phone, with no conditions given.** A written confirmation is still worth having, and the tool is capped and paced in code regardless.
2. ~~**Date metadata may be unreliable.** In 2 of 5 samples, a decision-date filter for one year returned a judgment cited from a later year: a 2012 filter returned a `[2015] HCJAC`, a 2020 filter returned a `[2021] SC GLW`. Too small a sample to call a pattern; check before trusting date filters.~~ **Measured 2026-10-08 (40 PDFs):** `additionalDate` is the date printed in the judgment in 36 of 40, 1 has a mistyped year. A neutral citation's later year (21 of 297 rows, mostly the High Court of Justiciary) is the year of publication, not a metadata error: that is what the 2026-10-02 samples showed. So `additionalDate` is usable as the date of decision; never take a date from the citation. pdfplumber extracted 40 of 40 (median 24,777 characters, 0.46 s); the citation is in the opening text of 31 of the 34 decided from 2005.
3. **Two hosts to whitelist:** `api.pa.web.scotcourts.gov.uk` (search) and `www.scotcourts.gov.uk` (PDFs).
4. **Not Northern Ireland, and not unpublished decisions.**

### Reproduce

```bash
curl -s -H "Content-Type: application/json" \
  -d '{"query":"\"title to sue\"","filters":[{"field":"Court","value":"Court of Session"}],"page":1,"indexType":"Judgments","category":"","limit":5}' \
  https://api.pa.web.scotcourts.gov.uk/web/search
```

---

## 4. National Archives — the published API and licence, read 2026-10-02

The Find Case Law API is documented at
[`nationalarchives.github.io/ds-find-caselaw-docs/public`](https://nationalarchives.github.io/ds-find-caselaw-docs/public)
(OpenAPI: `public_api.yml` in `nationalarchives/ds-find-caselaw-docs`). Our code sends
`query`, `court` and two date parameters the feed ignores (P3.9). Probed live:

| Finding | Detail | Row |
|---|---|---|
| **Default order is newest first** | `order` defaults to `-date`. `order=relevance` (the advanced search's sort, not in the spec's enum) ranks by relevance over the same matching set ("Evans": 520 pages under every ordering). Re-checked 6 Oct (batch 8 C, every stored query live): the same matching set on 356 of 356 searches with results, a different first three about seven times in ten, and still absent from `public_api.yml` v0.6.0 (enum `date`, `updated`, `transformation`). Decided: relevance, with `per_page=50`. Built 7 Oct (*branch only*): `search_case_law` sends both (`caselaw.CASE_LAW_ORDER_PARAMS`) | P3.22 |
| **An explicit `order` resets the page size to 10** | Why Thomas saw relevance cut 50 → 10; `order=-date` does it too. Send `per_page` with `order` | P3.22 |
| **`per_page` is not capped at 50** | 500 returned 500. `page` pages through the rest | — |
| **The total is in the `last` link** | ~~Final page number at the requested page size; the total to within one page. The last page can be empty ("Donoghue v Stevenson": page 12 held 0), so treat it as an upper bound~~ **Corrected 2026-10-05 (batch 7 D, live): the final page number counted at ten judgments a page, whatever page size is asked for, so the total to within ten** ("Evans": `last` page 520 with or without `per_page=50`, 5,193 by paging). The empty last pages were the link read at 50 a page, which made every figure five times too high. Built: `caselaw.case_law_count` | P3.23 **done** |
| **`party` and `judge`** | Match one full word of a party's or judge's name. A route to a case the lawyer names (6359's *Clark*, Thomas's *R v Evans (Graham)*); unused | — |
| **Dates** | The spec documents no date parameter. The advanced search's `from_date_0/1/2` / `to_date_0/1/2` work; ~~what we send is ignored~~ since P3.9 (2026-10-05) we send that form (`caselaw.case_law_date_window`) | P3.9 **done** |
| **Rate limit** | 1,000 requests per rolling 5 minutes **per IP**, HTTP 429. The target is one IP for all users; ~~our case-law calls bypass `_request_with_retry`~~ since P4.19 (2026-10-05) both case-law calls go through it | P4.19 **done** |
| **Document URIs** | `court/year/seq` until April 2025, `d-{UUID}` since. Not checked against `_court_rank`, which falls back to the URL for the court code | — |

### The licence

The Open Justice Licence permits reading, downloading, quoting and republishing judgments,
including commercially. It does **not** permit "computational analysis", which TNA
[defines](https://caselaw.nationalarchives.gov.uk/when-you-need-permission) as "using
automated or algorithmic methods to process large numbers of judgments systematically —
including using AI or large language models (LLMs)", and lists as including "building
services or products using AI or large language models (LLMs)" and "natural language
processing of judgment text". Reading individual judgments, downloading them one at a time
and using the search function do not need permission.

AILA searches the feed programmatically and processes judgment text with an LLM, so it reads
as in scope. **The licence is free** (`caselawlicence@nationalarchives.gov.uk`). No record of
an application exists in this repo. This is a decision for the user and the deploying
organisation, not an engineering row.
