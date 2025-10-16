"""
Main Application Entry Point
----------------------------
FastAPI app for the Intelligent Fraud Detection Chatbot.

Handles:
 - Fraud scoring and risk assessment
 - Guidance and explanations
 - Conversational chatbot queries
 - Validation, health, and system info endpoints
"""

from fastapi import FastAPI, Request
from fastapi.responses import ORJSONResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from datetime import datetime
import traceback
import json
import os

# =========================================================
# 📦 Internal Imports
# =========================================================
from src.utils.logger import logger
from src.config import config
from src.services.guidance import get_guidance_response
from src.api.endpoints import (
    score_claim,
    explain_alarm,
    chatbot,
)

# =========================================================
# 🚀 FastAPI Initialization
# =========================================================
app = FastAPI(
    title="Intelligent Fraud Detection Chatbot",
    version="1.0.0",
    description="AI-powered fraud detection and claim decisioning API.",
)

# =========================================================
# 🌐 CORS Configuration
# =========================================================
ALLOWED_ORIGINS = getattr(config, "ALLOWED_ORIGINS", ["*"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================================================
# 🔌 Include Routers (only main file uses prefix)
# =========================================================
# ✅ Keep router paths clean — no double prefix
app.include_router(score_claim.router, prefix="/api/v1")
app.include_router(explain_alarm.router, prefix="/api/v1")
app.include_router(chatbot.router, prefix="/api/v1")

# =========================================================
# ⚙️ Exception Handlers
# =========================================================
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handles invalid request payloads gracefully."""
    log_data = {
        "event": "request_error",
        "type": "ValidationError",
        "status": 422,
        "path": str(request.url.path),
        "errors": exc.errors(),
    }
    logger.error(json.dumps(log_data))

    return ORJSONResponse(
        status_code=422,
        content={"detail": "Invalid input. Please check your request payload."},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all for unexpected runtime exceptions."""
    log_data = {
        "event": "request_error",
        "type": type(exc).__name__,
        "status": 500,
        "path": str(request.url.path),
        "trace": traceback.format_exc(),
    }
    logger.error(json.dumps(log_data))

    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again later."},
    )


# =========================================================
# 💬 Guidance Endpoint (Standalone)
# =========================================================
@app.post("/api/v1/guidance")
async def guidance_api(query: dict):
    """
    Provides chatbot-style guidance for user queries.
    Returns 400 for empty queries.
    """
    user_query = query.get("query", "").strip()

    if not user_query:
        return ORJSONResponse(
            status_code=400,
            content={"detail": "Query text cannot be empty."},
        )

    guidance_data = get_guidance_response(user_query)

    return ORJSONResponse(
        status_code=200,
        content={
            "guidance": {"response": guidance_data["response"]},
            "relevance_score": guidance_data.get("relevance_score", 1.0),
        },
    )


# =========================================================
# 🧩 Utility Endpoints
# =========================================================
@app.get("/")
async def root():
    """Root endpoint for system information."""
    return {
        "status": "running",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "message": "Welcome to Intelligent Fraud Detection API",
        "fraud_types_detected": 15,
        "ml_enabled": getattr(config, "ML_ENABLED", True),
    }


@app.get("/health")
async def health():
    """Basic health check."""
    return {"status": "healthy"}


@app.get("/me")
async def get_me():
    """Mock user profile (for testing authentication)."""
    return {
        "user_id": "test_user",
        "role": "analyst",
        "environment": getattr(config, "ENV", "development"),
    }


# =========================================================
# 🧾 Debug Utility: Show Registered Routes
# =========================================================
@app.on_event("startup")
async def list_routes():
    """Logs all routes when app starts."""
    routes = [route.path for route in app.routes]
    logger.info("🚦 Registered Routes:")
    for r in routes:
        logger.info(f"  • {r}")


# =========================================================
# 🏁 Local Debug Runner
# =========================================================
if __name__ == "__main__":
    import uvicorn

    logger.info("🚀 Starting Intelligent Fraud Detection API (debug mode)")
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=getattr(config, "DEBUG", True),
    )
