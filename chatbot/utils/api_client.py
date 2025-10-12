"""
API Client Utilities
--------------------
Handles communication with the backend (FastAPI) services.

Used by LangChain tools:
- submit_and_score:  → /api/v1/score_claim
- explain_alarms:    → /api/v1/explain/{alarm_type}
- retrieve_guidance: → /api/v1/guidance

Features:
- Centralized request handling with timeout and JSON safety.
- Auto-logs errors for debugging.
- Future-proof: easy to extend for authentication tokens.

Usage:
    from chatbot.utils.api_client import call_score_claim, call_guidance
"""

import json
import requests
from typing import Dict, Any, Optional
from chatbot.config.settings import settings
from chatbot.utils.logger import logger

# =========================================================
# 🧩 Helpers
# =========================================================

def _url(endpoint: str) -> str:
    """Construct a full API URL from relative endpoint."""
    base = settings.BACKEND_URL.rstrip("/")
    return f"{base}/api/v1/{endpoint.lstrip('/')}"


def _headers() -> Dict[str, str]:
    """Return standard headers for API requests."""
    headers = {"Content-Type": "application/json"}
    # If auth key/token is used later, add here:
    # if settings.API_KEY: headers["Authorization"] = f"Bearer {settings.API_KEY}"
    return headers


def _safe_request(method: str, url: str, **kwargs) -> Optional[Dict[str, Any]]:
    """Unified HTTP request handler with logging and error control."""
    try:
        logger.debug(f"API Request: {method.upper()} {url} | Payload: {kwargs.get('json')}")
        resp = requests.request(method, url, headers=_headers(), timeout=30, **kwargs)
        resp.raise_for_status()
        logger.debug(f"API Response [{resp.status_code}]: {resp.text[:300]}")  # limit output size
        return resp.json()
    except requests.RequestException as e:
        logger.error(f"❌ API Request failed: {url} | Error: {e}")
        return None
    except json.JSONDecodeError:
        logger.error(f"⚠️ Invalid JSON response from {url}")
        return None


# =========================================================
# 🧠 API CALLS
# =========================================================

def call_score_claim(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Submit a claim for fraud scoring.

    Args:
        payload (dict): Claim details, e.g., amount, provider, notes.

    Returns:
        dict | None: Response with fraud probability, decision, alarms, etc.
    """
    url = _url("score_claim")
    return _safe_request("POST", url, json=payload)


def call_explain_alarm(alarm_type: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve details about a specific fraud alarm type.

    Args:
        alarm_type (str): e.g., "high_amount", "late_reporting"

    Returns:
        dict | None: Explanation, severity, and mitigation details.
    """
    url = _url(f"explain/{alarm_type}")
    return _safe_request("GET", url)


def call_guidance(query: str, backend_url: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Retrieve policy guidance from the backend database (Postgres).

    Args:
        query (str): User question (e.g., "What docs are needed for a claim?")
        backend_url (str, optional): Override backend base URL.

    Returns:
        dict | None: Policy response and relevance score.
    """
    base_url = backend_url or settings.BACKEND_URL
    url = f"{base_url.rstrip('/')}/api/v1/guidance"
    return _safe_request("POST", url, json={"query": query})


# =========================================================
# 🧾 Example Usage (for debugging)
# =========================================================
if __name__ == "__main__":
    print("Testing API client connectivity...")
    test = call_score_claim({
        "amount": 10000,
        "city": "New York",
        "provider": "ABC Hospital",
        "delay_days": 5,
        "notes": "Minor injury"
    })
    print("Response:", test)
