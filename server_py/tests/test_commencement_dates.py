"""FIX_PLAN P3.21 — the commencement DATE, from legislation.gov.uk's Changes to
Legislation record read through LEX's proxy.

P3.5's change record says which instrument commenced which provision and never
when. `agent/tools/commencement_dates.py` reads the subject's affected effects
feed once per change-record call (at most 2 pages, 8 s, fail-soft, memoised
per request), matches each listed commencement made by another instrument to
its feed effect, refuses a date earlier than the commencing instrument's made
date, and adds ``in_force`` / ``qualification`` to the entry and a
``commencement_dates`` status to the result. The wording that said the record
carries no dates is gated on that result in `utils/search_scope.py`.

Every id, title and provision here is synthetic ("Widget (Scotland) Act 1901").
No test reaches the network: `conftest.py` refuses the hop's client by
default, and the tests below serve synthetic pages through `_client`.
"""
import asyncio
import json
import re
from urllib.parse import unquote

import httpx
import pytest

from src.agent.tools import commencement_dates as cd
from src.agent.provider_factory import set_request_provider_config

SUBJECT = "asp/1901/1"
INST_A = "ssi/1901/3"
INST_B = "ssi/1901/4"
LGU = "http://www.legislation.gov.uk/id"


# ---------------------------------------------------------------------------
# synthetic pages
# ---------------------------------------------------------------------------

def _effect(changed="s. 1", inst=INST_A, by="reg. 2", date="1901-10-08",
            qual="wholly in force", effect="coming into force", subject=SUBJECT,
            prospective=False):
    inforce = (f'<ukm:InForce Prospective="true" Qualification="{qual}"/>' if prospective
               else f'<ukm:InForce Applied="true" Date="{date}" Qualification="{qual}"/>'
               if date else "")
    return (
        "<entry><content type=\"text/xml\">"
        f'<ukm:Effect Type="{effect}" AffectedURI="{LGU}/{subject}" '
        f'AffectedProvisions="{changed}" AffectingURI="{LGU}/{inst}" '
        f'AffectingProvisions="{by}" Applied="true" RequiresApplied="true">'
        f"<ukm:InForceDates>{inforce}</ukm:InForceDates></ukm:Effect>"
        "</content></entry>"
    )


def _feed(effects, page=1, total_pages=1, total=None):
    total = len(effects) if total is None else total
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<feed xmlns="http://www.w3.org/2005/Atom" '
        'xmlns:leg="http://www.legislation.gov.uk/namespaces/legislation" '
        'xmlns:ukm="http://www.legislation.gov.uk/namespaces/metadata" '
        'xmlns:openSearch="http://a9.com/-/spec/opensearch/1.1/">'
        f"<openSearch:itemsPerPage>500</openSearch:itemsPerPage>"
        f"<leg:page>{page}</leg:page><leg:totalPages>{total_pages}</leg:totalPages>"
        f"<openSearch:totalResults>{total}</openSearch:totalResults>"
        + "".join(effects) + "</feed>"
    )


def _intro(made="1901-09-01", tag="Made"):
    return (
        '<Legislation xmlns="http://www.legislation.gov.uk/namespaces/legislation" '
        'xmlns:ukm="http://www.legislation.gov.uk/namespaces/metadata"><ukm:Metadata>'
        f'<ukm:SecondaryMetadata><ukm:{tag} Date="{made}"/></ukm:SecondaryMetadata>'
        "</ukm:Metadata></Legislation>"
    )


def _group(inst=INST_A, changes=None, self_=False, effect="coming into force", count=None):
    changes = changes if changes is not None else [{"by": "reg. 2", "changed": ["s. 1"]}]
    n = sum(len(c["changed"]) for c in changes)
    return {"legislation_id": inst, "url": f"https://www.legislation.gov.uk/id/{inst}",
            "self": self_, "type_of_effect": effect, "count": count or n,
            "changes": changes}


def _record(groups, direction="to", subject=SUBJECT):
    return {"legislation_id": subject, "url": "", "direction": direction,
            "relations": sum(g["count"] for g in groups),
            "by_other_legislation": sum(g["count"] for g in groups if not g["self"]),
            "by_this_legislation_itself": sum(g["count"] for g in groups if g["self"]),
            "effects": {}, "provisions_commenced": sum(
                g["count"] for g in groups if g["type_of_effect"] == "coming into force"),
            "commencement_orders_of_amendments": 0, "repeal_or_revocation_relations": 0,
            "related_instruments": len(groups), "related": groups,
            "window_complete": True}


class _Server:
    """Serves the hop's proxy GETs from dicts, and records each path asked."""

    def __init__(self, feed_pages=None, made=None, fail=None, delay=0.0):
        self.feed_pages = feed_pages or {}
        self.made = made or {}
        self.fail = fail or {}
        self.delay = delay
        self.asked = []
        self.urls = []

    async def handler(self, request):
        url = str(request.url)
        self.urls.append(url)
        assert "/legislation/proxy/" in url
        segment = url.split("/legislation/proxy/", 1)[1]
        assert "/" not in segment and "?" not in segment  # one encoded segment
        path = unquote(segment)
        self.asked.append(path)
        if self.delay:
            await asyncio.sleep(self.delay)
        if path in self.fail:
            f = self.fail[path]
            if isinstance(f, Exception):
                raise f
            return httpx.Response(f, text="gateway error")
        if path.startswith("changes/affected/"):
            page = int(path.split("page=")[1]) if "page=" in path else 1
            if page in self.feed_pages:
                return httpx.Response(200, text=self.feed_pages[page])
            return httpx.Response(404, text="no page")
        if path.endswith("/introduction/data.xml"):
            lid = path[: -len("/introduction/data.xml")]
            if lid in self.made:
                return httpx.Response(200, text=self.made[lid])
            return httpx.Response(404, text="none")
        raise AssertionError(path)

    def install(self, monkeypatch):
        monkeypatch.setattr(
            cd, "_client",
            lambda: httpx.AsyncClient(transport=httpx.MockTransport(self.handler)))
        return self


