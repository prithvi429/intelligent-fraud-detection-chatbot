# outputs
# API Gateway URL
output "api_gateway_url" {
  description = "Invoke URL for the API Gateway stage"
  value       = aws_api_gateway_deployment.api_deployment.invoke_url
}

# RDS Endpoint
output "rds_endpoint" {
  description = "RDS instance endpoint"
  value       = aws_db_instance.fraud_db.endpoint
}

# S3 Bucket Name
output "s3_bucket_name" {
  description = "S3 bucket for artifacts"
  value       = aws_s3_bucket.artifacts.bucket
}

# Lambda ARNs
output "fraud_scoring_lambda_arn" {
  description = "ARN of fraud scoring Lambda"
  value       = aws_lambda_function.fraud_scoring.arn
}

output "chatbot_lambda_arn" {
  description = "ARN of chatbot Lambda"
  value       = aws_lambda_function.chatbot.arn
}

# SageMaker Endpoint
output "sagemaker_endpoint_name" {
  description = "SageMaker endpoint name"
  value       = aws_sagemaker_endpoint.fraud_endpoint.name
}

# IAM Roles
output "lambda_role_arn" {
  description = "Lambda execution role ARN"
  value       = aws_iam_role.lambda_role.arn
}

output "sagemaker_role_arn" {
  description = "SageMaker execution role ARN"
  value       = aws_iam_role.sagemaker_role.arn
}