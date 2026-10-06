"""P3.22's live probe, `tools.caselaw_probe.check_order`, on synthetic feeds.

The probe is what tells us the feed still ranks by relevance when asked to:
`order=relevance` is not in the National Archives' published spec, and any
explicit `order` resets the page size to 10 unless `per_page` travels with it.
So it must FAIL when the value is ignored (the list comes back newest first,
as by default), when the page size falls back to 10, and when the matching
set changes (a different `last` link). Fixtures are synthetic ("Widget Co v
Example Ltd", 1901-1902); no network.
"""
from types import SimpleNamespace

from tools import caselaw_probe
from tools.caselaw_probe import RELEVANCE_PARAMS, check_order

_BASE = "https://caselaw.nationalarchives.gov.uk/atom.xml?query=widget"


def _entry(i: int, day: int) -> str:
    return (
        "<entry>"
        f"<title>Widget Co v Example Ltd {i}</title>"
        f'<link rel="alternate" href="https://caselaw.nationalarchives.gov.uk/ewhc/ch/1901/{i}"/>'
        f"<published>1901-{1 + day // 28:02d}-{1 + day % 28:02d}T00:00:00Z</published>"
        f'<tna:identifier slug="ewhc/ch/1901/{i}" type="ukncn">[1901] EWHC {i} (Ch)</tna:identifier>'
        "</entry>"
    )


def _feed(ids_days, last=None) -> SimpleNamespace:
    links = f'<link href="{_BASE}&amp;page=1" rel="first"/>'
    if last is not None:
        links += f'<link href="{_BASE}&amp;page={last}" rel="last"/>'
    body = "".join(_entry(i, d) for i, d in ids_days)
    return SimpleNamespace(text=(
        '<?xml version="1.0" encoding="utf-8"?>'
        '<feed xmlns="http://www.w3.org/2005/Atom" '
        'xmlns:tna="https://caselaw.nationalarchives.gov.uk">'
        f"{links}{body}</feed>"))


# Newest first: ids 1..60 dated from the most recent day backwards.
_NEWEST = [(i, 300 - i) for i in range(1, 61)]
# A relevance order: not by date (interleaved).
_RELEVANT = [(i, 300 - i) for i in list(range(60, 30, -1)) + list(range(1, 31))]


def _getter(relevance=None, bare=None, default_last=520, relevance_last=520,
            calls=None):
    """A fake GET: answers by which params were sent, records them."""
    def get(url, params=None):
        params = dict(params or {})
        if calls is not None:
            calls.append(params)
        if "order" not in params:
            return _feed(_NEWEST[:50], last=default_last)
        if "per_page" in params:
            return relevance if relevance is not None else _feed(_RELEVANT[:50], last=relevance_last)
        return bare if bare is not None else _feed(_RELEVANT[:10], last=relevance_last and relevance_last * 5)
    return get


def test_passes_when_relevance_reorders_a_full_page_over_the_same_set():
    calls = []
    assert check_order(_getter(calls=calls), query="widget") is True
    # The probe sends exactly the default params, the relevance params, and
    # `order` alone: so it checks the params P3.22 sends, both together.
    assert calls == [{"query": "widget"},
                     {"query": "widget", **RELEVANCE_PARAMS},
                     {"query": "widget", "order": "relevance"}]


def test_relevance_params_pin_both_parameters():
    assert RELEVANCE_PARAMS == {"order": "relevance", "per_page": "50"}


def test_relevance_params_are_the_products_own():
    """P3.22 built: the probe checks the params the product sends, not a copy
    that could drift from them."""
    from src.agent.tools.caselaw import CASE_LAW_ORDER_PARAMS
    assert RELEVANCE_PARAMS is CASE_LAW_ORDER_PARAMS


# --- since P3.22, the count and dates checks send the product's request --------

def test_check_count_reads_the_range_from_the_products_request():
    """The first GET is the product's request (with the order params), so the
    range checked is the one the product reports; the paging GET counts the
    same set at ten a page, in the feed's default order."""
    calls = []

    def get(url, params=None):
        params = dict(params or {})
        calls.append(params)
        if "page" in params:                       # page 520 at ten a page
            return _feed(_NEWEST[:3], last=520)
        return _feed(_RELEVANT[:50], last=520)

    assert caselaw_probe.check_count(get, query="widget") is True
    assert calls == [{"query": "widget", **RELEVANCE_PARAMS},
                     {"query": "widget", "per_page": "10", "page": "520"}]


