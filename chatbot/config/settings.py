from os import getenv


class Settings:
    LLM_PROVIDER = getenv("LLM_PROVIDER", "openai")
    LLM_API_KEY = getenv("LLM_API_KEY", "")
    VECTOR_DB_URL = getenv("VECTOR_DB_URL", "http://localhost:6333")


settings = Settings()