def _hop(record, **kw):
    async def go():
        set_request_provider_config({"_test": True})
        return await cd.add_commencement_dates(record, call_id="t", **kw)
    return asyncio.run(go())


# ---------------------------------------------------------------------------
# parsers
# ---------------------------------------------------------------------------

def test_the_feed_parser_reads_each_effect_with_its_date_and_qualification():
    p = cd.parse_effects_feed(_feed([
        _effect(),
        _effect(changed="s. 2", date=None, prospective=True, qual=""),
    ], total=2))
    assert p["total"] == 2 and p["page"] == 1 and p["total_pages"] == 1
    e = p["effects"][0]
    assert (e["affected"], e["affecting"]) == (SUBJECT, INST_A)
    assert e["affected_provisions"] == "s. 1" and e["affecting_provisions"] == "reg. 2"
    assert e["in_force"] == [{"date": "1901-10-08", "qualification": "wholly in force"}]
    assert p["effects"][1]["in_force"] == [{"date": None, "qualification": ""}]


@pytest.mark.parametrize("page", [
    "<html><body>502 Bad Gateway</body></html>",
    "not xml at all",
    "",
    '<?xml version="1.0"?><!DOCTYPE feed [<!ENTITY x "y">]><feed xmlns="http://www.w3.org/2005/Atom"/>',
])
def test_a_page_that_is_not_a_feed_is_never_read_as_no_effects(page):
    with pytest.raises(ValueError):
        cd.parse_effects_feed(page)


def test_a_feed_date_that_is_not_an_iso_date_is_no_date():
    p = cd.parse_effects_feed(_feed([_effect(date="8 October 1901"), _effect(date="1901-10")]))
    assert [e["in_force"][0]["date"] for e in p["effects"]] == [None, None]
    assert cd.feed_date_index(p["effects"], SUBJECT) == {}


def test_the_made_date_is_read_from_made_or_enactment_date_and_never_guessed():
    assert cd.parse_made_date(_intro("1901-09-01")) == "1901-09-01"
    assert cd.parse_made_date(_intro("1901-06-01", tag="EnactmentDate")) == "1901-06-01"
    assert cd.parse_made_date(_intro("1 September 1901")) is None
    assert cd.parse_made_date(
        '<Legislation xmlns:ukm="http://www.legislation.gov.uk/namespaces/metadata"/>') is None
    with pytest.raises(ValueError):
        cd.parse_made_date("<html>error")


def test_the_proxy_url_carries_the_path_and_query_as_one_encoded_segment():
    url = cd.proxy_url(cd.feed_path(SUBJECT, 2))
    seg = url.split("/legislation/proxy/", 1)[1]
    assert "/" not in seg and "?" not in seg and "&" not in seg
    assert unquote(seg) == f"changes/affected/{SUBJECT}/data.feed?results-count=500&page=2"
    assert unquote(cd.proxy_url(cd.feed_path(SUBJECT, 1)).split("/proxy/", 1)[1]) == (
        f"changes/affected/{SUBJECT}/data.feed?results-count=500")
    assert unquote(cd.proxy_url(cd.introduction_path(INST_A)).split("/proxy/", 1)[1]) == (
        f"{INST_A}/introduction/data.xml")


def test_the_index_keeps_only_dated_commencements_of_the_subject_by_another_instrument():
    effects = cd.parse_effects_feed(_feed([
        _effect(changed="S.  1", by="Reg. 2"),                      # case and spaces
        _effect(changed="s. 2", inst=SUBJECT, by="s. 9"),             # self
        _effect(changed="s. 3", effect="words substituted"),          # not a commencement
        _effect(changed="s. 4", subject="asp/1901/9"),                # another subject
        _effect(changed="s. 5", date=None, prospective=True),         # no date
    ]))["effects"]
    idx = cd.feed_date_index(effects, SUBJECT)
    assert idx == {("s. 1", INST_A, "reg. 2"): {("1901-10-08", "wholly in force")}}


# ---------------------------------------------------------------------------
# apply_dates: the shape agent E reads
# ---------------------------------------------------------------------------

def _ok(effects, total=None):
    return {"status": "ok", "effects": cd.parse_effects_feed(_feed(effects))["effects"],
            "total": total if total is not None else len(effects), "read": len(effects)}


def test_a_dated_relation_carries_in_force_and_qualification_and_the_status_counts():
    rec = _record([_group(changes=[{"by": "reg. 2", "changed": ["s. 1", "s. 2"]}])])
    out = cd.apply_dates(rec, _ok([_effect(), _effect(changed="s. 2")]),
                         {INST_A: "1901-09-01"})
    assert out["related"][0]["changes"] == [
        {"by": "reg. 2", "changed": ["s. 1", "s. 2"], "in_force": "1901-10-08",
         "qualification": "wholly in force"}]
    assert out["commencement_dates"] == {
        "status": "retrieved", "source": cd.DATE_SOURCE,
        "relations": 2, "dated": 2, "refused": 0}
    # the input is not modified
    assert "in_force" not in rec["related"][0]["changes"][0]
    assert "commencement_dates" not in rec


def test_an_entry_whose_provisions_take_different_dates_is_split_and_an_unmatched_one_kept():
    rec = _record([_group(changes=[{"by": "reg. 2", "changed": ["s. 1", "s. 2", "s. 3"]}])])
    out = cd.apply_dates(rec, _ok([
        _effect(changed="s. 1", date="1901-10-08"),
        _effect(changed="s. 2", date="1901-12-01", qual="for specified purposes"),
    ]), {INST_A: "1901-09-01"})
    assert out["related"][0]["changes"] == [
        {"by": "reg. 2", "changed": ["s. 1"], "in_force": "1901-10-08",
         "qualification": "wholly in force"},
        {"by": "reg. 2", "changed": ["s. 2"], "in_force": "1901-12-01",
         "qualification": "for specified purposes"},
        {"by": "reg. 2", "changed": ["s. 3"]},
    ]
    assert out["commencement_dates"]["dated"] == 2
    assert out["commencement_dates"]["relations"] == 3


