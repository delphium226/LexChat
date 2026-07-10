# Parliament Bot — Video Deep-Link Implementation Plan

> Status: **planned, not started.** Written 2026-07-09. Feasibility spike + PoC **done and passing**
> (see §2). This is a self-contained brief: a cold session should be able to implement from this
> document plus the referenced files. Companion to `SEMANTIC_RETRIEVAL_PLAN.md` — the two are
> independent and can ship in either order.
>
> **Both pre-build blockers cleared (2026-07-09):** target URL whitelisting is available, and
> copyright is not an issue (internal government deployment, deep-link not rehost). See §7.

---

## 1. What we're building & why

Users (lawyers) have asked that when the parliament bot cites a Scottish Parliament source, it also
link to the **exact moment in the Scottish Parliament TV video** where the words were spoken — e.g.
*"the Cabinet Secretary said X — [watch from 14:56:52](…)"*. This turns an Official Report citation
into a verifiable, watchable source (useful for *Pepper v Hart*-style reliance on a minister's exact
statement of statutory purpose).

**Scope:** plenary (chamber) debates first — that is what the PoC proved and where our data is
strongest. Committees are a fast-follow (§6). Written answers / bills / members are out of scope
(no video).

---

## 2. Feasibility — already proven (spike + PoC, 2026-07-09)

Everything below was validated end-to-end against a real `sp_plenary_items` row (2 June 2026
"Phone-free Classrooms" ministerial statement). **No server-side blockers.**

### The four external facts we rely on
1. **Deep-link format works.** scottishparliament.tv runs the **Vualto** player. Meeting pages are
   `https://www.scottishparliament.tv/meeting/{slug}`. The player's share feature (in
   `ts/eventpage.js` `generateUrl`) produces `?clip_start=HH:MM:SS&clip_end=HH:MM:SS`, where the
   times are **local wall-clock** (Europe/London). A hand-built URL returns HTTP 200.
2. **Playback model is a plain REST GET** (no auth, works server-side):
   `GET https://www.scottishparliament.tv/Player/PlaybackModel/{eventId}` → JSON with `eventTitle`,
   `eventDescription` (the agenda), `startTime` (broadcast start, local ISO), `hlsStreamUrl`,
   `canClip`, `isYoutube`, `youtubeUrl`. The `{eventId}` GUID is embedded in the meeting page HTML
   (`Player.init({eventId})`).
3. **Captions exist and are timestamped.** The HLS manifest (`scotparl-live.cdn.vustreams.com`,
   Unified Streaming, VOD) carries a WebVTT subtitle track (`TYPE=SUBTITLES ... textstream_eng`).
   The subtitle playlist has one `#EXT-X-PROGRAM-DATE-TIME:<UTC>` anchor that **exactly matches**
   `startTime`, plus ~6s WebVTT segments (2,317 for a ~3.9h sitting).
4. **Text → time is a direct calculation.** Match an Official Report speech's distinctive phrase to a
   caption cue → cue wall-clock = anchor + offset → format as local `HH:MM:SS` → `clip_start`.

### The two engineering gotchas the PoC surfaced (must be honoured in the build)
- **Timing from segment ordinal, NOT global MPEGTS.** Each WebVTT segment is `EXTINF:6`s. The
  per-segment `X-TIMESTAMP-MAP MPEGTS` counter **resets mid-stream**, so global MPEGTS deltas give
  negative/garbage offsets (first attempt put the minister *before* the meeting started). Correct
  offset = `segment_ordinal * 6 + cue_time_within_segment`, anchored by the single PROGRAM-DATE-TIME.
- **Prefer the rarest phrase + anchor the search window.** Boilerplate openings
  ("I thank the cabinet secretary…") recur all afternoon; naive `indexOf` grabs an earlier
  occurrence. Fix: for each speech pick the caption phrase with the **fewest occurrences** in the
  transcript, and constrain matching to **at/after the agenda-item anchor** (the item's first
  distinctive speech). With both fixes, all four PoC speeches resolved correctly and monotonically.

PoC scripts live in `C:\Temp` (`poc_final2.js`, `cues.json`) on the dev machine — reference only,
not committed.

---

## 3. Architecture decisions (proposed — confirm before building)

- **Cache captions, don't fetch per query.** A sitting's captions are ~1.4M chars / ~28k cue lines.
  Fetching 2,300 segments at query time is far too slow. Crawl once, store a compact per-event
  **caption transcript** (deduped cue text + a `char-offset → wall-clock` index), mirroring the
  existing `sp_plenary_items` crawl pattern.
