# Implementation Tasks: Personal Financial Intelligence Platform MVP

## Status Legend
- `[ ]` Not started
- `[-]` In progress
- `[x]` Completed

---

## Phase 1: Core Infrastructure

- [x] 1. Database schema and migrations
  - [x] 1.1 Create `scripts/migrate.py` with idempotent DDL statements
  - [x] 1.2 users, income_entries, expense_entries, savings_goals tables
  - [x] 1.3 llm_usage table for LLM cost/latency tracking
  - [x] 1.4 Add `initial_amount` column to savings_goals (ALTER TABLE IF NOT EXISTS)

- [x] 2. Shared infrastructure
  - [x] 2.1 `src/shared/db.py` — psycopg2 connection with env-based config
  - [x] 2.2 `src/shared/auth.py` — JWT validation, ENVIRONMENT=local bypass
  - [x] 2.3 `src/shared/llm.py` — Cerebras + Bedrock client with usage tracking
  - [x] 2.4 `src/shared/logger.py` — structured JSON logger
  - [x] 2.5 `src/shared/validation.py` — shared validators (positive amount, future date)
  - [x] 2.6 `src/shared/exceptions.py` — unhandled exception decorator

---

## Phase 2: Domain Agents

- [x] 3. Income Agent
  - [x] 3.1 `POST /v1/income` — create entry with validation
  - [x] 3.2 `GET /v1/income` — list entries sorted by date DESC
  - [x] 3.3 Unit tests (TestCreateIncome, TestListIncome)

- [x] 4. Expense Agent
  - [x] 4.1 `POST /v1/expenses` — create entry with LLM categorization
  - [x] 4.2 `GET /v1/expenses` — list entries with categories
  - [x] 4.3 `src/expense_agent/categorizer.py` — Cerebras/Bedrock + rule-based fallback
  - [x] 4.4 Unit tests (TestCreateExpense, TestListExpenses, TestCategorizer)

- [x] 5. Savings Goal Agent
  - [x] 5.1 `POST /v1/goals` — create goal with initial_amount support
  - [x] 5.2 `GET /v1/goals` — list with progress_pct + predicted_completion_date
  - [x] 5.3 `src/savings_agent/calculator.py` — progress formula + monthly rate
  - [x] 5.4 Unit tests (TestCreateGoal, TestListGoals, TestCalculateProgress)

---

## Phase 3: Insights Agent (Production-Grade AI Governance)

- [x] 6. Agent contracts (Pydantic models)
  - [x] 6.1 `IncomeAgentContract` — typed output with fetched_at
  - [x] 6.2 `ExpenseAgentContract` — typed output with by_category + fetched_at
  - [x] 6.3 `SavingsAgentContract` — typed output with progress_pct + fetched_at
  - [x] 6.4 `OrchestrationState` — trace_id, data_sources, llm_calls, validation_attempts, guardrail flags
  - [x] 6.5 `ValidationResult` — per-attempt pass/fail tracking
  - [x] 6.6 `InsightResponse` — includes trace_id, decision, reason, retried, data_sources

- [x] 7. Context builder (Coordinator pattern)
  - [x] 7.1 `fetch_income_context()` — returns IncomeAgentContract
  - [x] 7.2 `fetch_expense_context()` — returns ExpenseAgentContract
  - [x] 7.3 `fetch_savings_context()` — returns SavingsAgentContract
  - [x] 7.4 `build_financial_context()` — coordinator merges contracts, tracks data_sources

- [x] 8. Validation Engine + Decision Loop
  - [x] 8.1 LLM output schema validator (pre-gate) — rejects empty, JSON, over-length
  - [x] 8.2 Layer 1: Numeric grounding (±1.5% tolerance)
  - [x] 8.3 Layer 2: Coverage check (categories, goals referenced)
  - [x] 8.4 Layer 3: Relevance check (not a deflection)
  - [x] 8.5 Layer 4: Consistency check (no self-contradiction)
  - [x] 8.6 Explicit retry loop (MAX_RETRIES=1, bounded)
  - [x] 8.7 SQL fallback (deterministic answers for common queries)
  - [x] 8.8 Guardrail constants: MAX_RETRIES, MAX_ANSWER_TOKENS, LLM_TIMEOUT_S, COST_LIMIT_USD, LATENCY_LIMIT_MS

