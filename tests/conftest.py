"""
Pytest Configuration File
-------------------------
Defines global test fixtures and mock setup for the Intelligent Fraud Detection Chatbot.

Fixes:
- ScopeMismatch (monkeypatch is function-scoped)
- Isolates environment variables, API keys, and test configs
- Ensures each test runs independently and cleanly
"""

import os
import pytest
from unittest.mock import patch
from src.config import config


# =========================================================
# 🧩 Test Config Fixture (fixed scope)
# =========================================================
@pytest.fixture(scope="function")
def mock_test_config(monkeypatch):
    """
    Mocks environment variables and config values for each test.
    Function-scoped so it plays well with pytest.monkeypatch.
    """

    # 🔐 Mock environment variables
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test_fraud.db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/1")
    monkeypatch.setenv("OPENAI_API_KEY", "fake-test-key")

    # 🧠 Patch config values used in production code
    monkeypatch.setattr(config, "IS_TEST", True, raising=False)
    monkeypatch.setattr(config, "LOG_LEVEL", "DEBUG", raising=False)
    monkeypatch.setattr(config, "REDIS_ENABLED", False, raising=False)
    monkeypatch.setattr(config, "ENABLE_EXTERNAL_APIS", False, raising=False)

    yield config

    # 🧹 Cleanup after each test
    for var in ["APP_ENV", "DATABASE_URL", "REDIS_URL", "OPENAI_API_KEY"]:
        monkeypatch.delenv(var, raising=False)


# =========================================================
# 🧠 Global Auto-Mocks for Heavy Components
# =========================================================
@pytest.fixture(autouse=True)
def mock_external_services(monkeypatch):
    """
    Prevents real API or network calls during tests.
    Automatically applied to all tests (autouse=True).
    """
    # Mock external API calls (weather, vendor, etc.)
    monkeypatch.setattr(
        "src.utils.external_apis.check_vendor_fraud",
        lambda claim: {"is_fraudulent": False, "risk_score": 0.1, "reason": "Mock vendor OK"},
        raising=False,
    )

    monkeypatch.setattr(
        "src.utils.external_apis.calculate_location_distance",
        lambda loc1, loc2: 50.0,
        raising=False,
    )

    monkeypatch.setattr(
        "src.utils.external_apis.check_weather_at_location",
        lambda loc: {"condition": "Clear", "is_rainy": False},
        raising=False,
    )

    # Mock ML/NLP model loading to avoid GPU/memory load
    monkeypatch.setattr("src.nlp.text_analyzer.load_nlp_models", lambda: True, raising=False)
    monkeypatch.setattr("src.nlp.text_analyzer.get_text_similarity", lambda t1, t2: 0.8, raising=False)

    # ✅ FIX: Correct mocking for RedisCache (class inside cache.py)
    from src.utils.cache import RedisCache
    monkeypatch.setattr(RedisCache, "get_client", lambda self: None, raising=False)

    # Mock DB engine to avoid DB connections
    monkeypatch.setattr("src.utils.db.engine", None, raising=False)

    yield


# =========================================================
# 🌐 FastAPI Test Client (for API tests)
# =========================================================
@pytest.fixture(scope="function")
def client(mock_test_config):
    """
    Provides a FastAPI test client for API integration tests.
    """
    from fastapi.testclient import TestClient
    from src.main import app
    return TestClient(app)
