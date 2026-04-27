# ── API ──────────────────────────────────────────────────────
output "api_gateway_url" {
  description = "Base URL for the PFIP REST API — set as VITE_API_URL for frontend"
  value       = "https://${module.api_gateway.rest_api_id}.execute-api.${var.aws_region}.amazonaws.com/api/v1"
}

# ── Auth ─────────────────────────────────────────────────────
output "cognito_user_pool_id" {
  description = "Cognito User Pool ID — set as COGNITO_USER_POOL_ID"
  value       = module.cognito.user_pool_id
}

output "cognito_client_id" {
  description = "Cognito App Client ID — used by frontend SDK"
  value       = module.cognito.client_id
}

# ── Database ─────────────────────────────────────────────────
output "aurora_endpoint" {
  description = "Aurora cluster writer endpoint"
  value       = module.aurora.cluster_endpoint
}

output "aurora_secret_arn" {
  description = "Secrets Manager ARN for DB credentials — set as DB_SECRET_ARN"
  value       = module.aurora.secret_arn
}

# ── Frontend ─────────────────────────────────────────────────
output "frontend_bucket" {
  description = "S3 bucket name for frontend deployment"
  value       = aws_s3_bucket.frontend.id
}

output "frontend_url" {
  description = "S3 static website URL for the frontend dashboard"
  value       = "http://${aws_s3_bucket.frontend.bucket}.s3-website-${var.aws_region}.amazonaws.com"
}

# ── Lambda Functions ─────────────────────────────────────────
output "lambda_function_names" {
  description = "All Lambda function names for CI/CD deployment"
  value = {
    income   = module.lambda_income.function_name
    expense  = module.lambda_expense.function_name
    savings  = module.lambda_savings.function_name
    insights = module.lambda_insights.function_name
    metrics  = module.lambda_metrics.function_name
    mcp      = module.lambda_mcp_server.function_name
    auth     = module.lambda_auth.function_name
  }
}

# ── JWT Secret ───────────────────────────────────────────────
output "jwt_secret_arn" {
  description = "Secrets Manager ARN for JWT secret"
  value       = aws_secretsmanager_secret.jwt_secret.arn
}
