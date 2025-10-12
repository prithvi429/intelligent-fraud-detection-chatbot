"""
Pydantic data models for claim input and fraud response output.
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
    APPROVE = "Approve"
    REVIEW = "Review"
    REJECT = "Reject"


# =========================================================
# 🚨 FRAUD ALARM MODEL
# =========================================================
class FraudAlarm(BaseModel):
    type: str = Field(..., description="Alarm type (e.g., 'high_amount', 'duplicate_claim')")
    description: str = Field(..., description="Human-readable explanation for the flag")
    severity: str = Field("medium", description="Alarm severity: low, medium, or high")

    model_config = ConfigDict(extra="ignore")  # Ignore extra fields gracefully


# =========================================================
# 📄 CLAIM INPUT MODEL
# =========================================================
class ClaimData(BaseModel):
    amount: float = Field(..., ge=0, description="Claim amount in USD")
    report_delay_days: int = Field(0, ge=0, description="Days delayed in reporting claim")
    provider: str = Field(..., description="Insurance provider/vendor name")
    notes: str = Field("", description="Unstructured claim notes or invoice text")
    claimant_id: str = Field(..., description="Unique claimant identifier (e.g., email or ID)")
    location: Optional[str] = Field("", description="Incident location (city, address, or lat/long)")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Claim submission time (UTC)")
    is_new_bank: bool = Field(False, description="Indicates if a new bank account was recently used")

    model_config = ConfigDict(extra="ignore")


# =========================================================
# 🧠 FRAUD RESPONSE MODEL
# =========================================================
class FraudResponse(BaseModel):
    fraud_probability: float = Field(..., ge=0.0, le=1.0, description="Fraud score as probability (0.0–1.0)")
    alarms: List[FraudAlarm] = Field(default_factory=list, description="List of triggered fraud alarms")
    decision: Decision = Field(..., description="Final fraud decision: Approve / Review / Reject")
    explanation: str = Field(..., description="Plain language explanation of fraud decision")

    model_config = ConfigDict(extra="ignore")
