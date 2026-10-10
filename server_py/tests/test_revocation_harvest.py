"""FIX_PLAN P3.33: `tools/revocation_harvest.py`, the type-wide harvest and the snapshot attach.

A fake transport stands in for legislation.gov.uk (no network). Pins: a crawl is accepted only
when it is consistent (every page, the stated total, a check read generated after every page,
nothing modified since the EARLIEST page was generated); an unclean scope is crawled again with a
fresh URL; a resumed run reads nothing twice; and `--attach` writes flags only for clean scopes,
so an instrument in an unchecked scope reads "not checked", never "no revocation recorded".
"""
import gzip
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import revocation_harvest as H  # noqa: E402

NOW = datetime(2026, 10, 10, 9, 0, tzinfo=timezone.utc)


def page(effects, page_no, pages, total, generated):
    rows = "".join(
        f'<entry><content type="text/xml"><ukm:Effect EffectId="{e[0]}" Type="{e[1]}" '
        f'AffectedURI="http://www.legislation.gov.uk/id/{e[2]}" AffectedProvisions="{e[3]}" '
        f'AffectingURI="http://www.legislation.gov.uk/id/{e[4]}"'
        + (f' Modified="{e[5]}"' if len(e) > 5 and e[5] else "") +
        '><ukm:InForceDates><ukm:InForce Date="2020-01-01" Qualification="wholly in force"/>'
        f'</ukm:InForceDates></ukm:Effect></content><updated>2020-01-01T00:00:00Z</updated></entry>'
        for e in effects)
    return (
        '<feed xmlns="http://www.w3.org/2005/Atom" xmlns:leg="http://www.legislation.gov.uk/namespaces/legislation" '
        'xmlns:ukm="http://www.legislation.gov.uk/namespaces/metadata" '
        'xmlns:openSearch="http://a9.com/-/spec/opensearch/1.1/">'
        f'<updated>{generated}</updated><leg:page>{page_no}</leg:page><leg:totalPages>{pages}</leg:totalPages>'
        f'<openSearch:totalResults>{total}</openSearch:totalResults>{rows}</feed>').encode()


SSI_P1 = [("k1", "revoked", "ssi/1901/1", "Regulations", "ssi/1903/9", "2020-01-01T00:00:00Z"),
          ("k2", "words omitted", "ssi/1901/2", "reg. 2", "ssi/1903/9", "2019-01-01T00:00:00Z")]
SSI_P2 = [("k3", "revoked", "ssi/1901/3", "reg. 4", "ssi/1904/1")]           # in the tail: no Modified
UK_P1 = [("k4", "revoked", "wsi/1901/5", "Regulations", "wsi/1902/1", "2020-01-01T00:00:00Z")]


class Fake:
    """legislation.gov.uk as a dict of URL -> body; records every URL read."""

    def __init__(self, pages):
        self.pages, self.read = pages, []

    def __call__(self, url):
        self.read.append(url)
        if url in self.pages:
            return 200, self.pages[url]
        return 404, b"<html>not found</html>"


def site(gen="2026-10-10T08:59:00Z", check_gen="2026-10-10T09:30:00Z", total=3, check_effects=None,
         attempt=1):
    return {
        H.page_url("ssi", attempt, 1): page(SSI_P1, 1, 2, total, gen),
        H.page_url("ssi", attempt, 2): page(SSI_P2, 2, 2, total, gen),
        H.check_url("ssi", attempt): page(check_effects or SSI_P1, 1, 2, total, check_gen),
        H.page_url("uksi/1901", attempt, 1): page(UK_P1, 1, 1, 1, gen),
        H.check_url("uksi/1901", attempt): page(UK_P1, 1, 1, 1, check_gen),
    }


def test_urls_are_distinct_per_attempt_and_the_check_is_never_a_page():
    urls = {H.page_url("ssi", a, p) for a in (1, 2, 3) for p in (1, 2)}
    assert len(urls) == 6
    assert not {H.check_url("ssi", a) for a in (1, 2, 3)} & urls
    assert H.scopes_from("ssi,uksi:1987-1989") == ["ssi", "uksi/1987", "uksi/1988", "uksi/1989"]


def test_a_consistent_crawl_is_clean(tmp_path):
    store = H.Store(tmp_path, cap=10, gap=0, transport=Fake(site()))
    rec = H.crawl(store, "ssi", 1, NOW, log=lambda m: None)
    assert rec["clean"] and rec["entries_read"] == 3 and rec["problems"] == []


def test_a_short_read_is_not_clean(tmp_path):
    store = H.Store(tmp_path, cap=10, gap=0, transport=Fake(site(total=4)))
    rec = H.crawl(store, "ssi", 1, NOW, log=lambda m: None)
    assert not rec["clean"] and "read 3 != total 4" in rec["problems"]


def test_an_effect_modified_after_the_earliest_page_was_generated_is_caught(tmp_path):
    # The attempt starts at 09:00, but its pages were generated (cached) at 07:00; an effect
    # modified at 08:00 is inside the window even though it is before the attempt began.
    moved = [("k9", "revoked", "ssi/1901/9", "Regulations", "ssi/1905/1", "2026-10-10T08:00:00Z")] + SSI_P1
    store = H.Store(tmp_path, cap=10, gap=0,
                    transport=Fake(site(gen="2026-10-10T07:00:00Z", check_effects=moved)))
    rec = H.crawl(store, "ssi", 1, NOW, log=lambda m: None)
    assert not rec["clean"] and rec["moved_during_crawl"] == 1
    assert rec["window_from"] == "2026-10-10T07:00:00+00:00" and rec["pages_generated_before_start"] == 2


