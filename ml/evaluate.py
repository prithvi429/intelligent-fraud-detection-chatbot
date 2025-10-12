"""
ML Model Evaluation
-------------------
- Loads trained model (.pkl) and test data (processed/test.csv).
- Predicts fraud probabilities & labels.
- Computes key metrics: Accuracy, Precision/Recall/F1, ROC-AUC.
- Focus: High recall for fraud class (label=1) to minimize false negatives.
- Saves JSON reports, confusion matrix, ROC curve, and CSV summary.
- Automatically timestamps each run for traceability.

Run:
    python src/ml/evaluate.py
Output:
    ml/evaluation/evaluation_metrics_<timestamp>.json
    ml/evaluation/confusion_matrix_<timestamp>.png
    ml/evaluation/roc_curve_<timestamp>.png
    ml/evaluation/evaluation_summary.csv
"""

import os
import json
import joblib
import datetime
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    roc_auc_score,
    confusion_matrix,
    classification_report,
    roc_curve
)
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from src.config import config
from src.utils.logger import logger

# =========================================================
# 📁 Paths and Constants
# =========================================================
MODEL_PATH = config.FRAUD_MODEL_PATH  # e.g., ml/fraud_model.pkl
PREPROCESSORS_PATH = MODEL_PATH.replace(".pkl", "_preprocessors.pkl")
TEST_DATA_PATH = "ml/data/processed/test.csv"
EVAL_DIR = "ml/evaluation"

FEATURES = [
    "amount_normalized", "delay_days", "is_new_bank", "is_out_of_network",
    "num_alarms", "high_severity_count", "repeat_count", "text_similarity_score",
    "location_distance", "time_anomaly_score", "suspicious_keyword_count",
    "sentiment_score", "vendor_risk_score", "external_mismatch_count"
]
LABEL_COL = "fraud_label"

# Create output directory
os.makedirs(EVAL_DIR, exist_ok=True)
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


# =========================================================
# 🔍 Load Model & Preprocessors
# =========================================================
def load_model_and_preprocessors():
    """Load trained RandomForest model and its preprocessors."""
    try:
        model = joblib.load(MODEL_PATH)
        imputer, scaler = joblib.load(PREPROCESSORS_PATH)
        logger.info(f"✅ Model loaded: {type(model).__name__}, preprocessors ready.")
        return model, imputer, scaler
    except FileNotFoundError as e:
        logger.error(f"❌ Missing model or preprocessors: {e}. Run train.py first.")
        raise
    except Exception as e:
        logger.error(f"Error loading model: {e}")
        raise


# =========================================================
# 📦 Load Test Data
# =========================================================
def load_test_data():
    """Load and validate test data."""
    if not os.path.exists(TEST_DATA_PATH):
        raise FileNotFoundError(f"Test data not found at {TEST_DATA_PATH}. Run preprocess.py first.")

    df = pd.read_csv(TEST_DATA_PATH)
    X_test = df[FEATURES]
    y_test = df[LABEL_COL]

    fraud_ratio = y_test.mean()
    logger.info(f"✅ Loaded test data: {len(df)} rows ({fraud_ratio:.1%} fraud).")
    return X_test, y_test


# =========================================================
# ⚙️ Preprocessing
# =========================================================
def preprocess_test_data(X_test, imputer: SimpleImputer, scaler: StandardScaler):
    """Apply imputation and scaling."""
    X_imputed = imputer.transform(X_test)
    X_scaled = scaler.transform(X_imputed)
    logger.info(f"✅ Test data preprocessed: {X_scaled.shape}")
    return X_scaled


# =========================================================
# 📊 Evaluation Metrics
# =========================================================
def compute_metrics(y_true, y_pred, y_proba):
    """Compute performance metrics."""
    accuracy = accuracy_score(y_true, y_pred)

    precision_fraud, recall_fraud, f1_fraud, _ = precision_recall_fscore_support(
        y_true, y_pred, average="binary", zero_division=0
    )

    precision_weighted, recall_weighted, f1_weighted, _ = precision_recall_fscore_support(
        y_true, y_pred, average="weighted", zero_division=0
    )

    auc = roc_auc_score(y_true, y_proba)

    metrics = {
        "accuracy": accuracy,
        "precision_fraud": precision_fraud,
        "recall_fraud": recall_fraud,
        "f1_fraud": f1_fraud,
        "precision_weighted": precision_weighted,
        "recall_weighted": recall_weighted,
        "f1_weighted": f1_weighted,
        "roc_auc": auc,
        "fraud_prevalence": float(np.mean(y_true)),
        "num_fraud_detected": int(np.sum(y_pred[y_true == 1])),
        "total_fraud": int(np.sum(y_true)),
    }

    report = classification_report(y_true, y_pred, output_dict=True, zero_division=0)

    logger.info("📊 Evaluation Results:")
    logger.info(json.dumps(metrics, indent=2))
    return metrics, report


