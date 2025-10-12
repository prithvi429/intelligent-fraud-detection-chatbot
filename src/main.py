"""
Main FastAPI Application
------------------------
Entry point for the Insurance Fraud Detection Chatbot API.

Features:
- Fraud Scoring, Alarm Explanations, and Policy Guidance APIs
- Integrates SQL DB, SageMaker ML model, and Pinecone vector DB
- Structured logging, health monitoring, and secure middleware

Run locally:
    uvicorn src.main:app --reload
"""

import time
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session
import uvicorn

# =========================================================
# 🔧 Local Imports
# =========================================================
from src.config import config
from src.utils.db import init_db, get_db
from src.utils.logger import logger
from src.utils.security import get_current_user
from src.fraud_engine.ml_inference import load_fraud_model, is_model_loaded
from src.api.endpoints import score_claim, explain_alarm, get_guidance
from src.middleware.logging_middleware import LoggingMiddleware  # ✅ Logging Middleware


# =========================================================
# 🧠 Application Lifecycle
# =========================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events for the app."""
    start_time = time.time()
    logger.info("🚀 Starting Insurance Fraud Detection Chatbot API...")
    logger.info(f"Environment: {config.ENV.upper()} | DEBUG={config.DEBUG} | LOG_LEVEL={config.LOG_LEVEL}")

    try:
        # 1️⃣ Initialize Database
        init_db()
        logger.info("✅ Database connection initialized.")

        # 2️⃣ Load ML Model (SageMaker or local)
        if config.is_ml_enabled:
            load_fraud_model()
            logger.info("✅ Fraud ML model loaded successfully.")
        else:
            logger.warning("⚠️ ML model not found. Using rule-based engine fallback.")

        # 3️⃣ Initialize Pinecone (if enabled)
        if config.is_pinecone_enabled:
            from src.chatbot.tools.retrieve_guidance import init_pinecone
            init_pinecone()
            logger.info("✅ Pinecone vector DB initialized.")

        logger.info(f"✨ Startup completed in {time.time() - start_time:.2f}s")

    except Exception as e:
        logger.error(f"❌ Startup error: {e}")
        raise

    # App runs here
    yield

    # Shutdown
    uptime = time.time() - start_time
    logger.info("🛑 Shutting down API service...")
    logger.info(f"🕒 Total uptime: {uptime:.2f}s")


# =========================================================
# ⚙️ FastAPI Configuration
# =========================================================
app = FastAPI(
    title="Insurance Fraud Detection Chatbot API",
    version="1.0.0",
    description="""
AI-driven system for analyzing and detecting fraudulent insurance claims.

### Core Capabilities
- 🧠 **Fraud Scoring** — ML + rule-based detection for 13 fraud patterns  
- 📘 **Alarm Explanations** — Human-readable insights into alarms  
- 💬 **Policy Guidance** — LLM + Pinecone hybrid Q&A search

Built using **FastAPI**, **SQLAlchemy**, **LangChain**, and **SageMaker**.
""",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# =========================================================
# 🌍 Middleware Configuration
# =========================================================

# 1️⃣ CORS Middleware (must be first)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",  # Streamlit frontend
        "http://localhost:3000",  # React dev
        "*",                      # Allow all (dev mode)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2️⃣ Logging Middleware (wraps all)
app.add_middleware(
    LoggingMiddleware,
    redact_pii=not config.DEBUG  # Redact PII in production only
)


# =========================================================
# ⚠️ Exception Handling
# =========================================================
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle pydantic validation errors globally."""
    logger.warning(f"Validation error at {request.url.path}: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Invalid input data. Please verify the request body.",
            "errors": exc.errors(),
        },
    )


@app.middleware("http")
async def global_exception_middleware(request: Request, call_next):
    """Global middleware to catch unhandled errors."""
    try:
        return await call_next(request)
    except HTTPException as e:
        logger.warning(f"Handled HTTPException: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"Unhandled exception: {type(e).__name__}: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "error": str(e)},
        )


# =========================================================
# 🧩 Routers
# =========================================================
app.include_router(score_claim.router, prefix="/api/v1", tags=["Fraud Scoring"])
app.include_router(explain_alarm.router, prefix="/api/v1", tags=["Explanations"])
app.include_router(get_guidance.router, prefix="/api/v1", tags=["Guidance"])


# =========================================================
# 🌡️ Health and Root Endpoints
# =========================================================
@app.get("/", tags=["Root"])
async def root_endpoint(request: Request):
    """Root endpoint for metadata and basic health info."""
    return {
        "message": "Welcome to the Insurance Fraud Detection Chatbot API!",
        "version": "1.0.0",
        "status": "running",
        "docs": str(request.url_for("docs")),
        "ml_model_loaded": config.is_ml_enabled and is_model_loaded(),
        "pinecone_enabled": config.is_pinecone_enabled,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check for DB, ML, and Pinecone readiness."""
    db_status = ml_status = pinecone_status = "ok"

    # Database Check
    try:
        db: Session = next(get_db())
        db.execute("SELECT 1")
        db.close()
    except Exception as e:
        db_status = f"error: {e}"

    # ML Model Check
    ml_status = "ok" if is_model_loaded() else "not loaded"

    # Pinecone Check
    pinecone_status = "ok" if config.is_pinecone_enabled else "disabled"

    healthy = db_status == "ok" and ml_status == "ok"
    status_code = 200 if healthy else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if healthy else "degraded",
            "database": db_status,
            "ml_model": ml_status,
            "pinecone": pinecone_status,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


# =========================================================
# 👤 Authenticated User Endpoint
# =========================================================
@app.get("/me", tags=["User"])
async def get_current_user_info(current_user=Depends(get_current_user)):
    """Return info about the current authenticated user."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {
        "user_id": current_user.get("user_id", "unknown"),
        "role": current_user.get("role", "user"),
    }


# =========================================================
# ▶️ CLI Server Runner
# =========================================================
def run_api(host: str = None, port: int = None, reload: bool = None):
    """Launch FastAPI server (CLI entry)."""
    host = host or config.API_HOST
    port = port or config.API_PORT
    reload = reload if reload is not None else config.DEBUG

    logger.info(f"🌐 Starting server → http://{host}:{port}")
    logger.info(f"📘 Docs available at → http://{host}:{port}/docs")

    uvicorn.run(
        "src.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level=config.LOG_LEVEL.lower(),
        access_log=config.DEBUG,
    )


# =========================================================
# 🧩 Main Entry
# =========================================================
if __name__ == "__main__":
    run_api()
