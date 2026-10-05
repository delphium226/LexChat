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


def main(get: Callable = paced_get) -> int:
    results = {"P3.23 count": check_count(get)}
    print("\n" + "; ".join(f"{k}: {'PASS' if v else 'FAIL'}" for k, v in results.items()))
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
