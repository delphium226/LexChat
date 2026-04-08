import logging

logger = logging.getLogger("agent")


class TimingCollector:
    """Collects per-request timing data across the agent call stack.

    Passed through chat_loop, worker agent, and LEX API calls so every
    stage can record its own elapsed time without touching the HTTP layer.
    """

    def __init__(self, request_id: str):
        self.request_id = request_id
        self.queue_wait_ms: float = 0.0
        self.learning_db_ms: float = 0.0
        self.llm_calls: int = 0
        self.llm_total_ms: float = 0.0
        self.llm_ttft_first_ms: float = 0.0
        self.lex_api_calls: int = 0
        self.lex_api_total_ms: float = 0.0
        self.total_ms: float = 0.0

    def record_queue_wait(self, ms: float) -> None:
        self.queue_wait_ms = ms
        logger.info("[TIMING] [%s] queue_wait: %.0fms", self.request_id, ms)

    def record_learning_db(self, ms: float) -> None:
        self.learning_db_ms = ms
        logger.info("[TIMING] [%s] learning_db_query: %.0fms", self.request_id, ms)

    def record_llm_call(self, ttft_ms: float, total_ms: float) -> None:
        self.llm_calls += 1
        self.llm_total_ms += total_ms
        if self.llm_ttft_first_ms == 0.0:
            self.llm_ttft_first_ms = ttft_ms
        logger.info(
            "[TIMING] [%s] ollama_call #%d — ttft: %.0fms, stream_total: %.0fms",
            self.request_id, self.llm_calls, ttft_ms, total_ms,
        )

    def record_lex_api_call(self, tool_name: str, ms: float) -> None:
        self.lex_api_calls += 1
        self.lex_api_total_ms += ms
        logger.info("[TIMING] [%s] lex_api_%s: %.0fms", self.request_id, tool_name, ms)

    def record_total(self, ms: float) -> None:
        self.total_ms = ms
        logger.info(
            "[TIMING] [%s] TOTAL: %.0fms | LLM calls: %d (%.0fms total, %.0fms ttft) "
            "| LEX calls: %d (%.0fms total)",
            self.request_id, ms,
            self.llm_calls, self.llm_total_ms, self.llm_ttft_first_ms,
            self.lex_api_calls, self.lex_api_total_ms,
        )

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
        }
