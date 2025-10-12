"""
Session State Utils
-------------------
Manages Streamlit session state:
- Generates persistent unique user/session IDs.
- Maintains message history between reruns.
- Provides helper functions for adding, clearing, and summarizing chat history.

Usage:
    session_id = get_session_id()
    add_message(st.session_state.messages, "user", "Hello!")
"""

import streamlit as st
from datetime import datetime
import hashlib
import secrets
from typing import List, Dict


# --------------------------------------------------------------------
# 🧠 SESSION ID HANDLING
# --------------------------------------------------------------------
def get_session_id() -> str:
    """
    Generate or retrieve a persistent unique session ID.

    Returns:
        str: 16-character hash (e.g., "a1b2c3d4e5f6g7h8")
    """
    if "session_id" not in st.session_state:
        # Create random + timestamp hash for uniqueness
        timestamp = datetime.utcnow().isoformat()
        random_bytes = secrets.token_bytes(16)
        seed = f"{timestamp}:{random_bytes.hex()}"
        st.session_state.session_id = hashlib.sha256(seed.encode()).hexdigest()[:16]

    return st.session_state.session_id


# --------------------------------------------------------------------
# 💬 CHAT HISTORY MANAGEMENT
# --------------------------------------------------------------------
def add_message(messages: List[Dict], role: str, content: str) -> None:
    """
    Append a message (user/assistant) to chat history.

    Args:
        messages (list): Streamlit session messages (e.g., st.session_state.messages)
        role (str): Either "user" or "assistant"
        content (str): Message text
    """
    if role not in {"user", "assistant"}:
        raise ValueError("Role must be either 'user' or 'assistant'.")

    timestamp = datetime.now().strftime("%H:%M:%S")

    messages.append({
        "role": role,
        "content": content.strip(),
        "timestamp": timestamp
    })


def clear_history(messages: List[Dict]) -> None:
    """
    Clear chat history and reset session ID.

    Args:
        messages (list): st.session_state.messages
    """
    messages.clear()
    if "session_id" in st.session_state:
        del st.session_state.session_id

    st.toast("Chat history cleared 🧹", icon="🗑️")


def get_history_summary(messages: List[Dict], max_items: int = 5) -> str:
    """
    Return a short summary of recent messages (for AI context or debugging).

    Args:
        messages (list): List of message dicts.
        max_items (int): Number of most recent messages to include.

    Returns:
        str: Truncated summary (e.g., "User: Check claim... | Assistant: Reviewed...")
    """
    if not messages:
        return "No previous chat history."

    recent = messages[-max_items:]
    summary_parts = []
    for msg in recent:
        role = "User" if msg["role"] == "user" else "Assistant"
        snippet = msg["content"][:50].replace("\n", " ").strip()
        summary_parts.append(f"{role}: {snippet}...")

    return " | ".join(summary_parts)
