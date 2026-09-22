"""The two user-facing mode controls, and the marker injected when one changes.

FIX_PLAN P4.1 (bucket B7, the research-mode dead-end). Session 6346 — the
pre-pilot's only 1/1 session — is a lawyer changing the research type
mid-conversation, saying so, and being told four times that she had not.
The backend was never stale: `researchMode` is sent on every request and the
system prompt is rebuilt per turn. The model anchors on its OWN earlier
refusal, still in the conversation history, over the current system prompt;
a fresh session with the same question answered first time (6347).

Invariant 2 (code enforcement beats prompt obedience): when the resolved mode
differs from the mode the previous assistant turn ran under, the change is
stated IN THE HISTORY, next to the refusal it supersedes, rather than left to
the system prompt the model has already shown it will not re-read.

There are TWO controls, and the product's own deflections named the wrong
one (bug (b)): the CHAT MODE (Conversational / Research / Deep Research, the
"Mode" menu in the sidebar) and the RESEARCH TYPE (Legislation only / Case
law only / Legislation & case law, under the "Filters" button above the
message box). Their labels below are the UI's, verbatim — `Sidebar.jsx`,
`App.jsx` and `ResearchFiltersModal.jsx` — so a prompt or a marker that
needs a control's name takes it from here and never invents one (bug (c),
"typically located at the top or side of your screen").

Where the previous turn's mode comes from: each assistant message the client
sends back carries `research_mode` and `chat_mode`, the values echoed on the
`result` event and persisted on `messages` (additive columns). A history
without them — an older row, a consulted peer's single message, a harness
that does not stamp — yields no marker, which is exactly today's behaviour.
"""

from __future__ import annotations

import re
from typing import Optional

# Labels as the UI renders them. Keep in step with the client.
RESEARCH_MODE_LABELS = {
    "legislation_only": "Legislation only",
    "case_law_only": "Case law only",
    "legislation_and_case_law": "Legislation & case law",
    "parliamentary_records": "Parliamentary records",
    "westminster_records": "Parliamentary records",
    "drafting": "Drafting",
}
CHAT_MODE_LABELS = {
    "conversational": "Conversational",
    "research": "Research",
    "deep_research": "Deep Research",
}

# How a user changes each control, in the words the prompts use. The research
# type is a FILTER, not a mode, and it takes effect on the next message in the
# same conversation — the model has told users to "start a new chat" and to
# use a "mode selector" that does not exist.
RESEARCH_TYPE_CONTROL = (
    "the Filters button above the message box (Research filters > Research type)"
)
CHAT_MODE_CONTROL = "the Mode menu in the sidebar"

# Per-message keys the client stamps on assistant messages.
RESEARCH_MODE_KEY = "research_mode"
CHAT_MODE_KEY = "chat_mode"

_MARKER_HEAD = "[SYSTEM NOTICE"

# A change to the chat mode that is only Deep Research being one-shot: the
# frontend reverts to conversational when a Deep Research turn completes, so
# a conversational turn after a Deep Research one is not the user switching
# anything, and saying so would be noise on every such turn (20 of 155
# pre-pilot turns).
_SILENT_CHAT_TRANSITIONS = {("deep_research", "conversational")}


def research_mode_label(mode: Optional[str]) -> str:
    return RESEARCH_MODE_LABELS.get(mode or "", mode or "unknown")


def chat_mode_label(mode: Optional[str]) -> str:
    return CHAT_MODE_LABELS.get(mode or "", mode or "unknown")


def previous_modes(messages: list) -> dict:
    """The modes the LAST assistant reply in `messages` ran under.

    `{"research_mode": str | None, "chat_mode": str | None}`; a key is None
    when no assistant message carries it. Only the last assistant message
    counts: the question is what the model most recently said under, not the
    conversation's history of settings.
    """
    out = {RESEARCH_MODE_KEY: None, CHAT_MODE_KEY: None}
    for m in reversed(messages or []):
        if not isinstance(m, dict) or m.get("role") != "assistant":
            continue
        rm = m.get(RESEARCH_MODE_KEY)
        cm = m.get(CHAT_MODE_KEY)
        out[RESEARCH_MODE_KEY] = rm if isinstance(rm, str) and rm else None
        out[CHAT_MODE_KEY] = cm if isinstance(cm, str) and cm else None
        break
    return out


