# sagemaker stub
# IAM Role for SageMaker Execution
resource "aws_iam_role" "sagemaker_role" {
  name = local.sagemaker_role

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = [
            "sagemaker.amazonaws.com",
            "sagemaker-ap-south-1.amazonaws.com"  # Add regions if multi-region
          ]
        }
      }
    ]
  })

  tags = {
    Name = local.sagemaker_role
  }
}

# Attach SageMaker full access (adjust for least-privilege in prod)
resource "aws_iam_role_policy_attachment" "sagemaker_full_access" {
  role       = aws_iam_role.sagemaker_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSageMakerFullAccess"
}

# Custom policy for S3 model access
resource "aws_iam_policy" "sagemaker_s3_access" {
  name = "${local.project_name}-sagemaker-s3-${var.environment}"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.artifacts.arn,
          "${aws_s3_bucket.artifacts.arn}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "sagemaker_s3_policy" {
  role       = aws_iam_role.sagemaker_role.name
  policy_arn = aws_iam_policy.sagemaker_s3_access.arn
}

# SageMaker Model (from S3 tar.gz)
resource "aws_sagemaker_model" "fraud_model" {
  name = "${local.project_name}-model-${var.environment}"

  primary_container {
    image = "683313688378.dkr.ecr.${var.aws_region}.amazonaws.com/sagemaker-scikit-learn:1.2-1-cpu-py3"  # SKLearn container
    model_data_url = "s3://${aws_s3_bucket.artifacts.bucket}/${var.model_s3_key}"  # model.tar.gz
  }

  execution_role_arn = aws_iam_role.sagemaker_role.arn

  # VPC config (optional; if in private subnet)
  # vpc_config {
  #   security_group_ids = [aws_security_group.sagemaker_sg.id]
  #   subnets = data.aws_subnets.private.ids
  # }

  tags = {
    Name = "${local.project_name}-model-${var.environment}"
  }
}

# SageMaker Endpoint Configuration
resource "aws_sagemaker_endpoint_configuration" "fraud_endpoint_config" {
  name = "${local.project_name}-endpoint-config-${var.environment}"

  production_variants {
    variant_name           = "AllTraffic"
    initial_instance_count = var.environment == "prod" ? 2 : 1  # Scale for prod
    instance_type          = var.sagemaker_instance_type
    initial_variant_weight = 1.0
    model_name             = aws_sagemaker_model.fraud_model.name
  }

  # KMS encryption (optional)
  kms_key_arn = var.kms_key_arn  # Pass via vars if needed

  tags = {
    Name = "${local.project_name}-endpoint-config-${var.environment}"
  }
}

# SageMaker Endpoint (production deployment)
resource "aws_sagemaker_endpoint" "fraud_endpoint" {
  name                 = "${local.project_name}-endpoint-${var.environment}"
  endpoint_config_name = aws_sagemaker_endpoint_configuration.fraud_endpoint_config.name

  tags = {
    Name = "${local.project_name}-endpoint-${var.environment}"
  }

  # Lifecycle to handle updates (new config → new endpoint)
  lifecycle {
    create_before_destroy = true
    ignore_changes = [tags]
  }

  depends_on = [aws_iam_role_policy_attachment.sagemaker_s3_policy]
}

# Optional: Auto-scaling policy (for prod traffic)
resource "aws_appautoscaling_target" "sagemaker_target" {
  count = var.environment == "prod" ? 1 : 0

  max_capacity       = 5
  min_capacity       = 1
  resource_id        = "endpoint/${aws_sagemaker_endpoint.fraud_endpoint.name}/variant/AllTraffic"
  scalable_dimension = "sagemaker:variant:DesiredInstanceCount"
  service_namespace  = "sagemaker"
}

resource "aws_appautoscaling_policy" "sagemaker_policy" {
  count = var.environment == "prod" ? 1 : 0

  name               = "${local.project_name}-scaling-policy-${var.environment}"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.sagemaker_target[0].resource_id
  scalable_dimension = aws_appautoscaling_target.sagemaker_target[0].scalable_dimension
  service_namespace  = aws_appautoscaling_target.sagemaker_target[0].service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "SageMakerVariantInvocationsPerInstance"
    }
    target_value       = 100.0  # Scale when >100 invocations/instance
    scale_in_cooldown  = 60
    scale_out_cooldown = 60
  }

  depends_on = [aws_sagemaker_endpoint.fraud_endpoint]
}

# CloudWatch Log Group for Endpoint (auto-created, but tag for organization)
resource "aws_cloudwatch_log_group" "sagemaker_logs" {
  name              = "/aws/sagemaker/Endpoints/${aws_sagemaker_endpoint.fraud_endpoint.name}"
  retention_in_days = 14  # 2 weeks for dev; 30+ for prod

  tags = {
    Name = "${local.project_name}-sagemaker-logs-${var.environment}"
  }
}

# Optional: Alarm for endpoint errors (CloudWatch)
resource "aws_cloudwatch_metric_alarm" "sagemaker_errors" {
  alarm_name          = "${local.project_name}-sagemaker-errors-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Invocation4XXErrors"
  namespace           = "AWS/SageMaker"
  period              = "300"
  statistic           = "Sum"
  threshold           = "5"  # Alert if >5 4xx errors/5min
  alarm_description   = "SageMaker endpoint 4xx errors high"
  alarm_actions       = [var.sns_topic_arn]  # Pass SNS ARN via vars

  dimensions = {
    EndpointName = aws_sagemaker_endpoint.fraud_endpoint.name
    VariantName  = "AllTraffic"
  }

  tags = {
    Name = "${local.project_name}-sagemaker-alarm-${var.environment}"
  }
}