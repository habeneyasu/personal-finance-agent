variable "aws_region" {
  description = "AWS region to deploy all resources into"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment (staging | production)"
  type        = string
  default     = "staging"
}

variable "project_name" {
  description = "Short project name used as prefix for all resource names"
  type        = string
  default     = "pfip"
}

variable "aurora_master_password" {
  description = "Master password for Aurora PostgreSQL (stored in Secrets Manager)"
  type        = string
  sensitive   = true
  # No default — provide via TF_VAR_aurora_master_password or terraform.tfvars
}

variable "subnet_ids" {
  description = "VPC subnet IDs for Aurora and Lambda (must span ≥2 AZs)"
  type        = list(string)
  # No default — provide via terraform.tfvars
}

variable "vpc_id" {
  description = "VPC ID where Aurora and Lambda functions will be deployed"
  type        = string
  # No default — provide via terraform.tfvars
}

variable "jwt_secret" {
  description = "Secret key for signing local JWT tokens (min 32 chars)"
  type        = string
  sensitive   = true
  default     = "REPLACE_WITH_STRONG_RANDOM_SECRET_AT_LEAST_32_CHARS"
}

variable "bedrock_model_id" {
  description = "AWS Bedrock model ID for expense categorization and insights"
  type        = string
  default     = "amazon.nova-lite-v1:0"
}

variable "pfip_api_key" {
  description = "API key for MCP server authentication"
  type        = string
  sensitive   = true
  default     = "REPLACE_WITH_STRONG_API_KEY"
}
