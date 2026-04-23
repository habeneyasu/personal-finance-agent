variable "api_name" {
  description = "Name of the API Gateway REST API"
  type        = string
  default     = "pfip-api"
}

variable "stage_name" {
  description = "Deployment stage name (e.g. v1)"
  type        = string
  default     = "v1"
}

variable "cognito_user_pool_arn" {
  description = "ARN of the Cognito User Pool used for JWT authorization"
  type        = string
}

variable "environment" {
  description = "Deployment environment (e.g. staging, production)"
  type        = string
  default     = "staging"
}
