"""
Local ML Training
-----------------
- Loads processed CSVs from ml/data/processed/.
- Trains RandomForestClassifier for fraud detection.
- Evaluates model (AUC, precision, recall, F1).
- Saves: model (.pkl) + preprocessors (imputer/scaler).
- Focus: Fraud recall > 0.8.
Run:
    python src/ml/train.py --hyperparams '{"n_estimators": 200, "max_depth": 15}'
Output:
    ml/fraud_model.pkl
"""

import argparse
import json
import os
import joblib
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score, precision_recall_fscore_support, classification_report
from sklearn.model_selection import train_test_split, RandomizedSearchCV
from src.config import config
from src.utils.logger import logger

# =========================================================
# 🧩 Constants
# =========================================================
PROCESSED_TRAIN = "ml/data/processed/train.csv"
PROCESSED_TEST = "ml/data/processed/test.csv"
MODEL_PATH = config.FRAUD_MODEL_PATH  # Default: ml/fraud_model.pkl
PREPROCESSORS_PATH = MODEL_PATH.replace(".pkl", "_preprocessors.pkl")

FEATURES = [
    "amount_normalized", "delay_days", "is_new_bank", "is_out_of_network", "num_alarms",
    "high_severity_count", "repeat_count", "text_similarity_score", "location_distance",
    "time_anomaly_score", "suspicious_keyword_count", "sentiment_score",
    "vendor_risk_score", "external_mismatch_count"
]
LABEL_COL = "fraud_label"


# =========================================================
# ⚙️ Load Data
# =========================================================
def load_data(train_path: str, test_path: str):
    """Load train and test CSVs."""
    train_df = pd.read_csv(train_path)
    test_df = pd.read_csv(test_path)

    X_train, y_train = train_df[FEATURES], train_df[LABEL_COL]
    X_test, y_test = test_df[FEATURES], test_df[LABEL_COL]

    logger.info(f"✅ Loaded data: Train {X_train.shape}, Test {X_test.shape}")
    logger.info(f"Fraud ratio (train): {y_train.mean():.2%}, (test): {y_test.mean():.2%}")

    return X_train, y_train, X_test, y_test


# =========================================================
# 🧹 Preprocess
# =========================================================
def preprocess_data(X_train: pd.DataFrame, X_test: pd.DataFrame):
    """Impute missing values and scale."""
    imputer = SimpleImputer(strategy="median")
    scaler = StandardScaler()

    X_train_imp = imputer.fit_transform(X_train)
    X_test_imp = imputer.transform(X_test)

    X_train_scaled = scaler.fit_transform(X_train_imp)
    X_test_scaled = scaler.transform(X_test_imp)

    logger.info("✅ Data preprocessing complete (imputed + scaled).")
    return X_train_scaled, X_test_scaled, imputer, scaler


# =========================================================
# 🧠 Model Training
# =========================================================
def train_model(X_train, y_train, hyperparams: dict = None) -> RandomForestClassifier:
    """Train RandomForest model (with optional tuning)."""
    hyperparams = hyperparams or {
        "n_estimators": 150,
        "max_depth": 12,
        "min_samples_split": 4,
        "random_state": 42,
        "n_jobs": -1
    }

    model = RandomForestClassifier(**hyperparams)
    model.fit(X_train, y_train)

    logger.info(f"✅ Model trained with params: {hyperparams}")
    return model


# =========================================================
# 🧪 Evaluation
# =========================================================
def evaluate_model(model, X_test, y_test):
    """Evaluate trained model on test set."""
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    auc = roc_auc_score(y_test, y_proba)
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_test, y_pred, average="binary", zero_division=0
    )

    metrics = {
        "AUC": round(auc, 3),
        "Precision": round(precision, 3),
        "Recall": round(recall, 3),
        "F1": round(f1, 3),
    }

    logger.info(f"📊 Evaluation Metrics: {json.dumps(metrics, indent=2)}")
    logger.info("Detailed Classification Report:\n" + classification_report(y_test, y_pred))
    return metrics


# =========================================================
# 💾 Save Artifacts
# =========================================================
def save_model(model, imputer, scaler):
    """Save model and preprocessing objects."""
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    joblib.dump((imputer, scaler), PREPROCESSORS_PATH)
    logger.info(f"✅ Model saved: {MODEL_PATH}")
    logger.info(f"✅ Preprocessors saved: {PREPROCESSORS_PATH}")


# =========================================================
# 🚀 Main Workflow
# =========================================================
def main(hyperparams: dict = None):
    """Main training flow."""
    if not os.path.exists(PROCESSED_TRAIN):
        logger.error("❌ Processed data not found. Run `preprocess.py --generate` first.")
        return

    # Load & preprocess
    X_train, y_train, X_test, y_test = load_data(PROCESSED_TRAIN, PROCESSED_TEST)
    X_train_scaled, X_test_scaled, imputer, scaler = preprocess_data(X_train, X_test)

    # Train
    model = train_model(X_train_scaled, y_train, hyperparams)

    # Evaluate
    metrics = evaluate_model(model, X_test_scaled, y_test)
    if metrics["Recall"] < 0.8:
        logger.warning(f"⚠️ Low fraud recall ({metrics['Recall']:.2f}). Consider hyperparam tuning or rebalancing.")

    # Save
    save_model(model, imputer, scaler)

    logger.info("🎯 Training complete.")


# =========================================================
# 🧩 CLI Entry
# =========================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train local fraud detection model.")
    parser.add_argument(
        "--hyperparams",
        type=str,
        help="JSON string for model hyperparameters, e.g. '{\"n_estimators\": 200, \"max_depth\": 15}'",
        default="{}"
    )
    args = parser.parse_args()
    try:
        hyperparams = json.loads(args.hyperparams)
    except json.JSONDecodeError:
        hyperparams = {}

    main(hyperparams)
