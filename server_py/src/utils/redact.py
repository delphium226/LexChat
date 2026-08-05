"""Log-safe renderings of user content and PII.

Users are government lawyers and the logs are files on disk with 14-day
retention (`utils/logger.py`), so several INFO lines were writing the full
text of what a user asked into `agent.log`, and their email address into
`app.log`. That was already the wrong default for research queries. It
becomes a real problem for the drafting bot, where the "query" is a clause
of pre-publication legislative text.

The contract is: INFO gets a redaction — length, a short prefix, and a hash
so two occurrences of the same text can still be correlated across log lines
— and the full text is available only at DEBUG (see `LOG_LEVEL`).

Nothing here raises. A logging helper that can throw turns a log line into an
outage, so every function tolerates whatever it is handed.
"""

import hashlib
import json

# Argument names whose values are structural identifiers, not user prose:
# Act IDs, meeting IDs, dates, jurisdictions, filter enums. These stay in the
# clear because they are what makes a log line useful when reconstructing what
# a request actually retrieved, and none of them can carry a draft clause.
#
# This is an ALLOWLIST on purpose. A tool added later with a new free-text
# parameter is redacted by default: the cost of forgetting to update this set
# is a less informative log line, not a leak. Inverting it — a denylist of
# known-sensitive names — would fail the other way.
SAFE_ARG_KEYS = frozenset({
    "legislation_id",
    "legislation_type",
    "jurisdiction",
    "current_only",
    "year_from",
    "year_to",
    "date_from",
    "date_to",
    "court",
    "debate_ext_id",
    "debate_type",
    "record_type",
    "house",
    "committee",
    "meeting_id",
    "iob_id",
    "slug",
    "name",
    "url",
    "limit",
    "page",
})


def redact_text(s: str, keep: int = 24) -> str:
    """Log-safe: length + short prefix + sha1[:8], never the full body.

    The prefix is what makes a redacted line readable at a glance ("this was
    a commencement question"); the hash is what lets you tell two different
    queries apart, and spot the same one recurring, without storing either.
    """
    if not s:
        return "<empty>"
    try:
        h = hashlib.sha1(s.encode("utf-8", "replace")).hexdigest()[:8]
        head = s[:keep].replace("\n", " ").replace("\r", " ")
        return f"<{len(s)} chars, sha1:{h}, '{head}…'>"
    except Exception:
        return "<unloggable>"


def redact_email(e: str) -> str:
    """`alice.smith@gov.scot` -> `al***@gov.scot`.

    The domain is kept because it is operationally useful (which org, which
    tenant) and is not itself identifying; the local part is what names a
    person.
    """
    if not e or "@" not in e:
        return "<email>"
    try:
        name, _, dom = e.partition("@")
        return f"{name[:2]}***@{dom}"
    except Exception:
        return "<email>"


def redact_args(args: dict) -> dict:
    """Redact the free-text values in a tool-call argument dict.

    Keys in `SAFE_ARG_KEYS` and non-string scalars pass through unchanged;
    everything else is replaced by `redact_text`. The result is a plain dict
    intended to be `json.dumps`-ed straight into a log line.
    """
    if not isinstance(args, dict):
        return {"<args>": redact_text(str(args))}

    out = {}
    for key, value in args.items():
        if key in SAFE_ARG_KEYS or isinstance(value, (int, float, bool)) or value is None:
            out[key] = value
        elif isinstance(value, str):
            out[key] = redact_text(value)
        else:
            # Lists / nested dicts: unknown shape, so redact wholesale rather
            # than walking a structure we cannot classify.
            try:
                out[key] = redact_text(json.dumps(value, default=str))
            except Exception:
                out[key] = "<unloggable>"
    return out
