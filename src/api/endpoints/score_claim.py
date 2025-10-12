"""
/score_claim Endpoint:
----------------------
Main API route for fraud scoring.
Runs rule-based and ML-based fraud detection, applies decision policy,
and returns a FraudResponse.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from src.models.claim import ClaimData
from src.models.fraud import FraudResponse, FraudAlarm, Decision, FraudFeatures, AlarmSeverity
from src.api.dependencies import get_db_session, require_ml_model, authenticated_user, get_claimant_context
from src.fraud_engine.alarms import check_all_alarms
from src.fraud_engine.ml_inference import get_fraud_probability
from src.fraud_engine.decision_policy import get_decision
from src.utils.db import save_claim_to_db
from src.utils.logger import logger
from src.config import config


router = APIRouter(tags=["Fraud Detection"])


@router.post(
    "/score_claim",
    response_model=FraudResponse,
    summary="Score a claim for fraud risk",
    description=(
        "Analyzes an insurance claim for potential fraud by running rule-based and ML-based checks. "
        "Returns alarms, probability, decision, and explanation."
    ),
)
async def score_claim_endpoint(
    claim_data: ClaimData,
    db: Session = Depends(get_db_session),
    ml_enabled: bool = Depends(require_ml_model),
    user: dict = Depends(authenticated_user),
    context: dict = Depends(get_claimant_context),
):
    try:
        logger.info(f"🚀 Scoring claim for user: {user.get('user_id', 'anonymous')} | Claimant: {claim_data.claimant_id}")

        # =========================================================
        # 1️⃣ Run Rule-Based Alarms (All 13 Types)
        # =========================================================
        raw_alarms = check_all_alarms(claim_data, db)
        alarms: List[FraudAlarm] = []

        for raw_alarm in raw_alarms:
            parts = raw_alarm.split(":", 1)
            alarm_type = parts[0].strip().lower().replace(" ", "_")
            description = parts[1].strip() if len(parts) > 1 else raw_alarm

            severity = (
                AlarmSeverity.HIGH
                if any(k in alarm_type for k in ["blacklist", "duplicate", "vendor", "external"])
                else AlarmSeverity.MEDIUM
            )

            alarms.append(
                FraudAlarm(
                    type=alarm_type,
                    description=description,
                    severity=severity,
                    evidence={"claim_id": claim_data.claimant_id, "timestamp": claim_data.timestamp},
                )
            )

        # =========================================================
        # 2️⃣ Prepare ML Features
        # =========================================================
        features = FraudFeatures(
            amount_normalized=claim_data.amount / 5000,  # Replace 5000 with DB mean
            delay_days=claim_data.report_delay_days,
            is_new_bank=claim_data.is_new_bank,
            is_out_of_network="out-of-network" in claim_data.provider.lower(),
            num_alarms=len(alarms),
            high_severity_count=len([a for a in alarms if a.severity == AlarmSeverity.HIGH]),
            repeat_count=context.get("prior_claims", 0),
        )

        # =========================================================
        # 3️⃣ Compute Fraud Probability
        # =========================================================
        if ml_enabled:
            fraud_prob = get_fraud_probability(features.to_array(), alarms, db)
        else:
            fraud_prob = min(1.0, len(alarms) * 0.1)  # Fallback: 10% per alarm

        # =========================================================
        # 4️⃣ Apply Decision Policy
        # =========================================================
        decision = get_decision(fraud_prob, len(alarms))

        # =========================================================
        # 5️⃣ Generate Explanation
        # =========================================================
        alarm_summaries = ", ".join([f"{a.type}: {a.description[:40]}..." for a in alarms[:3]]) or "No alarms triggered"

        if decision == Decision.REJECT:
            outcome_msg = "High risk – claim rejected due to critical fraud indicators."
        elif decision == Decision.REVIEW:
            outcome_msg = "Moderate risk – claim requires manual review."
        else:
            outcome_msg = "Low risk – claim approved automatically."

        explanation = (
            f"Fraud analysis complete for claim of ${claim_data.amount:.2f} from claimant {claim_data.claimant_id}. "
            f"Predicted fraud risk: {fraud_prob * 100:.1f}%. Decision: {decision.value}. "
            f"Detected {len(alarms)} alarms ({alarm_summaries}). {outcome_msg}"
        )

        # =========================================================
        # 6️⃣ Save to Database (with Fraud Metadata)
        # =========================================================
        try:
            save_claim_to_db(claim_data, db, fraud_prob, decision, alarms)
        except Exception as db_err:
            logger.warning(f"⚠️ Failed to save claim to DB: {str(db_err)}")

        # =========================================================
        # 7️⃣ Build Response
        # =========================================================
        logger.info(
            f"✅ Claim scored: {claim_data.claimant_id} | Prob: {fraud_prob * 100:.1f}% | Decision: {decision.value}"
        )

        return FraudResponse(
            fraud_probability=fraud_prob,
            alarms=alarms,
            decision=decision,
            explanation=explanation,
            features_used=features if config.DEBUG else None,
            recommendation=(
                "Submit supporting documents or appeal decision."
                if decision != Decision.APPROVE
                else None
            ),
        )

    # =========================================================
    # ❌ Exception Handling
    # =========================================================
    except ValueError as ve:
        logger.error(f"Validation error scoring claim: {ve}")
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(ve))

    except Exception as e:
        logger.exception(f"Internal error scoring claim: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")
