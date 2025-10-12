provider "aws" {
  region = var.aws_region
}

resource "aws_s3_bucket" "artifacts" {
  bucket = var.s3_bucket_name
  acl    = "private"

  tags = var.tags
}

resource "aws_db_instance" "fraud_rds" {
  allocated_storage    = 20
  engine               = "postgres"
  instance_class       = var.db_instance_class
  name                 = "frauddb"
  username             = var.db_username
  password             = var.db_password
  skip_final_snapshot  = true

  tags = var.tags
}

resource "aws_sagemaker_model" "fraud_model" {
  name              = "fraud-model-${var.environment}"
  execution_role_arn = aws_iam_role.sagemaker_exec.arn
  primary_container {
    image         = "683313688378.dkr.ecr.${var.aws_region}.amazonaws.com/sagemaker-scikit-learn:1.2-1-cpu-py3"
    model_data_url = "s3://${var.s3_bucket_name}/${var.model_s3_key}"
  }

  tags = var.tags
}
