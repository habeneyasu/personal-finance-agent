variable "cluster_identifier" {
  description = "Unique identifier for the Aurora cluster"
  type        = string
}

variable "database_name" {
  description = "Name of the initial database to create in the cluster"
  type        = string
  default     = "pfip"
}

variable "master_username" {
  description = "Master username for the Aurora cluster"
  type        = string
  default     = "pfip_admin"
}

variable "master_password" {
  description = "Master password for the Aurora cluster (stored in Secrets Manager)"
  type        = string
  sensitive   = true
}

variable "environment" {
  description = "Deployment environment (e.g. staging, production)"
  type        = string
  default     = "staging"
}

variable "subnet_ids" {
  description = "List of subnet IDs for the DB subnet group (must span ≥2 AZs)"
  type        = list(string)
}

variable "vpc_id" {
  description = "VPC ID where the Aurora cluster and security group will be created"
  type        = string
}

variable "allowed_cidr_blocks" {
  description = "CIDR blocks allowed to connect to Aurora on port 5432 (e.g. Lambda subnet CIDRs)"
  type        = list(string)
  default     = ["10.0.0.0/8"]
}
