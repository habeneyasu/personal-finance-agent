output "user_pool_id" {
  description = "ID of the Cognito User Pool"
  value       = aws_cognito_user_pool.this.id
}

output "user_pool_arn" {
  description = "ARN of the Cognito User Pool (used by API Gateway authorizer)"
  value       = aws_cognito_user_pool.this.arn
}

output "client_id" {
  description = "ID of the Cognito app client (used by frontend to authenticate)"
  value       = aws_cognito_user_pool_client.this.id
}
