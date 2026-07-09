# Parliament Bot — Video Deep-Links v2: Committee Spike Brief

> Status: **planned, not started.** Written 2026-07-09 as a cold-start handoff for a new session.
> v1 (plenary video deep-links) is **built, tested locally, and merged on `chore/tidy-up`.** This
> brief covers the one deferred piece: extending video deep-links to **committee** meetings.
> Read alongside `VIDEO_DEEPLINK_PLAN.md` (the v1 build brief) and `PARLIAMENTARY_DATA.md` §8.

---

## 1. Goal of the spike

Prove (or disprove) that we can resolve a **committee meeting → its Scottish Parliament TV
`event_id`**, so the *existing* video pipeline can attach timestamped deep links to committee
transcripts exactly as it now does for plenary.

**This is the only unsolved piece.** Everything downstream already works and is reused unchanged:
playback model → HLS → WebVTT captions → rarest-phrase matcher → `?clip_start=…` deep link.

Deliverable: a working `resolve_committee_event(meeting_date, committee_name/code)` → `event_id`,
validated end-to-end against one real `sp_committee_items` row (see §5).

---

## 2. Why plenary was easy and committee is not

- **Plenary (v1, done):** exactly one chamber sitting per day, so the SP TV slug is **derivable
  from the date alone** — `meeting-of-the-parliament-june-2-2026`. No lookup needed.
  `sptv_client.plenary_slug_for_date()` does this.
- **Committee (v2):** **several committees meet on the same day**, each with its own video. Date
  alone is ambiguous. Example from our DB — three committees on 2026-06-25:

  | meeting_id | slug | committee | date |
  |---|---|---|---|
  | 20190 | `PPC-25-06-2026` | Public Petitions Committee | 2026-06-25 |
  | 20187 | `CA-25-06-2026` | Climate Action Committee | 2026-06-25 |
  | 20193 | `PAC-25-06-2026` | Public Audit Committee | 2026-06-25 |

  So we need `date + committee → event_id`. The SP TV committee slug/URL pattern is **unknown** —
  that is what the spike must discover.

---

## 3. What to investigate (in priority order)

1. **Find a committee video on scottishparliament.tv and inspect its URL + page.**
   - Browse/search https://www.scottishparliament.tv for a committee meeting (e.g. a recent
     Climate Action or Public Audit Committee session that we have in `sp_committee_items`).
   - Capture: the meeting-page URL/slug pattern for committees (v1 plenary uses
     `/meeting/{slug}`), and confirm the page HTML still embeds `Player.init({eventId})` the same
     way (it should — same Vualto player).
2. **Look for an archive/listing/search endpoint that filters by date + committee.**
   - Does scottishparliament.tv expose a searchable archive (by date, by committee/channel)?
     Check the site's browse/archive pages and any XHR/JSON calls the front-end makes (network tab).
   - Candidate: a channel or committee filter that yields a list of events with `event_id` +
     title + date, which we can match to a committee name/date.
3. **Failing a search endpoint, try a committee-code → SP TV channel/slug mapping.**
   - Each committee may have a stable SP TV channel. If a deterministic slug can be built from
     committee + date (analogous to the plenary slug), that is the cleanest solution.
4. **Cross-check with the Official Report.** The committee meeting page on parliament.scot
   (already crawled) may itself link to the SP TV video — inspect the meeting detail page HTML for
   an outbound scottishparliament.tv link. If present, that is the simplest resolver of all
   (scrape the link → extract slug/event_id).

**Ground truth for timing** (as in v1): the committee Official Report page has sparse embedded
`>HH:MM<` wall-clock markers — use them to verify a matched timestamp, and remember the v1 lesson:
**segment ordinal = true HLS playlist index (spans caption-less segments), NOT caption-stream MPEGTS
transitions.**

---

## 4. Reuse map — what's already built (do NOT rebuild)

| Component | File | Committee change needed |
|---|---|---|
| Event resolution | `services/sptv_client.py` `resolve_event()` / `plenary_slug_for_date()` | **NEW** `resolve_committee_event()` — the spike's core output |
| Playback model | `sptv_client.get_playback_model()` | none — reuse as-is |
| Caption transcript | `sptv_client.fetch_caption_transcript()` | none — reuse as-is |
| Cache table/model | `SpVideoCaption` / `sp_video_captions` | none — `meeting_id` already keys committee meetings too (it's the OR `?meeting=` id, shared shape) |
| Matcher | `services/caption_match.py` (`annotate_speeches`, `build_deeplink`) | none — reuse as-is |
| Citation wiring | `agent/tools/parliament.py` `get_scottish_plenary_debate` (video enrichment block) | **MIRROR** into `get_scottish_committee_transcript` |
| Source panel `video` field | `agent/agent_shared.py` `_extract_sources_inner` (`get_scottish_plenary_debate` branch) | **MIRROR** into the `get_scottish_committee_transcript` branch |
| Backfill/crawl | `services/parliament_crawler.py` `backfill_captions()` + `_capture_meeting_captions()` | extend to iterate `sp_committee_items` too, once resolution works |
| Frontend | `client/src/components/SourcesRail.jsx` | none — the `Committee` kind + video pill already render; panel is source-kind adaptive |

Config flag `ENABLE_VIDEO_DEEPLINKS` already gates everything — committee work stays dark-launched
under the same flag.

---

## 5. Validation target for the spike

Pick one committee meeting we already have crawled with a decent number of speeches, e.g.
**Climate Action Committee, 2026-06-25** (`meeting_id=20187`, slug `CA-25-06-2026`), or any recent
committee row from `sp_committee_items` (`lexchat_parliament` DB, creds `lexuser`/`lexpassword`).
End-to-end success = resolve its `event_id`, fetch captions, match a distinctive speech, and get a
`clip_start` that lands within a few seconds of the Official Report's embedded time marker for that
speech (same acceptance bar as the v1 plenary smoke test).

---

## 6. Environment / dev notes (same as v1)

- Parliament bot DB: `lexchat_parliament` (creds `lexuser`/`lexpassword`); tables `sp_committee_items`,
  `sp_plenary_items`, `sp_video_captions`. `psql` at `C:\Program Files\PostgreSQL\18\bin\psql.exe`.
- Python 3.14 at `C:\Python314\python` (deps installed globally). Run scripts from `server_py/`.
- Local flag ON: `bots/parliament/.env` has `ENABLE_VIDEO_DEEPLINKS=TRUE` (gitignored — stays local).
- Launch: `deployment/start_federation_dev.ps1` (bakes `bots/parliament/.env` into the bot's env at
  cmd start — must fully relaunch to pick up flag changes). Parliament bot = port 8001 ("Parli Chat").
- Node (for `client` rebuild): `export PATH="/c/Users/rhett/node_portable/node-v22.15.0-win-x64:$PATH"`.
- v1 reference PoC scripts (plenary): `C:\Temp\poc_final2.js`, `cues.json` (reference only).
- Whitelisting for the target: `scottishparliament.tv` + `*.vustreams.com` (already flagged for v1).

---

## 7. Scope guardrails

- **Spike first, build second.** The immediate task is proving committee → `event_id`. Only once
  that works, mirror the v1 wiring (§4) and extend the backfill.
- Keep everything **additive and fail-soft** — no committee video link must ever block or error a
  committee transcript response.
- Stay behind `ENABLE_VIDEO_DEEPLINKS`. Land on `chore/tidy-up` (or a follow-on branch) — not main.
- Session 6 caption coverage remains out of scope (Session 7 only, matching the crawl).
