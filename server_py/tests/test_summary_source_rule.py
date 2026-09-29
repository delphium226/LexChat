"""P3.3 (B11): the summariser may not add law that is not in the text it summarises.

6338's summaries added an interpretation Act that does not apply, from the
summariser's training, to section-search results that never mention it; the
Worker then reported it as retrieved. The rule sits in the summariser's prompt,
and the local prompt cache (whose rows are that prompt's output, shared across
users) was bumped so rows written before it stop being served. Synthetic text.

P3.16 (Session 33) added a second rule, against the summariser's own reading of
the text, and bumped the cache again (v3).
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


def test_the_gloss_rule_is_in_the_prompt_after_the_source_rule_and_before_the_text():
    # P3.16: the source rule stopped added law, not the summariser's own reading
    # of the text ("(including sprockets by definition)").
    p = summarisation.summarise_prompt("Section 1) A widget is a gadget.", "Is a sprocket a widget?")
    rule = summarisation.SUMMARY_GLOSS_RULE
    assert rule in p
    assert p.index(summarisation.SUMMARY_SOURCE_RULE) < p.index(rule) < p.index("Section 1) A widget")
    # Worded as what to leave out, never as what to declare absent: Session 32's
    # "say that it does not" wording multiplied false negatives about sixfold.
    assert "leave that out" in rule
    assert "say that it does not" not in rule and "say so" not in rule
    assert "includes, excludes or leads to" in rule


def test_summary_probe_draws_without_exactly_the_named_rule():
    # The instrument that measured the rule: its "without rule" side must drop
    # that rule and nothing else.
    from tools import summary_probe as sp
    s, sides = sp._prompts("gloss")
    with_p = sides["with rule"]("Section 1) A widget.", "q")
    without_p = sides["without rule"]("Section 1) A widget.", "q")
    assert s.SUMMARY_GLOSS_RULE in with_p and s.SUMMARY_GLOSS_RULE not in without_p
    assert s.SUMMARY_SOURCE_RULE in without_p
    _s, src_sides = sp._prompts("source")
    assert s.SUMMARY_GLOSS_RULE in src_sides["without rule"]("x", "q")


def test_the_cache_key_changed_with_the_summariser_prompt():
    assert lpc._CANON_VERSION == "v3"
    # A row keyed under v1 or v2 (the prompt before the gloss rule) cannot be
    # matched by a v3 lookup.
    import hashlib
    q = "what is a widget"
    for old in ("v1", "v2"):
        stale = hashlib.sha256(f"{old}|{lpc.canonicalise_query(q)}".encode("utf-8")).hexdigest()
        assert lpc._query_hash(q) != stale
