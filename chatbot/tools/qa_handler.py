"""
QA Handler Tool
---------------
LangChain tool: Handles follow-up Q&A such as
“Why was my claim rejected?” or “How can I appeal my decision?”

🧠 Combines outputs from:
- explain_alarms (for technical reasoning behind rejections)
- retrieve_guidance (for next steps or appeal instructions)

Adds empathetic, conversational formatting to improve user experience.
"""

from langchain.tools import tool
from typing import Optional
from ..tools.explain_alarms import explain_alarms
from ..tools.retrieve_guidance import retrieve_guidance
from ..utils.logger import log_tool_call, log_error


@tool("qa_handler", return_direct=True)
def qa_handler(query: str, session_id: Optional[str] = None) -> str:
    """
    Handle user Q&A related to claim rejections, reviews, or appeal steps.

    Args:
        query (str): User message (e.g., "Why was my claim rejected?" or "How to appeal?")
        session_id (Optional[str]): Session ID for logging.

    Returns:
        str: Markdown-formatted empathetic answer with alarm reasoning + appeal guidance.
    """
    session_id = session_id or "anonymous"
    log_tool_call(session_id, "qa_handler", {"query": query[:100]})

    try:
        query_lower = query.lower()

        # ------------------------------------------------
        # 🎯 Step 1: Detect Intent (Why / How / Appeal)
        # ------------------------------------------------
        intent = "reason" if "why" in query_lower or "rejected" in query_lower else "appeal"

        response_parts = []

        # ------------------------------------------------
        # 🧩 Step 2: Handle Rejection Explanation
        # ------------------------------------------------
        if intent == "reason":
            response_parts.append("😔 **I’m sorry your claim was rejected. Let me explain what might have happened.**\n")
            # Try to extract alarm-related reasoning
            alarm_keywords = ["high amount", "late", "bank", "blacklist", "location", "keyword"]
            alarm_query = next((k for k in alarm_keywords if k in query_lower), "high_amount")

            alarm_explanation = explain_alarms(f"Explain {alarm_query} alarm", session_id)
            response_parts.append(alarm_explanation)
            response_parts.append("")

        # ------------------------------------------------
        # 🧾 Step 3: Provide Appeal or Next-Step Guidance
        # ------------------------------------------------
        response_parts.append("💡 **What you can do next:**")
        guidance_query = (
            "How to appeal a rejected claim?" if intent == "reason" else query
        )

        guidance_response = retrieve_guidance(guidance_query, session_id)
        response_parts.append(guidance_response)

        # ------------------------------------------------
        # 🧩 Step 4: Combine & Format Response
        # ------------------------------------------------
        response_parts.append(
            "\n💬 *Tip:* If you’d like, I can help you draft an appeal message or explain another alarm in detail."
        )

        return "\n\n".join(response_parts)

    except Exception as e:
        log_error(session_id, f"QA handler failed: {e}", query)
        return (
            "❌ **System Error:** I couldn’t retrieve your rejection details right now.\n"
            "Please try again or rephrase your question."
        )