- [x] 9. Insights handler
  - [x] 9.1 `POST /v1/insights/query` — full pipeline with OrchestrationState
  - [x] 9.2 trace_id propagation through state, logs, and response
  - [x] 9.3 Runtime guardrail checks (latency, cost)
  - [x] 9.4 Decision transparency in API response

- [x] 10. Insights unit tests
  - [x] 10.1 TestQueryInsights — basic cases, no-data, local dev mode
  - [x] 10.2 TestBedrockFailureFallback — LLM exception + empty response
  - [x] 10.3 TestContextAssembly — income/expense/goal totals, category aggregation
  - [x] 10.4 TestValidationEngine — all 4 layers (grounding, coverage, relevance, consistency)
  - [x] 10.5 TestCoordinatorPattern — worker contracts, data_sources tracking
  - [x] 10.6 TestConsistencyCheck — self-contradiction detection
  - [x] 10.7 TestOrchestrationState — trace_id, finish(), data_sources
  - [x] 10.8 TestLlmOutputSchemaValidation — empty, JSON, too-long rejection
  - [x] 10.9 TestGuardrailConstants — MAX_RETRIES, COST_LIMIT_USD, LATENCY_LIMIT_MS
  - [x] 10.10 TestDecisionTransparency — decision + trace_id in API response

---

## Phase 4: Metrics Agent

- [x] 11. Metrics Agent
  - [x] 11.1 `GET /v1/metrics` — quality baselines + LLM usage stats
  - [x] 11.2 Categorization accuracy, data completeness, goal prediction coverage
  - [x] 11.3 LLM usage from `llm_usage` table (total + per-agent breakdown)

---

## Phase 5: Auth API

- [x] 12. Auth API
  - [x] 12.1 `POST /auth/register` — bcrypt hash, JWT return
  - [x] 12.2 `POST /auth/login` — verify bcrypt, JWT return
  - [x] 12.3 `GET /auth/me` — decode JWT, return user info
  - [x] 12.4 ENVIRONMENT=local bypass for development

---

## Phase 6: MCP Server

- [x] 13. MCP Server
  - [x] 13.1 7 tools: create/list income, create/list expenses, create/list goals, query_insights
  - [x] 13.2 3 resources: income://, expenses://, goals://
  - [x] 13.3 Tool discovery via MCP protocol
  - [x] 13.4 Multi-step orchestration support (Claude can chain tools)

---

## Phase 7: React Dashboard

- [x] 14. Frontend
  - [x] 14.1 Overview tab — income/expense/savings summary cards
  - [x] 14.2 Transactions tab — income + expense lists with pagination/scroll
  - [x] 14.3 Goals tab — savings goals with progress bars
  - [x] 14.4 Insights tab — chat UI with decision badge (✓ Accepted / ↺ Retry / ⚡ SQL)
  - [x] 14.5 Metrics tab — LLM usage at top, quality metric cards
  - [x] 14.6 Decision transparency — badge shows decision + reason + data_sources
  - [x] 14.7 HTTP polling every 3 seconds

---

## Phase 8: Infrastructure

- [x] 15. Terraform
  - [x] 15.1 Aurora Serverless v2 module
  - [x] 15.2 Lambda module (Python 3.11, X-Ray, 7-day logs)
  - [x] 15.3 API Gateway REST module
  - [x] 15.4 Cognito module
  - [x] 15.5 IAM least-privilege roles per Lambda
  - [x] 15.6 Secrets Manager for DB credentials + JWT secret

- [x] 16. CI/CD
  - [x] 16.1 GitHub Actions — pytest + coverage (≥73%)
  - [x] 16.2 Terraform plan/apply on main branch
  - [x] 16.3 Frontend build + S3 deploy

---

## Phase 9: Documentation

- [x] 17. Documentation
  - [x] 17.1 `DEVELOPER_GUIDE.md` — local setup, env vars, running tests
  - [x] 17.2 `DEPLOY.md` — AWS deployment steps
  - [x] 17.3 `README.md` — project overview

---

## Current Test Coverage

- Total tests: 163
- Coverage: 78.68%
- Threshold: 73%
