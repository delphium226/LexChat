"""P4.3 (B8): does a Worker report vouch for a source it retrieved?

`agent_core._source_is_used` decides which of a Worker's accumulated sources
reach the lawyer's Sources rail. It used to keep a source only on an excerpt or
an exact identifying token (`legislation_id`, URL, `cite`, `sub`) in the report,
and when that kept nothing it fell back to the WHOLE accumulator, every Phase-1
search hit included. Batch 10 C measured that one fall-back as 67% of the
unused sources on report turns (879 of 1,321, on 90 of 1,393 turns): mostly
negative answers whose report names the instruments in words, never by URL.

This module holds the two tests the filter now applies, and nothing else:

* `token_in`: the old exact-token test, made boundary-aware. A bare substring
  test kept `ssi/1901/3` for a report citing `ssi/1901/31`, and a neutral
  citation `[1901] UKSC 1` for `[1901] UKSC 12`.
* `named_in`: the report names the source in words: its title (normalised,
  never as the head of a longer title such as "... Act 1901 (Commencement No. 1)
  Regulations 1902"), its SI number "YYYY/N", an EU number "N/YYYY", or an old
  SI's "YYYY No. N". Legislation and case-law sources only: the parliamentary
  kinds were never measured, so their keep test is unchanged.

A short form ("the 1901 Act", an acronym) is deliberately NOT a naming: of 21
candidates in the stored replays, 16 were "the YYYY Act" matching a
commencement instrument's title, which names the parent Act, not the source.
"""
import re

# Source kinds `agent_shared._extract_sources_inner` gives legislation.
LEGISLATION_KINDS = frozenset({"Act", "SI", "Statute", "Draft SI"})
# legislation.gov.uk types whose citation is "YYYY/N" (an SI number).
SI_TYPES = frozenset({"ssi", "uksi", "wsi", "nisr", "nisi", "ukdsi", "sdsi"})

MIN_TOKEN_CHARS = 6   # the old filter's floor: a 3-char cite would match anywhere
MIN_TITLE_CHARS = 8   # a title shorter than this is not distinctive

_BARE_LID = re.compile(r"^[a-z]+/\d{4}/\d+")
_LID_PARTS = re.compile(r"^([a-z]+)/(\d{4})/(\d+)$")
_OLD_SI = re.compile(r"(\d{4}) No\. ?(\d+)", re.I)
# What follows a title that is the head of a longer instrument title: a
# parenthesis, then "Regulations"/"Order"/"Rules"/"Scheme" (English) or a year
# (Welsh titles put the instrument word first: "Gorchymyn Deddf ... 1901
# (Cychwyn Rhif 1) 1902").
_LONGER_TITLE = re.compile(
    r"\s*\([^)]{1,80}\)\s*(?:regulations|order|rules|scheme|\d{4}(?!\d))"
)
_STRIP_CHARS = re.compile(r"[*_`,]")
# Line breaks are kept: a case named in one bullet is not cited by the next
# bullet's neutral citation (`_names_other_judgment` stops at a line end).
_SPACES = re.compile(r"[^\S\n]+")


def is_legislation(src: dict) -> bool:
    return bool(src.get("_lid")) or src.get("kind") in LEGISLATION_KINDS


def _bounded(text: str, start: int, end: int, lead: bool, trail: bool) -> bool:
    """Whether text[start:end] stands alone: no letter or digit runs into it."""
    if lead and start > 0 and text[start - 1].isalnum():
        return False
    if trail and end < len(text) and text[end].isalnum():
        return False
    return True


def token_in(token, text: str) -> bool:
    """An identifying token occurs in text, not as part of a longer one.

    The guard applies only on a side where the token itself ends in a letter or
    digit: a URL token's trailing digit must not run on (`/ssi/1901/3` inside
    `/ssi/1901/31`), but a token opening with "[" needs no guard before it.
    """
    tok = str(token or "")
    if len(tok) < MIN_TOKEN_CHARS or not text:
        return False
    lead, trail = tok[0].isalnum(), tok[-1].isalnum()
    i = text.find(tok)
    while i != -1:
        if _bounded(text, i, i + len(tok), lead, trail):
            return True
        i = text.find(tok, i + 1)
    return False


def norm_text(text: str) -> str:
    """Lower case, straight quotes, no emphasis marks or commas, single spaces
    (line breaks kept).

    Commas go so "Widget Act, 1901" (an older citation style) reads as the title
    "Widget Act 1901"; emphasis marks so "**Widget Act 1901**" does.
    """
    t = (text or "").lower()
    t = t.replace("’", "'").replace("‘", "'").replace(" ", " ")
    t = _STRIP_CHARS.sub("", t)
    return _SPACES.sub(" ", t)


