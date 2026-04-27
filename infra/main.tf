terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }

  # Remote state — S3 bucket created and configured
  backend "s3" {
    bucket = "pfip-terraform-state-523476390411"
    key    = "pfip/production/terraform.tfstate"
    region = "us-east-1"
  }
}

provider "aws" {
  region = var.aws_region
}

# VPC CIDR must be allowed on Aurora SG for traffic from ENIs in this VPC (e.g. 172.31.0.0/16
# in the default VPC). The old 10.0.0.0/8-only rule blocked all default-VPC private addresses.
data "aws_vpc" "pfip" {
  id = var.vpc_id
}

# ─────────────────────────────────────────────
# JWT Secret in Secrets Manager
# ─────────────────────────────────────────────
resource "aws_secretsmanager_secret" "jwt_secret" {
  name        = "pfip/${var.environment}/jwt-secret"
  description = "JWT signing secret for PFIP auth API"
  tags        = { Environment = var.environment }
}

resource "aws_secretsmanager_secret_version" "jwt_secret" {
  secret_id     = aws_secretsmanager_secret.jwt_secret.id
  secret_string = var.jwt_secret
  version_stages = ["AWSCURRENT"]
}

# ─────────────────────────────────────────────
# Aurora Serverless v2 — PostgreSQL 15.4
# ─────────────────────────────────────────────
module "aurora" {
  source = "./modules/aurora"

  cluster_identifier  = "${var.project_name}-${var.environment}"
  database_name       = var.project_name
  master_password     = var.aurora_master_password
  environment         = var.environment
  subnet_ids          = var.subnet_ids
  vpc_id              = var.vpc_id
  allowed_cidr_blocks = distinct(concat(["10.0.0.0/8"], [data.aws_vpc.pfip.cidr_block]))
}

# Lambdas must run in the same VPC as Aurora to reach the private cluster endpoint.
# Secrets Manager is reachable via the Interface VPC endpoint below (no NAT required for DB creds).
# Bedrock and other public AWS APIs still need a NAT or additional VPC endpoints.
resource "aws_security_group" "lambda" {
  name_prefix = "${var.project_name}-${var.environment}-lambda-"
  description = "PFIP Lambda: outbound traffic; Aurora allows 5432 from this SG"
  vpc_id      = var.vpc_id

  egress {
    description = "Internet and AWS APIs (Secrets Manager, Bedrock, etc.)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-lambda"
    Environment = var.environment
  }
}

resource "aws_security_group_rule" "aurora_from_lambda" {
  type                     = "ingress"
  description              = "PostgreSQL from PFIP Lambda ENIs"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = module.aurora.security_group_id
  source_security_group_id = aws_security_group.lambda.id
}

# Lambdas in private subnets without a NAT gateway cannot reach the public Secrets Manager
# endpoint. This interface endpoint keeps GetSecretValue on the AWS private network.
resource "aws_security_group" "secretsmanager_vpce" {
  name_prefix = "${var.project_name}-${var.environment}-smvpce-"
  vpc_id      = var.vpc_id
  description = "Secrets Manager VPC interface endpoint"

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-secretsmanager-vpce"
    Environment = var.environment
  }
}

resource "aws_security_group_rule" "secretsmanager_vpce_from_lambda" {
  type                     = "ingress"
  description              = "HTTPS from PFIP Lambda"
  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  security_group_id        = aws_security_group.secretsmanager_vpce.id
  source_security_group_id = aws_security_group.lambda.id
}

resource "aws_vpc_endpoint" "secretsmanager" {
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.secretsmanager"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = var.subnet_ids
  security_group_ids  = [aws_security_group.secretsmanager_vpce.id]
  private_dns_enabled = true

  tags = {
    Name        = "${var.project_name}-${var.environment}-secretsmanager"
    Environment = var.environment
  }
}

# ─────────────────────────────────────────────
# Cognito — user pool + app client
# ─────────────────────────────────────────────
module "cognito" {
  source = "./modules/cognito"

  user_pool_name = "${var.project_name}-${var.environment}-user-pool"
  client_name    = "${var.project_name}-web-client"
  environment    = var.environment
}

