#!/usr/bin/env python
"""Live checks of the National Archives case-law feed (FIX_PLAN P3.23, P3.9).

    python -m tools.lex_probe --caselaw      # or: python -m tools.caselaw_probe

Each check calls the PRODUCT's own code to build the request or read the
response, so it fails when the product and the feed disagree, not when this
file and the feed do. Every GET is paced at least 1.1 s after the previous one
and printed (URL, status, bytes); the whole run is a handful of GETs, far under
the published limit of 1,000 requests per rolling five minutes per IP.

* **P3.23, the count.** The feed's `<link rel="last">` is counted at ten
  judgments a page whatever page size is asked for, so the product reads the
  total to within ten (`caselaw.case_law_count`). The check pages to that last
  page at ten a page and asserts the true count lies in the product's range. If
  the feed starts counting `last` at the requested page size, the true count
  falls far below the range and this fails.
* **P3.9, the dates.** The params `caselaw.case_law_date_window` builds
  (`from_date_0/1/2`, `to_date_0/1/2`) make the feed apply the window: every
  judgment returned for a one-year window is dated in that year, none of them
  is on the first undated page (so the window reaches past it), and the same
  holds with one end only. `check_dates(known=...)` also asserts a named
  judgment is in the window and not on the first undated page, which is the
  shape of Thomas's reproduction (P3.9's row); its query and citation are
  passed in, not kept here.

The National Archives' published spec (`public_api.yml`) documents neither the
`last` link's page size nor a date parameter; both are what the feed does, so
both are checked here, live.
"""

import time
from typing import Callable

import httpx

ATOM = "https://caselaw.nationalarchives.gov.uk/atom.xml"
GAP_S = 1.1

_last_call = [0.0]


def paced_get(url: str, params=None) -> httpx.Response:
    """The default getter: paced, printed, read-only."""
    wait = _last_call[0] + GAP_S - time.time()
    if wait > 0:
        time.sleep(wait)
    _last_call[0] = time.time()
    r = httpx.get(url, params=params, timeout=30.0)
    print(f"    GET {r.request.url} -> {r.status_code}, {len(r.content)} bytes")
    return r


def check_count(get: Callable = paced_get, query: str = "negligence") -> bool:
    """P3.23: the product's total range holds the true count for `query`."""
    from src.agent.tools.caselaw import (
        _LAST_LINK_PAGE_SIZE,
        _parse_case_law_atom,
        _parse_case_law_last_page,
        case_law_count,
    )

    print(f"\n--- P3.23: the matching total for {query!r} ---")
    first = get(ATOM, params={"query": query})
    shown = len(_parse_case_law_atom(first.text))
    c = case_law_count(first.text, shown)
    last = _parse_case_law_last_page(first.text)
    print(f"  shown {shown}; last page {last}; product says {c['total_min']}-{c['total_max']} "
          f"(total {c['total']}, exact {c['total_exact']})")
    if c["total_exact"]:
        ok = True
        print("  the page is not full, so the total is the shown count: nothing to page")
        return ok
    tail = get(ATOM, params={"query": query, "per_page": str(_LAST_LINK_PAGE_SIZE),
                             "page": str(last)})
    n_last = len(_parse_case_law_atom(tail.text))
    true = (last - 1) * _LAST_LINK_PAGE_SIZE + n_last
    ok = n_last > 0 and c["total_min"] <= true <= c["total_max"]
    print(f"  page {last} at {_LAST_LINK_PAGE_SIZE} a page holds {n_last}: true count {true} "
          f"-> {'PASS' if ok else 'FAIL'} (within the product's range, which is "
          f"{c['total_max'] - c['total_min'] + 1} wide)")
    return ok


def _dated(get, params, window, label):
    from src.agent.tools.caselaw import _parse_case_law_atom

    r = get(ATOM, params=params)
    rows = _parse_case_law_atom(r.text)
    lo, hi = window.get("from") or "0000-00-00", window.get("to") or "9999-99-99"
    outside = [x["date"] for x in rows if not (lo <= x["date"] <= hi)]
    print(f"  {label}: {len(rows)} judgments, {len(outside)} outside {lo}..{hi}")
    return rows, outside


def check_dates(get: Callable = paced_get, query: str = "negligence",
                court: str = "ewca/civ", year: int = 2015, known: str = "") -> bool:
    """P3.9: the product's date params make the feed apply the window.

    Built by `case_law_date_window`, so this checks the product's params, not
    a copy of them. The feed lists newest first, so for an older `year` the
    first undated page holds none of the window's judgments: a window that the
    feed ignored would return that page again (which is what it did before
    P3.9, when `date_from`/`date_to` were sent).
    """
    from src.agent.tools.caselaw import _parse_case_law_atom, case_law_date_window

    print(f"\n--- P3.9: the case-law date filter ({query!r}, {court}, {year}) ---")
    base = {"query": query, "court": court}
    w = case_law_date_window({"date_from": f"{year}-01-01", "date_to": f"{year}-12-31"}, {})
    rows, outside = _dated(get, {**base, **w["params"]}, w["dates"], f"{year} window")
    undated = _parse_case_law_atom(get(ATOM, params=base).text)
    overlap = {x["url"] for x in rows} & {x["url"] for x in undated}
    print(f"  first undated page: {len(undated)} rows, {len(overlap)} of them in the window's results")
    ok = bool(rows) and not outside and not overlap
    if known:
        in_window = any(x.get("ncn") == known for x in rows)
        on_undated = any(x.get("ncn") == known for x in undated)
        print(f"  {known}: in the window {in_window}; on the first undated page {on_undated}")
        ok = ok and in_window and not on_undated
    # One end only, as 25 of the 88 stored dated calls sent (the lawyer's
    # range can also arrive with one end).
    w2 = case_law_date_window({"date_to": f"{year}-12-31"}, {})
    rows2, outside2 = _dated(get, {**base, **w2["params"]}, w2["dates"],
                             f"up to {year}-12-31 only")
    ok = ok and bool(rows2) and not outside2
    print(f"  -> {'PASS' if ok else 'FAIL'}")
    return ok


def main(get: Callable = paced_get) -> int:
    results = {"P3.23 count": check_count(get), "P3.9 dates": check_dates(get)}
    print("\n" + "; ".join(f"{k}: {'PASS' if v else 'FAIL'}" for k, v in results.items()))
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
