# Requirements Document: Personal Financial Intelligence Platform MVP

## Introduction

The Personal Financial Intelligence Platform (PFIP) MVP addresses a well-documented problem: **70% of people who start tracking expenses manually abandon it within 30 days** due to friction. Existing solutions require manual data entry and provide only backward-looking reports.

**Why this is an AI problem, not a rules problem:**
Rule-based categorization breaks on ambiguous merchants, new merchants, and multi-language inputs. Natural language insights require multi-step reasoning over structured data. The conversational interface (MCP) removes the UI entirely for power users.

**Scope decisions and trade-offs:**
- Chose MCP over REST for the agent interface — enables any LLM client to connect without custom integration
- Chose HTTP polling over WebSocket — eliminates connection state management, sufficient for demo latency
- Chose simplified savings formula (global income - expenses) over per-goal allocation — reduces complexity by 60% with acceptable accuracy for MVP
- Chose Aurora Serverless over DynamoDB — financial aggregations are naturally relational; SQL is more expressive
- Added LLM validation loop with OrchestrationState — tracks full execution flow with trace_id, guardrails, and decision metadata

## Glossary

- **MCP_Server**: Model Context Protocol server exposing financial agents as tools and resources
- **Income_Agent**: Agent handling income entry creation and retrieval
- **Expense_Agent**: Agent managing expense entries with AI-powered categorization
- **Savings_Goal_Agent**: Agent tracking savings goals with progress calculation and completion prediction
- **Insights_Agent**: Coordinator agent answering natural language queries — orchestrates worker agents and applies the Validation_Engine
- **OrchestrationState**: Per-request state object tracking trace_id, data_sources, llm_calls, validation_attempts, guardrail flags, decision, and completed_at — enables full observability of every AI decision
- **Validation_Engine**: Deterministic 4-layer validation inside Insights_Agent (numeric grounding, coverage, relevance, consistency) — not a separate deployed agent
- **LLM_Output_Schema_Validator**: Pre-validation gate that rejects empty, JSON-formatted, or over-length LLM outputs before they reach the Validation_Engine
- **API_Gateway**: AWS API Gateway providing REST endpoints
- **Aurora_Database**: Aurora Serverless v2 PostgreSQL database for data persistence
- **Bedrock_Service**: AWS Bedrock service using Nova Lite model for AI reasoning
- **Cerebras_Service**: Cerebras Cloud API (Llama 3.1) for fast, free-tier LLM inference
- **Dashboard**: React web interface displaying financial data with HTTP polling (3-second refresh)
- **Terraform**: Infrastructure as Code tool for AWS resource provisioning
- **GitHub_Actions**: CI/CD pipeline for automated testing and deployment
- **Auth_API**: Local JWT-based authentication service (register/login/me) using bcrypt + python-jose

---

## Requirements

### Requirement 1: Income Entry Management

**User Story:** As a user, I want to add and view income entries, so that I can track my earnings over time.

#### Acceptance Criteria

1. WHEN a user submits an income entry with amount, source, date, and optional notes, THE Income_Agent SHALL persist the entry to Aurora_Database
2. WHEN a user requests income entries, THE Income_Agent SHALL return all entries for the authenticated user sorted by date descending
3. THE Dashboard SHALL reflect new income entries within 3 seconds via HTTP polling
4. THE Income_Agent SHALL validate that amount is a positive decimal number
5. THE Income_Agent SHALL validate that date is in ISO 8601 format and not in the future
6. WHEN an invalid income entry is submitted, THE Income_Agent SHALL return a descriptive error message with HTTP 400 status

---

### Requirement 2: Expense Entry Management with AI Categorization

**User Story:** As a user, I want to add expenses that are automatically categorized, so that I can understand my spending patterns without manual classification.

#### Acceptance Criteria

