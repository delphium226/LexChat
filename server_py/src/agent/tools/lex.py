"""LEX API result slimming and legislation-search helpers."""

import re
from urllib.parse import urlparse

from ...config import settings


def _slim_search_results(resp_json: dict) -> dict:
    """Strip the search_legislation response down to only the fields the model needs.

    The raw API response includes provenance metadata, timestamps, descriptions,
    and a ranked sections array. Stripping these keeps a typical 5-result
    payload well under the summarisation threshold (~1-2k chars) and gives the
    model a clean, readable result.

    **The ranked sections array is dropped on purpose, and that was measured
    (FIX_PLAN P3.1, 2026-09-18).** Every result carries `sections: [{number,
    provision_type, score}]`, the API's ranking of which provisions matched the
    query. It is real, but it ranks against the SEARCH query, and the Worker
    prompts make that query the Act's title, so it answers "which sections
    match the words of the title", not "which sections answer the question".
    For FOISA the title search ranks ss.70, 76 and 3 and omits s.36; for SSI
    2007/174 it omits Schedule 1, which holds the answer. Over the stored runs
    it held the provision the answer went on to cite 56% (title queries) to 66%
    (topical) of the time, while every provision the P3.1 acceptance sessions
    needed was retrieved by `search_legislation_sections` in one call. Numbers
    are section-level only, and 1,196 entries carry an empty `number` (any
    non-integer id: inserted sections such as 6B, dotted court rules, Parts).
    So it would steer Phase 2 at least as often as it helped. Decided with the
    user at Session 16: not used.

    description is intentionally excluded — it is verbose and redundant once Phase 2
    retrieves actual section text via search_legislation_sections.

    legislation_id is derived from the URI and included explicitly so the model
    can pass it directly to search_legislation_sections.

    **`status` is emitted as `text_version`, and the rename is FIX_PLAN P2.5
    (bucket B4).** The API field records which text version legislation.gov.uk
    holds. Its measured vocabulary over the 15,160 model-visible search rows in
    the replay corpus is `final` (60.3%), `revised` (38.8%) and `stub` (0.9%) —
    three values, not the two the plan recorded — and **not one of them says
    anything about whether the instrument is in force.** Under the key `status`
    the model read it as currency and said so: of the 34 in-force sentences in
    the Wave 1 sweep almost every one reads *"is currently in force (status:
    revised)"* or *"(revised)"*. That is not the model inventing a source; it is
    the model quoting the only field that looked like one.

    So the affordance is removed rather than argued with, which is Invariant 2 —
    P2.2 measured the tell-the-model-to version of this shape at 56%. A model
    that sees `text_version: "revised"` can still say the revised text is held,
    which is true; it cannot read currency out of the key. `extract_sources`
    still reads it into the Sources rail's `meta`, so what a lawyer sees there is
    byte-identical.
    """
    slimmed = []
    for item in resp_json.get("results", []):
        uri = item.get("uri", "")
        legislation_id = urlparse(uri).path.lstrip("/") if uri else ""
        # Some API responses include /id/ in the URI path — strip it so the
        # legislation_id can be passed directly to search_legislation_sections.
        if legislation_id.startswith("id/"):
            legislation_id = legislation_id[3:]
        slimmed.append({
            "legislation_id": legislation_id,
            "title": item.get("title", ""),
            "url": uri,
            # See the note above: the key is deliberately NOT `status`.
            "text_version": item.get("status", ""),
            "year": item.get("year"),
            "extent": item.get("extent", []),
        })
    return {
        "results": slimmed,
        "total": resp_json.get("total", len(slimmed)),
    }


# The complete `extent` vocabulary the LEX API emits, measured over 17,560 result
# rows in the P0.3 baseline (docs/prepilot-fixes/BASELINE.md). Pinned as a fixture
# so that an API vocabulary change breaks `tests/test_jurisdiction_filter.py`
# rather than silently breaking the product, which is exactly how the original
# defect survived a 62-session pre-pilot.
#
#     ['']                                  6668
#     ['United Kingdom']                    3289
#     ['Scotland']                          2765
#     []                                    2662
#     ['England', 'Wales']                   918
#     ['Northern Ireland']                   761
#     ['England', 'Wales', 'Scotland']       484
#     ['England']                             10
#     ['England', 'Wales', 'Northern Ireland'] 2
#     ['Wales']                                1
_TERRITORY_ALIASES = {
    "england": "E",
    "wales": "W",
    "scotland": "S",
    "northern ireland": "NI",
    "united kingdom": "UK",
    "great britain": "GB",
}

