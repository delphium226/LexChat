"""P4.3's grader: `replay_report rail`, the careful-reader test on the Sources rail.

Synthetic run files only. Pins the reader's routes, its three batch 11 C fixes
(a citation or id running on into a longer one, a regnal-year id, a case's
parties followed by another judgment's citation), the turn classes, the
unvouched (fall-back) detector, the bar and its exit code, `--exclude` and
`--drops`.
"""
import json
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import replay_report as rr  # noqa: E402

LEG = "https://www.legislation.gov.uk/"
CASE = "https://caselaw.nationalarchives.gov.uk/"


def _leg(lid, title=None, excerpt=""):
    s = {"kind": "SI", "title": title or lid, "url": LEG + "id/" + lid, "cite": lid}
    if excerpt:
        s["excerpt"] = excerpt
    return s


def _case(title, ncn, path):
    return {"kind": "Case", "title": title, "sub": ncn, "cite": ncn, "url": CASE + path}


def _turn(answer, sources, reports=("A report.",), mode="conversational", fallback=0,
          status="ok", halted=None):
    dgs = [{"step": None, "report": r, "tools": [], "halted": None, "lost": None, "error": None}
           for r in reports]
    if halted is not None:
        dgs[halted]["halted"] = {"limit": 20}
    return {"turn": 1, "status": status, "answer": answer, "chat_mode": mode,
            "timing": {"source_filter_fallback": fallback},
            "audit": {"chat_mode": mode, "sources": sources, "delegations": dgs}}


def _read(s, body):
    return rr.rail_reader(s, *rr._rail_text_index(body))


# --- the reader's routes -----------------------------------------------------------

def test_reader_routes():
    assert _read(_leg("ssi/1901/3"), f"See [reg 2]({LEG}ssi/1901/3/regulation/2).") == "url"
    assert _read(_leg("ssi/1901/3", "The Widget Order 1901"), "the Widget Order 1901 applies") == "title"
    assert _read(_leg("ssi/1901/3"), "made as SSI 1901/3") == "si-number"
    assert _read(_leg("eur/1901/3"), "Regulation (EC) No 3/1901") == "eu-number"
    assert _read(_leg("ssi/1901/3"), "the record for ssi/1901/3 shows") == "id-text"
    assert _read(_leg("ssi/1901/3"), "nothing on point") == ""


def test_reader_old_si_with_a_malformed_url():
    s = {"kind": "Statute", "title": "Widget Order", "url": LEG + "id/1901 No. 3 (S. 1)",
         "cite": "1901 No. 3 (S. 1)"}
    assert _read(s, "made as S.I. 1901/3") == "si-number"
    assert _read(s, "made as 1901 No. 3") == "si-number"
    assert _read(s, "made as 1901 No. 4") == ""


def test_reader_title_as_the_head_of_a_longer_title_is_not_a_reference():
    s = _leg("asp/1901/3", "Widget (Scotland) Act 1901")
    s["kind"] = "Act"
    assert _read(s, "the Widget (Scotland) Act 1901 (Commencement No. 1) Order 1902") == ""
    assert _read(s, "under the Widget (Scotland) Act 1901, the duty") == "title"


# --- the three fixes -----------------------------------------------------------------

def test_a_neutral_citation_running_on_is_not_a_reference():
    s = _case("Widget Co v Example Ltd", "[1901] UKSC 1", "uksc/1901/1")
    assert _read(s, "In Gadget v Other [1901] UKSC 12 it was held") == ""
    assert _read(s, "In [1901] UKSC 1 it was held") == "ncn"
    assert _read(s, "In [1901] UKSC 12, and later in [1901] UKSC 1, it was held") == "ncn"


def test_a_bare_id_running_on_is_not_a_reference():
    assert _read(_leg("ssi/1901/3"), "the record for ssi/1901/31 shows") == ""


def test_a_regnal_year_id_is_read_with_all_four_segments():
    s = {"kind": "Act", "title": "Widget Act 1901", "url": LEG + "id/ukpga/Edw7/1/3",
         "cite": "ukpga/Edw7/1/3"}
    assert rr._rail_src_lid(s) == "ukpga/edw7/1/3"
    assert _read(s, f"See [s 1]({LEG}ukpga/Edw7/1/4/section/1).") == ""
    assert _read(s, f"See [s 1]({LEG}ukpga/Edw7/1/3/section/1).") == "url"
    # An ordinary id is unchanged.
    assert rr._rail_src_lid(_leg("ssi/1901/3")) == "ssi/1901/3"


