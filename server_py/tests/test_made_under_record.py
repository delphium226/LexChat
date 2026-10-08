"""P3.31 Step 3: the made-under record as the Worker uses it.

`find_instruments_made_under` answers the reverse made-under question from a
harvest of instrument preambles. These tests pin: where the tool is offered,
the result shape and its cap, the ENABLING POWER block it adds (permits the
listed instruments, never a total), the scope-log entries, the Manager's limb
and the lawyer's footer clause (no detector trip), the forward fallback that
hands over a stored recital, and the snapshot rows. Synthetic data: instrument
ids and titles are invented ("Widget (Scotland) Act 1901", `ssi/1901/3`).
"""

import asyncio
import gzip
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agent.tools.schemas import get_worker_tools  # noqa: E402
from src.services import made_under_store as store  # noqa: E402
from src.utils import made_under as mu  # noqa: E402
from src.utils import search_scope as ss  # noqa: E402

COV = store.coverage({"label": "Scottish statutory instruments made from 1901 to 1905",
                      "harvested_at": "1906-01-01",
                      "not_covered": "UK statutory instruments"}, None, 0)


def _found(n=3):
    rows = [(f"ssi/1901/{i}", f"The Widget Regulations 1901 No. {i}",
             "Widget (Scotland) Act 1901", "asp/1901/1", "power") for i in range(1, n + 1)]
    return store.build_result("Widget (Scotland) Act 1901", "95", "section/95", rows, [], COV)


# --- where it is offered ----------------------------------------------------

def _names(tools):
    return [t["function"]["name"] for t in tools]


@pytest.mark.parametrize("rm,cm", [("legislation_only", None), ("legislation_only", "research"),
                                   ("legislation_and_case_law", None),
                                   ("legislation_only", "conversational")])
def test_offered_to_every_legislation_worker(rm, cm):
    assert mu.MADE_UNDER_TOOL in _names(get_worker_tools(rm, cm))


@pytest.mark.parametrize("rm", ["case_law_only", "parliamentary_records", "westminster_records"])
def test_not_offered_elsewhere(rm):
    assert mu.MADE_UNDER_TOOL not in _names(get_worker_tools(rm))


# --- keys ---------------------------------------------------------------------

def test_provision_key_and_title_normalisation():
    assert mu.provision_key("95") == "section/95"
    assert mu.provision_key("s.95(1)(a)") == "section/95"
    assert mu.provision_key("Section 35A") == "section/35A"
    assert mu.provision_key("schedule/2/paragraph/1") == "schedule/2/paragraph/1"
    assert mu.provision_key("the whole Act") == ""
    assert mu.normalise_title("The Widget (Scotland) Act, 1901") == "widget (scotland) act 1901"
    assert mu.is_legislation_id("asp/1901/1") and mu.is_legislation_id("ukpga/Eliz2/10-11/47")
    assert not mu.is_legislation_id("Widget (Scotland) Act 1901")


# --- result shape -----------------------------------------------------------

def test_found_result_sorted_with_urls_and_count():
    d = _found(3)
    assert d["status"] == "found" and d["count"] == 3
    assert [i["legislation_id"] for i in d["instruments"]] == ["ssi/1901/1", "ssi/1901/2", "ssi/1901/3"]
    assert d["instruments"][0]["url"] == "https://www.legislation.gov.uk/ssi/1901/1"
    assert "roles" not in d["instruments"][0]          # plain power: nothing to say
    assert d["matched_act"] == "Widget (Scotland) Act 1901" and d["act_id"] == "asp/1901/1"


def test_qualified_role_is_kept():
    rows = [("ssi/1901/1", "T", "Widget (Scotland) Act 1901", None, "as applied by")]
    d = store.build_result("Widget (Scotland) Act 1901", "95", "section/95", rows, [], COV)
    assert d["instruments"][0]["roles"] == ["as applied by"]


def test_list_is_capped_and_bounded():
    d = _found(mu.MAX_LISTED + 7)
    assert d["count"] == mu.MAX_LISTED + 7 and len(d["instruments"]) == mu.MAX_LISTED
    # Bounded so it is never summarised away (exempted in run_worker_tool).
    assert len(json.dumps(d)) < 12_000


def test_empty_results_say_what_the_record_holds():
    d = store.build_result("Widget (Scotland) Act 1901", "117", "section/117", [],
                           [("section/144", 18), ("section/76", 10)], COV)
    assert d["status"] == "act_known_section_not_cited"
    assert d["provisions_of_act_cited"] == ["section/144", "section/76"]
    d = store.build_result("Gadget Act 1902", "1", "section/1", [], [], COV)
    assert d["status"] == "act_not_in_record" and d["instruments"] == []


