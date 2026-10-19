# LEX API Specification

*Last updated 2026-10-13, against `main` at release v2026.10.4. Request bodies below are what the
code sends; schemas are from the API's own OpenAPI document (a copy recorded 2026-10-02 lists
`"title": "Lex API"`, `"version": "0.0.0"`).*

## Overview

Base URL: `https://lex.lab.i.ai.gov.uk` (the `LEX_API_URL` setting, default
`https://lex.lab.i.ai.gov.uk/` in `server_py/src/config.py`; the trailing slash is stripped as
`LEX_API_URL` in `agent/tools/lex.py`).

The API serves UK legislation, amendment relations and explanatory notes. It publishes an OpenAPI
spec at **`GET /openapi.json`** documenting **13 endpoints**; AILA calls **7** of them (marked
**[CALLED]** below). **It exposes no case-law endpoint**: case law comes from the National Archives
(`agent/tools/caselaw.py`) and, behind a feature flag, SCTS (`agent/tools/scts.py`).

Re-run the evidence behind this document with `python -m tools.lex_probe` (`--surface` lists the
endpoints; `--coverage`, `--enabling`, `--commencement`, `--inforce` probe the data). Note that the
probe's own `<- we call this` marker still lists only the original three endpoints.

## Authentication and transport

- **No authentication.** The executor sends no auth headers, and neither does the probe.
- **The read endpoints are `POST` with a JSON body**; only `/legislation/proxy/{…}`,
  `/openapi.json`, `/api/stats` and `/healthcheck` are `GET`.
- The tool and proxy-read clients are created with `verify=False` (deployments behind SSL
  inspection or self-signed certs).
- **Retry:** every Worker-tool call to LEX goes through `_request_with_retry`
  (`agent/tools/executor.py`): statuses `429`, `502`, `503`, `504` and network errors (timeouts,
  transport errors) are retried up to 3 times with exponential backoff (0.5 s, 1 s, 2 s plus
  jitter, capped at 8 s), honouring `Retry-After` (capped at 30 s). Any other status returns to the
  caller unchanged. The proxy reads (below) are deliberately **not** retried.
- **Timeouts:** 30 s per Worker-tool call by default; 120 s for `/amendment/search`; 60 s for the
  code-made provision list and text-with-schedules fetches; proxy reads 8 s (commencement dates),
  15 s (published text) and 20 s (the made-under refresh).
- **Health check:** `services/health_service.py` sends `GET` to the base URL itself (not
  `/healthcheck`) every 300 s and records it as `lex_api` in `service_health_logs`.

## Endpoints

### Legislation

#### Search Legislation — **[CALLED]** `search_legislation`
`POST /legislation/search`

Find Acts and SIs by title, content or metadata.

**Request body, as sent:**
```json
{
  "query": "string",       // the model's query (required)
  "year_from": 1998,       // the legal professional's filter intersected with the model's argument, or null
  "year_to": 2024,         // likewise
  "limit": 5,              // 20 when a jurisdiction or legislation-type filter is set, else 5
  "include_text": false
}
```
Also accepted by the API and **not sent**: `legislation_type` (list), `offset` (default 0). The
legislation-type and jurisdiction filters are applied **after** the call, in code
(`_TYPE_CODES` on the id prefix; `_matches_jurisdiction` on `extent`).

**Response:** `{"results": [...], "total": int, "offset": int, "limit": int}`. Each result is an
open object; the fields read are `uri`, `title`, `status`, `year`, `extent`, `description` and
`sections`.

**What the model receives** (`_slim_search_results`, then the executor): at most 5 results, each
`{legislation_id, title, url, text_version, year, extent, description?}`, plus `total` (the API's
match count), `total_matched`, `returned`, `removed_by_filters` and `filters_applied` (when a filter
removed anything).

**Traps:**
- **`status` is the text version legislation.gov.uk holds** (`final`, `revised`, `stub`), not
  in-force status. It is emitted as `text_version` for that reason (FIX_PLAN P2.5).
- **`extent` is a list of full territory names**: `['Scotland']`, `['United Kingdom']`,
  `['England', 'Wales']`, `['']`, `[]` (enum `England`, `Wales`, `Scotland`, `Northern Ireland`,
  `United Kingdom`, `""`). Not the `E+W+S` code form. `['']` and `[]` are common and mean unknown.