def test_one_relation_with_two_dated_effects_is_listed_under_both_and_counted_once():
    rec = _record([_group(changes=[{"by": "sch.", "changed": ["s. 1"]}])])
    out = cd.apply_dates(rec, _ok([
        _effect(by="sch.", date="1901-10-08", qual="for specified purposes"),
        _effect(by="sch.", date="1902-01-01", qual="in force in so far as not already in force"),
    ]), {INST_A: "1901-09-01"})
    dates = [(c["in_force"], c["changed"]) for c in out["related"][0]["changes"]]
    assert dates == [("1901-10-08", ["s. 1"]), ("1902-01-01", ["s. 1"])]
    assert out["commencement_dates"]["dated"] == 1


def test_a_date_before_the_made_date_is_refused_and_the_made_date_itself_allowed():
    rec = _record([_group(changes=[{"by": "reg. 2", "changed": ["s. 1", "s. 2"]}])])
    out = cd.apply_dates(rec, _ok([
        _effect(changed="s. 1", date="1901-08-31"),     # a day before it was made
        _effect(changed="s. 2", date="1901-09-01"),     # the day it was made
    ]), {INST_A: "1901-09-01"})
    assert out["related"][0]["changes"] == [
        {"by": "reg. 2", "changed": ["s. 2"], "in_force": "1901-09-01",
         "qualification": "wholly in force"},
        {"by": "reg. 2", "changed": ["s. 1"]},
    ]
    st = out["commencement_dates"]
    assert st["refused"] == 1 and st["dated"] == 1
    assert st["refused_instruments"] == [INST_A]
    # the refused date is not in the result anywhere the model reads
    assert "1901-08-31" not in json.dumps(out)


def test_a_date_whose_made_date_could_not_be_read_is_not_given():
    rec = _record([_group(), _group(inst=INST_B)])
    out = cd.apply_dates(rec, _ok([_effect(), _effect(inst=INST_B)]),
                         {INST_A: "1901-09-01", INST_B: None})
    assert out["related"][0]["changes"][0].get("in_force") == "1901-10-08"
    assert "in_force" not in out["related"][1]["changes"][0]
    assert out["commencement_dates"]["made_date_not_read"] == [INST_B]
    assert out["commencement_dates"]["dated"] == 1


def test_self_commencement_and_commencement_order_groups_are_never_dated():
    rec = _record([
        _group(inst=SUBJECT, self_=True, changes=[{"by": "s. 9", "changed": ["s. 1"]}]),
        _group(inst=INST_B, effect="Commencement Order",
               changes=[{"by": "art. 2", "changed": ["specified amended provision(s)"]}]),
        _group(),
    ])
    out = cd.apply_dates(rec, _ok([
        _effect(inst=SUBJECT, by="s. 9"),
        _effect(inst=INST_B, by="art. 2", changed="specified amended provision(s)",
                effect="Commencement Order"),
        _effect(),
    ]), {INST_A: "1901-09-01", INST_B: "1901-09-01", SUBJECT: "1901-01-01"})
    assert out["related"][0] == rec["related"][0]
    assert out["related"][1] == rec["related"][1]
    assert out["related"][2]["changes"][0]["in_force"] == "1901-10-08"


def test_a_failed_feed_leaves_the_record_as_it_was_and_says_so():
    rec = _record([_group()])
    out = cd.apply_dates(rec, {"status": "failed", "reason": "no_reply"}, {})
    assert out.pop("commencement_dates") == {"status": "not_retrieved", "reason": "no_reply"}
    assert out == rec


def test_a_cut_feed_states_its_window():
    rec = _record([_group()])
    out = cd.apply_dates(rec, {**_ok([_effect()]), "total": 1300, "read": 1000},
                         {INST_A: "1901-09-01"})
    assert out["commencement_dates"]["feed_window"] == {"read": 1000, "total": 1300}


# ---------------------------------------------------------------------------
# the hop
# ---------------------------------------------------------------------------

FEED_PATH = cd.feed_path(SUBJECT, 1)


def test_no_hop_and_no_call_where_there_is_nothing_to_date(monkeypatch):
    srv = _Server().install(monkeypatch)
    for rec in (
        _record([_group(inst=SUBJECT, self_=True)]),                      # self only
        _record([_group(effect="words substituted")]),                     # an amendment
        _record([_group()], direction="by"),                               # "by"
        _record([]),                                                       # empty record
        {"text": "unexpected"},                                            # not our shape
    ):
        out = _hop(dict(rec))
        assert "commencement_dates" not in out
        assert out == rec
    assert srv.asked == []


def test_an_id_that_is_not_a_plain_path_is_never_put_in_a_proxy_path(monkeypatch):
    srv = _Server(feed_pages={1: _feed([_effect()])}, made={INST_A: _intro()}).install(monkeypatch)
    rec = _record([_group()], subject="../asp/1901/1")
    assert _hop(json.loads(json.dumps(rec))) == rec
    rec2 = _record([_group(inst="ssi/1901/3?x=1"), _group()])
    out = _hop(rec2)
    assert [p for p in srv.asked if p.endswith("introduction/data.xml")] == [
        f"{INST_A}/introduction/data.xml"]
    assert "in_force" not in out["related"][0]["changes"][0]
    assert out["related"][1]["changes"][0]["in_force"] == "1901-10-08"


def test_one_feed_read_and_one_made_date_read_per_instrument(monkeypatch):
    srv = _Server(feed_pages={1: _feed([_effect(), _effect(inst=INST_B)])},
                  made={INST_A: _intro(), INST_B: _intro()}).install(monkeypatch)
    out = _hop(_record([_group(), _group(inst=INST_B)]))
    assert sorted(srv.asked) == sorted([
        FEED_PATH, f"{INST_A}/introduction/data.xml", f"{INST_B}/introduction/data.xml"])
    assert out["commencement_dates"]["dated"] == 2


