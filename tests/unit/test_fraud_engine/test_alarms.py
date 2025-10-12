"""
Unit Tests: Fraud Alarms
------------------------
Covers src/fraud_engine/alarms.py and individual check modules.
Validates:
- Alarm detection logic (all 13 rules)
- NLP and external API mocks
- DB query handling (repeat claimant, blacklist)
Run:
    pytest tests/unit/test_alarms.py -v
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime as dt
from sqlalchemy.orm import Session
from src.models.claim import ClaimData
from src.fraud_engine.alarms import check_all_alarms, SUSPICIOUS_PHRASES
from src.fraud_engine.checks.high_amount_check import check_high_amount
from src.fraud_engine.checks.repeat_claimant_check import check_repeat_claimant
from src.fraud_engine.checks.suspicious_keywords_check import check_suspicious_keywords
from src.fraud_engine.checks.location_mismatch_check import check_location_mismatch
from src.fraud_engine.checks.duplicate_claims_check import check_duplicate_claims
from src.fraud_engine.checks.vendor_fraud_check import check_vendor_fraud
from src.fraud_engine.checks.time_pattern_fraud_check import check_time_patterns
from src.fraud_engine.checks.external_mismatch_check import check_external_mismatch


# =========================================================
# 🧪 Sample Claims
# =========================================================
LOW_RISK_CLAIM = ClaimData(
    amount=2000,
    report_delay_days=2,
    provider="Trusted Clinic",
    notes="Normal minor claim.",
    claimant_id="low_user",
    location="New York, NY",
    timestamp=dt(2024, 5, 1, 12, 0),
    is_new_bank=False
)

HIGH_RISK_CLAIM = ClaimData(
    amount=15000,
    report_delay_days=10,
    provider="shady_clinic",
    notes="Staged quick cash accident.",
    claimant_id="high_user",
    location="Los Angeles, CA",
    timestamp=dt(2024, 1, 1, 3, 0),  # Unusual hour (3 AM)
    is_new_bank=True
)


# =========================================================
# 🔎 Alarm Engine Tests
# =========================================================
class TestAlarms:
    """Unit tests for alarms.py and all check modules."""

    def test_check_all_alarms_low_risk_no_db(self):
        """Low-risk claim → no alarms, no DB connection."""
        alarms = check_all_alarms(LOW_RISK_CLAIM, db=None)
        assert isinstance(alarms, list)
        assert len(alarms) == 0

    @patch("src.fraud_engine.alarms.analyze_text")
    @patch("src.utils.db.get_blacklist_providers", return_value=[])
    def test_check_all_alarms_high_risk_no_db(self, mock_blacklist, mock_analyze):
        """High-risk claim → multiple alarms (>8) even without DB."""
        mock_analyze.return_value = {
            "suspicious_phrases": ["staged", "quick cash"],
            "keyword_count": 2,
            "max_similarity": 0.85,
            "is_suspicious": True
        }

        with patch("src.utils.external_apis.calculate_location_distance", return_value=200.0), \
             patch("src.utils.external_apis.check_vendor_fraud", return_value={
                 "is_fraudulent": True, "risk_score": 0.9, "reason": "Blacklisted"
             }), \
             patch("src.utils.external_apis.check_weather_at_location", return_value={
                 "condition": "Clear", "is_rainy": False
             }):

            alarms = check_all_alarms(HIGH_RISK_CLAIM, db=None)

        assert isinstance(alarms, list)
        assert len(alarms) >= 8  # high_amount, delay, new_bank, vendor, etc.
        joined = " ".join(alarms).lower()
        for keyword in [
            "late reporting", "new bank", "blacklist", "suspicious",
            "high claim amount", "location mismatch", "vendor", "time pattern"
        ]:
            assert keyword in joined

    def test_check_all_alarms_with_db(self):
        """Test repeat claimant + blacklist DB queries."""
        mock_db = Mock(spec=Session)
        mock_db.execute.return_value.fetchone.return_value = (3,)  # Repeat count
        with patch("src.utils.db.get_blacklist_providers", return_value=["shady_clinic"]):
            alarms = check_all_alarms(HIGH_RISK_CLAIM, db=mock_db)
        joined = " ".join(alarms).lower()
        assert "repeat claimant" in joined
        assert "blacklist" in joined

    # =====================================================
    # Individual Check Modules
    # =====================================================
    def test_high_amount_check(self):
        alarms = check_high_amount(HIGH_RISK_CLAIM)
        assert len(alarms) == 1
        assert "high claim amount" in alarms[0].lower()

        low_alarms = check_high_amount(LOW_RISK_CLAIM)
        assert len(low_alarms) == 0

    @patch("src.fraud_engine.checks.repeat_claimant_check.db")
    def test_repeat_claimant_check(self, mock_db):
        """Repeat > threshold triggers alarm."""
        mock_db.execute.return_value.fetchone.return_value = (3,)
        alarms = check_repeat_claimant(HIGH_RISK_CLAIM, db=mock_db)
        assert len(alarms) == 1
        assert "repeat claimant" in alarms[0].lower()

    @patch("src.nlp.text_analyzer.analyze_text")
    def test_suspicious_keywords_check(self, mock_analyze):
        mock_analyze.return_value = {"keyword_count": 2, "suspicious_phrases": ["staged"]}
        alarms = check_suspicious_keywords(HIGH_RISK_CLAIM)
        assert len(alarms) == 1
        assert "suspicious keywords" in alarms[0].lower()

    @patch("src.utils.external_apis.calculate_location_distance", return_value=200.0)
    def test_location_mismatch_check(self, mock_distance):
        alarms = check_location_mismatch(HIGH_RISK_CLAIM)
        assert len(alarms) == 1
        assert "location mismatch" in alarms[0].lower()

    @patch("src.nlp.text_analyzer.get_text_similarity", return_value=0.9)
    @patch("src.fraud_engine.checks.duplicate_claims_check.db")
    def test_duplicate_claims_check(self, mock_db, mock_sim):
        mock_db.execute.return_value.fetchall.return_value = [("previous note",)]
        alarms = check_duplicate_claims(HIGH_RISK_CLAIM, db=mock_db)
        assert len(alarms) == 1
        assert "duplicate claims" in alarms[0].lower()

    @patch("src.utils.external_apis.check_vendor_fraud")
    def test_vendor_fraud_check(self, mock_vendor):
        mock_vendor.return_value = {"is_fraudulent": True, "risk_score": 0.9}
        alarms = check_vendor_fraud(HIGH_RISK_CLAIM)
        assert len(alarms) == 1
        assert "vendor fraud" in alarms[0].lower()

    def test_time_pattern_check(self):
        alarms = check_time_patterns(HIGH_RISK_CLAIM)
        assert len(alarms) == 1
        assert "time pattern" in alarms[0].lower()

        # Safe hour (no alarm)
        claim_daytime = ClaimData(
            **{**HIGH_RISK_CLAIM.dict(), "timestamp": dt(2024, 1, 1, 12, 0)}
        )
        low_alarms = check_time_patterns(claim_daytime)
        assert len(low_alarms) == 0

    @patch("src.utils.external_apis.check_weather_at_location")
    def test_external_mismatch_check(self, mock_weather):
        mock_weather.return_value = {"condition": "Clear", "is_rainy": False}
        alarms = check_external_mismatch(HIGH_RISK_CLAIM)
        assert len(alarms) == 1
        assert "external mismatch" in alarms[0].lower()

    def test_suspicious_phrases_constant(self):
        assert isinstance(SUSPICIOUS_PHRASES, list)
        assert "staged" in SUSPICIOUS_PHRASES
        assert len(SUSPICIOUS_PHRASES) > 5
