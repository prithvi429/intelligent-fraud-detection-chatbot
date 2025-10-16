"""
ML Inference for Fraud Probability
----------------------------------
- Loads a trained RandomForestClassifier (.pkl)
- Extracts normalized numerical + NLP + rule-based features
- Returns fraud probability (0–100%)

Supports fallback scoring if model unavailable.

Feature vector (14):
amount_normalized, delay_days, is_new_bank, is_out_network, num_alarms,
high_alarm_count, repeat_count, similarity, distance,
time_anomaly, keyword_count, sentiment, vendor_risk, external_mismatch.
"""

import os
import joblib
import numpy as np
from typing import Optional, List
from sqlalchemy.orm import Session
from datetime import datetime

from src.models.claim import ClaimData
from src.models.fraud import FraudFeatures
from src.config import config
from src.utils.logger import logger
from src.utils.external_apis import calculate_location_distance
from src.nlp.text_analyzer import analyze_text


# =========================================================
# 🔧 Global State
# =========================================================
model = None
is_model_loaded = False


# =========================================================
# 🚀 Model Loading
# =========================================================
def load_fraud_model(model_path: Optional[str] = None) -> bool:
    """Loads trained fraud model (.pkl). Falls back if unavailable."""
    global model, is_model_loaded
    path = model_path or getattr(config, "FRAUD_MODEL_PATH", "ml/fraud_model.pkl")

    if not os.path.exists(path):
        logger.warning(f"[ML] Model not found at '{path}' — using fallback mode.")
        return False

    try:
        model = joblib.load(path)
        is_model_loaded = True
        logger.info(f"[ML] ✅ Model loaded successfully from '{path}'.")
        return True
    except Exception as e:
        logger.error(f"[ML] ❌ Model loading failed: {e}")
        return False


# =========================================================
# ⚙️ Fallback Inference
# =========================================================
def _fallback_prob(alarms: List) -> float:
    """Simple rule-based fallback: 10% per alarm (max 100%)."""
    prob = min(100.0, len(alarms) * 10.0)
    logger.debug(f"[ML] Fallback fraud probability = {prob:.1f}% ({len(alarms)} alarms).")
    return prob


def get_fraud_probability(features_array: np.ndarray, alarms: list, db: Optional[Session] = None) -> float:
    """Predict fraud probability using ML model or fallback if unavailable."""
    global model, is_model_loaded

    if not is_model_loaded or model is None:
        logger.debug("[ML] Model not loaded — using fallback scoring.")
        return _fallback_prob(alarms)

    try:
        prob = float(model.predict_proba(features_array)[0][1]) * 100.0
        logger.debug(f"[ML] Predicted fraud probability = {prob:.1f}%")
        return prob
    except Exception as e:
        logger.error(f"[ML] ❌ Inference failed: {e}")
        return _fallback_prob(alarms)


