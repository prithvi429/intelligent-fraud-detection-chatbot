"""
API Client Utils
----------------
Handles communication with backend endpoints:
- /score_claim
- /guidance
- /explain/{alarm_type}
- /process_invoice (for OCR)

Includes:
✅ Error handling
✅ Optional API key authorization
✅ Streamlit-friendly logging
"""

import os
import json
import requests
from typing import Dict, Optional, Any
from dotenv import load_dotenv
import streamlit as st

# Load environment
load_dotenv()
API_KEY = os.getenv("API_KEY", "")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


# --------------------------------------------------------------------
# 🧠 Generic Request Wrapper
# --------------------------------------------------------------------
def _make_request(
    method: str, endpoint: str, payload: Optional[Dict] = None, backend_url: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Make a generic API call to backend (POST/GET).

    Args:
        method: "GET" or "POST"
        endpoint: Endpoint path (e.g., "score_claim")
        payload: JSON payload (dict)
        backend_url: Override backend base URL (optional)

    Returns:
        dict or None (if error)
    """
    base_url = backend_url or BACKEND_URL
    url = f"{base_url.rstrip('/')}/api/v1/{endpoint.lstrip('/')}"
    headers = {"Content-Type": "application/json"}

    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"

    try:
        if method.upper() == "POST":
            response = requests.post(url, json=payload or {}, headers=headers, timeout=30)
        else:
            response = requests.get(url, params=payload or {}, headers=headers, timeout=30)

        response.raise_for_status()
        return response.json()

    except requests.exceptions.Timeout:
        st.error("⏳ API request timed out. Please try again.")
    except requests.exceptions.ConnectionError:
        st.error("❌ Could not connect to the backend API. Make sure it's running.")
    except requests.exceptions.HTTPError as e:
        st.error(f"⚠️ API returned an error: {response.status_code} — {response.text}")
    except Exception as e:
        st.error(f"❌ Unexpected error: {e}")

    return None


# --------------------------------------------------------------------
# 🎯 Specific API Calls
# --------------------------------------------------------------------
def call_score_claim(claim_data: Dict, backend_url: str = None) -> Optional[Dict]:
    """POST /score_claim → returns fraud probability, decision, alarms, explanation"""
    return _make_request("POST", "score_claim", payload=claim_data, backend_url=backend_url)


def call_guidance(query: str, backend_url: str = None) -> Optional[Dict]:
    """POST /guidance → returns policy response and required documents"""
    payload = {"query": query}
    return _make_request("POST", "guidance", payload=payload, backend_url=backend_url)


def call_explain_alarm(alarm_type: str, backend_url: str = None) -> Optional[Dict]:
    """GET /explain/{alarm_type} → returns alarm meaning/explanation"""
    endpoint = f"explain/{alarm_type}"
    return _make_request("GET", endpoint, backend_url=backend_url)


def call_process_invoice(file, backend_url: str = None) -> Optional[Dict]:
    """POST /process_invoice → OCR extract claim info from PDF/Image"""
    base_url = backend_url or BACKEND_URL
    url = f"{base_url.rstrip('/')}/api/v1/process_invoice"
    headers = {}

    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"

    try:
        files = {"file": (file.name, file, file.type)}
        response = requests.post(url, files=files, headers=headers, timeout=60)
        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as e:
        st.error(f"❌ Upload failed: {e}")
        return None