# =========================================================
# 🧮 Plot Confusion Matrix
# =========================================================
def plot_confusion_matrix(y_true, y_pred, save_path):
    """Save confusion matrix as PNG."""
    cm = confusion_matrix(y_true, y_pred)
    plt.figure(figsize=(6, 5))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
                xticklabels=["Legit", "Fraud"], yticklabels=["Legit", "Fraud"])
    plt.title("Confusion Matrix")
    plt.xlabel("Predicted")
    plt.ylabel("Actual")
    plt.tight_layout()
    plt.savefig(save_path, dpi=300)
    plt.close()
    logger.info(f"🖼️ Confusion matrix saved: {save_path}")


# =========================================================
# 📈 Plot ROC Curve
# =========================================================
def plot_roc_curve(y_true, y_proba, save_path):
    """Plot and save ROC curve."""
    fpr, tpr, _ = roc_curve(y_true, y_proba)
    auc = roc_auc_score(y_true, y_proba)

    plt.figure(figsize=(6, 5))
    plt.plot(fpr, tpr, color="orange", lw=2, label=f"AUC = {auc:.2f}")
    plt.plot([0, 1], [0, 1], linestyle="--", color="gray")
    plt.xlabel("False Positive Rate")
    plt.ylabel("True Positive Rate")
    plt.title("ROC Curve")
    plt.legend(loc="lower right")
    plt.tight_layout()
    plt.savefig(save_path, dpi=300)
    plt.close()
    logger.info(f"📈 ROC curve saved: {save_path}")


# =========================================================
# 💾 Save Reports
# =========================================================
def save_evaluation_results(metrics, report):
    """Save evaluation metrics and report as JSON + CSV."""
    metrics_path = os.path.join(EVAL_DIR, f"evaluation_metrics_{timestamp}.json")
    report_path = os.path.join(EVAL_DIR, f"classification_report_{timestamp}.json")
    csv_path = os.path.join(EVAL_DIR, "evaluation_summary.csv")

    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    # Append metrics summary to CSV
    pd.DataFrame([metrics]).to_csv(csv_path, mode="a", header=not os.path.exists(csv_path), index=False)

    logger.info(f"💾 Results saved: {metrics_path}, {report_path}, {csv_path}")


# =========================================================
# 🚀 Main Evaluation
# =========================================================
def main():
    logger.info("🚀 Starting model evaluation...")
    model, imputer, scaler = load_model_and_preprocessors()
    X_test, y_test = load_test_data()
    X_test_scaled = preprocess_test_data(X_test, imputer, scaler)

    y_pred = model.predict(X_test_scaled)
    y_proba = model.predict_proba(X_test_scaled)[:, 1]

    metrics, report = compute_metrics(y_test.values, y_pred, y_proba)

    # Save plots
    cm_path = os.path.join(EVAL_DIR, f"confusion_matrix_{timestamp}.png")
    roc_path = os.path.join(EVAL_DIR, f"roc_curve_{timestamp}.png")
    plot_confusion_matrix(y_test.values, y_pred, cm_path)
    plot_roc_curve(y_test.values, y_proba, roc_path)

    save_evaluation_results(metrics, report)

    # 📋 Summary
    print("\n=== EVALUATION SUMMARY ===")
    print(f"Accuracy:        {metrics['accuracy']:.3f}")
    print(f"Fraud Recall:    {metrics['recall_fraud']:.3f} (Target ≥ 0.80)")
    print(f"ROC-AUC:         {metrics['roc_auc']:.3f} (Target ≥ 0.85)")
    print(f"Weighted F1:     {metrics['f1_weighted']:.3f}")
    print(f"Fraud Prevalence: {metrics['fraud_prevalence']:.1%}")
    if metrics["recall_fraud"] >= 0.8:
        print("✅ Model meets fraud recall target (≥ 0.8)")
    else:
        print("⚠️ Model recall below target — consider retraining.")
    logger.info("✅ Evaluation complete. Files available in ml/evaluation/")


if __name__ == "__main__":
    main()
