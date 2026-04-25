# Personal Financial Intelligence Platform (PFIP) MVP

An AI-native personal finance platform built on AWS serverless architecture with Model Context Protocol (MCP) integration. Four specialized agents handle income tracking, expense categorization, savings goals, and natural language insights.

## Architecture

- **Runtime**: Python 3.11 on AWS Lambda (FastAPI + Mangum)
- **Database**: Aurora Serverless v2 (PostgreSQL 15.4)
- **AI**: AWS Bedrock (Claude / Nova) for expense categorization and NL insights
- **LLM-as-Judge**: Validates LLM answers before returning to user — CoT retry + SQL fallback
- **Auth**: AWS Cognito (production) / local JWT (development)
- **MCP**: Model Context Protocol server for Claude Desktop integration
- **IaC**: Terraform
- **CI/CD**: GitHub Actions
- **Frontend**: React + Vite + Recharts

## Project Structure

```
src/
  shared/          # Logger, exception handler, validators, auth, DB
  income_agent/    # Income entry Lambda (POST/GET /v1/income)
  expense_agent/   # Expense Lambda + Bedrock categorizer
  savings_agent/   # Savings goal Lambda + progress calculator
  insights_agent/  # Natural language insights Lambda
  mcp_server/      # MCP protocol server (7 tools, 3 resources)
  auth_api/        # Local auth (register/login/me)
infra/             # Terraform modules (Aurora, Cognito, IAM, Lambda, API GW)
tests/unit/        # pytest unit tests (126 tests, 90% coverage)
scripts/           # DB migration, seed data, local runners
frontend/          # React dashboard (Overview, Transactions, Goals, Insights)
.github/workflows/ # CI/CD pipeline
```

## Quick Start (Local)

**1. Start the database:**
```bash
docker-compose up -d
```

**2. Run migrations + seed demo data:**
```bash
export $(cat .env.local | grep -v '^#' | grep -v '^$' | xargs)
python3 scripts/migrate.py --env local
python3 scripts/seed_demo.py --env local --reset
```

**3. Start the backend API:**
```bash
uvicorn scripts.run_api_local:app --port 8000 --reload
```

**4. Start the frontend:**
```bash
cd frontend && npm install && npm run dev
```

Open http://localhost:5173 — login with `demo@pfip.dev` / `Demo1234!`

**5. Start the MCP Inspector (optional):**
```bash
npx @modelcontextprotocol/inspector python3 scripts/run_mcp_local.py
```

## Running Tests

```bash
pip install -e ".[dev]"
ENVIRONMENT=local pytest tests/unit/ --cov=src --cov-fail-under=80 -q
```

## Demo

See `scripts/demo_script.md` for the full Friday presentation flow.

## AWS Deployment

```bash
cd infra
terraform init
terraform apply \
  -var="aurora_master_password=YourSecurePassword" \
  -var="subnet_ids=[\"subnet-xxx\",\"subnet-yyy\"]" \
  -var="vpc_id=vpc-xxx"
```

Required GitHub secrets for CI/CD:
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
- `AURORA_MASTER_PASSWORD`, `TF_SUBNET_IDS`, `TF_VPC_ID`
