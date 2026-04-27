output "income_agent_role_arn" {
  description = "ARN of the IAM role for the Income Agent Lambda"
  value       = aws_iam_role.income_agent.arn
}

output "expense_agent_role_arn" {
  description = "ARN of the IAM role for the Expense Agent Lambda"
  value       = aws_iam_role.expense_agent.arn
}

output "savings_agent_role_arn" {
  description = "ARN of the IAM role for the Savings Agent Lambda"
  value       = aws_iam_role.savings_agent.arn
}

output "insights_agent_role_arn" {
  description = "ARN of the IAM role for the Insights Agent Lambda"
  value       = aws_iam_role.insights_agent.arn
}

output "metrics_agent_role_arn" {
  description = "ARN of the IAM role for the Metrics Agent Lambda"
  value       = aws_iam_role.metrics_agent.arn
}

output "mcp_server_role_arn" {
  description = "ARN of the IAM role for the MCP Server Lambda"
  value       = aws_iam_role.mcp_server.arn
}
