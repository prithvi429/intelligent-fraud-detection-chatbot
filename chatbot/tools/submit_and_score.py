"""
Submit and Score Tool
---------------------
LangChain tool: Parses user input for claim details and calls backend `/score_claim` API.

Functions:
- Extracts: amount, delay, provider, notes, location, new_bank (regex-based).
- Calls: Backend API via call_score_claim.
- Returns: Decision, probability, alarms, explanation (formatted Markdown).
- Logs: Structured via chat_logger for traceability.

Usage:
    submit_and_score("Score $15,000 claim with shady clinic, new bank account.", session_id="sess123")
"""

from langchain.tools import tool
from typing import Optional, Dict, Any
import re
import time

from ..utils.api_client import call_score_claim
from ..utils.logger import log_tool_call, log_error
from ..config.settings import settings
from ..config.constants import ALARM_EMOJIS, DECISION_EMOJIS


@tool("submit_and_score", return_direct=True)
def submit_and_score(query: str, session_id: Optional[str] = None) -> str:
    """
    Score an insurance claim for potential fraud.

    Args:
        query (str): User message describing the claim (e.g., "$20,000 crash, provider shady_clinic").
        session_id (Optional[str]): Session for logging context.

    Returns:
        str: Markdown-formatted fraud analysis result (decision, probability, alarms, explanation).
    """
    session_id = session_id or f"chat_{int(time.time())}"
    log_tool_call(session_id, "submit_and_score", {"query": query[:100]})

    try:
        # ----------------------------
        # 🔍 Parse Claim Details
        # ----------------------------
        amount_match = re.search(r"\$?(\d+(?:,\d{3})*(?:\.\d{2})?)", query)
        delay_match = re.search(r"(?:reported|delay)\s*(\d+)\s*(?:days?|hrs?)", query, re.I)
        provider_match = re.search(
            r"(?:provider|clinic|hospital)\s*:?\s*([A-Za-z\s]+?)(?=\s*(?:,|$|\.|notes))", query, re.I
        )
        location_match = re.search(
            r"(?:location|city|place)\s*:?\s*([A-Za-z\s,]+?)(?=\s*(?:,|$|\.|provider))", query, re.I
        )
        is_new_bank = any(kw in query.lower() for kw in ["new bank", "new account"])

        claim_data = {
            "amount": float(amount_match.group(1).replace(",", "")) if amount_match else 0.0,
            "report_delay_days": int(delay_match.group(1)) if delay_match else 0,
            "provider": provider_match.group(1).strip() if provider_match else "Unknown Provider",
            "notes": query.strip(),
            "claimant_id": f"{session_id}_{int(time.time())}",
            "location": location_match.group(1).strip() if location_match else "Unknown Location",
            "is_new_bank": is_new_bank,
        }

        # ----------------------------
        # ⚠️ Validation
        # ----------------------------
        if claim_data["amount"] <= 0:
            return (
                "❌ **Error:** Could not parse a valid claim amount from your query.\n"
                "Please include an amount like `$15,000` for accurate scoring."
            )

        # ----------------------------
        # 🧠 Call Backend API
        # ----------------------------
        result = call_score_claim(claim_data, settings.BACKEND_URL)
        if not result:
            return (
                "⚠️ **Backend Error:** I couldn’t reach the fraud detection service.\n"
                "Please try again later or rephrase your claim details."
            )

        # ----------------------------
        # 📊 Extract Results
        # ----------------------------
        prob = float(result.get("fraud_probability", 0))
        decision = result.get("decision", "Review")
        alarms = result.get("alarms", [])
        explanation = result.get("explanation", "No additional explanation provided.")

        # ----------------------------
        # 🧾 Format Response (Markdown)
        # ----------------------------
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
                    f"{sev_emoji} **{alarm.get('type', 'Unknown').replace('_', ' ').title()}** — {alarm.get('description', 'No details')}"
                )
            if len(alarms) > 3:
                formatted.append(f"*...and {len(alarms) - 3} more alarms.*")
        else:
            formatted.append("✅ **No alarms triggered.** Claim appears legitimate.")

        formatted.append(f"\n**Explanation:** {explanation.strip()}")
        formatted.append(
            "\n💡 *You can ask:* “Explain high_amount” or “Why was this rejected?” for detailed insight."
        )

        return "\n\n".join(formatted)

    except Exception as e:
        log_error(session_id, f"submit_and_score failed: {e}", query)
        return "❌ **System Error:** Something went wrong while analyzing the claim. Please try again."


