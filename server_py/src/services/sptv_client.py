"""
Scottish Parliament TV client — resolve a plenary meeting to its SP TV video and
build a cached caption transcript for text→timestamp matching.

The data chain (see bots/parliament/VIDEO_DEEPLINK_PLAN.md §2):

    meeting_date ──► SP TV slug ──► meeting page ──► eventId
    eventId ──► /Player/PlaybackModel/{eventId} ──► hlsStreamUrl, startTime, isYoutube
    HLS master ──► WebVTT subtitle playlist ──► PROGRAM-DATE-TIME anchor + ~6s segments
    segments ──► (transcript, offset_index)   # char-offset → wall-clock(ms)

Two hard-won facts baked in here (from the PoC):
  * Caption timing = **segment ordinal × 6s** (each EXTINF is 6s), NOT global MPEGTS
    deltas — the per-segment MPEGTS counter resets mid-stream and yields garbage offsets.
    The single PROGRAM-DATE-TIME value is the only timeline anchor.
  * The WebVTT cue timestamps inside each segment file are *local to that segment*
    (they restart near 00:00:00 each file), so the absolute offset of a cue is
    `segment_index * 6 + cue_start_seconds`.

Everything fails soft: any parse/fetch problem returns a caption row with
`caption_ok=False` (or None) so the caller simply omits the video link.
"""
import asyncio
import calendar
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Optional

import httpx

from ..config import settings

logger = logging.getLogger("sptv")

_HEADERS = {"User-Agent": "Mozilla/5.0"}
_SEGMENT_SECONDS = 6  # each WebVTT segment is EXTINF:6
_SUB_CONCURRENCY = 40  # bounded concurrency for segment fetches
_EVENT_ID_RE = re.compile(r'"eventId"\s*:\s*"([0-9a-fA-F-]{36})"')
_SUB_URI_RE = re.compile(r'TYPE=SUBTITLES[^\n]*URI="([^"]+)"', re.I)
_PDT_RE = re.compile(r'PROGRAM-DATE-TIME:([0-9TZ:.+-]+)')
_CUE_RE = re.compile(
    r'(\d\d:\d\d:\d\d\.\d\d\d)\s*-->\s*(\d\d:\d\d:\d\d\.\d\d\d)\n'
    r'([\s\S]*?)(?=\n\n|\n\d\d:\d\d|$)'
)


def norm(s: str) -> str:
    """Normalise caption/speech text to lowercase [a-z0-9 ] with collapsed spaces.

    Mirrors the PoC's `norm` exactly so caption and speech text compare identically.
    """
    s = re.sub(r'[^a-z0-9 ]', ' ', (s or "").lower())
    return re.sub(r'\s+', ' ', s).strip()


def _hms_to_seconds(t: str) -> float:
    h, m, s = t.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def plenary_slug_for_date(d: date) -> str:
    """Derive the SP TV plenary slug from a meeting date.

    e.g. 2026-06-02 → 'meeting-of-the-parliament-june-2-2026'. Note this differs
    from the Official Report slug ('meeting-of-parliament-02-06-2026').
    """
    return f"meeting-of-the-parliament-{calendar.month_name[d.month].lower()}-{d.day}-{d.year}"


@dataclass
class PlaybackModel:
    event_id: str
    event_title: str = ""
    start_time: str = ""          # ISO local wall-clock string from SP TV
    hls_stream_url: str = ""
    is_youtube: bool = False
    youtube_url: str = ""
    can_clip: bool = True


@dataclass
class CaptionTranscript:
    caption_ok: bool
    start_time_utc: Optional[datetime] = None
    transcript: str = ""
    offset_index: Optional[list] = None  # [[char_offset, wall_clock_ms], ...]


