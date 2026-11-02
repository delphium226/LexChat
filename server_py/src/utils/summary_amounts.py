"""P3.58: a money amount the summariser wrote that its source does not hold.

P3.45 removes a case citation a summary carries and the summarised text does
not. Nothing checked an amount: in a stored 6382 run the summariser gave
SSI 2024/173 a '£151' figure, twice, inside formulas the instrument does not
contain (its whole text holds no '£' and no '151'), and the answer repeated it;
three other stored summaries add '£300' from the summariser's own knowledge of
a different instrument ("which typically specifies the £300").

This module finds the amounts in a summary and says which the source (or the
research question) does not hold. `summary_citations.strip_unsourced_citations`
removes each such amount's passage with P3.45's actions (the list item or the
sentence; never a heading or the block under it).

Amounts read: '£151', '£1,510.00', '£1.5 million', 'GBP 40', '151 pounds',
'50 pence' / '50p', and an amount in words before 'pounds' or 'pence'.

**Held** errs towards held, because removing a figure the source does hold is
the worse mistake. An amount is held when:

* the source states that value as money in any written form: a decimal point
  written '.', '·', '∙', ':' or '-' ('£237∙55', '£3-48', '£2:9' in old texts),
  a thousands separator written ',' or a space ('£40 000');
* or the figure's digits occur anywhere in the source, as written or with
  separators normalised as above, with no word boundary required: a table
  whose cells run together ("100235.0012,262", '£' in the column heading)
  holds '£235.00' and '£12,262', and a figure the source gives in another
  currency ('EUR 250') holds '£250';
* or it is a step from an amount the source states: one penny either side
  ('£473.99' for "less than £474.00") or, for a whole-pound amount, a pound
  either side ('£585' for "less than £586");
* or the research question (the brief) holds it, in the same senses.

So a short figure is usually found somewhere in a long source and held; the
amounts the summariser invented were not short. Measured over every stored
summary (Session 52): 2,251 amounts read, 7 unheld in 5 summaries, every one
the summariser's; 24 held only by their digits, every one read and in the
source. Nothing is ever added. Fail-soft: an error yields no amounts (nothing
removed).
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import NamedTuple, Optional

_NUM = r"(?P<n>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
_SCALE = r"(?:\s*(?P<s>thousand|million|billion|mn|bn|m|k)\b)?"
_MULT = {"k": 1000, "thousand": 1000, "m": 10**6, "mn": 10**6, "million": 10**6,
         "bn": 10**9, "billion": 10**9}
# '£151', 'GBP 151', '£1.5 million'
_SIGN = re.compile(r"(?:£|&pound;|&#163;|\bGBP\s?)\s?" + _NUM + _SCALE, re.I)
# '151 pounds', '1.5 million pounds'
_POUNDS = re.compile(r"(?<![\w.,])" + _NUM + _SCALE + r"\s+pounds?\b", re.I)
# '50 pence', '50p' (not '5p.' of a page reference or 's.5p')
_PENCE = re.compile(r"(?<![\w.,£])" + _NUM + r"\s?(?:pence\b|p\b(?![.\w]))", re.I)
_UNITS = ("zero one two three four five six seven eight nine ten eleven twelve thirteen "
          "fourteen fifteen sixteen seventeen eighteen nineteen").split()
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
         "eighty": 80, "ninety": 90}
_WORD = r"(?:" + "|".join(_UNITS + list(_TENS)) + r"|hundred|thousand|million)"
# 'three hundred pounds', 'fifty pence'
_WORDS = re.compile(r"\b(?P<w>" + _WORD + r"(?:(?:[\s-]+(?:and[\s-]+)?)" + _WORD + r")*)"
                    r"\s+(?P<u>pounds?|pence)\b", re.I)


class Amount(NamedTuple):
    start: int
    end: int
    text: str
    pence: Decimal      # the value, in pence
    digits: str         # the figure as written, without thousands separators ("" for words)
    figure: str = ""    # the figure as written ("12,262")


def _dec(n: str) -> Optional[Decimal]:
    try:
        return Decimal(n.replace(",", ""))
    except InvalidOperation:
        return None


def _words_value(w: str) -> Optional[Decimal]:
    total, cur, seen = 0, 0, False
    for tok in re.split(r"[\s-]+", w.lower()):
        if tok in ("", "and"):
            continue
        if tok in _UNITS:
            cur += _UNITS.index(tok)
        elif tok in _TENS:
            cur += _TENS[tok]
        elif tok == "hundred":
            cur = (cur or 1) * 100
        elif tok in ("thousand", "million"):
            total += (cur or 1) * (1000 if tok == "thousand" else 10**6)
            cur = 0
        else:
            continue
        seen = True
    return Decimal(total + cur) if seen else None


def find_amounts(text: str) -> list[Amount]:
    """Every money amount in text, in order; where two readings overlap the
    first found wins ('£5 pounds' is one amount)."""
    text = text or ""
    found: list[Amount] = []
    taken: list[tuple[int, int]] = []

    def add(m, pence, figure):
        s, e = m.span()
        if pence is None or any(s < te and ts < e for ts, te in taken):
            return
        taken.append((s, e))
        found.append(Amount(s, e, m.group(0), pence, figure.replace(",", ""), figure))

    for rx in (_SIGN, _POUNDS):
        for m in rx.finditer(text):
            v = _dec(m.group("n"))
            if v is not None:
                v = v * _MULT.get((m.group("s") or "").lower(), 1) * 100
            add(m, v, m.group("n"))
    for m in _PENCE.finditer(text):
        add(m, _dec(m.group("n")), m.group("n"))
    for m in _WORDS.finditer(text):
        v = _words_value(m.group("w"))
        if v is not None and not m.group("u").lower().startswith("pence"):
            v = v * 100
        add(m, v, "")
    return sorted(found, key=lambda a: a.start)


# A decimal point as old and EU-derived texts write it, between two digits.
_ODD_POINT = re.compile(r"(?<=\d)[·∙:\-‐–](?=\d)")
# A thousands separator: ',' or a space (also no-break and thin) before three
# digits that are not followed by a fourth.
_THOUSANDS = re.compile(r"(?<=\d)[,   ](?=\d{3}(?!\d))")


def _flat(text: str) -> str:
    """text with every odd decimal point made '.', and thousands separators
    dropped: the form a figure's digits are looked for in."""
    t = (text or "").replace("&pound;", "£").replace("&#163;", "£")
    return _THOUSANDS.sub("", _ODD_POINT.sub(".", t))