# ─────────────────────────────────────────────
# IAM — per-Lambda least-privilege roles
# ─────────────────────────────────────────────
module "iam" {
  source = "./modules/iam"

  db_secret_arn      = module.aurora.secret_arn
  aurora_cluster_arn = "arn:aws:rds:${var.aws_region}:*:cluster:${var.project_name}-${var.environment}"
  environment        = var.environment
}

# ─────────────────────────────────────────────
# API Gateway — REST API with Cognito authorizer
# ─────────────────────────────────────────────
module "api_gateway" {
  source = "./modules/api_gateway"

  api_name              = "${var.project_name}-api"
  stage_name            = "api"
  cognito_user_pool_arn = module.cognito.user_pool_arn
  environment           = var.environment
  cors_allow_origin     = local.cors_allow_origin
}

# CORS on API Gateway-generated errors (403 before Lambda, etc.) — avoids false "CORS" in DevTools.
resource "aws_api_gateway_gateway_response" "default_4xx" {
  rest_api_id   = module.api_gateway.rest_api_id
  response_type = "DEFAULT_4XX"
  response_parameters = {
    "gatewayresponse.header.Access-Control-Allow-Origin"  = "'${local.cors_allow_origin}'"
    "gatewayresponse.header.Access-Control-Allow-Methods" = "'GET,OPTIONS,PUT,POST,DELETE,HEAD'"
    "gatewayresponse.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
  }
}

resource "aws_api_gateway_gateway_response" "default_5xx" {
  rest_api_id   = module.api_gateway.rest_api_id
  response_type = "DEFAULT_5XX"
  response_parameters = {
    "gatewayresponse.header.Access-Control-Allow-Origin"  = "'${local.cors_allow_origin}'"
    "gatewayresponse.header.Access-Control-Allow-Methods" = "'GET,OPTIONS,PUT,POST,DELETE,HEAD'"
    "gatewayresponse.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
  }
}

# ─────────────────────────────────────────────
# Common Lambda environment variables
# ─────────────────────────────────────────────
locals {
  # DB_* avoids Secrets Manager at Lambda runtime (no VPC endpoint/NAT required for DB creds).
  # migrate.py / laptops can still use DB_SECRET_ARN from terraform output.
  common_env = {
    ENVIRONMENT      = var.environment
    DB_HOST          = module.aurora.cluster_endpoint
    DB_PORT          = tostring(module.aurora.cluster_port)
    DB_NAME          = module.aurora.database_name
    DB_USER          = module.aurora.master_username
    DB_PASSWORD      = var.aurora_master_password
    JWT_SECRET       = aws_secretsmanager_secret_version.jwt_secret.secret_string
    BEDROCK_MODEL_ID = var.bedrock_model_id
    AWS_REGION_NAME  = var.aws_region
    ALLOWED_ORIGINS  = local.cors_allow_origin
  }
  api_source_arn = "${module.api_gateway.rest_api_execution_arn}/*/*"
  # Browsers allow only one Access-Control-Allow-Origin value; comma-separated origins break preflight.
  cors_allow_origin = var.cors_allow_origin != "" ? var.cors_allow_origin : (
    var.environment == "production"
    ? "http://pfip-production-frontend.s3-website-us-east-1.amazonaws.com"
    : var.environment == "staging"
    ? "http://pfip-staging-frontend.s3-website-us-east-1.amazonaws.com"
    : "http://localhost:5173"
  )
}

# ─────────────────────────────────────────────
# Lambda — Income Agent
# ─────────────────────────────────────────────
module "lambda_income" {
  source                 = "./modules/lambda"
  function_name          = "${var.project_name}-${var.environment}-income-agent"
  handler                = "handler.lambda_handler"
  role_arn               = module.iam.income_agent_role_arn
  filename               = "${path.module}/../dist/income_agent.zip"
  timeout                = 30
  memory_size            = 512
  environment_variables  = local.common_env
  api_gateway_source_arn = local.api_source_arn
  vpc_subnet_ids         = var.subnet_ids
  vpc_security_group_ids = [aws_security_group.lambda.id]
}

