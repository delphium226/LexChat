"""
Caption matcher — map a stored Official Report speech to a moment in the SP TV
video and build a `?clip_start=…&clip_end=…` deep link.

Two hard-won rules from the PoC (honoured here):
  * **Rarest phrase.** Boilerplate openings ("I thank the cabinet secretary…")
    recur all afternoon; a naive first-match grabs an earlier occurrence. For each
    speech we try several word-windows and prefer the phrase with the fewest
    occurrences in the transcript.
  * **Anchor the window.** Matching is constrained to at/after the agenda item's
    first distinctive speech, so a cited speech never resolves to an earlier item.

Timing is derived from the caption row's `offset_index` ([[char_offset, wall_ms], …])
built by sptv_client. `clip_start` is real Europe/London wall-clock (DST-correct via
zoneinfo — the PoC hard-coded a fixed +1h BST offset, which this replaces).

Everything fails soft: no confident match → return None and the caller keeps the
plain Official Report citation.
"""
import logging
import re
from datetime import datetime, timezone
from typing import Optional

try:
    from zoneinfo import ZoneInfo
    _LONDON = ZoneInfo("Europe/London")
except Exception:  # noqa: BLE001 — tzdata missing; fall back to naive UTC (rare)
    _LONDON = timezone.utc

logger = logging.getLogger("sptv")

MIN_CONFIDENCE = 0.5          # threshold for attaching a video link
CLIP_DURATION_SECONDS = 60    # length of the clip window (clip_end - clip_start)
_MIN_WINDOW = 8               # shortest word-window to match on
_MAX_WINDOW = 12              # longest word-window to match on
_MAX_SKIP = 40                # how far into a speech to scan for a distinctive phrase


def _norm(s: str) -> str:
    s = re.sub(r'[^a-z0-9 ]', ' ', (s or "").lower())
    return re.sub(r'\s+', ' ', s).strip()


def _attr(row, name: str, default=None):
    """Read a field from either a dict or an ORM/object caption row."""
    if isinstance(row, dict):
        return row.get(name, default)
    return getattr(row, name, default)


def _count_occurrences(transcript: str, phrase: str) -> int:
    n = 0
    i = transcript.find(phrase)
    while i >= 0:
        n += 1
        i = transcript.find(phrase, i + len(phrase))
    return n


def _wall_at(offset_index: list, pos: int) -> int:
    """Wall-clock (ms) at a char offset: the largest indexed offset ≤ pos."""
    wall = offset_index[0][1]
    for off, ms in offset_index:
        if off <= pos:
            wall = ms
        else:
            break
    return wall


def _locate(transcript: str, text: str, anchor_pos: int = 0) -> Optional[dict]:
    """Find the rarest distinctive phrase from `text`, first match at/after anchor_pos.

    Returns {pos, window, phrase, occ, score} or None. `score` is lower-is-better:
    occurrence count, heavily penalised if the only match is before the anchor.
    """
    words = _norm(text).split(" ")
    if len(words) < _MIN_WINDOW:
        return None
    best: Optional[dict] = None
    for skip in range(0, min(_MAX_SKIP, len(words) - _MIN_WINDOW), 2):
        for w in range(_MAX_WINDOW, _MIN_WINDOW - 1, -1):
            window_words = words[skip:skip + w]
            if len(window_words) < w:
                continue
            phrase = " ".join(window_words)
            occ = _count_occurrences(transcript, phrase)
            if occ == 0:
                continue
            pos = transcript.find(phrase, anchor_pos)
            if pos < 0:
                pos = transcript.find(phrase)
            score = occ + (100 if pos < anchor_pos else 0)
            if best is None or score < best["score"] or (score == best["score"] and w > best["window"]):
                best = {"pos": pos, "window": w, "phrase": phrase, "occ": occ, "score": score}
            if occ == 1 and pos >= anchor_pos:
                return best  # unique + in-window: perfect
    return best


def _confidence(match: dict, anchor_pos: int) -> float:
    """Confidence in [0,1] from occurrence count, window length, and anchor position."""
    if match["pos"] < anchor_pos:
        return 0.2  # only a pre-anchor fallback match exists — weak
    occ = match["occ"]
    window = match["window"]
    conf = 1.0 if occ == 1 else max(0.0, 1.0 - 0.15 * (occ - 1))
    if window < 10:
        conf *= 0.9
    return round(conf, 3)


def _format_clip_times(wall_ms: int) -> tuple[str, str]:
    """Return (clip_start, clip_end) as Europe/London HH:MM:SS wall-clock strings."""
    start = datetime.fromtimestamp(wall_ms / 1000.0, tz=timezone.utc).astimezone(_LONDON)
    end = datetime.fromtimestamp(
        wall_ms / 1000.0 + CLIP_DURATION_SECONDS, tz=timezone.utc
    ).astimezone(_LONDON)
    return start.strftime("%H:%M:%S"), end.strftime("%H:%M:%S")