# =========================================================
# 🧠 Feature Extraction
# =========================================================
def extract_features(claim: ClaimData, alarms: list, db: Optional[Session] = None) -> FraudFeatures:
    """
    Extracts numerical + derived features for fraud prediction.
    Combines rule-based, NLP, and contextual inputs.
    """
    try:
        # --- Base claim attributes ---
        amount_norm = round((claim.amount or 0) / 5000.0, 2)
        delay_days = getattr(claim, "report_delay_days", 0)
        is_new_bank = bool(getattr(claim, "is_new_bank", False))
        is_out_network = bool("out-of-network" in (claim.provider or "").lower())

        # --- Alarms summary ---
        num_alarms = len(alarms)
        high_alarm_count = sum("high" in str(a).lower() or "blacklist" in str(a).lower() for a in alarms)

        # --- Claim frequency (DB lookup optional) ---
        repeat_count = 0
        if db:
            try:
                result = db.execute("SELECT COUNT(*) FROM claims WHERE claimant_id = :id", {"id": claim.claimant_id})
                repeat_count = result.scalar() or 0
            except Exception as e:
                logger.warning(f"[ML] ⚠️ Repeat claim count query failed: {e}")

        # --- NLP insights ---
        nlp_result = analyze_text(claim.notes or "")
        similarity = round(nlp_result.get("max_similarity", 0.0), 3)
        keyword_count = nlp_result.get("keyword_count", 0)
        sentiment = nlp_result.get("sentiment", 0.0)

        # --- Geographic features ---
        registered_addr = "New York, NY"
        distance = calculate_location_distance(claim.location or "", registered_addr) or 0.0

        # --- Rule-derived anomaly indicators ---
        time_anomaly = int(any("time pattern" in str(a).lower() for a in alarms))
        vendor_risk = float(any("vendor fraud" in str(a).lower() for a in alarms))
        external_mismatch = int(any("external mismatch" in str(a).lower() for a in alarms))

        # ✅ Return structured FraudFeatures object
        features = FraudFeatures(
            amount_normalized=amount_norm,
            delay_days=delay_days,
            is_new_bank=is_new_bank,
            is_out_of_network=is_out_network,
            num_alarms=num_alarms,
            high_severity_count=high_alarm_count,
            repeat_count=repeat_count,
            text_similarity_score=similarity,
            location_distance=distance,
            time_anomaly_score=float(time_anomaly),
            suspicious_keyword_count=keyword_count,
            sentiment_score=sentiment,
            vendor_risk_score=vendor_risk,
            external_mismatch_count=external_mismatch,
        )

        logger.debug(f"[ML] ✅ Extracted features for {claim.claimant_id}: {features.model_dump()}")
        return features

    except Exception as e:
        logger.error(f"[ML] ❌ Feature extraction failed for {claim.claimant_id}: {e}")
        # ✅ Return safe zeroed-out feature set
        return FraudFeatures(
            amount_normalized=0.0,
            delay_days=0,
            is_new_bank=False,
            is_out_of_network=False,
            num_alarms=0,
            high_severity_count=0,
            repeat_count=0,
            text_similarity_score=0.0,
            location_distance=0.0,
            time_anomaly_score=0.0,
            suspicious_keyword_count=0,
            sentiment_score=0.0,
            vendor_risk_score=0.0,
            external_mismatch_count=0,
        )


# =========================================================
# 🧪 Synthetic Model Trainer (for testing)
# =========================================================
def train_synthetic_model(save_path: str = "ml/fraud_model.pkl"):
    """Trains a simple RandomForestClassifier on synthetic data for testing environments."""
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import roc_auc_score
    import pandas as pd

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    logger.info("[ML] 🧩 Training synthetic fraud model...")

    n = 1000
    df = pd.DataFrame({
        "amount": np.random.rand(n) * 3,
        "delay_days": np.random.randint(0, 30, n),
        "is_new_bank": np.random.randint(0, 2, n),
        "num_alarms": np.random.randint(0, 6, n),
        "sentiment": np.random.uniform(-1, 1, n),
    })

    df["fraud"] = ((df["amount"] > 2) | (df["num_alarms"] > 3) | (df["sentiment"] < -0.5)).astype(int)

    X = df.drop(columns=["fraud"])
    y = df["fraud"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    auc = roc_auc_score(y_test, model.predict_proba(X_test)[:, 1])
    logger.info(f"[ML] ✅ Synthetic model trained (AUC={auc:.3f})")

    joblib.dump(model, save_path)
    logger.info(f"[ML] 💾 Model saved at '{save_path}'")


# =========================================================
# 🧪 Manual Test
# =========================================================
if __name__ == "__main__":
    claim = ClaimData(
        amount=15000,
        provider="shady_clinic",
        notes="Quick cash claim with fake injury",
        location="Los Angeles, CA",
        claimant_id="user123",
        report_delay_days=8,
        is_new_bank=True,
    )

    alarms = [
        "High claim amount",
        "Vendor fraud: Provider risk 0.85",
        "Time pattern fraud",
    ]

    features = extract_features(claim, alarms)
    features_array = np.array([features.to_array()])  # ✅ to_array() method from FraudFeatures

    if not load_fraud_model():
        train_synthetic_model()
        load_fraud_model()

    prob = get_fraud_probability(features_array, alarms)
    print(f"\n🔮 Predicted Fraud Probability: {prob:.2f}%")
