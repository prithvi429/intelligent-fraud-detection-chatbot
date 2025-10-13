"""
Explanation Service
-------------------
Maps alarm names to descriptive explanations for users.
"""

EXPLANATIONS = {
    "high_amount": {"description": "Claim amount exceeds typical policy range."},
    "shady_provider": {"description": "Provider appears on internal watchlist or has prior fraudulent activity."},
    "delayed_report": {"description": "Claim reported with unusual delay after incident."},
    "new_bank": {"description": "Recent bank account may indicate fraudulent intent."},
}


def get_explanation_for_alarm(alarm_name: str):
    """Fetch explanation for a specific alarm trigger."""
    return EXPLANATIONS.get(alarm_name)
