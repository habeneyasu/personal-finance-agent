terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }

  # Remote state — create S3 bucket first, then uncomment:
  # aws s3 mb s3://pfip-terraform-state-YOUR_ACCOUNT_ID --region us-east-1
  # backend "s3" {
  #   bucket = "pfip-terraform-state-YOUR_ACCOUNT_ID"
  #   key    = "pfip/staging/terraform.tfstate"
  #   region = "us-east-1"
  # }
}

provider "aws" {
  region = var.aws_region
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
  allowed_cidr_blocks = ["10.0.0.0/8"]
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
  stage_name            = "v1"
  cognito_user_pool_arn = module.cognito.user_pool_arn
  environment           = var.environment
}

# ─────────────────────────────────────────────
# Common Lambda environment variables
# ─────────────────────────────────────────────
locals {
  common_env = {
    ENVIRONMENT      = var.environment
    DB_SECRET_ARN    = module.aurora.secret_arn
    BEDROCK_MODEL_ID = var.bedrock_model_id
    AWS_REGION_NAME  = var.aws_region
  }
  api_source_arn = "${module.api_gateway.rest_api_execution_arn}/*/*"
}

# ─────────────────────────────────────────────
# Lambda — Income Agent
# ─────────────────────────────────────────────
module "lambda_income" {
  source        = "./modules/lambda"
  function_name = "${var.project_name}-${var.environment}-income-agent"
  handler       = "handler.lambda_handler"
  role_arn      = module.iam.income_agent_role_arn
  timeout       = 30
  memory_size   = 512
  environment_variables  = local.common_env
  api_gateway_source_arn = local.api_source_arn
}

# ─────────────────────────────────────────────
# Lambda — Expense Agent
# ─────────────────────────────────────────────
module "lambda_expense" {
  source        = "./modules/lambda"
  function_name = "${var.project_name}-${var.environment}-expense-agent"
  handler       = "handler.lambda_handler"
  role_arn      = module.iam.expense_agent_role_arn
  timeout       = 30
  memory_size   = 512
  environment_variables  = local.common_env
  api_gateway_source_arn = local.api_source_arn
}

# ─────────────────────────────────────────────
# Lambda — Savings Agent
# ─────────────────────────────────────────────
module "lambda_savings" {
  source        = "./modules/lambda"
  function_name = "${var.project_name}-${var.environment}-savings-agent"
  handler       = "handler.lambda_handler"
  role_arn      = module.iam.savings_agent_role_arn
  timeout       = 30
  memory_size   = 512
  environment_variables  = local.common_env
  api_gateway_source_arn = local.api_source_arn
}

# ─────────────────────────────────────────────
# Lambda — Insights Agent (higher timeout for Bedrock)
# ─────────────────────────────────────────────
module "lambda_insights" {
  source        = "./modules/lambda"
  function_name = "${var.project_name}-${var.environment}-insights-agent"
  handler       = "handler.lambda_handler"
  role_arn      = module.iam.insights_agent_role_arn
  timeout       = 60
  memory_size   = 512
  environment_variables  = local.common_env
  api_gateway_source_arn = local.api_source_arn
}

# ─────────────────────────────────────────────
# Lambda — MCP Server
# ─────────────────────────────────────────────
module "lambda_mcp_server" {
  source        = "./modules/lambda"
  function_name = "${var.project_name}-${var.environment}-mcp-server"
  handler       = "handler.lambda_handler"
  role_arn      = module.iam.mcp_server_role_arn
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
}

