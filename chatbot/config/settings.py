"""
Settings
--------
Loads and validates configuration from `.env` using Pydantic BaseSettings.

Covers:
- API Keys: OpenAI, Pinecone (required if enabled)
- URLs: Backend API
- Toggles: Pinecone/Redis
- Limits: Token, thresholds, debug
Usage:
    from chatbot.config import settings
    print(settings.openai_api_key)
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator
from typing import Optional
from dotenv import load_dotenv
import os

# Load environment variables early
load_dotenv()


class Settings(BaseSettings):
    """
    Chatbot configuration class with validation.
    Loads from environment variables or .env file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",             # Supports local dev and Lambda
        env_ignore_empty=True,
        extra="ignore"
    )

    # --------------------------
    # OpenAI (LLM Config)
    # --------------------------
    openai_api_key: str
    openai_model: str = "gpt-3.5-turbo"

    # --------------------------
    # Backend API (FastAPI)
    # --------------------------
    backend_url: str = "http://localhost:8000"

    # --------------------------
    # Pinecone (RAG)
    # --------------------------
    pinecone_api_key: Optional[str] = None
    pinecone_env: str = "us-west2-gcp-free"
    pinecone_index_name: str = "fraud-guidance"
    pinecone_enabled: bool = False

    # --------------------------
    # Redis (Session Persistence)
    # --------------------------
    redis_url: Optional[str] = None
    use_redis_sessions: bool = False

    # --------------------------
    # Limits and Thresholds
    # --------------------------
    max_tokens: int = 4000
    guidance_threshold: float = 0.7  # 0–1 similarity cutoff

    # --------------------------
    # Logging / Debug
    # --------------------------
    log_level: str = "INFO"
    debug: bool = False

    # --------------------------
    # Validation
    # --------------------------
    @model_validator(mode="after")
    def validate_keys(self):
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required.")
        if self.pinecone_enabled and not self.pinecone_api_key:
            raise ValueError("PINECONE_API_KEY is required when PINECONE_ENABLED=true.")
        if self.use_redis_sessions and not self.redis_url:
            raise ValueError("REDIS_URL is required when USE_REDIS_SESSIONS=true.")
        if not (0 <= self.guidance_threshold <= 1):
            raise ValueError("GUIDANCE_THRESHOLD must be between 0 and 1.")
        if self.max_tokens < 1000:
            raise ValueError("MAX_TOKENS must be at least 1000.")
        return self


# --------------------------
# Global instance
# --------------------------
settings = Settings()


# --------------------------
# Utility: Logging level mapper
# --------------------------
def get_logger_level() -> int:
    """Return numeric logging level for configured log level."""
    level_map = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
    return level_map.get(settings.log_level.upper(), 20)
