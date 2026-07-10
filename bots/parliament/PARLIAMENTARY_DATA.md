# Parliamentary Data Model

Reference for how the parliament bot's data is structured and what is available for each
data type. **The parliament bot is Scotland-only (Scottish Parliament / Holyrood).** All
Westminster (UK Parliament / Hansard) search and retrieval has been removed.

The bot draws on four distinct textual data sources, each with a different structure, freshness
model, and level of retrievable detail. The single most important distinction:

> **Committee transcripts *and plenary (chamber) debates* are crawled into local databases
> and are fully searchable and retrievable. Written answers, bills, and members are fetched
> live at query time and are excerpt-only / metadata-only.**

A fifth source — **Scottish Parliament TV video** — is not searched for content; it is an
*enrichment layer* that turns a plenary citation into a timestamped video deep link (the exact
moment the words were spoken). Feasibility is proven; see §8. It is planned, not yet built.

---

## 1. The Scottish Parliament session model

Holyrood organises its work into **parliamentary sessions** — the period between two
general elections. Each session contains all the meetings, debates, bills, and members
current during that term. The Scottish Parliament Official Report exposes sessions as
discrete filters:

| Session | Start | End | Notes |
|---|---|---|---|
| Session 1 | 12 May 1999 | 6 May 2003 | |
| Session 2 | 7 May 2003 | 8 May 2007 | |
| Session 3 | 9 May 2007 | 10 May 2011 | |
| Session 4 | 11 May 2011 | 11 May 2016 | |
| Session 5 | 12 May 2016 | 11 May 2021 | |
| **Session 6** | **13 May 2021** | 12 May 2026 | Crawled into the DB (see §3) |
| **Session 7** | **14 May 2026** | *current* | Crawled into the DB (see §3) |

(Dates as published by the SP Official Report session picker.)

### How sessions gate the source data

The SP Official Report search (`search-what-was-said-in-parliament`) **defaults to the
current session** and silently ignores a custom `dtDateFrom`/`dtDateTo` range that falls
outside it. To retrieve older sessions the request **must include `dateSelect=custom`** —
this is a non-obvious requirement discovered during crawler development. Without it, a
2022 date window returns zero meetings even though the data exists. The crawler sets this
param on every backfill window (see `backfill_sessions()` in
`server_py/src/services/parliament_crawler.py`).

The crawler currently backfills from **Session 6 start (13 May 2021)** onward, covering
Session 6 and Session 7. The dissolution gap between sessions simply returns empty
windows. To include earlier sessions, move `_BACKFILL_START` further back.

---

## 2. Data hierarchy

### Committee transcripts & plenary debates (the crawled, DB-backed sources)

Both share the same hierarchy and table shape. Committee transcripts:

```
Session
└── Meeting                     (one committee sitting on one date)
    │   meeting_id   e.g. "13588"
    │   slug         e.g. "SPPAC-10-02-2022"   (committee code + date)
    │   committee    e.g. "Standards, Procedures and Public Appointments Committee"
    │   date         e.g. 2022-02-10
    └── Agenda item              (one item of business within the meeting)
        │   iob_id   e.g. "223940"   ("item of business" ID)
        │   title    e.g. "Subordinate Legislation"
        └── Speeches             (verbatim contributions)
                speaker + text, in order
```

Plenary (chamber) debates:

```
Session
└── Meeting of Parliament       (one plenary sitting on one date)
    │   meeting_id   e.g. "20164"
    │   slug         e.g. "meeting-of-parliament-02-06-2026"
    │   committee    (label only) "Meeting of Parliament"  (committee_code "MOP")
    │   date         e.g. 2026-06-02
    └── Agenda item              (FMQs, General Question Time, named debate, Decision Time)
        │   iob_id   e.g. "223568"   ("item of business" ID)
        │   title    e.g. "Phone-free Classrooms"
        └── Speeches             (verbatim, attributed contributions)
                speaker + text, in order
```

A single row in the `sp_committee_items` / `sp_plenary_items` table = **one agenda item of
one meeting**, uniquely identified by `(meeting_id, iob_id)`. The full speech list for that
item is stored inline (as JSON) plus a flattened `full_text` blob for full-text search.

### Written answers / bills / members (live sources)

