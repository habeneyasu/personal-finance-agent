terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

# ─────────────────────────────────────────────
# Subnet group — Aurora must live in ≥2 AZs
# ─────────────────────────────────────────────
resource "aws_db_subnet_group" "this" {
  name        = "${var.cluster_identifier}-subnet-group"
  subnet_ids  = var.subnet_ids
  description = "Subnet group for Aurora cluster ${var.cluster_identifier}"

  tags = {
    Name        = "${var.cluster_identifier}-subnet-group"
    Environment = var.environment
  }
}

# ─────────────────────────────────────────────
# Security group — allow PostgreSQL inbound from
# specified CIDR blocks only; all outbound allowed
# ─────────────────────────────────────────────
resource "aws_security_group" "this" {
  name        = "${var.cluster_identifier}-sg"
  description = "Allow PostgreSQL (5432) inbound from allowed CIDRs"
  vpc_id      = var.vpc_id

  ingress {
    description = "PostgreSQL from allowed CIDRs"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidr_blocks
  }

  egress {
    description = "All outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.cluster_identifier}-sg"
    Environment = var.environment
  }
}

# ─────────────────────────────────────────────
# Aurora Serverless v2 cluster
#
# Notes:
#   - engine_version: PostgreSQL 15.4 per requirements (8.1, 11.x)
#   - skip_final_snapshot = true: MVP only — avoids leaving orphaned
#     snapshots during rapid iteration; set to false for production
#   - deletion_protection = false: MVP only — allows teardown without
#     manual intervention; enable for production workloads
#   - serverlessv2_scaling_configuration: 0.5–2 ACUs per requirement 8.1
# ─────────────────────────────────────────────
resource "aws_rds_cluster" "this" {
  cluster_identifier      = var.cluster_identifier
  engine                  = "aurora-postgresql"
  engine_mode             = "provisioned"
  engine_version          = "15.12"
  database_name           = var.database_name
  master_username         = var.master_username
  master_password         = var.master_password
  db_subnet_group_name    = aws_db_subnet_group.this.name
  vpc_security_group_ids  = [aws_security_group.this.id]

  # MVP: skip final snapshot to allow clean teardown during development
  skip_final_snapshot = true

  # MVP: deletion protection disabled for rapid iteration; enable in production
  deletion_protection = false
  apply_immediately   = true

  serverlessv2_scaling_configuration {
    min_capacity = 0.5
    max_capacity = 2
  }

  tags = {
    Name        = var.cluster_identifier
    Environment = var.environment
  }
}

# ─────────────────────────────────────────────
# Aurora Serverless v2 instance
#
# A single writer instance is sufficient for the MVP.
# instance_class = "db.serverless" is required for
# Serverless v2 — it delegates capacity to the cluster's
# serverlessv2_scaling_configuration block above.
# publicly_accessible = false keeps the DB inside the VPC.
# ─────────────────────────────────────────────
resource "aws_rds_cluster_instance" "this" {
  identifier         = "${var.cluster_identifier}-instance-1"
  cluster_identifier = aws_rds_cluster.this.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.this.engine
  engine_version     = aws_rds_cluster.this.engine_version

  # Keep the DB private — Lambda functions access it via VPC
  publicly_accessible = false

  tags = {
    Name        = "${var.cluster_identifier}-instance-1"
    Environment = var.environment
  }
}

# ─────────────────────────────────────────────
# Secrets Manager — store DB credentials as JSON
# so Lambda functions can retrieve them at runtime
# without hardcoding credentials in environment vars
# ─────────────────────────────────────────────
resource "aws_secretsmanager_secret" "db_credentials" {
  name        = "pfip/${var.environment}/db-credentials"
  description = "Aurora PostgreSQL credentials for PFIP ${var.environment}"

  tags = {
    Environment = var.environment
  }
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id

  secret_string = jsonencode({
    host     = aws_rds_cluster.this.endpoint
    port     = aws_rds_cluster.this.port
    dbname   = aws_rds_cluster.this.database_name
    username = aws_rds_cluster.this.master_username
    password = var.master_password
  })
}