def _forms(pence: Decimal) -> set[str]:
    """The digit strings a value in pence is written as, in pounds: '151' and
    '151.00'; '2.9' and '2.90'."""
    pounds = pence / 100
    out = {f"{pounds:.2f}"}
    if pounds == pounds.to_integral_value():
        out.add(str(int(pounds)))
    else:
        out.add(format(pounds.normalize(), "f"))
    return out


class AmountIndex:
    """What a source and the research question hold, for amounts."""

    def __init__(self, raw, query: str = ""):
        from .summary_citations import source_text
        # A separator is dropped only before exactly three digits, so a figure
        # in a table whose cells run together keeps its comma
        # ("100235.0012,26290211.50" still holds "12,262" as written).
        self.hay = [_flat(source_text(raw)), _flat(query or "")]
        self.values = set()
        for h in self.hay:
            self.values |= {a.pence for a in find_amounts(h)}

    def held(self, a: Amount) -> bool:
        if a.pence in self.values:
            return True
        # A step from a stated amount: one penny either side ('£473.99' for
        # "less than £474.00"), a pound either side of a whole-pound amount.
        steps = (1, 100) if a.pence % 100 == 0 else (1,)
        if any(a.pence + d * st in self.values for st in steps for d in (-1, 1)):
            return True
        if not a.digits:
            words = re.sub(r"\s+", " ", a.text.lower())
            return any(words in h.lower() for h in self.hay)
        forms = _forms(a.pence) | {a.digits, a.figure}
        return any(f in h for f in forms for h in self.hay)


def unsourced_amounts(summary: str, raw, query: str = "") -> list[Amount]:
    """Every amount in summary that neither raw nor the question holds.
    [] on any error (fail-soft: nothing is removed)."""
    try:
        amounts = find_amounts(summary)
        if not amounts:
            return []
        index = AmountIndex(raw, query)
        return [a for a in amounts if not index.held(a)]
    except Exception:
        return []