def test_a_check_older_than_the_pages_does_not_count(tmp_path):
    store = H.Store(tmp_path, cap=10, gap=0, transport=Fake(site(check_gen="2026-10-10T08:00:00Z")))
    rec = H.crawl(store, "ssi", 1, NOW, log=lambda m: None)
    assert not rec["clean"] and "check read not generated after every page" in rec["problems"]


def test_harvest_resumes_without_reading_anything_twice(tmp_path):
    fake = Fake(site())
    H.harvest(tmp_path, ["ssi", "uksi/1901"], cap=50, gap=0, transport=fake)
    first = list(fake.read)
    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert state["ssi"]["clean"] and state["uksi/1901"]["clean"]
    H.harvest(tmp_path, ["ssi", "uksi/1901"], cap=50, gap=0, transport=fake)
    assert fake.read == first                       # nothing read again
    assert len(first) == len(set(first)) == 5


def test_an_unclean_scope_is_crawled_again_with_fresh_urls(tmp_path):
    pages = site(total=4)                            # attempt 1 short
    pages.update(site(attempt=2))                    # attempt 2 consistent
    fake = Fake(pages)
    state = H.harvest(tmp_path, ["ssi"], cap=50, gap=0, transport=fake)
    assert state["ssi"]["clean"] and state["ssi"]["attempt"] == 2


def test_the_cap_stops_the_harvest(tmp_path):
    state = H.harvest(tmp_path, ["ssi"], cap=2, gap=0, transport=Fake(site()))
    assert not state["ssi"]["clean"] and "call cap reached" in state["ssi"]["reason"]


def _snapshot(d):
    d.mkdir()
    recs = [{"id": i, "title": "T", "powers": []} for i in
            ("ssi/1901/1", "ssi/1901/2", "ssi/1901/3", "uksi/1901/5", "uksi/1902/6")]
    with gzip.open(d / "made_under_snapshot.jsonl.gz", "wt", encoding="utf-8") as fh:
        for r in recs:
            fh.write(json.dumps(r) + "\n")
    (d / "manifest.json").write_text(json.dumps({"version": "old", "label": "L"}), encoding="utf-8")


def test_attach_writes_flags_and_check_dates_for_clean_scopes_only(tmp_path):
    harv, snap = tmp_path / "h", tmp_path / "snap"
    H.harvest(harv, ["ssi", "uksi/1901"], cap=50, gap=0, transport=Fake(site()))
    _snapshot(snap)
    out = H.attach(harv, snap, "new")
    recs = {r["id"]: r for r in (json.loads(x) for x in gzip.open(snap / "made_under_snapshot.jsonl.gz",
                                                                    "rt", encoding="utf-8"))}
    assert recs["ssi/1901/1"]["revocation"]["state"] == "wholly"
    assert recs["ssi/1901/3"]["revocation"]["state"] == "partly"       # "reg. 4" is a provision
    assert "revocation" not in recs["ssi/1901/2"]                       # words omitted: not revoked
    assert recs["uksi/1901/5"]["revocation"]["state"] == "wholly"       # filed as wsi/1901/5
    manifest = json.loads((snap / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "new"
    assert set(manifest["revocations"]["checked"]) == {"ssi", "uksi/1901"}   # uksi/1902 never checked
    assert out["flagged"] == {"wholly": 2, "partly": 1}


def test_attach_leaves_an_unclean_scope_unchecked(tmp_path):
    harv, snap = tmp_path / "h", tmp_path / "snap"
    pages = site()
    pages[H.check_url("uksi/1901", 1)] = page(UK_P1, 1, 1, 2, "2026-10-10T09:30:00Z")   # total moved
    for a in (2, 3):
        pages.update({H.page_url("uksi/1901", a, 1): page(UK_P1, 1, 1, 1, "2026-10-10T08:59:00Z"),
                      H.check_url("uksi/1901", a): page(UK_P1, 1, 1, 2, "2026-10-10T09:30:00Z")})
    state = H.harvest(harv, ["ssi", "uksi/1901"], cap=50, gap=0, transport=Fake(pages))
    assert state["ssi"]["clean"] and not state["uksi/1901"]["clean"]
    _snapshot(snap)
    out = H.attach(harv, snap, "new")
    recs = {r["id"]: r for r in (json.loads(x) for x in gzip.open(snap / "made_under_snapshot.jsonl.gz",
                                                                    "rt", encoding="utf-8"))}
    assert "revocation" not in recs["uksi/1901/5"]           # its feed was not clean
    manifest = json.loads((snap / "manifest.json").read_text(encoding="utf-8"))
    assert set(manifest["revocations"]["checked"]) == {"ssi"}
    assert out["scopes_not_clean"] == ["uksi/1901"]


def test_an_interrupted_scope_resumes_without_reading_its_saved_pages(tmp_path):
    fake = Fake(site())
    state = H.harvest(tmp_path, ["ssi"], cap=2, gap=0, transport=fake)      # stops before the check
    assert "call cap reached" in state["ssi"]["reason"]
    read_first = list(fake.read)
    assert read_first == [H.page_url("ssi", 1, 1), H.page_url("ssi", 1, 2)]
    state = H.harvest(tmp_path, ["ssi"], cap=50, gap=0, transport=fake)
    assert state["ssi"]["clean"] and state["ssi"]["attempt"] == 1
    assert fake.read[len(read_first):] == [H.check_url("ssi", 1)]           # only what was missing