# Which territory tokens satisfy each filter value. UK (and GB, where it appears)
# count for their constituent nations: a UK-wide Act applies in Scotland, so a
# lawyer filtering for Scotland must see it. This is the "applies in" reading of
# the control, decided 2026-09-14 — see the note below.
_JURISDICTION_ACCEPTS = {
    "england_and_wales": {"E", "W", "UK", "GB"},
    "scotland": {"S", "UK", "GB"},
    "northern_ireland": {"NI", "UK"},
    "wales": {"W", "UK", "GB"},
    "uk_wide": {"UK"},
}

# Legislation-id prefixes that belong to one devolved jurisdiction whatever the
# `extent` field says. Used ONLY to reject a row whose extent is unknown — an
# explicit extent always wins. This is what lets unknown-extent rows be admitted
# (necessary: 2,009 Scottish SIs carry `['']`) without admitting Northern Irish
# and Welsh instruments alongside them.
_ID_PREFIX_JURISDICTION = {
    "asp": "scotland", "ssi": "scotland",
    "nia": "northern_ireland", "nisr": "northern_ireland",
    "nisro": "northern_ireland", "nisi": "northern_ireland",
    "apni": "northern_ireland",
    "asc": "wales", "anaw": "wales", "wsi": "wales", "mwa": "wales",
}


def _extent_tokens(extent: list) -> set[str]:
    """Normalise an `extent` list to territory tokens.

    Handles the API's real vocabulary (full territory names, one per list entry)
    and the "E+W+S+NI" form the original implementation expected, so a future
    API change back to codes does not reintroduce the defect.
    """
    tokens: set[str] = set()
    for e in extent or []:
        for part in str(e).split("+"):
            part = part.strip()
            if not part:
                continue
            tokens.add(_TERRITORY_ALIASES.get(part.lower(), part.upper()))
    return tokens


def _matches_jurisdiction(
    extent: list, jurisdiction: str, legislation_id: str = ""
) -> bool:
    """Return True if this result should survive the `jurisdiction` filter.

    **This function used to discard almost everything.** It split `extent` on
    "+" and tested single-letter tokens `E`/`W`/`S`/`NI`; the API returns full
    territory names (`['Scotland']`, `['United Kingdom']`, `['']`), so every
    row carrying a real extent failed. It did not fail *closed*, though — the
    old `if not extent: return True` meant rows with a MISSING extent passed,
    so the filter returned a plausible non-empty result set composed entirely of
    unknown-territory items. Measured over the P0.3 baseline: of 1,009 rows that
    survived a jurisdiction filter, every single one had `extent: []`, and a
    `jurisdiction=scotland` search returned the Building Materials and Housing
    Act 1945. That is why 13 pre-pilot sessions ran with it and none reported a
    broken filter, and why the fix is not just "map the vocabulary".

    Three rules, in order:

    1. **A stated extent decides it.** Matched against `_JURISDICTION_ACCEPTS`,
       in which UK-wide counts for each constituent nation — a UK Act applies in
       Scotland, and the assimilated EU regulations a lawyer needs (`eur/…`,
       23% of the `['United Kingdom']` rows) are only reachable this way. This
       is the "law that **applies in** Scotland" reading of the control rather
       than "law **made for** Scotland", decided 2026-09-14: CambeulW's 6406
       needed assimilated EU instruments under a Scotland filter, and under
       Invariant 1 a filter that hides a relevant Act is worse than one that
       shows an irrelevant one, because the lawyer can see the second and not
       the first.

    2. **An unknown extent is included unless the id says otherwise.** `['']`
       and `[]` are 53% of all rows and are not junk: 2,009 Scottish SIs carry
       `['']`, so excluding unknowns would drop 40% of Scottish material and
       swap one trap for another. But an `nisr/`/`wsi/` instrument is not
       Scottish whatever its extent says, so the id prefix rejects those.

    3. **`uk_wide` means UK-wide**, and nothing else — unknown extents are NOT
       admitted there, because "UK-wide only" is an explicit narrowing and a row
       that does not say it is UK-wide does not satisfy it.

    Scored against the 17,560 baseline rows, this drops **0%** of unambiguously
    Scottish rows and admits **0** rows that are clearly not Scottish. The old
    implementation dropped 97.5% of the Scottish ones.
    """
    accepts = _JURISDICTION_ACCEPTS.get(jurisdiction)
    if accepts is None:
        return True  # unknown filter value: never silently narrow

    tokens = _extent_tokens(extent)
    if tokens:
        return bool(tokens & accepts)

    # Extent unknown from here on.
    if jurisdiction == "uk_wide":
        return False

    prefix = (legislation_id or "").split("/")[0].strip().lower()
    owner = _ID_PREFIX_JURISDICTION.get(prefix)
    if owner is None:
        return True          # UK-level or unrecognised: could apply anywhere
    if owner == jurisdiction:
        return True
    # England & Wales and Wales overlap: a Welsh instrument is in scope for an
    # England & Wales search, but an English one is not exclusively Welsh.
    return owner == "wales" and jurisdiction == "england_and_wales"


