"""
Formatter Utility
-----------------
Centralized output formatting for chatbot messages and tool responses.

Features:
- Cleans and beautifies chatbot responses (Markdown, JSON, plain text)
- Ensures consistent structure across all modules
- Prevents overly long or malformed outputs
- Backward-compatible with old function names

Usage:
    from chatbot.utils.formatter import format_chat_response, format_tool_output
"""

import json
import re
from typing import Any, Dict, Union


# =========================================================
# 🧠 Helper — Clean Markdown / Text Output
# =========================================================
def _clean_text(text: str) -> str:
    """Basic text cleaner: removes excessive whitespace and broken lines."""
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace(" .", ".").replace(" ,", ",")
    return text


# =========================================================
# 💬 Chat Response Formatter
# =========================================================
def format_chat_response(response: Union[str, Dict[str, Any]]) -> str:
    """
    Format chatbot responses for display (Markdown or plain text).

    Args:
        response (str | dict): The chatbot's generated text or structured output.

    Returns:
        str: Clean, readable string formatted for chat UI.
    """
    try:
        if response is None:
            return "⚠️ No response generated."

        # If dict or structured data → JSON pretty-print
        if isinstance(response, (dict, list)):
            return "```json\n" + json.dumps(response, indent=2, ensure_ascii=False) + "\n```"

        response = str(response).strip()

        # Clean weird tokens (e.g., LangChain artifacts)
        response = re.sub(r"(?i)Observation:|Thought:|Action:|Final Answer:", "", response)
        response = re.sub(r"```(json|python|markdown)?", "```", response)
        response = _clean_text(response)

        # Limit message length
        if len(response) > 5000:
            response = response[:5000] + "\n\n... ✂️ (truncated for display)"

        return response

    except Exception as e:
        return f"⚠️ Error while formatting response: {e}"


# =========================================================
# 🧰 Tool Output Formatter
# =========================================================
def format_tool_output(output: Any) -> str:
    """
    Format raw tool outputs (like API calls, RAG results, or fraud analysis).

    Args:
        output (Any): Raw tool result (dict, str, etc.)

    Returns:
        str: Human-readable formatted version (Markdown or JSON)
    """
    try:
        if output is None:
            return "⚠️ Tool returned no output."

        # JSON or dict-like structure
        if isinstance(output, (dict, list)):
            return "```json\n" + json.dumps(output, indent=2, ensure_ascii=False) + "\n```"

        # Convert to string
        text_output = str(output).strip()

        # Clean unnecessary newlines / whitespace
        text_output = re.sub(r"\n{3,}", "\n\n", text_output)
        text_output = _clean_text(text_output)

        # Truncate very long text (to avoid flooding)
        if len(text_output) > 4000:
            text_output = text_output[:4000] + "\n\n... ✂️ (output truncated)"

        return text_output

    except Exception as e:
        return f"⚠️ Error while formatting tool output: {e}"


# =========================================================
# 🔧 Optional Combined Formatter
# =========================================================
def format_combined_output(agent_response: str, tool_output: Any) -> str:
    """
    Combine both chatbot reasoning + tool response into one display block.

    Args:
        agent_response (str): Chatbot’s thought or explanation.
        tool_output (Any): Tool output or API result.

    Returns:
        str: Formatted Markdown block combining both.
    """
    formatted_agent = format_chat_response(agent_response)
    formatted_tool = format_tool_output(tool_output)

    return f"🧠 **Agent Reasoning:**\n\n{formatted_agent}\n\n📊 **Tool Output:**\n\n{formatted_tool}"


# =========================================================
# ✅ Summary
# =========================================================
# These are imported by other modules:
# from chatbot.utils.formatter import format_chat_response, format_tool_output
#
# Example:
# formatted = format_tool_output({"decision": "Reject", "probability": 92.5})
# print(formatted)