def test_at_most_two_feed_pages_are_read_and_the_window_is_stated(monkeypatch):
    pages = {p: _feed([_effect(changed=f"s. {p}")], page=p, total_pages=3, total=1500)
             for p in (1, 2, 3)}
    srv = _Server(feed_pages=pages, made={INST_A: _intro()}).install(monkeypatch)
    rec = _record([_group(changes=[{"by": "reg. 2", "changed": ["s. 1", "s. 2", "s. 3"]}])])
    out = _hop(rec)
    feeds = [p for p in srv.asked if p.startswith("changes/")]
    assert feeds == [cd.feed_path(SUBJECT, 1), cd.feed_path(SUBJECT, 2)]
    st = out["commencement_dates"]
    assert st["feed_window"] == {"read": 2, "total": 1500}
    assert st["dated"] == 2
    assert out["related"][0]["changes"][-1] == {"by": "reg. 2", "changed": ["s. 3"]}


def test_a_failed_second_page_keeps_the_first(monkeypatch):
    pages = {1: _feed([_effect()], page=1, total_pages=2, total=600)}
    srv = _Server(feed_pages=pages, made={INST_A: _intro()},
                  fail={cd.feed_path(SUBJECT, 2): 502}).install(monkeypatch)
    out = _hop(_record([_group()]))
    assert out["commencement_dates"]["status"] == "retrieved"
    assert out["commencement_dates"]["feed_window"] == {"read": 1, "total": 600}
    assert len([p for p in srv.asked if p.startswith("changes/")]) == 2


@pytest.mark.parametrize("failure,reason", [
    (httpx.ReadTimeout("slow"), "no_reply"),
    (httpx.ConnectError("refused"), "error"),
    (502, "http_502"),
    (429, "http_429"),
])
def test_a_feed_that_cannot_be_read_fails_soft(monkeypatch, failure, reason):
    _Server(fail={FEED_PATH: failure}, made={INST_A: _intro()}).install(monkeypatch)
    rec = _record([_group()])
    out = _hop(json.loads(json.dumps(rec)))
    assert out.pop("commencement_dates") == {"status": "not_retrieved", "reason": reason}
    assert out == rec


def test_a_page_that_is_not_a_feed_fails_soft(monkeypatch):
    _Server(feed_pages={1: "<html>error</html>"}, made={INST_A: _intro()}).install(monkeypatch)
    out = _hop(_record([_group()]))
    assert out["commencement_dates"] == {"status": "not_retrieved", "reason": "unreadable"}


def test_the_decided_bounds_and_the_real_client():
    """The user's bounds (P3.21's row): 2 pages of 500, 8 s, no retry. The
    module's own client factory, not the conftest replacement, carries the 8 s
    on every phase (connect, read, write, pool)."""
    assert (cd.FEED_PER_PAGE, cd.MAX_FEED_PAGES, cd.HOP_TIMEOUT_S) == (500, 2, 8.0)
    client = cd._make_client()
    try:
        assert client.timeout == httpx.Timeout(8.0)
    finally:
        asyncio.run(client.aclose())


def test_the_feed_is_read_once_per_request_and_shared_by_a_batched_round(monkeypatch):
    srv = _Server(feed_pages={1: _feed([_effect()])}, made={INST_A: _intro()},
                  delay=0.05).install(monkeypatch)

    async def go():
        set_request_provider_config({"_test": True})
        a, b = await asyncio.gather(
            cd.add_commencement_dates(_record([_group()]), call_id="a"),
            cd.add_commencement_dates(_record([_group()]), call_id="b"))
        c = await cd.add_commencement_dates(_record([_group()]), call_id="c")
        return a, b, c
    a, b, c = asyncio.run(go())
    assert srv.asked.count(FEED_PATH) == 1
    assert srv.asked.count(f"{INST_A}/introduction/data.xml") == 1
    assert a["commencement_dates"]["dated"] == b["commencement_dates"]["dated"] == 1
    assert c == a


def test_a_new_request_reads_again(monkeypatch):
    srv = _Server(feed_pages={1: _feed([_effect()])}, made={INST_A: _intro()}).install(monkeypatch)
    _hop(_record([_group()]))
    _hop(_record([_group()]))
    assert srv.asked.count(FEED_PATH) == 2


def test_made_dates_are_read_for_at_most_eight_instruments(monkeypatch):
    insts = [f"ssi/1901/{10 + i}" for i in range(10)]
    srv = _Server(feed_pages={1: _feed([_effect(inst=i) for i in insts])},
                  made={i: _intro() for i in insts}).install(monkeypatch)
    out = _hop(_record([_group(inst=i) for i in insts]))
    made_reads = [p for p in srv.asked if p.endswith("/introduction/data.xml")]
    assert len(made_reads) == cd.MAX_MADE_DATE_READS == 8
    st = out["commencement_dates"]
    assert st["dated"] == 8 and st["made_date_not_read"] == insts[8:]


def test_a_made_date_read_once_is_not_read_again_in_the_process(monkeypatch):
    srv = _Server(feed_pages={1: _feed([_effect()])}, made={INST_A: _intro()}).install(monkeypatch)
    _hop(_record([_group()]))
    out = _hop(_record([_group()]))          # a new request: the feed again, no made date
    assert srv.asked.count(FEED_PATH) == 2
    assert srv.asked.count(f"{INST_A}/introduction/data.xml") == 1
    assert out["commencement_dates"]["dated"] == 1
    assert cd._MADE_CACHE == {INST_A: "1901-09-01"}


def test_a_failed_made_date_read_is_not_kept(monkeypatch):
    srv = _Server(feed_pages={1: _feed([_effect()])},
                  fail={f"{INST_A}/introduction/data.xml": httpx.ReadTimeout("slow")}
                  ).install(monkeypatch)
    first = _hop(_record([_group()]))
    assert first["commencement_dates"]["made_date_not_read"] == [INST_A]
    srv.fail = {}
    srv.made = {INST_A: _intro()}
    second = _hop(_record([_group()]))
    assert second["commencement_dates"]["dated"] == 1
    assert srv.asked.count(f"{INST_A}/introduction/data.xml") == 2


def test_the_cap_counts_reads_not_instruments(monkeypatch):
    insts = [f"ssi/1901/{10 + i}" for i in range(10)]
    for i in insts[:4]:
        cd._MADE_CACHE[i] = "1901-09-01"
    srv = _Server(feed_pages={1: _feed([_effect(inst=i) for i in insts])},
                  made={i: _intro() for i in insts}).install(monkeypatch)
    out = _hop(_record([_group(inst=i) for i in insts]))
    assert len([p for p in srv.asked if p.endswith("/introduction/data.xml")]) == 6
    assert out["commencement_dates"]["dated"] == 10
    assert "made_date_not_read" not in out["commencement_dates"]


