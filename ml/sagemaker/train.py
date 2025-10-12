"""
SageMaker Training Script (Entry Point)
---------------------------------------
Trains a RandomForestClassifier for insurance fraud detection.

📘 Features:
- Input: S3 channels → train/validation CSVs with 14 features + 'fraud_label' (0/1)
- Preprocessing: Imputation (median), StandardScaler
- Training: RandomForestClassifier (configurable via hyperparameters)
- Evaluation: AUC, Precision, Recall, F1 (recall prioritized)
- Output: 
    - /opt/ml/model/fraud_model.joblib
    - /opt/ml/model/preprocessors.joblib
    - /opt/ml/output/metrics.json, report.json

Logs to CloudWatch automatically.
"""

import os
import json
import joblib
import argparse
import logging
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    roc_auc_score,
    precision_recall_fscore_support,
    classification_report,
)
import boto3

# ------------------------------
# Logging Configuration
# ------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ------------------------------
# SageMaker Environment Paths
# ------------------------------
MODEL_DIR = os.environ.get("SM_MODEL_DIR", "/opt/ml/model")
OUTPUT_DIR = os.environ.get("SM_OUTPUT_DATA_DIR", "/opt/ml/output")
TRAIN_DIR = os.environ.get("SM_CHANNEL_TRAINING", "/opt/ml/input/data/training")
VAL_DIR = os.environ.get("SM_CHANNEL_VALIDATION", "/opt/ml/input/data/validation")

# ------------------------------
# Feature Columns
# ------------------------------
FEATURES = [
    "amount_normalized", "delay_days", "is_new_bank", "is_out_of_network", "num_alarms",
    "high_severity_count", "repeat_count", "text_similarity_score", "location_distance",
    "time_anomaly_score", "suspicious_keyword_count", "sentiment_score", "vendor_risk_score",
    "external_mismatch_count"
]
LABEL_COL = "fraud_label"

# ------------------------------
# Helper Functions
# ------------------------------
def parse_hyperparams() -> dict:
    """Read SageMaker hyperparameters JSON."""
    params_path = os.path.join("/opt/ml/input/config", "hyperparameters.json")
    if os.path.exists(params_path):
        with open(params_path, "r") as f:
            return json.load(f)
    return {}

def load_data(data_dir: str) -> pd.DataFrame:
    """Load CSV file from SageMaker channel."""
    files = [f for f in os.listdir(data_dir) if f.endswith(".csv")]
    if not files:
        raise FileNotFoundError(f"No CSV found in {data_dir}")
    file_path = os.path.join(data_dir, files[0])
    df = pd.read_csv(file_path)
    logger.info(f"Loaded {file_path}: {df.shape[0]} rows, {df.shape[1]} cols")
    return df

def preprocess_data(df: pd.DataFrame, fit: bool = True, imputer=None, scaler=None):
    """Impute missing values and scale features."""
    X = df[FEATURES].copy()
    y = df[LABEL_COL].astype(int)

    if fit:
        imputer = SimpleImputer(strategy="median").fit(X)
        scaler = StandardScaler().fit(imputer.transform(X))

    X_imp = imputer.transform(X)
    X_scaled = scaler.transform(X_imp)

    return X_scaled, y, imputer, scaler

def train_model(X_train, y_train, hyperparams: dict):
    """Train RandomForest model."""
    model = RandomForestClassifier(
        n_estimators=int(hyperparams.get("n_estimators", 100)),
        max_depth=int(hyperparams.get("max_depth", 10)),
        min_samples_split=int(hyperparams.get("min_samples_split", 5)),
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)
    logger.info(f"Model trained: {model.n_estimators} trees, max_depth={model.max_depth}")
    return model

def evaluate_model(model, X_val, y_val):
    """Compute validation metrics and save JSON reports."""
    y_pred = model.predict(X_val)
    y_prob = model.predict_proba(X_val)[:, 1]

    metrics = {
        "auc": float(roc_auc_score(y_val, y_prob)),
        "precision": float(precision_recall_fscore_support(y_val, y_pred, average="binary")[0]),
        "recall": float(precision_recall_fscore_support(y_val, y_pred, average="binary")[1]),
        "f1": float(precision_recall_fscore_support(y_val, y_pred, average="binary")[2]),
    }
    logger.info(f"Eval Results: AUC={metrics['auc']:.3f}, Precision={metrics['precision']:.3f}, Recall={metrics['recall']:.3f}, F1={metrics['f1']:.3f}")

    # Save to output
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(os.path.join(OUTPUT_DIR, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)
    with open(os.path.join(OUTPUT_DIR, "report.json"), "w") as f:
        json.dump(classification_report(y_val, y_pred, output_dict=True), f, indent=2)

    return metrics

def save_model(model, imputer, scaler, model_dir: str, version="v1"):
    """Save model and preprocessors."""
    os.makedirs(model_dir, exist_ok=True)
    joblib.dump(model, os.path.join(model_dir, f"fraud_model_{version}.joblib"))
    joblib.dump({"imputer": imputer, "scaler": scaler}, os.path.join(model_dir, "preprocessors.joblib"))
    logger.info(f"Model and preprocessors saved to {model_dir}")

def log_class_balance(y_train):
    """Log fraud class ratio."""
    ratio = np.mean(y_train)
    logger.info(f"Fraud rate in training set: {ratio:.2%}")

def push_metrics_to_cloudwatch(metrics: dict, namespace="FraudDetectionTraining"):
    """Optional: Push key metrics to CloudWatch."""
    try:
        cw = boto3.client("cloudwatch")
        for k, v in metrics.items():
            cw.put_metric_data(
                Namespace=namespace,
                MetricData=[{"MetricName": k, "Value": v, "Unit": "None"}],
            )
        logger.info("Metrics pushed to CloudWatch")
    except Exception as e:
        logger.warning(f"CloudWatch push failed: {e}")

# ------------------------------
# Main Execution
# ------------------------------
def main():
    logger.info("🚀 Starting SageMaker fraud model training job...")
    hyperparams = parse_hyperparams()

    # Load data
    train_df = load_data(TRAIN_DIR)
    val_df = load_data(VAL_DIR)

    # Preprocess
    X_train, y_train, imputer, scaler = preprocess_data(train_df, fit=True)
    X_val, y_val, _, _ = preprocess_data(val_df, fit=False, imputer=imputer, scaler=scaler)

    log_class_balance(y_train)

    # Train & Evaluate
    model = train_model(X_train, y_train, hyperparams)
    metrics = evaluate_model(model, X_val, y_val)

    # Save
    save_model(model, imputer, scaler, MODEL_DIR)
    push_metrics_to_cloudwatch(metrics)

    logger.info("✅ Training complete. Artifacts and metrics saved.")

if __name__ == "__main__":
    main()
