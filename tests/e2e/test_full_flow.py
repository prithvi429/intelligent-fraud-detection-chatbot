"""
E2E Tests: Full User Flow
-------------------------
Tests the complete fraud detection lifecycle:
Submit claim → Fraud scoring → Explanation → Guidance → Health.
"""

import pytest
from fastapi.testclient import TestClient
from src.models.fraud import Decision


class TestFullFlow:
    """E2E tests for full claim submission and fraud decisions."""

    @pytest.mark.usefixtures("mock_external_apis", "mock_nlp", "mock_ml_model", "override_get_db")
    def test_low_risk_claim_full_flow(self, test_app: TestClient, mock_ml_model):
        """Low-risk claim → APPROVE decision."""
        # Adjust mock ML to low prob (20%)
        mock_ml_model.predict_proba.return_value = [[0.8, 0.2]]

        payload = {
            "amount": 2000,
            "report_delay_days": 2,
            "provider": "Trusted Clinic",
            "notes": "Minor accident, normal claim.",
            "claimant_id": "low_user",
            "location": "New York, NY",
            "is_new_bank": False
        }

        res = test_app.post("/api/v1/score_claim", json=payload)
        assert res.status_code == 200

        data = res.json()
        assert data["decision"] == Decision.APPROVE.value
        assert data["fraud_probability"] < 30
        assert data["alarms"] == []
        assert "low risk" in data["explanation"].lower()

        # Check guidance works
        guide = test_app.post("/api/v1/guidance", json={"query": "What documents are required?"})
        assert guide.status_code == 200
        assert "document" in guide.json()["guidance"]["response"].lower()

    @pytest.mark.usefixtures("mock_external_apis", "mock_nlp", "mock_ml_model", "override_get_db")
    def test_medium_risk_claim_full_flow(self, test_app: TestClient, mock_ml_model):
        """Medium-risk claim → REVIEW decision."""
        mock_ml_model.predict_proba.return_value = [[0.5, 0.5]]

        payload = {
            "amount": 8000,
            "report_delay_days": 5,
            "provider": "Out-of-Network Hospital",
            "notes": "Some delay, but legitimate claim.",
            "claimant_id": "med_user",
            "location": "New York, NY",
            "is_new_bank": False
        }

        res = test_app.post("/api/v1/score_claim", json=payload)
        assert res.status_code == 200

        data = res.json()
        assert data["decision"] == Decision.REVIEW.value
        assert 30 <= data["fraud_probability"] <= 70
        assert 1 <= len(data["alarms"]) <= 4
        assert "review" in data["explanation"].lower()

        explain = test_app.get("/api/v1/explain/out_of_network_provider")
        assert explain.status_code in [200, 404]  # handle optional
        if explain.status_code == 200:
            assert "network" in explain.json()["description"].lower()

    @pytest.mark.usefixtures("mock_external_apis", "mock_nlp", "mock_ml_model", "override_get_db")
    def test_high_risk_claim_full_flow(self, test_app: TestClient, mock_ml_model):
        """High-risk claim → REJECT decision."""
        mock_ml_model.predict_proba.return_value = [[0.2, 0.8]]

        payload = {
            "amount": 15000,
            "report_delay_days": 10,
            "provider": "shady_clinic",
            "notes": "Staged accident for quick cash, exaggerated pain.",
            "claimant_id": "high_user",
            "location": "Los Angeles, CA",
            "is_new_bank": True
        }

        res = test_app.post("/api/v1/score_claim", json=payload)
        assert res.status_code == 200

        data = res.json()
        assert data["decision"] == Decision.REJECT.value
        assert data["fraud_probability"] > 70
        assert len(data["alarms"]) >= 4
        assert "high risk" in data["explanation"].lower()
        assert "rejected" in data["explanation"].lower()

        # Check explanation endpoint
        explain = test_app.get("/api/v1/explain/high_amount")
        assert explain.status_code == 200
        assert "exceed" in explain.json()["description"].lower()

    def test_invalid_claim_input(self, test_app: TestClient):
        """Invalid claim (negative amount) → 422 validation error."""
        payload = {
            "amount": -500,
            "report_delay_days": 3,
            "provider": "XYZ",
            "notes": "Test",
            "claimant_id": "invalid_user",
            "location": "NY"
        }

        res = test_app.post("/api/v1/score_claim", json=payload)
        assert res.status_code == 422
        detail = str(res.json()["detail"]).lower()
        assert "amount" in detail
        assert "positive" in detail

    def test_health_and_root_endpoints(self, test_app: TestClient):
        """Test health and root API endpoints."""
        root = test_app.get("/")
        assert root.status_code == 200
        data = root.json()
        assert "welcome" in data["message"].lower()
        assert data["fraud_types_detected"] >= 10
        assert isinstance(data["ml_enabled"], bool)

        health = test_app.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "healthy"

        me = test_app.get("/me")
        assert me.status_code == 200
        assert "user_id" in me.json()
