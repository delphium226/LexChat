"""FIX_PLAN P4.28: an index record whose `legislation_id` is a placeholder.

LEX's index holds OCR'd historical records whose `legislation_id` is not a
reference: "[UNCLEAR: possible reference 'ni/1944/80']", "[UNCLEAR: no
document reference provided]", "ukpga/1855/27 [UNCLEAR: local act reference]".
Their `uri` is built on the same text (0 of 5,020 raw rows carried a uri that
differs, `evidence/seam/s52/p334f/measure_unclear.txt`), so nothing in the row
identifies the instrument, and a "possible reference" inside the bracket is the
OCR model's guess, not the index's. Over the stored runs `search_legislation`
returned 324 such rows (31 ids) and `search_legislation_sections` 20 (2 ids),
and 14 sources-rail entries carried one: a link a legal professional can click
that leads nowhere.

The id is still LEX's own key for the record: both stored section searches
made with one returned 10 provisions, and one of them (6387 t2) held the
answer. So the Worker keeps the row and may search within it by that id; what
code must never do is offer the id, or the uri built on it, as a reference:
no rail entry, and no id named in a scope block, limb or footer. Where a
count is stated, the record is counted, as "with no identifiable reference".

P3.34's follow-up wrote the test first, in `utils.definitions`, which still
exports it under the same name.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

# A square bracket, or the index's own word. A round bracket is not a sign:
# "ukpga/1932/15 (22 & 23 Geo. 5. c. xv)" is a reference with a gloss.
_PLACEHOLDER_ID = re.compile(r"[\[\]]|\bUNCLEAR\b", re.I)


def is_placeholder_id(lid: Any) -> bool:
    """True where a legislation_id is an OCR placeholder, not a reference."""
    return bool(_PLACEHOLDER_ID.search(str(lid or "")))


def split_placeholders(ids: Iterable[Any]) -> tuple:
    """`(references, placeholders)`: the ids in order, each list deduplicated,
    a placeholder never among the references."""
    refs: list = []
    held: list = []
    for lid in ids or []:
        s = str(lid or "").strip()
        if not s:
            continue
        bucket = held if is_placeholder_id(s) else refs
        if s not in bucket:
            bucket.append(s)
    return refs, held


def unidentified_phrase(n: int, noun: bool = True) -> str:
    """How a list that names instruments by id counts the ones it cannot name:
    "1 instrument with no identifiable reference", or without the noun after a
    head that already says "instrument(s)" ("1 with no identifiable reference").
    """
    if noun:
        return (f"{n} instrument{'s' if n != 1 else ''} "
                "with no identifiable reference")
    return f"{n} with no identifiable reference"
