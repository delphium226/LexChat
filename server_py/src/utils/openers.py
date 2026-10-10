"""P3.2 (B6): an answer that opens by agreeing before anything was checked.

"You are absolutely right to challenge this" reads to a lawyer as a
resolution. In the pre-pilot and every replay since, it opened turns on which
the bot had not re-read the text, and on which it then changed position, or
did not (6406, 6370). `replay_report openers` counts 42 such openers in 1,580
replayed answers and 8 in the pre-pilot's 179.

This removes the agreement FORMULA from the start of a Manager answer and
nothing else. It is cosmetic by design and is not the fix for B6: it cannot
make a position change re-retrieve or cite anything (the rest of P3.2's
acceptance). What it guarantees is that the register never announces a
concession the answer does not go on to make.

The rules are conservative, and every edit over the stored corpus (1,633
answers) was read before wiring (Session 32):
  * a SCOPED agreement ("You are correct that X") is left alone: it says what
    is agreed, and the acceptance allows it;
  * a plain "Yes, that is correct." is left alone too: it is often the answer
    to a yes/no question (6409), which code cannot tell from a capitulation;
  * a sentence that is the formula alone ("You make a very precise point.")
    is dropped, unless it carries a link or a number, so a citation is never
    lost, and a "However," it leaves dangling goes with it;
  * a formula leading into content ("You are right to challenge this, and
    your reading ...") loses the formula and keeps the content;
  * at most two passes, for a formula followed by another ("You are correct,
    and I apologise for the confusion.");
  * anything else is left as written.
P4.13 widened the object of the bare and thanks formulas to the bot's own
earlier answer ("You are correct to challenge my earlier statement."): one new
edit over the 1,708 non-Deep-Research answers stored at the time, read.
P4.16 widened the bare formula's VERB to "highlight" ("You are correct to
highlight this."): the only challenge verb other than "challenge" that opens a
stored answer in this formula, and the thanks formula's verbs needed nothing
(every stored "Thank you for" opener thanks the lawyer for a citation or a
title). One new edit over the 1,783 non-Deep-Research answers stored, read.
Fail-soft: any error returns the answer unchanged.
"""

import re

_DEGREE = r"(?:(?:absolutely|entirely|quite|completely|perfectly|exactly|indeed|very|so)\s+)?"
_YOU_ARE = r"(?:yes[,.!]?\s+)?you(?:'re|\s+are)\s+" + _DEGREE + r"(?:correct|right)"

_SCOPED = re.compile(
    r"^" + _YOU_ARE + r"\s+(?:that|in\s+(?:your|noting|saying|pointing)|about|regarding|on|"
    r"to\s+(?:note|say|point\s+out|observe))\b", re.I)

# The bot's own earlier answer as the object of a challenge: "You are correct
# to challenge my earlier statement" (P4.13). Only the bot's OWN answer, named
# by one of these nouns, so a sentence naming anything else is left alone.
_MY_EARLIER = (r"my\s+(?:earlier|previous|last|original)\s+"
               r"(?:statement|answer|response|reply|position|assessment)")