- **Match at render time, not crawl time.** Which speech gets cited depends on the query, so run the
  matcher when the bot builds a citation — it is a millisecond string search over the cached
  transcript. Crawl-time matching would waste work and couple us to a fixed speech granularity.
- **Additive & degradable.** The link is an optional enrichment on an existing Official Report
  citation. If there's no event, no caption track, or no confident match → **omit the video link,
  keep the normal citation.** Never block or error a response on video resolution.
- **New table, not a column on `sp_plenary_items`.** Captions are per *meeting/event*, not per
  agenda item; one event maps to many `sp_plenary_items` rows. Keep them separate.
- **Plenary only in v1.** Plenary slug is derivable from date; committee event resolution is unsolved
  (§6, §7).

---

## 4. Data model

New table `sp_video_captions` — **one row per SP TV event** (i.e. per meeting), keyed to plenary
meetings by date.

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `meeting_id` | str, indexed | matches `sp_plenary_items.meeting_id` (the Official Report `?meeting=` id) |
| `event_id` | str, unique | SP TV Vualto GUID |
| `slug` | str | SP TV meeting slug, e.g. `meeting-of-the-parliament-june-2-2026` |
| `meeting_date` | date, indexed | |
| `start_time_utc` | datetime | broadcast start (caption anchor) |
| `is_youtube` | bool | if true, `youtube_url` set and HLS/caption path skipped |
| `youtube_url` | str, nullable | for the YouTube fallback (`&t=` deep link) |
| `transcript` | text | deduped, normalised continuous caption text |
| `offset_index` | JSON | `[[char_offset, wall_clock_ms], …]` — monotonic, for offset→time lookup |
| `caption_ok` | bool | false = no subtitle track (older events); skip matching, no link |
| `fetched_at` | datetime | |

Model `SpVideoCaption` in `server_py/src/models.py` (alongside `SpPlenaryItem`). No GIN index needed —
lookups are by `meeting_id`; the transcript is searched in-process, not by SQL.

---

## 5. Phased implementation

### Phase 1 — SP TV client module (`server_py/src/services/sptv_client.py`)
Pure fetch/parse helpers, reuse `_fetch_sp_page_with_retry`-style backoff:
- `resolve_event(meeting_date, slug=None)` → derive slug from date for plenary
  (`meeting-of-the-parliament-{month}-{day}-{year}`), GET the meeting page, regex the `eventId`.
- `get_playback_model(event_id)` → GET `/Player/PlaybackModel/{event_id}`, return the JSON dataclass.
- `fetch_caption_transcript(playback_model)` → GET HLS master → find `textstream` sub-playlist →
  read PROGRAM-DATE-TIME anchor + segment list → fetch all `.webvtt` segments (bounded concurrency,
  ~40) → build `(transcript, offset_index)` using **segment-ordinal timing** (§2 gotcha 1).
  Returns `caption_ok=False` if no subtitle track.

### Phase 2 — caption crawler hook (`parliament_crawler.py`)
- After a plenary meeting is crawled into `sp_plenary_items`, enqueue its `meeting_id` for caption
  capture: resolve event → fetch transcript → upsert `sp_video_captions` (ON CONFLICT DO NOTHING by
  `event_id`). Rate-limited like the existing crawls; runs only when
  `RESEARCH_MODE=parliamentary_records`.
- One-shot `backfill_captions()` over existing `sp_plenary_items` meeting_ids, staggered **after**
  `backfill_plenary()` so we don't hammer the origin (same pattern as committee/plenary backfills).
- Gate behind a config flag `ENABLE_VIDEO_DEEPLINKS` (default off) so it can be dark-launched.

### Phase 3 — matcher module (`server_py/src/services/caption_match.py`)
- `match_speech(caption_row, speech_text, anchor_pos=0)` → returns `{clip_start, clip_end, confidence,
  char_pos}` or `None`. Implements: normalise → for word-windows (8–12 words) at several skips, pick
  the **rarest** occurring phrase, first match at/after `anchor_pos`; `wall_clock` via `offset_index`;
  format `clip_start` as local `HH:MM:SS` (Europe/London — DST-correct, not a fixed +1h; the PoC
  hard-coded BST). `confidence` from occurrence count + window length.
