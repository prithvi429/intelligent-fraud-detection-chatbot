"""
Pytest Configuration & Fixtures
-------------------------------
Centralized setup for integration/unit tests:
- TestClient (FastAPI app)
- Mocked database session (SQLAlchemy)
- Mocked ML model & external APIs
- Patch management for consistent behavior
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.main import app
from src.utils.db import Base, get_db
from src.fraud_engine.ml_inference import FraudModel
from src.config import config


# =========================================================
# 🧱 Database Fixtures (SQLite In-Memory)
# =========================================================
@pytest.fixture(scope="session")
def test_engine():
    """Create a temporary in-memory SQLite DB for testing."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def test_db(test_engine):
    """Provide a new transactional DB session for each test."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def override_get_db(test_db):
    """Override dependency: injects test DB instead of production."""
    def _get_test_db():
        try:
            yield test_db
        finally:
            test_db.close()
    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.clear()


# =========================================================
# 🧠 Mock ML Model (SageMaker / Local)
# =========================================================
@pytest.fixture(scope="function")
def mock_ml_model(monkeypatch):
    """Mock the FraudModel used in inference."""
    mock_model = MagicMock(spec=FraudModel)
    mock_model.predict_proba.return_value = [[0.3, 0.7]]  # Default 70% fraud
    mock_model.is_loaded = True

    monkeypatch.setattr("src.fraud_engine.ml_inference.model", mock_model)
    monkeypatch.setattr("src.fraud_engine.ml_inference.is_model_loaded", lambda: True)
    yield mock_model


# =========================================================
# 🔗 Mock External APIs (Weather, Vendor, Pinecone)
# =========================================================
@pytest.fixture(scope="function")
def mock_external_apis(monkeypatch):
    """Mock all external API calls (weather, vendor, Pinecone)."""

    # Weather API mock
    monkeypatch.setattr("src.fraud_engine.external.weather_api.get_weather_condition", lambda *a, **k: "Clear")

    # Vendor fraud API mock
    monkeypatch.setattr("src.fraud_engine.external.vendor_api.get_vendor_risk", lambda *a, **k: 0.2)

    # Pinecone mock
    monkeypatch.setattr("src.chatbot.tools.retrieve_guidance.retrieve_from_pinecone",
                        lambda q, *a, **k: {"response": "Please submit ID and invoice.", "required_docs": ["ID", "Invoice"]})

    # OpenAI / LLM mock (used in guidance)
    monkeypatch.setattr("src.chatbot.tools.llm.ask_openai", lambda q, *a, **k: f"Mock LLM reply for: {q}")

    yield


# =========================================================
# 🧩 Mock NLP (spaCy, sentence-transformers)
# =========================================================
@pytest.fixture(scope="function")
def mock_nlp(monkeypatch):
    """Mock NLP-based components (keyword extraction, similarity)."""

    # Mock text similarity
    monkeypatch.setattr("src.fraud_engine.text_utils.get_similarity_score", lambda a, b: 0.1)

    # Mock keyword matcher
    monkeypatch.setattr("src.fraud_engine.text_utils.extract_suspicious_phrases",
                        lambda text: ["staged", "quick cash"] if "staged" in text else [])

    yield


# =========================================================
# 🧰 Test Client Fixture
# =========================================================
@pytest.fixture(scope="session")
def test_app():
    """Global FastAPI TestClient with full middleware."""
    client = TestClient(app)
    yield client


# =========================================================
# 🚫 Disable External Network Calls in Tests
# =========================================================
@pytest.fixture(autouse=True)
def disable_network(monkeypatch):
    """Prevent any real HTTP requests during tests (safety net)."""
    import requests

    def blocked(*args, **kwargs):
        raise RuntimeError("❌ External network calls are disabled during tests.")

    monkeypatch.setattr(requests, "get", blocked)
    monkeypatch.setattr(requests, "post", blocked)
    yield


# =========================================================
# 🧩 Mock Config (For Consistency)
# =========================================================
@pytest.fixture(scope="session", autouse=True)
def mock_test_config(monkeypatch):
    """Force test-safe config settings."""
    monkeypatch.setattr(config, "DEBUG", True)
    monkeypatch.setattr(config, "is_ml_enabled", True)
    monkeypatch.setattr(config, "is_pinecone_enabled", False)
    monkeypatch.setattr(config, "API_HOST", "127.0.0.1")
    monkeypatch.setattr(config, "API_PORT", 8000)
    yield