def norm_title(title: str) -> str:
    t = norm_text(title).strip()
    return t[4:] if t.startswith("the ") else t


def title_named(title: str, text_n: str, longer_guard: bool = True,
                other=None) -> bool:
    """A normalised title occurs in normalised text as a whole title.

    Not inside a longer word run on either side, (for legislation) not as the
    head of a longer instrument title, and not where `other(end)` says the
    occurrence names a different source.
    """
    if len(title) < MIN_TITLE_CHARS or _BARE_LID.match(title):
        return False
    i = text_n.find(title)
    while i != -1:
        end = i + len(title)
        if (_bounded(text_n, i, end, True, True)
                and not (longer_guard and _LONGER_TITLE.match(text_n, end))
                and not (other and other(end))):
            return True
        i = text_n.find(title, i + 1)
    return False


# A neutral citation in normalised text: "[1902] ewca civ 9", "[1901] ewhc 5
# (ch)" (year, court, number), and a judgment's URL path.
_NCN = re.compile(r"\[(\d{4})\]\s+([a-z]+(?:\s+[a-z]+){0,2}?)\s+(\d+)")
_CASE_URL = re.compile(r"caselaw\.nationalarchives\.gov\.uk/([a-z0-9/-]+?)/?(?=[)\s\]#?.;]|$)")
CASE_LOOKAHEAD_CHARS = 100


def _ncn_key(text: str):
    m = _NCN.search(norm_text(text))
    return m.groups() if m else None


def _case_url_key(url: str) -> str:
    m = _CASE_URL.search((url or "").lower())
    return m.group(1) if m else ""


def _names_other_judgment(src: dict, text_n: str, end: int) -> bool:
    """The case title at `end` is followed, in the same sentence, by a neutral
    citation or judgment URL that is not this source's.

    A first-instance judgment and its appeal share their parties' names, and
    the Worker is nudged (A2) to cite the higher court: a report citing
    "Widget Co v Example Ltd [1902] EWCA Civ 9" does not cite the first
    instance "[1901] EWHC 5", which a title test alone would keep.
    """
    win = text_n[end:end + CASE_LOOKAHEAD_CHARS]
    stops = [i for i in (win.find("\n"), win.find(". "), win.find("; ")) if i != -1]
    win = win[:min(stops)] if stops else win
    found = [m for m in (_NCN.search(win), _CASE_URL.search(win)) if m]
    if not found:
        return False
    first = min(found, key=lambda m: m.start())
    if first.re is _CASE_URL:
        own = _case_url_key(src.get("url") or "")
        return bool(own) and first.group(1) != own
    own = _ncn_key(str(src.get("cite") or src.get("sub") or ""))
    return bool(own) and first.groups() != own


def _number_named(src: dict, text: str) -> bool:
    """The source's own number, in the form a lawyer writes it."""
    lid = str(src.get("_lid") or "").strip().lower()
    m = _LID_PARTS.match(lid)
    if m:
        typ, year, num = m.groups()
        if typ in SI_TYPES and re.search(
                rf"(?<![\w/]){year}/{num}(?![\w/])", text):
            return True
        if typ.startswith("eu") and re.search(
                rf"(?<![\w/]){num}/{year}(?![\w/])", text):
            return True
        if typ in SI_TYPES and re.search(
                rf"(?<!\d){year} No\.? ?{num}(?!\d)", text, re.I):
            return True
        return False
    # An old SI whose identifier is its printed number: "1901 No. 3 (S. 1)".
    for field in (lid, str(src.get("cite") or "")):
        om = _OLD_SI.search(field)
        if om:
            year, num = om.groups()
            return bool(
                re.search(rf"(?<![\w/]){year}/{num}(?![\w/])", text)
                or re.search(rf"(?<!\d){year} No\.? ?{num}(?!\d)", text, re.I))
    return False


def named_in(src: dict, text: str) -> bool:
    """The text names a legislation or case-law source in words.

    Every other kind returns False: their keep test is the token test alone.
    """
    if not text:
        return False
    if src.get("kind") == "Case":
        text_n = norm_text(text)
        return title_named(norm_title(src.get("title") or ""), text_n,
                           longer_guard=False,
                           other=lambda end: _names_other_judgment(src, text_n, end))
    if not is_legislation(src):
        return False
    if title_named(norm_title(src.get("title") or ""), norm_text(text)):
        return True
    return _number_named(src, text)
