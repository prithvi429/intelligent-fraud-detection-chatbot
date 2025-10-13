"""
Fraud Engine Constants
----------------------
Centralized constants shared across fraud, NLP, and chatbot modules.
"""

# ⚙️ Suspicious Phrases (shared between NLP + Fraud Engine)
SUSPICIOUS_PHRASES = [
    "staged accident",
    "fake injury",
    "quick cash",
    "exaggerated pain",
    "ghost patient",
    "duplicate claim",
    "cash only",
    "out-of-network",
    "new bank account",
    "late reporting",
    "blacklist hit",
    "fake vendor",
    "fraudulent billing",
    "false invoice",
    "no witnesses",
    "inflated bill",
]

# 💰 Fraud Detection Thresholds
HIGH_AMOUNT_THRESHOLD = 10000  # USD threshold for high claim risk
SIMILARITY_THRESHOLD = 0.85    # Text similarity (duplicate claims)
LATE_REPORT_THRESHOLD_DAYS = 7
DUPLICATE_WINDOW_DAYS = 30

# ⚠️ Mock Data for Tests
BLACKLIST_PROVIDERS = ["shady_clinic", "fake_vendor", "ghost_hospital"]