def mode_change_for(messages: list, cfg: dict) -> Optional[dict]:
    """What changed between the previous assistant turn and this request.

    Returns None when nothing is known to have changed — including when the
    history carries no stamped mode at all, which must not be read as a
    change. Otherwise `{"research_mode": {"from", "to"} | None,
    "chat_mode": {"from", "to"} | None}` with at least one of the two set.
    """
    try:
        prev = previous_modes(messages)
        now_rm = (cfg or {}).get("_research_mode")
        now_cm = (cfg or {}).get("_chat_mode")
        rm = None
        if prev[RESEARCH_MODE_KEY] and now_rm and prev[RESEARCH_MODE_KEY] != now_rm:
            rm = {"from": prev[RESEARCH_MODE_KEY], "to": now_rm}
        cm = None
        if (
            prev[CHAT_MODE_KEY]
            and now_cm
            and prev[CHAT_MODE_KEY] != now_cm
            and (prev[CHAT_MODE_KEY], now_cm) not in _SILENT_CHAT_TRANSITIONS
        ):
            cm = {"from": prev[CHAT_MODE_KEY], "to": now_cm}
        if rm is None and cm is None:
            return None
        return {RESEARCH_MODE_KEY: rm, CHAT_MODE_KEY: cm}
    except Exception:
        return None


def _research_type_consequence(to_mode: str) -> str:
    if to_mode == "legislation_and_case_law":
        return "Both legislation and case law can now be searched."
    if to_mode == "case_law_only":
        return "Case law can now be searched; legislation cannot."
    if to_mode == "legislation_only":
        return "Legislation can now be searched; case law cannot."
    return ""


def mode_change_marker(change: dict) -> str:
    """The notice the model reads immediately before the user's message."""
    parts = []
    rm = change.get(RESEARCH_MODE_KEY)
    if rm:
        line = (
            f'Research type is now "{research_mode_label(rm["to"])}" '
            f'(it was "{research_mode_label(rm["from"])}" when you last replied).'
        )
        cons = _research_type_consequence(rm["to"])
        if cons:
            line += " " + cons
        parts.append(line)
    cm = change.get(CHAT_MODE_KEY)
    if cm:
        parts.append(
            f'Mode is now "{chat_mode_label(cm["to"])}" '
            f'(it was "{chat_mode_label(cm["from"])}" when you last replied).'
        )
    body = " ".join(parts)
    return (
        f"{_MARKER_HEAD} - the user changed a setting since your previous reply. "
        f"{body} Anything you said earlier in this conversation about the scope "
        "of your tools, about a setting not having changed, or about needing a "
        "new chat is out of date: do not repeat it, do not tell the user the "
        "setting has not changed, and act on the current setting now. If the "
        "user is repeating or referring back to an earlier question, research "
        "that question with the tools you now have.]"
    )


def apply_mode_change_marker(messages: list, cfg: dict) -> tuple[list, Optional[dict]]:
    """Prefix the marker onto the LAST user message when a mode changed.

    Returns `(messages, change)`: the same list object and None when nothing
    changed, otherwise a new list whose final user message carries the marker
    ahead of the user's own text. In-band on the user turn rather than a
    mid-history system message, so it survives every provider's role rules
    (the Phase-2 nudge pattern). The user's stored message is untouched — this
    is the provider payload only. Never raises.
    """
    try:
        change = mode_change_for(messages, cfg)
        if not change:
            return messages, None
        idx = None
        for i in range(len(messages) - 1, -1, -1):
            m = messages[i]
            if isinstance(m, dict) and m.get("role") == "user":
                idx = i
                break
        if idx is None:
            return messages, None
        out = list(messages)
        original = out[idx].get("content") or ""
        if isinstance(original, str) and original.startswith(_MARKER_HEAD):
            return messages, change  # already applied
        marked = {**out[idx], "content": f"{mode_change_marker(change)}\n\n{original}"}
        out[idx] = marked
        return out, change
    except Exception:
        return messages, None


# Suggestion chips only send text (`SuggestedQuestions.jsx` -> `handleSend`),
# so a chip offering to change a mode or filter is a button that cannot do
# what it says: 6407's lawyer clicked one and was told "I cannot change the
# mode for you". Any such line is dropped from the chips by code (Thomas's
# review, action 9); the prompts say so too, but a model that offers one
# anyway must not get it rendered.
MODE_SWITCH_CHIP = re.compile(
    r"\b(?:switch|change|enable|turn on|select|set|toggle|use|move|go)\b[^.?!]{0,60}?"
    r"\b(?:mode|research type|filters?|setting)s?\b"
    r"|\b(?:research|conversational|deep research) mode\b",
    re.IGNORECASE,
)


def is_mode_switch_offer(text: str) -> bool:
    return bool(text) and bool(MODE_SWITCH_CHIP.search(text))
