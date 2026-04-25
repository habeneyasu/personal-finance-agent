terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

# ─────────────────────────────────────────────
# Lambda Function
#
# Notes:
#   - runtime = "python3.11" per requirements 8.3
#   - filename defaults to "placeholder.zip" so the module
#     can be instantiated before Lambda code is deployed;
#     actual code is deployed via CI/CD (aws lambda update-function-code)
#   - timeout = 30s default; Insights Agent may need more for Bedrock calls
#   - memory_size = 512MB default; sufficient for FastAPI + psycopg2
# ─────────────────────────────────────────────
resource "aws_lambda_function" "this" {
  function_name = var.function_name
  runtime       = "python3.11"
  handler       = var.handler
  role          = var.role_arn
  filename      = local.resolved_filename
  timeout       = var.timeout
  memory_size   = var.memory_size

  tracing_config {
    mode = "Active"
  }

  dynamic "environment" {
    for_each = length(var.environment_variables) > 0 ? [1] : []
    content {
      variables = var.environment_variables
    }
  }

  # Log group is managed separately below to control retention
  depends_on = [aws_cloudwatch_log_group.this]

  tags = {
    Function = var.function_name
  }
}

# ─────────────────────────────────────────────
# CloudWatch Log Group
#
# Created explicitly (rather than letting Lambda auto-create it)
# so we can enforce 7-day retention per requirements 8.7.
# Without this, Lambda creates the log group with infinite retention.
# ─────────────────────────────────────────────
resource "aws_cloudwatch_log_group" "this" {
  name              = "/aws/lambda/${var.function_name}"
  retention_in_days = 7
}

# ─────────────────────────────────────────────
# Lambda Permission — allow API Gateway to invoke
#
# source_arn is passed in from the root module so this
# permission can be scoped to the specific API Gateway
# execution ARN (e.g. arn:aws:execute-api:region:account:api-id/*)
# ─────────────────────────────────────────────
resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.this.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = var.api_gateway_source_arn
}