async def _get(client: httpx.AsyncClient, url: str, attempts: int = 3) -> Optional[str]:
    """GET a URL as text with a couple of retries. Returns None on persistent failure."""
    last: Optional[Exception] = None
    for attempt in range(attempts):
        try:
            resp = await client.get(url, headers=_HEADERS, follow_redirects=True, timeout=30.0)
            resp.raise_for_status()
            if not resp.encoding or resp.encoding.lower() in ("iso-8859-1", "latin-1", "ascii"):
                resp.encoding = "utf-8"
            return resp.text
        except Exception as exc:  # noqa: BLE001 — fail soft
            last = exc
            if attempt < attempts - 1:
                await asyncio.sleep(1.5 * (attempt + 1))
    logger.warning(f"[SPTV] GET failed for {url}: {last}")
    return None


async def resolve_event(
    client: httpx.AsyncClient,
    meeting_date: date,
    slug: Optional[str] = None,
) -> Optional[tuple[str, str]]:
    """Resolve a plenary meeting date to (event_id, sptv_slug).

    Derives the SP TV slug from the date (unless one is supplied), fetches the
    meeting page and extracts the Vualto eventId GUID. Returns None if the page
    can't be fetched or no eventId is present (e.g. no video for that sitting).
    """
    sptv_slug = slug or plenary_slug_for_date(meeting_date)
    url = f"{settings.sptv_base_url}/meeting/{sptv_slug}"
    html = await _get(client, url)
    if not html:
        return None
    m = _EVENT_ID_RE.search(html)
    if not m:
        logger.info(f"[SPTV] No eventId found on meeting page {url}")
        return None
    return m.group(1), sptv_slug


_MEETING_LINK_RE = re.compile(r'<a[^>]*href="(/meeting/[^"]+)"[^>]*>(.*?)</a>', re.S | re.I)


def _norm_committee_name(s: str) -> str:
    """Lowercase, keep alnum only, collapse runs — for committee-title matching."""
    return re.sub(r'[^a-z0-9]+', ' ', (s or "").lower()).strip()


async def resolve_committee_event(
    client: httpx.AsyncClient,
    meeting_date: date,
    committee_name: str,
) -> Optional[tuple[str, str]]:
    """Resolve a committee meeting to (event_id, sptv_slug) via the SP TV archive.

    Plenary has one chamber sitting per day, so its slug derives from the date alone.
    Committees don't — several meet on the same day, each with its own video — so we
    query the SP TV archive date-filter (`/archive?DateFrom=DD/MM/YYYY&DateTo=…`),
    which lists every event that day with the committee name in the link text, and
    match on the committee name to disambiguate. Then reuse `resolve_event` (with the
    discovered slug) to pull the Vualto eventId off the meeting page.

    Fail-soft: returns None if the archive can't be fetched or no listing matches.
    """
    from urllib.parse import quote

    want = _norm_committee_name(committee_name)
    if not want:
        return None
    ds = quote(meeting_date.strftime("%d/%m/%Y"), safe="")
    url = f"{settings.sptv_base_url}/archive?DateFrom={ds}&DateTo={ds}"
    html = await _get(client, url)
    if not html:
        return None
    for mm in _MEETING_LINK_RE.finditer(html):
        title = _norm_committee_name(re.sub(r'<[^>]+>', ' ', mm.group(2)))
        if want in title:
            slug = mm.group(1).split("/meeting/", 1)[1]
            return await resolve_event(client, meeting_date, slug=slug)
    logger.info(f"[SPTV] No committee archive match for '{committee_name}' on {meeting_date}")
    return None


async def get_playback_model(
    client: httpx.AsyncClient, event_id: str
) -> Optional[PlaybackModel]:
    """GET /Player/PlaybackModel/{event_id} and return a PlaybackModel, or None."""
    url = f"{settings.sptv_base_url}/Player/PlaybackModel/{event_id}"
    body = await _get(client, url)
    if not body:
        return None
    try:
        import json
        data = json.loads(body)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[SPTV] PlaybackModel JSON parse failed for {event_id}: {exc}")
        return None
    return PlaybackModel(
        event_id=event_id,
        event_title=data.get("eventTitle") or "",
        start_time=data.get("startTime") or "",
        hls_stream_url=data.get("hlsStreamUrl") or "",
        is_youtube=bool(data.get("isYoutube")),
        youtube_url=data.get("youtubeUrl") or "",
        can_clip=bool(data.get("canClip", True)),
    )


