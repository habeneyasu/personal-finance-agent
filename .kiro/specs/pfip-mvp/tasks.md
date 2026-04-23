# Implementation Plan: Personal Financial Intelligence Platform MVP

## Overview

3-day sprint (Wed–Fri). The goal is a working demo Friday: Claude Desktop talking to 4 MCP agents backed by real AWS infrastructure. Every task is essential — nothing here is padding.

**Demo target:** MCP server + 4 agents + Bedrock + simple dashboard + seed data. That's it.

**Dropped from original plan:**
- WebSocket (replaced with HTTP polling — simpler, sufficient for demo)
- Property-based tests (unit tests cover correctness for 3-day scope)
- Integration test suite (smoke tests in Task 16 cover demo needs)
- Semantic version tagging
- `ws_connections` DB table (no WebSocket)

---

## Day 1 — Wednesday: Infrastructure + Data + Auth

- [x] 1. Bootstrap project structure and shared utilities
  - Repo layout, `pyproject.toml`, `src/shared/` (logger, exceptions, validation), tests scaffold
  - _Done_

- [x] 2. Terraform — Aurora Serverless v2 module
  - `infra/modules/aurora/` — cluster, instance, Secrets Manager
  - _Done_

- [x] 3. Terraform — Cognito, IAM, Lambda, API Gateway modules
  - `infra/modules/cognito/main.tf`: user pool, email verification, password policy, app client
  - `infra/modules/iam/main.tf`: per-Lambda roles — scoped to Aurora, Bedrock, Secrets Manager ARNs only
  - `infra/modules/lambda/main.tf`: reusable module — `aws_lambda_function` (Python 3.11), `aws_cloudwatch_log_group` (7-day retention), `aws_lambda_permission`
  - `infra/modules/api_gateway/main.tf`: REST API only (no WebSocket) with Cognito JWT authorizer
  - `infra/main.tf` wiring all modules with `variables.tf` and `outputs.tf`
  - _Requirements: 8.2–8.5, 8.7_

- [x] 4. Database schema + migration script
  - `scripts/migrate.py`: DDL for `users`, `income_entries`, `expense_entries`, `savings_goals` tables with indexes and FK constraints (no `ws_connections`)
  - `scripts/seed_demo.py` stub — full implementation in Task 14
  - _Requirements: 11.1–11.7_

- [x] 5. Auth middleware
  - `src/shared/auth.py` — decode and verify Cognito JWT using `python-jose`; extract `user_id` from claims
  - `src/shared/db.py` — DB connection helper: reads credentials from Secrets Manager, returns `psycopg2` connection
  - `tests/unit/test_auth.py` — valid token, expired token (401), malformed token (401)
  - _Requirements: 6.1–6.7_

---

## Day 2 — Thursday: 4 Agents + MCP Server

- [x] 6. Income Agent Lambda
  - `src/income_agent/handler.py` — FastAPI + mangum, `POST /v1/income`, `GET /v1/income`
  - Validate: amount > 0, date not in future; persist to `income_entries`; return 201
  - `GET`: return entries sorted by `date DESC`
  - `tests/unit/test_income_agent.py` — create, list, invalid amount, future date
  - _Requirements: 1.1–1.6, 10.1_

- [x] 7. Expense Agent Lambda
  - `src/expense_agent/handler.py` — `POST /v1/expenses`, `GET /v1/expenses`
  - `src/expense_agent/categorizer.py` — Bedrock prompt (fixed template from design.md); fallback to "Other" on any error; validate category is in allowed set
  - `tests/unit/test_expense_agent.py` — create with mocked Bedrock, Bedrock failure → "Other", list, invalid amount
  - _Requirements: 2.1–2.7, 10.2, 14.1–14.2_

- [x] 8. Savings Goal Agent Lambda
  - `src/savings_agent/handler.py` — `POST /v1/goals`, `GET /v1/goals`
  - `src/savings_agent/calculator.py` — `calculate_progress()` and `predict_completion()` (MVP simplified formula)
  - `GET`: return goals with `current_amount`, `progress_pct`, `predicted_completion_date`
  - `tests/unit/test_savings_agent.py` — progress calc, prediction, zero rate → null date, past target date rejection
  - _Requirements: 3.1–3.7, 10.3_

- [x] 9. Insights Agent Lambda
  - `src/insights_agent/handler.py` — `POST /v1/insights/query`
  - Assemble context: last 90 days income + expenses + active goals → JSON
  - Bedrock call using structured prompt template from design.md; validate response non-empty; fallback message on failure
  - Log `bedrock_latency_ms` as custom CloudWatch metric via `aws-lambda-powertools` Metrics
  - `tests/unit/test_insights_agent.py` — context assembly, mocked Bedrock response, failure fallback
  - _Requirements: 4.1–4.7, 10.4, 14.3–14.6_

