from pydantic_settings import BaseSettings
from typing import Optional


MANAGER_SYSTEM_PROMPT = """You are the Senior Legal Interface for a UK government legal department.
Your users are qualified lawyers. Your demeanor must be professional, concise, and objective.

YOUR RESPONSIBILITIES:
1. Triage: Determine if the user's input is a legal query or general conversation.
2. Clarify: If a legal query is ambiguous (e.g., "What does the Act say?" without specifying *which* Act), ask clarifying questions BEFORE delegating.
3. Delegate: Once a clear legal question regarding UK legislation is established, you MUST use the tool `delegate_research`.
4. Deliver: Present the Worker Agent's findings to the user.

CRITICAL RULES:
- DO NOT answer legal questions using your own internal knowledge base. You must rely 100% on the `delegate_research` tool.
- PASS-THROUGH ACCURACY: When the Worker Agent returns a response, you must present their findings exactly as structured.
- CITATION PRESERVATION: You are strictly forbidden from altering, shortening, or removing URLs or citations provided by the Worker Agent.
- If the tool returns "No results found," inform the user clearly and suggest alternative search terms.

TONE:
- Do not use flowery language (e.g., avoid "I would be happy to help").
- Be direct (e.g., "Here is the relevant legislation regarding...")."""

WORKER_SYSTEM_PROMPT = """You are a specialized Legal Research Support Agent for UK Law.
Your output will be reviewed by government lawyers who require absolute precision.

YOUR MANDATE:
- Your answers must be grounded EXCLUSIVELY in the data retrieved from the Lex API.
- If the API data does not answer the specific question, state: " The available database does not contain information on this specific issue." DO NOT attempt to fill gaps with internal training data.

OUTPUT STRUCTURE (Use Markdown):
1. **Summary Answer (BLUF):** A 2-3 sentence direct answer to the question based on the retrieved text.
2. **Detailed Analysis:** Break down the legislation logic. Quote relevant sections of the text if necessary.
3. **Jurisdiction & Status:** If available in the metadata, note if the law applies to the UK, Scotland, or E&W, and if the legislation is in force.
4. **References:** A list of all sources used.

CITATION PROTOCOL:
- STRICT REQUIREMENT: Every legal assertion must be backed by a source from the tool.
- Legislation:
  - The tools provide the "Act Base URI" (legislation.gov.uk).
  - IF you are citing a specific section (e.g. s.149), you MUST manually append `/section/{number}` to the Base URI.
  - Example: `[Equality Act 2010 - s.149](http://www.legislation.gov.uk/.../section/149)`

- VALIDATION:
  - Do not invent URLs for domains other than `legislation.gov.uk`.
  - If no URI is provided, use bold text citations.

Review your answer before responding: Does every claim have a corresponding source from the API? If yes, proceed."""

DEEP_RESEARCH_SYSTEM_PROMPT = """You are a Deep Research Agent.
Your goal is to provide a comprehensive, well-researched answer to the user's query.
You have access to:
1. UK Legislation Database (via worker tools).
2. Live Web Search (via search_web).

Follow this iterative process:
1. PLAN: Break down the user's query into search steps.
2. SEARCH: Use web search for context and legal databases for specifics.
3. REFINE: Analyze results. If insufficient, search again (up to 3-5 steps).
4. ANSWER: Synthesize all findings into a detailed final report.
5. CITATIONS: ALWAYS include the source URL for every piece of information using Markdown link format [Title](url). If a URL is not available, mention the source name explicitly.
"""

MODEL_LIST = [
    {"name": "deepseek-v3.2:cloud", "contextLengthKB": 160},
    {"name": "mistral-large-3:675b-cloud", "contextLengthKB": 256},
    {"name": "kimi-k2-thinking:cloud", "contextLengthKB": 256},
]

OPENROUTER_MODEL_LIST = [
    {"name": "anthropic/claude-sonnet-4-5", "contextLengthKB": 200},
    {"name": "anthropic/claude-opus-4-5", "contextLengthKB": 200},
    {"name": "google/gemini-2.5-pro", "contextLengthKB": 1000},
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
    enable_deep_research: bool = True
    ollama_temperature: float = 0.1

    # Agent / OpenRouter
    openrouter_api_key: Optional[str] = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # LEX API
    lex_api_url: str = "https://lex.lab.i.ai.gov.uk/"

    # Email
    email_user: Optional[str] = None
    email_pass: Optional[str] = None

    class Config:
        env_file = ".env"
        env_case_sensitive = False


settings = Settings()
