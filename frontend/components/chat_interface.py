"""
Chat Interface Component
------------------------
Displays formatted chat history between user and assistant.
- Differentiates by role (user / assistant).
- Applies color styling for risk levels (high, medium, low).
- Optionally includes timestamps.

Usage:
    display_chat_history(messages: list)
"""

import streamlit as st
from datetime import datetime


def display_chat_history(messages: list) -> None:
    """
    Render chat messages sequentially in Streamlit’s chat layout.

    Args:
        messages (list): A list of dicts with keys → {"role": "user"/"assistant", "content": str, "timestamp": optional}.
    """
    if not messages:
        st.info("Start a conversation by typing below 👇")
        return

    for msg in messages:
        role = msg.get("role", "assistant")
        content = msg.get("content", "")
        timestamp = msg.get("timestamp")

        # Choose role icon
        icon = "🧑‍💼" if role == "user" else "🤖"

        with st.chat_message(role, avatar=icon):
            # Timestamp (optional)
            if timestamp:
                st.caption(f"🕓 {timestamp}")

            # Highlight based on fraud-related keywords
            content_lower = content.lower()
            if any(k in content_lower for k in ["high risk", "fraud", "reject"]):
                st.markdown(f'<div class="high-risk">{content}</div>', unsafe_allow_html=True)
            elif any(k in content_lower for k in ["review", "medium risk"]):
                st.markdown(f'<div class="medium-risk">{content}</div>', unsafe_allow_html=True)
            elif any(k in content_lower for k in ["approve", "low risk"]):
                st.markdown(f'<div class="low-risk">{content}</div>', unsafe_allow_html=True)
            else:
                st.markdown(content)


def format_message(role: str, content: str) -> dict:
    """
    Helper: Create a message dict with timestamp (for saving to session state).

    Example:
        add_message(st.session_state, format_message("user", "Hello!"))
    """
    return {
        "role": role,
        "content": content.strip(),
        "timestamp": datetime.now().strftime("%H:%M:%S"),
    }