def test_the_made_date_store_is_bounded(monkeypatch):
    monkeypatch.setattr(cd, "_MADE_CACHE_MAX", 2)
    for i in range(3):
        cd._cache_made(f"ssi/1901/{i}", "1901-09-01")
    assert list(cd._MADE_CACHE) == ["ssi/1901/1", "ssi/1901/2"]
    cd._cache_made("ssi/1901/9", None)
    cd._cache_made("ssi/1901/8", "September 1901")
    assert list(cd._MADE_CACHE) == ["ssi/1901/1", "ssi/1901/2"]


def test_the_audit_records_each_call_by_size_never_by_body(monkeypatch):
    _Server(feed_pages={1: _feed([_effect()])}, made={INST_A: _intro()}).install(monkeypatch)
    events = []

    async def on_chunk(ev):
        events.append(ev)
    _hop(_record([_group()]), on_chunk=on_chunk)
    ends = [e for e in events if e["type"] == "api_call_end"]
    starts = [e for e in events if e["type"] == "api_call_start"]
    assert len(starts) == len(ends) == 2
    assert {e["method"] for e in starts} == {"GET"} and all(e["payload"] is None for e in starts)
    by_id = {e["id"]: e for e in ends}
    feed = by_id["t-lgu-feed-p1"]["response"]
    assert feed["effects"] == 1 and feed["total"] == 1 and feed["bytes"] > 0
    made = by_id[f"t-made-{INST_A.replace('/', '-')}"]["response"]
    assert made["made"] == "1901-09-01"
    assert "<" not in json.dumps([e["response"] for e in ends])


def test_the_hop_never_raises(monkeypatch):
    _Server(feed_pages={1: _feed([_effect()])}, made={INST_A: _intro()}).install(monkeypatch)

    def boom(*a, **k):
        raise RuntimeError("unexpected")
    monkeypatch.setattr(cd, "apply_dates", boom)
    rec = _record([_group()])
    out = _hop(json.loads(json.dumps(rec)))
    assert out.pop("commencement_dates") == {"status": "not_retrieved", "reason": "error"}
    assert out == rec


# ---------------------------------------------------------------------------
# the executor branch
# ---------------------------------------------------------------------------

def _rows():
    def row(changed_prov, affecting, affecting_prov):
        return {"changed_legislation": SUBJECT, "changed_url": f"{LGU}/{SUBJECT}",
                "changed_provision": changed_prov, "affecting_legislation": affecting,
                "affecting_url": f"{LGU}/{affecting}", "affecting_provision": affecting_prov,
                "type_of_effect": "coming into force"}
    return [row("s. 1", INST_A, "reg. 2"), row("s. 2", SUBJECT, "s. 9")]


def test_the_executor_adds_the_dates_to_a_change_record(monkeypatch):
    from src.agent.tools import executor
    srv = _Server(feed_pages={1: _feed([_effect()])}, made={INST_A: _intro()}).install(monkeypatch)

    async def fake(client, method, url, *, name="", **kwargs):
        return httpx.Response(200, json=_rows(), request=httpx.Request(method, url))
    monkeypatch.setattr(executor, "_request_with_retry", fake)
    events = []

    async def go():
        set_request_provider_config({"_test": True})
        return await executor.execute_worker_tool(
            "get_legislation_changes", {"legislation_id": SUBJECT},
            on_chunk=lambda ev: events.append(ev))
    out = json.loads(asyncio.run(go()))
    groups = {g["legislation_id"]: g for g in out["related"]}
    assert groups[INST_A]["changes"] == [{"by": "reg. 2", "changed": ["s. 1"],
                                          "in_force": "1901-10-08",
                                          "qualification": "wholly in force"}]
    assert groups[SUBJECT]["changes"] == [{"by": "s. 9", "changed": ["s. 2"]}]
    assert out["commencement_dates"]["status"] == "retrieved"
    assert FEED_PATH in srv.asked
    ids = [e["id"] for e in events if e["type"] == "api_call_start"]
    assert any(i.endswith("-lgu-feed-p1") for i in ids)


def test_the_executor_does_not_hop_for_direction_by(monkeypatch):
    from src.agent.tools import executor
    srv = _Server().install(monkeypatch)

    async def fake(client, method, url, *, name="", **kwargs):
        return httpx.Response(200, json=_rows(), request=httpx.Request(method, url))
    monkeypatch.setattr(executor, "_request_with_retry", fake)
    out = json.loads(asyncio.run(executor.execute_worker_tool(
        "get_legislation_changes", {"legislation_id": INST_A, "direction": "by"})))
    assert "commencement_dates" not in out and srv.asked == []


# ---------------------------------------------------------------------------
# the wording, gated on the hop (utils/search_scope.py)
# ---------------------------------------------------------------------------

from src.utils import search_scope as ss  # noqa: E402

OLD_CLOSING = (
    " Two things this record does NOT contain, whatever it shows: there is no "
    "DATE on any relation, so you cannot say when a provision came into force "
    "from this — retrieve the commencing instrument for that; and there is no "
    "made-under relation, so it says nothing about any instrument's enabling "
    "power.]"
)


def _with_repeal(rec):
    rec = json.loads(json.dumps(rec))
    rec["related"].append(_group(inst="ssi/1901/7", effect="repealed",
                                 changes=[{"by": "reg. 5", "changed": ["s. 8"]}]))
    rec["repeal_or_revocation_relations"] = 1
    rec["relations"] += 1
    rec["by_other_legislation"] += 1
    return rec


def _undated():
    return _with_repeal(_record([_group(changes=[{"by": "reg. 2", "changed": ["s. 1", "s. 2"]}])]))


def _dated(made=None):
    """A record the hop dated: ss. 1 and 2 by INST_A, plus a repeal by another
    instrument (undated, as every repeal is)."""
    return cd.apply_dates(_undated(), _ok([_effect(), _effect(changed="s. 2")]),
                          made or {INST_A: "1901-09-01"})


