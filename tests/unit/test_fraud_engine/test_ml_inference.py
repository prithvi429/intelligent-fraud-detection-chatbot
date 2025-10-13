"""
Unit Tests: ML Inference (Fraud Probability)
--------------------------------------------
Validates model loading, feature extraction, and inference behavior.
"""

import numpy as np
import pytest
from unittest.mock import patch, MagicMock

from src.fraud_engine.ml_inference import (
    load_fraud_model,
    extract_features,
    get_fraud_probability,
    train_synthetic_model,
    _fallback_prob,
)
from src.models.claim import ClaimData
from src.models.fraud import FraudFeatures


# =========================================================
# 🔧 Fixtures
# =========================================================
@pytest.fixture
def sample_claim():
    """Provide a mock claim for testing."""
    return ClaimData(
        amount=15000,
        provider="shady_clinic",
        notes="Quick cash claim with fake injury",
        location="Los Angeles, CA",
        claimant_id="user_test",
        report_delay_days=10,
        is_new_bank=True,
    )


@pytest.fixture
def sample_alarms():
    """Mock alarm list for tests."""
    return [
        "High claim amount",
        "Vendor fraud: Provider risk 0.85",
        "Time pattern fraud",
    ]


# =========================================================
# 🧠 Model Load Tests
# =========================================================
def test_model_load_missing(tmp_path):
    """Should gracefully handle missing model file."""
    model_path = tmp_path / "missing_model.pkl"
    result = load_fraud_model(str(model_path))
    assert result is False


def test_model_load_success(tmp_path):
    """Should load a saved synthetic model successfully."""
    model_path = tmp_path / "fraud_model.pkl"
    train_synthetic_model(str(model_path))
    assert load_fraud_model(str(model_path)) is True


# =========================================================
# 🧩 Feature Extraction Tests
# =========================================================
def test_feature_extraction_valid(sample_claim, sample_alarms):
    """Ensure extracted features have correct size and numeric type."""
    features = extract_features(sample_claim, sample_alarms)
    assert isinstance(features, FraudFeatures)
    assert len(features.values) == 14
    assert all(isinstance(v, (int, float)) for v in features.values)


def test_feature_extraction_fallback(monkeypatch):
    """Simulate error inside extract_features → should return zeros."""
    from src.fraud_engine import ml_inference

    def broken_analyze_text(_):
        raise ValueError("Simulated NLP error")

    monkeypatch.setattr(ml_inference, "analyze_text", broken_analyze_text)
    claim = ClaimData(amount=1000, claimant_id="bad_user")
    result = ml_inference.extract_features(claim, [])
    assert all(v == 0.0 for v in result.values)


# =========================================================
# 🔮 Inference Tests
# =========================================================
def test_fallback_probability(sample_alarms):
    """Fallback mode should return 10% per alarm, max 100."""
    prob = _fallback_prob(sample_alarms)
    assert 0 < prob <= 100


def test_model_inference_with_mock(sample_claim, sample_alarms):
    """Predict probability with a mocked model."""
    with patch("src.fraud_engine.ml_inference.model") as mock_model:
        mock_model.predict_proba.return_value = np.array([[0.25, 0.75]])
        from src.fraud_engine import ml_inference
        ml_inference.is_model_loaded = True
        prob = get_fraud_probability(np.array([[1, 2, 3]]), sample_alarms)
        assert round(prob, 1) == 75.0


def test_inference_fallback_on_error(monkeypatch, sample_alarms):
    """If model inference fails, should fallback."""
    from src.fraud_engine import ml_inference

    def broken_predict(*a, **k):
        raise RuntimeError("Model failure")

    ml_inference.model = MagicMock(predict_proba=broken_predict)
    ml_inference.is_model_loaded = True
    prob = ml_inference.get_fraud_probability(np.array([[1, 2, 3]]), sample_alarms)
    assert prob > 0


# =========================================================
# 🧪 Synthetic Model Smoke Test
# =========================================================
def test_train_synthetic_model(tmp_path):
    """Train synthetic model and validate file creation."""
    model_path = tmp_path / "fraud_model.pkl"
    train_synthetic_model(str(model_path))
    assert model_path.exists()
