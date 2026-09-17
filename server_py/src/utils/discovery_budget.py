"""A discovery budget for the legislation Worker (FIX_PLAN P2.7).

`run_worker_agent` gave a search budget only to the parliamentary modes, so
nothing stopped a legislation Worker searching until `chat_loop`'s step cap
(20 ReAct rounds) stopped it instead. A halted worker writes no findings at all
(P2.1), so every search and retrieval it paid for is lost to the answer.

**The budget counts ROUNDS in which the Worker searched, not search calls.**
The step cap counts rounds, and the model batches calls within a round. Measured
per worker run over the replay directories (`SESSION_LOG.md`, Session 15):

* post-P3.5 (`wave3_p35`, `wave2_p25`, `wave2_p28`): halted runs search in a
  median of 14 rounds (minimum 6); completed runs in a median of 2 (p90 5,
  maximum 9). A budget of 8 search rounds stops 11 of 13 halted runs and 1 of
  149 completed ones.
* A budget of 10 search CALLS, the best call budget on the same pool, stops 8
  of 13 halted runs and 9 of 149 completed ones. The completed runs it stops
  are 6341's broad "every definition of shop" delegations, which batch 9 to 21
  searches into 6 to 16 rounds and finish. A call budget cuts those as hard as
  the runs that flail.

**A memo-served search counts.** 57 of the 81 memo hits on halted runs repeat a
search the same step had already made, which is the loop itself (6383: 5
searches issued and 9 memo-served repeats). Charging by round keeps the cost of
this low for a Deep Research step that reuses an earlier step's search: at most
one round. So the check runs BEFORE the memo lookup, unlike the parliamentary
one, and a blocked search is not served from the memo either.

**`search_case_law` is not budgeted.** No halted run in any replay directory
issued a case-law search, and completed 6375 Deep Research steps use up to 9
case-law rounds. `case_law_only` therefore gets no budget.

**The parliamentary budget is unchanged**: three calls, checked after the memo
lookup, with its own stop message (`agent_shared.run_worker_tool`).

**Fail open.** If the round is unknown (a caller outside `chat_loop`), or
anything here raises, the search runs, which is the behaviour before P2.7. A
budget must never be the reason a research run fails (Invariant 5).
"""

from __future__ import annotations

import contextvars
import json
import logging
import uuid
from typing import Optional

logger = logging.getLogger(__name__)

__all__ = [
    "LEGISLATION_SEARCH_ROUNDS",
    "LEGISLATION_DISCOVERY_TOOLS",
    "PARLIAMENT_SEARCH_BUDGET",
    "set_react_round",
    "current_react_round",
    "new_search_budget",
    "is_legislation_budget",
    "legislation_budget_blocks",
    "legislation_stop_message",
]

# Rounds, not calls: see the module docstring. Decided with the user at
# Session 15 from the distribution above.
LEGISLATION_SEARCH_ROUNDS = 8
LEGISLATION_DISCOVERY_TOOLS = frozenset({"search_legislation"})
_LEGISLATION_MODES = ("legislation_only", "legislation_and_case_law")

# The parliamentary budget, as it has always been.
PARLIAMENT_SEARCH_BUDGET = 3
_PARLIAMENT_MODES = ("parliamentary_records", "westminster_records")

_BUDGET_KIND = "legislation_rounds"

# The ReAct round the current tool call belongs to. `chat_loop` (both
# providers) sets it just before it creates the round's tool tasks, and each
# task copies the context it was created in. A worker's `chat_loop` runs inside
# the Manager's tool task, so the worker's value never leaks to the Manager.
_REACT_ROUND: contextvars.ContextVar = contextvars.ContextVar(
    "aila_react_round", default=None
)


def set_react_round(turn: int) -> None:
    """Publish the round index to the tool tasks about to be created. Never raises."""
    try:
        _REACT_ROUND.set(turn)
    except Exception:
        pass


def current_react_round():
    """The round the current tool call belongs to, or None outside `chat_loop`."""
    try:
        return _REACT_ROUND.get()
    except Exception:
        return None


def new_search_budget(research_mode: str) -> Optional[dict]:
    """The search budget for one worker run, or None for a mode that has none."""
    if research_mode in _PARLIAMENT_MODES:
        return {"remaining": PARLIAMENT_SEARCH_BUDGET}
    if research_mode in _LEGISLATION_MODES:
        # `id` tells the lawyer's footer how many steps were cut short: the
        # turn's search record is pooled across every delegation and plan step.
        return {"kind": _BUDGET_KIND, "limit": LEGISLATION_SEARCH_ROUNDS,
                "rounds": set(), "id": uuid.uuid4().hex[:8]}
    return None


def is_legislation_budget(budget: Optional[dict]) -> bool:
    return isinstance(budget, dict) and budget.get("kind") == _BUDGET_KIND


def legislation_budget_blocks(budget: Optional[dict], name: str) -> bool:
    """True if this call must be stopped. Charges a new round when it is allowed.

    A round already charged is free for every further search in it, so batching
    is never penalised. Once `limit` rounds are charged, every later search is
    refused, memo-served or not. Never raises; fails open.
    """
    if not is_legislation_budget(budget) or name not in LEGISLATION_DISCOVERY_TOOLS:
        return False
    try:
        rnd = current_react_round()
        if rnd is None:
            if not budget.get("_warned"):
                budget["_warned"] = True
                logger.warning(
                    "[Worker] Discovery budget: no ReAct round in context — "
                    "searches allowed for this run"
                )
            return False
        rounds = budget["rounds"]
        if rnd in rounds:
            return False
        if len(rounds) < int(budget["limit"]):
            rounds.add(rnd)
            return False
        return True
    except Exception:
        logger.warning("[Worker] Discovery budget check failed — search allowed", exc_info=True)
        return False


def legislation_stop_message(budget: Optional[dict]) -> str:
    """The tool result a blocked `search_legislation` call returns.

    **Not the parliamentary message.** That one says *"if no results were found
    at all, synthesize your answer stating that no relevant records were
    found"*, which is the bare negative P2.2 exists to stop. A budget stop is a
    limit on the search, and a negative reached under it must say so.

    **No `results` or `total` key**, so neither the Worker nor an instrument can
    read it as a search that ran and matched nothing.
    """
    try:
        limit = int((budget or {}).get("limit") or LEGISLATION_SEARCH_ROUNDS)
    except (TypeError, ValueError):
        limit = LEGISLATION_SEARCH_ROUNDS
    return json.dumps({
        "notice": (
            "Search limit reached: this research step has already searched the "
            f"legislation index in {limit} rounds, the most one step may use. "
            "This search was NOT run."
        ),
        "searched": False,
        "instruction": (
            "Do not call search_legislation again in this step. Work from the "
            "instruments your earlier searches returned: retrieve what you need "
            "with search_legislation_sections, get_legislation_text or "
            "get_legislation_changes, then write your report. Anything you have "
            "not located was not searched for exhaustively, because searching "
            "was stopped by this limit. If your report says that something was "
            "not found, it must also say that searching was cut short by a limit "
            "on how much one step may search, and name what you were still "
            "looking for. Do not say that it does not exist."
        ),
    })
