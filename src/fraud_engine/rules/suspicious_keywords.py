"""
Suspicious Keywords Check
-------------------------
Scans claim notes for fraud-indicative language (e.g., “staged”, “fake”, “quick cash”).
Uses NLP text analysis to detect:
- Suspicious phrases (rule-based + NLP)
- Contextually risky tone or similarity
- Returns structured alarms for fraud engine

Example Output:
["[SUSPICIOUS-KW] 2 matches — 'staged', 'quick cash'"]
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from src.models.claim import ClaimData
from src.nlp.text_analyzer import analyze_text
from src.utils.logger import logger


def check_suspicious_keywords(claim: ClaimData, db: Optional[Session] = None) -> List[str]:
    """
    NLP-based fraud rule to identify suspicious keywords or phrases in claim notes.

    Args:
        claim (ClaimData): Input claim data.
        db (Session, optional): Unused; kept for consistent rule signature.

    Returns:
        List[str]: Fraud alarm messages.
    """
    alarms: List[str] = []
    notes = (getattr(claim, "notes", "") or "").strip()
    claimant_id = getattr(claim, "claimant_id", "unknown")

    if not notes:
        logger.debug("[SUSPICIOUS-KW] No claim notes provided — skipping NLP keyword check.")
        return alarms

    try:
        # 🔍 Run NLP analysis (cached inside text_analyzer)
        analysis = analyze_text(notes)

        keyword_count = int(analysis.get("keyword_count", 0))
        suspicious_phrases = analysis.get("suspicious_phrases", [])
        sentiment = analysis.get("sentiment", 0.0)

        # 🚨 Rule trigger: suspicious phrases found
        if keyword_count > 0:
            top_phrases = ", ".join(suspicious_phrases[:3]) if suspicious_phrases else "unknown phrases"
            alarms.append(
                f"[SUSPICIOUS-KW] {keyword_count} suspicious phrase"
                f"{'s' if keyword_count > 1 else ''} detected — {top_phrases}."
            )
            logger.info(
                f"[SUSPICIOUS-KW] 🚨 Claimant '{claimant_id}' — {keyword_count} flagged keyword(s): {top_phrases}"
            )

        # ⚠️ Sentiment-based signal (optional)
        elif sentiment < -0.5:
            alarms.append(
                f"[SUSPICIOUS-KW] Negative sentiment detected (score={sentiment:.2f}) — possible exaggeration or emotion."
            )
            logger.debug(f"[SUSPICIOUS-KW] {claimant_id}: Sentiment-only trigger (score={sentiment:.2f}).")

        else:
            logger.debug(f"[SUSPICIOUS-KW] {claimant_id}: No suspicious phrases or risky tone detected.")

    except Exception as e:
        logger.error(f"[SUSPICIOUS-KW] ❌ NLP analysis failed for {claimant_id}: {e}")

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

    print("\n🚨 Suspicious Keyword Alarms:")
    for alarm in check_suspicious_keywords(claim):
        print("•", alarm)
