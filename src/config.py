"""
Configuration management for the Insurance Fraud Chatbot.
---------------------------------------------------------
- Loads environment variables from `.env` (for local) or runtime environment (AWS/GCP/Prod).
- Centralized access for database, caching, model, and API keys.
- Includes computed flags for ML, Pinecone, and AWS runtime detection.
"""

import os
import json
from typing import Optional
from dotenv import load_dotenv

# Load .env only in local/dev mode
if os.getenv("ENV", "local") == "local":
    load_dotenv()


class Config:
    """Central configuration object for all service-level environment variables."""

    # =========================================================
    # 🧩 Helper
    # =========================================================
    @staticmethod
    def _from_env(key: str, default: Optional[str] = None, cast=None):
        """Load environment variable with optional casting."""
        value = os.getenv(key, default)
        if cast and value is not None:
            try:
                return cast(value)
            except ValueError:
                return default
        return value

    # =========================================================
    # 🌐 DATABASE & STORAGE
    # =========================================================
    DB_URL: str = _from_env.__func__("DB_URL", "sqlite:///./fraud.db")
    REDIS_URL: str = _from_env.__func__("REDIS_URL", "redis://localhost:6379/0")
    S3_BUCKET_NAME: str = _from_env.__func__("S3_BUCKET_NAME", "fraud-chatbot-artifacts")
    AWS_REGION: str = _from_env.__func__("AWS_REGION", "us-east-1")

    # =========================================================
    # 🔐 SECRETS & EXTERNAL SERVICES
    # =========================================================
    OPENAI_API_KEY: Optional[str] = _from_env.__func__("OPENAI_API_KEY")
    PINECONE_API_KEY: Optional[str] = _from_env.__func__("PINECONE_API_KEY")
    PINECONE_INDEX_NAME: str = _from_env.__func__("PINECONE_INDEX_NAME", "fraud-policies-index")
    WEATHER_API_KEY: Optional[str] = _from_env.__func__("WEATHER_API_KEY")
    VENDOR_CHECK_API_URL: Optional[str] = _from_env.__func__("VENDOR_CHECK_API_URL")
    JWT_SECRET: Optional[str] = _from_env.__func__("JWT_SECRET")  # Used in security.py

    # =========================================================
    # ⚙️ FRAUD ENGINE SETTINGS
    # =========================================================
    HIGH_AMOUNT_THRESHOLD: float = _from_env.__func__("HIGH_AMOUNT_THRESHOLD", 10000, float)
    REPEAT_CLAIM_THRESHOLD: int = _from_env.__func__("REPEAT_CLAIM_THRESHOLD", 3, int)
    SIMILARITY_THRESHOLD: float = _from_env.__func__("SIMILARITY_THRESHOLD", 0.8, float)
    LOCATION_DISTANCE_THRESHOLD: float = _from_env.__func__("LOCATION_DISTANCE_THRESHOLD", 100, float)
    ML_FRAUD_THRESHOLD: float = _from_env.__func__("ML_FRAUD_THRESHOLD", 0.7, float)
    FRAUD_MODEL_PATH: str = _from_env.__func__("FRAUD_MODEL_PATH", "ml/fraud_model.pkl")

    # =========================================================
    # 🚀 APP SETTINGS
    # =========================================================
    DEBUG: bool = _from_env.__func__("DEBUG", "True", lambda v: v.lower() == "true")
    LOG_LEVEL: str = _from_env.__func__("LOG_LEVEL", "INFO").upper()
    API_HOST: str = _from_env.__func__("API_HOST", "0.0.0.0")
    API_PORT: int = _from_env.__func__("API_PORT", 8000, int)
    ENV: str = _from_env.__func__("ENV", "local")  # local/dev/prod

    # =========================================================
    # ✅ Computed Properties
    # =========================================================
    @property
    def is_ml_enabled(self) -> bool:
        """Check if the local ML fraud model exists."""
        return os.path.exists(self.FRAUD_MODEL_PATH)

    @property
    def is_pinecone_enabled(self) -> bool:
        """Check if Pinecone integration is configured."""
        return bool(self.PINECONE_API_KEY)

    @property
    def is_aws_runtime(self) -> bool:
        """Detect AWS runtime environment."""
        env_vars = ["AWS_EXECUTION_ENV", "ECS_CONTAINER_METADATA_URI", "LAMBDA_TASK_ROOT"]
        return any(os.getenv(v) for v in env_vars)

    # =========================================================
    # 📋 Config Summary
    # =========================================================
    @staticmethod
    def _redact(value: Optional[str]) -> Optional[str]:
        """Redact sensitive info for display."""
        if not value:
            return None
        if len(value) <= 6:
            return "***"
        return f"{value[:3]}***{value[-3:]}"  # Masked middle part

    def print_summary(self) -> None:
        """Pretty-print configuration summary (safe for logs)."""
        summary = {
            "ENV": self.ENV,
            "DEBUG": self.DEBUG,
            "DB_URL": self.DB_URL,
            "REDIS_URL": self.REDIS_URL,
            "S3_BUCKET_NAME": self.S3_BUCKET_NAME,
            "AWS_REGION": self.AWS_REGION,
            "OPENAI_API_KEY": self._redact(self.OPENAI_API_KEY),
            "PINECONE_API_KEY": self._redact(self.PINECONE_API_KEY),
            "WEATHER_API_KEY": self._redact(self.WEATHER_API_KEY),
            "VENDOR_CHECK_API_URL": self.VENDOR_CHECK_API_URL,
            "JWT_SECRET": self._redact(self.JWT_SECRET),
            "ML_ENABLED": self.is_ml_enabled,
            "PINECONE_ENABLED": self.is_pinecone_enabled,
            "AWS_RUNTIME": self.is_aws_runtime,
        }

        print("\n🔧 Active Configuration:")
        print(json.dumps(summary, indent=4))


# =========================================================
# Instantiate Global Config
# =========================================================
config = Config()

# Auto-print summary if running locally
if __name__ == "__main__" or config.DEBUG:
    config.print_summary()
