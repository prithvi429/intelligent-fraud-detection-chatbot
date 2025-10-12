"""
Formatter Utils
---------------
Formats backend responses (fraud/guidance/explain) for clean Streamlit display.

Functions:
- format_fraud_response() → Dict (text + structured data)
- format_guidance_response() → str
- format_explain_alarm() → str

Usage Example:
    formatted = format_fraud_response(response)
    st.markdown(formatted["text"], unsafe_allow_html=True)
"""

import re
from typing import Dict, List


# --------------------------------------------------------------------
# 🧠 FRAUD RESPONSE FORMATTER
# --------------------------------------------------------------------
def format_fraud_response(response: Dict) -> Dict:
    """
    Format fraud detection response for Streamlit markdown display.

    Args:
        response: dict like:
        {
            "fraud_probability": 75.0,
            "decision": "Reject",
            "alarms": [...],
            "explanation": "Reasoning text"
        }

    Returns:
        dict: {
            "text": str (markdown),
            "formatted_alarms": list,
            "decision_class": str,
            "probability": float,
            "decision": str
        }
    """
    prob = response.get("fraud_probability", 0.0)
    decision = response.get("decision", "Review")
    alarms = response.get("alarms", [])
    explanation = response.get("explanation", "No explanation provided.")

    # Normalize decision string for CSS class
    decision_class = f"decision-{decision.lower().replace(' ', '-')}"

    # Format alarms with icons and severity
    formatted_alarms: List[Dict] = []
    for alarm in alarms:
        severity = alarm.get("severity", "medium").lower()
        icon = "🚨" if severity == "high" else "⚠️" if severity == "medium" else "ℹ️"
        formatted_alarms.append({
            "icon": icon,
            "type": alarm.get("type", "Unknown").replace("_", " ").title(),
            "description": alarm.get("description", "No details provided."),
            "severity": severity
        })

    # ----------------------------------------------------------
    # 🧾 Build Markdown output
    # ----------------------------------------------------------
    text = f"""
### 🧠 **Fraud Analysis Summary**
**Decision:** <span class="{decision_class}">{decision}</span>  
**Fraud Probability:** **{prob:.1f}%**

---

#### ⚠️ Alarms ({len(formatted_alarms)} detected)
"""

    if formatted_alarms:
        for alarm in formatted_alarms:
            text += f"- {alarm['icon']} **{alarm['type']}** ({alarm['severity']}): {alarm['description']}\n"
    else:
        text += "✅ No fraud alarms triggered.\n"

    text += f"""
---

#### 🧩 Explanation
{explanation}
"""

    return {
        "text": text.strip(),
        "formatted_alarms": formatted_alarms,
        "decision_class": decision_class,
        "probability": prob,
        "decision": decision
    }


# --------------------------------------------------------------------
# 📖 GUIDANCE RESPONSE FORMATTER
# --------------------------------------------------------------------
def format_guidance_response(response: Dict) -> str:
    """
    Format policy guidance response for display.

    Args:
        response: dict like:
        {
            "guidance": {"response": str, "required_docs": [...]},
            "relevance_score": 0.85
        }

    Returns:
        str: Markdown-formatted text.
    """
    guidance = response.get("guidance", {})
    guidance_text = guidance.get("response", "No guidance available.")
    required_docs = guidance.get("required_docs", [])
    score = response.get("relevance_score", 0.0)

    text = f"""
### 📖 **Policy Guidance**
**Response:** {guidance_text}

---
"""

    if required_docs:
        text += "**Required Documents:**\n"
        for doc in required_docs:
            text += f"- 🗂️ {doc}\n"
        text += "\n"

    text += f"**Relevance Score:** {score:.1%}  \n*(Indicates how well this policy matches your query)*"
    return text.strip()


# --------------------------------------------------------------------
# 🔍 ALARM EXPLANATION FORMATTER
# --------------------------------------------------------------------
def format_explain_alarm(response: Dict) -> str:
    """
    Format explain alarm response for user-friendly display.

    Args:
        response: dict like:
        {
            "type": "high_amount",
            "description": "Claim exceeds threshold",
            "severity": "high"
        }

    Returns:
        str: Markdown string
    """
    alarm_type = response.get("type", "Unknown").replace("_", " ").title()
    description = response.get("description", "No description provided.")
    severity = response.get("severity", "medium").lower()

    # Severity mapping
    emoji = "🚨" if severity == "high" else "⚠️" if severity == "medium" else "ℹ️"
    severity_label = severity.capitalize()

    text = f"""
### {emoji} **{alarm_type} Alarm** ({severity_label})
{description}
"""
    return text.strip()
