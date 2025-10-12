"""
Dependencies for FastAPI endpoints:
-----------------------------------
Handles database sessions, ML model availability,
authentication, and contextual data retrieval.
"""

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

from src.utils.db import get_db  # Database session factory
from src.config import config
from src.utils.logger import logger
from src.utils.security import get_current_user  # JWT/API key stub
from src.fraud_engine.ml_inference import is_model_loaded  # Model health check


# =========================================================
# 🗄️ DATABASE SESSION
# =========================================================
def get_db_session(db: Session = Depends(get_db)) -> Session:
    """
    Provides a managed SQLAlchemy DB session.
    Ensures session is properly closed after the request.
    """
    try:
        yield db
    finally:
        db.close()


# =========================================================
# 🤖 ML MODEL CHECK
# =========================================================
def require_ml_model() -> bool:
    """
    Ensures the ML model (local .pkl or SageMaker) is available before scoring.
    If unavailable, raises a 503 and falls back to rule-based detection.
    """
    if not config.is_ml_enabled or not is_model_loaded():
        logger.warning("⚠️ ML model not available – using rule-based scoring only.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Fraud ML model unavailable. Falling back to rule-based scoring.",
        )
    return True


# =========================================================
# 🔐 AUTHENTICATION (Stub / Extendable)
# =========================================================
def authenticated_user(current_user: Optional[dict] = Depends(get_current_user)) -> dict:
    """
    Optional authentication layer (e.g., JWT/OAuth2).
    Currently allows anonymous access in DEBUG mode.
    """
    if not current_user:
        if config.DEBUG:
            logger.debug("⚙️ Using anonymous access (DEBUG mode).")
            current_user = {"user_id": "anonymous", "role": "user"}
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required. Provide a valid token or API key.",
                headers={"WWW-Authenticate": "Bearer"},
            )
    return current_user


# =========================================================
# 👤 CLAIMANT CONTEXT FETCHER
# =========================================================
def get_claimant_context(claimant_id: str, db: Session = Depends(get_db_session)) -> dict:
    """
    Fetch claimant historical context (past claims, behavior patterns, etc.).
    Stub for demo; replace with real DB queries later.
    """
    # Example: history = db.query(Claimant).filter(Claimant.id == claimant_id).first()
    history = {"prior_claims": 0, "last_claim_date": None}
    logger.debug(f"Fetched claimant context for ID: {claimant_id}")
    return history