1. WHEN a user submits an expense entry with amount, merchant, and date, THE Expense_Agent SHALL persist the entry to Aurora_Database
2. WHEN an expense entry is created, THE Expense_Agent SHALL invoke Cerebras_Service (or Bedrock_Service) to categorize the expense based on merchant name and amount
3. THE Expense_Agent SHALL assign a category from the predefined list: Groceries, Transportation, Entertainment, Utilities, Healthcare, Shopping, Dining, Other
4. WHEN a user requests expense entries, THE Expense_Agent SHALL return all entries for the authenticated user with assigned categories
5. THE Expense_Agent SHALL validate that amount is a positive decimal number
6. WHEN LLM categorization fails, THE Expense_Agent SHALL apply rule-based categorization as fallback, defaulting to "Other" if no rule matches

---

### Requirement 3: Savings Goal Tracking

**User Story:** As a user, I want to create savings goals and track my progress, so that I can stay motivated and plan my financial future.

#### Acceptance Criteria

1. WHEN a user creates a savings goal with name, target amount, target date, and optional initial amount, THE Savings_Goal_Agent SHALL persist the goal to Aurora_Database
2. THE Savings_Goal_Agent SHALL calculate current progress using formula: `initial_amount + SUM(income since creation) - SUM(expenses since creation)`, where `initial_amount` is the existing balance at goal creation time (default 0)
3. THE Savings_Goal_Agent SHALL calculate predicted completion date based on average monthly savings rate from the last 30 days
4. WHEN a user requests savings goals, THE Savings_Goal_Agent SHALL return all goals with current amount, target amount, progress percentage, and predicted completion date
5. THE Savings_Goal_Agent SHALL validate that target amount is a positive decimal number
6. THE Savings_Goal_Agent SHALL validate that target date is in the future

---

### Requirement 4: Natural Language Financial Insights with LLM Validation Loop

**User Story:** As a user, I want to ask questions about my finances in natural language and receive accurate, verified answers.

#### Acceptance Criteria

1. WHEN a user submits a natural language query, THE Insights_Agent SHALL create an OrchestrationState object with a unique trace_id to track the full execution flow
2. THE Insights_Agent SHALL act as a coordinator and retrieve data by invoking Income_Agent, Expense_Agent, and Savings_Goal_Agent worker contracts — each returning a typed Pydantic model with a `fetched_at` freshness timestamp
3. THE Insights_Agent SHALL invoke Cerebras_Service (or Bedrock_Service) to generate a draft answer — LLM is ALWAYS called first
4. THE Insights_Agent SHALL apply a strict LLM output schema validator before the Validation_Engine — rejecting empty outputs, JSON-formatted outputs, and outputs exceeding MAX_ANSWER_TOKENS
5. THE Insights_Agent SHALL apply a deterministic Validation_Engine with 4 layers: (a) numeric grounding ±1.5%; (b) coverage check; (c) relevance check; (d) consistency check
6. WHEN all validation layers pass, THE system SHALL return the answer with decision="accept"
7. WHEN any validation layer fails, THE Insights_Agent SHALL retry the LLM call at most MAX_RETRIES=1 times using a chain-of-thought prompt, then re-run all 4 validation layers — retry logic is explicit and bounded, not implicit
8. WHEN the CoT retry also fails, THE system SHALL return a deterministic SQL-computed answer (decision="fallback")
9. THE system SHALL enforce runtime guardrails: COST_LIMIT_USD per request and LATENCY_LIMIT_MS per request — violations are logged with the trace_id
10. THE API response SHALL include `trace_id`, `decision`, `reason`, `retried`, and `data_sources` for full transparency
11. THE Insights_Agent SHALL log every decision with trace_id, decision, reason, llm_calls, and data_sources for evaluation and debugging
12. WHEN a query cannot be answered due to insufficient data, THE Insights_Agent SHALL return a helpful message
13. THE Insights_Agent SHALL orchestrate data retrieval by invoking typed worker contracts (IncomeAgentContract, ExpenseAgentContract, SavingsAgentContract) — not by querying the database directly

---

### Requirement 5: Real-Time Dashboard Updates

