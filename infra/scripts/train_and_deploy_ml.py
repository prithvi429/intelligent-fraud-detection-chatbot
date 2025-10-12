"""
ML Train and Deploy Script
--------------------------
Trains and deploys a fraud detection model to AWS SageMaker.

Steps:
  1. Train RandomForest model (inline or via src/ml/train.py).
  2. Save and package model.tar.gz (joblib + preprocessors).
  3. Upload to S3.
  4. Deploy or update SageMaker endpoint.

Usage:
  python infra/scripts/train_and_deploy_ml.py [--env dev] [--instance-type ml.t3.medium] [--no-deploy]

Requirements:
  - .env with AWS keys and S3_BUCKET
  - ml/data/processed/train.csv, test.csv
  - boto3, joblib, pandas, scikit-learn
"""

import os
import tarfile
import argparse
import boto3
import pandas as pd
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
from dotenv import load_dotenv
from botocore.exceptions import ClientError
from src.utils.logger import logger

load_dotenv()

# -------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------
def train_model_inline():
    """Train RandomForest model inline from preprocessed CSVs."""
    logger.info("📊 Loading preprocessed training data...")
    train_path = "ml/data/processed/train.csv"
    test_path = "ml/data/processed/test.csv"
    
    if not os.path.exists(train_path) or not os.path.exists(test_path):
        raise FileNotFoundError("❌ Preprocessed data not found in ml/data/processed/. Run preprocess.py first.")

    train_df = pd.read_csv(train_path)
    test_df = pd.read_csv(test_path)

    X_train, y_train = train_df.drop(columns=["fraud_label"]), train_df["fraud_label"]
    X_test, y_test = test_df.drop(columns=["fraud_label"]), test_df["fraud_label"]

    logger.info("🤖 Training RandomForest model...")
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        random_state=42,
        class_weight="balanced"
    )
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    report = classification_report(y_test, preds, output_dict=True)
    logger.info(f"✅ Model evaluation complete. Accuracy: {report['accuracy']:.4f}")

    return model, report


def package_model(model, env):
    """Save model to model.joblib and package to model-$ENV.tar.gz."""
    os.makedirs("ml/artifacts", exist_ok=True)
    model_path = f"ml/artifacts/model-{env}.joblib"
    tar_path = f"ml/artifacts/model-{env}.tar.gz"

    logger.info(f"💾 Saving model to {model_path}...")
    joblib.dump(model, model_path)

    logger.info(f"📦 Packaging model to {tar_path}...")
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(model_path, arcname="model.joblib")

    return tar_path


def upload_to_s3(tar_path, s3_bucket, s3_key, region="us-east-1"):
    """Upload model.tar.gz to S3."""
    s3_client = boto3.client("s3", region_name=region)
    logger.info(f"☁️ Uploading {tar_path} to s3://{s3_bucket}/{s3_key}...")
    try:
        s3_client.upload_file(tar_path, s3_bucket, s3_key)
        logger.info("✅ Upload complete.")
    except ClientError as e:
        logger.error(f"❌ Failed to upload model: {e}")
        raise


def deploy_to_sagemaker(s3_bucket, s3_key, env, instance_type="ml.t3.medium", region="us-east-1"):
    """Deploy model as SageMaker endpoint."""
    sm = boto3.client("sagemaker", region_name=region)
    model_name = f"fraud-model-{env}"
    endpoint_config_name = f"fraud-endpoint-config-{env}"
    endpoint_name = f"fraud-endpoint-{env}"

    # 1️⃣ Create or update Model
    image_uri = f"683313688378.dkr.ecr.{region}.amazonaws.com/sagemaker-scikit-learn:1.2-1-cpu-py3"

    try:
        logger.info(f"🧩 Creating/Updating SageMaker model {model_name}...")
        sm.create_model(
            ModelName=model_name,
            ExecutionRoleArn=os.getenv("SAGEMAKER_ROLE_ARN"),
            PrimaryContainer={
                "Image": image_uri,
                "ModelDataUrl": f"s3://{s3_bucket}/{s3_key}"
            }
        )
    except ClientError as e:
        if "ValidationException" in str(e):
            logger.info(f"ℹ️ Model {model_name} already exists. Skipping creation.")
        else:
            raise

    # 2️⃣ Create or update Endpoint Config
    try:
        logger.info(f"⚙️ Creating endpoint config {endpoint_config_name}...")
        sm.create_endpoint_config(
            EndpointConfigName=endpoint_config_name,
            ProductionVariants=[
                {
                    "VariantName": "AllTraffic",
                    "ModelName": model_name,
                    "InstanceType": instance_type,
                    "InitialInstanceCount": 1
                }
            ]
        )
    except ClientError as e:
        if "ValidationException" in str(e):
            logger.info(f"ℹ️ Endpoint config {endpoint_config_name} already exists. Skipping creation.")
        else:
            raise

    # 3️⃣ Create or update Endpoint
    try:
        logger.info(f"🚀 Deploying endpoint {endpoint_name}...")
        sm.create_endpoint(
            EndpointName=endpoint_name,
            EndpointConfigName=endpoint_config_name
        )
    except ClientError as e:
        if "ValidationException" in str(e):
            logger.info(f"🔄 Updating existing endpoint {endpoint_name}...")
            sm.update_endpoint(
                EndpointName=endpoint_name,
                EndpointConfigName=endpoint_config_name
            )
        else:
            raise

    logger.info(f"✅ SageMaker endpoint ready: {endpoint_name}")
    return endpoint_name


# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train and deploy ML model to SageMaker.")
    parser.add_argument("--env", default="dev", choices=["dev", "prod"], help="Environment (dev/prod)")
    parser.add_argument("--instance-type", default="ml.t3.medium", help="SageMaker instance type")
    parser.add_argument("--no-deploy", action="store_true", help="Train and upload only, skip deployment")

    args = parser.parse_args()

    env = args.env
    region = os.getenv("AWS_REGION", "us-east-1")
    s3_bucket = os.getenv("S3_BUCKET") or f"fraud-artifacts-{env}"
    s3_key = f"model-{env}.tar.gz"

    logger.info(f"🌍 Starting ML train/deploy pipeline for environment: {env}")

    # Train model
    model, report = train_model_inline()

    # Package and upload
    tar_path = package_model(model, env)
    upload_to_s3(tar_path, s3_bucket, s3_key, region)

    # Deploy to SageMaker (optional)
    if not args.no_deploy:
        endpoint_name = deploy_to_sagemaker(s3_bucket, s3_key, env, args.instance_type, region)
        logger.info(f"✅ Deployment complete! Endpoint: {endpoint_name}")
    else:
        logger.info("⚙️ Skipping deployment (--no-deploy set).")

    logger.info("🎉 ML pipeline finished successfully.")
