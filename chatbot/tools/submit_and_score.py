"""
Submit and Score Tool
---------------------
LangChain + test-safe callable that parses user claim input
and interacts with the fraud detection backend API.

Supports both:
 - Direct function call (pytest)
 - LangChain tool registration (chatbot)
"""

import re
import time
from typing import Optional, Dict, Any
from langchain.tools import tool

# =========================================================
# 🧩 Dynamic Path Fix for Test Compatibility
# =========================================================
import sys, os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# =========================================================
# 📦 Imports (work for both chatbot & src)
# =========================================================
from chatbot.utils.api_client import call_score_claim
from chatbot.utils.logger import log_tool_call, log_error
from chatbot.config.settings import settings
from chatbot.config.constants import ALARM_EMOJIS, DECISION_EMOJIS


# =========================================================
# 🔍 Helpers
# =========================================================
def _parse_claim_details(query: str, session_id: str) -> Dict[str, Any]:
    """Extract claim data from user text query."""
    amount_match = re.search(r"\$?(\d+(?:,\d{3})*(?:\.\d{2})?)", query)
    delay_match = re.search(r"(?:reported|delay)\s*(\d+)\s*(?:days?|hrs?)", query, re.I)
    provider_match = re.search(
        r"(?:provider|clinic|hospital)\s*:?\s*([A-Za-z\s_]+?)(?=\s*(?:,|$|\.|notes))", query, re.I
    )
    location_match = re.search(
        r"(?:location|city|place)\s*:?\s*([A-Za-z\s,]+?)(?=\s*(?:,|$|\.|provider))", query, re.I
    )
    is_new_bank = any(kw in query.lower() for kw in ["new bank", "new account"])

    return {
        "amount": float(amount_match.group(1).replace(",", "")) if amount_match else 0.0,
        "report_delay_days": int(delay_match.group(1)) if delay_match else 0,
        "provider": provider_match.group(1).strip() if provider_match else "Unknown Provider",
        "notes": query.strip(),
        "claimant_id": f"{session_id}_{int(time.time())}",
        "location": location_match.group(1).strip() if location_match else "Unknown Location",
        "is_new_bank": is_new_bank,
    }


def _format_result(result: Dict[str, Any]) -> str:
    """Format API result into user-friendly markdown output."""
    prob = float(result.get("fraud_probability", 0))
    decision = result.get("decision", "Review")
    alarms = result.get("alarms", [])
    explanation = result.get("explanation", "No additional explanation provided.")

    decision_emoji = DECISION_EMOJIS.get(decision.lower(), "❓")

    formatted = [
        f"{decision_emoji} **Claim Decision: {decision}**",
        f"**Fraud Probability:** {prob:.1f}% (Higher = more suspicious)\n",
    ]

    if alarms:
        formatted.append("🚨 **Key Alarms Detected:**")
        for alarm in alarms[:3]:
            sev_emoji = ALARM_EMOJIS.get(alarm.get("severity", "medium"), "⚠️")
            formatted.append(
                f"{sev_emoji} **{alarm.get('type', 'Unknown').replace('_', ' ').title()}** — "
                f"{alarm.get('description', 'No details')}"
            )
        if len(alarms) > 3:
            formatted.append(f"*...and {len(alarms) - 3} more alarms.*")
    else:
        formatted.append("✅ **No alarms triggered.** Claim appears legitimate.")

    formatted.append(f"\n**Explanation:** {explanation.strip()}")
    formatted.append(
        "\n💡 *You can ask:* “Explain high_amount” or “Why was this rejected?” for details."
    )

    return "\n\n".join(formatted)


# =========================================================
# 🧠 Main Callable
# =========================================================
@tool("submit_and_score", return_direct=True)
def submit_and_score(query: str, session_id: Optional[str] = None) -> str:
    """
    Submit a claim description and get a fraud risk analysis.
    Works as both:
     - A LangChain tool
     - A callable function for testing
    """
    session_id = session_id or f"chat_{int(time.time())}"
    log_tool_call(session_id, "submit_and_score", {"query": query[:100]})

    try:
        # 1️⃣ Parse claim info
        claim_data = _parse_claim_details(query, session_id)

        # 2️⃣ Validate required data
        if claim_data["amount"] <= 0:
            return (
                "❌ **Error:** Could not parse a valid claim amount from your query.\n"
                "Please include an amount like `$15,000` for accurate scoring."
            )

        # 3️⃣ Call backend fraud scoring API
        result = call_score_claim(claim_data, settings.BACKEND_URL)
        if not result:
            return (
                "⚠️ **Backend Error:** Could not reach the fraud detection service.\n"
                "Please try again later."
            )

        # 4️⃣ Format result
        return _format_result(result)

    except Exception as e:
        log_error(session_id, f"submit_and_score failed: {e}", query)
        return "❌ **System Error:** Something went wrong while analyzing the claim. Please try again."


# =========================================================
# 📤 Export
# =========================================================
__all__ = ["submit_and_score"]
