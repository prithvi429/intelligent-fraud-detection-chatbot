"""
Suspicious Keywords Check
-------------------------
Scans claim notes for fraud-indicative language (e.g., “staged”, “fake”, “quick cash”).
Uses NLP text analysis to detect:
- Suspicious phrases (rule-based list)
- Contextually risky tone or similarity
- Returns structured alarms for fraud engine

Output Example:
["Suspicious keywords: 2 matches — 'staged', 'quick cash'"]
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from src.models.claim import ClaimData
from src.nlp.text_analyzer import analyze_text
from src.utils.logger import logger


def check_suspicious_keywords(claim: ClaimData, db: Optional[Session] = None) -> List[str]:
    """
    NLP-based fraud rule to identify suspicious keywords/phrases in claim notes.

    Args:
        claim (ClaimData): Input claim data.
        db (Session, optional): Unused (for signature consistency).

    Returns:
        List[str]: Fraud alarm messages.
    """
    alarms: List[str] = []
    notes = (claim.notes or "").strip()

    if not notes:
        logger.debug("[SUSPICIOUS-KW] Empty notes — skipping keyword analysis.")
        return alarms

    try:
        # Run NLP analysis (caches automatically)
        analysis = analyze_text(notes)
        keyword_count = int(analysis.get("keyword_count", 0))
        suspicious_phrases = analysis.get("suspicious_phrases", [])

        # Trigger alarm if any keywords matched
        if keyword_count > 0:
            top_phrases = ", ".join(suspicious_phrases[:3])  # Show top 3
            alarm_text = (
                f"Suspicious keywords: {keyword_count} match"
                f"{'es' if keyword_count > 1 else ''} — {top_phrases}"
            )
            alarms.append(alarm_text)
            logger.debug(f"[SUSPICIOUS-KW] {claim.claimant_id}: {keyword_count} suspicious phrase(s) → {top_phrases}")

        else:
            logger.debug(f"[SUSPICIOUS-KW] {claim.claimant_id}: No suspicious keywords found.")

    except Exception as e:
        logger.error(f"[SUSPICIOUS-KW] NLP analysis failed for {claim.claimant_id}: {e}")

    return alarms


# =========================================================
# 🧪 Manual Test
# =========================================================
if __name__ == "__main__":
    from src.models.claim import ClaimData

    claim = ClaimData(
        amount=5000,
        provider="ABC Hospital",
        claimant_id="user_demo",
        notes="This was a staged accident for quick cash."
    )

    print("🚨 Alarms:", check_suspicious_keywords(claim))
