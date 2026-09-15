"""Provision-link enforcement (FIX_PLAN P1.6, bucket B14).

**The problem this solves, stated precisely.** A legislation.gov.uk provision URL
that no tool returned still *resolves* — `.../asp/2000/1/section/21` is a real
page whatever the research did — so a manufactured link reads to a lawyer exactly
like a verified citation and survives every link-check the sources rail supports.
That is why B14 is a correctness bucket and not a formatting one.

P1.4 removed the *instruction* to manufacture (`WORKER_SYSTEM_PROMPT` used to say
"you MUST manually append `/section/{number}` to the Base URI") and handed the
model the API's own provision URL instead. Measured over the replay corpus, links
pointing at a provision **no tool ever retrieved** went 75 -> 0. What remains is
the mechanism, not the outcome: in 19% of cited provision links the model is still
*reconstructing* the URL rather than copying one, because the retrieval that
carried it was summarised and the summariser does not keep URLs. It happens to
reconstruct correctly today. Nothing makes it do so.

Invariant 2 (code enforcement over prompt obedience) therefore gives two halves,
and this module holds both:

* **`provision_url_block`** - the cause. Appended *after* summarisation, exactly
  like the Phase-2 nudge and for exactly the same reason: the summariser cannot
  eat what it never saw. The model then copies a URL instead of rebuilding one.
* **`enforce_provision_links`** - the guarantee. At the seam where an answer is
  assembled, any provision-level legislation.gov.uk link whose URL was never
  returned by a tool in this run is demoted to the Act (when the Act *was*
  retrieved) or unlinked, and marked.

**Why this does not simply strip links.** When the model genuinely holds only the
Act, linking the Act is *correct* - the error is the label naming a provision as
though it had been verified. Stripping the link would trade a bad link for a bad
claim, which is the same trade in the other direction.

**Why the marker is a footnote and not prose.** The only thing we can state with
certainty is that no tool returned a URL for this citation. We cannot say the
provision was "not retrieved": a whole-Act `get_legislation_text` carries one URL
for the Act and none for its sections, so the text may well have been read.
Invariant 1 says a disclosure must be TRUE, so the wording asserts what is known
about the *link* and claims nothing about the research.
"""

from __future__ import annotations

import json
import re
from typing import Iterable, Optional

import logging

logger = logging.getLogger("agent")

__all__ = [
    "normalise_leg_url",
    "is_provision_url",
    "act_base_url",
    "harvest_legislation_urls",
    "provision_url_block",
    "enforce_provision_links",
    "PROVISION_MARKER",
    "PROVISION_FOOTNOTE",
]

_LEG_HOST = "legislation.gov.uk"

# Markdown inline link. Bounded label so a stray unmatched bracket cannot make
# the scan quadratic over a long report.
_MD_LINK = re.compile(r"\[([^\]\n]{1,300})\]\((https?://[^)\s]+)\)")

# The path segments legislation.gov.uk uses below an instrument. `paragraph` and
# `crossheading` only ever appear beneath one of the others, but they are listed
# so a deep URL is still recognised as provision-level.
_PROVISION_SEGMENT = re.compile(
    r"/(?:section|regulation|article|schedule|rule|order|chapter|part|paragraph|crossheading)/",
    re.I,
)

# Trailing punctuation a model routinely glues onto a URL inside prose.
_URL_TRAILING = ".,;:)]}'\"“”’"

PROVISION_MARKER = "†"
PROVISION_FOOTNOTE = (
    "† No provision-level URL was returned by any search for this citation; "
    "where a link is shown it points at the instrument as a whole."
)


def normalise_leg_url(url: str) -> str:
    """Reduce a legislation.gov.uk URL to a comparable key.

    Four spellings of the same resource are in play at once and every one of
    them appears in real traffic:

      * `http://` and `https://` - LEX returns `http://`, models emit `https://`;
      * with and without `www.`;
      * with and without the `/id/` segment - `legislation/search` returns the
        short form and `legislation/section/search` a full `/id/` URI;
      * with and without a trailing slash, and with prose punctuation stuck on.

    Comparing raw strings would report a URL as manufactured because the model
    upgraded the scheme. Returns "" for anything that is not legislation.gov.uk,
    which is the caller's signal to leave the link alone.
    """
    if not url:
        return ""
    s = str(url).strip().rstrip(_URL_TRAILING)
    s = re.sub(r"^https?://", "", s, flags=re.I)
    if _LEG_HOST not in s.lower():
        return ""
    s = re.sub(r"^www\.", "", s, flags=re.I)
    s = s.split("#", 1)[0].split("?", 1)[0]
    s = s.replace("/id/", "/", 1)
    return s.rstrip("/").lower()


def is_provision_url(url: str) -> bool:
    """Does this URL point below the level of a whole instrument?"""
    key = normalise_leg_url(url)
    return bool(key) and bool(_PROVISION_SEGMENT.search("/" + key))


def act_base_url(url: str) -> str:
    """`.../asp/2000/1/section/21` -> `.../asp/2000/1`, normalised.

    Returns "" when the URL is not a legislation.gov.uk provision URL.
    """
    key = normalise_leg_url(url)
    if not key:
        return ""
    m = _PROVISION_SEGMENT.search("/" + key)
    if not m:
        return ""
    # The match ran against a leading "/" we prepended, so subtract it.
    return key[: m.start()].rstrip("/")