def _short_legislation_id(value: str) -> str:
    """`http://www.legislation.gov.uk/id/asp/2014/18` -> `asp/2014/18`.

    The two LEX endpoints disagree: `legislation/search` returns the short form
    and `legislation/section/search` returns a full URI under the same key. The
    model has to pass this value back as `legislation_id`, so it is normalised
    to the short form both places.
    """
    if not value:
        return ""
    path = urlparse(value).path.lstrip("/") if "://" in value else value.lstrip("/")
    if path.startswith("id/"):
        path = path[3:]
    return path


def _slim_section_results(resp_json) -> dict:
    """Strip the search_legislation_sections response, keeping the provision URL.

    **P1.4 (bucket B14): this is where provision links come from.** The raw API
    item already carries the canonical, provision-level legislation.gov.uk URL
    in `uri` (`…/asp/2014/18/section/110`) — but the whole response used to be
    passed through untouched, buried in `created_at`, five null `provenance_*`
    fields, and three different spellings of the identifier. The model composed
    its own link instead, and across the pre-pilot 88 of 376 provision-labelled
    links (23.4%) pointed at the Act's contents page or the wrong provision.

    So the fix is not to teach the model to build URLs: it is to hand it the one
    the API already built, under an unambiguous key, and drop the noise it was
    guessing from. `provision_type` and `number` travel alongside so a citation
    can be checked against the link without re-parsing it.

    The response is a **bare JSON list** at the top level, not an object — hence
    the isinstance dance. Anything unexpected is passed through untouched rather
    than dropped: a slimmer must never be the reason a retrieval goes missing.
    """
    items = resp_json if isinstance(resp_json, list) else resp_json.get("results")
    if not isinstance(items, list):
        return resp_json

    slimmed = []
    for item in items:
        if not isinstance(item, dict):
            continue
        slimmed.append({
            "legislation_id": _short_legislation_id(item.get("legislation_id", "")),
            "provision_type": item.get("provision_type", ""),
            "number": item.get("number"),
            "title": item.get("title", ""),
            # The citation URL. Named `url` to match search_legislation, and it
            # is the API's own value — never reconstructed here either.
            "url": item.get("uri") or item.get("id", ""),
            "text": item.get("text", ""),
        })
    return {"results": slimmed, "returned": len(slimmed)}


def extract_legislation_ids_from_search(resp_json: dict) -> list[tuple[str, str]]:
    """Extract (legislation_id, title) pairs from a slimmed search_legislation response."""
    return [
        (item["legislation_id"], item.get("title", ""))
        for item in resp_json.get("results", [])
        if item.get("legislation_id")
    ]

LEX_API_URL = settings.lex_api_url.rstrip("/")

