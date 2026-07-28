"""Parse the assistant's `<suggestions>` block out of a manager answer.

The manager prompts instruct the model to end every response with a
`<suggestions>` block listing the next questions the user could ask. The block
is stripped from the answer here and returned separately so the frontend can
render each line as a one-click chip.

Everything about this is fail-soft: a missing, malformed, or empty block simply
yields the original content and no suggestions, so a model that ignores the
instruction produces exactly today's behaviour.
"""

import re

_BLOCK_RE = re.compile(r"<suggestions>(.*?)</suggestions>", re.IGNORECASE | re.DOTALL)
# Unterminated block — the model opened the tag and stopped (or was truncated).
_UNTERMINATED_RE = re.compile(r"<suggestions>.*$", re.IGNORECASE | re.DOTALL)
# Leading markdown bullet or numbering: "- ", "* ", "1. ", "2) ".
_BULLET_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")

MAX_SUGGESTIONS = 4
MAX_SUGGESTION_CHARS = 160


def _clean_line(line: str) -> str:
    """Strip bullets, numbering, surrounding quotes and whitespace from one line."""
    text = _BULLET_RE.sub("", line).strip()
    # Surrounding quotes (straight or curly) — the model often quotes the question.
    while len(text) >= 2 and text[0] in "\"'“‘" and text[-1] in "\"'”’":
        text = text[1:-1].strip()
    return text


def extract_suggestions(content: str) -> tuple[str, list[str]]:
    """Split `content` into (content without the suggestions block, suggestions).

    If several blocks appear, the LAST one wins — a weaker model may echo the tag
    mid-answer, and the trailing block is the one the prompt asked for. Items are
    deduped case-insensitively, capped at MAX_SUGGESTIONS, and any item longer
    than MAX_SUGGESTION_CHARS is dropped (a truncated half-question makes a bad
    button). Never raises.
    """
    if not content:
        return content or "", []

    try:
        matches = list(_BLOCK_RE.finditer(content))
        if matches:
            match = matches[-1]
            inner = match.group(1)
            cleaned = (content[: match.start()] + content[match.end():]).rstrip()
        else:
            match = _UNTERMINATED_RE.search(content)
            if not match:
                return content, []
            inner = match.group(0)[len("<suggestions>"):]
            cleaned = content[: match.start()].rstrip()

        items: list[str] = []
        seen: set[str] = set()
        for raw_line in inner.splitlines():
            line = _clean_line(raw_line)
            if not line or len(line) > MAX_SUGGESTION_CHARS:
                continue
            key = line.lower()
            if key in seen:
                continue
            seen.add(key)
            items.append(line)
            if len(items) >= MAX_SUGGESTIONS:
                break

        if not items:
            # Nothing usable — still strip the markup so no tag reaches the user.
            return cleaned, []
        return cleaned, items
    except Exception:  # pragma: no cover — defensive; this must never break a reply
        return content, []