def _parse_start_time_utc(start_time: str, pdt: Optional[str]) -> Optional[datetime]:
    """Prefer the caption PROGRAM-DATE-TIME anchor (UTC); fall back to playback startTime."""
    for candidate in (pdt, start_time):
        if not candidate:
            continue
        try:
            iso = candidate.replace("Z", "+00:00")
            dt = datetime.fromisoformat(iso)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:  # noqa: BLE001
            continue
    return None


async def fetch_caption_transcript(
    client: httpx.AsyncClient, pm: PlaybackModel
) -> CaptionTranscript:
    """Build a cached caption transcript + offset index for an event.

    Returns caption_ok=False if the event is YouTube-hosted, has no HLS URL, or
    carries no WebVTT subtitle track (older events). Never raises.
    """
    if pm.is_youtube or not pm.hls_stream_url:
        return CaptionTranscript(caption_ok=False)

    master = await _get(client, pm.hls_stream_url)
    if not master:
        return CaptionTranscript(caption_ok=False)

    sub_m = _SUB_URI_RE.search(master)
    if not sub_m:
        logger.info(f"[SPTV] No subtitle track for event {pm.event_id}")
        return CaptionTranscript(caption_ok=False)

    base_url = pm.hls_stream_url.rsplit("/", 1)[0] + "/"
    sub_playlist_url = base_url + sub_m.group(1)
    playlist = await _get(client, sub_playlist_url)
    if not playlist:
        return CaptionTranscript(caption_ok=False)

    pdt_m = _PDT_RE.search(playlist)
    if not pdt_m:
        logger.info(f"[SPTV] No PROGRAM-DATE-TIME anchor for event {pm.event_id}")
        return CaptionTranscript(caption_ok=False)

    base_utc = _parse_start_time_utc(pm.start_time, pdt_m.group(1))
    if base_utc is None:
        return CaptionTranscript(caption_ok=False)
    base_utc_ms = base_utc.timestamp() * 1000.0

    segments = [
        ln.strip() for ln in playlist.splitlines()
        if ln.strip() and not ln.startswith("#")
    ]
    if not segments:
        return CaptionTranscript(caption_ok=False)

    sub_base = sub_playlist_url.rsplit("/", 1)[0] + "/"
    sem = asyncio.Semaphore(_SUB_CONCURRENCY)

    async def _fetch_seg(name: str) -> Optional[str]:
        async with sem:
            return await _get(client, sub_base + name, attempts=2)

    seg_texts = await asyncio.gather(*[_fetch_seg(name) for name in segments])

    # Build the continuous transcript + char-offset → wall-clock(ms) index.
    # Timing anchor = segment ordinal × 6s + cue start (segment-local), NOT MPEGTS.
    transcript_parts: list[str] = []
    offset_index: list[list] = []
    char_len = 0
    last = ""
    for seg_index, vtt in enumerate(seg_texts):
        if not vtt:
            continue
        for cue in _CUE_RE.finditer(vtt):
            cue_start = cue.group(1)
            cue_text = re.sub(r'\s+', ' ', cue.group(3)).strip()
            n = norm(cue_text)
            if not n or n == last:
                continue
            last = n
            wall_ms = base_utc_ms + (seg_index * _SEGMENT_SECONDS + _hms_to_seconds(cue_start)) * 1000.0
            offset_index.append([char_len, int(wall_ms)])
            piece = (" " if char_len else "") + n
            transcript_parts.append(piece)
            char_len += len(piece)

    if not offset_index:
        return CaptionTranscript(caption_ok=False, start_time_utc=base_utc)

    return CaptionTranscript(
        caption_ok=True,
        start_time_utc=base_utc,
        transcript="".join(transcript_parts),
        offset_index=offset_index,
    )