These have **no local hierarchy** — they are queried live and return flat result lists
(speech excerpts, bill summaries, or member records). See §4.

---

## 3. The `sp_committee_items` and `sp_plenary_items` tables

Populated by the background crawler; queried via PostgreSQL GIN full-text search. Models:
`SpCommitteeItem` and `SpPlenaryItem` in `server_py/src/models.py`. **The two tables have an
identical schema and mechanism** — the only differences are the table/constraint names
(`uq_sp_meeting_iob` vs `uq_sp_plenary_meeting_iob`) and that plenary rows carry the fixed
label `committee_name = "Meeting of Parliament"` / `committee_code = "MOP"` (plenary has no
committee).

| Column | Type | Description |
|---|---|---|
| `id` | int PK | |
| `meeting_id` | str, indexed | Meeting identifier from the Official Report (`?meeting=ID`) |
| `slug` | str | URL slug — committee code + date, e.g. `SPPAC-10-02-2022` |
| `iob_id` | str | Agenda item ("item of business") ID (`&iob=ID`) |
| `committee_code` | str, indexed | Short code, e.g. `SPPAC`, `FPA`, `PSRC` |
| `committee_name` | str, indexed | Full committee name |
| `meeting_date` | date, indexed | Date of the sitting |
| `agenda_item_title` | str | Title of the agenda item |
| `url` | str, unique | Canonical transcript URL (`slug?meeting=ID&iob=ID`) |
| `speeches` | JSON | Ordered list of `{speaker, text}` objects |
| `full_text` | text | Committee name + agenda title + all speeches, flattened for FTS |
| `fetched_at` | datetime | When the crawler stored the row |

- **Unique constraint** on `(meeting_id, iob_id)` — the crawler inserts with
  `ON CONFLICT DO NOTHING`, so re-crawls are idempotent and resumable.
- **Full-text search** runs `to_tsvector('english', full_text) @@ plainto_tsquery(...)`,
  ranked by `ts_rank`, optionally filtered by committee (committee table only, ILIKE on
  name/code) and date range.

### How the crawler populates them

`server_py/src/services/parliament_crawler.py`, started on app startup **only when
`RESEARCH_MODE=parliamentary_records`**:

1. **`backfill_sessions()`** — one-shot at startup (committee). Requests the Official Report
   listing with `showCommittee=true&dateSelect=custom&dtDateFrom=X&dtDateTo=Y` in two-week
   windows. For each meeting found it fetches the meeting page (→ committee name + agenda
   items) and then each agenda item's transcript page, parsed with **`_parse_sp_plenary_transcript`**
   (committee and plenary pages share the same `<p id="orscontributions_...">` markup — the old
   committee-specific `_parse_sp_transcript_page` was removed after it was found to collapse
   every meeting into a single unnamed blob; see §8). **Start point is adaptive
   (`_backfill_window_start`):** on an empty DB it walks from `_BACKFILL_START` (Session 6
   start); on a populated DB it starts ~2 weeks before the newest stored meeting, so a normal
   restart re-scans only recent windows instead of re-walking five years. Empty (not-yet-
   published) items are skipped, not stored, so the daily delta retries them. Rate-limited to
   ~1.5 req/s.
2. **`backfill_plenary()`** — one-shot (plenary). Same as above but with `showPlenary=true`
   and `_parse_sp_plenary_meetings` (which *includes* the `meeting-of-parliament-*` slugs the
   committee parser excludes); item pages are parsed with `_parse_sp_plenary_transcript`.
   Uses the same adaptive high-water-mark start. Runs **after** `backfill_sessions()` so the
   two don't hit the origin concurrently. Transcript fetches use `_fetch_sp_page_with_retry`
   (retry/backoff, reject <20 KB) because the large plenary pages intermittently return a
   Cloudflare 524 error page.
3. **`background_crawl_loop()`** / **`background_plenary_crawl_loop()`** — run
   `crawl_sp_new_meetings()` / `crawl_sp_new_plenary()` daily as a **trailing-window delta**:
   they re-scan the last `_DELTA_WINDOW_DAYS` (30) and *reprocess* every meeting in that window,
   not just brand-new `meeting_id`s. This is how new sittings **and** late-published transcripts
   / newly-added agenda items on already-seen meetings are picked up — the source sends no
   `Last-Modified`/`ETag` (Cloudflare `no-cache, no-store`), so a recency-window re-scan against
   our stored state is the only way to detect updates. Per-item `(meeting_id, iob_id)` existence
   checks keep completed transcripts from being re-fetched, so steady-state cost is ~one
   meeting-page GET per recent meeting per day. The plenary loop is self-staggered (first run
   ~5 min after startup) to avoid overlapping the committee crawl.

