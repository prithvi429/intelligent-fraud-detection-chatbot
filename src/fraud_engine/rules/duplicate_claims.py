"""
Duplicate Claims Check
----------------------
Detects potential duplicate or near-identical claim notes from the same claimant.

How it works:
- Fetches up to 5 previous claim notes for the same claimant.
- Computes cosine similarity using SentenceTransformer embeddings.
- If similarity > threshold (e.g., 0.8), flags a duplicate alarm.

Example output:
["[DUPLICATE-CLAIM] 85% text similarity to prior claim (threshold: 80%)"]
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from src.models.claim import ClaimData
from src.config import config
from src.nlp.text_analyzer import get_text_similarity
from src.utils.logger import logger


def check_duplicate_claims(claim: ClaimData, db: Optional[Session] = None) -> List[str]:
    """
    NLP-based rule to detect duplicate or near-duplicate claims by the same claimant.

    Args:
        claim (ClaimData): The current claim being analyzed.
        db (Session, optional): SQLAlchemy DB session to fetch historical claims.

    Returns:
        List[str]: Fraud alarm messages (if any).
    """
    alarms: List[str] = []
    notes = (claim.notes or "").strip()

    # 🧩 Early exits
    if not notes:
        logger.debug("[DUPLICATE-CLAIM] No notes provided — skipping check.")
        return alarms

    if not db:
        logger.debug("[DUPLICATE-CLAIM] No DB connection — cannot fetch past claims.")
        return alarms

    try:
        # =========================================================
        # 🗄️ Fetch up to 5 past claims for same claimant
        # =========================================================
        sql = text("""
            SELECT notes FROM claims
            WHERE claimant_id = :claimant_id
              AND notes IS NOT NULL
              AND LENGTH(notes) > 10
            ORDER BY created_at DESC
            LIMIT 5
        """)
        result = db.execute(sql, {"claimant_id": claim.claimant_id})
        past_notes = [row[0].strip() for row in result.fetchall() if row[0] and row[0].strip()]

        if not past_notes:
            logger.debug(f"[DUPLICATE-CLAIM] No previous notes found for claimant '{claim.claimant_id}'.")
            return alarms

        # =========================================================
        # 🔍 Compare note similarity
        # =========================================================
        max_similarity = 0.0
        for past_note in past_notes:
            try:
                sim = get_text_similarity(notes, past_note)
                max_similarity = max(max_similarity, sim)
            except Exception as e:
                logger.warning(f"[DUPLICATE-CLAIM] Similarity check failed for claimant {claim.claimant_id}: {e}")

        threshold = getattr(config, "SIMILARITY_THRESHOLD", 0.8)
        logger.debug(
            f"[DUPLICATE-CLAIM] Max similarity={max_similarity:.2f} | Threshold={threshold:.2f}"
        )

        # =========================================================
        # 🚨 Flag duplicates
        # =========================================================
        if max_similarity > threshold:
            alarms.append(
                f"[DUPLICATE-CLAIM] {max_similarity:.1%} text similarity to prior claim "
                f"(threshold: {threshold:.1%})."
            )
            logger.info(f"[DUPLICATE-CLAIM] 🚨 Duplicate detected for claimant '{claim.claimant_id}'.")

    except Exception as e:
        logger.error(f"[DUPLICATE-CLAIM] Error during duplicate analysis for {claim.claimant_id}: {e}")

    return alarms


# =========================================================
# 🧪 Manual Test
# =========================================================
if __name__ == "__main__":
    from src.models.claim import ClaimData

    dummy_claim = ClaimData(
        amount=7500,
        provider="CityCare Hospital",
        claimant_id="user_demo",
        notes="Car accident on highway, minor injury.",
        location="LA"
    )

    alarms = check_duplicate_claims(dummy_claim)
    print("\n🚨 Duplicate Claim Alarms:", alarms)