def _not_retrieved(reason="no_reply"):
    return cd.apply_dates(_undated(), {"status": "failed", "reason": reason}, {})


def _found_nothing():
    """The hop ran and dated nothing: the feed holds no matching effect."""
    return cd.apply_dates(_undated(), _ok([_effect(changed="s. 99")]), {INST_A: "1901-09-01"})


def _mixed():
    """Dated, refused, unchecked and a cut feed, in one record."""
    rec = _with_repeal(_record([
        _group(changes=[{"by": "reg. 2", "changed": ["s. 1"]}]),
        _group(inst=INST_B),
        _group(inst="ssi/1901/5", changes=[{"by": "reg. 3", "changed": ["s. 3"]}]),
    ]))
    feed = {**_ok([_effect(), _effect(inst=INST_B),
                   _effect(inst="ssi/1901/5", by="reg. 3", changed="s. 3", date="1901-01-02")]),
            "total": 1400, "read": 1000}
    return cd.apply_dates(rec, feed, {INST_A: "1901-09-01", INST_B: None,
                                      "ssi/1901/5": "1901-03-01"})


def _note(rec):
    return ss.amendment_search_note({"legislation_id": SUBJECT}, json.dumps(rec))


def test_the_worker_note_is_unchanged_where_no_hop_ran_or_it_dated_nothing():
    for rec in (_undated(), _found_nothing(), _dated(made={INST_A: "1901-11-01"})):
        note = _note(rec)
        assert note.endswith(OLD_CLOSING), note[-400:]
        assert "added by code" not in note and "could not this time" not in note
        assert "The record gives no date for them either." in note


def test_the_worker_note_says_where_a_date_came_from_and_what_it_is_not():
    note = _note(_dated())
    assert OLD_CLOSING not in note and "there is no DATE on any relation" not in note
    assert ("The `in_force` date on 2 of the 2 commencement relation(s) made by another "
            "instrument listed here was added by code from legislation.gov.uk's Changes "
            "to Legislation record, read through the LEX API") in note
    assert "never evidence of in-force status today" in note
    assert "Do not give a date for a relation listed without `in_force`." in note
    # the repeal half stays undated, without "either"
    assert "The record gives no date for them." in note
    assert "for them either" not in note
    assert note.endswith("says nothing about any instrument's enabling power.]")


def test_the_worker_note_says_when_the_record_could_not_be_read():
    note = _note(_not_retrieved("no_reply"))
    assert ("and could not this time (the record did not answer within 8 seconds), so no "
            "date is given against any relation here.") in note
    assert note.endswith(OLD_CLOSING)
    assert "(the record answered with an error, HTTP 502)" in _note(_not_retrieved("http_502"))
    assert "(what came back was not a readable record)" in _note(_not_retrieved("unreadable"))
    assert "(the request failed)" in _note(_not_retrieved("error"))


def test_the_worker_note_names_refused_unchecked_and_cut_relations():
    note = _note(_mixed())
    assert ("For relations made by ssi/1901/5 no date is given: the date that record holds "
            "for them is earlier than the day the instrument was made, which is impossible."
            ) in note
    assert ("For relations made by ssi/1901/4 no date is given: the day that instrument was "
            "made could not be read, so the date could not be checked against it.") in note
    assert ("That record was read for the first 1000 of the 1400 changes it lists for "
            "asp/1901/1, so a relation without a date here may be in the part that was not "
            "read.") in note


def test_the_gate_is_an_entry_that_carries_a_date_not_the_count():
    """A status claiming dates with no entry carrying one (a record trimmed
    after the hop, say) changes no wording."""
    rec = _undated()
    rec["commencement_dates"] = {"status": "retrieved", "source": cd.DATE_SOURCE,
                                 "relations": 2, "dated": 2, "refused": 0}
    assert _note(rec).endswith(OLD_CLOSING)
    assert ss._relations_limb(_logs(rec)) == ss._relations_limb(_logs(_undated()))


def test_a_long_list_of_instruments_says_how_many_more():
    insts = [f"ssi/1901/{10 + i}" for i in range(8)]
    rec = cd.apply_dates(_record([_group()] + [_group(inst=i) for i in insts]),
                         _ok([_effect()] + [_effect(inst=i) for i in insts]),
                         {INST_A: "1901-09-01"})
    note = _note(rec)
    assert ("For relations made by ssi/1901/10, ssi/1901/11, ssi/1901/12, ssi/1901/13, "
            "ssi/1901/14, ssi/1901/15 and 2 more no date is given") in note


def _logs(*recs):
    log = []
    for r in recs:
        ss.record_relations(log, "get_legislation_changes", {"legislation_id": SUBJECT},
                            json.dumps(r))
        ss.record_currency(log, "get_legislation_changes", {"legislation_id": SUBJECT},
                           json.dumps(r))
    return log


def test_the_recorders_carry_the_dated_count():
    rel = [e for e in _logs(_dated()) if e["tool"] == "change_record"][0]
    cur = [e for e in _logs(_dated()) if e["tool"] == "currency"][0]
    assert rel["dated"] == 2 and cur["dated"] == 2
    for rec in (_undated(), _not_retrieved(), _found_nothing()):
        assert all(e["dated"] == 0 for e in _logs(rec))


def test_the_manager_limb_permits_a_retrieved_date_and_no_other():
    old = ss._relations_limb(_logs(_undated()))
    assert old.endswith(" The change record carries no dates and no made-under relation: do "
                        "not state a commencement date, or an enabling power, from it.")
    for rec in (_not_retrieved(), _found_nothing()):
        assert ss._relations_limb(_logs(rec)) == old
    new = ss._relations_limb(_logs(_dated()))
    assert "carries no dates and no made-under relation: do not state" not in new
    assert ("For the record of asp/1901/1, code added the date legislation.gov.uk's Changes "
            "to Legislation record gives for each commencement made by another instrument"
            ) in new
    assert "never as evidence of in-force status today" in new
    assert new.endswith("Do not state any other commencement date, or an enabling power, "
                        "from the change record.")


