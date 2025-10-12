"""
Fraud Detection Models:
=======================
Defines structured inputs, ML features, and fraud response schema
for the Insurance Fraud Detection Chatbot.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
import numpy as np
from pydantic import BaseModel, Field, field_validator, ConfigDict


# =========================================================
# 🧩 ENUMS — Decision & Alarm Severity
# =========================================================
class Decision(str, Enum):
    APPROVE = "Approve"  # Low risk
    REVIEW = "Review"    # Moderate risk
    REJECT = "Reject"    # High risk


class AlarmSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# =========================================================
# 🚨 FRAUD ALARM MODEL
# =========================================================
class FraudAlarm(BaseModel):
    type: str = Field(..., description="Alarm category (e.g., 'high_amount', 'duplicate_claim')")
    description: str = Field(..., description="Detailed explanation for user/chatbot")
    severity: AlarmSeverity = Field(AlarmSeverity.MEDIUM, description="Alarm risk level: low/medium/high")
    evidence: Optional[Dict[str, Any]] = Field(None, description="Supporting data (e.g., {'score': 0.85})")

    model_config = ConfigDict(extra="ignore")

    @field_validator("type")
    def validate_type(cls, v: str) -> str:
        """Ensure alarm type uses lowercase_with_underscores naming."""
        if not v or not isinstance(v, str):
            raise ValueError("Alarm type must be a descriptive string like 'high_amount'")
        return v.lower().replace(" ", "_")


# =========================================================
# 📊 FRAUD FEATURES (ML Input)
# =========================================================
class FraudFeatures(BaseModel):
    # Structured fields
    amount_normalized: float = Field(..., ge=0, description="Claim amount normalized to policy average")
    delay_days: int = Field(0, ge=0, description="Days delay in reporting claim")
    is_new_bank: bool = Field(False, description="New bank account indicator")
    is_out_of_network: bool = Field(False, description="Provider out-of-network flag")

    # Derived metrics
    num_alarms: int = Field(0, ge=0)
    high_severity_count: int = Field(0, ge=0)
    repeat_count: int = Field(0, ge=0)
    text_similarity_score: float = Field(0.0, ge=0, le=1)
    location_distance: float = Field(0.0, ge=0)
    time_anomaly_score: float = Field(0.0, ge=0, le=1)

    # NLP features
    suspicious_keyword_count: int = Field(0, ge=0)
    sentiment_score: float = Field(0.0, ge=-1, le=1)

    # External
    vendor_risk_score: float = Field(0.0, ge=0, le=1)
    external_mismatch_count: int = Field(0, ge=0)

    model_config = ConfigDict(extra="ignore")

    def to_array(self) -> np.ndarray:
        """Convert structured data into numpy array for ML models."""
        return np.array([
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
        ], dtype=np.float32)


# =========================================================
# 🧠 FRAUD RESPONSE MODEL (Main Output)
# =========================================================
class FraudResponse(BaseModel):
    fraud_probability: float = Field(..., ge=0.0, le=1.0, description="Predicted fraud probability (0.0–1.0)")
    alarms: List[FraudAlarm] = Field(default_factory=list, description="Triggered fraud alarms")
    decision: Decision = Field(..., description="Final decision (Approve / Review / Reject)")
    explanation: str = Field(..., description="Summary reasoning for decision")
    features_used: Optional[FraudFeatures] = Field(None, description="Input features for transparency")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Time of model scoring (UTC)")
    recommendation: Optional[str] = Field(None, description="Suggested next step for reviewer/user")

    model_config = ConfigDict(extra="ignore")

    # Validators
    @field_validator("fraud_probability")
    def validate_probability(cls, v: float) -> float:
        """Ensure fraud probability is between 0 and 1."""
        if not 0 <= v <= 1:
            raise ValueError("Fraud probability must be between 0.0 and 1.0")
        return round(v, 3)

    # Helper properties
    @property
    def risk_level(self) -> str:
        """Returns simple string risk level."""
        if v := self.fraud_probability > 0.7:
            return "high"
        elif v > 0.3:
            return "medium"
        return "low"

    @property
    def is_high_risk(self) -> bool:
        return self.decision == Decision.REJECT or self.fraud_probability > 0.7

    @property
    def total_alarms(self) -> int:
        return len(self.alarms)

    @property
    def high_severity_alarms(self) -> List[FraudAlarm]:
        return [a for a in self.alarms if a.severity == AlarmSeverity.HIGH]


# =========================================================
# 📦 BATCH FRAUD RESPONSE
# =========================================================
class BatchFraudResponse(BaseModel):
    claims: List[Dict[str, Any]] = Field(..., description="Input claim data or IDs")
    results: List[FraudResponse] = Field(..., description="Individual fraud scoring results")
    summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Aggregate results, e.g., {'avg_prob': 0.45, 'total_rejects': 2}",
    )

    model_config = ConfigDict(extra="ignore")


# =========================================================
# 🧪 TEST EXAMPLE
# =========================================================
if __name__ == "__main__":
    alarm = FraudAlarm(
        type="high_amount",
        description="Claim exceeds $10,000 threshold for this policy type.",
        severity=AlarmSeverity.HIGH,
        evidence={"threshold": 10000, "amount": 15000}
    )

    features = FraudFeatures(amount_normalized=3.5, delay_days=10, num_alarms=2, text_similarity_score=0.85)

    response = FraudResponse(
        fraud_probability=0.82,
        alarms=[alarm],
        decision=Decision.REJECT,
        explanation="High claim amount and delay indicate strong fraud likelihood.",
        features_used=features
    )

    print("✅ Response:", response.model_dump_json(indent=2))
    print("🚨 High risk?", response.is_high_risk)
