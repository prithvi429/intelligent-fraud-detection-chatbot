"""
/guidance Endpoint
------------------
Retrieves insurance policy guidance and procedural help for users.
Supports semantic (Pinecone), DB, and static fallback logic.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

from src.models.policy import GuidanceRequest, GuidanceResponse, PolicyGuidance
from src.api.dependencies import get_db_session, authenticated_user
from src.chatbot.tools.retrieve_guidance import get_guidance_from_pinecone_or_db  # Semantic search tool
from src.utils.logger import logger
from src.config import config
from src.utils.db import get_policy_from_db  # Optional DB query function

router = APIRouter(tags=["Policy Guidance"])

# =========================================================
# 🧾 Static fallback guidance (playbook-style responses)
# =========================================================
STATIC_GUIDANCE = [
    PolicyGuidance(
        query="What documents are needed?",
        response=(
            "For most insurance claims, you’ll need: a valid ID, original invoice or receipt, "
            "a medical or incident report, and any witness statements. Upload clear copies."
        ),
        required_docs=["Government ID", "Original invoice", "Medical/incident report", "Witness statement (if applicable)"],
        source="Policy Playbook v1.0",
    ),
    PolicyGuidance(
        query="Why was my claim rejected?",
        response=(
            "Claims are rejected when the fraud risk score exceeds 70%, often due to late reporting, "
            "unusual claim amount, or suspicious text patterns. You can appeal with more documents."
        ),
        required_docs=["Appeal form", "Supporting proof (timeline, receipts)"],
        source="Fraud Policy v1.0",
    ),
    PolicyGuidance(
        query="How do I appeal a rejected claim?",
        response=(
            "Submit an appeal through the portal or via email to support@insurance.com. "
            "Include the claim ID, your reasoning, and any new documents. Appeals are reviewed within 7–10 business days."
        ),
        required_docs=["Appeal form", "Claim ID", "New evidence"],
        source="Appeal Process v1.0",
    ),
    PolicyGuidance(
        query="What if I used an out-of-network provider?",
        response=(
            "Out-of-network claims are covered at 70% but may trigger review. "
            "Provide justification (e.g., emergency) and receipts for validation."
        ),
        required_docs=["Justification letter", "Receipts", "Provider details"],
        source="Provider Policy v1.0",
    ),
    PolicyGuidance(
        query="How to avoid location mismatch flags?",
        response=(
            "Ensure your claim address matches your registered policy location, "
            "or provide travel proof if the distance exceeds 100 miles."
        ),
        required_docs=["Travel receipts", "GPS or map evidence"],
        source="Location Policy v1.0",
    ),
]


# =========================================================
# 🎯 POST /guidance – Retrieve policy guidance
# =========================================================
@router.post(
    "/guidance",
    response_model=GuidanceResponse,
    summary="Retrieve policy or procedural guidance",
    description="Answers user questions using Pinecone, database, or static fallback."
)
async def get_policy_guidance_endpoint(
    request: GuidanceRequest,
    db: Session = Depends(get_db_session),
    user: dict = Depends(authenticated_user),
):
    """
    Retrieve insurance policy or fraud-related guidance.
    - Uses Pinecone for semantic similarity if available.
    - Falls back to database keyword match or static knowledge base.
    """
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Query cannot be empty.")

    logger.info(f"🧠 Guidance query from {user.get('user_id', 'anonymous')}: '{query}'")

    try:
        # =========================================================
        # Step 1️⃣ – Semantic (Pinecone) retrieval
        # =========================================================
        if config.is_pinecone_enabled:
            guidance, relevance_score = get_guidance_from_pinecone_or_db(query, db, use_pinecone=True)
            if guidance and relevance_score > 0.5:
                logger.debug(f"🔍 Pinecone relevance: {relevance_score:.2f}")
                return GuidanceResponse(guidance=guidance, relevance_score=relevance_score)

        # =========================================================
        # Step 2️⃣ – Database fallback (simple keyword match)
        # =========================================================
        db_guidance = get_policy_from_db(query, db)
        if db_guidance:
            match_words = sum(1 for word in query.lower().split() if word in db_guidance.query.lower())
            relevance_score = round(min(1.0, match_words / max(1, len(query.split()))), 2)
            logger.debug(f"🗂 DB relevance: {relevance_score:.2f}")
            return GuidanceResponse(guidance=db_guidance, relevance_score=relevance_score)

        # =========================================================
        # Step 3️⃣ – Static fallback (keyword overlap)
        # =========================================================
        best_match = max(
            STATIC_GUIDANCE,
            key=lambda g: sum(
                1 for w in query.lower().split() if w in g.query.lower() or w in g.response.lower()
            ),
            default=STATIC_GUIDANCE[0],
        )

        overlap = sum(
            1 for w in query.lower().split() if w in best_match.query.lower() or w in best_match.response.lower()
        )
        relevance_score = round(min(1.0, overlap / max(1, len(query.split()))), 2)

        logger.info(f"📘 Static fallback used – Matched '{best_match.query}' (score: {relevance_score:.2f})")

        return GuidanceResponse(guidance=best_match, relevance_score=relevance_score)

    except Exception as e:
        logger.exception(f"❌ Error while processing guidance query '{query}': {e}")

        fallback = PolicyGuidance(
            query=query,
            response="Sorry, I couldn’t find a relevant policy. Please contact support@insurance.com.",
            required_docs=["Contact support"],
            source="Fallback",
        )
        return GuidanceResponse(guidance=fallback, relevance_score=0.3)


# =========================================================
# 🧾 GET /guidance/topics – List all known guidance topics
# =========================================================
@router.get(
    "/guidance/topics",
    summary="List available policy guidance topics",
    description="Returns a list of predefined guidance topics for chatbot or frontend discovery."
)
async def list_guidance_topics(user: dict = Depends(authenticated_user)):
    topics = [{"topic": g.query, "description": g.response[:100] + "..."} for g in STATIC_GUIDANCE]
    logger.info(f"📚 Guidance topics requested by {user.get('user_id', 'anonymous')}")
    return {"topics": topics, "total": len(topics)}
