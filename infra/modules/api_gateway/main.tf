terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

# ─────────────────────────────────────────────
# REST API
#
# Note: WebSocket API was dropped from scope.
# The dashboard uses HTTP polling every 3 seconds
# instead of WebSocket push — simpler and sufficient
# for the demo. This avoids the ws_connections table,
# WebSocket handler Lambda, and connection lifecycle
# complexity.
# ─────────────────────────────────────────────
resource "aws_api_gateway_rest_api" "this" {
  name        = var.api_name
  description = "PFIP REST API — income, expenses, savings goals, and insights endpoints"

  tags = {
    Environment = var.environment
  }
}

# ─────────────────────────────────────────────
# Cognito JWT Authorizer
#
# All protected endpoints (/v1/income, /v1/expenses,
# /v1/goals, /v1/insights) require a valid Cognito JWT.
# API Gateway validates the token before invoking Lambda,
# so Lambda handlers never receive unauthenticated requests.
# ─────────────────────────────────────────────
resource "aws_api_gateway_authorizer" "cognito" {
  name          = "cognito-authorizer"
  rest_api_id   = aws_api_gateway_rest_api.this.id
  type          = "COGNITO_USER_POOLS"
  provider_arns = [var.cognito_user_pool_arn]

  # JWT is passed in the Authorization header
  identity_source = "method.request.header.Authorization"
}

# ─────────────────────────────────────────────
# CORS Configuration
# ─────────────────────────────────────────────
resource "aws_api_gateway_method" "options_root" {
  rest_api_id   = aws_api_gateway_rest_api.this.id
  resource_id   = aws_api_gateway_rest_api.this.root_resource_id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options_root" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  resource_id = aws_api_gateway_rest_api.this.root_resource_id
  http_method = aws_api_gateway_method.options_root.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "options_root" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  resource_id = aws_api_gateway_rest_api.this.root_resource_id
  http_method = aws_api_gateway_method.options_root.http_method
  status_code = "200"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_integration_response" "options_root" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  resource_id = aws_api_gateway_rest_api.this.root_resource_id
  http_method = aws_api_gateway_method.options_root.http_method
  status_code = aws_api_gateway_method_response.options_root.status_code
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'OPTIONS,GET,POST,PUT,DELETE,HEAD'"
    "method.response.header.Access-Control-Allow-Origin"  = "'http://localhost:5173,http://pfip-production-frontend.s3-website-us-east-1.amazonaws.com'"
  }
}

# ─────────────────────────────────────────────
# Note: Deployment is managed in root main.tf
# after all routes/integrations are created.
# ─────────────────────────────────────────────
