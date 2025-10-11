from pydantic import BaseModel
from typing import List, Dict, Any

class FraudResponse(BaseModel):
    probability: float
    decision: str
    alarms: List[str]
    explanations: Dict[str, Any]