**User Story:** As a user, I want the dashboard to update automatically when I add income or expenses.

#### Acceptance Criteria

1. THE Dashboard SHALL poll the API every 3 seconds to refresh income, expense, and goal totals
2. WHEN an income entry is created, THE Dashboard SHALL reflect the new total within 3 seconds
3. WHEN an expense entry is created, THE Dashboard SHALL reflect the new total within 3 seconds
4. THE Dashboard SHALL show a loading indicator while fetching data
5. THE Dashboard SHALL handle API errors gracefully without crashing

> **Note:** WebSocket was dropped from MVP scope. HTTP polling every 3 seconds is sufficient for the demo.

---

### Requirement 6: User Authentication

**User Story:** As a user, I want to securely log in to the system, so that my financial data remains private and protected.

#### Acceptance Criteria

1. WHEN a user registers with email and password, THE Auth_API SHALL create a user account with hashed password stored in Aurora_Database
2. WHEN a user logs in with valid credentials, THE Auth_API SHALL return a JWT access token (24-hour expiry)
3. THE API_Gateway SHALL validate JWT tokens for all protected endpoints
4. WHEN a JWT token is expired or invalid, THE API_Gateway SHALL return HTTP 401 status
5. WHEN a user logs out, THE Dashboard SHALL clear the JWT from localStorage
6. THE Auth_API SHALL enforce password requirements: minimum 8 characters, at least one uppercase, one lowercase, one number
7. WHEN authentication fails, THE Auth_API SHALL return a generic error message to prevent user enumeration

---

### Requirement 7: MCP Server Integration

**User Story:** As a developer, I want to interact with financial agents through MCP protocol, so that I can integrate with Claude Desktop and other MCP clients.

#### Acceptance Criteria

1. THE MCP_Server SHALL expose Income_Agent, Expense_Agent, Savings_Goal_Agent, and Insights_Agent as MCP tools
2. THE MCP_Server SHALL expose financial data as MCP resources with URIs: income://, expenses://, goals://
3. WHEN an MCP client invokes a tool, THE MCP_Server SHALL authenticate the request using API key
4. THE MCP_Server SHALL return responses in MCP-compliant JSON format
5. WHEN a tool invocation fails, THE MCP_Server SHALL return an error response with descriptive message
6. THE MCP_Server SHALL support tool discovery via MCP protocol
7. THE MCP_Server SHALL log all tool invocations with user ID, tool name, and timestamp
8. THE MCP_Server SHALL support multi-step tool orchestration where an MCP client can invoke multiple tools in sequence (e.g., `create_expense_entry` followed by `query_insights`) within a single user interaction, enabling AI clients to orchestrate agents dynamically

---

### Requirement 8: Infrastructure Deployment

**User Story:** As a DevOps engineer, I want to deploy the entire system using Terraform, so that infrastructure is reproducible and version-controlled.

#### Acceptance Criteria

1. THE Terraform SHALL provision Aurora_Database with PostgreSQL 15.12 and auto-scaling from 0.5 to 2 ACUs
2. THE Terraform SHALL provision Lambda functions for all agents with Python 3.11 runtime
3. THE Terraform SHALL provision API_Gateway with REST API endpoints (no WebSocket)
4. THE Terraform SHALL provision Cognito_Service user pool with email verification enabled
5. THE Terraform SHALL configure IAM roles with least-privilege permissions for each Lambda function
6. THE Terraform SHALL store database credentials and JWT secret in AWS Secrets Manager
7. THE Terraform SHALL configure CloudWatch log groups with 7-day retention and X-Ray tracing

---

### Requirement 9: CI/CD Pipeline

**User Story:** As a developer, I want automated testing and deployment, so that code changes are validated and deployed safely.

#### Acceptance Criteria

