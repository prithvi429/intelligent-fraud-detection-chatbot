"""
Security Utility
----------------
Handles:
- JWT token creation and verification
- Input sanitization
- PII anonymization
- Basic validation helpers
"""

import os
import re
import hashlib
import secrets
import jwt
from jwt import ExpiredSignatureError, InvalidTokenError
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from src.config import config
from src.utils.logger import logger

# =========================================================
# 🔐 JWT Setup
# =========================================================
security = HTTPBearer()

# Use environment key or generate temporary for dev
JWT_SECRET = os.getenv("JWT_SECRET", secrets.token_hex(32))
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRY_MINUTES = int(os.getenv("JWT_EXPIRY_MINUTES", "30"))


def create_jwt_token(data: Dict[str, Any]) -> str:
    """
    Create a signed JWT token with expiry.
    Example payload: {"sub": user_id, "role": "user"}
    """
    expire_time = datetime.utcnow() + timedelta(minutes=JWT_EXPIRY_MINUTES)
    payload = {**data, "exp": expire_time, "type": "access"}

    try:
        token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        logger.info(f"JWT created for {data.get('sub', 'unknown')}")
        return token
    except Exception as e:
        logger.error(f"Error creating JWT: {e}")
        raise HTTPException(status_code=500, detail="Failed to create authentication token")


def verify_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify JWT and return decoded payload if valid."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except ExpiredSignatureError:
        logger.warning("JWT token expired")
        raise HTTPException(status_code=401, detail="Token expired")
    except InvalidTokenError:
        logger.warning("Invalid JWT token")
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        logger.error(f"JWT verification failed: {e}")
        return None


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Optional[Dict[str, Any]]:
    """
    Extract user info from JWT in Authorization header.
    In DEBUG mode, allows anonymous access.
    """
    if config.DEBUG:
        return {"user_id": "dev_user", "role": "admin"}

    token = credentials.credentials if credentials else None
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = verify_jwt_token(token)
    return {"user_id": payload.get("sub"), "role": payload.get("role", "user")}


# =========================================================
# 🔒 PII Anonymization
# =========================================================
def anonymize_pii(data: str, method: str = "sha256") -> str:
    """
    Anonymize personally identifiable information.
    Supports:
    - "sha256" → irreversible hash
    - "mask" → human-readable masking (e.g., emails)
    """
    if not data:
        return ""

    if method == "sha256":
        return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]

    elif method == "mask":
        if "@" in data:
            local, domain = data.split("@")
            domain_name, *rest = domain.split(".")
            return f"{local[0]}***@{domain_name[0]}***.{'.'.join(rest)}"
        return data[0] + "*" * (len(data) - 1)

    logger.warning(f"Unknown anonymization method: {method}")
    return data


# =========================================================
# 🧼 Input Sanitization
# =========================================================
def sanitize_input(text: str) -> str:
    """
    Remove common XSS/SQL injection patterns and limit input length.
    For safe use in notes, provider names, etc.
    """
    if not text:
        return ""

    text = text[:1000]  # Max length
    dangerous_patterns = [
        r"<script.*?>.*?</script>",
        r"on\w+\s*=",
        r"javascript:",
        r"\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|EXEC|ALTER|CREATE|GRANT|REVOKE)\b",
    ]

    for pattern in dangerous_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    # Strip control characters and whitespace
    text = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", text).strip()

    logger.debug(f"Sanitized input ({len(text)} chars): {text[:60]}...")
    return text


# =========================================================
# 💰 Claim Validation
# =========================================================
def validate_claim_amount(amount: float) -> bool:
    """Ensure claim amount is positive and below a logical limit."""
    try:
        if amount <= 0:
            raise ValueError("Claim amount must be positive.")
        if amount > 1_000_000:
            raise ValueError("Claim amount exceeds the allowed limit (₹10 lakh cap).")
        return True
    except ValueError as e:
        logger.warning(f"Invalid claim amount: {amount} ({e})")
        raise HTTPException(status_code=400, detail=str(e))


# =========================================================
# 🧪 Local Test
# =========================================================
if __name__ == "__main__":
    token = create_jwt_token({"sub": "user123", "role": "user"})
    print("JWT Token:", token)
    print("Decoded:", verify_jwt_token(token))

    print("Anonymized:", anonymize_pii("user@example.com"))
    print("Sanitized:", sanitize_input("<script>alert(1)</script> DROP TABLE users;"))
    validate_claim_amount(9999.0)
