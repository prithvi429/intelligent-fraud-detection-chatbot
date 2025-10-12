"""
Constants
---------
Hardcoded constants used throughout the FraudBot system.

Includes:
- Fraud alarm types and severity emojis
- Decision emojis (approve/reject/review)
- Guidance thresholds
- Session limits
- Supported languages
- Tool descriptions
- Common error messages

Usage:
    from chatbot.config.constants import ALARM_TYPES, DECISION_EMOJIS
"""

from typing import List, Dict

# ---------------------------------------
# 🚨 Fraud Alarm Types
# ---------------------------------------
ALARM_TYPES: List[str] = [
    "late_reporting",
    "new_bank",
    "out_of_network_provider",
    "blacklist_hit",
    "suspicious_text_phrases",
    "high_amount",
    "repeat_claimant",
    "suspicious_keywords",
    "location_mismatch",
    "duplicate_claims",
    "vendor_fraud",
    "time_patterns",
    "external_mismatch",
]

# ---------------------------------------
# ⚠️ Alarm Severity Emojis
# ---------------------------------------
ALARM_EMOJIS: Dict[str, str] = {
    "high": "🚨",
    "medium": "⚠️",
    "low": "ℹ️",
    "unknown": "❓",
}

# ---------------------------------------
# ✅ Decision Emojis
# ---------------------------------------
DECISION_EMOJIS: Dict[str, str] = {
    "approve": "✅",
    "review": "🔍",
    "reject": "❌",
}

# ---------------------------------------
# 📘 Guidance Settings
# ---------------------------------------
GUIDANCE_THRESHOLD: float = 0.7  # Min cosine similarity for match (can be overridden by settings)
MAX_GUIDANCE_RESULTS: int = 3    # Top-k results from Pinecone or DB

# ---------------------------------------
# 💬 Chat Session Limits
# ---------------------------------------
MAX_TOKENS: int = 4000           # Default token limit for LLM (can override in settings)
MAX_HISTORY_MESSAGES: int = 20   # Keep last N messages in memory

# ---------------------------------------
# 🌍 Supported Languages
# ---------------------------------------
SUPPORTED_LANGUAGES: List[str] = ["en"]  # English only for now

# ---------------------------------------
# 🧩 Tool Descriptions (Used in Agent Prompt)
# ---------------------------------------
TOOL_DESCRIPTIONS: Dict[str, str] = {
    "submit_and_score": "Use for analyzing claim details (amount, delay, notes) to detect fraud.",
    "explain_alarms": "Use for explaining specific alarms like 'high_amount' or 'late_reporting'.",
    "retrieve_guidance": "Use for policy or documentation-related questions.",
    "qa_handler": "Use for rejection or appeal Q&A, combining explanations and guidance.",
}

# ---------------------------------------
# ❗ Common Error Messages
# ---------------------------------------
ERROR_MESSAGES: Dict[str, str] = {
    "api_unavailable": "⚠️ Sorry, the backend is temporarily unavailable. Please try again later.",
    "invalid_query": "❓ I couldn't understand that. Please provide more details or rephrase your question.",
    "no_guidance": "📞 No specific guidance found. Please contact support@insurance.com for assistance.",
}
