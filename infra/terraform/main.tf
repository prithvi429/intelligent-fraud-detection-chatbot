terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = var.tags
  }
}

# Locals
locals {
  project_name = "fraud-chatbot"
  api_name     = "${local.project_name}-api-${var.environment}"
  lambda_role  = "${local.project_name}-lambda-${var.environment}-role"
  sagemaker_role = "${local.project_name}-sagemaker-${var.environment}-role"
  db_name      = "${local.project_name}-db-${var.environment}"
}