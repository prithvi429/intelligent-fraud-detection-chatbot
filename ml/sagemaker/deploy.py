"""
SageMaker Deployment Script
---------------------------
Trains and deploys the insurance fraud detection model as a real-time endpoint.

Steps:
1. Create SKLearn estimator.
2. Train on S3 data (train/validation CSVs).
3. Deploy a real-time inference endpoint.
4. Test with sample features.
5. (Optional) Cleanup endpoint.

Usage:
    python src/fraud_engine/training/deploy_sagemaker.py --bucket fraud-chatbot-artifacts
Requires:
    - AWS credentials (IAM Role)
    - S3 paths for training and validation data
    - train_sagemaker.py in the same directory
"""

import os
import argparse
import boto3
import sagemaker
from sagemaker.sklearn.estimator import SKLearn
from sagemaker.inputs import TrainingInput
from sagemaker.serializers import CSVSerializer
from sagemaker.deserializers import JSONDeserializer
from sagemaker import get_execution_role
from datetime import datetime
from src.config import config
from src.utils.logger import logger

# ==============================================================
# CONFIGURATION
# ==============================================================

REGION = config.AWS_REGION or "us-east-1"
ROLE = get_execution_role()
BUCKET = config.S3_BUCKET_NAME or "fraud-chatbot-artifacts"

TRAIN_S3 = f"s3://{BUCKET}/ml/data/train/"
VAL_S3 = f"s3://{BUCKET}/ml/data/validation/"
OUTPUT_S3 = f"s3://{BUCKET}/ml/models/"

TRAIN_INSTANCE_TYPE = "ml.m5.large"
DEPLOY_INSTANCE_TYPE = "ml.t3.medium"

ENTRY_POINT = "train_sagemaker.py"  # training script
SOURCE_DIR = os.path.dirname(os.path.abspath(__file__))

# Timestamp for unique endpoint/versioning
TIMESTAMP = datetime.now().strftime("%Y%m%d-%H%M%S")
ENDPOINT_NAME = f"fraud-detection-endpoint-{TIMESTAMP}"


# ==============================================================
# MAIN FUNCTIONS
# ==============================================================

def create_estimator():
    """Create SKLearn estimator for training."""
    logger.info("📦 Initializing SKLearn estimator...")

    sklearn_image_uri = sagemaker.image_uris.retrieve(
        framework="sklearn",
        region=REGION,
        version="1.2-1",  # scikit-learn version
        py_version="py3"
    )

    estimator = SKLearn(
        entry_point=ENTRY_POINT,
        source_dir=SOURCE_DIR,
        role=ROLE,
        instance_count=1,
        instance_type=TRAIN_INSTANCE_TYPE,
        framework_version="1.2-1",
        py_version="py3",
        hyperparameters={
            "n_estimators": 150,
            "max_depth": 15,
            "min_samples_split": 4
        },
        output_path=OUTPUT_S3,
        image_uri=sklearn_image_uri,
        sagemaker_session=sagemaker.Session(default_bucket=BUCKET)
    )

    logger.info("✅ Estimator created successfully.")
    return estimator


def train_model(estimator):
    """Trigger SageMaker training job."""
    logger.info("🚀 Starting training job...")

    train_input = TrainingInput(TRAIN_S3, content_type="text/csv")
    val_input = TrainingInput(VAL_S3, content_type="text/csv")

    estimator.fit({"train": train_input, "validation": val_input}, wait=True)
    logger.info("✅ Training completed successfully.")


def deploy_endpoint(estimator):
    """Deploy trained model as real-time endpoint."""
    logger.info(f"🚀 Deploying endpoint: {ENDPOINT_NAME} ...")

    predictor = estimator.deploy(
        initial_instance_count=1,
        instance_type=DEPLOY_INSTANCE_TYPE,
        endpoint_name=ENDPOINT_NAME,
        serializer=CSVSerializer(),
        deserializer=JSONDeserializer(),
        wait=True
    )

    logger.info(f"✅ Endpoint deployed successfully: {ENDPOINT_NAME}")
    return predictor


def test_endpoint(predictor):
    """Run a test inference with sample fraud features."""
    logger.info("🧪 Running test inference...")

    # Example input: 14 normalized features (as per FraudFeatures)
    sample_features = [
        3.5, 10, 1, 1, 3,     # amount_normalized, delay_days, is_new_bank, is_out_of_network, num_alarms
        2, 4, 0.85, 150,      # high_severity_count, repeat_count, text_similarity_score, location_distance
        1, 2, -0.3, 0.9, 1    # time_anomaly_score, suspicious_keyword_count, sentiment, vendor_risk, external_mismatch_count
    ]

    csv_input = ",".join(map(str, sample_features))
    response = predictor.predict(csv_input)

    # Adapt to model output format
    prob = response.get("score") or response.get("fraud_probability") or 0.0

    logger.info(f"✅ Test inference completed: Fraud probability = {float(prob):.2%}")
    return prob


def save_endpoint_name():
    """Save endpoint name for later use in ml_inference.py."""
    with open("endpoint_name.txt", "w") as f:
        f.write(ENDPOINT_NAME)
    logger.info(f"📝 Endpoint name saved locally: {ENDPOINT_NAME}")


def delete_endpoint(endpoint_name: str):
    """Optionally delete endpoint after testing."""
    logger.warning(f"⚠️ Deleting endpoint {endpoint_name} ...")
    sagemaker.Predictor(endpoint_name).delete_endpoint()
    logger.info(f"✅ Endpoint {endpoint_name} deleted successfully.")


# ==============================================================
# MAIN
# ==============================================================

def main():
    parser = argparse.ArgumentParser(description="Deploy fraud detection model on SageMaker")
    parser.add_argument("--bucket", default=BUCKET, help="S3 bucket name")
    parser.add_argument("--cleanup", action="store_true", help="Delete endpoint after test")
    args = parser.parse_args()

    global BUCKET
    BUCKET = args.bucket

    try:
        estimator = create_estimator()
        train_model(estimator)
        predictor = deploy_endpoint(estimator)
        test_endpoint(predictor)
        save_endpoint_name()

        if args.cleanup:
            delete_endpoint(ENDPOINT_NAME)

    except Exception as e:
        logger.error(f"❌ Deployment pipeline failed: {e}")
        raise


if __name__ == "__main__":
    main()