def test_a_case_named_with_another_judgments_citation_is_not_a_reference():
    first = _case("Widget Co v Example Ltd", "[1901] EWHC 5 (Ch)", "ewhc/ch/1901/5")
    assert _read(first, "Widget Co v Example Ltd & Anor [1902] EWCA Civ 9 held it") == ""
    assert _read(first, f"[Widget Co v Example Ltd]({CASE}ewca/civ/1902/9) held it") == ""
    assert _read(first, "Widget Co v Example Ltd held it") == "title"
    assert _read(first, "Widget Co v Example Ltd. Gadget v Other [1902] EWCA Civ 9") == "title"
    assert _read(first, "Widget Co v Example Ltd; Gadget v Other [1902] EWCA Civ 9") == "title"
    assert _read(first, "Widget Co v Example Ltd " + "x" * 100 + " [1902] EWCA Civ 9") == "title"
    # A later occurrence without the other citation still names it.
    assert _read(first, "Widget Co v Example Ltd [1902] EWCA Civ 9 reversed Widget Co v "
                        "Example Ltd at first instance") == "title"


def test_a_case_with_no_own_citation_is_named_by_its_parties():
    s = _case("Widget Co v Example Ltd", "", "")
    s["url"] = ""
    assert _read(s, "Widget Co v Example Ltd [1902] EWCA Civ 9") == "title"


def test_the_same_judgment_after_the_parties_is_a_reference():
    first = _case("Widget Co v Example Ltd", "[1901] EWHC 5 (Ch)", "ewhc/ch/1901/5")
    first["cite"] = first["sub"] = "Widget"     # too short to match, and no ncn of its own
    assert _read(first, f"[Widget Co v Example Ltd]({CASE}ewhc/ch/1901/5) held it") == "url"
    first["cite"] = first["sub"] = "[1901] EWHC 5 (Ch)"
    assert _read(first, f"Widget Co v Example Ltd ({CASE}ewhc/ch/1901/5) held it") in ("url", "title")


# --- turn classes and the unvouched detector ---------------------------------------

def test_turn_classes():
    assert rr.rail_turn(_turn("", []))["cls"] == "unanswered"
    assert rr.rail_turn(_turn("x", [], status="needs_clarification"))["cls"] == "unanswered"
    t = _turn("x", [])
    t["audit"]["delegations"] = []
    assert rr.rail_turn(t)["cls"] == "no_delegation"
    assert rr.rail_turn(_turn("x", []))["cls"] == "report"
    assert rr.rail_turn(_turn("x", [], reports=("a", "b"), halted=1))["cls"] == "report_mixed"
    assert rr.rail_turn(_turn("x", [], reports=("a",), halted=0))["cls"] == "no_report"
    assert rr.rail_turn(_turn("x", [], reports=("",)))["cls"] == "no_report"


def test_unvouched_is_a_source_no_completed_report_references():
    vouched = _leg("ssi/1901/3", "The Widget Order 1901")
    retrieved = _leg("ssi/1901/4", excerpt="text")
    hit = _leg("ssi/1901/5")
    g = rr.rail_turn(_turn("The Widget Order 1901 applies.", [vouched, retrieved, hit],
                           reports=("The Widget Order 1901 applies.",)))
    assert [x["unvouched"] for x in g["sources"]] == [False, False, True]
    assert [bool(x["reader"]) for x in g["sources"]] == [True, False, False]


def test_a_report_scope_block_does_not_vouch_for_a_source():
    hit = _leg("ssi/1901/5")
    report = ("Nothing on point.\n\n[SEARCH SCOPE — what this research step actually did]\n"
              "Searched the legislation index for: ssi/1901/5\n[/SEARCH SCOPE]")
    g = rr.rail_turn(_turn("Nothing on point.", [hit], reports=(report,)))
    assert g["sources"][0]["unvouched"] is True


def test_only_report_turns_carry_unvouched_sources():
    hit = _leg("ssi/1901/5")
    g = rr.rail_turn(_turn("x", [hit], reports=("a", "b"), halted=1))
    assert g["cls"] == "report_mixed" and g["sources"][0]["unvouched"] is False


# --- the subcommand ----------------------------------------------------------------

def _write(tmp, name, turns):
    d = tmp / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "9999_rep1.json").write_text(json.dumps({"session_id": "9999", "turns": turns}),
                                      encoding="utf-8")
    return d


def _clean_turn():
    s = _leg("ssi/1901/3", "The Widget Order 1901")
    return _turn("The Widget Order 1901 applies.", [s], reports=("The Widget Order 1901 applies.",))


def test_rail_meets_the_bar_on_a_clean_directory(tmp_path, capsys):
    d = _write(tmp_path, "clean", [_clean_turn()])
    rc = rr.main(["--dir", str(d), "rail"])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "bar: 0 fall-back turns and each chat mode <= 15% unused: MET" in out


