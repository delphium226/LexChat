from pydantic_settings import BaseSettings
from typing import Optional

# Document upload limits
MAX_DOC_CHARS_PER_FILE = 50_000   # ~12K tokens per file
MAX_TOTAL_DOC_CHARS = 80_000      # total injected into system prompt
MAX_DOC_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB



# Prompts moved to prompts.py; re-exported here so existing
# `from .config import <PROMPT>` imports keep working.
from .prompts import (  # noqa: F401,E402
    MANAGER_SYSTEM_PROMPT,
    MANAGER_SYSTEM_PROMPT_CONVERSATIONAL,
    PARLIAMENT_MANAGER_SYSTEM_PROMPT,
    PARLIAMENT_WORKER_SYSTEM_PROMPT,
    WORKER_SYSTEM_PROMPT,
    WORKER_SYSTEM_PROMPT_CASE_LAW,
    WORKER_SYSTEM_PROMPT_CONVERSATIONAL,
    WORKER_SYSTEM_PROMPT_HYBRID,
    build_filter_constraint_block,
    get_manager_mode_note,
    get_manager_system_prompt,
    get_worker_system_prompt,
)


MODEL_LIST = [
    {"name": "deepseek-v3.2:cloud", "contextLengthKB": 160},
    {"name": "deepseek-v4-pro:cloud", "contextLengthKB": 160},
    {"name": "mistral-large-3:675b-cloud", "contextLengthKB": 160},
    {"name": "kimi-k2-thinking:cloud", "contextLengthKB": 256},
    {"name": "kimi-k2.6:cloud", "contextLengthKB": 256},
    {"name": "glm-5.1:cloud", "contextLengthKB": 128},
    {"name": "minimax-m2.7:cloud", "contextLengthKB": 256},
]

OPENROUTER_MODEL_LIST = [
    {"name": "anthropic/claude-sonnet-4-6", "contextLengthKB": 200},
    {"name": "anthropic/claude-opus-4-7", "contextLengthKB": 200},
    {"name": "google/gemini-2.5-pro", "contextLengthKB": 1000},
    {"name": "google/gemini-2.0-flash", "contextLengthKB": 1000},
    {"name": "openai/gpt-4o", "contextLengthKB": 128},
    {"name": "mistralai/mistral-large-2411", "contextLengthKB": 128},
    {"name": "deepseek/deepseek-r1", "contextLengthKB": 128},
]


class Settings(BaseSettings):
    # Core
    port: int = 8000
    host: str = "0.0.0.0"

    # Database
    database_url: str = "postgresql://lexuser:lexpassword@localhost:5432/lexchat"
    db_max_connections: int = 20

    # Auth
    jwt_secret: str = "dev_secret_key_change_me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 1 day default

    # Agent / Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_api_key: Optional[str] = None
    ollama_default_context: int = 131072
    max_concurrent_requests: int = 5
    ollama_temperature: float = 0.1

    # Agent / OpenRouter
    openrouter_api_key: Optional[str] = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # LEX API
    lex_api_url: str = "https://lex.lab.i.ai.gov.uk/"

    # Parliament APIs
    twfy_api_key: Optional[str] = None  # TheyWorkForYou API key (free at theyworkforyou.com/api/key)

    # Scottish Parliament TV video deep-links (see docs/parliament/VIDEO_DEEPLINK_PLAN.md).
    # Dark-launched: when off, no captions are crawled and no video links are attached.
    enable_video_deeplinks: bool = False
    sptv_base_url: str = "https://www.scottishparliament.tv"

    # UK Parliament (parliamentlive.tv) video deep-links — the Westminster sibling of
    # the above, kept separate so the two jurisdictions toggle independently.
    # See docs/parliament/WESTMINSTER_VIDEO_IMPLEMENTATION_PLAN.md.
    enable_westminster_video_deeplinks: bool = False
    plive_base_url: str = "https://www.parliamentlive.tv"

    # Proxy
    https_proxy: Optional[str] = None

    # Email
    email_user: Optional[str] = None
    email_pass: Optional[str] = None

    # Bot identity — overridden by BOT_ID / BOT_CONFIG_PATH env vars
    bot_id: str = "legislation_bot"
    bot_config_path: str = ""

    # Research mode override — if set, takes precedence over the per-request value
    # sent by the frontend. Used by dedicated bots (e.g. parliament_bot sets
    # RESEARCH_MODE=parliamentary_records in their .env).
    research_mode: str = ""

    # Logging — base level for the app/agent/http/crawler/sptv loggers. Read
    # directly from the environment in utils/logger.py (before settings import);
    # declared here so it is documented and validated as a known setting.
    log_level: str = "INFO"
    console_log_level: str = ""  # blank = same as log_level

    class Config:
        env_file = ".env"
        env_case_sensitive = False


settings = Settings()


