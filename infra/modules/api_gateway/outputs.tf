output "rest_api_id" {
  description = "ID of the API Gateway REST API"
  value       = aws_api_gateway_rest_api.this.id
}

output "rest_api_root_resource_id" {
  description = "Root resource ID of the REST API (used to attach child resources)"
  value       = aws_api_gateway_rest_api.this.root_resource_id
}

output "rest_api_execution_arn" {
  description = "Execution ARN of the REST API (used to scope Lambda permissions)"
  value       = aws_api_gateway_rest_api.this.execution_arn
}

output "authorizer_id" {
  description = "ID of the Cognito authorizer (used when attaching methods to routes)"
  value       = aws_api_gateway_authorizer.cognito.id
}

output "deployment_invoke_url" {
  description = "Invoke URL for deployed stage (e.g. https://{id}.execute-api.{region}.amazonaws.com/v1)"
  value       = "https://${aws_api_gateway_rest_api.this.id}.execute-api.us-east-1.amazonaws.com/v1"
}