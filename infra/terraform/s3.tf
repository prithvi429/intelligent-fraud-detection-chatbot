# S3 Bucket for models, Lambda ZIPs, artifacts
resource "aws_s3_bucket" "artifacts" {
  bucket = var.s3_bucket_name
}

# Versioning
resource "aws_s3_bucket_versioning" "artifacts_versioning" {
  bucket = aws_s3_bucket.artifacts.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Server-side encryption (SSE-S3)
resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts_encryption" {
  bucket = aws_s3_bucket.artifacts.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Public access block
resource "aws_s3_bucket_public_access_block" "artifacts_public_access" {
  bucket = aws_s3_bucket.artifacts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Bucket policy (Lambda/SageMaker read access)
resource "aws_s3_bucket_policy" "artifacts_policy" {
  bucket = aws_s3_bucket.artifacts.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowLambdaSageMakerRead"
        Effect    = "Allow"
        Principal = {
          Service = [
            "lambda.amazonaws.com",
            "sagemaker.amazonaws.com"
          ]
        }
        Action   = ["s3:GetObject", "s3:ListBucket"]
        Resource = [
          aws_s3_bucket.artifacts.arn,
          "${aws_s3_bucket.artifacts.arn}/*"
        ]
      }
    ]
  })
}

# Lifecycle rule (expire old versions after 30 days)
resource "aws_s3_bucket_lifecycle_configuration" "artifacts_lifecycle" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    id     = "expire-old-versions"
    status = "Enabled"

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}