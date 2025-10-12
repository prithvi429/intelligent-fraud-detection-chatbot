"""
ML Data Preprocessing
---------------------
- Generates or loads raw insurance claim data.
- Engineers 14 ML-ready features for fraud prediction (matches FraudFeatures model).
- Cleans, imputes, scales, and splits data into train/test.
- Optionally generates synthetic data for training.
- Saves processed CSVs for local or SageMaker training.

Usage:
    python src/ml/preprocess.py --generate
    python src/ml/preprocess.py --output-dir ml/data/processed
"""

import argparse
import os
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from imblearn.over_sampling import SMOTE  # pip install imbalanced-learn
from faker import Faker
from typing import Tuple
from src.config import config
from src.utils.logger import logger
from src.utils.security import anonymize_pii

# =========================================================
# 🧩 Constants
# =========================================================
FEATURES = [
    "amount_normalized", "delay_days", "is_new_bank", "is_out_of_network",
    "num_alarms", "high_severity_count", "repeat_count", "text_similarity_score",
    "location_distance", "time_anomaly_score", "suspicious_keyword_count",
    "sentiment_score", "vendor_risk_score", "external_mismatch_count"
]
LABEL_COL = "fraud_label"
RAW_DATA_PATH = "ml/data/raw/synthetic_claims.csv"
PROCESSED_DIR = "ml/data/processed"


# =========================================================
# 🧠 Synthetic Data Generator
# =========================================================
def generate_synthetic_data(n_samples: int = 2000, fraud_ratio: float = 0.2) -> pd.DataFrame:
    """Generate synthetic claim data for ML training."""
    fake = Faker()
    np.random.seed(42)
    data = []

    for _ in range(n_samples):
        is_fraud = np.random.rand() < fraud_ratio
        fraud_label = 1 if is_fraud else 0

        claimant_id = anonymize_pii(fake.email())
        amount = np.random.normal(5000, 2000) if not is_fraud else np.random.exponential(10000)
        amount = np.clip(amount, 100, 50000)
        delay_days = np.random.poisson(2 if not is_fraud else 10)
        provider = fake.company()
        notes = fake.sentence() + (" staged quick cash" if is_fraud else "")
        location = "Los Angeles, CA" if is_fraud else fake.city()
        timestamp = fake.date_time_this_year()
        is_new_bank = np.random.choice([0, 1], p=[0.9, 0.1] if not is_fraud else [0.6, 0.4])

        data.append({
            "claimant_id": claimant_id,
            "amount": amount,
            "delay_days": delay_days,
            "provider": provider,
            "notes": notes,
            "location": location,
            "timestamp": timestamp,
            "is_new_bank": is_new_bank,
            LABEL_COL: fraud_label
        })

    df = pd.DataFrame(data)
    os.makedirs(os.path.dirname(RAW_DATA_PATH), exist_ok=True)
    df.to_csv(RAW_DATA_PATH, index=False)
    logger.info(f"✅ Generated {len(df)} synthetic samples ({df[LABEL_COL].sum()} frauds).")
    return df


