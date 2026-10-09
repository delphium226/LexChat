"""P4.24 (B8): a Sources-rail entry titled with a bare id gets its title in code.

`agent_shared._extract_sources_inner` titles a change-record group with its
id (`ssi/1901/3`), and a section search with no earlier search hit takes its
title from the result or the id and its URL from the result or nothing. The
rail is the lawyer's verification surface, and an id is not a title. Batch 10
C counted 807 such entries over 4,917; batch 12 D 1,634 over the rails the
built code produces with P4.3's lever R (which re-admits change-record
instruments an answer cites), 590 of them with no URL.

The title comes, in this order, from:
  1. the same turn's retrievals: another source this turn retrieved for the
     same id with a real title (a search hit, a section search, a text read),
     else the title a `lookup_legislation` for the id returned;
  2. the made-under record (`made_under_store.titles_for`): an SSI's or UK
     SI's own title, else an Act's title as the record's recitals resolved it.
An entry with no exact title stays as it is: nothing is invented. An entry
with no URL gets legislation.gov.uk's identifier URI for its id, which is
exact for any id of the form this module recognises.

Pure functions; `agent_core.title_rail_sources` calls them. The order of the
sources is kept and no entry is added or removed.
"""
from __future__ import annotations

import re

# A legislation id as a rail title: `ssi/1901/3`, `eur/1901/3`, or a regnal-year
# id `ukpga/Edw7/1/9` (four segments). Nothing else is read as an id.
_BARE_ID = re.compile(r"^[a-z]+/(?:\d{4}|[A-Za-z]+\d*/[\d-]+)/\d+$")
LEG_ID_URL = "https://www.legislation.gov.uk/id/"
_YEAR = re.compile(r"(?<!\d)(?:1[2-9]\d\d|20\d\d)(?!\d)")


def bare_id(title) -> str:
    """The id a rail title consists of, or "" when the title is not a bare id."""
    t = str(title or "").strip()
    return t if _BARE_ID.match(t) else ""


def id_url(lid: str) -> str:
    """legislation.gov.uk's identifier URI for an id, or "" for anything else."""
    return LEG_ID_URL + lid if bare_id(lid) else ""


def exact_title(title) -> str:
    """A title fit to show: not empty, not itself an id, not cut short (the
    record shortens a title over 300 characters with an ellipsis), and naming
    a year, as an instrument's title does. LEX returned a section heading
    ("Short title, commencement, and extent.") as one old Act's search-hit
    title; of 1,644 titles the stored rails would take, it was the only one
    with no year (batch 12 D)."""
    t = str(title or "").strip()
    if not t or bare_id(t) or t.endswith("…") or not _YEAR.search(t):
        return ""
    return t


def in_turn_titles(retrieved, lookup_titles=None) -> dict:
    """{id: title} from the turn's own retrievals: the first real title a
    source retrieved for the id carries, else the title a `lookup_legislation`
    for it returned (a lookup adds no rail source, but its title is LEX's)."""
    out: dict = {}
    for src in retrieved or []:
        lid = src.get("_lid")
        title = exact_title(src.get("title"))
        if lid and title and lid not in out:
            out[lid] = title
    for lid, title in (lookup_titles or {}).items():
        title = exact_title(title)
        if lid and title and lid not in out:
            out[lid] = title
    return out


def untitled_ids(rail, retrieved, lookup_titles=None) -> list:
    """The ids of rail entries titled with a bare id that the turn's own
    retrievals cannot title: what to ask the made-under record for."""
    have = in_turn_titles(retrieved, lookup_titles)
    out: list = []
    for src in rail or []:
        lid = bare_id(src.get("title"))
        if lid and lid not in have and lid not in out:
            out.append(lid)
    return out


def fill_rail(rail, retrieved, record_titles, lookup_titles=None) -> tuple:
    """`(rail, titled, given_a_url)`: the rail with each bare-id title replaced
    by an exact one where there is one, and each such entry with no URL given
    its id's URI. Entries are copied, never mutated."""
    have = in_turn_titles(retrieved, lookup_titles)
    out: list = []
    titled = urled = 0
    for src in rail or []:
        lid = bare_id(src.get("title"))
        if not lid:
            out.append(src)
            continue
        new = dict(src)
        title = have.get(lid) or exact_title((record_titles or {}).get(lid))
        if title:
            new["title"] = title
            titled += 1
        if not new.get("url"):
            new["url"] = id_url(lid)
            urled += 1
        out.append(new)
    return out, titled, urled