def test_the_commencement_line_gives_the_date_wording_only_where_dated():
    full_old = ss._commencement_lines(_logs(_undated()))
    assert "Neither carries a date." in full_old
    full_new = ss._commencement_lines(_logs(_dated()))
    assert "Neither carries a date." not in full_new
    assert ("with the date legislation.gov.uk's Changes to Legislation record gives for it "
            "where the report gives one: the day that instrument brought it into force, with "
            "its qualification, never its status today") in full_new
    assert "citing this record, without a date." in full_new
    cut, cut_old = _dated(), _undated()
    cut["related"][0]["changes_not_listed"] = 3
    cut_old["related"][0]["changes_not_listed"] = 3
    assert "brought it into force" in ss._commencement_lines(_logs(cut))
    assert "brought it into force" not in ss._commencement_lines(_logs(cut_old))
    # one instrument consulted twice in a step, once dated: the date wording
    assert "brought it into force" in ss._commencement_lines(_logs(_not_retrieved(), _dated()))


def test_the_currency_limb_drops_again_only_where_dated():
    assert "again without a date." in ss._currency_limb(_logs(_undated()))
    new = ss._currency_limb(_logs(_dated()))
    assert "again without a date" not in new and "is supported, without a date." in new


def test_the_lawyer_footer_clauses_say_where_a_date_came_from():
    rel_old = ss._relations_footer_clause(_logs(_undated()))
    cur_old = ss._currency_footer_clause(_logs(_undated()))
    assert "those records carry no dates, so any date given above was read from" in rel_old
    assert "nothing above has been checked against a commencement date" in cur_old
    for rec in (_not_retrieved(), _found_nothing()):
        assert ss._relations_footer_clause(_logs(rec)) == rel_old
        assert ss._currency_footer_clause(_logs(rec)) == cur_old
    rel_new = ss._relations_footer_clause(_logs(_dated()))
    assert ("those records carry no dates of their own, so a commencement date given above "
            "for a provision commenced by another instrument is the date legislation.gov.uk's "
            "Changes to Legislation record gives for that commencement, read through the LEX "
            "API, with its qualification.") in rel_new
    assert "not whether it has been amended or repealed since" in rel_new
    cur_new = ss._currency_footer_clause(_logs(_dated()))
    assert cur_new == (
        " Whether legislation is in force is not something this index reports; what was "
        "checked is the recorded changes for asp/1901/1, which name the instruments involved "
        "provision by provision, and, for the commencements of asp/1901/1 made by another "
        "instrument, the date legislation.gov.uk's Changes to Legislation record gives for "
        "each. Neither is a check of whether a provision has since been amended or repealed.")


# ---------------------------------------------------------------------------
# every new sentence against every detector that reads answers
# ---------------------------------------------------------------------------

def _new_texts():
    """Every variant of every NEW sentence, as the model or the lawyer would
    meet it. The last is the currency footer clause. (The two sites where a
    word was only dropped, "either" and "again", are screened by
    `test_the_dropped_words_add_no_detector_hit` instead: the sentences around
    them are P2.5's and trip detectors by design.)"""
    texts = []
    for rec in (_dated(), _mixed()):
        note = _note(rec)
        texts.append(note[note.index(" The relations themselves carry no date."):])
    for reason in ("no_reply", "http_502", "unreadable", "error"):
        note = _note(_not_retrieved(reason))
        texts.append(note[note.index(" Code tried to read"):note.index(" Two things this record")])
    cut = _dated()
    cut["related"][0]["changes_not_listed"] = 3
    limb = ss._relations_limb(_logs(_dated()))
    texts += [
        limb[limb.index(" The change record's relations carry no dates of their own"):],
        ss._commencement_lines(_logs(_dated())),
        ss._commencement_lines(_logs(cut)),
        ss._relations_footer_clause(_logs(_dated())),
        ss._currency_footer_clause(_logs(_dated())),
    ]
    assert all(texts)
    return texts


def test_the_dropped_words_add_no_detector_hit():
    """`_relation_currency_limb`'s "either" and `_currency_limb`'s "again" are
    dropped where the hop dated something; every detector reads the dated
    text no worse than the undated one."""
    rr = _detectors()
    rx_type = type(rr.NEG_ASSERTED)
    pats = {k: v for k, v in vars(rr).items() if isinstance(v, rx_type)}
    old_r, new_r = ss._relation_currency_limb(_undated()), ss._relation_currency_limb(_dated())
    assert old_r.replace(" for them either.", " for them.") == new_r
    old_c, new_c = ss._currency_limb(_logs(_undated())), ss._currency_limb(_logs(_dated()))
    rep = re.compile(r" Repeal or revocation relations were retrieved for [^.]*\.")
    assert rep.search(old_c).group(0).replace("again without", "without") == rep.search(
        new_c).group(0)
    # outside the commencement lines (screened above), nothing else moved
    lines = re.compile(r" Commencement, from the change records.*?commenced\.", re.S)
    assert lines.sub("", old_c).replace("again without", "without") == lines.sub("", new_c)
    for old, new in ((old_r, new_r), (rep.search(old_c).group(0), rep.search(new_c).group(0))):
        for name, rx in pats.items():
            assert len(rx.findall(new)) <= len(rx.findall(old)), name
        assert ([rr.negcurrency_claim(s)[0] for s in rr._sentences(new)]
                == [rr.negcurrency_claim(s)[0] for s in rr._sentences(old)])
        assert ([rr._currency_asserted(s) for s in rr._sentences(new)]
                == [rr._currency_asserted(s) for s in rr._sentences(old)])


def _detectors():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools import replay_report as rr
    return rr


