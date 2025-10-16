"""
Chatbot API Endpoint
--------------------
Provides a unified conversational interface for the
Intelligent Fraud Detection Chatbot.

Features:
- Understands user intent (fraud check vs. guidance)
- Routes queries to either the fraud scoring engine or the guidance system
- Returns structured chatbot-style JSON responses
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import ORJSONResponse

from src.services.fraud_engine import score_claim
from src.services.guidance import get_guidance_response
from src.nlp.text_analyzer import analyze_text
from src.utils.logger import logger


# =========================================================
# 🚀 Router Initialization
# =========================================================
router = APIRouter(prefix="/api/v1", tags=["Chatbot Interface"])


# =========================================================
# 🧠 Chatbot Endpoint
# =========================================================
@router.post("/chatbot")
async def chatbot_api(payload: dict):
    """
    Unified chatbot endpoint.

    Expects:
    {
      "query": "User message",
      "claim_data": { ... optional claim JSON ... }
    }

    Behavior:
    - If the query mentions claim/fraud keywords → routes to fraud scoring
    - Otherwise → routes to the guidance response generator
    """
    query = payload.get("query", "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    logger.info(f"🧩 Chatbot received query: {query}")

    # Simple heuristic-based intent detection
    fraud_keywords = ["claim", "fraud", "accident", "amount", "delay", "provider", "hospital"]
    intent = "fraud_check" if any(k in query.lower() for k in fraud_keywords) else "guidance"

    # Optional NLP-based scoring (semantic intent detection)
    try:
        nlp_result = analyze_text(query)
        if nlp_result.get("keyword_count", 0) > 0:
            intent = "fraud_check"
    except Exception as e:
        logger.warning(f"⚠️ NLP intent detection failed: {e}")

    # =====================================================
    # 🧾 Fraud Check Intent
    # =====================================================
    if intent == "fraud_check":
        claim_data = payload.get("claim_data")
        if not claim_data:
            return ORJSONResponse(
                status_code=400,
                content={
                    "response_type": "fraud_analysis",
                    "error": "Missing claim_data for fraud scoring.",
                    "example_format": {
                        "claim_data": {
                            "amount": 10000,
                            "report_delay_days": 3,
                            "provider": "ABC Hospital",
                            "notes": "Patient claimed duplicate accident",
                            "claimant_id": "C123",
                            "location": "Pune",
                            "is_new_bank": False,
                        }
                    },
                },
            )

        try:
            logger.info("⚙️ Running fraud scoring from chatbot...")
            result = await score_claim(claim_data)
            logger.info(f"✅ Fraud scoring completed for {claim_data.get('claimant_id', 'Unknown')}")

            return ORJSONResponse(
                status_code=200,
                content={
                    "response_type": "fraud_analysis",
                    "intent": intent,
                    "fraud_probability": result.get("fraud_probability"),
                    "decision": result.get("decision"),
                    "alarms": result.get("alarms", []),
                    "explanation": result.get("explanation", ""),
                },
            )

        except Exception as e:
            logger.error(f"❌ Error during chatbot fraud scoring: {e}")
            raise HTTPException(status_code=500, detail="Error processing fraud analysis.")

    # =====================================================
    # 💬 Guidance Intent
    # =====================================================
    else:
        try:
            logger.info("💡 Routing query to guidance system...")
            response = get_guidance_response(query)
            return ORJSONResponse(
                status_code=200,
                content={
                    "response_type": "guidance",
                    "intent": intent,
                    "message": response["response"],
                    "relevance_score": response.get("relevance_score", 1.0),
                },
            )

        except Exception as e:
            logger.error(f"❌ Error generating chatbot guidance: {e}")
            raise HTTPException(status_code=500, detail="Error generating guidance.")
