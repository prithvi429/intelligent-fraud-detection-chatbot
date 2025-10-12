#!/bin/bash

# =====================================================
# Fraud Detection Lambda Deployment Script
# -----------------------------------------------------
# Usage:
#   ./lambda_deploy.sh [dev|prod] [localstack]
# Example:
#   ./lambda_deploy.sh dev true
#
# Deploys Lambdas to AWS or LocalStack:
#   - fraud_api.py
#   - chatbot_handler.py
#   - external_checker.py
#
# Requires: AWS CLI, zip, and valid AWS credentials or LocalStack running.
# =====================================================

set -euo pipefail

# ---------------------------------------------
# Parse Arguments & Environment
# ---------------------------------------------
ENV=${1:-dev}
LOCALSTACK=${2:-false}
REGION=${AWS_REGION:-us-east-1}
PROFILE=${AWS_PROFILE:-default}

LAMBDA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../lambdas" && pwd)"
ARTIFACTS_BUCKET="fraud-artifacts-${ENV}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "000000000000")

# Optional DB_URL can be set in env
DB_URL=${DB_URL:-postgresql://fraud_user:fraud_pass@db:5432/fraud_db}

# LocalStack or AWS endpoint
if [ "$LOCALSTACK" = true ]; then
  AWS_ENDPOINT_URL="--endpoint-url http://localhost:4566"
  echo "🧱 Deploying to LocalStack (env=$ENV, region=$REGION)..."
else
  AWS_ENDPOINT_URL=""
  echo "☁️ Deploying to AWS ($ENV, region=$REGION)..."
fi

# ---------------------------------------------
# Ensure S3 bucket exists
# ---------------------------------------------
echo "🔍 Checking S3 bucket: $ARTIFACTS_BUCKET"
if ! aws s3 ls "s3://$ARTIFACTS_BUCKET" $AWS_ENDPOINT_URL >/dev/null 2>&1; then
  echo "📦 Creating S3 bucket: $ARTIFACTS_BUCKET"
  aws s3 mb "s3://$ARTIFACTS_BUCKET" $AWS_ENDPOINT_URL || true
fi

# ---------------------------------------------
# Function: zip and upload
# ---------------------------------------------
zip_and_upload() {
  local handler=$1
  local runtime=${2:-python3.11}
  local timeout=${3:-30}
  local memory=${4:-512}
  local s3_key="${handler}-${ENV}.zip"
  local zip_path="${LAMBDA_DIR}/${handler}.zip"

  echo "⚙️ Packaging $handler..."

  (
    cd "$LAMBDA_DIR"
    rm -f "$zip_path"
    zip -r "$zip_path" "${handler}.py" requirements_lambda.txt >/dev/null
  )

  echo "⬆️ Uploading to s3://$ARTIFACTS_BUCKET/$s3_key"
  aws s3 cp "$zip_path" "s3://$ARTIFACTS_BUCKET/$s3_key" $AWS_ENDPOINT_URL >/dev/null

  # Deploy or update Lambda
  echo "🚀 Deploying Lambda function: fraud-${handler}-${ENV}"
  if ! aws lambda get-function --function-name "fraud-${handler}-${ENV}" $AWS_ENDPOINT_URL >/dev/null 2>&1; then
    aws lambda create-function \
      --function-name "fraud-${handler}-${ENV}" \
      --runtime "$runtime" \
      --role "arn:aws:iam::${ACCOUNT_ID}:role/fraud-lambda-${ENV}-role" \
      --handler "${handler}.lambda_handler" \
      --zip-file "fileb://${zip_path}" \
      --timeout "$timeout" \
      --memory-size "$memory" \
      --environment "Variables={ENVIRONMENT=${ENV},DB_URL=${DB_URL},S3_BUCKET=${ARTIFACTS_BUCKET}}" \
      $AWS_ENDPOINT_URL >/dev/null
    echo "✅ Created new Lambda: fraud-${handler}-${ENV}"
  else
    aws lambda update-function-code \
      --function-name "fraud-${handler}-${ENV}" \
      --zip-file "fileb://${zip_path}" \
      $AWS_ENDPOINT_URL >/dev/null
    echo "🔁 Updated existing Lambda: fraud-${handler}-${ENV}"
  fi
}

# ---------------------------------------------
# Deploy All Lambda Functions
# ---------------------------------------------
zip_and_upload "fraud_api" "python3.11" 30 512
zip_and_upload "chatbot_handler" "python3.11" 60 1024
zip_and_upload "external_checker" "python3.11" 20 256

# ---------------------------------------------
# Add API Gateway Permission (only for AWS)
# ---------------------------------------------
if [ "$LOCALSTACK" = false ]; then
  echo "🔐 Adding permission for API Gateway..."
  aws lambda add-permission \
    --function-name "fraud-fraud_api-${ENV}" \
    --statement-id api-gateway-access \
    --action lambda:InvokeFunction \
    --principal apigateway.amazonaws.com \
    --source-arn "arn:aws:execute-api:${REGION}:${ACCOUNT_ID}:*/*/POST/score_claim" \
    || echo "⚠️ Permission already exists"
fi

echo "✅ Lambda Deployment complete for environment: $ENV"