def test_coverage_statement():
    assert COV["statement"].startswith("Scottish statutory instruments made from 1901 to 1905, "
                                       "as harvested from legislation.gov.uk on 1906-01-01.")
    assert "Not covered: UK statutory instruments." in COV["statement"]
    c = store.coverage({"label": "L", "harvested_at": "D"}, "1907-02-02", 4)
    assert "with 4 newer instrument(s) added up to 1907-02-02" in c["statement"]


def test_invalid_query_needs_no_database():
    d = asyncio.run(store.query("", "95"))
    assert d["status"] == "invalid"
    d = asyncio.run(store.query("Widget (Scotland) Act 1901", "the whole Act"))
    assert d["status"] == "invalid"


# --- the block the Worker reads ---------------------------------------------

def test_found_block_permits_the_listed_instruments_and_names_the_edge():
    note = mu.made_under_note(json.dumps(_found(3)))
    assert note.startswith("\n\n[ENABLING POWER — the made-under record")
    assert "You MAY state that each of them was made under" in note
    assert "does NOT establish that no other instrument" in note
    assert "Scottish statutory instruments made from 1901 to 1905" in note
    # One balanced block, so `strip_scope_blocks` removes all of it.
    assert note.count("[") == 1 and note.count("]") == 1
    stripped, _ = ss.strip_scope_blocks("Answer." + note)
    assert stripped.strip() == "Answer."


def test_found_block_says_when_the_list_is_cut():
    note = mu.made_under_note(json.dumps(_found(mu.MAX_LISTED + 2)))
    assert f"Only {mu.MAX_LISTED} of the {mu.MAX_LISTED + 2} are listed here" in note


def test_empty_block_forbids_a_negative_about_the_law():
    d = store.build_result("Gadget Act 1902", "1", "section/1", [], [], COV)
    note = mu.made_under_note(json.dumps(d))
    assert "NOT evidence that nothing was made under the provision" in note
    assert note.count("[") == 1 and note.count("]") == 1


def test_no_block_for_other_tools_or_failures():
    assert mu.made_under_note(json.dumps({"tool": "lookup_legislation"})) == ""
    assert mu.made_under_note(json.dumps({"tool": mu.MADE_UNDER_TOOL, "status": "unavailable"})) == ""
    assert mu.made_under_note("not json") == ""


# --- scope log, limb, footer -------------------------------------------------

def test_record_marks_each_listed_instrument_stated_and_keeps_coverage():
    log = []
    ss.record_made_under(log, json.dumps(_found(3)))
    stated = [e for e in log if e["tool"] == "enabling_power"]
    assert [e["legislation_id"] for e in stated] == ["ssi/1901/1", "ssi/1901/2", "ssi/1901/3"]
    assert all(e["stated"] for e in stated)
    (mu_entry,) = [e for e in log if e["tool"] == ss.MADE_UNDER_ENTRY]
    assert mu_entry["count"] == 3 and mu_entry["coverage"].startswith("Scottish statutory")
    # The Manager is not then told these derivations are unverified.
    assert ss._enabling_limb(log).startswith("Enabling power: retrieved for 3 of 3")
    limb = ss._made_under_limb(log)
    assert "3 instrument(s) whose own preamble names section 95" in limb
    assert "never a total" in limb


def test_unavailable_or_invalid_records_nothing():
    log = []
    ss.record_made_under(log, json.dumps({"tool": mu.MADE_UNDER_TOOL, "status": "unavailable"}))
    ss.record_made_under(log, "garbage")
    assert log == []


def test_footer_clause_trips_no_detector():
    from tools.replay_report import NEG_ASSERTED, derivation_claims
    log = []
    ss.record_made_under(log, json.dumps(_found(37)))
    for clause in (ss._made_under_footer_clause(log), ss._enabling_footer_clause(log)):
        assert clause
        assert not NEG_ASSERTED.search(clause)
        assert derivation_claims(clause)[0] == []
    assert "and 33 more" in ss._enabling_footer_clause(log)


# --- the forward fallback ----------------------------------------------------

def test_stored_recital_becomes_the_permitting_block(monkeypatch):
    from src.agent import agent_shared

    async def fake(lid):
        return "conferred by section 95 of the Widget (Scotland) Act 1901" if lid == "ssi/1901/3" else None
    monkeypatch.setattr(store, "recital_for", fake)
    log = []
    note = asyncio.run(agent_shared.stored_enabling_note("ssi/1901/3", log))
    assert "DOES state what ssi/1901/3 was made" in note and "made-under record" in note
    assert log == [{"tool": "enabling_power", "legislation_id": "ssi/1901/3", "stated": True,
                    "source": "made_under_record"}]
    # Once per instrument per run, never for primary legislation, never without a recital.
    assert asyncio.run(agent_shared.stored_enabling_note("ssi/1901/3", log)) == ""
    assert asyncio.run(agent_shared.stored_enabling_note("asp/1901/1", [])) == ""
    assert asyncio.run(agent_shared.stored_enabling_note("ssi/1901/4", [])) == ""