Written answers, bills, and members are **not** crawled — they are fetched live per query.

---

## 4. Data types and what is available

| Data type | Source | Tool(s) | Keyword search | Full text retrievable | Date filter | Session coverage |
|---|---|---|---|---|---|---|
| **Committee transcripts** | Local DB (crawled from SP Official Report) | `search_scottish_committee_transcripts` → `get_scottish_committee_transcript` | ✅ FTS | ✅ verbatim speeches | ✅ | Session 6 + 7 (whatever is crawled) |
| **Plenary (chamber) debates** | Local DB `sp_plenary_items` (crawled from SP Official Report) | `search_scottish_plenary` → `get_scottish_plenary_debate` | ✅ FTS | ✅ **verbatim speeches** | ✅ | Session 6 + 7 (whatever is crawled) |
| **Plenary debates (fallback)** | TheyWorkForYou `getHansard` (live) | `search_scottish_parliament` | ✅ | ❌ excerpt only | ⚠️ ignored by TWFY | Whatever TWFY indexes (older/breadth fallback) |
| **Written answers** | TheyWorkForYou `getHansard` type=spwrans (live) | `search_scottish_parliament` (`debate_type=written_answers`) | ✅ | ❌ excerpt only | ⚠️ ignored | Whatever TWFY indexes |
| **Bills** | `data.parliament.scot/api/bills` (live) | `search_bills` | ⚠️ client-side keyword filter | n/a (metadata) | ❌ | All Holyrood bills |
| **Members (MSPs)** | TheyWorkForYou `getMSPs` (live) | `get_member_info` | by name | n/a (bio record) | ❌ | Current + historic MSPs |
| **Video timestamps** *(built, dark-launched)* | Scottish Parliament TV (Vualto) — playback model + HLS WebVTT captions; `sp_video_captions` cache | *(enrichment on plenary **and committee** citations, no tool)* | n/a (not searched) | n/a (produces a deep link, not text) | n/a | Plenary + committee, Session 6+7 where captions exist (gated on `ENABLE_VIDEO_DEEPLINKS`) |

### Committee transcripts & plenary debates — the fully-retrievable sources

- **Committee search** (`search_scottish_committee_transcripts`): full-text keyword search
  over the DB. Returns up to 10 ranked agenda items with `meeting_id`, `slug`, `iob_id`,
  `committee_name`, `meeting_date`, `agenda_item_title`, `url`, and a 300-char excerpt.
  Optional `committee` and `date_from`/`date_to` filters.
- **Committee retrieve** (`get_scottish_committee_transcript`): pass `meeting_id` + `slug` +
  `iob_id` back to fetch the verbatim transcript — full speeches (minister responses, member
  questions, witness evidence). This is a **live fetch** of the transcript page (not the
  DB), returning `{page_title, committee_name, url, speeches[], total_speeches}`.
- **Plenary search** (`search_scottish_plenary`): full-text keyword search over
  `sp_plenary_items`. Same result shape as committee search (no `committee` filter). Optional
  `date_from`/`date_to`.
- **Plenary retrieve** (`get_scottish_plenary_debate`): pass `meeting_id` + `slug` + `iob_id`
  back to fetch the verbatim chamber speeches for that agenda item (a ministerial statement,
  an FMQs exchange, a named debate). Live fetch parsed by `_parse_sp_plenary_transcript`
  (scoped to the item via its stored `agenda_item_title`), with retry/backoff for Cloudflare
  524s. Returns `{page_title, url, speeches[], total_speeches}`. This is the *Pepper v Hart*
  route — the minister's exact words, verbatim.
- If a DB is empty (crawl not yet finished), the corresponding search returns a graceful note
  telling the model to fall back to `search_scottish_parliament`.

### Plenary (fallback) & written answers — excerpt only