- `build_deeplink(caption_row, speeches, cited_index)` → anchor on the agenda item's first distinctive
  speech, then match the cited speech; returns the full `?clip_start=…&clip_end=…` URL or `None`.
- YouTube branch: if `is_youtube`, emit `youtube_url + "&t=" + seconds` instead.

### Phase 4 — wire into citation output
- Where the parliament worker/manager assembles plenary citations from `sp_plenary_items` results,
  call `build_deeplink` for the cited agenda item and append the video link **when confidence ≥
  threshold**. Confirm the exact citation-assembly point during build (candidates:
  `get_scottish_plenary_debate` result shaping in `agent/tools/parliament.py`, and the manager
  synthesis prompt/format). Keep the Official Report URL as the primary link; video is secondary.

### Phase 5 — config + docs
- Add `ENABLE_VIDEO_DEEPLINKS`, `SPTV_BASE_URL` to config/`.env` table in `CLAUDE.md`.
- Update `PARLIAMENTARY_DATA.md` availability matrix: plenary now has a "video timestamp" column.
- Note the external dependency in the API table (SP TV `/Player/PlaybackModel`, `*.vustreams.com`
  HLS) — **must be whitelisted on the internet-restricted target**, else feature auto-disables.

---

## 6. Committee fast-follow (v2)

Committee video resolution is the one unsolved piece. Plenary slug is derivable from date; committees
have several videos per day, so date alone is ambiguous. Options to investigate: the SP TV **archive
listing/search** endpoint (filter by date + committee name), or a mapping from committee code → SP TV
channel. Everything downstream (playback model, captions, matcher) is identical once `event_id` is
known.

---

## 7. Open questions / risks (raise before starting)

- **Whitelist. RESOLVED (2026-07-09).** Deployment owner confirmed the required URLs
  (`scottishparliament.tv`, `*.vustreams.com`, and the meeting/HLS hosts) can be whitelisted on the
  target. Capture the final exact host list during Phase 1 and hand it over for whitelisting.
- **Caption coverage. MEASURED (full Session 6+7 backfill, Jul 2026).** ~1,140 SP TV events cached;
  **~540 (~47%) have a usable caption track** (`caption_ok=true`), the rest `caption_ok=False` (no
  subtitle track). Coverage skews strongly to recent sittings — most June-2026 plenary and committee
  events are captioned; many pre-2024 events are not. The build degrades gracefully (no track → no
  link, plain citation).
- **Match reliability.** Distinctive 8–11 word windows matched cleanly in the PoC, but live captions
  are lightly garbled/rolling. Very short or heavily paraphrased contributions will fall back to the
  page link. Acceptable, but set user expectations: timestamp is **±a few seconds**.
- **Undocumented contract.** `clip_start`, `/Player/PlaybackModel/`, and the HLS layout are
  unofficial and could change. All parsing must fail soft (log + omit link, never 500).
- **Storage.** `transcript` + `offset_index` are ~1.5–2 MB/sitting. For Session 6+7 plenary
  (~hundreds of sittings) that is low-hundreds of MB in Postgres — fine, but note it.
- **Copyright/policy. RESOLVED (2026-07-09).** Not a blocker — this is an internal government
  deployment and we deep-link to SP TV's own player rather than rehosting video (within their
  [social-media clip policy](https://www.parliament.scot/about/how-parliament-works/policies/social-media-use-of-parliament-tv-clips)).

---

## 8. File-change checklist

- `server_py/src/models.py` — add `SpVideoCaption`.
- `server_py/src/services/sptv_client.py` — **new** (Phase 1).
- `server_py/src/services/caption_match.py` — **new** (Phase 3).
- `server_py/src/services/parliament_crawler.py` — caption crawl hook + `backfill_captions()`.
- `server_py/src/agent/tools/parliament.py` — attach deep link in plenary citation shaping.
- `server_py/src/config.py` — `ENABLE_VIDEO_DEEPLINKS`, `SPTV_BASE_URL`.
- `CLAUDE.md`, `PARLIAMENTARY_DATA.md` — docs + env table + availability matrix.
- DB migration for `sp_video_captions` (follow the project's existing table-create approach).

## 9. Suggested order of execution
P1 (client) → P3 (matcher, unit-testable against saved fixtures) → P4 (wire one plenary citation,
eyeball) → P2 (crawler + backfill, the slow part) → P5 (config/docs) → v2 committees.
Ship P1–P5 behind `ENABLE_VIDEO_DEEPLINKS=off`, backfill, spot-check, then enable.
