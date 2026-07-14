"""Tests for the per-mode efficiency profiles (WI-5).

Profile selection is driven by settings.research_mode; breach evaluation reads
the selected profile (fan-out denominator + budget rule differ by mode).
"""
from src.config import (
    EFFICIENCY_PROFILES,
    evaluate_efficiency_breaches,
    get_efficiency_profile,
    settings,
)


def test_profile_selection_legislation_default(monkeypatch):
    monkeypatch.setattr(settings, "research_mode", "")
    assert get_efficiency_profile() is EFFICIENCY_PROFILES["legislation"]


def test_profile_selection_parliamentary(monkeypatch):
    monkeypatch.setattr(settings, "research_mode", "parliamentary_records")
    assert get_efficiency_profile() is EFFICIENCY_PROFILES["parliamentary_records"]


def test_profile_selection_unknown_falls_back(monkeypatch):
    monkeypatch.setattr(settings, "research_mode", "something_else")
    assert get_efficiency_profile() is EFFICIENCY_PROFILES["legislation"]


def test_budget_blocked_breach_fires_for_parliamentary(monkeypatch):
    monkeypatch.setattr(settings, "research_mode", "parliamentary_records")
    breaches = evaluate_efficiency_breaches({"search_budget_blocked": 1})
    assert any("search budget exhausted" in b for b in breaches)


def test_budget_blocked_not_evaluated_for_legislation(monkeypatch):
    monkeypatch.setattr(settings, "research_mode", "")
    breaches = evaluate_efficiency_breaches({"search_budget_blocked": 3})
    assert not any("search budget" in b for b in breaches)


def test_fanout_uses_distinct_retrieved_denominator(monkeypatch):
    monkeypatch.setattr(settings, "research_mode", "parliamentary_records")
    # phase2=6, distinct_retrieved=2 → ratio 3.0 ≥ 2.0 and phase2 ≥ 5 → breach.
    # sources_kept is deliberately large; it must NOT be the denominator here.
    breaches = evaluate_efficiency_breaches({
        "phase2_retrieval_calls": 6,
        "distinct_legislation_ids_retrieved": 2,
        "sources_kept": 50,
    })
    assert any("fan-out" in b for b in breaches)


def test_fanout_legislation_uses_sources_kept(monkeypatch):
    monkeypatch.setattr(settings, "research_mode", "")
    # Same numbers, but legislation denominator is sources_kept=50 → ratio ~0.1,
    # no fan-out breach.
    breaches = evaluate_efficiency_breaches({
        "phase2_retrieval_calls": 6,
        "distinct_legislation_ids_retrieved": 2,
        "sources_kept": 50,
    })
    assert not any("fan-out" in b for b in breaches)