1. WHEN code is pushed to the main branch, THE GitHub_Actions SHALL run unit tests with pytest
2. THE GitHub_Actions SHALL enforce minimum 73% code coverage
3. WHEN tests pass, THE GitHub_Actions SHALL deploy infrastructure changes using Terraform
4. THE GitHub_Actions SHALL deploy Lambda function code via direct upload
5. WHEN deployment fails, THE GitHub_Actions SHALL send a notification and halt the pipeline
6. THE GitHub_Actions SHALL build and deploy the React frontend to S3

---

### Requirement 10: Error Handling and Logging

**User Story:** As a developer, I want comprehensive error handling and logging, so that I can diagnose issues quickly in production.

#### Acceptance Criteria

1. ALL agents SHALL log operations with structured JSON format including user_id, operation, timestamp, and status
2. THE Expense_Agent SHALL log LLM invocations with latency metrics
3. THE Insights_Agent SHALL log every validation decision with trace_id, decision, reason, retried, llm_calls, and data_sources
4. WHEN an unhandled exception occurs, THE Lambda function SHALL log the full stack trace and return HTTP 500
5. THE system SHALL track LLM token usage, cost, and latency in the `llm_usage` database table
6. THE Insights_Agent SHALL propagate trace_id through all log entries for end-to-end request tracing

---

### Requirement 11: Data Model and Schema

**User Story:** As a developer, I want a well-defined database schema, so that data integrity is maintained and queries are efficient.

#### Acceptance Criteria

1. THE Aurora_Database SHALL have a users table with id, email, hashed_password, created_at, updated_at
2. THE Aurora_Database SHALL have an income_entries table with id, user_id, amount, source, date, notes, created_at
3. THE Aurora_Database SHALL have an expense_entries table with id, user_id, amount, merchant, category, date, created_at
4. THE Aurora_Database SHALL have a savings_goals table with id, user_id, name, target_amount, current_amount, initial_amount, target_date, created_at
5. THE Aurora_Database SHALL have an llm_usage table with id, user_id, agent, model, prompt_tokens, completion_tokens, total_tokens, latency_ms, estimated_cost_usd, created_at
6. THE Aurora_Database SHALL enforce foreign key constraints between user_id columns and users table
7. THE Aurora_Database SHALL have indexes on user_id and date columns for efficient querying

---

### Requirement 12: AI Quality Metrics Dashboard

**User Story:** As a developer, I want measurable quality baselines displayed in the dashboard, so that I can evaluate system performance.

#### Acceptance Criteria

1. THE Metrics_Agent SHALL compute: categorization accuracy, data completeness, goal prediction coverage, insights data richness, and overall quality score
2. THE Dashboard SHALL display LLM usage metrics: total calls, total tokens, estimated cost, average latency
3. THE Dashboard SHALL display per-agent LLM usage breakdown
4. THE Dashboard SHALL display quality metric cards with progress bars vs baseline targets
5. THE system SHALL track all LLM usage in the `llm_usage` table for historical analysis

---

### Requirement 13: Non-Functional Requirements

#### Acceptance Criteria

1. THE API_Gateway SHALL respond to non-AI endpoints within 500ms at the 95th percentile
2. THE API_Gateway SHALL respond to AI endpoints within 3 seconds at the 95th percentile
3. ALL data stored in Aurora_Database SHALL be encrypted at rest
4. ALL data in transit SHALL use HTTPS/TLS
5. THE system operational cost SHALL not exceed $10/day during the demo period

---

### Known Limitations (MVP Scope)

- **Savings goal progress** uses simplified formula: `initial_amount + (income - expenses since creation)` (not per-goal allocation)
- **Expense categorization** uses Cerebras locally; AWS Bedrock in production (blocked by org SCP in current account)
- **Multi-currency** not supported — all amounts treated as single currency
- **Investment tracking**, **receipt OCR**, and **fraud detection** are out of scope
- **LLM judge number tolerance** is ±1.5% — very precise numbers may occasionally fail grounding check
- **LLM timeout** is delegated to Lambda function timeout (15 min max) — LLM_TIMEOUT_S is a documented constant, not enforced via SIGALRM (not thread-safe)