# Legislation-id prefixes for each `legislation_type` filter value.
#
# P1.3 (bucket B5): `eur` was missing from every set, so a `legislation_type`
# filter of any value silently discarded **every assimilated EU instrument** —
# they are present and retrievable (`eur/2009/1069` returns 10 sections) and
# were exactly what CambeulW needed in session 6406. Assimilated regulations and
# decisions are directly-applicable law made outside Parliament, so they sit
# with secondary rather than primary: a lawyer filtering for "primary" means
# Acts, and a lawyer filtering for "secondary" means everything below an Act.
# `eudn`/`eudr` (decisions and directives) are included on the same reasoning.
#
# Northern Irish and Scottish secondary prefixes seen live but previously
# absent are added here too (`nisro`, `nisi`) — the same class of omission.
_TYPE_CODES: dict[str, set[str]] = {
    "primary":   {"ukpga", "ukppa", "ukla", "asp", "nia", "apni", "anaw", "asc", "mwa"},
    "secondary": {"uksi", "ssi", "wsi", "nisr", "nisro", "nisi",
                  "eur", "eudn", "eudr"},
    "draft":     {"ukdsi", "sdsi"},
}


# ---------------------------------------------------------------------------
# P3.5 (bucket B3) — relationship retrieval over /amendment/search
# ---------------------------------------------------------------------------
#
# B3 is the largest bucket and it was assumed to be permanently a disclosure.
# P5.1 found the API publishes an OpenAPI spec listing 13 endpoints of which we
# called 3, and that `/amendment/search` returns **commencement, amendment,
# repeal and revocation** relations — provision-to-provision, with a resolvable
# URL on both sides and a `search_amended` flag carrying the direction. P2.3
# forbade the unverified claim; this retrieves the verifiable one.
#
# **What it refutes.** 6409 asked which sections of the Social Security
# (Amendment) (Scotland) Act 2025 had been commenced by regulation and was told
# "No commencement regulations have been made yet." `asp/2025/2` has eight
# provisions commenced by SSI (seven by `ssi/2025/119`, one by `ssi/2025/377`).
# 6410 got the same sentence about the Care Reform (Scotland) Act 2025;
# `asp/2025/9` has twenty provisions commenced by `ssi/2025/388`. Both are false
# negatives against data that was one endpoint away. Reproduce either with
# `python -m tools.lex_probe --commencement`.
#
# Four properties of the raw feed decide the shape of this function, and three
# of them make a naive pass-through wrong:
#
# 1. **A bare JSON list**, not `{results: []}` — the same shape trap
#    `_slim_section_results` already handles.
# 2. **35% of rows are scheme duplicates.** The same relation is returned twice,
#    once with `http://` URLs and once with `https://`, and the API's own `id`
#    embeds the scheme so they are not equal by id. Measured over 6,738 rows on
#    eight instruments in both directions: 4,363 distinct, 2,375 duplicates
#    (35%), concentrated in the Scottish material this corpus is about —
#    `asp/2025/2` returns 71 rows for 36 relations, `asp/2018/9` 956 for 484,
#    `asp/2014/18` 607 for 309, while `ukpga/1998/46`, `asp/2000/1` and
#    `ukpga/1981/67` have none at all. A tool that counts rows therefore reports
#    roughly double, and "15 provisions commenced" would be 8.
#    ~~31% over 6,266 rows~~ — that first figure was itself computed from a
#    `size=2000` sample, which truncated `ukpga/2010/15` at 2,000 of its 2,472
#    rows. The measurement had the exact defect the escalation below exists to
#    avoid, and putting it behind `lex_probe --commencement` is what caught it.
# 3. **`type_of_effect` is sometimes null** (19% over P5.1's 1,358-row sample;
#    6% on `ukpga/1998/46`). These are **labelled, not dropped**: the row still
#    records that an instrument changed a provision, which is a real retrieval,
#    and dropping it would make the tool the reason a relation went missing. The
#    label is the literal "not stated" and the tool block forbids describing
#    such a row as a commencement, amendment or repeal.
# 4. **Commencement rows are frequently self-referential** — 28 of `asp/2025/2`'s
#    36 relations are the Act commencing its own sections under s. 27, not a
#    regulation. `self` and the two top-level counts separate them, because
#    "commenced by regulation" and "commenced by the Act itself" are different
#    answers to the question 6409 actually asked.
#
# There is **no date** on a relation row (confirmed at P5.1 and again here), so
# this tool can establish that s. 9 was commenced by `ssi/2025/119` and never
# that it came into force on a given day. That bears on P2.5, and the tool block
# says it in terms.

