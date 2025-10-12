"""
ML Inference for Fraud Probability
----------------------------------
- Loads local RandomForest model from `.pkl` (trained with SageMaker train.py).
- Extracts FraudFeatures from ClaimData + alarms.
- Predicts fraud probability (0–100%).
- Falls back to:
    1. SageMaker endpoint (if AWS runtime & endpoint active).
    2. Rule-based scoring (if no model).
"""

import os
import json
import joblib
import boto3
import numpy as np
from typing import Optional, List
from sqlalchemy.orm import Session

from src.models.claim import ClaimData
from src.models.fraud import FraudFeatures
from src.config import config
from src.utils.logger import logger
from src.nlp.text_analyzer import analyze_text
from src.utils.external_apis import calculate_location_distance

# Global model variables
model = None
is_model_loaded = False


# =========================================================
# 🧩 Model Load / Health
# =========================================================
def load_fraud_model(model_path: Optional[str] = None) -> bool:
    """
    Load trained RandomForest model from .pkl.
    Called on app startup in main.py.
    """
    global model, is_model_loaded
    path = model_path or config.FRAUD_MODEL_PATH

    if not os.path.exists(path):
        logger.warning(f"⚠️ Fraud model not found at {path} — using rule-based or SageMaker fallback.")
        return False

    try:
        model = joblib.load(path)
        is_model_loaded = True
        logger.info(f"✅ Fraud ML model loaded from {path}")
        return True
    except Exception as e:
        logger.error(f"❌ Error loading ML model: {e}")
        model = None
        is_model_loaded = False
        return False


def is_model_available() -> bool:
    """Check if local model is loaded."""
    return bool(model and is_model_loaded)


# =========================================================
# ☁️ AWS SageMaker Inference (Remote)
# =========================================================
def get_sagemaker_prediction(features_array: np.ndarray, endpoint_name: str) -> float:
    """
    Send feature array to deployed SageMaker endpoint.
    Returns fraud probability (%).
    """
    try:
        runtime = boto3.client("sagemaker-runtime", region_name=config.AWS_REGION)
        features_csv_str = ",".join(map(str, features_array.flatten()))

        response = runtime.invoke_endpoint(
            EndpointName=endpoint_name,
            ContentType="text/csv",
            Body=features_csv_str
        )

        result = json.loads(response["Body"].read().decode("utf-8"))
        prob = result.get("score") or result.get("fraud_probability") or 0.0

        logger.info(f"SageMaker inference → {prob:.2%}")
        return float(prob) * 100

    except Exception as e:
        logger.error(f"SageMaker inference failed: {e}")
        return 0.0  # fallback


# =========================================================
# 🧠 Local Model Inference (RandomForest)
# =========================================================
def get_fraud_probability(features_array: np.ndarray, alarms: List[str]) -> float:
    """
    Predict fraud probability using local ML model or fallback.
    """
    if not is_model_available():
        # Rule-based fallback: 10% per alarm
        fallback_prob = min(100.0, len(alarms) * 10.0)
        logger.debug(f"Rule-based fallback fraud probability: {fallback_prob:.1f}%")
        return fallback_prob

    try:
        prob = model.predict_proba(features_array)[0][1] * 100
        logger.debug(f"Local model prediction: {prob:.1f}%")
        return prob
    except Exception as e:
        logger.error(f"Local model inference failed: {e}")
        return min(100.0, len(alarms) * 10.0)


# =========================================================
# 🧩 Feature Extraction (Claim → Model Input)
# =========================================================
def extract_features(claim: ClaimData, alarms: List[str], db: Optional[Session] = None) -> FraudFeatures:
    """
    Extract structured features from claim + alarms for ML model input.
    """
    # Basic numerical and categorical features
    amount_normalized = claim.amount / 5000.0  # normalize
    delay_days = claim.report_delay_days
    is_new_bank = 1 if claim.is_new_bank else 0
    is_out_of_network = 1 if "out-of-network" in claim.provider.lower() else 0

    # From alarms (derived)
    num_alarms = len(alarms)
    high_severity_count = sum(
        1 for a in alarms if any(keyword in a.lower() for keyword in ["high", "blacklist", "duplicate"])
    )

    # Text analysis
    text_results = analyze_text(claim.notes)
    text_similarity_score = text_results.get("max_similarity", 0.0)
    suspicious_keyword_count = text_results.get("keyword_count", 0)
    sentiment_score = text_results.get("sentiment", 0.0)

    # Location distance (mock fallback)
    registered_addr = "New York, NY"
    location_distance = calculate_location_distance(claim.location, registered_addr) or 0.0

    # Temporal anomaly (flag if time-based alarms exist)
    time_anomaly_score = 1.0 if any("time pattern" in a.lower() for a in alarms) else 0.0

    # Vendor / external features
    vendor_risk_score = 0.8 if any("vendor fraud" in a.lower() for a in alarms) else 0.0
    external_mismatch_count = sum(1 for a in alarms if "external mismatch" in a.lower())

    # Historical features (if DB available)
    repeat_count = 0
    if db:
        try:
            result = db.execute(
                "SELECT COUNT(*) FROM claims WHERE claimant_id = :cid",
                {"cid": claim.claimant_id}
            )
            repeat_count = result.scalar() or 0
        except Exception as e:
            logger.warning(f"DB query failed for repeat_count: {e}")

    return FraudFeatures(
        amount_normalized=amount_normalized,
        delay_days=delay_days,
        is_new_bank=is_new_bank,
        is_out_of_network=is_out_of_network,
        num_alarms=num_alarms,
        high_severity_count=high_severity_count,
        repeat_count=repeat_count,
        text_similarity_score=text_similarity_score,
        location_distance=location_distance,
        time_anomaly_score=time_anomaly_score,
        suspicious_keyword_count=suspicious_keyword_count,
        sentiment_score=sentiment_score,
        vendor_risk_score=vendor_risk_score,
        external_mismatch_count=external_mismatch_count
    )


# =========================================================
# 🚀 Main Fraud Prediction Orchestrator
# =========================================================
def predict_fraud_probability(claim: ClaimData, alarms: List[str], db: Optional[Session] = None) -> float:
    """
    Main orchestrator: extract features → infer via ML or SageMaker → return fraud probability.
    """
    features = extract_features(claim, alarms, db)
    features_array = np.array([features.to_array()])

    # Choose inference mode
    if config.is_aws_runtime:
        logger.info("Using AWS SageMaker inference.")
        prob = get_sagemaker_prediction(features_array, "fraud-detection-endpoint-v1")
    else:
        logger.info("Using local model inference.")
        prob = get_fraud_probability(features_array, alarms)

    logger.info(f"🧮 Final fraud probability for {claim.claimant_id}: {prob:.2f}%")
    return prob


# =========================================================
# 🧪 Manual Test
# =========================================================
if __name__ == "__main__":
    from src.models.claim import ClaimData
    from datetime import datetime as dt

    claim = ClaimData(
        amount=12000,
        provider="Shady Clinic",
        claimant_id="user123",
        report_delay_days=10,
        is_new_bank=True,
        location="Los Angeles, CA",
        notes="Staged accident for quick cash.",
        timestamp=dt.now(),
    )

    alarms = ["High claim amount", "Vendor fraud: Shady Clinic", "Suspicious keywords: staged accident"]

    print("\n🔍 Running test inference...\n")
    load_fraud_model()
    prob = predict_fraud_probability(claim, alarms)
    print(f"Fraud Probability: {prob:.2f}%")
