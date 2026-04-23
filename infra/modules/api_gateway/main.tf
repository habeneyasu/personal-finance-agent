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
# Deployment + Stage
#
# depends_on is intentionally empty here — actual route/integration
# resources are added in infra/main.tf when wiring Lambda modules.
# The deployment will be re-created when routes are added.
#
# stage_name defaults to "v1" to match the /v1/ API path prefix.
# ─────────────────────────────────────────────
resource "aws_api_gateway_deployment" "this" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  stage_name  = var.stage_name

  # Force a new deployment when the REST API changes
  triggers = {
    redeployment = sha1(jsonencode(aws_api_gateway_rest_api.this.body))
  }

  lifecycle {
    create_before_destroy = true
  }
}
