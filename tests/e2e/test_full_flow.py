"""
Pytest Configuration File
-------------------------
Defines global test fixtures and mock setup for the Intelligent Fraud Detection Chatbot.

Features:
- Safe environment + config isolation
- Mocked Redis/DB/API/NLP/ML dependencies
- Compatible with all E2E, integration, and unit tests
"""

import os
import pytest
from unittest.mock import MagicMock
from src.config import config


# =========================================================
# 🧩 Test Config Fixture
# =========================================================
@pytest.fixture(scope="function")
def mock_test_config(monkeypatch):
    """
    Mocks environment variables and config values for each test.
    Function-scoped for isolation.
    """
    # 🔐 Environment mock
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test_fraud.db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/1")
    monkeypatch.setenv("OPENAI_API_KEY", "fake-test-key")

    # 🧠 Patch config attributes
    monkeypatch.setattr(config, "IS_TEST", True, raising=False)
    monkeypatch.setattr(config, "LOG_LEVEL", "DEBUG", raising=False)
    monkeypatch.setattr(config, "REDIS_ENABLED", False, raising=False)
    monkeypatch.setattr(config, "ENABLE_EXTERNAL_APIS", False, raising=False)

    yield config

    # 🧹 Cleanup
    for var in ["APP_ENV", "DATABASE_URL", "REDIS_URL", "OPENAI_API_KEY"]:
        monkeypatch.delenv(var, raising=False)


# =========================================================
# 🌐 Auto-Mock External Services (applied globally)
# =========================================================
@pytest.fixture(autouse=True)
def mock_external_services(monkeypatch):
    """
    Prevents real API or network calls during tests.
    Automatically applied to all tests (autouse=True).
    """

    # ✅ External APIs
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

    # ✅ NLP mocks
    monkeypatch.setattr("src.nlp.text_analyzer.load_nlp_models", lambda: True, raising=False)
    monkeypatch.setattr("src.nlp.text_analyzer.get_text_similarity", lambda t1, t2: 0.8, raising=False)

    # ✅ Redis mock (avoid real connection)
    from src.utils.cache import RedisCache
    monkeypatch.setattr(RedisCache, "get_client", lambda self: None, raising=False)

    # ✅ DB mock (prevent connection to SQLite or AWS)
    monkeypatch.setattr("src.utils.db.engine", None, raising=False)

    yield


# =========================================================
# ⚡ FastAPI Test Client
# =========================================================
@pytest.fixture(scope="function")
def client(mock_test_config):
    """Provides a FastAPI test client for integration and E2E tests."""
    from fastapi.testclient import TestClient
    from src.main import app
    return TestClient(app)


# =========================================================
# 🧩 Compatibility Fixtures (expected by older tests)
# =========================================================

@pytest.fixture(name="mock_external_apis", autouse=False)
def mock_external_apis_fixture(mock_external_services):
    """Alias for backward compatibility with older test names."""
    return mock_external_services


@pytest.fixture(name="mock_nlp", autouse=False)
def mock_nlp_fixture(monkeypatch):
    """Mocks NLP analyzer and text extraction."""
    monkeypatch.setattr(
        "src.nlp.text_analyzer.analyze_text",
        lambda text: {"summary": "Mock summary", "risk": "low"},
        raising=False,
    )
    monkeypatch.setattr(
        "src.nlp.text_analyzer.extract_entities",
        lambda text: {"amount": 1000, "provider": "Mock Hospital"},
        raising=False,
    )
    return True


@pytest.fixture(name="mock_ml_model", autouse=False)
def mock_ml_model_fixture(mocker):
    """Mocks ML model prediction for fraud detection."""
    mock_model = mocker.MagicMock()
    mock_model.predict_proba.return_value = [[0.5, 0.5]]
    return mock_model


@pytest.fixture(name="override_get_db", autouse=False)
def override_get_db_fixture(monkeypatch):
    """Mocks the DB session dependency in FastAPI routes."""
    from sqlalchemy.orm import Session

    class DummySession(Session):
        def __init__(self):
            pass

    monkeypatch.setattr("src.utils.db.get_db", lambda: DummySession())
    return DummySession()