def _walk(obj, out: set) -> None:
    if isinstance(obj, dict):
        for v in obj.values():
            if isinstance(v, str) and _LEG_HOST in v.lower():
                key = normalise_leg_url(v)
                if key:
                    out.add(key)
            else:
                _walk(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _walk(v, out)


def _loads_prefix(raw):
    """Parse the JSON value a tool result *starts* with.

    `run_worker_tool` appends the Phase-2 nudge after the JSON, so a plain
    `json.loads` raises "Extra data" on exactly the calls that returned results -
    the successful ones.
    """
    if not isinstance(raw, str):
        return raw if isinstance(raw, (dict, list)) else None
    try:
        obj, _ = json.JSONDecoder().raw_decode(raw.lstrip())
        return obj
    except Exception:
        return None


def harvest_legislation_urls(raw_result, into: Optional[set] = None) -> set:
    """Every legislation.gov.uk URL a raw tool result carried, normalised.

    Harvested from the **raw** result, before summarisation - that is the whole
    point. The question this set answers is "did the research retrieve this
    provision", not "was the model shown the string", and the two diverge on
    precisely the ~70% of section searches that get summarised.

    Deliberately recursive and key-agnostic: the two LEX endpoints spell the
    identifier three ways (`uri`, `id`, `url`) and a future tool will spell it a
    fourth. Fail-soft - an unparseable result contributes nothing rather than
    raising into a research run.
    """
    out = into if into is not None else set()
    try:
        parsed = _loads_prefix(raw_result)
        if parsed is not None:
            _walk(parsed, out)
    except Exception:  # pragma: no cover - defensive
        logger.debug("[Citations] URL harvest skipped", exc_info=True)
    return out


def provision_url_block(raw_result, max_entries: int = 12) -> str:
    """The citation-URL block appended after a summarised section retrieval.

    Summarisation turns a 32K `search_legislation_sections` response into ~3.5K
    of prose that names the sections and carries no URLs at all, so the model -
    forbidden from inventing a URL and holding none - reconstructs one from the
    Act's base URI. This hands the URLs back.

    Appended after summarisation for the same reason the Phase-2 nudge is (see
    `run_worker_tool`): the summariser cannot discard what it never saw. Returns
    "" when the result carries no provision URLs, so the caller may append
    unconditionally.
    """
    parsed = _loads_prefix(raw_result)
    if not isinstance(parsed, dict):
        return ""
    results = parsed.get("results")
    if not isinstance(results, list):
        return ""

    lines: list = []
    seen: set = set()
    for item in results:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or item.get("uri") or "")
        if not url or not is_provision_url(url):
            continue
        key = normalise_leg_url(url)
        if key in seen:
            continue
        seen.add(key)
        ptype = str(item.get("provision_type") or "").strip()
        number = item.get("number")
        label = " ".join(
            p for p in (ptype, str(number) if number is not None else "") if p
        )
        lines.append(f"- {label or 'provision'}: {url}")
        if len(lines) >= max_entries:
            break

    if not lines:
        return ""
    return (
        "\n\n[CITATION URLS - these are the URLs this retrieval returned. Use them "
        "verbatim when citing these provisions. Do NOT build a provision URL from "
        "an Act's base URI; if a provision you want to cite is not listed here, "
        "cite it in bold text without a link.]\n" + "\n".join(lines)
    )


def enforce_provision_links(
    text: str,
    retrieved: Optional[Iterable[str]],
) -> tuple:
    """Rewrite provision links that no tool returned. Returns (text, demoted, unlinked).

    Three cases, and the middle one is the whole design:

      * URL **was** returned by a tool -> untouched, however the model spells it.
      * URL not returned but the **Act** was -> the link is retargeted at the Act
        and the label marked. The lawyer still gets a working link to the right
        instrument and is told it is not the provision they were shown.
      * neither -> the link is removed and the citation left in bold, which is
        what `CITATION PROTOCOL -> VALIDATION` already tells the model to do.
        This is enforcement making a stated rule true, not a new policy.

    Only legislation.gov.uk provision URLs are considered. Case law, Official
    Report and every other host pass through untouched - they have their own
    identifier discipline and are not what B14 measures.

    Idempotent: re-running over already-marked text is a no-op, so it is safe at
    both the worker-report seam and the final-answer seam (a Manager that passes
    the report through verbatim would otherwise mark it twice).
    """
    if not text or retrieved is None:
        return text, 0, 0
    retrieved_keys = {k for k in (normalise_leg_url(u) for u in retrieved) if k}

    counts = {"demoted": 0, "unlinked": 0}

    def _fix(m) -> str:
        label, url = m.group(1), m.group(2)
        key = normalise_leg_url(url)
        if not key or not is_provision_url(url):
            return m.group(0)
        if key in retrieved_keys:
            return m.group(0)
        if PROVISION_MARKER in label:          # already enforced upstream
            return m.group(0)
        base = act_base_url(url)
        marked = f"{label} {PROVISION_MARKER}"
        if base and base in retrieved_keys:
            counts["demoted"] += 1
            # Truncate the model's own URL rather than rebuilding from the
            # normalised key: the key has lost the scheme and the `www.`, and a
            # rewritten link that changes host spelling mid-answer looks like a
            # different source to a lawyer checking citations.
            cut = _PROVISION_SEGMENT.search(url)
            return f"[{marked}]({url[: cut.start()] if cut else base})"
        counts["unlinked"] += 1
        return f"**{marked}**"

    out = _MD_LINK.sub(_fix, text)
    if (counts["demoted"] or counts["unlinked"]) and PROVISION_FOOTNOTE not in out:
        out = out.rstrip() + "\n\n" + PROVISION_FOOTNOTE
    return out, counts["demoted"], counts["unlinked"]
