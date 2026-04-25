# PFIP Developer and Deployment Guide

This document is the single technical reference for both local development and AWS production deployment of the Personal Financial Intelligence Platform (PFIP).

---

## 1) What PFIP Does

PFIP is an AI-native personal finance platform where users track income, expenses, and savings goals, then query insights in natural language.

Key architecture decisions:
- FastAPI services run locally as one app (`scripts/run_api_local.py`) and in production as Lambda handlers (via Mangum).
- PostgreSQL is the system of record (Docker locally, Aurora Serverless in AWS).
- LLM calls are used for categorization and insights, with deterministic fallback paths.
- MCP server exposes finance capabilities as AI tools/resources.

---

## 2) High-Level Architecture

### Local
- Frontend: React + Vite (`http://localhost:5173`)
- Backend API: FastAPI (`http://localhost:8000`)
- DB: Postgres Docker container (`localhost:5433`)
- Optional: MCP Inspector + local MCP runner

### Production (AWS)
- API Gateway + Lambda microservices
- Aurora Serverless v2 (PostgreSQL)
- S3 static frontend hosting
- IAM + Secrets Manager + CloudWatch

Core service endpoints:
- `GET/POST /v1/income`
- `GET/POST /v1/expenses`
- `GET/POST /v1/goals`
- `POST /v1/insights/query`
- `GET /v1/metrics`
- Auth: `/auth/register`, `/auth/login`, `/auth/me` (local dev API)

---

## 3) Repository Map

```text
src/
  shared/          # auth, db, llm, logging, exception helpers
  income_agent/    # income handlers
  expense_agent/   # expense handlers + categorizer
  savings_agent/   # goals + calculator
  insights_agent/  # context builder + judge
  metrics_agent/   # quality/metrics endpoint
  mcp_server/      # MCP tools/resources server
  auth_api/        # local auth endpoints
frontend/          # React dashboard
infra/             # Terraform IaC
scripts/           # local runners, migration, seed, packaging
tests/unit/        # unit tests
docker-compose.yml # local postgres
```

---

## 4) Local Development Quick Start

From repo root:

```bash
# 1) Start local Postgres
docker compose up -d

# 2) Apply schema + seed demo data
export $(cat .env.local | grep -v '^#' | grep -v '^$' | xargs)
python3 scripts/migrate.py --env local
python3 scripts/seed_demo.py --env local --reset

# 3) Start backend API
python3 -m uvicorn scripts.run_api_local:app --port 8000 --reload

# 4) Start frontend
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` and login with:
- `demo@pfip.dev`
- `Demo1234!`

Optional MCP inspector:

```bash
npx @modelcontextprotocol/inspector python3 scripts/run_mcp_local.py
```

---

## 5) Request and Auth Flow

### Local auth flow
1. Frontend calls `/auth/login`.
2. Auth API validates bcrypt hash and returns JWT.
3. `run_api_local.py` middleware parses JWT and injects mock API Gateway claims.
4. Agent handlers read `user_id` from request scope via shared auth helper.

### Production auth flow
- API Gateway authorizer validates token before Lambda invocation.
- Same shared user-id extraction path is used in handlers.

---

## 6) Database Notes

Local DB defaults are set by `scripts/run_api_local.py`:
- `DB_HOST=localhost`
- `DB_PORT=5433`
- `DB_NAME=pfip`
- `DB_USER=pfip_admin`
- `DB_PASSWORD=pfip_local_password`

Primary tables:
- `users`
- `income_entries`
- `expense_entries`
- `savings_goals`

---

## 7) AI and Insights Behavior

- Expense categorization priority:
  1. Cerebras (if key configured)
  2. Bedrock (non-local fallback)
  3. Local rule-based categorizer
- Insights endpoint builds structured context and prompts the LLM.
- Judge logic validates numeric claims and falls back to SQL summaries when needed.

---

## 8) Testing

```bash
ENVIRONMENT=local pytest tests/unit/ --cov=src -q
```

---

## 9) AWS Deployment Runbook

