output "cluster_endpoint" {
  description = "Writer endpoint for the Aurora cluster (use for INSERT/UPDATE/DELETE)"
  value       = aws_rds_cluster.this.endpoint
}

output "cluster_reader_endpoint" {
  description = "Reader endpoint for the Aurora cluster (use for SELECT queries)"
  value       = aws_rds_cluster.this.reader_endpoint
}

output "cluster_port" {
  description = "Port the Aurora cluster listens on (PostgreSQL default: 5432)"
  value       = aws_rds_cluster.this.port
}

output "database_name" {
  description = "Name of the database created in the Aurora cluster"
  value       = aws_rds_cluster.this.database_name
}

output "master_username" {
  description = "Master username for the Aurora cluster (same as in Secrets Manager JSON)"
  value       = aws_rds_cluster.this.master_username
}

output "secret_arn" {
  description = "ARN of the Secrets Manager secret containing DB credentials"
  value       = aws_secretsmanager_secret.db_credentials.arn
}

output "security_group_id" {
  description = "ID of the security group attached to the Aurora cluster"
  value       = aws_security_group.this.id
}