def test_rail_fails_on_a_fall_back_turn(tmp_path, capsys):
    hit = _leg("ssi/1901/1")                                 # no report vouches for it
    named = _leg("ssi/1902/1", "The Gadget Order 1902")
    t = _turn("The Gadget Order 1902 applies.", [named, hit],
              reports=("The Gadget Order 1902 applies.",), fallback=1)
    # 1 of 2 unused would also be over the bar: pad the rail with referenced sources,
    # so the fall-back alone fails it (1 of 12 unused).
    pad = [_leg(f"ssi/1903/{i}", f"The Sprocket Order 1903 No {i}") for i in range(1, 11)]
    t["audit"]["sources"] += pad
    t["answer"] += " " + " ".join(f"The Sprocket Order 1903 No {i}." for i in range(1, 11))
    t["audit"]["delegations"][0]["report"] = t["answer"]
    d = _write(tmp_path, "fb", [t])
    rc = rr.main(["--dir", str(d), "rail", "--drops"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "detector only 0, counter only 0" in out and "both 1" in out
    assert "NOT MET" in out
    assert "UNVOUCHED" in out and "ssi/1901/1" in out


def test_rail_fails_when_a_mode_is_over_the_bar(tmp_path, capsys):
    t = _clean_turn()
    excerpted = [_leg(f"ssi/1904/{i}", excerpt="text") for i in range(1, 4)]
    t["audit"]["sources"] += excerpted        # retrieved, never referenced: 3 of 4 unused
    d = _write(tmp_path, "over", [t])
    rc = rr.main(["--dir", str(d), "rail"])
    out = capsys.readouterr().out
    assert rc == 1 and "75.0%)*" in out


def test_rail_bar_is_inclusive_at_fifteen_percent(tmp_path, capsys):
    t = _clean_turn()
    s = t["audit"]["sources"][0]
    refs = [_leg(f"ssi/1905/{i}", f"The Cog Order 1905 No {i}") for i in range(1, 17)]
    t["answer"] += " " + " ".join(f"The Cog Order 1905 No {i}." for i in range(1, 17))
    t["audit"]["delegations"][0]["report"] = t["answer"]
    unused = [_leg(f"ssi/1906/{i}", excerpt="text") for i in range(1, 4)]
    t["audit"]["sources"] = [s] + refs + unused            # 3 of 20 = 15.0%
    d = _write(tmp_path, "edge", [t])
    assert rr.main(["--dir", str(d), "rail"]) == 0, capsys.readouterr().out


def test_rail_all_and_exclude(tmp_path, capsys):
    _write(tmp_path, "keep", [_clean_turn()])
    bad = _clean_turn()
    bad["audit"]["sources"].append(_leg("ssi/1907/1"))   # unvouched
    _write(tmp_path, "baseline", [bad])
    assert rr.main(["--dir", str(tmp_path), "rail", "--all"]) == 1
    capsys.readouterr()
    rc = rr.main(["--dir", str(tmp_path), "rail", "--all", "--exclude", "baseline"])
    out = capsys.readouterr().out
    assert rc == 0 and "1 directory" in out and "excluded: baseline" in out


def test_rail_drops_lists_every_disagreement_both_ways(tmp_path, capsys):
    named_only = _leg("ssi/1901/3", "The Widget Order 1901")          # reader yes, token no
    token_only = {"kind": "SI", "title": "x", "url": "", "cite": "ssi/1901/9",
                  "sub": "Interpretation"}                              # token (sub) yes, reader no
    answer = "The Widget Order 1901 applies. Interpretation is for the court."
    t = _turn(answer, [named_only, token_only], reports=(answer,))
    d = _write(tmp_path, "drops", [t])
    rr.main(["--dir", str(d), "rail", "--drops"])
    out = capsys.readouterr().out
    assert "reader-only 1, token-only 1" in out
    assert "READER-ONLY title" in out and "TOKEN-ONLY" in out


def test_rail_does_not_read_the_code_footer():
    """The lawyer-facing scope line is code, not the answer citing anything."""
    s = _leg("ssi/1901/3")
    answer = ("Nothing on point.\n\n*Search scope: the legislation index was searched for "
              "ssi/1901/3; nothing was found.*")
    g = rr.rail_turn(_turn(answer, [s], reports=("Nothing on point.",)))
    assert g["sources"][0]["reader"] == ""
    g = rr.rail_turn(_turn("Nothing; see ssi/1901/3.", [s], reports=("Nothing on point.",)))
    assert g["sources"][0]["reader"] == "id-text"