# ---------------------------------------------------------------------------
# Agent-loop efficiency profiles (per bot / research mode)
# ---------------------------------------------------------------------------
# Per-request breach rules AND dashboard indicator bands for the Manager→Worker
# loop, keyed by the bot's research mode (RESEARCH_MODE env → settings.research_mode).
# When a request's metrics breach a rule, an ActivityLog(event_type="EFFICIENCY")
# row is written so regressions surface in the admin activity feed automatically.
#
# The two bots run the same codebase but have different healthy baselines:
#   - "legislation" — delegate once, retrieve ~1-3 focused Acts; fan-out measured
#     against sources_kept. These values reflect measured legislation-bot baselines.
#   - "parliamentary_records" — retrieve distinct SP transcripts (fan-out measured
#     against distinct_legislation_ids_retrieved, ≈1 retrieval per transcript) and
#     honour the search budget. The parliamentary band/threshold values below are
#     STARTING POINTS, not measured baselines — re-tune once real parliament
#     traffic accumulates.
#
# "fanout_denominator" names the SQL column used as the fan-out denominator in
# stats.py; it is allowlist-validated there before interpolation.
# "bands" values are (warn_at, bad_at) cut points for stats.py _band().
#
# The "reformat" band (worker report-structure repair rate) is UNMEASURED on
# every profile — it was added to establish the base rate, so its cut-points are
# a placeholder to be re-tuned once real traffic accumulates. Deliberately an
# indicator only, with no matching breach rule: the reformat retry is fail-soft
# and expected occasionally, so alerting on a single one would flood the activity
# feed before we know what "normal" looks like.
EFFICIENCY_PROFILES = {
    "legislation": {
        # per-request breach rules (evaluate_efficiency_breaches)
        "max_delegations": 1,           # >1 = the manager re-delegated the same question
        "max_redundant_tool_calls": 0,  # >0 = same Act/case fetched more than once
        "fanout_abs": 5,                # phase-2 retrieval calls at/above this count, AND
        "fanout_ratio": 3.0,            # retrievals-per-kept-source at/above this ratio → fan-out
        "fanout_denominator": "sources_kept",
        # dashboard indicator bands: (warn_at, bad_at) for _band()
        "bands": {
            "delegation": (1.05, 1.15),
            "fanout": (2.0, 3.0),
            "redundant": (0.05, 0.10),
            "halt": (0.001, 0.02),
            "fallback": (0.1, 0.25),
            "reformat": (0.05, 0.15),
        },
    },
    "parliamentary_records": {
        "max_delegations": 1,
        "max_redundant_tool_calls": 0,             # legitimate after the composite-key fix
        "fanout_abs": 5,
        "fanout_ratio": 2.0,                       # retrievals per distinct transcript ≈ 1
        "fanout_denominator": "distinct_legislation_ids_retrieved",
        "max_budget_blocked": 0,                   # any blocked search = model looped on search
        "bands": {
            "delegation": (1.05, 1.15),
            "fanout": (1.3, 2.0),
            "redundant": (0.05, 0.10),
            "halt": (0.001, 0.02),
            "fallback": (0.15, 0.35),              # excerpt-heavy answers cite less precisely
            "budget_blocked": (0.05, 0.15),        # share of requests hitting the budget wall
            "reformat": (0.05, 0.15),
        },
    },
    # Westminster: same search→retrieve shape as the Holyrood bot (one
    # get_hansard_debate per distinct debate), so it starts from the Holyrood
    # numbers. These are UNMEASURED starting points — re-tune once real
    # Westminster traffic accumulates. The one expected difference is a lower
    # fallback rate: Hansard retrieval is full-text, never excerpt-only.
    "westminster_records": {
        "max_delegations": 1,
        "max_redundant_tool_calls": 0,
        "fanout_abs": 5,
        "fanout_ratio": 2.0,                       # retrievals per distinct debate ≈ 1
        "fanout_denominator": "distinct_legislation_ids_retrieved",
        "max_budget_blocked": 0,
        "bands": {
            "delegation": (1.05, 1.15),
            "fanout": (1.3, 2.0),
            "redundant": (0.05, 0.10),
            "halt": (0.001, 0.02),
            "fallback": (0.1, 0.25),
            "budget_blocked": (0.05, 0.15),
            "reformat": (0.05, 0.15),
        },
    },
}


def get_efficiency_profile() -> dict:
    """Return the efficiency profile for this bot process, selected by
    settings.research_mode. Blank / unknown mode → the legislation profile."""
    mode = settings.research_mode or "legislation"
    return EFFICIENCY_PROFILES.get(mode, EFFICIENCY_PROFILES["legislation"])


def evaluate_efficiency_breaches(m: dict) -> list:
    """Return a list of human-readable breach reasons for a request's metrics
    dict (TimingCollector.to_dict()). Empty list = healthy."""
    # Deep Research is code-orchestrated: one worker run per approved plan step
    # plus a synthesis call, so N delegations / wide fan-out is the design, not
    # a breach. The thresholds above describe the standard Manager→Worker loop.
    if m.get("chat_mode") == "deep_research":
        return []

    t = get_efficiency_profile()
    breaches = []

    if m.get("manager_delegations", 0) > t["max_delegations"]:
        breaches.append(f"re-delegation (delegations={m['manager_delegations']})")

    if m.get("max_turns_halted", 0):
        breaches.append(f"max-turns halt (turns={m.get('react_turns_max', 0)})")

    if m.get("redundant_tool_calls", 0) > t["max_redundant_tool_calls"]:
        breaches.append(f"redundant tool calls={m['redundant_tool_calls']}")

    if m.get("source_filter_fallback", 0):
        breaches.append("source-filter fallback (answer cited no retrieved source)")

    phase2 = m.get("phase2_retrieval_calls", 0)
    denom = m.get(t["fanout_denominator"], 0)
    ratio = phase2 / max(denom, 1)
    if phase2 >= t["fanout_abs"] and ratio >= t["fanout_ratio"]:
        breaches.append(f"Phase-2 fan-out (retrievals={phase2}, denom={denom}, ratio={ratio:.1f})")

    if "max_budget_blocked" in t and m.get("search_budget_blocked", 0) > t["max_budget_blocked"]:
        breaches.append(f"search budget exhausted (blocked={m['search_budget_blocked']})")

    return breaches