# The agreement formula at the start of an answer: (kind, whether what follows
# the formula is content by itself, pattern). Each pattern matches the FORMULA
# only; what follows it is the content test's business.
_FORMULAS = (
    ("bare", False, re.compile(
        r"^" + _YOU_ARE + r"(?:\s+to\s+(?:challenge|question|query|push\s+back\s+on|"
        r"press\s+(?:me\s+)?on|flag|raise|highlight|pick\s+up\s+on)\s+(?:this|that|me|the\s+point|"
        + _MY_EARLIER + r")(?:\s+point)?)?", re.I)),
    ("praise", False, re.compile(
        r"^you(?:'ve|\s+have)?\s+(?:make|made|raise|raised|hit\s+on|highlight|highlighted)\s+"
        r"(?:a|an|the)\s+(?:(?:very|really|entirely|highly)\s+)?(?:\w+\s+){0,2}"
        r"(?:point|observation|argument|question|distinction|catch)"
        r"(?:\s+(?:about|regarding|on|here|there)\b[^.!?:;—,\[(]{0,80})?", re.I)),
    # "You have correctly identified that X": X is the content. Only with
    # "that": "You have correctly identified a gap" has no clause to keep.
    ("praise", True, re.compile(
        r"^you(?:'ve|\s+have)?\s+(?:correctly|rightly)\s+(?:identified|pointed\s+out|noted|"
        r"spotted|highlighted)\s+that\s+", re.I)),
    ("apology", False, re.compile(
        r"^(?:my\s+apologies|i\s+apologi[sz]e|apologies|sorry)"
        r"(?:\s+for\s+(?:that|(?:the|any|my)\s+(?:confusion|error|oversight|mistake|"
        r"inconvenience)(?:\s+in\s+my\s+(?:previous|earlier|last)\s+(?:answer|response|"
        r"reply))?))?", re.I)),
    ("thanks", False, re.compile(
        r"^thank\s+you\s+for\s+(?:pressing|pointing|flagging|challenging|raising|highlighting|"
        r"catching|pushing)(?:\s+(?:me\s+)?(?:on\s+)?(?:this|that|it|" + _MY_EARLIER + r")"
        r"(?:\s+out)?(?:\s+point)?)?",
        re.I)),
)

# What may join a formula to the content it leads into.
_CONNECTOR = re.compile(r"^\s*(?:[,;:]\s*(?:and|but|so)?\s*|\s*[—–-]\s*|\s+and\s+)", re.I)
# A contrast that answered the dropped concession, and reads wrong without it.
_DANGLING = re.compile(r"^(?:However|But|Nevertheless|That said|Even so),?\s+")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n")
_KEEP = re.compile(r"\]\(|https?://|\d")


def _capitalise(s: str) -> str:
    """Upper-case the first letter, inside a leading link or emphasis too."""
    m = re.match(r"^([\[*_]*)(\w)", s or "")
    return s[:m.start(2)] + m.group(2).upper() + s[m.end(2):] if m else s


def _one_pass(text: str) -> tuple:
    lead = len(text) - len(text.lstrip())
    body = text[lead:]
    if not body or _SCOPED.match(body):
        return text, None
    for kind, tail_is_content, rx in _FORMULAS:
        m = rx.match(body)
        if not m:
            continue
        end = _SENTENCE_END.search(body)
        sentence = body[: end.start()] if end else body
        rest_of_answer = body[end.end():] if end else ""
        head = sentence[: m.end()]
        if (m.end() > len(sentence) or head.count("[") != head.count("]")
                or head.count("(") != head.count(")")):
            # Never cut inside a link or a parenthesis.
            return text, None
        tail = sentence[m.end():]
        if not tail.strip(" .!"):
            # The formula is the whole sentence: drop it, if anything is left
            # and it carries no link or number.
            if _KEEP.search(sentence) or not rest_of_answer.strip():
                return text, None
            rest = rest_of_answer.lstrip()
            d = _DANGLING.match(rest)
            if d:
                rest = _capitalise(rest[d.end():])
            return text[:lead] + rest, kind
        c = _CONNECTOR.match(tail)
        if c and tail[c.end():].strip():
            return text[:lead] + _capitalise(tail[c.end():].lstrip()) + body[len(sentence):], kind
        if tail_is_content and tail.strip():
            return text[:lead] + _capitalise(tail.lstrip()) + body[len(sentence):], kind
        return text, None
    return text, None


def strip_agreement_opener(answer: str) -> tuple:
    """(answer, kind) with unscoped agreement formulas removed from the start;
    kind is the first one removed, None when nothing was changed. Never
    raises."""
    try:
        text, first = answer or "", None
        for _ in range(2):
            text, kind = _one_pass(text)
            if not kind:
                break
            first = first or kind
        return (text, first) if first else (answer, None)
    except Exception:
        return answer, None
