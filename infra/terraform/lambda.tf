# IAM Role for Lambdas
resource "aws_iam_role" "lambda_role" {
  name = local.lambda_role

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# Attach policies
resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "lambda_rds" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonRDSDataFullAccess"
}

resource "aws_iam_role_policy_attachment" "lambda_s3" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
}

resource "aws_iam_role_policy_attachment" "lambda_sagemaker" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSageMakerFullAccess"
}

# Custom policy for CloudWatch logs
resource "aws_iam_policy" "lambda_logs" {
  name = "${local.project_name}-lambda-logs-${var.environment}"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Effect   = "Allow"
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.lambda_logs.arn
}

# Fraud Scoring Lambda
resource "aws_lambda_function" "fraud_scoring" {
  filename         = "${var.s3_bucket_name}/${var.lambda_zip_s3_key}"  # Assume uploaded
  function_name    = "${local.project_name}-fraud-scoring-${var.environment}"
  role             = aws_iam_role.lambda_role.arn
  handler          = "fraud_api.lambda_handler"
  runtime          = "python3.11"
  source_code_hash = filebase64sha256("${var.s3_bucket_name}/${var.lambda_zip_s3_key}")  # Update trigger

  timeout       = 30
  memory_size   = 512

  environment {
    variables = {
      ENVIRONMENT    = var.environment
      DB_URL         = "postgresql://${var.db_username}:${var.db_password}@${aws_db_instance.fraud_db.endpoint}/fraud_db"
      S3_BUCKET      = aws_s3_bucket.artifacts.bucket
      FRAUD_MODEL_PATH = "s3://${aws_s3_bucket.artifacts.bucket}/${var.model_s3_key}"
    }
  }

  depends_on = [aws_cloudwatch_log_group.fraud_scoring_logs]
}

# Chatbot Lambda
resource "aws_lambda_function" "chatbot" {
  filename         = "${var.s3_bucket_name}/${var.chatbot_zip_s3_key}"
  function_name    = "${local.project_name}-chatbot-${var.environment}"
  role             = aws_iam_role.lambda_role.arn
  handler          = "chatbot_handler.lambda_handler"
  runtime          = "python3.11"
  source_code_hash = filebase64sha256("${var.s3_bucket_name}/${var.chatbot_zip_s3_key}")

  timeout       = 60  # LangChain
  memory_size   = 1024

  environment {
    variables = {
      ENVIRONMENT    = var.environment
      DB_URL         = "postgresql://${var.db_username}:${var.db_password}@${aws_db_instance.fraud_db.endpoint}/fraud_db"
      S3_BUCKET      = aws_s3_bucket.artifacts.bucket
      OPENAI_API_KEY = var.openai_api_key  # Pass as var or Secrets Manager
      PINECONE_API_KEY = var.pinecone_api_key
    }
  }

  depends_on = [aws_cloudwatch_log_group.chatbot_logs]
}

# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "fraud_scoring_logs