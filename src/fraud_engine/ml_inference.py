"""
ML Inference for Fraud Probability
----------------------------------
- Loads a trained RandomForestClassifier model (.pkl).
- Extracts numeric features from ClaimData and alarms.
- Returns fraud probability (0–100%).
- Fallback: Rule-based scoring if model unavailable.

Features used (14):
amount, delay_days, is_new_bank, is_out_of_network, num_alarms,
high_alarm_count, repeat_count, similarity_score, location_distance,
time_anomaly, keyword_count, sentiment, vendor_risk, external_mismatch.
"""

import os
import joblib
import numpy as np
from typing import Optional, List
from sqlalchemy.orm import Session
from src.models.claim import ClaimData
from src.models.fraud import FraudFeatures
from src.config import config
from src.utils.logger import logger
from src.utils.external_apis import calculate_location_distance
from src.nlp.text_analyzer import analyze_text
from datetime import datetime

# Global model (lazy loaded)
model = None
is_model_loaded = False


# =========================================================
# 🚀 MODEL LOADING
# =========================================================
def load_fraud_model(model_path: Optional[str] = None) -> bool:
    """Load trained model at startup."""
    global model, is_model_loaded
    path = model_path or config.FRAUD_MODEL_PATH

    if not os.path.exists(path):
        logger.warning(f"[ML] Model not found at {path} — using fallback.")
        return False

    try:
        model = joblib.load(path)
        is_model_loaded = True
        logger.info(f"[ML] ✅ Loaded fraud model from {path}. Classes: {model.classes_}")
        return True
    except Exception as e:
        logger.error(f"[ML] Error loading model: {e}")
        return False


# =========================================================
# ⚙️ FALLBACK & INFERENCE
# =========================================================
def _fallback_prob(alarms: List) -> float:
    """Simple rule-based fallback: 10% per alarm, capped at 100."""
    prob = min(100.0, len(alarms) * 10.0)
    logger.debug(f"[ML] Fallback probability = {prob:.1f}% ({len(alarms)} alarms)")
    return prob


def get_fraud_probability(features_array: np.ndarray, alarms: list, db: Optional[Session] = None) -> float:
    """Predict fraud probability using model or fallback."""
    global model, is_model_loaded

    if model is None or not is_model_loaded:
        return _fallback_prob(alarms)

    try:
        prob = model.predict_proba(features_array)[0][1] * 100  # Class 1 = fraud
        logger.debug(f"[ML] Predicted fraud probability = {prob:.1f}%")
        return prob
    except Exception as e:
        logger.error(f"[ML] Inference failed: {e}")
        return _fallback_prob(alarms)


# =========================================================
# 🧠 FEATURE EXTRACTION
# =========================================================
def extract_features(claim: ClaimData, alarms: list, db: Optional[Session] = None) -> FraudFeatures:
    """
    Extract features from ClaimData + alarms.
    Returns FraudFeatures (for model input).
    """

    # --- Base claim features ---
    amount_norm = round(claim.amount / 5000.0, 2)
    delay_days = getattr(claim, "report_delay_days", 0)
    is_new_bank = 1 if getattr(claim, "is_new_bank", False) else 0
    is_out_network = 1 if "out-of-network" in (claim.provider or "").lower() else 0

    # --- Alarms summary ---
    num_alarms = len(alarms)
    high_alarm_count = sum("high" in str(a).lower() or "blacklist" in str(a).lower() for a in alarms)

    # --- Repeat claimant history (mock/DB) ---
    repeat_count = 0
    if db:
        try:
            result = db.execute(
                "SELECT COUNT(*) FROM claims WHERE claimant_id = :id", {"id": claim.claimant_id}
            )
            repeat_count = result.scalar() or 0
        except Exception as e:
            logger.warning(f"[ML] DB repeat query failed: {e}")

    # --- NLP signals ---
    text_results = analyze_text(claim.notes or "")
    similarity = round(text_results.get("max_similarity", 0.0), 3)
    keyword_count = text_results.get("keyword_count", 0)
    sentiment = text_results.get("sentiment", 0.0)

    # --- Geo signals ---
    registered_addr = "New York, NY"
    distance = calculate_location_distance(claim.location or "", registered_addr) or 0.0

    # --- Time anomaly ---
    time_anomaly = 1 if any("time pattern" in str(a).lower() for a in alarms) else 0

    # --- Vendor / external mismatch flags ---
    vendor_risk = 1 if any("vendor fraud" in str(a).lower() for a in alarms) else 0
    external_mismatch = 1 if any("external mismatch" in str(a).lower() for a in alarms) else 0

    # --- Build feature vector ---
    features = [
        amount_norm, delay_days, is_new_bank, is_out_network,
        num_alarms, high_alarm_count, repeat_count, similarity,
        distance, time_anomaly, keyword_count, sentiment,
        vendor_risk, external_mismatch
    ]

    logger.debug(f"[ML] Extracted features: {features}")

    # Wrap in FraudFeatures dataclass (if implemented)
    return FraudFeatures(values=features)


# =========================================================
# 🧪 TRAINING (SYNTHETIC DEMO)
# =========================================================
def train_synthetic_model(save_path: str = "ml/fraud_model.pkl"):
    """
    Train a simple RandomForest model on synthetic data for testing.
    """
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import roc_auc_score, classification_report
    import pandas as pd

    logger.info("[ML] Training synthetic fraud model...")

    # Create mock data
    n = 1000
    data = pd.DataFrame({
        "amount": np.random.rand(n) * 3,
        "delay_days": np.random.randint(0, 30, n),
        "is_new_bank": np.random.randint(0, 2, n),
        "num_alarms": np.random.randint(0, 6, n),
        "sentiment": np.random.uniform(-1, 1, n),
    })
    # Synthetic target
    data["fraud"] = (
        (data["amount"] > 2) |
        (data["num_alarms"] > 3) |
        (data["sentiment"] < -0.5)
    ).astype(int)

    X = data.drop("fraud", axis=1)
    y = data["fraud"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)

    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    auc = roc_auc_score(y_test, y_prob)
    logger.info(f"[ML] Synthetic model trained (AUC={auc:.3f})")

    joblib.dump(model, save_path)
    logger.info(f"[ML] Model saved → {save_path}")


# =========================================================
# 🧪 Manual Test
# =========================================================
if __name__ == "__main__":
    from src.models.claim import ClaimData

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
        "Time pattern fraud"
    ]

    features = extract_features(claim, alarms)
    features_array = np.array([features.values])

    if not load_fraud_model():
        train_synthetic_model()  # Create one if missing
        load_fraud_model()

    prob = get_fraud_probability(features_array, alarms)
    print(f"Predicted Fraud Probability: {prob:.2f}%")
