# API Gateway REST API
resource "aws_api_gateway_rest_api" "fraud_api" {
  name        = "${local.project_name}-api-${var.environment}"
  description = "API for insurance fraud detection and chatbot guidance"
  protocol_type = "REST"

  endpoint_configuration {
    types = ["REGIONAL"]  # Or EDGE for global
  }

  tags = {
    Name = "${local.project_name}-api-${var.environment}"
  }
}

# CORS (for frontend calls, e.g., Streamlit)
resource "aws_api_gateway_rest_api" "fraud_api" {
  # ... (above)
}

# Root Resource (/)
resource "aws_api_gateway_resource" "root" {
  rest_api_id = aws_api_gateway_rest_api.fraud_api.id
  parent_id   = aws_api_gateway_rest_api.fraud_api.root_resource_id
  path_part   = ""
}

# /score_claim Resource (POST)
resource "aws_api_gateway_resource" "score_claim" {
  rest_api_id = aws_api_gateway_rest_api.fraud_api.id
  parent_id   = aws_api_gateway_rest_api.fraud_api.root_resource_id
  path_part   = "score_claim"
}

# POST /score_claim Method (to fraud_scoring Lambda)
resource "aws_api_gateway_method" "score_claim_post" {
  rest_api_id   = aws_api_gateway_rest_api.fraud_api.id
  resource_id   = aws_api_gateway_resource.score_claim.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "score_claim_integration" {
  rest_api_id             = aws_api_gateway_rest_api.fraud_api.id
  resource_id             = aws_api_gateway_resource.score_claim.id
  http_method             = aws_api_gateway_method.score_claim_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.fraud_scoring.invoke_arn
}

# OPTIONS /score_claim (CORS preflight)
resource "aws_api_gateway_method" "score_claim_options" {
  rest_api_id   = aws_api_gateway_rest_api.fraud_api.id
  resource_id   = aws_api_gateway_resource.score_claim.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "score_claim_options_integration" {
  rest_api_id             = aws_api_gateway_rest_api.fraud_api.id
  resource_id             = aws_api_gateway_resource.score_claim.id
  http_method             = aws_api_gateway_method.score_claim_options.http_method
  type                    = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "score_claim_options_200" {
  rest_api_id = aws_api_gateway_rest_api.fraud_api.id
  resource_id = aws_api_gateway_resource.score_claim.id
  http_method = aws_api_gateway_method.score_claim_options.http_method
  status_code = "200"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "score_claim_options_integration_response" {
  rest_api_id = aws_api_gateway_rest_api.fraud_api.id
  resource_id = aws_api_gateway_resource.score_claim.id
  http_method = aws_api_gateway_method.score_claim_options.http_method
  status_code = aws_api_gateway_method_response.score_claim_options_200.status_code
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'POST,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# /explain Resource (parent)
resource "aws_api_gateway_resource" "explain" {
  rest_api_id = aws_api_gateway_rest_api.fraud_api.id
  parent_id   = aws_api_gateway_rest_api.fraud_api.root_resource_id
  path_part   = "explain"
}

# /{alarm_type} Proxy Resource (child of /explain)
resource "aws_api_gateway_resource" "alarm_type" {
  rest_api_id = aws_api_gateway_rest_api.fraud_api.id
  parent_id   = aws_api_gateway_resource.explain.id
  path_part   = "{alarm_type}"
}

# GET /explain/{alarm_type} Method (to fraud_scoring Lambda)
resource "aws_api_gateway_method" "explain_get" {
  rest_api_id   = aws_api_gateway_rest_api.fraud_api.id
  resource_id   = aws_api_gateway_resource.alarm_type.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "explain_integration" {
  rest_api_id             = aws_api_gateway_rest_api.fraud_api.id
  resource_id             = aws_api_gateway_resource.alarm_type.id
  http_method             = aws_api_gateway_method.explain_get.http_method
  integration_http_method = "GET"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.fraud_scoring.invoke_arn
}

# OPTIONS /explain/{alarm_type} (CORS)
resource "aws_api_gateway_method" "explain_options" {
  rest_api_id   = aws_api_gateway_rest_api.fraud_api.id
  resource_id   = aws_api_gateway_resource.alarm_type.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "explain_options_integration" {
  rest_api_id             = aws_api_gateway_rest_api.fraud_api.id
  resource_id             = aws_api_gateway_resource.alarm_type.id
  http_method             = aws_api_gateway_method.explain_options.http_method
  type                    = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "explain_options_200" {
  rest_api_id = aws_api_gateway_rest_api.fraud_api.id
  resource_id = aws_api_gateway_resource.alarm_type.id
  http_method = aws_api_gateway_method.explain_options.http_method
  status_code = "200"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "explain_options_integration_response" {
  rest_api_id = aws_api_gateway_rest_api.fraud_api.id
  resource_id = aws_api_gateway_resource.alarm_type.id
  http_method = aws_api_gateway_method.explain_options.http_method
  status_code = aws_api_gateway_method_response.explain_options_200.status_code
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# /guidance Resource (POST)
resource "aws_api_gateway_resource" "guidance" {
  rest_api_id = aws_api_gateway_rest_api.fraud_api.id
  parent_id   = aws_api_gateway_rest_api.fraud_api.root_resource_id
  path_part   = "guidance"
}

# POST /guidance Method (to chatbot Lambda)
resource "aws_api_gateway_method" "guidance_post" {
  rest_api_id   = aws_api_gateway_rest_api.fraud_api.id
  resource_id   = aws_api_gateway_resource.guidance.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "guidance_integration" {
  rest_api_id             = aws_api_gateway_rest_api.fraud_api.id
  resource_id             = aws_api_gateway_resource.guidance.id
  http_method             = aws_api_gateway_method.guidance_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.chatbot.invoke_arn
}

# OPTIONS /guidance (CORS)
resource "aws_api_gateway_method" "guidance_options" {
  rest_api_id   = aws_api_gateway_rest_api.fraud_api.id
  resource_id   = aws_api_gateway_resource.guidance.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "guidance_options_integration" {
  rest_api_id             = aws_api_gateway_rest_api.fraud_api.id
  resource_id             = aws_api_gateway_resource.guidance.id
  http_method             = aws_api_gateway_method.guidance_options.http_method
  type                    = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "guidance_options_200" {
  rest_api_id = aws_api_gateway_rest_api.fraud_api.id
  resource_id = aws_api_gateway_resource.guidance.id
  http_method = aws_api_gateway_method.guidance_options.http_method
  status_code = "200"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "guidance_options_integration_response" {
  rest_api_id = aws_api_gateway_rest_api.fraud_api.id
  resource_id = aws_api_gateway_resource.guidance.id
  http_method = aws_api_gateway_method.guidance_options.http_method
  status_code = aws_api_gateway_method_response.guidance_options_200.status_code
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'POST,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# API Gateway Deployment
resource "aws_api_gateway_deployment" "api_deployment" {
  rest_api_id = aws_api_gateway_rest_api.fraud_api.id
  stage_name  = var.environment  # deploys to /dev or /prod stage

  depends_on = [
    aws_api_gateway_integration.score_claim_integration,
    aws_api_gateway_integration.explain_integration,
    aws_api_gateway_integration.guidance_integration
  ]

  lifecycle {
    create_before_destroy = true
  }
}

# Stage (with logging)
resource "aws_api_gateway_stage" "api_stage" {
  deployment_id = aws_api_gateway_deployment.api_deployment.id
  rest_api_id   = aws_api_gateway_rest_api.fraud_api.id
  stage_name    = var.environment

  xray_tracing_enabled = true  # Optional X-Ray

  # CloudWatch logging
  logs {
    cloudwatch_logs_role_arn = aws_iam_role.api_gateway_cloudwatch_role.arn
    level                    = "INFO"
    data_trace_enabled       = true
  }

  tags = {
    Name = "${local.project_name}-stage-${var.environment}"
  }
}

# IAM Role for API Gateway CloudWatch Logs
resource "aws_iam_role" "api_gateway_cloudwatch_role" {
  name = "${local.project_name}-apigw-logs-${var.environment}-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "apigateway.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "api_gateway_cloudwatch_policy" {
  name = "${local.project_name}-apigw-logs-${var.environment}-policy"
  role = aws_iam_role.api_gateway_cloudwatch_role.id

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
        Resource = "arn:aws:logs:${var.aws_region}:*:log-group:/aws/apigateway/${local.project_name}-api-${var.environment}/*"
      }
    ]
  })
}

# Lambda Permissions (API Gateway invoke Lambdas)
resource "aws_lambda_permission" "fraud_scoring_permission" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.fraud_scoring.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.fraud_api.execution_arn}/*/*"
}

resource "aws_lambda_permission" "chatbot_permission" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.chatbot.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.fraud_api.execution_arn}/*/*"
}