"""
Claim Models
------------
Defines input and response schemas for insurance claim processing.
Compatible with Pydantic v2 and FastAPI 0.104+.
"""

from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


# =========================================================
# 🧩 ENUMS
# =========================================================
class Decision(str, Enum):
    """Fraud decision levels for claims."""
    APPROVE = "APPROVE"
    REVIEW = "REVIEW"
    REJECT = "REJECT"


class AlarmSeverity(str, Enum):
    """Alarm severity levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


# =========================================================
# 🚨 FRAUD ALARM MODEL
# =========================================================
class FraudAlarm(BaseModel):
    """Represents a triggered fraud alarm for a given claim."""
    type: str = Field(..., description="Alarm type (e.g., 'high_amount', 'duplicate_claim')")
    description: str = Field(..., description="Reason this alarm was triggered.")
    severity: AlarmSeverity = Field(default=AlarmSeverity.MEDIUM, description="LOW / MEDIUM / HIGH")

    model_config = ConfigDict(extra="ignore")


# =========================================================
# 📄 CLAIM INPUT MODEL
# =========================================================
class ClaimData(BaseModel):
    """Incoming claim data schema (used in /score_claim endpoint)."""
    claimant_id: str = Field(..., description="Unique claimant identifier (e.g., ID, email, or policy number)")
    amount: float = Field(..., gt=0, description="Claim amount in USD")
    report_delay_days: int = Field(default=0, ge=0, description="Days delayed in reporting claim")
    provider: Optional[str] = Field(default="", description="Insurance provider or vendor name")
    notes: Optional[str] = Field(default="", description="Free-text claim notes or explanation")
    location: Optional[str] = Field(default="", description="Incident location (city, address, or coordinates)")
    is_new_bank: bool = Field(default=False, description="Indicates if a new bank account was used")
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Claim submission timestamp (UTC)")

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "example": {
                "claimant_id": "api_test_user",
                "amount": 15000.0,
                "provider": "shady_clinic",
                "notes": "Staged accident quick cash",
                "location": "Los Angeles, CA",
                "report_delay_days": 10,
                "is_new_bank": True
            }
        },
    )


# =========================================================
# 🧠 FRAUD RESPONSE MODEL
# =========================================================
class FraudResponse(BaseModel):
    """Output structure returned by the fraud engine."""
    fraud_probability: float = Field(..., ge=0.0, le=1.0, description="Fraud probability (0.0–1.0)")
    alarms: List[FraudAlarm] = Field(default_factory=list, description="List of triggered fraud alarms")
    decision: Decision = Field(..., description="Final fraud decision: APPROVE / REVIEW / REJECT")
    explanation: str = Field(..., description="Human-readable explanation of the decision")

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "example": {
                "fraud_probability": 0.85,
                "decision": "REJECT",
                "explanation": "High-risk claim detected due to duplicate claimant and large amount.",
                "alarms": [
                    {
                        "type": "duplicate_claim",
                        "description": "Claimant filed another claim in past 30 days.",
                        "severity": "HIGH",
                    }
                ],
            }
        },
    )
