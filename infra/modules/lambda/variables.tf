variable "function_name" {
  description = "Name of the Lambda function"
  type        = string
}

variable "handler" {
  description = "Lambda handler (e.g. handler.lambda_handler)"
  type        = string
  default     = "handler.lambda_handler"
}

variable "role_arn" {
  description = "ARN of the IAM role for this Lambda function"
  type        = string
}

variable "filename" {
  description = "Path to the Lambda deployment package (zip file)"
  type        = string
  default     = "placeholder.zip"
}

variable "timeout" {
  description = "Lambda timeout in seconds"
  type        = number
  default     = 30
}

variable "memory_size" {
  description = "Lambda memory size in MB"
  type        = number
  default     = 512
}

variable "environment_variables" {
  description = "Environment variables for the Lambda function"
  type        = map(string)
  default     = {}
}

variable "api_gateway_source_arn" {
  description = "ARN of the API Gateway execution (used to scope Lambda permission)"
  type        = string
}
