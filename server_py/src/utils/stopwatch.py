# Worker tool classification for the search:retrieval efficiency ratio.
# Phase 1 = discovery searches; Phase 2 = retrieving full provisions/judgments.
_PHASE1_SEARCH_TOOLS = frozenset({
    "search_legislation", "search_case_law",
    "search_scottish_parliament", "search_scottish_committee_transcripts",
    "search_scottish_plenary", "search_bills",
})
_PHASE2_RETRIEVAL_TOOLS = frozenset({
    "search_legislation_sections", "get_legislation_text", "get_case_law_text",
    "get_scottish_committee_transcript", "get_scottish_plenary_debate",
})
# get_member_info is intentionally unclassified — it is a metadata lookup (MSP
# details), neither a discovery search nor primary-source retrieval.

# Primary-resource retrieval tools whose key_arg identifies a distinct resource,
# used to count "distinct primary resources retrieved" (see _retrieved_lids /
# distinct_legislation_ids_retrieved). Legislation Acts + case-law judgments.
_LEGISLATION_RETRIEVAL_TOOLS = frozenset({
    "search_legislation_sections", "get_legislation_text",
})
# SP transcript retrieval tools. After WI-2's composite-key fix, their key_arg is
# "meeting_id:iob_id", so the same distinct-resource set counts distinct transcripts.
_TRANSCRIPT_RETRIEVAL_TOOLS = frozenset({
    "get_scottish_plenary_debate", "get_scottish_committee_transcript",
})