def match_speech(caption_row, speech_text: str, anchor_pos: int = 0) -> Optional[dict]:
    """Locate a speech in the cached captions and return clip timing + confidence.

    Returns {clip_start, clip_end, confidence, char_pos, wall_ms, phrase, occ, window}
    or None if the row has no usable captions or no phrase matches.
    """
    transcript = _attr(caption_row, "transcript")
    offset_index = _attr(caption_row, "offset_index")
    if not _attr(caption_row, "caption_ok", True) or not transcript or not offset_index:
        return None

    match = _locate(transcript, speech_text, anchor_pos)
    if not match:
        return None

    wall_ms = _wall_at(offset_index, match["pos"])
    clip_start, clip_end = _format_clip_times(wall_ms)
    return {
        "clip_start": clip_start,
        "clip_end": clip_end,
        "confidence": _confidence(match, anchor_pos),
        "char_pos": match["pos"],
        "wall_ms": wall_ms,
        "phrase": match["phrase"],
        "occ": match["occ"],
        "window": match["window"],
    }


def _speech_text(speech) -> str:
    if isinstance(speech, dict):
        return speech.get("text", "")
    return getattr(speech, "text", "") or str(speech)


def _anchor_pos(transcript: str, speeches: list) -> int:
    """Anchor on the agenda item's first distinctive speech (rarest opening phrase).

    Scans the item's opening speeches and picks the char position of the one whose
    distinctive phrase occurs least often — the most reliable item-start marker.
    """
    best: Optional[dict] = None
    for sp in speeches[:5]:
        r = _locate(transcript, _speech_text(sp), 0)
        if r and (best is None or r["occ"] < best["occ"]):
            best = r
    return best["pos"] if best else 0


def _clip_url(caption_row, result: dict) -> str:
    """Build the deep-link URL for a resolved match (SP TV clip_start or YouTube &t=)."""
    if _attr(caption_row, "is_youtube") and _attr(caption_row, "youtube_url"):
        start = _attr(caption_row, "start_time_utc")
        secs = int(result["wall_ms"] / 1000.0 - (start.timestamp() if start else 0))
        yt = _attr(caption_row, "youtube_url")
        sep = "&" if "?" in yt else "?"
        return f"{yt}{sep}t={max(0, secs)}"
    from ..config import settings
    slug = _attr(caption_row, "slug") or ""
    return (
        f"{settings.sptv_base_url}/meeting/{slug}"
        f"?clip_start={result['clip_start']}&clip_end={result['clip_end']}"
    )


def annotate_speeches(caption_row, speeches: list) -> int:
    """Attach a `video_deeplink` to each confidently-matched speech, in place.

    Anchors once on the item's first distinctive speech, then matches every speech
    at/after that anchor. Returns the number of speeches annotated. Fail-soft: any
    error leaves speeches untouched and returns 0.
    """
    if not _attr(caption_row, "caption_ok", False) or not speeches:
        return 0
    try:
        transcript = _attr(caption_row, "transcript") or ""
        anchor = _anchor_pos(transcript, speeches)
        annotated = 0
        for sp in speeches:
            if not isinstance(sp, dict):
                continue
            result = match_speech(caption_row, sp.get("text", ""), anchor)
            if not result or result["confidence"] < MIN_CONFIDENCE:
                continue
            sp["video_deeplink"] = {
                "url": _clip_url(caption_row, result),
                "clip_start": result["clip_start"],
                "clip_end": result["clip_end"],
                "confidence": result["confidence"],
            }
            annotated += 1
        return annotated
    except Exception as exc:  # noqa: BLE001 — never break a citation over video
        logger.warning(f"[SPTV] annotate_speeches failed: {exc}")
        return 0


def build_deeplink(caption_row, speeches: list, cited_index: int) -> Optional[dict]:
    """Build a video deep link for the cited speech of an agenda item.

    Anchors on the item's first distinctive speech, then matches the cited speech
    at/after that anchor. Returns {url, clip_start, clip_end, confidence} or None
    when there is no confident match (caller then keeps the plain OR citation).

    YouTube-hosted events (`is_youtube`) emit a `&t={seconds}` link instead — but
    these have no caption track in practice, so this path is effectively inactive.
    """
    if not speeches or cited_index < 0 or cited_index >= len(speeches):
        return None
    if not _attr(caption_row, "caption_ok", False):
        return None

    transcript = _attr(caption_row, "transcript") or ""
    anchor = _anchor_pos(transcript, speeches)
    result = match_speech(caption_row, _speech_text(speeches[cited_index]), anchor)
    if not result or result["confidence"] < MIN_CONFIDENCE:
        return None

    return {
        "url": _clip_url(caption_row, result),
        "clip_start": result["clip_start"],
        "clip_end": result["clip_end"],
        "confidence": result["confidence"],
    }
