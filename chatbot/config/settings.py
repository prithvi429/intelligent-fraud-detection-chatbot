"""
Settings
--------
Central configuration for the FraudBot system.
Loads environment variables from `.env` using Pydantic BaseSettings.

Includes:
- API Keys (OpenAI, Pinecone)
- Backend URLs
- Optional Redis & feature toggles
- Token & threshold limits
- Logging & debug options

Usage:
    from chatbot.config.settings import settings
    print(settings.OPENAI_API_KEY)
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator
from dotenv import load_dotenv

# Load .env from project root or chatbot directory
load_dotenv()


class Settings(BaseSettings):
    """
    Chatbot configuration model.
    Values are read from environment variables, with validation & defaults.
    """

    # -----------------------------
    # 🧠 Model / API Configurations
    # -----------------------------
    openai_api_key: str
    openai_model: str = "gpt-3.5-turbo"

    # -----------------------------
    # 🌐 Backend API
    # -----------------------------
    backend_url: str = "http://localhost:8000"

    # -----------------------------
    # ☁️ Pinecone (Vector DB for RAG)
    # -----------------------------
    pinecone_api_key: Optional[str] = None
    pinecone_env: str = "us-west2-gcp-free"
    pinecone_index_name: str = "fraud-guidance"
    pinecone_enabled: bool = False

    # -----------------------------
    # 🗄️ Redis (Session Cache)
    # -----------------------------
    redis_url: Optional[str] = None
    use_redis_sessions: bool = False

    # -----------------------------
    # ⚙️ Limits & Thresholds
    # -----------------------------
    max_tokens: int = 4000
    guidance_threshold: float = 0.7  # cosine similarity threshold (0–1)

    # -----------------------------
    # 🧾 Logging & Debug Options
    # -----------------------------
    log_level: str = "INFO"
    debug: bool = False

    # -----------------------------
    # ✅ Pydantic Model Config
    # -----------------------------
    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore"  # Ignore unrecognized environment vars
    )

    # -----------------------------
    # 🔍 Validation
    # -----------------------------
    @model_validator(mode="after")
    def validate_keys(self):
        """Validate key dependencies and numeric limits."""
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required.")
        if self.pinecone_enabled and not self.pinecone_api_key:
            raise ValueError("PINECONE_API_KEY is required when PINECONE_ENABLED=True.")
        if self.use_redis_sessions and not self.redis_url:
            raise ValueError("REDIS_URL is required when USE_REDIS_SESSIONS=True.")
        if not (0 <= self.guidance_threshold <= 1):
            raise ValueError("GUIDANCE_THRESHOLD must be between 0 and 1.")
        if self.max_tokens < 1000:
            raise ValueError("MAX_TOKENS must be at least 1000.")
        return self

    # -----------------------------
    # 🔁 Compatibility Properties
    # -----------------------------
    # Allows both snake_case and UPPER_CASE access
    @property
    def OPENAI_API_KEY(self): return self.openai_api_key
    @property
    def OPENAI_MODEL(self): return self.openai_model
    @property
    def BACKEND_URL(self): return self.backend_url
    @property
    def PINECONE_API_KEY(self): return self.pinecone_api_key
    @property
    def PINECONE_ENV(self): return self.pinecone_env
    @property
    def PINECONE_INDEX_NAME(self): return self.pinecone_index_name
    @property
    def PINECONE_ENABLED(self): return self.pinecone_enabled
    @property
    def REDIS_URL(self): return self.redis_url
    @property
    def USE_REDIS_SESSIONS(self): return self.use_redis_sessions
    @property
    def MAX_TOKENS(self): return self.max_tokens
    @property
    def GUIDANCE_THRESHOLD(self): return self.guidance_threshold
    @property
    def LOG_LEVEL(self): return self.log_level
    @property
    def DEBUG(self): return self.debug


# ---------------------------------
# 🧩 Global Settings Instance
# ---------------------------------
settings = Settings()


# ---------------------------------
# 🪵 Utility: Get Log Level Int
# ---------------------------------
def get_logger_level() -> int:
    """Map textual LOG_LEVEL to numeric value."""
    level_map = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
    return level_map.get(settings.log_level.upper(), 20)
