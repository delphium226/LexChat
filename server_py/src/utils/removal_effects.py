"""FIX_PLAN P3.28: a change-record relation's removal class, read off its effect type.

The change record (`get_legislation_changes`, LEX's `/amendment/search`) types
every relation with legislation.gov.uk's own effect string ("repealed",
"omitted", "words repealed", "repealed (prosp.)" ...). The product used to count
a relation as a repeal when the string held "repeal", "revok" or "revoc", and
said of every such relation that the named provision "is no longer in force".
That was wrong in both directions (batch 12 G, 1,709 stored calls):

* it MISSED the removal families written another way: "omitted", "removed",
  "deleted", "ceases to have effect" and the "rev" abbreviations (101 types,
  3,422 relations), so a record whose only removal of a whole provision was
  "omitted" counted 0 and the answer said no repeal was retrieved;
* it OVER-CLAIMED on the relations it did count: "words repealed" removes words
  from a provision, which stays in force; "repealed (prosp.)" has not yet taken
  effect; and "power to repeal conferred" removes nothing at all.

So every relation is put in one of four classes (user decision, Session 44):

* ``provision``          a whole provision removed;
* ``provision_in_part``  part of a provision removed ("repealed in part");
* ``words_only``         words or entries removed: the text is amended, the
                         provision stays ("words omitted", "entry repealed");
* ``qualified``          a removal whose effect carries a qualification:
                         prospective, temporary, conditional, for specified
                         purposes, or for part of the United Kingdom only
                         ("repealed (S)", "repealed (EW)");

or ``None``, not a removal of the subject. "No longer in force" may be said only
of the first two. LEX's type strings and legislation.gov.uk's effects feed's are
identical (18,926 of 18,926 matched relations), so no second source is read.

The rule was written by reading every type in both vocabularies (713 feed types,
2,063 LEX types; `evidence/seam/batch12/G/p328_class.py`). Pure functions; no
import from the agent package, so `search_scope` can use it.
"""
from __future__ import annotations

import re
from typing import Any, Optional

PROVISION = "provision"
PROVISION_IN_PART = "provision_in_part"
WORDS_ONLY = "words_only"
QUALIFIED = "qualified"

# The slimmer's three counts (`agent/tools/lex._slim_amendment_results`).
PROVISION_KEY = "provision_removal_relations"
WORDS_ONLY_KEY = "words_only_removal_relations"
QUALIFIED_KEY = "qualified_removal_relations"
# The pre-P3.28 count, kept only as the last fallback for a record that carries
# no effect histogram (none of the stored ones lacks it).
LEGACY_KEY = "repeal_or_revocation_relations"

# A removal word that does not remove anything from the subject: a power
# conferred, a removal or expiry of an EARLIER amending or commencing provision
# (the subject's text is untouched by it), a saving for one. Each matched a
# naive widening on the stored vocabulary (14 "omitted in earlier amending
# provision" types alone). Batch 12 G's rule also named "expiry of" and
# "functions cease": every stored "expiry of" type is "of earlier affecting
# provision" or a "saving for" one, and no "functions ..." type carries a
# removal word, so neither alternative excluded anything the others do not.
_NOT_SUBJECT = re.compile(
    r"conferred|earlier\s+(?:affecting|amending|commencing)|^\s*saving\s+for", re.I)

# The removal families. "rev" is legislation.gov.uk's abbreviation in older
# entries ("rev (saving)", "rev. (saving)", "rev in pt (...)").
_REMOVAL = re.compile(
    r"repeal|revok|revoc|omit|\bremoved\b|\bdeleted\b"
    r"|\bcease[sd]?\s+to\s+have\s+effect\b|(?:^|\s)rev(?:\.|\s|\(|$)", re.I)

# Qualifiers, first match wins, in this order.
_QUALIFIERS = (
    ("prospective", re.compile(r"prosp", re.I)),
    ("temporary", re.compile(r"\btemp", re.I)),
    ("conditional", re.compile(r"\(cond|\bconditional", re.I)),
    ("for specified purposes", re.compile(r"specified\s+purposes", re.I)),
    # A territorial restriction in the effect itself: "(S)", "(EW)", "(E.W.)",
    # "(N.I.)". Case-sensitive on purpose: the codes are capitals, and a
    # lower-case "(s)" is a plural.
    ("for part of the United Kingdom only",
     re.compile(r"\((?:(?:E|W|S|N\.?\s?I)\.?\s?\+?\s?)+\)")),
)
_IN_PART = re.compile(r"in\s+part|in\s+pt\b|\bpart\b", re.I)
_WORDS = re.compile(r"\bwords?\b|\bentr(?:y|ies)\b", re.I)


def classify_removal(effect: Any) -> tuple:
    """``(class, qualifier)`` for one effect string.

    ``class`` is one of the four module constants, or ``None`` when the
    relation does not remove anything from the subject; ``qualifier`` is ""
    except for ``QUALIFIED``, where it names the qualification.
    """
    t = str(effect or "")
    if not _REMOVAL.search(t) or _NOT_SUBJECT.search(t):
        return None, ""
    for name, rx in _QUALIFIERS:
        if rx.search(t):
            return QUALIFIED, name
    # Words before part: no stored type carries both, and of the two readings
    # "words only" is the one that does not permit "no longer in force".
    if _WORDS.search(t):
        return WORDS_ONLY, ""
    if _IN_PART.search(t):
        return PROVISION_IN_PART, ""
    return PROVISION, ""


def counts_from_effects(effects: Optional[dict]) -> dict:
    """The three counts from an effect histogram (``{type: relations}``)."""
    out = {PROVISION_KEY: 0, WORDS_ONLY_KEY: 0, QUALIFIED_KEY: 0}
    for effect, n in (effects or {}).items():
        if not isinstance(n, int):
            continue
        cls, _ = classify_removal(effect)
        if cls in (PROVISION, PROVISION_IN_PART):
            out[PROVISION_KEY] += n
        elif cls == WORDS_ONLY:
            out[WORDS_ONLY_KEY] += n
        elif cls == QUALIFIED:
            out[QUALIFIED_KEY] += n
    return out


def removal_counts(d: Any) -> dict:
    """The three counts for one change-record result. Never raises.

    The slimmer's own counts where it wrote them; otherwise the record's effect
    histogram, classified here, which is how a result stored before P3.28
    rebuilds through current code (`seam_replay --from-raw`); otherwise, for a
    record with no histogram at all, the pre-P3.28 count, read as provision
    removals because nothing finer can be said of it.
    """
    try:
        if not isinstance(d, dict):
            return counts_from_effects(None)
        if all(isinstance(d.get(k), int) for k in (PROVISION_KEY, WORDS_ONLY_KEY, QUALIFIED_KEY)):
            return {k: d[k] for k in (PROVISION_KEY, WORDS_ONLY_KEY, QUALIFIED_KEY)}
        effects = d.get("effects")
        if isinstance(effects, dict):
            return counts_from_effects(effects)
        out = counts_from_effects(None)
        if isinstance(d.get(LEGACY_KEY), int):
            out[PROVISION_KEY] = d[LEGACY_KEY]
        return out
    except Exception:
        return counts_from_effects(None)
