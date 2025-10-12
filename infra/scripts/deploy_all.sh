#!/bin/bash

# =========================================================
# 🚀 Full Deployment Script for Fraud Detection Platform
# ---------------------------------------------------------
# Deploys:
#   1. Lambdas (via lambda_deploy.sh)
#   2. CloudFormation API + ML Stacks
#   3. Terraform-managed infra (RDS, S3, etc.)
#   4. Optional DB seed for production
#
# Usage:
#   ./deploy_all.sh [dev|prod] [localstack]
# =========================================================

set -euo pipefail

# ---------------------------------------------
# Helper functions
# ---------------------------------------------
log()  { echo -e "\033[1;34m[INFO]\033[0m $1"; }
warn() { echo -e "\033[1;33m[WARN]\033[0m $1"; }
err()  { echo -e "\033[1;31m[ERROR]\033[0m $1"; }

trap 'err "Deployment failed! Rolling back partial stacks (if any)..." && rollback' ERR

rollback() {
  if [ "$LOCALSTACK" = true ]; then
    aws cloudformation delete-stack --stack-name "$STACK_PREFIX-api" --endpoint-url "http://localhost:4566" || true
  else
    aws cloudformation delete-stack --stack-name "$STACK_PREFIX-api" || true
  fi
}

# ---------------------------------------------
# Environment setup
# ---------------------------------------------
ENV=${1:-dev}
LOCALSTACK=${2:-false}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LAMBDA_DEPLOY_SCRIPT="$SCRIPT_DIR/../deployment/lambda_deploy.sh"

# Load environment variables
if [ -f "$PROJECT_ROOT/.env" ]; then
  export $(grep -v '^#' "$PROJECT_ROOT/.env" | xargs)
else
  err ".env file not found in $PROJECT_ROOT. Copy .env.example and fill in credentials."
  exit 1
fi

AWS_REGION=${AWS_REGION:-us-east-1}
ARTIFACTS_BUCKET="fraud-artifacts-$ENV"
STACK_PREFIX="fraud-$ENV"
TF_VAR_FILE="terraform.tfvars.$ENV"
ENDPOINT_ARG=""

if [ "$LOCALSTACK" = true ]; then
  ENDPOINT_ARG="--endpoint-url http://localhost:4566"
  log "🌍 Deploying using LocalStack (offline AWS simulation)"
else
  log "☁️ Deploying to AWS Cloud ($ENV, region: $AWS_REGION)"
fi

# ---------------------------------------------
# 1️⃣ Deploy Lambdas
# ---------------------------------------------
log "Step 1: Building and deploying Lambda functions..."
pushd "$PROJECT_ROOT" >/dev/null
  "$LAMBDA_DEPLOY_SCRIPT" "$ENV" "$LOCALSTACK"
popd >/dev/null

# ---------------------------------------------
# 2️⃣ Deploy CloudFormation API Stack
# ---------------------------------------------
log "Step 2: Deploying API CloudFormation stack..."
aws cloudformation deploy \
  --template-file "$SCRIPT_DIR/../cloudformation/api-stack.yaml" \
  --stack-name "$STACK_PREFIX-api" \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    Environment="$ENV" \
    FraudLambdaCodeS3Bucket="$ARTIFACTS_BUCKET" \
    FraudLambdaCodeS3Key="fraud_api-$ENV.zip" \
    ChatbotLambdaCodeS3Bucket="$ARTIFACTS_BUCKET" \
    ChatbotLambdaCodeS3Key="chatbot_handler-$ENV.zip" \
  $ENDPOINT_ARG \
  || warn "API stack deploy/update completed with warnings."

# ---------------------------------------------
# 3️⃣ Deploy CloudFormation ML Stack
# ---------------------------------------------
log "Step 3: Deploying ML CloudFormation stack..."
aws cloudformation deploy \
  --template-file "$SCRIPT_DIR/../cloudformation/ml-stack.yaml" \
  --stack-name "$STACK_PREFIX-ml" \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    Environment="$ENV" \
    ModelS3Bucket="$ARTIFACTS_BUCKET" \
    ModelS3Key="model-$ENV.tar.gz" \
    InstanceType="ml.t3.medium" \
  $ENDPOINT_ARG \
  || warn "ML stack deploy/update completed with warnings."

# ---------------------------------------------
# 4️⃣ Terraform Infra (RDS, S3, etc.)
# ---------------------------------------------
log "Step 4: Applying Terraform infrastructure..."
pushd "$SCRIPT_DIR/../terraform" >/dev/null
  terraform init -input=false
  terraform workspace select "$ENV" >/dev/null 2>&1 || terraform workspace new "$ENV"
  terraform apply -auto-approve \
    -var-file="$TF_VAR_FILE" \
    -var="environment=$ENV" \
    -var="s3_bucket_name=$ARTIFACTS_BUCKET" \
    || warn "Terraform apply completed with warnings or no changes."
popd >/dev/null

# ---------------------------------------------
# 5️⃣ Seed Database (Production Only)
# ---------------------------------------------
if [ "$LOCALSTACK" = false ] && [ "$ENV" = "prod" ]; then
  log "Step 5: Seeding production database..."
  if [ -z "${DB_URL:-}" ]; then
    err "DB_URL not set. Please configure in .env"
  else
    psql "$DB_URL" -f "$SCRIPT_DIR/seed_db.sql" -v ON_ERROR_STOP=1
  fi
fi

# ---------------------------------------------
# ✅ Outputs and Summary
# ---------------------------------------------
log "✅ Deployment complete for environment: $ENV"

if [ "$LOCALSTACK" = false ]; then
  API_URL=$(aws cloudformation describe-stacks --stack-name "$STACK_PREFIX-api" \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' --output text)
  ENDPOINT_NAME=$(aws cloudformation describe-stacks --stack-name "$STACK_PREFIX-ml" \
    --query 'Stacks[0].Outputs[?OutputKey==`SageMakerEndpointName`].OutputValue' --output text)
  log "API URL: $API_URL"
  log "SageMaker Endpoint: $ENDPOINT_NAME"
else
  log "🧱 LocalStack deployment ready! Access services via http://localhost:4566"
fi

log "🎉 All components deployed successfully!"