# **Provision labels, not provision URLs, and that is a decision rather than an
# omission.** Emitting a URL beside every listed provision costs 45-70 KB on the
# large Acts (measured: `ukpga/2004/33` 26 KB -> 70 KB, `asp/2018/9` 18 -> 48)
# against 3.7 KB on `asp/2025/2`, which is a lot of context for a citation form
# a commencement answer does not use — a lawyer writes "ss. 2, 9, 17 and 20-23",
# not eight hyperlinks. What the result does carry is the subject Act's own URL
# and each related instrument's, which is what a commencement answer cites.
#
# The consequence is bounded and already handled: a model that does link a
# provision of the subject Act is covered by P1.6 either way — the section
# search almost always run in the same turn harvests those URLs (6409 turn 5 and
# 6410 turn 1 both called it on the Act in question), and where it was not,
# `enforce_provision_links` demotes the link to the Act and marks it, which is
# the designed behaviour and not a defect.

# What one group of relations may list before it starts counting instead. Taken
# from the measured shape rather than picked: the largest real commencement
# group in the corpus is `asp/2018/9`'s 58 provisions commenced by
# `ssi/2018/298`, and a commencement answer that stops at 40 of them is a worse
# answer than one that lists them. Above this the count carries the fact and the
# list carries the examples.
_MAX_CHANGED_PROVISIONS = 60
# How many related instruments are listed. `ukpga/2004/33` reaches 369 groups;
# no answer is improved by the 41st, and the total is reported either way.
_MAX_RELATED_INSTRUMENTS = 40
# The operative provision on the other side ("reg. 2 sch.") — a handful is
# provenance, a hundred is noise.
_MAX_EFFECTING_PROVISIONS = 6


def _provision_sort_key(label) -> list:
    """Natural order for provision labels: s. 2 before s. 10, Sch. 6 para. 2 before 10.

    The API returns rows in no useful order, and a lawyer reading "s. 9, s. 21,
    s. 20, s. 17" cannot see at a glance which sections are commenced. Digit
    runs compare numerically, everything else case-insensitively as text.
    """
    parts = re.split(r"(\d+)", str(label or ""))
    return [(1, int(p)) if p.isdigit() else (0, p.lower()) for p in parts if p != ""]


def _https(url) -> str:
    """Upgrade a legislation.gov.uk URL to https.

    The feed emits both schemes for the same resource (see note 2 above). One
    spelling is emitted so a citation copied out of this result is stable, and
    https is the one legislation.gov.uk actually serves. `normalise_leg_url`
    (P1.6) already treats the two as equal, so link enforcement is unaffected
    either way — this is for the reader.
    """
    return re.sub(r"^http://", "https://", str(url or ""))


# FIX_PLAN P2.5 (B4): the two commencement effect strings are NOT the same
# relation, and merging them answers "what commenced this Act" with instruments
# that commenced something else.
#
# `coming into force` names a real provision of the subject: 19,031 relations
# over 5,180 distinct `changed_provision` values across the legislation_ids the
# replay corpus touches. That is the subject's own commencement and it is what
# P3.5 retrieves.
#
# `Commencement Order` never does. Across **1,355 of those relations the
# `changed_provision` is one of eight placeholder values** — `specified amended
# provision(s)` (1,068), `None` (199), `C/O` (73), `specified provision(s)` (11)
# and four casing/typo variants — and not one of them is a provision. The row
# means *some other Act's commencement order brought into force an amendment TO
# the subject*: `ssi/2001/81`, the Adults with Incapacity (Scotland) Act 2000
# (Commencement No. 1) Order 2001, appears against `ukpga/1963/41` because
# `asp/2000/4` substituted words in its s. 90(1) and that order commenced the
# substitution.
#
# **This is the trap P3.5 left open and the reason it matters here.**
# `ukpga/1998/46` — 6411's Scotland Act 1998, the acceptance session for this
# row — has **zero `coming into force` relations and 29 `Commencement Order`
# ones**, whose affecting instruments include two commencement orders for
# entirely unrelated Acts. P3.5's block invites the model to state any relation
# it lists, citing the instrument named against it. Left merged, the fix for
# 6411's unsourced *"the Scotland Act 1998 (Commencement) Order 1998"* would
# have been a differently-sourced wrong answer. `asp/2000/4` carries both
# classes (35 real, 14 placeholder), so the split is not academic.
#
# Re-measure with `python -m tools.lex_probe --inforce`.
_COMMENCEMENT_OF_SUBJECT = "coming into force"
_COMMENCEMENT_ORDER_EFFECT = "commencement order"

