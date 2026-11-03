"""FIX_PLAN P4.28: an index record whose `legislation_id` is a placeholder.

LEX's index holds OCR'd records whose id is "[UNCLEAR: ...]" and whose uri is
built on the same text, so it links nowhere. Before P4.28 such an id reached
the sources rail (14 stored rail entries), the Manager's scope block (the one
stored report carrying one), the section-search block the Worker reads and,
in principle, the section-scope footer a legal professional reads.

What this file pins:

1. the test itself, and that `utils.definitions` still exports it;
2. no rail source from a placeholder id, from any extraction branch, and the
   rest of the rail exactly as before;
3. the NEXT STEP nudge keeps the row (LEX takes the id as its key) and marks it;
4. no scope block, limb or footer names a placeholder id, and each says how
   many instruments it could not name;
5. byte identity without a placeholder, against outputs captured at 558184b
   (`fixtures/p428_golden.json`);
6. end to end through `run_worker_tool`.

Mutation checks (each guard broken in turn, a test here fails) are recorded
in `evidence/seam/s52/p428/mutation_p428.txt`.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agent import agent_shared  # noqa: E402
from src.agent.agent_shared import (  # noqa: E402
    _extract_listed_instruments,
    _extract_sources_inner,
    phase2_nudge,
    run_worker_tool,
)
from src.agent.provider_factory import set_request_provider_config  # noqa: E402
from src.agent.tools.lex import extract_legislation_ids_from_search  # noqa: E402
from src.utils import definitions as D  # noqa: E402
from src.utils import placeholder_ids as PI  # noqa: E402
from src.utils import search_scope as SS  # noqa: E402

GOLDEN = json.loads(
    (Path(__file__).parent / "fixtures" / "p428_golden.json").read_text(encoding="utf-8"))

PH = "[UNCLEAR: possible reference ukpga/23-24-Vict/159]"
PH2 = "[UNCLEAR: S.R. & O. (Northern Ireland) 1932 No. 105]"
LEX = "http://www.legislation.gov.uk/id/"

R1 = {"legislation_id": "ssi/2013/85", "title": "The Example (Scotland) Regulations 2013",
      "url": LEX + "ssi/2013/85", "text_version": "revised", "year": 2013,
      "extent": ["Scotland"]}
R2 = {"legislation_id": "ukpga/1950/28", "title": "Shops Act 1950 (repealed)",
      "url": LEX + "ukpga/1950/28", "text_version": "final", "year": 1950, "extent": []}
RP = {"legislation_id": PH, "title": "The North British Railway (Stations) Act, 1860",
      "url": LEX + PH, "text_version": "revised", "year": 1900, "extent": []}


def _has_placeholder(text) -> bool:
    return "UNCLEAR" in json.dumps(text) if not isinstance(text, str) else "UNCLEAR" in text


# ---------------------------------------------------------------------------
# 1. The test
# ---------------------------------------------------------------------------

def test_definitions_still_exports_the_same_test():
    assert D.is_placeholder_id is PI.is_placeholder_id
    assert D._PLACEHOLDER_ID is PI._PLACEHOLDER_ID


@pytest.mark.parametrize("lid", [PH, PH2, "ukpga/1855/27 [UNCLEAR: local act reference]",
                                 LEX + PH, "2 & 3 Geo. 5. Ch. xv. (1912) [ukpga/2-3Geo5/chapter15/1912]"])
def test_placeholders(lid):
    assert PI.is_placeholder_id(lid)


@pytest.mark.parametrize("lid", ["ssi/2013/85", "28 & 29 Vict. Cap. clii", "ukpga/1894/152 (Ch. clii.)",
                                 "", None])
def test_references(lid):
    assert not PI.is_placeholder_id(lid)


def test_split_and_phrase():
    assert PI.split_placeholders(["a/1/2", PH, "a/1/2", PH, "", None, PH2, "b/3/4"]) == (
        ["a/1/2", "b/3/4"], [PH, PH2])
    assert PI.unidentified_phrase(1) == "1 instrument with no identifiable reference"
    assert PI.unidentified_phrase(2) == "2 instruments with no identifiable reference"
    assert PI.unidentified_phrase(2, noun=False) == "2 with no identifiable reference"


# ---------------------------------------------------------------------------
# 2. The rail
# ---------------------------------------------------------------------------

_SEC = {"results": [{"title": "Interpretation", "text": "In these Regulations...", "number": "2"}]}


def _rail(search_rows):
    acc = []
    _extract_sources_inner("search_legislation", {}, {"results": search_rows}, acc)
    _extract_sources_inner("search_legislation_sections", {"legislation_id": "ssi/2013/85"}, _SEC, acc)
    return acc


def test_a_search_row_with_a_placeholder_id_is_no_rail_source():
    assert _rail([R1, RP, R2]) == GOLDEN["SOURCES"]


def test_the_rail_without_a_placeholder_is_byte_identical():
    assert _rail([R1, R2]) == GOLDEN["SOURCES"]


@pytest.mark.parametrize("name", ["search_legislation_sections", "get_legislation_text"])
def test_a_retrieval_by_a_placeholder_id_adds_or_enriches_nothing(name):
    data = _SEC if name == "search_legislation_sections" else {"content": "XII. The Height ...",
                                                               "title": "t", "url": LEX + PH}
    acc = []
    _extract_sources_inner(name, {"legislation_id": PH}, data, acc)
    assert acc == []
    # An earlier entry under the same key (only possible pre-P4.28) is not enriched.
    acc = [{"_lid": PH, "cite": PH, "title": "x"}]
    _extract_sources_inner(name, {"legislation_id": PH}, data, acc)
    assert acc == [{"_lid": PH, "cite": PH, "title": "x"}]


def test_a_change_record_never_adds_a_placeholder_instrument():
    acc = []
    data = {"legislation_id": "asp/2002/13", "related": [
        {"legislation_id": PH, "type_of_effect": "repealed", "url": LEX + PH},
        {"legislation_id": "ssi/2004/1", "type_of_effect": "commenced", "url": LEX + "ssi/2004/1"}]}
    _extract_sources_inner("get_legislation_changes", {"legislation_id": "asp/2002/13"}, data, acc)
    assert [s["_lid"] for s in acc] == ["ssi/2004/1"]


def test_a_lookup_of_a_placeholder_id_is_never_listed():
    listed = []
    _extract_listed_instruments("lookup_legislation", {}, json.dumps(
        {"status": "held", "legislation_id": PH, "title": "t", "url": LEX + PH}), listed)
    assert listed == []
    _extract_listed_instruments("lookup_legislation", {}, json.dumps(
        {"status": "held", "legislation_id": "ssi/2013/85", "title": "t", "url": LEX + "ssi/2013/85"}),
        listed)
    assert [s["_lid"] for s in listed] == ["ssi/2013/85"]


# ---------------------------------------------------------------------------
# 3. The nudge
# ---------------------------------------------------------------------------

def _base_nudge(pairs):
    """The inline code in `run_worker_tool` at 558184b, verbatim."""
    id_lines = "\n".join(f'  - legislation_id: "{lid}"  ({title})' for lid, title in pairs[:5])
    return (f"\n\n[NEXT STEP: Call search_legislation_sections with the relevant "
            f"legislation_id(s) below to retrieve the actual legal text before "
            f"composing your answer:\n{id_lines}]")


def test_the_nudge_without_a_placeholder_is_byte_identical():
    pairs = extract_legislation_ids_from_search({"results": [R1, R2]})
    assert phase2_nudge(pairs) == _base_nudge(pairs)
    assert phase2_nudge([]) == ""


def test_the_nudge_keeps_a_placeholder_row_and_marks_it():
    pairs = extract_legislation_ids_from_search({"results": [R1, RP, R2]})
    out = phase2_nudge(pairs)
    lines = out.splitlines()
    base = _base_nudge(pairs).splitlines()
    marked = [i for i, ln in enumerate(lines) if "no identifiable reference" in ln]
    assert len(marked) == 1 and PH in lines[marked[0]]
    assert lines[marked[0]].startswith(base[marked[0]].rstrip("]"))
    assert "cite it by its title only" in lines[marked[0]]
    # every other line exactly as before
    assert [ln for i, ln in enumerate(lines) if i not in marked] == \
        [ln for i, ln in enumerate(base) if i not in marked]


# ---------------------------------------------------------------------------
# 4. Scope blocks, limbs and footers
# ---------------------------------------------------------------------------

def test_the_section_search_block_does_not_repeat_a_placeholder_id():
    out = SS.section_search_note({"legislation_id": PH, "query": "employer"}, {"results": [{"text": "x"}]})
    assert not _has_placeholder(out)
    assert out.endswith(SS._UNIDENTIFIED_SECTION_CLAUSE + "]")
    # otherwise the block a search without an id gets, word for word
    plain = SS.section_search_note({"query": "employer"}, {"results": [{"text": "x"}]})
    assert out == plain[:-1] + SS._UNIDENTIFIED_SECTION_CLAUSE + "]"
    out0 = SS.section_search_note({"legislation_id": PH, "query": "employer"}, {"results": []})
    assert not _has_placeholder(out0)
    assert out0 == SS.section_search_note({"query": "employer"}, {"results": []})


def test_a_title_marker_on_a_placeholder_row_names_the_title():
    rp = {**RP, "title": "Shops (Sunday Trading Restriction) Act, 1936 (repealed)"}
    out = SS.currency_note({"query": "shops"}, {"results": [R1, rp]})
    assert not _has_placeholder(out)
    assert '"Shops (Sunday Trading Restriction) Act, 1936 (repealed)" — title says repealed' in out
    log = []
    SS.record_currency(log, "search_legislation", {"query": "shops"}, {"results": [rp]})
    assert not _has_placeholder(log)
    assert not _has_placeholder(SS._currency_limb(log))


def _log(section_ids, search=True, stops=()):
    log = []
    if search:
        SS.record_search(log, "search_legislation", {"query": "shops"}, {"results": [R1, R2], "total": 40})
        SS.record_currency(log, "search_legislation", {"query": "shops"}, {"results": [R1, R2], "total": 40})
    for lid in section_ids:
        SS.record_search(log, "search_legislation_sections", {"query": "employer", "legislation_id": lid},
                         {"results": [{"text": "x"}]})
    for lid in stops:
        SS.record_section_budget_stop(log, "search_legislation_sections",
                                      {"legislation_id": lid, "query": "q"}, {"section_limit": 3, "id": "r1"})
    return log


_IDS = ["ssi/2013/85", "ukpga/1950/28", "asp/2002/13", "uksi/2003/2682"]


def test_the_manager_block_counts_a_placeholder_and_does_not_name_it():
    out = SS.worker_scope_block(_log(_IDS[:1] + [PH] + _IDS[1:2]))
    assert not _has_placeholder(out)
    assert ("Searched within 3 instrument(s) for specific provisions: ssi/2013/85, "
            "ukpga/1950/28, 1 with no identifiable reference (ranked extracts") in out
    only = SS.worker_scope_block(_log([PH, PH2]))
    assert "Searched within 2 instrument(s) for specific provisions: 2 with no identifiable reference (" in only


def test_the_section_footer_counts_a_placeholder_and_does_not_name_it():
    out = SS.section_scope_footer(_log(_IDS + [PH], search=False))
    assert not _has_placeholder(out)
    assert ("the text of ssi/2013/85, ukpga/1950/28, asp/2002/13, 1 more and 1 instrument "
            "with no identifiable reference in the legislation index was searched") in out
    one = SS.section_scope_footer(_log([PH], search=False))
    assert "the text of 1 instrument with no identifiable reference in the legislation index" in one


def test_the_section_budget_limb_counts_a_placeholder_and_does_not_name_it():
    log = _log(["asp/2002/13"], stops=["asp/2002/13", PH])
    out = SS._section_budget_limb(log)
    assert not _has_placeholder(out)
    assert out.startswith("Searching within asp/2002/13, 1 instrument with no identifiable reference "
                          "was cut short")
    assert "each of those instruments" in out


def test_a_placeholder_never_takes_the_held_provision_list_sentences():
    log = _log([], stops=[PH])
    log[-1].update({"provisions": 12, "units": ["Schedule 1"]})
    assert SS._section_budget_held(log) == {}
    out = SS._section_budget_limb(log)
    assert not _has_placeholder(out) and "UNCLEAR" not in out
    assert not _has_placeholder(SS._section_budget_footer_clause(log))


# ---------------------------------------------------------------------------
# 5. Byte identity without a placeholder (captured at 558184b)
# ---------------------------------------------------------------------------

def test_scope_texts_without_a_placeholder_are_byte_identical():
    args = {"legislation_id": "ssi/2013/85", "query": "employer"}
    assert SS.section_search_note(args, {"results": [{"text": "x"}]}) == GOLDEN["SEC_NOTE"]
    assert SS.section_search_note(args, {"results": []}) == GOLDEN["SEC_NOTE0"]
    assert SS.currency_note({"query": "shops"}, {"results": [R1, R2]}) == GOLDEN["CUR"]
    log = _log(_IDS, stops=["asp/2002/13"])
    assert SS.worker_scope_block(log) == GOLDEN["BLOCK"]
    assert SS.answer_scope_footer(log) == GOLDEN["FOOTER"]
    assert SS.section_scope_footer([e for e in log if e["tool"] != "search_legislation"]) == \
        GOLDEN["SEC_FOOTER"]


# ---------------------------------------------------------------------------
# 6. End to end through run_worker_tool
# ---------------------------------------------------------------------------

@pytest.fixture
def _config():
    set_request_provider_config({"_provider": "openrouter", "_research_mode": "legislation_only",
                                 "model": "test-model"})
    yield
    set_request_provider_config({})


@pytest.fixture
def fake_exec(monkeypatch):
    async def fake(name, args, on_chunk=None, timing_collector=None, worker_call=False,
                   results_bounded=False):
        if name == "search_legislation":
            return json.dumps({"results": [R1, RP], "total": 2})
        return json.dumps({"results": [{"legislation_id": LEX + str(args.get("legislation_id")),
                                        "title": "Heights of Buildings at Edinburgh Station regulated.",
                                        "text": "XII. The Height of any Buildings ...",
                                        "uri": LEX + str(args.get("legislation_id")) + "/section/XII"}]})

    monkeypatch.setattr(agent_shared, "execute_worker_tool", fake)


async def _chunk(*a, **k):
    return None


@pytest.mark.asyncio
async def test_run_worker_tool_end_to_end(_config, fake_exec):
    acc, log = [], []
    out = await run_worker_tool("search_legislation", {"query": "Waverley height"}, "brief", _chunk,
                                "test-model", source_accumulator=acc, search_log=log)
    # The Worker still sees the row, and the nudge offers it, marked.
    assert PH in out
    assert "no identifiable reference: you may search within it" in out
    out2 = await run_worker_tool("search_legislation_sections", {"legislation_id": PH, "query": "height"},
                                 "brief", _chunk, "test-model", source_accumulator=acc, search_log=log)
    assert "XII. The Height" in out2
    assert SS._UNIDENTIFIED_SECTION_CLAUSE in out2
    assert [s["_lid"] for s in acc] == ["ssi/2013/85"]
    block = SS.worker_scope_block(log)
    assert not _has_placeholder(block)
    assert "1 with no identifiable reference" in block
    assert not _has_placeholder(SS.answer_scope_footer(log))