# ─────────────────────────────────────────────
# Lambda — Expense Agent
# ─────────────────────────────────────────────
module "lambda_expense" {
  source                 = "./modules/lambda"
  function_name          = "${var.project_name}-${var.environment}-expense-agent"
  handler                = "handler.lambda_handler"
  role_arn               = module.iam.expense_agent_role_arn
  filename               = "${path.module}/../dist/expense_agent.zip"
  timeout                = 30
  memory_size            = 512
  environment_variables  = local.common_env
  api_gateway_source_arn = local.api_source_arn
  vpc_subnet_ids         = var.subnet_ids
  vpc_security_group_ids = [aws_security_group.lambda.id]
}

# ─────────────────────────────────────────────
# Lambda — Savings Agent
# ─────────────────────────────────────────────
module "lambda_savings" {
  source                 = "./modules/lambda"
  function_name          = "${var.project_name}-${var.environment}-savings-agent"
  handler                = "handler.lambda_handler"
  role_arn               = module.iam.savings_agent_role_arn
  filename               = "${path.module}/../dist/savings_agent.zip"
  timeout                = 30
  memory_size            = 512
  environment_variables  = local.common_env
  api_gateway_source_arn = local.api_source_arn
  vpc_subnet_ids         = var.subnet_ids
  vpc_security_group_ids = [aws_security_group.lambda.id]
}

# ─────────────────────────────────────────────
# Lambda — Insights Agent (higher timeout for Bedrock)
# ─────────────────────────────────────────────
module "lambda_insights" {
  source                 = "./modules/lambda"
  function_name          = "${var.project_name}-${var.environment}-insights-agent"
  handler                = "handler.lambda_handler"
  role_arn               = module.iam.insights_agent_role_arn
  filename               = "${path.module}/../dist/insights_agent.zip"
  timeout                = 60
  memory_size            = 512
  environment_variables  = local.common_env
  api_gateway_source_arn = local.api_source_arn
  vpc_subnet_ids         = var.subnet_ids
  vpc_security_group_ids = [aws_security_group.lambda.id]
}

# ─────────────────────────────────────────────
# Lambda — Metrics Agent
# ─────────────────────────────────────────────
module "lambda_metrics" {
  source                 = "./modules/lambda"
  function_name          = "${var.project_name}-${var.environment}-metrics-agent"
  handler                = "handler.lambda_handler"
  role_arn               = module.iam.metrics_agent_role_arn
  filename               = "${path.module}/../dist/metrics_agent.zip"
  timeout                = 30
  memory_size            = 512
  environment_variables  = local.common_env
  api_gateway_source_arn = local.api_source_arn
  vpc_subnet_ids         = var.subnet_ids
  vpc_security_group_ids = [aws_security_group.lambda.id]
}

# ─────────────────────────────────────────────
# Lambda — MCP Server
# ─────────────────────────────────────────────
module "lambda_mcp_server" {
  source        = "./modules/lambda"
  function_name = "${var.project_name}-${var.environment}-mcp-server"
  handler       = "simple_handler.lambda_handler"
  role_arn      = module.iam.mcp_server_role_arn
  filename      = "${path.module}/../dist/mcp_server.zip"
  timeout       = 30
  memory_size   = 512
  environment_variables = merge(local.common_env, {
    PFIP_API_KEY      = var.pfip_api_key
    INCOME_FUNCTION   = module.lambda_income.function_name
    EXPENSE_FUNCTION  = module.lambda_expense.function_name
    SAVINGS_FUNCTION  = module.lambda_savings.function_name
    INSIGHTS_FUNCTION = module.lambda_insights.function_name
  })
  api_gateway_source_arn = local.api_source_arn
  vpc_subnet_ids         = var.subnet_ids
  vpc_security_group_ids = [aws_security_group.lambda.id]
}

# ─────────────────────────────────────────────
# Lambda — Auth API
# ─────────────────────────────────────────────
module "lambda_auth" {
  source                 = "./modules/lambda"
  function_name          = "${var.project_name}-${var.environment}-auth-api"
  handler                = "handler.lambda_handler"
  role_arn               = module.iam.income_agent_role_arn
  filename               = "${path.module}/../dist/auth_api.zip"
  timeout                = 29
  memory_size            = 256
  environment_variables  = local.common_env
  api_gateway_source_arn = local.api_source_arn
  vpc_subnet_ids         = var.subnet_ids
  vpc_security_group_ids = [aws_security_group.lambda.id]
}

