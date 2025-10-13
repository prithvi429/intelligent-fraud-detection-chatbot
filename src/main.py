"""
Main Application Entry Point
----------------------------
FastAPI app for the Intelligent Fraud Detection Chatbot.
Includes fraud scoring, guidance, explanations, and consistent validation handling.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, ORJSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
import json
import traceback

from src.utils.logger import logger
from src.config import config
from src.models.fraud import Decision
from src.services.fraud_engine import score_claim
from src.services.guidance import get_guidance_response
from src.services.explain import get_explanation_for_alarm


# =========================================================
# 🚀 App Initialization
# =========================================================
app = FastAPI(
    title="Intelligent Fraud Detection Chatbot",
    version="1.0.0",
    description="AI-powered fraud detection and claim decisioning API.",
)

# Allow requests from anywhere (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# 📦 Request Model (Pydantic Validation)
# =========================================================
class ClaimRequest(BaseModel):
    amount: float = Field(gt=0, description="Claim amount must be greater than 0")
    report_delay_days: int = Field(ge=0, description="Days delayed in reporting the claim")
    provider: str
    notes: str
    claimant_id: str
    location: str
    is_new_bank: bool = False


# =========================================================
# ⚙️ Exception Handlers
# =========================================================
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handles invalid request payloads gracefully and ensures response matches test expectations.
    """
    log_data = {
        "event": "request_error",
        "type": "ValidationError",
        "status": 422,
        "path": str(request.url.path),
        "errors": exc.errors(),
    }

    # Log structured validation error
    logger.error(json.dumps(log_data))

    # ✅ Exact capitalization and message that test expects
    response_body = {
        "detail": "Invalid input. Please check your request payload."
    }

    # Use ORJSONResponse to ensure exact string casing (no auto-lowercasing)
    return ORJSONResponse(status_code=422, content=response_body)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catches unexpected runtime errors gracefully."""
    log_data = {
        "event": "request_error",
        "type": type(exc).__name__,
        "status": 500,
        "trace": traceback.format_exc(),
    }

    logger.error(json.dumps(log_data))

    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again later."},
    )


# =========================================================
# 🧠 Core API Endpoints
# =========================================================
@app.post("/api/v1/score_claim")
async def score_claim_api(claim: ClaimRequest):
    """
    POST endpoint for fraud scoring.
    Automatically validates input using ClaimRequest schema.
    """
    logger.info(json.dumps({"event": "request_start", "path": "/api/v1/score_claim"}))

    result = await score_claim(claim.dict())

    response = {
        "claimant_id": claim.claimant_id,
        "fraud_probability": result["fraud_probability"],
        "decision": result["decision"],
        "alarms": result.get("alarms", []),
        "explanation": result.get("explanation", ""),
    }

    logger.info(json.dumps({
        "event": "request_end",
        "decision": result["decision"],
        "fraud_probability": result["fraud_probability"],
        "alarms": result.get("alarms", []),
    }))

    return JSONResponse(status_code=200, content=response)


@app.post("/api/v1/guidance")
async def guidance_api(query: dict):
    """Provides chatbot-like guidance for user queries."""
    response = get_guidance_response(query.get("query", ""))
    return JSONResponse(status_code=200, content={"guidance": response})


@app.get("/api/v1/explain/{alarm_name}")
async def explain_alarm(alarm_name: str):
    """Returns explanation for a triggered fraud alarm."""
    explanation = get_explanation_for_alarm(alarm_name)
    if not explanation:
        return JSONResponse(status_code=404, content={"detail": "Alarm explanation not found."})
    return JSONResponse(status_code=200, content=explanation)


@app.get("/")
async def root():
    """Root endpoint for basic API info."""
    return {
        "message": "Welcome to Intelligent Fraud Detection API",
        "fraud_types_detected": 15,
        "ml_enabled": config.ML_ENABLED,
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/me")
async def get_me():
    """Mock endpoint for authenticated user."""
    return {"user_id": "test_user", "role": "analyst", "environment": config.ENV}


# =========================================================
# 🏁 Entry Point
# =========================================================
if __name__ == "__main__":
    import uvicorn

    logger.info("🚀 Starting Intelligent Fraud Detection API (debug mode)")
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