# The repeal/revocation family, matched on the effect string. Deliberately a
# substring test rather than a fixed set: the vocabulary has 2,912 distinct
# values over the same sample and the family spans `repealed` (2,957), `words
# repealed` (1,182), `revoked` (525), `word repealed` (376), `repealed in part`
# (210), `repeal` (194), `entry repealed`, `repealed (1.1.1996)` and more. A
# fixed set would silently miss the tail, and missing a repeal is the direction
# this row exists to stop.
_REPEAL_EFFECT_TOKENS = ("repeal", "revok", "revoc")


def _effect_is_commencement_of_subject(effect: str) -> bool:
    """True only for the effect that names a provision of the subject."""
    return str(effect or "").strip().lower() == _COMMENCEMENT_OF_SUBJECT


def _effect_is_commencement_order(effect: str) -> bool:
    """True for a `Commencement Order` row — a commencement of an AMENDMENT."""
    return str(effect or "").strip().lower() == _COMMENCEMENT_ORDER_EFFECT


def _effect_is_repeal(effect: str) -> bool:
    """True for anything in the repeal/revocation family. See `_REPEAL_EFFECT_TOKENS`."""
    low = str(effect or "").lower()
    return any(tok in low for tok in _REPEAL_EFFECT_TOKENS)


def _slim_amendment_results(resp_json, legislation_id: str, direction: str) -> dict:
    """Collapse an `/amendment/search` response into grouped, deduplicated relations.

    `direction` is the model's word for the API's `search_amended` flag:

      * ``"to"`` — changes made **to** `legislation_id` (``search_amended=True``).
        This is the direction that answers "has it been commenced, amended or
        repealed", and it is the default.
      * ``"by"`` — changes `legislation_id` makes **to** other legislation
        (``search_amended=False``).

    Two field mappings fall out of that, and they are **direction-independent**,
    which is what lets one shape serve both: `changed_provision` is always the
    provision that was changed, and `affecting_provision` is always the
    provision that effected the change. Only the *grouping* side flips — the
    other instrument is the affecting one under ``"to"`` and the changed one
    under ``"by"``.

    Anything that is not a list of dicts is passed through untouched, for the
    reason `_slim_section_results` does: a slimmer must never be the reason a
    retrieval goes missing.
    """
    items = resp_json if isinstance(resp_json, list) else (
        resp_json.get("results") if isinstance(resp_json, dict) else None
    )
    if not isinstance(items, list):
        return resp_json

    lid = _short_legislation_id(legislation_id)
    other_key = "affecting_legislation" if direction == "to" else "changed_legislation"
    other_url_key = "affecting_url" if direction == "to" else "changed_url"

    seen = set()
    groups = {}
    effects = {}
    rows_returned = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        rows_returned += 1
        # Identity WITHOUT the URLs, which is what collapses the http/https
        # twins. Everything that distinguishes two real relations is here:
        # which provision of what was changed, which provision of what did it,
        # and the effect.
        key = (
            item.get("changed_legislation"), item.get("changed_provision"),
            item.get("affecting_legislation"), item.get("affecting_provision"),
            item.get("type_of_effect"),
        )
        if key in seen:
            continue
        seen.add(key)

        effect = item.get("type_of_effect") or "not stated"
        effects[effect] = effects.get(effect, 0) + 1
        other = _short_legislation_id(item.get(other_key) or "")
        g = groups.setdefault((other, effect), {
            "legislation_id": other,
            "url": _https(item.get(other_url_key)),
            "self": bool(other) and other == lid,
            "type_of_effect": effect,
            # P2.5: `Commencement Order` rows do not commence the subject — see
            # the note above. Emitted only on those rows, so a group without the
            # key is not thereby asserted to commence anything.
            **({"commences_this_legislation": False}
               if _effect_is_commencement_order(effect) else {}),
            "count": 0,
            "changed_provisions": [],
            "effected_by": [],
        })
        g["count"] += 1
        prov = item.get("changed_provision")
        if prov and prov not in g["changed_provisions"]:
            g["changed_provisions"].append(prov)
        eff_prov = item.get("affecting_provision")
        if eff_prov and eff_prov not in g["effected_by"]:
            g["effected_by"].append(eff_prov)

    related = []
    for g in groups.values():
        g["changed_provisions"].sort(key=_provision_sort_key)
        held = len(g["changed_provisions"])
        if held > _MAX_CHANGED_PROVISIONS:
            g["changed_provisions"] = g["changed_provisions"][:_MAX_CHANGED_PROVISIONS]
            g["changed_provisions_not_listed"] = held - _MAX_CHANGED_PROVISIONS
        g["effected_by"] = sorted(
            g["effected_by"], key=_provision_sort_key
        )[:_MAX_EFFECTING_PROVISIONS]
        related.append(g)
    # Relations by another instrument first: that is the answer to "commenced by
    # regulation", and the self-referential block is context for it. P2.5 sends
    # `Commencement Order` groups to the same back of the queue as the
    # self-referential ones, and for the same reason: neither is an answer to
    # "what commenced this", so neither should displace a real relation at
    # `_MAX_RELATED_INSTRUMENTS`. On `ukpga/1998/46` that is 29 groups of one row
    # each against 857 relations.
    related.sort(key=lambda g: (
        g["self"] or _effect_is_commencement_order(g["type_of_effect"]),
        -g["count"], g["legislation_id"],
    ))

    by_self = sum(g["count"] for g in related if g["self"])
    # The subject's own URL, taken from the feed rather than composed. Two
    # consumers need it and neither is obvious: the model, to cite the Act it
    # is answering about, and `enforce_provision_links` (P1.6), which demotes an
    # unverified provision link to the Act only when the Act's URL was returned
    # by some tool. Per-provision URLs are deliberately NOT emitted — see the
    # note above `_MAX_CHANGED_PROVISIONS`.
    subject_url = ""
    for item in items:
        if isinstance(item, dict):
            key = "changed_url" if direction == "to" else "affecting_url"
            if _short_legislation_id(item.get(key.replace("_url", "_legislation"))) == lid:
                subject_url = _https(item.get(key))
                break
    out = {
        "legislation_id": lid,
        "url": subject_url,
        "direction": direction,
        "relations_are": (
            "changes made TO %s by the legislation listed below" % lid
            if direction == "to"
            else "changes made BY %s to the legislation listed below" % lid
        ),
        "rows_returned": rows_returned,
        "relations": len(seen),
        "duplicate_rows_collapsed": rows_returned - len(seen),
        "by_other_legislation": len(seen) - by_self,
        "by_this_legislation_itself": by_self,
        "effects": dict(sorted(effects.items(), key=lambda kv: (-kv[1], kv[0]))),
        # P2.5 (B4): the three currency-bearing counts, separated in code so no
        # agent downstream has to parse the effect vocabulary to tell them
        # apart. `commencement_orders_of_amendments` is the trap.
        "provisions_commenced": sum(
            v for k, v in effects.items() if _effect_is_commencement_of_subject(k)
        ),
        "commencement_orders_of_amendments": sum(
            v for k, v in effects.items() if _effect_is_commencement_order(k)
        ),
        "repeal_or_revocation_relations": sum(
            v for k, v in effects.items() if _effect_is_repeal(k)
        ),
        "related_instruments": len(related),
        "related": related[:_MAX_RELATED_INSTRUMENTS],
    }
    if len(related) > _MAX_RELATED_INSTRUMENTS:
        out["related_instruments_not_listed"] = len(related) - _MAX_RELATED_INSTRUMENTS
    return out