class TimingCollector:
    """Collects per-request timing AND algorithmic-efficiency data across the
    agent call stack.

    Passed through chat_loop, worker agent, summarisation, and LEX API calls so
    every stage can record its own signals without touching the HTTP layer.

    Timing fields answer "how long / how much did it cost?"; the efficiency
    fields answer "is the Manager→Worker loop behaving correctly?" (delegating
    once, searching minimally, retrieving each primary resource once, not fanning
    out or duplicating, summarising only when needed, citing what it retrieved).

    distinct_legislation_ids_retrieved is a generic "distinct primary resources
    retrieved" counter — Acts / judgments (by redundancy key) on the legislation
    bot, SP transcripts (keyed meeting_id:iob_id) on the parliament bot. The DB
    column name is kept for backward compatibility.
    """

    def __init__(self, request_id: str):
        self.request_id = request_id
        # --- Timing / cost (existing) ---
        self.queue_wait_ms: float = 0.0
        self.learning_db_ms: float = 0.0
        self.llm_calls: int = 0
        self.llm_total_ms: float = 0.0
        self.llm_ttft_first_ms: float = 0.0
        self.lex_api_calls: int = 0
        self.lex_api_total_ms: float = 0.0
        self.total_ms: float = 0.0
        self.total_cost_usd: float = 0.0

        # --- Efficiency (new) ---
        self.manager_delegations: int = 0
        self.peer_consults: int = 0
        self.worker_tool_calls: int = 0
        self.react_turns_max: int = 0
        self.max_turns_halted: int = 0
        self.phase1_search_calls: int = 0
        self.phase2_retrieval_calls: int = 0
        self.distinct_legislation_ids_seen: int = 0
        self.distinct_legislation_ids_retrieved: int = 0
        self.redundant_tool_calls: int = 0
        self.summarisation_calls: int = 0
        self.summarisation_chars_in: int = 0
        self.summarisation_chars_out: int = 0
        self.summarisation_chunks: int = 0
        self.truncation_events: int = 0
        self.sources_extracted: int = 0
        self.sources_kept: int = 0
        self.source_filter_fallback: int = 0
        # Parliamentary search budget: count of search calls hard-stopped because
        # the per-request budget was already exhausted (the model looped on search).
        self.search_budget_blocked: int = 0
        # Deep Research tool-result memo: exact-repeat tool calls served from the
        # per-request memo (a saving, NOT a loop-health signal — deliberately kept
        # out of worker_tool_calls / phase counts / redundant_tool_calls).
        self.memo_hits: int = 0
        # Provider prompt caching (OpenRouter): input tokens served from the
        # provider's prompt cache, and the discount OpenRouter reports for them.
        self.cached_prompt_tokens: int = 0
        self.cache_discount_usd: float = 0.0

        # Internal sets (not persisted) backing the distinct/redundant counters.
        self._seen_call_sigs: set = set()
        self._seen_lids: set = set()
        self._retrieved_lids: set = set()

    # --- Timing / cost recorders (existing) ---

    def record_queue_wait(self, ms: float) -> None:
        self.queue_wait_ms = ms

    def record_learning_db(self, ms: float) -> None:
        self.learning_db_ms = ms

    def record_llm_call(self, ttft_ms: float, total_ms: float) -> None:
        self.llm_calls += 1
        self.llm_total_ms += total_ms
        if self.llm_ttft_first_ms == 0.0:
            self.llm_ttft_first_ms = ttft_ms

    def record_lex_api_call(self, tool_name: str, ms: float) -> None:
        self.lex_api_calls += 1
        self.lex_api_total_ms += ms

    def record_total(self, ms: float) -> None:
        self.total_ms = ms

    def record_cost(self, usd: float) -> None:
        self.total_cost_usd += usd

    # --- Efficiency recorders (new) ---

    def record_delegation(self) -> None:
        self.manager_delegations += 1

    def record_peer_consult(self) -> None:
        self.peer_consults += 1

    def record_worker_tool(self, name: str, key_arg: str = None) -> None:
        """Record one worker tool invocation: total count, phase classification,
        redundant-call detection, and distinct-Act-retrieval tracking.

        key_arg is the identifying argument (legislation_id / url / gid / meeting_id)
        used to detect the same resource being fetched twice in one request.
        """
        self.worker_tool_calls += 1
        if name in _PHASE1_SEARCH_TOOLS:
            self.phase1_search_calls += 1
        elif name in _PHASE2_RETRIEVAL_TOOLS:
            self.phase2_retrieval_calls += 1

        if key_arg:
            sig = (name, key_arg)
            if sig in self._seen_call_sigs:
                self.redundant_tool_calls += 1
            else:
                self._seen_call_sigs.add(sig)
            if name in _LEGISLATION_RETRIEVAL_TOOLS or name in _TRANSCRIPT_RETRIEVAL_TOOLS:
                self._retrieved_lids.add(key_arg)
                self.distinct_legislation_ids_retrieved = len(self._retrieved_lids)

    def record_legislation_ids_seen(self, ids) -> None:
        """Record legislation_ids returned by a search_legislation result."""
        for lid in ids:
            if lid:
                self._seen_lids.add(lid)
        self.distinct_legislation_ids_seen = len(self._seen_lids)

    def record_react_turn(self, turn: int) -> None:
        if turn > self.react_turns_max:
            self.react_turns_max = turn

    def record_max_turns_halt(self) -> None:
        self.max_turns_halted = 1

    def record_summarisation(self, chars_in: int, chars_out: int, chunks: int = 1) -> None:
        self.summarisation_calls += 1
        self.summarisation_chars_in += chars_in
        self.summarisation_chars_out += chars_out
        self.summarisation_chunks += chunks

    def record_truncation(self) -> None:
        self.truncation_events += 1

    def record_source_stats(self, extracted: int, kept: int, fallback: bool) -> None:
        """Accumulate source extract/keep counts (a request may delegate more
        than once, each producing its own source list)."""
        self.sources_extracted += extracted
        self.sources_kept += kept
        if fallback:
            self.source_filter_fallback = 1

    def record_search_budget_blocked(self) -> None:
        self.search_budget_blocked += 1

    def record_memo_hit(self) -> None:
        self.memo_hits += 1

    def record_cached_tokens(self, tokens: int, discount_usd: float = 0.0) -> None:
        self.cached_prompt_tokens += int(tokens or 0)
        # OpenRouter reports cache_discount as a negative delta on cost for
        # Anthropic cache reads; store its absolute value as "money saved".
        if discount_usd:
            self.cache_discount_usd += abs(float(discount_usd))

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "total_ms": round(self.total_ms),
            "queue_wait_ms": round(self.queue_wait_ms),
            "learning_db_ms": round(self.learning_db_ms),
            "llm_calls": self.llm_calls,
            "llm_total_ms": round(self.llm_total_ms),
            "llm_ttft_first_ms": round(self.llm_ttft_first_ms),
            "lex_api_calls": self.lex_api_calls,
            "lex_api_total_ms": round(self.lex_api_total_ms),
            "total_cost_usd": self.total_cost_usd,
            # Efficiency
            "manager_delegations": self.manager_delegations,
            "peer_consults": self.peer_consults,
            "worker_tool_calls": self.worker_tool_calls,
            "react_turns_max": self.react_turns_max,
            "max_turns_halted": self.max_turns_halted,
            "phase1_search_calls": self.phase1_search_calls,
            "phase2_retrieval_calls": self.phase2_retrieval_calls,
            "distinct_legislation_ids_seen": self.distinct_legislation_ids_seen,
            "distinct_legislation_ids_retrieved": self.distinct_legislation_ids_retrieved,
            "redundant_tool_calls": self.redundant_tool_calls,
            "summarisation_calls": self.summarisation_calls,
            "summarisation_chars_in": self.summarisation_chars_in,
            "summarisation_chars_out": self.summarisation_chars_out,
            "summarisation_chunks": self.summarisation_chunks,
            "truncation_events": self.truncation_events,
            "sources_extracted": self.sources_extracted,
            "sources_kept": self.sources_kept,
            "source_filter_fallback": self.source_filter_fallback,
            "search_budget_blocked": self.search_budget_blocked,
            "memo_hits": self.memo_hits,
            "cached_prompt_tokens": self.cached_prompt_tokens,
            "cache_discount_usd": self.cache_discount_usd,
        }