## Prerequisites
- AWS CLI configured
- Terraform installed
- Python 3.11+
- Node 20+
- IAM rights for Lambda, API Gateway, RDS/Aurora, S3, CloudWatch, Secrets Manager

## 9.1 Gather AWS values

```bash
aws sts get-caller-identity --query Account --output text
aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" --query "Vpcs[0].VpcId" --output text
aws ec2 describe-subnets --filters "Name=defaultForAz,Values=true" --query "Subnets[0:2].SubnetId" --output text
```

Generate secrets:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"      # jwt_secret
python3 -c "import secrets; print(secrets.token_urlsafe(32))"  # pfip_api_key
python3 -c "import secrets; print(secrets.token_urlsafe(24))"  # aurora password
```

## 9.2 Configure Terraform

Create `infra/terraform.tfvars`:

```hcl
aws_region             = "us-east-1"
environment            = "production"
project_name           = "pfip"
aurora_master_password = "your_secure_password"
vpc_id                 = "vpc-xxxx"
subnet_ids             = ["subnet-aaaa", "subnet-bbbb"]
jwt_secret             = "your_generated_jwt_secret"
pfip_api_key           = "your_generated_api_key"
```

## 9.3 Deploy infrastructure

```bash
cd infra
terraform init
terraform plan
terraform apply
```

## 9.4 Package and deploy Lambda code

From repo root:

```bash
bash scripts/package_lambdas.sh

for agent in income expense savings insights mcp auth; do
  aws lambda update-function-code \
    --function-name "pfip-production-${agent}-agent" \
    --zip-file "fileb://dist/${agent}_agent.zip"
done
```

If auth package differs in your setup, deploy `auth_api` zip explicitly.

## 9.5 Run production migration

```bash
export DB_SECRET_ARN=$(cd infra && terraform output -raw aurora_secret_arn)
python3 scripts/migrate.py --env production
```

## 9.6 Build and deploy frontend

```bash
API_URL=$(cd infra && terraform output -raw api_gateway_url)
echo "VITE_API_URL=${API_URL}" > frontend/.env.production

cd frontend
npm ci
npm run build

# Replace with terraform output bucket name
aws s3 sync dist/ s3://pfip-production-frontend/ --delete
```

---

## 10) Post-Deploy Verification

Smoke tests:

```bash
curl -i "$API_URL/health"
curl -i "$API_URL/v1/metrics"
curl -i -X POST "$API_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@pfip.dev","password":"Demo1234!"}'
```

Check logs:

```bash
aws logs tail /aws/lambda/pfip-production-income-agent --since 10m
aws logs tail /aws/lambda/pfip-production-expense-agent --since 10m
```

---

## 11) Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `ERR_CONNECTION_REFUSED :8000` | API not running | Start uvicorn on port 8000 |
| `500` on `/v1/income` or `/v1/expenses` locally | Postgres down | `docker compose up -d` |
| Browser says "CORS" + backend failing | Error response path | Ensure using current `run_api_local.py` |
| `double /v1/v1/...` requests | Bad `VITE_API_URL` | Remove trailing `/v1` in env var |
| Bedrock/Cerebras fallback answers | Missing API key or provider issue | Verify env vars and provider access |

Useful commands:

```bash
# Local
docker compose ps
curl -i http://127.0.0.1:8000/health

# AWS
aws apigateway get-deployments --rest-api-id <api-id>
aws logs filter-log-events --log-group-name /aws/lambda/pfip-production-auth-api --start-time $(date -d '5 minutes ago' +%s)000
```

---

## 12) Operations and Rollback

Routine tasks:
- monitor Lambda error rates and duration
- review CloudWatch logs
- rotate secrets
- keep dependencies updated

Rollback examples:

```bash
# Lambda rollback
aws lambda update-function-code --function-name <fn-name> --zip-file fileb://dist/<previous>.zip

# Frontend rollback
aws s3 sync dist/previous/ s3://<frontend-bucket>/ --delete
```

---

**Last updated:** Apr 25, 2026  
**Scope:** Local development + production deployment