- Backed by TheyWorkForYou's `getHansard`. `search_scottish_parliament` is **excerpt-only**
  (max ~400 chars each, up to 10 results) — for full plenary text use `search_scottish_plenary`
  + `get_scottish_plenary_debate` instead. `search_scottish_parliament` remains useful as an
  older-session / breadth fallback (TWFY may index dates not yet crawled into `sp_plenary_items`)
  and is the route for **written answers**.
- TWFY quirks baked into the code:
  - `type=sp` is **broken** (returns Westminster content) — the caller omits it and
    post-filters results to SP by `/sp/` and `/spwrans/` listurl patterns.
  - Debate titles come from `speech.parent.body` (HTML), not `speech.debate` (always empty).
  - `date_from`/`date_to` are **not supported** by TWFY `getHansard` and are silently ignored.
- Requires `TWFY_API_KEY`; without it `search_scottish_parliament` returns a clear error.

### Bills — metadata only

- The Scottish Parliament Bills API returns the full list; there is no server-side search,
  so `search_bills` fetches everything and filters by keyword client-side (short/long
  title). Returns `billId`, `shortTitle`, `currentStage`, and a link — no bill text.

### Members (MSPs) — biographical record

- `get_member_info` calls TWFY `getMSPs` with a name search (the old `getMSPInfo` endpoint
  was removed). Returns biography, party, constituency, and roles. Scotland/MSPs only.

---

## 5. Filter enforcement

The frontend exposes a **Record type** filter (`debates` / `written_answers` / `committee`)
and a **Date range**. `_apply_parliament_filters` in `parliament.py` maps these onto tools:

- `debates` → redirects `search_scottish_parliament` to `search_scottish_plenary` (the
  full-text plenary route); a `search_scottish_plenary` call is allowed through.
- `written_answers` → sets `debate_type='written_answers'` on `search_scottish_parliament`.
- `committee` → short-circuits `search_scottish_parliament` **and** `search_scottish_plenary`
  with a redirect telling the model to use `search_scottish_committee_transcripts`.
- Date range → merged into `search_scottish_committee_transcripts` and `search_scottish_plenary`
  (honoured, DB queries) and `search_scottish_parliament` (accepted but ignored downstream by
  TWFY).

A `search_budget` of 3 caps the total number of `search_scottish_plenary` +
`search_scottish_parliament` + `search_scottish_committee_transcripts` calls per research run,
forcing weaker models to stop searching and synthesise.

---

## 6. Known gaps — data a researcher may expect but the bot does not (yet) provide

Prioritised by impact for the bot's audience (lawyers doing statutory-interpretation and
scrutiny research). None of these are bugs — they are coverage boundaries.

### Tier 1 — undercuts the core legal use case

- ~~**No full text for plenary (chamber) debates.**~~ **CLOSED.** Plenary chamber debates are
  now crawled into `sp_plenary_items` and exposed via `search_scottish_plenary` (FTS) →
  `get_scottish_plenary_debate` (verbatim speeches), mirroring the committee pipeline. This
  closes the *Pepper v Hart* gap: a minister's full statement of statutory purpose in the
  chamber is now retrievable verbatim. `_parse_sp_plenary_transcript` parses the plenary
  markup (`<p id="orscontributions_...">` contributions, speaker in the first `/msps/` anchor)
  — validated at 30/30 and 41/41 speech attribution on the spike fixtures. `search_scottish_parliament`
  (TWFY, excerpt-only) is retained only as an older-session/breadth fallback. Operational
  handling: transcript fetches retry with backoff and reject <20 KB Cloudflare-524 error pages
  (`_fetch_sp_page_with_retry`); the fetcher forces UTF-8 so mislabelled charset doesn't leave
  replacement chars in `full_text`.
- **Bills are metadata-only.** `search_bills` returns title, current stage, and a link.
  Missing the material lawyers reason from: bill text, how a provision changed
  Stage 1→2→3, amendments/marshalled lists, and — importantly — the **Explanatory Notes,
  Policy Memorandum, and Financial Memorandum** that accompany a bill and are heavily used
  in statutory interpretation. No Royal Assent date either.

### Tier 2 — standard parliamentary research staples, entirely absent

