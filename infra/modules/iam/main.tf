terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

# ─────────────────────────────────────────────
# Common assume-role policy document
# Allows Lambda service to assume these roles
# ─────────────────────────────────────────────
data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

# ─────────────────────────────────────────────
# Shared CloudWatch Logs policy document
# Scoped to /aws/lambda/pfip-* log groups only
# ─────────────────────────────────────────────
data "aws_iam_policy_document" "logs" {
  statement {
    sid    = "CloudWatchLogs"
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    # Scoped to PFIP Lambda log groups only — least privilege
    resources = ["arn:aws:logs:*:*:log-group:/aws/lambda/pfip-*"]
  }
}

# ─────────────────────────────────────────────
# Shared DB access policy document
# Scoped to the specific Aurora cluster and secret ARNs
# ─────────────────────────────────────────────
data "aws_iam_policy_document" "db_access" {
  statement {
    sid    = "SecretsManagerRead"
    effect = "Allow"
    actions = [
      "secretsmanager:GetSecretValue",
    ]
    # Scoped to the specific DB credentials secret — not all secrets
    resources = [var.db_secret_arn]
  }

  statement {
    sid    = "AuroraDataAPI"
    effect = "Allow"
    actions = [
      "rds-data:ExecuteStatement",
      "rds-data:BatchExecuteStatement",
    ]
    # Scoped to the specific Aurora cluster — not all RDS resources
    resources = [var.aurora_cluster_arn]
  }
}

# ─────────────────────────────────────────────
# Bedrock policy document
# Used by expense_agent and insights_agent only
# ─────────────────────────────────────────────
data "aws_iam_policy_document" "bedrock_invoke" {
  statement {
    sid    = "BedrockInvokeModel"
    effect = "Allow"
    actions = [
      "bedrock:InvokeModel",
    ]
    # Scoped to all Bedrock foundation models — model ID is chosen at runtime
    resources = ["arn:aws:bedrock:*:*:foundation-model/*"]
  }
}

# ─────────────────────────────────────────────
# Lambda invoke policy document
# Used by mcp_server only — allows invoking PFIP agent Lambdas
# ─────────────────────────────────────────────
data "aws_iam_policy_document" "lambda_invoke" {
  statement {
    sid    = "InvokePfipLambdas"
    effect = "Allow"
    actions = [
      "lambda:InvokeFunction",
    ]
    # Scoped to PFIP Lambda functions only — not all Lambda functions
    resources = ["arn:aws:lambda:*:*:function:pfip-*"]
  }
}

# ─────────────────────────────────────────────
# Income Agent IAM Role
# Permissions: CloudWatch Logs + DB access
# ─────────────────────────────────────────────
resource "aws_iam_role" "income_agent" {
  name               = "pfip-${var.environment}-income-agent-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json

  tags = {
    Environment = var.environment
    Agent       = "income"
  }
}

resource "aws_iam_role_policy" "income_agent_logs" {
  name   = "logs"
  role   = aws_iam_role.income_agent.id
  policy = data.aws_iam_policy_document.logs.json
}

resource "aws_iam_role_policy" "income_agent_db" {
  name   = "db-access"
  role   = aws_iam_role.income_agent.id
  policy = data.aws_iam_policy_document.db_access.json
}

# ─────────────────────────────────────────────
# Expense Agent IAM Role
# Permissions: CloudWatch Logs + DB access + Bedrock
# (Bedrock needed for merchant categorization)
# ─────────────────────────────────────────────
resource "aws_iam_role" "expense_agent" {
  name               = "pfip-${var.environment}-expense-agent-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json

  tags = {
    Environment = var.environment
    Agent       = "expense"
  }
}

resource "aws_iam_role_policy" "expense_agent_logs" {
  name   = "logs"
  role   = aws_iam_role.expense_agent.id
  policy = data.aws_iam_policy_document.logs.json
}

resource "aws_iam_role_policy" "expense_agent_db" {
  name   = "db-access"
  role   = aws_iam_role.expense_agent.id
  policy = data.aws_iam_policy_document.db_access.json
}

resource "aws_iam_role_policy" "expense_agent_bedrock" {
  name   = "bedrock-invoke"
  role   = aws_iam_role.expense_agent.id
  policy = data.aws_iam_policy_document.bedrock_invoke.json
}