def _dated_feed(prefix: str, year: int, n: int) -> SimpleNamespace:
    body = "".join(
        "<entry>"
        f"<title>Widget Co v Example Ltd {prefix}{i}</title>"
        f'<link rel="alternate" href="https://caselaw.nationalarchives.gov.uk/ewhc/ch/{year}/{prefix}{i}"/>'
        f"<published>{year}-06-{1 + i:02d}T00:00:00Z</published>"
        "</entry>" for i in range(n))
    return SimpleNamespace(text=(
        '<?xml version="1.0" encoding="utf-8"?>'
        '<feed xmlns="http://www.w3.org/2005/Atom" '
        'xmlns:tna="https://caselaw.nationalarchives.gov.uk">'
        f"{body}</feed>"))


def test_check_dates_sends_the_products_dated_requests():
    """The dated requests carry the product's order params (they are what the
    product sends); the undated comparator stays the feed's default order,
    newest first, which is what makes "none on the first undated page" mean
    the window reached past it."""
    calls = []

    def get(url, params=None):
        params = dict(params or {})
        calls.append(params)
        if "from_date_2" in params or "to_date_2" in params:
            return _dated_feed("w", 1901, 5)
        return _dated_feed("n", 1902, 5)

    assert caselaw_probe.check_dates(get, query="widget", court="ewhc/ch", year=1901) is True
    base = {"query": "widget", "court": "ewhc/ch"}
    assert calls == [
        {**base, "from_date_0": "1", "from_date_1": "1", "from_date_2": "1901",
         "to_date_0": "31", "to_date_1": "12", "to_date_2": "1901", **RELEVANCE_PARAMS},
        base,
        {**base, "to_date_0": "31", "to_date_1": "12", "to_date_2": "1901", **RELEVANCE_PARAMS},
    ]


def test_check_dates_fails_when_the_window_is_ignored():
    """An ignored window returns judgments outside it."""
    def get(url, params=None):
        return _dated_feed("n", 1902, 5)

    assert caselaw_probe.check_dates(get, query="widget", court="ewhc/ch", year=1901) is False


def test_fails_when_the_feed_ignores_the_order():
    # A withdrawn `order=relevance` looks like the default list again.
    ignored = _feed(_NEWEST[:50], last=520)
    assert check_order(_getter(relevance=ignored), query="widget") is False


def test_fails_when_a_different_order_is_still_newest_first():
    # A list that differs but is still sorted by date is not a relevance order.
    by_date_other = _feed(_NEWEST[5:55], last=520)
    assert check_order(_getter(relevance=by_date_other), query="widget") is False


def test_fails_when_the_page_size_falls_back_to_ten():
    # The `last` link counts at ten a page whatever page size is sent, so a
    # page size that falls back to 10 keeps the same link: only the row count shows it.
    trapped = _feed(_RELEVANT[:10], last=520)
    assert check_order(_getter(relevance=trapped), query="widget") is False


def test_fails_when_the_matching_set_changes():
    assert check_order(_getter(relevance_last=400), query="widget") is False


def test_fails_when_the_feed_gives_no_last_link():
    assert check_order(_getter(default_last=None, relevance_last=None), query="widget") is False


def test_the_bare_order_call_is_reported_not_asserted(capsys):
    # The 10-row trap disappearing is not a failure of the product's params.
    no_trap = _feed(_RELEVANT[:50], last=520)
    assert check_order(_getter(bare=no_trap), query="widget") is True
    assert "no 10-row trap" in capsys.readouterr().out


def test_main_runs_the_order_check(monkeypatch):
    seen = []
    monkeypatch.setattr(caselaw_probe, "check_count", lambda get: seen.append("count") or True)
    monkeypatch.setattr(caselaw_probe, "check_dates", lambda get: seen.append("dates") or True)
    monkeypatch.setattr(caselaw_probe, "check_order", lambda get: seen.append("order") or False)
    assert caselaw_probe.main(get=lambda *a, **k: None) == 1
    assert seen == ["count", "dates", "order"]
