"""
Explain Alarms Tool
-------------------
LangChain tool: Fetches detailed alarm explanation from the backend `/explain/{alarm_type}` endpoint.

Features:
- Extracts alarm_type from user query (regex + fuzzy keyword mapping)
- Calls backend API for explanation, severity, evidence, and mitigation steps
- Returns Markdown-formatted explanation
- Handles invalid or unknown alarms gracefully
- Logs all calls and errors for observability

Usage:
    explain_alarms("Explain high amount alarm", session_id="user123")
"""

from langchain.tools import tool
from typing import Optional
import re

from ..utils.api_client import call_explain_alarm
from ..utils.logger import log_tool_call, log_error
from ..config.settings import settings
from ..config.constants import ALARM_TYPES, ALARM_EMOJIS


# =========================================================
# 🧠 LangChain Tool Definition
# =========================================================
@tool("explain_alarms", return_direct=True)
def explain_alarms(query: str, session_id: Optional[str] = None) -> str:
    """
    Explain a specific fraud alarm in detail.

    Args:
        query (str): User message (e.g., "Explain high_amount alarm" or "What does location mismatch mean?")
        session_id (Optional[str]): Unique session ID for tracking/logging.

    Returns:
        str: Markdown-formatted explanation for the specified alarm.
    """
    session_id = session_id or "anonymous"
    log_tool_call(session_id, "explain_alarms", {"query": query[:100]})

    try:
        # ------------------------------------------------
        # 🔍 Step 1: Identify Alarm Type
        # ------------------------------------------------
        query_lower = query.lower().strip()
        alarm_type = None

        # Direct match
        for valid_type in ALARM_TYPES:
            if valid_type.replace("_", " ") in query_lower or valid_type in query_lower:
                alarm_type = valid_type
                break

        # Heuristic fallback mapping
        if not alarm_type:
            keyword_map = {
                "late": "late_reporting",
                "delay": "late_reporting",
                "amount": "high_amount",
                "high": "high_amount",
                "blacklist": "blacklist_hit",
                "location": "location_mismatch",
                "keyword": "suspicious_keywords",
                "phrase": "suspicious_keywords",
                "vendor": "vendor_fraud",
            }
            for kw, mapped in keyword_map.items():
                if kw in query_lower:
                    alarm_type = mapped
                    break

        # ------------------------------------------------
        # ❓ Step 2: Handle Unknown Alarm
        # ------------------------------------------------
        if not alarm_type:
            supported = ", ".join(ALARM_TYPES[:6]) + ", etc."
            return (
                "❓ **Unknown or unrecognized alarm type.**\n"
                "Try asking about a specific one, e.g., `Explain high_amount`.\n\n"
                f"Supported alarms include: {supported}"
            )

        # ------------------------------------------------
        # ⚙️ Step 3: Call Backend API
        # ------------------------------------------------
        result = call_explain_alarm(alarm_type, settings.BACKEND_URL)
        if not result:
            return (
                f"⚠️ **Backend Error:** Could not fetch details for `{alarm_type}`.\n"
                "Try again later or choose another alarm (e.g., `Explain late_reporting`)."
            )

        # ------------------------------------------------
        # 📊 Step 4: Extract Fields
        # ------------------------------------------------
        description = result.get("description", "No detailed explanation available.")
        severity = result.get("severity", "medium").lower()
        evidence = result.get("evidence_required", [])
        mitigation = result.get("mitigation", "Provide additional documentation or clarification.")

        emoji = ALARM_EMOJIS.get(severity, "⚠️")

        # ------------------------------------------------
        # 🧾 Step 5: Format Markdown Response
        # ------------------------------------------------
        formatted = [
            f"{emoji} **Explanation for {alarm_type.replace('_', ' ').title()} Alarm** ({severity.upper()} Severity)",
            "",
            f"**What it means:** {description}",
        ]

        if evidence:
            formatted.append("\n**Evidence Typically Needed:**")
            for e in evidence:
                formatted.append(f"• {e}")
            formatted.append("")

        formatted.append(f"**How to Resolve:** {mitigation}")
        formatted.append(
            "\n💡 *Tip:* If you think this alarm is incorrect, you can appeal with additional proof (bills, documents, timestamps)."
        )

        return "\n".join(formatted)

    except Exception as e:
        log_error(session_id, f"explain_alarms failed: {e}", query)
        return (
            "❌ **System Error:** Something went wrong while explaining this alarm.\n"
            "Please try again or ask about another one."
        )


# =========================================================
# 🧩 Test Compatibility Wrapper (Singular)
# =========================================================
def explain_alarm(alarm_type: str) -> str:
    """
    ✅ Test-safe wrapper used in integration tests.
    Delegates to `explain_alarms()` to ensure consistent behavior.
    """
    return explain_alarms(f"Explain {alarm_type}")


# =========================================================
# 📤 Exports
# =========================================================
__all__ = ["explain_alarms", "explain_alarm"]
