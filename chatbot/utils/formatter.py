"""
Response Formatter
------------------
Formats agent/tool outputs for user-friendly display.
- Converts raw model or API outputs into clean Markdown.
- Adds emojis, headings, and structured bullet points.
- Handles multiple response types: fraud, guidance, explain, general.
- Optionally trims overly long responses for concise chat UIs.

Usage:
    formatted = format_chat_response(raw_output, response_type="fraud", data=response_dict)
"""

from typing import Dict, Any, Optional

# Visual emoji mappings
ALARM_EMOJIS = {
    "high": "🚨",
    "medium": "⚠️",
    "low": "ℹ️"
}

DECISION_EMOJIS = {
    "approve": "✅",
    "review": "🔍",
    "reject": "❌"
}

def format_chat_response(
    raw_output: str,
    response_type: str = "general",
    data: Optional[Dict[str, Any]] = None,
    max_length: int = 500
) -> str:
    """
    Format a chatbot or tool response with rich Markdown.
    Args:
        raw_output: Raw LLM or tool text.
        response_type: One of ["fraud", "guidance", "explain", "general"].
        data: Optional structured data (alarms, probability, etc.).
        max_length: Character limit for UI display (truncate if longer).
    Returns:
        str: Markdown-formatted string ready for UI.
    """
    if not raw_output:
        return "⚠️ No response received."

    # Route based on type
    response_type = response_type.lower().strip()
    if response_type == "fraud":
        formatted = _format_fraud_response(raw_output, data)
    elif response_type == "guidance":
        formatted = _format_guidance_response(raw_output, data)
    elif response_type == "explain":
        formatted = _format_explain_response(raw_output, data)
    else:
        formatted = f"🤖 {raw_output.strip()}"

    # Trim overly long outputs for chat display
    if len(formatted) > max_length:
        formatted = formatted[:max_length].rsplit("\n", 1)[0] + "\n\n*(trimmed for readability...)*"

    return formatted


# --------------------------------------------------------------------
# 🧠 Fraud Response Formatter
# --------------------------------------------------------------------
def _format_fraud_response(raw: str, data: Optional[Dict] = None) -> str:
    """Format fraud detection results (decision, alarms, explanation)."""
    if not isinstance(data, dict):
        data = {}

    prob = float(data.get("probability", 0))
    decision = str(data.get("decision", "Review")).title()
    alarms = data.get("alarms", [])

    decision_emoji = DECISION_EMOJIS.get(decision.lower(), "❓")
    formatted = f"{decision_emoji} **{decision}** — Fraud Probability: **{prob:.1f}%**\n\n"

    if alarms:
        formatted += "🚨 **Detected Alarms:**\n"
        for alarm in alarms[:5]:  # Limit to 5 alarms for brevity
            severity = alarm.get("severity", "medium").lower()
            alarm_emoji = ALARM_EMOJIS.get(severity, "⚠️")
            alarm_type = alarm.get("type", "Unknown").title()
            desc = alarm.get("description", "")
            formatted += f"{alarm_emoji} **{alarm_type}** ({severity}): {desc}\n"

        if len(alarms) > 5:
            formatted += f"...and {len(alarms) - 5} more.\n"
    else:
        formatted += "✅ No alarms triggered.\n"

    formatted += f"\n🧾 **Explanation:** {raw.strip()}"
    return formatted


# --------------------------------------------------------------------
# 📘 Guidance Response Formatter
# --------------------------------------------------------------------
def _format_guidance_response(raw: str, data: Optional[Dict] = None) -> str:
    """Format policy guidance or documentation lookup response."""
    if not isinstance(data, dict):
        data = {}

    score = float(data.get("relevance_score", 0))
    docs = data.get("required_docs", [])

    formatted = f"📖 **Policy Guidance**\n\n{raw.strip()}\n\n"
    if docs:
        formatted += "**📋 Required Documents:**\n"
        for doc in docs:
            formatted += f"- {doc}\n"

    formatted += f"\n📊 **Confidence:** {score:.1%} (match quality)"
    return formatted


# --------------------------------------------------------------------
# 💡 Explain Alarm Formatter
# --------------------------------------------------------------------
def _format_explain_response(raw: str, data: Optional[Dict] = None) -> str:
    """Format alarm explanation (single alarm info)."""
    if not isinstance(data, dict):
        data = {}

    alarm_type = data.get("type", "Unknown")
    severity = data.get("severity", "medium").lower()
    emoji = ALARM_EMOJIS.get(severity, "⚠️")

    formatted = (
        f"{emoji} **Alarm Explanation: {alarm_type.title()}** ({severity.upper()})\n\n"
        f"{raw.strip()}"
    )
    return formatted
