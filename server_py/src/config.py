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

    class Config:
        env_file = ".env"
        env_case_sensitive = False


settings = Settings()