# ─────────────────────────────────────────────
# API Gateway Routes
# Wires each Lambda to its REST endpoint
# ─────────────────────────────────────────────

# Helper: /v1 resource
resource "aws_api_gateway_resource" "v1" {
  rest_api_id = module.api_gateway.rest_api_id
  parent_id   = module.api_gateway.rest_api_root_resource_id
  path_part   = "v1"
}

# ── /v1/health (public health check) ──────────────────────
resource "aws_api_gateway_method" "v1_health_get" {
  rest_api_id   = module.api_gateway.rest_api_id
  resource_id   = aws_api_gateway_resource.v1.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "v1_health_get" {
  rest_api_id             = module.api_gateway.rest_api_id
  resource_id             = aws_api_gateway_resource.v1.id
  http_method             = aws_api_gateway_method.v1_health_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = module.lambda_auth.invoke_arn
}

# CORS for health check
resource "aws_api_gateway_method" "v1_health_options" {
  rest_api_id   = module.api_gateway.rest_api_id
  resource_id   = aws_api_gateway_resource.v1.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "v1_health_options" {
  rest_api_id = module.api_gateway.rest_api_id
  resource_id = aws_api_gateway_resource.v1.id
  http_method = aws_api_gateway_method.v1_health_options.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "v1_health_options" {
  rest_api_id = module.api_gateway.rest_api_id
  resource_id = aws_api_gateway_resource.v1.id
  http_method = aws_api_gateway_method.v1_health_options.http_method
  status_code = "200"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_integration_response" "v1_health_options" {
  rest_api_id = module.api_gateway.rest_api_id
  resource_id = aws_api_gateway_resource.v1.id
  http_method = aws_api_gateway_method.v1_health_options.http_method
  status_code = aws_api_gateway_method_response.v1_health_options.status_code
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'OPTIONS,GET,POST,PUT,DELETE,HEAD'"
    "method.response.header.Access-Control-Allow-Origin"  = "'${local.cors_allow_origin}'"
  }
}

# ── /v1/income ──────────────────────────────
resource "aws_api_gateway_resource" "income" {
  rest_api_id = module.api_gateway.rest_api_id
  parent_id   = aws_api_gateway_resource.v1.id
  path_part   = "income"
}

resource "aws_api_gateway_method" "income_options" {
  rest_api_id   = module.api_gateway.rest_api_id
  resource_id   = aws_api_gateway_resource.income.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_method" "income_post" {
  rest_api_id   = module.api_gateway.rest_api_id
  resource_id   = aws_api_gateway_resource.income.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "income_options" {
  rest_api_id = module.api_gateway.rest_api_id
  resource_id = aws_api_gateway_resource.income.id
  http_method = aws_api_gateway_method.income_options.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "income_options" {
  rest_api_id = module.api_gateway.rest_api_id
  resource_id = aws_api_gateway_resource.income.id
  http_method = aws_api_gateway_method.income_options.http_method
  status_code = "200"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_integration_response" "income_options" {
  rest_api_id = module.api_gateway.rest_api_id
  resource_id = aws_api_gateway_resource.income.id
  http_method = aws_api_gateway_method.income_options.http_method
  status_code = aws_api_gateway_method_response.income_options.status_code
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'OPTIONS,GET,POST,PUT,DELETE,HEAD'"
    "method.response.header.Access-Control-Allow-Origin"  = "'${local.cors_allow_origin}'"
  }
}

resource "aws_api_gateway_integration" "income_post" {
  rest_api_id             = module.api_gateway.rest_api_id
  resource_id             = aws_api_gateway_resource.income.id
  http_method             = aws_api_gateway_method.income_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = module.lambda_income.invoke_arn
}

resource "aws_api_gateway_method" "income_get" {
  rest_api_id   = module.api_gateway.rest_api_id
  resource_id   = aws_api_gateway_resource.income.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "income_get" {
  rest_api_id             = module.api_gateway.rest_api_id
  resource_id             = aws_api_gateway_resource.income.id
  http_method             = aws_api_gateway_method.income_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = module.lambda_income.invoke_arn
}

# ── /v1/expenses ────────────────────────────
resource "aws_api_gateway_resource" "expenses" {
  rest_api_id = module.api_gateway.rest_api_id
  parent_id   = aws_api_gateway_resource.v1.id
  path_part   = "expenses"
}

resource "aws_api_gateway_method" "expenses_post" {
  rest_api_id   = module.api_gateway.rest_api_id
  resource_id   = aws_api_gateway_resource.expenses.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "expenses_post" {
  rest_api_id             = module.api_gateway.rest_api_id
  resource_id             = aws_api_gateway_resource.expenses.id
  http_method             = aws_api_gateway_method.expenses_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = module.lambda_expense.invoke_arn
}

resource "aws_api_gateway_method" "expenses_get" {
  rest_api_id   = module.api_gateway.rest_api_id
  resource_id   = aws_api_gateway_resource.expenses.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "expenses_get" {
  rest_api_id             = module.api_gateway.rest_api_id
  resource_id             = aws_api_gateway_resource.expenses.id
  http_method             = aws_api_gateway_method.expenses_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = module.lambda_expense.invoke_arn
}

# CORS for expenses endpoint
resource "aws_api_gateway_method" "expenses_options" {
  rest_api_id   = module.api_gateway.rest_api_id
  resource_id   = aws_api_gateway_resource.expenses.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "expenses_options" {
  rest_api_id = module.api_gateway.rest_api_id
  resource_id = aws_api_gateway_resource.expenses.id
  http_method = aws_api_gateway_method.expenses_options.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "expenses_options" {
  rest_api_id = module.api_gateway.rest_api_id
  resource_id = aws_api_gateway_resource.expenses.id
  http_method = aws_api_gateway_method.expenses_options.http_method
  status_code = "200"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_integration_response" "expenses_options" {
  rest_api_id = module.api_gateway.rest_api_id
  resource_id = aws_api_gateway_resource.expenses.id
  http_method = aws_api_gateway_method.expenses_options.http_method
  status_code = aws_api_gateway_method_response.expenses_options.status_code
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'OPTIONS,GET,POST,PUT,DELETE,HEAD'"
    "method.response.header.Access-Control-Allow-Origin"  = "'${local.cors_allow_origin}'"
  }
}

# ── /v1/goals ───────────────────────────────
resource "aws_api_gateway_resource" "goals" {
  rest_api_id = module.api_gateway.rest_api_id
  parent_id   = aws_api_gateway_resource.v1.id
  path_part   = "goals"
}

resource "aws_api_gateway_method" "goals_post" {
  rest_api_id   = module.api_gateway.rest_api_id
  resource_id   = aws_api_gateway_resource.goals.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "goals_post" {
  rest_api_id             = module.api_gateway.rest_api_id
  resource_id             = aws_api_gateway_resource.goals.id
  http_method             = aws_api_gateway_method.goals_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = module.lambda_savings.invoke_arn
}

# CORS for goals endpoint
resource "aws_api_gateway_method" "goals_options" {
  rest_api_id   = module.api_gateway.rest_api_id
  resource_id   = aws_api_gateway_resource.goals.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "goals_options" {
  rest_api_id = module.api_gateway.rest_api_id
  resource_id = aws_api_gateway_resource.goals.id
  http_method = aws_api_gateway_method.goals_options.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "goals_options" {
  rest_api_id = module.api_gateway.rest_api_id
  resource_id = aws_api_gateway_resource.goals.id
  http_method = aws_api_gateway_method.goals_options.http_method
  status_code = "200"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_integration_response" "goals_options" {
  rest_api_id = module.api_gateway.rest_api_id
  resource_id = aws_api_gateway_resource.goals.id
  http_method = aws_api_gateway_method.goals_options.http_method
  status_code = aws_api_gateway_method_response.goals_options.status_code
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'OPTIONS,GET,POST,PUT,DELETE,HEAD'"
    "method.response.header.Access-Control-Allow-Origin"  = "'${local.cors_allow_origin}'"
  }
}

resource "aws_api_gateway_method" "goals_get" {
  rest_api_id   = module.api_gateway.rest_api_id
  resource_id   = aws_api_gateway_resource.goals.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "goals_get" {
  rest_api_id             = module.api_gateway.rest_api_id
  resource_id             = aws_api_gateway_resource.goals.id
  http_method             = aws_api_gateway_method.goals_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = module.lambda_savings.invoke_arn
}

# ── /v1/insights/query ──────────────────────
resource "aws_api_gateway_resource" "insights" {
  rest_api_id = module.api_gateway.rest_api_id
  parent_id   = aws_api_gateway_resource.v1.id
  path_part   = "insights"
}

resource "aws_api_gateway_resource" "insights_query" {
  rest_api_id = module.api_gateway.rest_api_id
  parent_id   = aws_api_gateway_resource.insights.id
  path_part   = "query"
}

resource "aws_api_gateway_method" "insights_query_post" {
  rest_api_id   = module.api_gateway.rest_api_id
  resource_id   = aws_api_gateway_resource.insights_query.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "insights_query_post" {
  rest_api_id             = module.api_gateway.rest_api_id
  resource_id             = aws_api_gateway_resource.insights_query.id
  http_method             = aws_api_gateway_method.insights_query_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = module.lambda_insights.invoke_arn
}

# CORS for insights endpoint
resource "aws_api_gateway_method" "insights_query_options" {
  rest_api_id   = module.api_gateway.rest_api_id
  resource_id   = aws_api_gateway_resource.insights_query.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "insights_query_options" {
  rest_api_id = module.api_gateway.rest_api_id
  resource_id = aws_api_gateway_resource.insights_query.id
  http_method = aws_api_gateway_method.insights_query_options.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "insights_query_options" {
  rest_api_id = module.api_gateway.rest_api_id
  resource_id = aws_api_gateway_resource.insights_query.id
  http_method = aws_api_gateway_method.insights_query_options.http_method
  status_code = "200"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_integration_response" "insights_query_options" {
  rest_api_id = module.api_gateway.rest_api_id
  resource_id = aws_api_gateway_resource.insights_query.id
  http_method = aws_api_gateway_method.insights_query_options.http_method
  status_code = aws_api_gateway_method_response.insights_query_options.status_code
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'OPTIONS,GET,POST,PUT,DELETE,HEAD'"
    "method.response.header.Access-Control-Allow-Origin"  = "'${local.cors_allow_origin}'"
  }
}

# ── /v1/metrics ──────────────────────────────
resource "aws_api_gateway_resource" "metrics" {
  rest_api_id = module.api_gateway.rest_api_id
  parent_id   = aws_api_gateway_resource.v1.id
  path_part   = "metrics"
}

resource "aws_api_gateway_method" "metrics_get" {
  rest_api_id   = module.api_gateway.rest_api_id
  resource_id   = aws_api_gateway_resource.metrics.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "metrics_get" {
  rest_api_id             = module.api_gateway.rest_api_id
  resource_id             = aws_api_gateway_resource.metrics.id
  http_method             = aws_api_gateway_method.metrics_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = module.lambda_metrics.invoke_arn
}

resource "aws_api_gateway_method" "metrics_options" {
  rest_api_id   = module.api_gateway.rest_api_id
  resource_id   = aws_api_gateway_resource.metrics.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "metrics_options" {
  rest_api_id = module.api_gateway.rest_api_id
  resource_id = aws_api_gateway_resource.metrics.id
  http_method = aws_api_gateway_method.metrics_options.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "metrics_options" {
  rest_api_id = module.api_gateway.rest_api_id
  resource_id = aws_api_gateway_resource.metrics.id
  http_method = aws_api_gateway_method.metrics_options.http_method
  status_code = "200"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_integration_response" "metrics_options" {
  rest_api_id = module.api_gateway.rest_api_id
  resource_id = aws_api_gateway_resource.metrics.id
  http_method = aws_api_gateway_method.metrics_options.http_method
  status_code = aws_api_gateway_method_response.metrics_options.status_code
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'OPTIONS,GET,POST,PUT,DELETE,HEAD'"
    "method.response.header.Access-Control-Allow-Origin"  = "'${local.cors_allow_origin}'"
  }
}

# ── /auth (no Cognito auth — public endpoints) ──
resource "aws_api_gateway_resource" "auth" {
  rest_api_id = module.api_gateway.rest_api_id
  parent_id   = module.api_gateway.rest_api_root_resource_id
  path_part   = "auth"
}

resource "aws_api_gateway_resource" "auth_register" {
  rest_api_id = module.api_gateway.rest_api_id
  parent_id   = aws_api_gateway_resource.auth.id
  path_part   = "register"
}

resource "aws_api_gateway_method" "auth_register_options" {
  rest_api_id   = module.api_gateway.rest_api_id
  resource_id   = aws_api_gateway_resource.auth_register.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_method" "auth_register_post" {
  rest_api_id   = module.api_gateway.rest_api_id
  resource_id   = aws_api_gateway_resource.auth_register.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "auth_register_options" {
  rest_api_id = module.api_gateway.rest_api_id
  resource_id = aws_api_gateway_resource.auth_register.id
  http_method = aws_api_gateway_method.auth_register_options.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "auth_register_options" {
  rest_api_id = module.api_gateway.rest_api_id
  resource_id = aws_api_gateway_resource.auth_register.id
  http_method = aws_api_gateway_method.auth_register_options.http_method
  status_code = "200"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_integration_response" "auth_register_options" {
  rest_api_id = module.api_gateway.rest_api_id
  resource_id = aws_api_gateway_resource.auth_register.id
  http_method = aws_api_gateway_method.auth_register_options.http_method
  status_code = aws_api_gateway_method_response.auth_register_options.status_code
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'OPTIONS,GET,POST,PUT,DELETE,HEAD'"
    "method.response.header.Access-Control-Allow-Origin"  = "'${local.cors_allow_origin}'"
  }
}

resource "aws_api_gateway_integration" "auth_register_post" {
  rest_api_id             = module.api_gateway.rest_api_id
  resource_id             = aws_api_gateway_resource.auth_register.id
  http_method             = aws_api_gateway_method.auth_register_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = module.lambda_auth.invoke_arn
}

# CORS for auth register

resource "aws_api_gateway_resource" "auth_login" {
  rest_api_id = module.api_gateway.rest_api_id
  parent_id   = aws_api_gateway_resource.auth.id
  path_part   = "login"
}

resource "aws_api_gateway_method" "auth_login_post" {
  rest_api_id   = module.api_gateway.rest_api_id
  resource_id   = aws_api_gateway_resource.auth_login.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "auth_login_post" {
  rest_api_id             = module.api_gateway.rest_api_id
  resource_id             = aws_api_gateway_resource.auth_login.id
  http_method             = aws_api_gateway_method.auth_login_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = module.lambda_auth.invoke_arn
}

# CORS for auth login
resource "aws_api_gateway_method" "auth_login_options" {
  rest_api_id   = module.api_gateway.rest_api_id
  resource_id   = aws_api_gateway_resource.auth_login.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "auth_login_options" {
  rest_api_id = module.api_gateway.rest_api_id
  resource_id = aws_api_gateway_resource.auth_login.id
  http_method = aws_api_gateway_method.auth_login_options.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "auth_login_options" {
  rest_api_id = module.api_gateway.rest_api_id
  resource_id = aws_api_gateway_resource.auth_login.id
  http_method = aws_api_gateway_method.auth_login_options.http_method
  status_code = "200"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_integration_response" "auth_login_options" {
  rest_api_id = module.api_gateway.rest_api_id
  resource_id = aws_api_gateway_resource.auth_login.id
  http_method = aws_api_gateway_method.auth_login_options.http_method
  status_code = aws_api_gateway_method_response.auth_login_options.status_code
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'OPTIONS,GET,POST,PUT,DELETE,HEAD'"
    "method.response.header.Access-Control-Allow-Origin"  = "'${local.cors_allow_origin}'"
  }
}

# ─────────────────────────────────────────────
# API Gateway Deployment (depends on all routes)
# ─────────────────────────────────────────────
resource "aws_api_gateway_deployment" "main" {
  rest_api_id = module.api_gateway.rest_api_id

  depends_on = [
    aws_api_gateway_integration.income_post,
    aws_api_gateway_integration.income_get,
    aws_api_gateway_integration.income_options,
    aws_api_gateway_integration.expenses_post,
    aws_api_gateway_integration.expenses_get,
    aws_api_gateway_integration.expenses_options,
    aws_api_gateway_integration.goals_post,
    aws_api_gateway_integration.goals_get,
    aws_api_gateway_integration.goals_options,
    aws_api_gateway_integration.insights_query_post,
    aws_api_gateway_integration.insights_query_options,
    aws_api_gateway_integration.metrics_get,
    aws_api_gateway_integration.metrics_options,
    aws_api_gateway_integration.auth_register_post,
    aws_api_gateway_integration.auth_register_options,
    aws_api_gateway_integration.auth_login_post,
    aws_api_gateway_integration.auth_login_options,
    aws_api_gateway_integration.v1_health_get,
    aws_api_gateway_integration_response.v1_health_options,
    aws_api_gateway_integration_response.income_options,
    aws_api_gateway_integration_response.expenses_options,
    aws_api_gateway_integration_response.goals_options,
    aws_api_gateway_integration_response.insights_query_options,
    aws_api_gateway_integration_response.metrics_options,
    aws_api_gateway_integration_response.auth_register_options,
    aws_api_gateway_integration_response.auth_login_options,
        aws_api_gateway_gateway_response.default_4xx,
    aws_api_gateway_gateway_response.default_5xx,
  ]

  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_gateway_response.default_4xx.id,
      aws_api_gateway_gateway_response.default_5xx.id,
      aws_api_gateway_resource.v1.id,
      aws_api_gateway_resource.income.id,
      aws_api_gateway_resource.expenses.id,
      aws_api_gateway_resource.goals.id,
      aws_api_gateway_resource.insights_query.id,
      aws_api_gateway_resource.metrics.id,
      aws_api_gateway_resource.auth_login.id,
      sha1(jsonencode({
        v1_health  = aws_api_gateway_integration_response.v1_health_options.response_parameters
        income     = aws_api_gateway_integration_response.income_options.response_parameters
                expenses   = aws_api_gateway_integration_response.expenses_options.response_parameters
        goals      = aws_api_gateway_integration_response.goals_options.response_parameters
        insights   = aws_api_gateway_integration_response.insights_query_options.response_parameters
        metrics    = aws_api_gateway_integration_response.metrics_options.response_parameters
        auth_reg   = aws_api_gateway_integration_response.auth_register_options.response_parameters
        auth_login = aws_api_gateway_integration_response.auth_login_options.response_parameters
      })),
      local.cors_allow_origin,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_stage" "v1" {
  deployment_id = aws_api_gateway_deployment.main.id
  rest_api_id   = module.api_gateway.rest_api_id
  stage_name    = "api"
}

# ─────────────────────────────────────────────
# S3 + CloudFront — Frontend Hosting
# ─────────────────────────────────────────────
# ─────────────────────────────────────────────
# S3 — Frontend Hosting (public static website)
# Note: CloudFront skipped — account not verified for CloudFront.
# Using S3 static website hosting directly for the demo.
# ─────────────────────────────────────────────
resource "aws_s3_bucket" "frontend" {
  bucket        = "${var.project_name}-${var.environment}-frontend"
  force_destroy = true
  tags          = { Environment = var.environment }
}

resource "aws_s3_bucket_website_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  index_document { suffix = "index.html" }
  error_document { key = "index.html" }
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket                  = aws_s3_bucket.frontend.id
  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket_policy" "frontend" {
  bucket     = aws_s3_bucket.frontend.id
  depends_on = [aws_s3_bucket_public_access_block.frontend]
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "PublicReadGetObject"
      Effect    = "Allow"
      Principal = "*"
      Action    = "s3:GetObject"
      Resource  = "${aws_s3_bucket.frontend.arn}/*"
    }]
  })
}
