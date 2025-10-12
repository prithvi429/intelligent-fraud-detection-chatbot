"""
Pydantic models for policy and guidance retrieval responses.
Supports GPT / Pinecone-based document guidance.
"""

from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


# =========================================================
# 📘 CORE GUIDANCE MODEL
# =========================================================
class PolicyGuidance(BaseModel):
    query: str = Field(..., description="User query (e.g., 'What documents are needed for a vehicle claim?')")
    response: str = Field(..., description="Generated or retrieved explanation from knowledge base or GPT.")
    required_docs: List[str] = Field(default_factory=list, description="List of documents required for the claim.")
    source: Optional[str] = Field(default="", description="Reference source (e.g., 'Policy Playbook v1').")

    model_config = ConfigDict(extra="ignore")


# =========================================================
# 📩 REQUEST MODEL
# =========================================================
class GuidanceRequest(BaseModel):
    query: str = Field(..., description="User's question related to policy or claim process.")

    model_config = ConfigDict(extra="ignore")


# =========================================================
# 📤 RESPONSE MODEL
# =========================================================
class GuidanceResponse(BaseModel):
    guidance: PolicyGuidance = Field(..., description="Detailed guidance response with policy info.")
    relevance_score: float = Field(..., ge=0.0, le=1.0, description="Semantic match confidence (0.0–1.0).")

    model_config = ConfigDict(extra="ignore")
