from pydantic_settings import BaseSettings
import logging

# Configure Logging (Centralized)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lexchat")

class Settings(BaseSettings):
    PORT: int = 3000
    DATABASE_URL: str = "postgresql://lexuser:lexpassword@127.0.0.1:5432/lexchat"
    JWT_SECRET: str = "docker_default_jwt_secret"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    
    # Email Settings
    EMAIL_USER: str = ""
    EMAIL_PASS: str = ""
    
    # Lex API
    LEX_API_URL: str = "https://lex.lab.i.ai.gov.uk"
    
    class Config:
        env_file = "../server/.env"
        extra = "ignore"

settings = Settings()