# ─────────────────────────────────────────────
# Lambda — Auth API
# ─────────────────────────────────────────────
module "lambda_auth" {
  source        = "./modules/lambda"
  function_name = "${var.project_name}-${var.environment}-auth-api"
  handler       = "handler.lambda_handler"
  role_arn      = module.iam.income_agent_role_arn
  timeout       = 15
  memory_size   = 256
  environment_variables = merge(local.common_env, {
    JWT_SECRET = aws_secretsmanager_secret_version.jwt_secret.secret_string
  })
  api_gateway_source_arn = local.api_source_arn
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

# ── /v1/income ──────────────────────────────
resource "aws_api_gateway_resource" "income" {
  rest_api_id = module.api_gateway.rest_api_id
  parent_id   = aws_api_gateway_resource.v1.id
  path_part   = "income"
}

resource "aws_api_gateway_method" "income_post" {
  rest_api_id   = module.api_gateway.rest_api_id
  resource_id   = aws_api_gateway_resource.income.id
  http_method   = "POST"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = module.api_gateway.authorizer_id
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
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = module.api_gateway.authorizer_id
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
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = module.api_gateway.authorizer_id
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
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = module.api_gateway.authorizer_id
}

resource "aws_api_gateway_integration" "expenses_get" {
  rest_api_id             = module.api_gateway.rest_api_id
  resource_id             = aws_api_gateway_resource.expenses.id
  http_method             = aws_api_gateway_method.expenses_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = module.lambda_expense.invoke_arn
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
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = module.api_gateway.authorizer_id
}

resource "aws_api_gateway_integration" "goals_post" {
  rest_api_id             = module.api_gateway.rest_api_id
  resource_id             = aws_api_gateway_resource.goals.id
  http_method             = aws_api_gateway_method.goals_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = module.lambda_savings.invoke_arn
}

resource "aws_api_gateway_method" "goals_get" {
  rest_api_id   = module.api_gateway.rest_api_id
  resource_id   = aws_api_gateway_resource.goals.id
  http_method   = "GET"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = module.api_gateway.authorizer_id
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
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = module.api_gateway.authorizer_id
}

resource "aws_api_gateway_integration" "insights_query_post" {
  rest_api_id             = module.api_gateway.rest_api_id
  resource_id             = aws_api_gateway_resource.insights_query.id
  http_method             = aws_api_gateway_method.insights_query_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = module.lambda_insights.invoke_arn
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

resource "aws_api_gateway_method" "auth_register_post" {
  rest_api_id   = module.api_gateway.rest_api_id
  resource_id   = aws_api_gateway_resource.auth_register.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "auth_register_post" {
  rest_api_id             = module.api_gateway.rest_api_id
  resource_id             = aws_api_gateway_resource.auth_register.id
  http_method             = aws_api_gateway_method.auth_register_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = module.lambda_auth.invoke_arn
}

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

# ─────────────────────────────────────────────
# API Gateway Deployment (depends on all routes)
# ─────────────────────────────────────────────
resource "aws_api_gateway_deployment" "main" {
  rest_api_id = module.api_gateway.rest_api_id
  stage_name  = "v1"

  depends_on = [
    aws_api_gateway_integration.income_post,
    aws_api_gateway_integration.income_get,
    aws_api_gateway_integration.expenses_post,
    aws_api_gateway_integration.expenses_get,
    aws_api_gateway_integration.goals_post,
    aws_api_gateway_integration.goals_get,
    aws_api_gateway_integration.insights_query_post,
    aws_api_gateway_integration.auth_register_post,
    aws_api_gateway_integration.auth_login_post,
  ]

  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.v1.id,
      aws_api_gateway_resource.income.id,
      aws_api_gateway_resource.expenses.id,
      aws_api_gateway_resource.goals.id,
      aws_api_gateway_resource.insights_query.id,
      aws_api_gateway_resource.auth_login.id,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }
}

# ─────────────────────────────────────────────
# S3 + CloudFront — Frontend Hosting
# ─────────────────────────────────────────────
resource "aws_s3_bucket" "frontend" {
  bucket        = "${var.project_name}-${var.environment}-frontend"
  force_destroy = true
  tags          = { Environment = var.environment }
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket                  = aws_s3_bucket.frontend.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_cloudfront_origin_access_control" "frontend" {
  name                              = "${var.project_name}-${var.environment}-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "frontend" {
  enabled             = true
  default_root_object = "index.html"
  comment             = "PFIP ${var.environment} frontend"

  origin {
    domain_name              = aws_s3_bucket.frontend.bucket_regional_domain_name
    origin_id                = "S3-${aws_s3_bucket.frontend.id}"
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
  }

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "S3-${aws_s3_bucket.frontend.id}"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true

    forwarded_values {
      query_string = false
      cookies { forward = "none" }
    }

    min_ttl     = 0
    default_ttl = 3600
    max_ttl     = 86400
  }

  # SPA routing — return index.html for all 404s
  custom_error_response {
    error_code         = 404
    response_code      = 200
    response_page_path = "/index.html"
  }

  restrictions {
    geo_restriction { restriction_type = "none" }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = { Environment = var.environment }
}

# Allow CloudFront to read from S3
resource "aws_s3_bucket_policy" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowCloudFrontRead"
      Effect    = "Allow"
      Principal = { Service = "cloudfront.amazonaws.com" }
      Action    = "s3:GetObject"
      Resource  = "${aws_s3_bucket.frontend.arn}/*"
      Condition = {
        StringEquals = {
          "AWS:SourceArn" = aws_cloudfront_distribution.frontend.arn
        }
      }
    }]
  })
}