# ─────────────────────────────────────────────
# Savings Agent IAM Role
# Permissions: CloudWatch Logs + DB access
# ─────────────────────────────────────────────
resource "aws_iam_role" "savings_agent" {
  name               = "pfip-${var.environment}-savings-agent-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json

  tags = {
    Environment = var.environment
    Agent       = "savings"
  }
}

resource "aws_iam_role_policy" "savings_agent_logs" {
  name   = "logs"
  role   = aws_iam_role.savings_agent.id
  policy = data.aws_iam_policy_document.logs.json
}

resource "aws_iam_role_policy" "savings_agent_db" {
  name   = "db-access"
  role   = aws_iam_role.savings_agent.id
  policy = data.aws_iam_policy_document.db_access.json
}

# ─────────────────────────────────────────────
# Insights Agent IAM Role
# Permissions: CloudWatch Logs + DB access + Bedrock
# (Bedrock needed for natural language query answering)
# ─────────────────────────────────────────────
resource "aws_iam_role" "insights_agent" {
  name               = "pfip-${var.environment}-insights-agent-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json

  tags = {
    Environment = var.environment
    Agent       = "insights"
  }
}

resource "aws_iam_role_policy" "insights_agent_logs" {
  name   = "logs"
  role   = aws_iam_role.insights_agent.id
  policy = data.aws_iam_policy_document.logs.json
}

resource "aws_iam_role_policy" "insights_agent_db" {
  name   = "db-access"
  role   = aws_iam_role.insights_agent.id
  policy = data.aws_iam_policy_document.db_access.json
}

resource "aws_iam_role_policy" "insights_agent_bedrock" {
  name   = "bedrock-invoke"
  role   = aws_iam_role.insights_agent.id
  policy = data.aws_iam_policy_document.bedrock_invoke.json
}

# ─────────────────────────────────────────────
# Metrics Agent IAM Role
# Permissions: CloudWatch Logs + DB access
# ─────────────────────────────────────────────
resource "aws_iam_role" "metrics_agent" {
  name               = "pfip-${var.environment}-metrics-agent-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json

  tags = {
    Environment = var.environment
    Agent       = "metrics"
  }
}

resource "aws_iam_role_policy" "metrics_agent_logs" {
  name   = "logs"
  role   = aws_iam_role.metrics_agent.id
  policy = data.aws_iam_policy_document.logs.json
}

resource "aws_iam_role_policy" "metrics_agent_db" {
  name   = "db-access"
  role   = aws_iam_role.metrics_agent.id
  policy = data.aws_iam_policy_document.db_access.json
}

# ─────────────────────────────────────────────
# MCP Server IAM Role
# Permissions: CloudWatch Logs + DB access + Lambda invoke
# (Lambda invoke needed to call the 4 agent Lambdas)
# No Bedrock access — MCP server delegates to agents
# ─────────────────────────────────────────────
resource "aws_iam_role" "mcp_server" {
  name               = "pfip-${var.environment}-mcp-server-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json

  tags = {
    Environment = var.environment
    Agent       = "mcp-server"
  }
}

resource "aws_iam_role_policy" "mcp_server_logs" {
  name   = "logs"
  role   = aws_iam_role.mcp_server.id
  policy = data.aws_iam_policy_document.logs.json
}

resource "aws_iam_role_policy" "mcp_server_db" {
  name   = "db-access"
  role   = aws_iam_role.mcp_server.id
  policy = data.aws_iam_policy_document.db_access.json
}

resource "aws_iam_role_policy" "mcp_server_lambda_invoke" {
  name   = "lambda-invoke"
  role   = aws_iam_role.mcp_server.id
  policy = data.aws_iam_policy_document.lambda_invoke.json
}

# Required when Lambdas use vpc_config (ENI creation in VPC)
resource "aws_iam_role_policy_attachment" "income_agent_vpc" {
  role       = aws_iam_role.income_agent.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_iam_role_policy_attachment" "expense_agent_vpc" {
  role       = aws_iam_role.expense_agent.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_iam_role_policy_attachment" "savings_agent_vpc" {
  role       = aws_iam_role.savings_agent.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_iam_role_policy_attachment" "insights_agent_vpc" {
  role       = aws_iam_role.insights_agent.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_iam_role_policy_attachment" "metrics_agent_vpc" {
  role       = aws_iam_role.metrics_agent.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_iam_role_policy_attachment" "mcp_server_vpc" {
  role       = aws_iam_role.mcp_server.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}