- **`sections` is a ranked list** `[{number, provision_type, score}]` that ranks provisions against
  the *search query*, not the question; it is dropped on purpose (FIX_PLAN P3.1). `number` is
  empty for any non-integer provision id (s.6B, Sch A1, dotted court rules).
- **`description`** is kept, cut at a word to 600 characters (`SEARCH_DESCRIPTION_CAP`, P3.6): it
  can state what a commencement instrument brings into force, and when. Values with no letter (dot
  leaders) are dropped.
- **`uri`** sometimes carries `/id/` in its path; `legislation_id` is the path with that prefix
  removed.
- An EU measure is **not** found by its number; use `/legislation/lookup` with
  `legislation_type: "eur"`.

#### Search Legislation Sections — **[CALLED]** `search_legislation_sections`
`POST /legislation/section/search`

Find text within the provisions of one instrument.

**Request body, as sent:**
```json
{
  "query": "string",
  "legislation_id": "ukpga/1998/42",
  "size": 10
}
```
**The page-size field is `size`, not `limit`**: `limit` is silently ignored (verified live
2026-09-18; the product sent `limit` for years and it matched the default of 10 by coincidence).
Also accepted and not sent: `legislation_category` (list), `legislation_type` (list), `year_from`,
`year_to`, `offset`, `include_text` (default `true`, so text is returned). Only `query` is
required. Recorded live at FIX_PLAN P3.34 (batch 13 G), and not used by the product: with no
`legislation_id` (null, `""` or omitted) the search covers the whole index, and `size` changes
which rows rank top, not only how many are returned.

**Response:** a **bare JSON list** of `LegislationSection`
(`id`, `uri`, `legislation_id`, `title`, `text`, `extent`, `provision_type`, `number`,
`legislation_type`, `legislation_year`, `legislation_number`, `created_at`, `provenance_*`).

**What the model receives** (`_slim_section_results`): `{"results": [{legislation_id,
provision_type, number, title, url, text}], "returned": n}`, where `url` is the API's own
provision-level `uri` (FIX_PLAN P1.4).

**Traps:**
- **`legislation_id` in this response is a full URI** (`http://www.legislation.gov.uk/id/…`),
  where `/legislation/search` returns the short form; `_short_legislation_id` normalises both.
- **`number` is `null`** for any provision whose id is not a plain integer; the `uri` still
  carries the real id.
- **`provision_type` is `section` or `schedule`** only: a regulation or article is `section`.
- **A Schedule (or an EU Annex) is ONE provision** (`…/schedule/B1`, `…/annex/XIV`); nothing finer
  than `/schedule/X` is held. A search for a paragraph number rarely ranks the Schedule.

#### Get Legislation Text — **[CALLED]** `get_legislation_text`
`POST /legislation/text`

The whole text of an instrument as one document.

**Request bodies, as sent (two calls per read):**
```json
{ "legislation_id": "ukpga/1998/42", "include_schedules": true }
```
```json
{ "legislation_id": "ukpga/1998/42" }
```
`include_schedules` defaults to `false` ("only sections are returned"), so every read before
FIX_PLAN P3.27 omitted every schedule and annex. With the flag, the sections come first and the
schedules are appended. The second, unflagged call is made only to locate where the schedules start
(`schedule_units.mark_schedule_boundary`); its failure is tolerated. The same flagged body is also
sent by `executor.fetch_text_with_schedules`, P3.12's fallback when the provision list cannot be
fetched.

**Response:** `{"legislation": <Legislation>, "full_text": "string"}`.

**Traps:**
- **Read `full_text`.** The nested `legislation.text` is empty for every instrument, including
  fully held Acts.
- An instrument held without text returns `full_text` equal to the literal sentence
  `"No text content available for this legislation."`.
- `legislation.description` can carry an SI's enabling-power recital, though 0 of 28 sampled
  Scottish instruments carry one (P2.3); `legislation.valid_date` is the date the held revised
  text is stated to be up to date to, not an in-force date.

#### Lookup Legislation — **[CALLED]** `lookup_legislation`
`POST /legislation/lookup`

Fetch one instrument by type, year and number: the held/absent test (FIX_PLAN P3.7).