- [x] 10. MCP Server Lambda
  - `src/mcp_server/handler.py` — MCP protocol router
  - Register all 7 tools (tool naming: `{verb}_{entity}` snake_case); implement `tools/list` discovery
  - Each invocation: authenticate via API key, invoke target Lambda via `boto3 lambda.invoke()`, return MCP-compliant JSON (`result` or `error`)
  - Expose resources: `income://entries`, `expenses://entries`, `goals://active`
  - Structured log per invocation: `user_id`, `tool_name`, `timestamp`
  - `tests/unit/test_mcp_server.py` — tool discovery, successful invocation, error shape, log fields
  - _Requirements: 7.1–7.7_

- [x] 11. Day 2 checkpoint — all agents working locally
  - Run `pytest tests/ --cov=src --cov-fail-under=80`
  - Verify all 5 Lambda handlers import cleanly with no errors
  - Test MCP tool call manually: `create_expense_entry` → confirm Bedrock categorization works

---

## Day 3 — Friday: Dashboard + Demo + Deploy

- [x] 12. React dashboard (minimal)
  - Vite + TypeScript in `frontend/`; install `axios`, `recharts`
  - Local JWT login/logout via `src/auth_api/handler.py` (bcrypt + python-jose)
  - Login page: email + password form → JWT stored in `localStorage` → attached to all API calls
  - 4 pages: **Overview** (income total, expense total, net — bar chart + pie chart), **Transactions** (income + expense lists with add forms), **Goals** (goal cards with progress bars), **Insights** (chat UI)
  - HTTP polling every 3 seconds to refresh totals (replaces WebSocket — simpler, sufficient for demo)
  - _Requirements: 5.1–5.7, 6.1–6.7, 12.7_

- [x] 13. Insights UI
  - Add **Insights** page: chat-style text input → `POST /v1/insights/query` → render answer
  - _Requirements: 4.6, 12.3, 12.4_

- [x] 14. Demo seed data + demo script
  - Complete `scripts/seed_demo.py`: create demo user, 3 months income (salary + freelance), 2 months expenses across all 8 categories, 2 goals (vacation, emergency fund)
  - Write `scripts/demo_script.md`:
    - Happy path: add expense via Claude Desktop → show categorization → ask insights query
    - Failure scenario: trigger Bedrock fallback → show "Other" category + system continues
    - Invalid input: submit negative amount → show HTTP 400 error message
    - State known limitations (savings goal simplified formula)
  - _Requirements: 12.1–12.9_

- [x] 15. GitHub Actions CI/CD (minimal)
  - `.github/workflows/deploy.yml`:
    - `test` job: `pytest --cov=src --cov-fail-under=80`
    - `terraform` job (needs: test): `terraform init && plan && apply`
    - `deploy-lambdas` job (needs: terraform): zip + `aws lambda update-function-code` for each agent
  - _Requirements: 9.1–9.5_

- [x]* 15.1 CloudWatch alarms + X-Ray (optional)
  - X-Ray active tracing on all Lambdas (`tracing_config { mode = "Active" }`) — in `infra/main.tf`
  - CloudWatch alarm: error rate > 5% over 5 min per Lambda — in `infra/main.tf`
  - JWT secret stored in Secrets Manager — done
  - S3 + CloudFront frontend hosting — done
  - API Gateway routes fully wired — done
  - _Requirements: 16.1–16.6_

- [x] 16. Final smoke test + demo rehearsal
  - Deploy to staging via `terraform apply` + Lambda deploy
  - Run `seed_demo.py --env staging`
  - Smoke test all demo scenarios from `demo_script.md`
  - Verify: non-AI endpoints < 500ms, AI endpoints < 3s
  - Connect Claude Desktop to MCP server — confirm all 7 tools discoverable
  - Rehearse full demo flow end-to-end

---

## What's NOT in scope (intentional)

- WebSocket real-time push (HTTP polling is sufficient for demo)
- Property-based tests (unit tests cover correctness)
- Multi-currency, receipt OCR, fraud detection, investment tracking
- Per-goal savings allocation (simplified formula documented in demo script)
- Semantic version tagging
- Full integration test suite

## What was added beyond original scope

- `src/auth_api/handler.py` — local JWT auth (register/login/me) with bcrypt
- `frontend/src/components/Login.tsx` — login/register UI
- `infra/main.tf` — full API Gateway route wiring, S3+CloudFront frontend hosting, JWT secret in Secrets Manager
- `.env.example` + `infra/terraform.tfvars.example` — all config as placeholders
- `DEPLOY.md` — step-by-step AWS deployment guide
- `scripts/package_lambdas.sh` — Lambda packaging script
