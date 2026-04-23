variable "db_secret_arn" {
  description = "ARN of the Secrets Manager secret containing Aurora DB credentials"
  type        = string
}

variable "aurora_cluster_arn" {
  description = "ARN of the Aurora cluster (used to scope RDS Data API permissions)"
  type        = string
}

variable "environment" {
  description = "Deployment environment (e.g. staging, production)"
  type        = string
  default     = "staging"
}