**Request body, as sent:**
```json
{
  "legislation_type": "ssi",
  "year": 2025,
  "number": 377
}
```
`number` is an **integer**. All three fields are required.

**Response:** 200 with **one** `Legislation` object. The fields read are `uri` (or `id`), `title`,
`category`, `enactment_date`, `valid_date` and `description` (cut to 600 characters).

**Traps:**
- **Only LEX's own sentence is a negative:** 404 `{"detail": "Legislation not found: ssi 2025
  No. 377"}` means not held. A route 404 (`{"detail": "Not Found"}`) must not be read as not held;
  the executor reports it as `lookup_failed`.
- A 200 does not mean the text is held (`number_of_provisions` is not a text signal); the tool
  checks the text with `/legislation/section/lookup` (below).
- `legislation_type: "eur"` resolves an EU measure by number where search does not.

#### Lookup Legislation Sections — **[CALLED]** `lookup_legislation`, and code
`POST /legislation/section/lookup`

Every provision of an instrument, with its text.

**Request bodies, as sent:**
```json
{ "legislation_id": "ssi/2025/377", "limit": 1 }
```
(the lookup tool's text check), and
```json
{ "legislation_id": "ukpga/1986/45", "limit": 5000 }
```
(`executor.fetch_provision_list`, P3.12's route to one schedule or annex a section search named but
did not return; called by `agent_shared.schedule_route_block`, never by the model).

**Response:** a bare list of `LegislationSection` (same item shape as section search); 404
`{"detail": "No sections found …"}` for an instrument held without text.

**Traps:**
- `limit` defaults to 10. The list is complete when `limit` exceeds the provision count, but its
  order is **not** sections-then-schedules (one Act's Schedule is row 123 of 674), so pick a unit
  by `uri`, never by position.
- A complete list is the route to a provision by number: look up, then filter.

#### Proxy Legislation Data — **[CALLED]**, code only
`GET /legislation/proxy/{path}`

The spec describes it as returning legislation.gov.uk's HTML for a `legislation_id`. In practice it
passes **any legislation.gov.uk path** through, byte for byte, including XML documents and Atom
feeds, **when the whole path, query string included, is URL-encoded into one segment**
(`quote(path, safe='')`). Because it goes through LEX's host, it needs no extra whitelist entry on
the target. Three callers, none of them a Worker tool:

| Caller | Paths read | Bounds |
|---|---|---|
| `agent/tools/commencement_dates.py` (P3.21, inside `get_legislation_changes`) | `changes/affected/<id>/data.feed?results-count=500[&page=2]`; `<id>/introduction/data.xml` for the commencing instrument's made date | 2 feed pages, 8 made-date reads a call, 8 s, one attempt, memoised per request |
| `services/made_under_store.py` (P3.31 daily refresh) | `new/ssi/data.feed?page=N`, `new/uksi/data.feed?page=N`; then `<id>/introduction/made/data.xml`, falling back to `<id>/made/data.xml` | 5 pages a feed, 120 fetches a run, 20 s, daily |
| `agent/tools/published_text.py` (P3.38) | `<id>/made/data.xml` (or `/enacted/` for an Act), then `<id>/data.xml` | 2 calls an instrument, 8 instruments a request, 15 s, 8 MB, one attempt, never cached |

**Errors:** 404 with LEX's `"Legislation not found: <path>"` and 502 with
`"External API error: Client error '400 Bad Request' for url …"` both mean legislation.gov.uk has no
such document; a bare route 404 does not. It inherits legislation.gov.uk's latency and availability.

### Amendments

#### Search Amendments — **[CALLED]** `get_legislation_changes`
`POST /amendment/search`

Amendment, commencement, repeal and revocation relations for one instrument, provision to
provision (FIX_PLAN P3.5).

**Request body, as sent:**
```json
{
  "legislation_id": "asp/2025/2",
  "search_amended": true,   // true = changes made TO it (direction "to"); false = changes it MAKES ("by")
  "size": 2000              // escalated once to 20000 if exactly `size` rows come back
}
```
`size` defaults to 100.

**Response:** a **bare JSON list** of `Amendment`: `changed_legislation`, `changed_year`,
`changed_number`, `changed_url`, `changed_provision`, `changed_provision_url`,
`affecting_legislation`, `affecting_year`, `affecting_number`, `affecting_url`,
`affecting_provision`, `affecting_provision_url`, `type_of_effect`, `id`, `ai_explanation`,
`ai_explanation_model`, `ai_explanation_timestamp`.

**What the model receives** (`_slim_amendment_results`): relations deduplicated and grouped by
(other instrument, effect), each group listing `changes` as `{"by": <effecting provision>,
"changed": [...]}` (P3.19), with counts (`relations`, `duplicate_rows_collapsed`,
`by_other_legislation`, `by_this_legislation_itself`, `provisions_commenced`,
`commencement_orders_of_amendments`, and P3.28's `provision_removal_relations`,
`words_only_removal_relations`, `qualified_removal_relations`), `window_complete`, and, from P3.21,
`in_force`/`qualification` dates on commencements by another instrument plus a
`commencement_dates` status.

**Traps (three make a naive read wrong):**
- **About 35% of rows are `http`/`https` duplicates of one relation**, and `id` embeds the scheme,
  so deduping on `id` removes nothing (`asp/2025/2`: 71 rows for 36 relations). Dedupe on
  `(changed_legislation, changed_provision, affecting_legislation, affecting_provision,
  type_of_effect)`.
- **`size` truncates silently and there is no count field.** Exactly `size` rows back can only mean
  the cap bound; ask for more or say the list is a window (`window_complete: false`,
  `window_size`).
- **Commencement rows are often self-referential** (an Act commencing its own sections):
  `changed_legislation == affecting_legislation` separates them from commencement by another
  instrument.
- `type_of_effect` is null on a share of rows (labelled `not stated`, never dropped).
- `Commencement Order` rows carry a placeholder `changed_provision` (`specified amended
  provision(s)`, `None`, `C/O` …): they commence an amendment *to* the subject, not the subject
  itself, and are marked `commences_this_legislation: false`.
- **No row carries a date.** Dates come from legislation.gov.uk's Changes to Legislation feed,
  read through the proxy (above).
- Removal effects are not only "repealed"/"revoked" ("omitted", "ceases to have effect", "words
  repealed" …); `utils/removal_effects.classify_removal` classifies them.

#### Search Amendment Sections — not called
`POST /amendment/section/search`

```json
{ "provision_id": "ukpga/1998/42/section/3", "search_amended": true, "size": 100 }
```
Matches the **exact** provision URL only (a section id returns `[]` where its subsections have
rows), and a relation whose `changed_provision_url` is null cannot be reached from the changed side.

### Explanatory notes — not called

- `POST /explanatory_note/legislation/lookup` — `{"legislation_id": "...", "limit": 1000}`; all notes
  for one Act. Act-level only (404 for an SSI).
- `POST /explanatory_note/section/lookup` — `{"legislation_id": "...", "section_number": 3}`; the
  note for one section.
- `POST /explanatory_note/section/search` — `{"query": "", "legislation_id": null, "note_type":
  [...], "section_type": [...], "size": 20}`; search notes by content.

### Other — not called

- `GET /api/stats` — live dataset statistics (5-minute cache).
- `GET /healthcheck` — health check with Qdrant connection verification.

## Data types

### LegislationType
The enum in the spec: `ukpga`, `asp`, `asc`, `anaw`, `wsi`, `uksi`, `ssi`, `ukcm`, `nisr`, `nia`,
`eudn`, `eudr`, `eur`, `ukla`, `ukppa`, `apni`, `gbla`, `aosp`, `aep`, `apgb`, `mwa`, `aip`,
`mnia`, `nisro`, `nisi`, `uksro`, `ukmo`, `ukci`. Pre-1963 Acts carry regnal-year ids
(`ukpga/Geo6/9-10/72`), which no year/number lookup reaches.

### LegislationCategory
`primary`, `secondary`, `european`, `euretained`.

### GeographicalExtent
`England`, `Wales`, `Scotland`, `Northern Ireland`, `United Kingdom`, `""`. An `extent` is a list of
these; legislation.gov.uk's own `E+W+S+N.I.` code form is also understood by
`_matches_jurisdiction` but LEX does not emit it.

### ProvisionType
`section`, `schedule`.
