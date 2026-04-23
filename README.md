# Personal Financial Intelligence Platform (PFIP)

An AI-native personal finance platform built on AWS serverless architecture with Model Context Protocol (MCP) integration.

## 🚀 Quick Start

This repository contains the complete MVP implementation. See the pull requests for detailed implementation:

- [PR #1: Project Documentation and Configuration](https://github.com/habeneyasu/personal-finance-agent/pull/new/pr/documentation-setup)
- [PR #2: Backend Infrastructure and Core Functionality](https://github.com/habeneyasu/personal-finance-agent/pull/new/pr/backend-infrastructure)  
- [PR #3: React Frontend with Professional UI/UX](https://github.com/habeneyasu/personal-finance-agent/pull/new/pr/frontend-ui-ux)
- [PR #4: Complete MVP Integration](https://github.com/habeneyasu/personal-finance-agent/pull/new/pr/complete-mvp)

## 📋 Architecture

- **Backend**: Python 3.11 with FastAPI + AWS Lambda
- **Database**: Aurora Serverless v2 (PostgreSQL)
- **AI/ML**: AWS Bedrock for expense categorization and insights
- **Frontend**: React + TypeScript with professional UI/UX
- **Infrastructure**: Terraform IaC for AWS deployment
- **Integration**: MCP server for Claude Desktop compatibility

## 🔧 Development Setup

```bash
# Clone the repository
git clone https://github.com/habeneyasu/personal-finance-agent.git
cd personal-finance-agent

# Start local development
docker-compose up -d
python3 scripts/migrate.py --env local
python3 scripts/seed_demo.py --env local --reset
uvicorn scripts.run_api_local:app --port 8000 --reload
cd frontend && npm install && npm run dev
```

## 🎯 Demo

- **URL**: http://localhost:5173
- **Email**: demo@pfip.dev
- **Password**: Demo1234!

## 📚 Documentation

- [Requirements Specification](MVP-Initialy.md)
- [Deployment Guide](DEPLOY.md)
- [API Documentation](docs/api.md)

## 🏗️ Project Structure

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
```

## 🧪 Testing

```bash
pip install -e ".[dev]"
pytest tests/unit/ --cov=src --cov-fail-under=80
```

## 🚀 Deployment

```bash
cd infra
terraform init
terraform apply
```

## 📄 License

MIT License - see LICENSE file for details.