- **Voting / division records** — how MSPs voted on a bill or motion.
- **Motions and amendments** (S6M-xxxxx) — the formal instruments debates hang on.
- **Published committee outputs** — the committee tool covers *meeting transcripts*
  (Official Report) but **not** formal inquiry/Stage 1 reports or **written evidence
  submissions** to inquiries, which are often more citable than the oral session.
- **Public petitions** (PE numbers) and their consideration.

### Tier 3 — coverage boundaries within existing sources

- **Committees & plenary: Session 6–7 only.** Pre-May-2021 work returns nothing from the
  crawled DBs. The TWFY `search_scottish_parliament` fallback may reach further back but
  remains excerpt-only.
- **Plenary date filtering** — now honoured for `search_scottish_plenary` (DB query). It is
  still silently ignored by the TWFY `search_scottish_parliament` fallback (`getHansard`
  drops `date_from`/`date_to`).
- **Transcript truncation** — `get_scottish_committee_transcript` and
  `get_scottish_plenary_debate` cap each speech at 3000 chars (committee also caps at 30
  speeches); very long sessions are cut.
- **MSP data is bio-only** — no Register of Interests, no per-member voting history.

---

## 7. Quick reference — external endpoints

| Source | Base URL | Auth |
|---|---|---|
| SP Official Report (committee + plenary crawl + transcript fetch) | `https://www.parliament.scot/chamber-and-committees/official-report/search-what-was-said-in-parliament` | none |
| TheyWorkForYou (`getHansard`, `getMSPs`) | `https://www.theyworkforyou.com/api` | `TWFY_API_KEY` |
| SP Bills | `https://data.parliament.scot/api/bills` | none |
| SP TV meeting page + playback model *(video, dark-launched)* | `https://www.scottishparliament.tv/meeting/{slug}`, `https://www.scottishparliament.tv/Player/PlaybackModel/{eventId}` | none |
| SP TV video/caption CDN *(video, dark-launched)* | `https://scotparl-live.cdn.vustreams.com/…` (HLS `.m3u8` + WebVTT segments) | none |

> The two SP TV hosts must be reachable from the (internet-restricted) target for the video
> feature to work — whitelisting has been confirmed available. If unreachable, the feature
> auto-disables and citations fall back to the Official Report link.

---

## 8. Scottish Parliament TV — video timestamp deep links (planned)

**Status:** **built (2026-07-09), dark-launched behind `ENABLE_VIDEO_DEEPLINKS` (default off).** Plenary
(v1) **and committee (v2)**. Full build brief: [`VIDEO_DEEPLINK_PLAN.md`](VIDEO_DEEPLINK_PLAN.md);
committee spike: [`VIDEO_COMMITTEE_SPIKE.md`](VIDEO_COMMITTEE_SPIKE.md). Implemented in
`services/sptv_client.py` (resolve — `resolve_event` for plenary, `resolve_committee_event` for
committee — + captions), `services/caption_match.py` (text→time match),
`parliament_crawler.backfill_captions()` / `backfill_committee_captions()` (caching), and
`SpVideoCaption` / `sp_video_captions`. When enabled, `get_scottish_plenary_debate` **and
`get_scottish_committee_transcript`** attach a `video_deeplink` to matched speeches. This section
documents the *data source* — how SP TV video maps to our Official Report data.

### What it adds
When the bot cites a plenary speech, it can also link to the **exact moment** in the SP TV video where
the words were spoken — e.g. *"the Cabinet Secretary said X — watch from 14:56:52"*. This is an
enrichment on an existing citation, not a new search capability: video is never searched for content,
and if a link can't be resolved the normal Official Report citation stands.

### How the mapping works (the data chain)
SP TV runs the **Vualto** player. There is no field linking an Official Report speech to a video time,
so the link is *derived* through captions:

1. **Meeting → event.** Plenary SP TV slug is derivable from the meeting date
   (`meeting-of-the-parliament-{month}-{day}-{year}`). The meeting page HTML embeds the Vualto
   `eventId` GUID (`Player.init({eventId})`).
2. **Event → streams.** `GET /Player/PlaybackModel/{eventId}` returns JSON (no auth): `eventTitle`,
   `eventDescription` (the agenda), `startTime` (broadcast start), `hlsStreamUrl`, `isYoutube` /
   `youtubeUrl`.
