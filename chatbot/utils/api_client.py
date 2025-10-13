"""
API Client Utilities
--------------------
Handles communication with the backend (FastAPI) services.

Used by LangChain tools:
- submit_and_score:  → /api/v1/score_claim
- explain_alarms:    → /api/v1/explain/{alarm_type}
- retrieve_guidance: → /api/v1/guidance
"""

import json
import requests
from typing import Dict, Any, Optional
from chatbot.config.settings import settings
from chatbot.utils.logger import logger


# =========================================================
# 🧩 Helpers
# =========================================================

def _url(endpoint: str, backend_url: Optional[str] = None) -> str:
    """Construct a full API URL from a relative endpoint."""
    base = (backend_url or settings.BACKEND_URL).rstrip("/")
    return f"{base}/api/v1/{endpoint.lstrip('/')}"


def _headers() -> Dict[str, str]:
    """Return standard headers for API requests."""
    headers = {"Content-Type": "application/json"}
    return headers


def _safe_request(method: str, url: str, **kwargs) -> Optional[Dict[str, Any]]:
    """Unified HTTP request handler with logging and error control."""
    try:
        logger.debug(f"🌐 API Request: {method.upper()} {url} | Payload: {kwargs.get('json')}")

        # ✅ Test-safe patch: allow mocking requests.post/get
        if method.upper() == "POST":
            resp = requests.post(url, headers=_headers(), timeout=30, **kwargs)
        elif method.upper() == "GET":
            resp = requests.get(url, headers=_headers(), timeout=30, **kwargs)
        else:
            resp = requests.request(method, url, headers=_headers(), timeout=30, **kwargs)

        resp.raise_for_status()
        data = resp.json()

        # ✅ Final fix: unwrap Mock response if needed
        if hasattr(data, "get") is False and isinstance(resp, object) and hasattr(resp, "json"):
            try:
                data = resp.json()
            except Exception:
                pass

        if not isinstance(data, dict):
            logger.error(f"⚠️ Unexpected response type: {type(data)} from {url}")
            return None

        logger.debug(f"✅ API Response [{resp.status_code}]: {str(data)[:300]}")
        return data

    except requests.RequestException as e:
        logger.error(f"❌ API request failed: {url} | Error: {e}")
        return None
    except json.JSONDecodeError:
        logger.error(f"⚠️ Invalid JSON response from {url}")
        return None


# =========================================================
# 🧠 API CALLS
# =========================================================

def call_score_claim(payload: Dict[str, Any], backend_url: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Submit a claim for fraud scoring."""
    url = _url("score_claim", backend_url)
    return _safe_request("POST", url, json=payload)


def call_explain_alarm(alarm_type: str, backend_url: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieve details about a specific fraud alarm type."""
    url = _url(f"explain/{alarm_type}", backend_url)
    return _safe_request("GET", url)


def call_guidance(query: str, backend_url: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieve policy guidance from the backend database."""
    url = _url("guidance", backend_url)
    return _safe_request("POST", url, json={"query": query})


# =========================================================
# 🧾 Example Usage (manual test)
# =========================================================
if __name__ == "__main__":
    print("🔍 Testing API client connectivity...")

    test_payload = {
        "amount": 10000,
        "report_delay_days": 5,
        "provider": "ABC Hospital",
        "notes": "Minor injury",
        "location": "New York",
        "claimant_id": "manual_test_user",
    }

    response = call_score_claim(test_payload, "http://localhost:8000")
    print("Response:", response)