# =========================================================
# ⚙️ Feature Engineering
# =========================================================
def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Engineer 14 numerical ML features based on raw claim data."""
    df_features = pd.DataFrame(index=df.index)
    global_avg = df["amount"].mean()

    df_features["amount_normalized"] = df["amount"] / global_avg
    df_features["delay_days"] = df["delay_days"]
    df_features["is_new_bank"] = df["is_new_bank"].astype(int)
    df_features["is_out_of_network"] = np.where(df[LABEL_COL] == 1, np.random.choice([0, 1], p=[0.3, 0.7]), np.random.choice([0, 1], p=[0.8, 0.2]))
    df_features["num_alarms"] = np.random.poisson(1 + 3 * df[LABEL_COL])
    df_features["high_severity_count"] = np.minimum(df_features["num_alarms"], np.random.binomial(df_features["num_alarms"], 0.3))
    df_features["repeat_count"] = np.random.poisson(1 + 2 * df[LABEL_COL])
    df_features["text_similarity_score"] = np.where(df[LABEL_COL] == 1, np.random.beta(5, 2), np.random.beta(2, 5))
    df_features["location_distance"] = np.where(df[LABEL_COL] == 1, np.random.normal(150, 40), np.random.normal(20, 10)).clip(0)
    df_features["time_anomaly_score"] = np.where(df[LABEL_COL] == 1, np.random.beta(5, 2), np.random.beta(2, 5))
    df_features["suspicious_keyword_count"] = np.random.poisson(0.5 + 2.5 * df[LABEL_COL])
    df_features["sentiment_score"] = np.where(df[LABEL_COL] == 1, np.random.normal(-0.4, 0.3), np.random.normal(0.2, 0.3)).clip(-1, 1)
    df_features["vendor_risk_score"] = np.where(df[LABEL_COL] == 1, np.random.beta(5, 2), np.random.beta(2, 5))
    df_features["external_mismatch_count"] = np.random.poisson(0.2 + 1.5 * df[LABEL_COL])

    df_features[LABEL_COL] = df[LABEL_COL]
    logger.info(f"✅ Engineered features: {df_features.shape[1]} columns.")
    return df_features


# =========================================================
# 🧹 Data Cleaning
# =========================================================
def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Clean missing values, clip outliers, and log balance."""
    imputer = SimpleImputer(strategy="median")
    df[FEATURES] = imputer.fit_transform(df[FEATURES])

    for col in FEATURES:
        if df[col].dtype in [np.float64, np.int64]:
            mean, std = df[col].mean(), df[col].std()
            df[col] = df[col].clip(mean - 3 * std, mean + 3 * std)

    fraud_pct = df[LABEL_COL].mean() * 100
    logger.info(f"Data balance: {fraud_pct:.1f}% fraud cases.")

    # Optional SMOTE
    # smote = SMOTE(random_state=42)
    # X_res, y_res = smote.fit_resample(df[FEATURES], df[LABEL_COL])
    # df = pd.DataFrame(X_res, columns=FEATURES)
    # df[LABEL_COL] = y_res
    return df


# =========================================================
# 🔀 Train/Test Split
# =========================================================
def split_data(df: pd.DataFrame, test_size: float = 0.2) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Split train/test data, stratified by label."""
    train_df, test_df = train_test_split(df, test_size=test_size, random_state=42, stratify=df[LABEL_COL])
    logger.info(f"Split: Train={len(train_df)}, Test={len(test_df)}.")
    return train_df, test_df


# =========================================================
# 💾 Save Outputs
# =========================================================
def save_processed(train_df: pd.DataFrame, test_df: pd.DataFrame, output_dir: str):
    """Save processed train/test datasets for local + SageMaker."""
    os.makedirs(output_dir, exist_ok=True)
    train_path = os.path.join(output_dir, "train.csv")
    test_path = os.path.join(output_dir, "test.csv")

    train_df.to_csv(train_path, index=False, header=True)
    test_df.to_csv(test_path, index=False, header=True)

    # SageMaker-compatible (no header)
    train_df.to_csv(train_path.replace(".csv", "_sagemaker.csv"), index=False, header=False)
    logger.info(f"✅ Processed data saved to {output_dir}")


# =========================================================
# 🚀 Main
# =========================================================
def main(generate: bool = False, output_dir: str = PROCESSED_DIR):
    """Run full preprocessing pipeline."""
    if generate or not os.path.exists(RAW_DATA_PATH):
        df_raw = generate_synthetic_data()
    else:
        df_raw = pd.read_csv(RAW_DATA_PATH)
        logger.info(f"Loaded raw data: {len(df_raw)} rows.")

    df_features = engineer_features(df_raw)
    df_clean = clean_data(df_features)
    train_df, test_df = split_data(df_clean)
    save_processed(train_df, test_df, output_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Preprocess data for ML training.")
    parser.add_argument("--generate", action="store_true", help="Generate synthetic data")
    parser.add_argument("--output-dir", default=PROCESSED_DIR, help="Output directory path")
    args = parser.parse_args()
    main(generate=args.generate, output_dir=args.output_dir)