def test_executor_routes_to_the_store(monkeypatch):
    from src.agent.tools import executor

    async def fake(act, section):
        return {"tool": mu.MADE_UNDER_TOOL, "status": "found", "act": act, "section": section}
    monkeypatch.setattr(store, "query", fake)
    out = json.loads(asyncio.run(executor.execute_worker_tool(
        mu.MADE_UNDER_TOOL, {"act": "Widget (Scotland) Act 1901", "section": "95"})))
    assert out["status"] == "found" and out["section"] == "95"


# --- snapshot -----------------------------------------------------------------

def test_snapshot_rows(tmp_path):
    recs = [{"id": "ssi/1901/3", "title": "T", "version": "made", "recital": "conferred by ...",
             "powers": [{"act": "Widget (Scotland) Act 1901", "act_id": "asp/1901/1",
                         "provisions": ["section/95", "section/2"], "role": "power"},
                        {"act": None, "provisions": ["section/9"], "role": "power"}]}]
    with gzip.open(tmp_path / store.SNAPSHOT_FILE, "wt", encoding="utf-8") as fh:
        for r in recs:
            fh.write(json.dumps(r) + "\n")
    (tmp_path / store.MANIFEST_FILE).write_text(json.dumps({"version": "v1"}), encoding="utf-8")
    assert store.read_manifest(tmp_path)["version"] == "v1"
    (rec,) = store.read_snapshot(tmp_path)
    inst, powers = store._rows_for(rec)
    assert inst["lid"] == "ssi/1901/3" and inst["source"] == "snapshot"
    # An unresolved anaphor ("act": None) adds no row.
    assert [(p["act_norm"], p["provision"]) for p in powers] == [
        ("widget (scotland) act 1901", "section/95"), ("widget (scotland) act 1901", "section/2")]


def test_refresh_record_from_xml():
    xml = ("<Legislation><dc:title>The Widget Regulations 1901</dc:title><SecondaryPreamble>"
           "<Text>The Scottish Ministers make the following Regulations in exercise of the powers "
           "conferred by section 95 of the Widget (Scotland) Act 1901 and all other powers enabling "
           "them to do so.</Text></SecondaryPreamble></Legislation>")
    rec = store.record_from_xml("ssi/1901/3", xml)
    assert rec["powers"][0]["act"] == "Widget (Scotland) Act 1901"
    assert rec["powers"][0]["provisions"] == ["section/95"]


def test_recital_lookup_touches_no_database_until_the_record_is_loaded(monkeypatch):
    # Every SSI text read and section search calls it; an unloaded server
    # (a unit test, a parliament bot) must not open a connection for it.
    def boom(*a, **k):
        raise AssertionError("database touched")
    import src.database as db
    monkeypatch.setattr(db, "async_session_maker", boom)
    monkeypatch.setitem(store._STATE, "available", False)
    assert asyncio.run(store.recital_for("ssi/1901/3")) is None


def test_p23_grader_counts_the_made_under_record_as_evidence():
    # Without this, every claim the record supports graded as unverified
    # (9 of 9 turns of wave4_p331).
    from tools.replay_report import retrieved_enabling
    listed = json.dumps(_found(2))
    stored = ("..." + "\n\n[ENABLING POWER — the made-under record (the as-made preamble of "
              "ssi/1901/9, harvested from legislation.gov.uk) DOES state what ssi/1901/9 was made under]")
    turn = {"audit": {"delegations": [{"tools": [
        {"name": mu.MADE_UNDER_TOOL, "raw_result": listed, "final_result": listed},
        {"name": "search_legislation_sections", "raw_result": "{}", "final_result": stored},
    ]}]}}
    assert [x[0] for x in retrieved_enabling(turn)] == ["ssi/1901/1", "ssi/1901/2", "ssi/1901/9"]
    # A result that found nothing is no evidence for any instrument.
    empty = json.dumps(store.build_result("Gadget Act 1902", "1", "section/1", [], [], COV))
    assert retrieved_enabling({"audit": {"delegations": [{"tools": [
        {"name": mu.MADE_UNDER_TOOL, "raw_result": empty}]}]}}) == []
