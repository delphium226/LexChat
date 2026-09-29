"""P3.3 (B11): the summariser may not add law that is not in the text it summarises.

6338's summaries added an interpretation Act that does not apply, from the
summariser's training, to section-search results that never mention it; the
Worker then reported it as retrieved. The rule sits in the summariser's prompt,
and the local prompt cache (whose rows are that prompt's output, shared across
users) was bumped so rows written before it stop being served. Synthetic text.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agent import summarisation  # noqa: E402
from src.services import local_prompt_cache as lpc  # noqa: E402


def test_the_source_rule_is_in_the_prompt_before_the_text():
    p = summarisation.summarise_prompt("Section 1) A widget is a gadget.", "What is a widget?")
    assert summarisation.SUMMARY_SOURCE_RULE in p
    assert p.index(summarisation.SUMMARY_SOURCE_RULE) < p.index("Section 1) A widget")
    # It forbids adding law, and says to leave out, not to declare absent.
    rule = summarisation.SUMMARY_SOURCE_RULE
    assert "Do not add any legislation, definition or rule of interpretation" in rule
    assert "leave out" in rule and "say" not in rule


def test_the_cache_key_changed_with_the_summariser_prompt():
    assert lpc._CANON_VERSION == "v2"
    # A row keyed under v1 cannot be matched by a v2 lookup.
    import hashlib
    q = "what is a widget"
    v1 = hashlib.sha256(f"v1|{lpc.canonicalise_query(q)}".encode("utf-8")).hexdigest()
    assert lpc._query_hash(q) != v1
