from pydantic import BaseModel
from typing import List

class PolicyGuidance(BaseModel):
    policy_name: str
    required_docs: List[str]
