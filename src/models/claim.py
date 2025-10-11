from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ClaimData(BaseModel):
    claimant_id: str
    amount: float
    provider: Optional[str] = None
    notes: Optional[str] = None
    location: Optional[str] = None
    timestamp: Optional[datetime] = None
    delay_days: Optional[int] = None
