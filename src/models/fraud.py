"""
Fraud Models
------------
Defines data structures used for fraud detection, alarms, and responses.

✅ Compatible with Pydantic v2
✅ Imports cleanly for all API endpoints and ML tests
✅ Includes AlarmSeverity (fixes ImportError)
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


# =========================================================
# 🧩 ENUMS
# =========================================================
class Decision(str, Enum):
    """Fraud decision levels."""
    APPROVE = "Approve"
    REVIEW = "Review"
    REJECT = "Reject"


class AlarmSeverity(str, Enum):
    """Severity levels for fraud alarms."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# =========================================================
# 🚨 FRAUD ALARM MODEL
# =========================================================
class FraudAlarm(BaseModel):
    """Represents a single fraud alarm triggered during detection."""
    type: str = Field(..., description="Alarm type (e.g., 'high_amount', 'duplicate_claim')")
    description: str = Field(..., description="Explanation for the alarm trigger.")
    severity: AlarmSeverity = Field(AlarmSeverity.MEDIUM, description="Severity level of the alarm.")
    evidence: Optional[Dict[str, Any]] = Field(None, description="Supporting evidence details if available.")

    model_config = ConfigDict(extra="ignore")


# =========================================================
# 📊 FRAUD FEATURES MODEL
# =========================================================
class FraudFeatures(BaseModel):
    """Feature vector used for ML fraud prediction (14 standard features)."""
    amount_normalized: float = Field(0.0, description="Normalized claim amount ratio")
    delay_days: int = Field(0, description="Days delayed in reporting")
    is_new_bank: bool = Field(False, description="New bank account used")
    is_out_of_network: bool = Field(False, description="Out-of-network provider flag")
    num_alarms: int = Field(0, description="Number of alarms triggered")
    high_severity_count: int = Field(0, description="High severity alarm count")
    repeat_count: int = Field(0, description="Repeat claims by same claimant")
    text_similarity_score: float = Field(0.0, description="Similarity of text vs past claims")
    location_distance: float = Field(0.0, description="Distance from registered location")
    time_anomaly_score: float = Field(0.0, description="Temporal anomaly indicator")
    suspicious_keyword_count: int = Field(0, description="Count of suspicious terms in text")
    sentiment_score: float = Field(0.0, description="Sentiment polarity of claim notes")
    vendor_risk_score: float = Field(0.0, description="Vendor-level fraud risk score")
    external_mismatch_count: int = Field(0, description="External data mismatches")

    model_config = ConfigDict(extra="ignore")

    @property
    def values(self) -> List[float]:
        """Return all feature values as a list (for ML input arrays)."""
        return [
            self.amount_normalized,
            self.delay_days,
            int(self.is_new_bank),
            int(self.is_out_of_network),
            self.num_alarms,
            self.high_severity_count,
            self.repeat_count,
            self.text_similarity_score,
            self.location_distance,
            self.time_anomaly_score,
            self.suspicious_keyword_count,
            self.sentiment_score,
            self.vendor_risk_score,
            self.external_mismatch_count,
        ]


# =========================================================
# 🧠 FRAUD RESPONSE MODEL
# =========================================================
class FraudResponse(BaseModel):
    """Fraud scoring result returned from the API."""
    fraud_probability: float = Field(..., ge=0.0, le=1.0, description="Fraud score (0.0–1.0)")
    alarms: List[FraudAlarm] = Field(default_factory=list, description="Triggered fraud alarms")
    decision: Decision = Field(..., description="Final decision outcome")
    explanation: str = Field(..., description="Text explanation of the decision")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Decision timestamp")
    features_used: Optional[FraudFeatures] = Field(None, description="Optional feature data used for decision")

    model_config = ConfigDict(extra="ignore")


# =========================================================
# 📦 BATCH FRAUD RESPONSE MODEL
# =========================================================
class BatchFraudResponse(BaseModel):
    """Represents multiple fraud responses in batch processing."""
    results: List[FraudResponse] = Field(default_factory=list, description="List of fraud responses")
    summary: Dict[str, Any] = Field(default_factory=dict, description="Batch summary stats")

    model_config = ConfigDict(extra="ignore")


# =========================================================
# ✅ EXPLICIT EXPORTS
# =========================================================
__all__ = [
    "Decision",
    "AlarmSeverity",
    "FraudAlarm",
    "FraudFeatures",
    "FraudResponse",
    "BatchFraudResponse",
]


# =========================================================
# 🧪 LOCAL TEST (Optional)
# =========================================================
if __name__ == "__main__":
    alarm = FraudAlarm(
        type="high_amount",
        description="Claim exceeds threshold.",
        severity=AlarmSeverity.HIGH,
        evidence={"amount": 15000, "limit": 10000},
    )

    features = FraudFeatures(amount_normalized=0.8, delay_days=4, high_severity_count=1)
    response = FraudResponse(
        fraud_probability=0.85,
        alarms=[alarm],
        decision=Decision.REJECT,
        explanation="High severity alarms triggered rejection.",
        features_used=features,
    )

    print("✅ FraudResponse example:")
    print(response.model_dump_json(indent=2))