3. **Streams → captions.** The HLS manifest carries a WebVTT subtitle track (`textstream_eng`). The
   caption playlist has one `#EXT-X-PROGRAM-DATE-TIME` anchor (matches `startTime` exactly) plus
   ~6-second WebVTT segments (thousands per sitting).
4. **Caption text → time.** Match a distinctive phrase from the stored `speeches` text (from
   `sp_plenary_items`) against the caption cues; the cue's wall-clock = anchor + offset.
5. **Time → link.** The player accepts `?clip_start=HH:MM:SS&clip_end=HH:MM:SS` where the times are
   **local wall-clock (Europe/London)**. Final link:
   `https://www.scottishparliament.tv/meeting/{slug}?clip_start=…&clip_end=…`.

### Two hard-won implementation facts
- **Caption timing = segment ordinal × 6s (`EXTINF`), using the TRUE HLS playlist index.** The
  per-segment MPEGTS counter resets mid-stream, so global MPEGTS deltas produce garbage (negative)
  offsets — only the single PROGRAM-DATE-TIME value anchors the timeline. **But the ordinal must be
  each segment's real index in the HLS playlist, not the count of caption-stream MPEGTS transitions:**
  ~7% of segments carry no captions (171 of 2317 in the validation sitting), so counting only
  caption-bearing segments (as the original `poc_final2.js` did) undercounts and puts speeches minutes
  too early. `sptv_client.fetch_caption_transcript` uses `seg_index` over the full playlist. (This
  corrects the PoC, which reported `14:56:52` for the 2 June 2026 "Phone-free Classrooms" statement;
  the correct time is `15:02:46`, verified against the Official Report's own embedded `15:02` marker.)
- **Match on the rarest phrase, within the agenda-item window.** Boilerplate openings ("I thank the
  cabinet secretary…") recur throughout a sitting and cause false matches to earlier occurrences.
  Prefer the caption phrase with the fewest occurrences and constrain the search to at/after the
  agenda item's first distinctive speech. `clip_start` is real Europe/London wall-clock (DST-correct
  via `zoneinfo`), not the PoC's hard-coded +1h BST.

### Coverage & limitations
- **Plenary (v1) and committee (v2) both supported.** Plenary slug derives from the date; committees
  can't (several meet the same day), so committee events are resolved via the **SP TV archive
  date-filter** (`GET /archive?DateFrom=DD/MM/YYYY&DateTo=…`), which lists every event that day with
  the committee name in the link text — matched on `committee_name` to disambiguate, then the meeting
  page yields the eventId. Implemented as `sptv_client.resolve_committee_event`; captions are cached
  by `parliament_crawler.backfill_committee_captions()` (+ the rolling committee crawl hook) and
  `get_scottish_committee_transcript` attaches the deep links. Everything downstream of `eventId`
  (playback model, HLS captions, matcher) is identical to plenary. **Committee note:** the retrieval
  tool **and the committee crawler** now parse committee pages with `_parse_sp_plenary_transcript`
  (the same `orscontributions` markup as plenary); the older `_parse_sp_transcript_page` returned a
  single unnamed blob and was deleted. Session 6+7 committee data was re-crawled under the fixed
  parser (attribution ~1 → ~13 speeches/item).
- **Caption coverage (measured, full Session 6+7 backfill Jul 2026).** ~1,140 SP TV events cached in
  `sp_video_captions`; **~540 (~47%) have a usable caption track** (`caption_ok=true`) and can yield a
  video link. The remainder are older sittings with no subtitle track (`caption_ok=false`) — no link,
  fail-soft. Availability skews strongly to recent sittings: most June-2026 plenary and committee
  events are captioned, while many pre-2024 events are not. A `caption_ok=false` row is still stored
  so the event isn't retried.
- **Accuracy ±a few seconds.** Live captions are lightly garbled/rolling; distinctive 8–11 word
  windows match cleanly, but very short or heavily paraphrased contributions fall back to the page
  link.
- **YouTube-hosted events.** Some events are served via `youtubeUrl` instead of HLS — handled with a
  `&t={seconds}` deep link rather than `clip_start`.
- **Undocumented contract.** `clip_start`, `/Player/PlaybackModel/`, and the HLS layout are unofficial
  and could change without notice; all parsing must fail soft (omit the link, never error a response).