def test_no_new_sentence_trips_a_detector():
    """Screened the way `test_footer_trips_no_detector` screens P3.24's line:
    each text, and each sentence of it, against every detector that reads
    answers. The opening of P2.5's currency clause is kept on purpose (its one
    "is in force" is an indirect question, and its disclaimer literal), so that
    clause is held to that one match, as the shared test holds it."""
    rr = _detectors()
    texts = _new_texts()
    currency_clause = texts.pop()
    for text in texts:
        assert not rr.NEG_ASSERTED.search(text), text
        assert not rr.NOT_FOUND.search(text), text
        assert rr.derivation_claims(text)[0] == [], text
        assert not rr.IN_FORCE_CLAIM.search(text), text
        assert not rr._CUR_DISCLOSED.search(text), text
        for rx in (rr.NEG_TERMS, rr.NEG_LIMITS, rr.NEG_BLAMED_INDEX, rr.NEG_BLAMED_USER,
                   rr.HALT_LITERAL, rr.HALT_PARAPHRASE, rr.HALT_AS_TIMEOUT, rr.OPENER_VOCAB):
            assert not rx.search(text), (rx.pattern[:40], text)
        assert not rr._names_search_terms(text), text
        assert rr._without_footer(text) == text.strip()
        for s in rr._sentences(text):
            assert not (rr._CMC_CONTEXT.search(s) and rr._CMC_DENIED.search(s)), s
            assert not rr._currency_asserted(s), s
            assert rr.negcurrency_claim(s)[0] is None, s
    # P2.5's currency clause keeps its opening sentence word for word ("Whether
    # legislation is in force is not something this index reports"), which the
    # shared test already holds to one `IN_FORCE_CLAIM` and which trips
    # `NEG_BLAMED_INDEX` in the old clause too. So the new clause is held to
    # the shared test's screen, and to no more hits than the clause it replaces.
    old_clause = ss._currency_footer_clause(_logs(_undated()))
    assert len(rr.IN_FORCE_CLAIM.findall(currency_clause)) == 1
    assert not rr.NEG_ASSERTED.search(currency_clause)
    assert rr.derivation_claims(currency_clause)[0] == []
    assert not rr._CUR_DISCLOSED.search(currency_clause)
    old_v, new_v = _verdicts(rr, old_clause), _verdicts(rr, currency_clause)
    for name, n in new_v["patterns"].items():
        assert n <= old_v["patterns"][name], name
    for k in old_v:
        if k != "patterns":
            assert new_v[k] <= old_v[k], k
    for s in rr._sentences(currency_clause):
        assert not (rr._CMC_CONTEXT.search(s) and rr._CMC_DENIED.search(s)), s
        assert not rr._currency_asserted(s), s
        assert rr.negcurrency_claim(s)[0] is None, s


def _verdicts(rr, text):
    """What every answer-reading detector in `replay_report` says of `text`:
    the public patterns (upper case, not the `LK_` parts of the lookup
    classifier, which is read whole below), and each sentence classifier."""
    rx_type = type(rr.NEG_ASSERTED)
    pats = {k: len(v.findall(text)) for k, v in vars(rr).items()
            if isinstance(v, rx_type) and k.isupper() and not k.startswith("LK_")
            and not k.startswith("_")}
    sents = rr._sentences(text)
    unit = re.compile(r"\b(?:schedules?|annex(?:es)?)\b", re.I)
    return {
        "patterns": pats,
        "derivations": len(rr.derivation_claims(text)[0]),
        "search_terms": rr._names_search_terms(text),
        "negcurrency": sum(rr.negcurrency_claim(s)[0] is not None for s in sents),
        "currency_asserted": sum(rr._currency_asserted(s) for s in sents),
        "commencement_denied": sum(bool(rr._CMC_CONTEXT.search(s) and rr._CMC_DENIED.search(s))
                                   for s in sents),
        "lookup_classes": sum(bool(rr._lk_classify(s)) for s in sents),
        "caselaw_gap": len(rr.caselaw_gap_statements(text)),
        "schedule_clauses": len(rr.sched_unit_clauses(text, unit)),
    }


def test_the_whole_note_trips_no_detector_the_old_note_did_not():
    """P4.18's method, on the whole Worker-facing note: dated (and failed)
    against undated for the same record, every public pattern and every
    sentence classifier, so any verdict the new closing adds shows. (Counting
    every compiled pattern, the parts as well as the detectors, is not a
    measure for a longer closing: the vocabulary screens and the sentence
    splitter count more of anything; `batch9/C/pattern_rises.py` lists them.)"""
    rr = _detectors()
    old = _verdicts(rr, _note(_undated()))
    assert len(old["patterns"]) > 15
    for new_rec in (_dated(), _mixed(), _not_retrieved()):
        new = _verdicts(rr, _note(new_rec))
        for name, n in new["patterns"].items():
            assert n <= old["patterns"][name], name
        for k in old:
            if k != "patterns":
                assert new[k] <= old[k], (k, new[k], old[k])


def test_the_blocks_still_strip_whole():
    """No bracket inside a block: the strippers stop at the first one."""
    rr = _detectors()
    for rec in (_dated(), _mixed(), _not_retrieved()):
        assert ss.strip_scope_blocks("Answer." + _note(rec)) == ("Answer.", 1)
    log = [{"tool": "search_legislation", "query": "q", "legislation_id": "",
            "shown": 5, "matched": 141}] + _logs(_dated())
    block = ss.worker_scope_block(log, {})
    assert "brought it into force" in block
    assert ss.strip_scope_blocks("Report." + block) == ("Report.", 1)
    footer = ss.answer_scope_footer(log, {})
    assert "Changes to Legislation record" in footer
    assert rr._without_footer("Answer." + footer) == "Answer."


# ---------------------------------------------------------------------------
# the shape agent E's grader reads (pinned)
# ---------------------------------------------------------------------------

def test_the_output_shape():
    rec = _dated()
    assert rec["related"][0]["changes"] == [
        {"by": "reg. 2", "changed": ["s. 1", "s. 2"], "in_force": "1901-10-08",
         "qualification": "wholly in force"}]
    assert rec["commencement_dates"] == {
        "status": "retrieved", "source": cd.DATE_SOURCE, "relations": 2, "dated": 2,
        "refused": 0}
    st = _mixed()["commencement_dates"]
    assert set(st) == {"status", "source", "relations", "dated", "refused",
                       "refused_instruments", "made_date_not_read", "feed_window"}
    nr = _not_retrieved()
    assert nr["commencement_dates"] == {"status": "not_retrieved", "reason": "no_reply"}
    assert nr["related"][0]["changes"] == [{"by": "reg. 2", "changed": ["s. 1", "s. 2"]}]
