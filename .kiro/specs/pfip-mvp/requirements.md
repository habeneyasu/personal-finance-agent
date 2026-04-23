# Requirements Document: Personal Financial Intelligence Platform MVP

## Introduction

The Aequitas Personal Financial Intelligence Platform (PFIP) MVP addresses a well-documented problem: **70% of people who start tracking expenses manually abandon it within 30 days** due to friction. Existing solutions (Mint, YNAB, spreadsheets) require manual data entry and provide only backward-looking reports — they tell you what happened, not what to do next.

**Why this is an AI problem, not a rules problem:**
Rule-based categorization breaks on ambiguous merchants ("Whole Foods" → Dining vs Groceries), new merchants, and multi-language inputs. Natural language insights require reasoning over structured data — a task LLMs handle natively. The conversational interface (MCP) removes the UI entirely for power users.

**Scope decisions and trade-offs:**
- Chose MCP over REST for the agent interface — enables any LLM client to connect without custom integration
- Chose HTTP polling over WebSocket — eliminates connection state management, sufficient for demo latency
- Chose simplified savings formula (global income - expenses) over per-goal allocation — reduces complexity by 60% with acceptable accuracy for MVP
- Chose Aurora Serverless over DynamoDB — financial aggregations are naturally relational; SQL is more expressive than scan-filter patterns
- Excluded fraud detection, receipt OCR, multi-currency — each adds 2+ weeks; core value proposition doesn't require them

**AI relevance:** Bedrock provides two distinct AI capabilities: (1) zero-shot merchant categorization that generalises to unseen merchants, and (2) contextual financial reasoning that answers questions requiring multi-step inference over structured data.

## Glossary

- **MCP_Server**: Model Context Protocol server exposing financial agents as tools and resources
- **Income_Agent**: MCP agent handling income entry creation and retrieval
- **Expense_Agent**: MCP agent managing expense entries with AI-powered categorization
- **Savings_Goal_Agent**: MCP agent tracking savings goals with progress calculation and completion prediction
- **Insights_Agent**: MCP agent answering natural language queries about financial data using AWS Bedrock
- **API_Gateway**: AWS API Gateway providing REST and WebSocket endpoints
- **Aurora_Database**: Aurora Serverless v2 PostgreSQL database for data persistence
- **Bedrock_Service**: AWS Bedrock service using Claude or Nova models for AI reasoning
- **Dashboard**: Real-time web interface displaying financial data with HTTP polling (3-second refresh)
- **Terraform**: Infrastructure as Code tool for AWS resource provisioning
- **GitHub_Actions**: CI/CD pipeline for automated testing and deployment
- **Auth_API**: Local JWT-based authentication service (register/login/me) using bcrypt + python-jose

## Requirements

### Requirement 1: Income Entry Management

**User Story:** As a user, I want to add and view income entries, so that I can track my earnings over time.

#### Acceptance Criteria

1. WHEN a user submits an income entry with amount, source, date, and optional notes, THE Income_Agent SHALL persist the entry to Aurora_Database
2. WHEN a user requests income entries, THE Income_Agent SHALL return all entries for the authenticated user sorted by date descending
3. WHEN an income entry is created, THE API_Gateway SHALL broadcast an update via WebSocket to connected clients
4. THE Income_Agent SHALL validate that amount is a positive decimal number
5. THE Income_Agent SHALL validate that date is in ISO 8601 format and not in the future
6. WHEN an invalid income entry is submitted, THE Income_Agent SHALL return a descriptive error message with HTTP 400 status

### Requirement 2: Expense Entry Management with AI Categorization

**User Story:** As a user, I want to add expenses that are automatically categorized, so that I can understand my spending patterns without manual classification.

#### Acceptance Criteria

1. WHEN a user submits an expense entry with amount, merchant, and date, THE Expense_Agent SHALL persist the entry to Aurora_Database
2. WHEN an expense entry is created, THE Expense_Agent SHALL invoke Bedrock_Service to categorize the expense based on merchant name and amount
3. THE Expense_Agent SHALL assign a category from the predefined list: Groceries, Transportation, Entertainment, Utilities, Healthcare, Shopping, Dining, Other
4. WHEN a user requests expense entries, THE Expense_Agent SHALL return all entries for the authenticated user with assigned categories
5. WHEN an expense entry is created, THE API_Gateway SHALL broadcast an update via WebSocket to connected clients
6. THE Expense_Agent SHALL validate that amount is a positive decimal number
7. WHEN Bedrock_Service categorization fails, THE Expense_Agent SHALL assign category "Other" and log the error

### Requirement 3: Savings Goal Tracking

**User Story:** As a user, I want to create savings goals and track my progress, so that I can stay motivated and plan my financial future.

#### Acceptance Criteria

1. WHEN a user creates a savings goal with name, target amount, and target date, THE Savings_Goal_Agent SHALL persist the goal to Aurora_Database
2. THE Savings_Goal_Agent SHALL calculate current progress by summing income entries and subtracting expense entries since goal creation
3. THE Savings_Goal_Agent SHALL calculate predicted completion date based on average monthly savings rate from the last 30 days
4. WHEN a user requests savings goals, THE Savings_Goal_Agent SHALL return all goals with current amount, target amount, progress percentage, and predicted completion date
5. WHEN a new income or expense entry is created, THE Savings_Goal_Agent SHALL recalculate progress for all active goals
6. THE Savings_Goal_Agent SHALL validate that target amount is a positive decimal number
7. THE Savings_Goal_Agent SHALL validate that target date is in the future

### Requirement 4: Natural Language Financial Insights

**User Story:** As a user, I want to ask questions about my finances in natural language, so that I can get quick answers without navigating complex interfaces.

#### Acceptance Criteria

1. WHEN a user submits a natural language query, THE Insights_Agent SHALL retrieve relevant financial data from Aurora_Database
2. THE Insights_Agent SHALL invoke Bedrock_Service with the query and financial context to generate a natural language response
3. THE Insights_Agent SHALL support queries about total income, total expenses, spending by category, and savings goal progress
4. THE Insights_Agent SHALL support comparative queries like "How did I spend this month compared to last month?"
5. THE Insights_Agent SHALL support predictive queries like "Can I afford a $500 purchase without impacting my vacation goal?"
6. WHEN Bedrock_Service returns a response, THE Insights_Agent SHALL return the answer with HTTP 200 status
7. WHEN a query cannot be answered due to insufficient data, THE Insights_Agent SHALL return a helpful message explaining what data is needed

### Requirement 5: Real-Time Dashboard Updates

**User Story:** As a user, I want the dashboard to update automatically when I add income or expenses, so that I always see current financial data without refreshing.

#### Acceptance Criteria

1. THE Dashboard SHALL poll the API every 3 seconds to refresh income, expense, and goal totals
2. WHEN an income entry is created, THE Dashboard SHALL reflect the new total within 3 seconds
3. WHEN an expense entry is created, THE Dashboard SHALL reflect the new total within 3 seconds
4. WHEN a savings goal progress changes, THE Dashboard SHALL reflect the updated progress within 3 seconds
5. THE Dashboard SHALL update displayed totals and charts within 3 seconds of a new entry being created
6. THE Dashboard SHALL show a loading indicator while fetching data
7. THE Dashboard SHALL handle API errors gracefully without crashing

> **Note:** WebSocket was dropped from MVP scope. HTTP polling every 3 seconds is sufficient for the demo and eliminates WebSocket infrastructure complexity.

### Requirement 6: User Authentication

**User Story:** As a user, I want to securely log in to the system, so that my financial data remains private and protected.

#### Acceptance Criteria

1. WHEN a user registers with email and password, THE Auth_API SHALL create a user account with hashed password stored in Aurora_Database
2. WHEN a user logs in with valid credentials, THE Auth_API SHALL return a JWT access token (24-hour expiry)
3. THE API_Gateway SHALL validate JWT tokens for all protected endpoints
4. WHEN a JWT token is expired or invalid, THE API_Gateway SHALL return HTTP 401 status with error message
5. WHEN a user logs out, THE Dashboard SHALL clear the JWT from localStorage
6. THE Auth_API SHALL enforce password requirements: minimum 8 characters, at least one uppercase, one lowercase, one number
7. WHEN authentication fails, THE Auth_API SHALL return a generic error message to prevent user enumeration

> **Note:** AWS Cognito is provisioned via Terraform for production. Local development uses the Auth_API (bcrypt + python-jose JWT) to avoid Cognito setup friction.

### Requirement 7: MCP Server Integration

**User Story:** As a developer, I want to interact with financial agents through MCP protocol, so that I can integrate with Claude Desktop and other MCP clients.

#### Acceptance Criteria

1. THE MCP_Server SHALL expose Income_Agent, Expense_Agent, Savings_Goal_Agent, and Insights_Agent as MCP tools
2. THE MCP_Server SHALL expose financial data as MCP resources with URIs: income://, expenses://, goals://
3. WHEN an MCP client invokes a tool, THE MCP_Server SHALL authenticate the request using API key or JWT token
4. THE MCP_Server SHALL return responses in MCP-compliant JSON format
5. WHEN a tool invocation fails, THE MCP_Server SHALL return an error response with descriptive message
6. THE MCP_Server SHALL support tool discovery via MCP protocol
7. THE MCP_Server SHALL log all tool invocations with user ID, tool name, and timestamp

### Requirement 8: Infrastructure Deployment

**User Story:** As a DevOps engineer, I want to deploy the entire system using Terraform, so that infrastructure is reproducible and version-controlled.

#### Acceptance Criteria

1. THE Terraform SHALL provision Aurora_Database with PostgreSQL 15.4 and auto-scaling from 0.5 to 2 ACUs
2. THE Terraform SHALL provision Lambda functions for Income_Agent, Expense_Agent, Savings_Goal_Agent, and Insights_Agent with Python 3.11 runtime
3. THE Terraform SHALL provision API_Gateway with REST API endpoints (no WebSocket — HTTP polling used instead)
4. THE Terraform SHALL provision Cognito_Service user pool with email verification enabled
5. THE Terraform SHALL configure IAM roles with least-privilege permissions for each Lambda function
6. THE Terraform SHALL store database credentials in AWS Secrets Manager
7. THE Terraform SHALL configure CloudWatch log groups with 7-day retention for all Lambda functions

### Requirement 9: CI/CD Pipeline

**User Story:** As a developer, I want automated testing and deployment, so that code changes are validated and deployed safely.

#### Acceptance Criteria

1. WHEN code is pushed to the main branch, THE GitHub_Actions SHALL run unit tests with pytest
2. THE GitHub_Actions SHALL enforce minimum 80% code coverage for all Python modules
3. WHEN tests pass, THE GitHub_Actions SHALL deploy infrastructure changes using Terraform
4. THE GitHub_Actions SHALL deploy Lambda function code using AWS SAM or direct upload
5. WHEN deployment fails, THE GitHub_Actions SHALL send a notification and halt the pipeline
6. THE GitHub_Actions SHALL run integration tests against the deployed staging environment
7. WHEN all tests pass, THE GitHub_Actions SHALL tag the release with semantic version

### Requirement 10: Error Handling and Logging

**User Story:** As a developer, I want comprehensive error handling and logging, so that I can diagnose issues quickly in production.

#### Acceptance Criteria

1. THE Income_Agent SHALL log all operations with structured JSON format including user_id, operation, timestamp, and status
2. THE Expense_Agent SHALL log Bedrock_Service invocations with request and response payloads
3. THE Savings_Goal_Agent SHALL log calculation errors with input data for debugging
4. THE Insights_Agent SHALL log query processing time and Bedrock_Service latency
5. WHEN an unhandled exception occurs, THE Lambda function SHALL log the full stack trace and return HTTP 500 status
6. THE API_Gateway SHALL log all requests with request ID, path, method, status code, and latency
7. THE CloudWatch SHALL aggregate logs with queryable fields for user_id, agent_name, and error_type

### Requirement 11: Data Model and Schema

**User Story:** As a developer, I want a well-defined database schema, so that data integrity is maintained and queries are efficient.

#### Acceptance Criteria

1. THE Aurora_Database SHALL have a users table with id, email, hashed_password, created_at, and updated_at columns
2. THE Aurora_Database SHALL have an income_entries table with id, user_id, amount, source, date, notes, and created_at columns
3. THE Aurora_Database SHALL have an expense_entries table with id, user_id, amount, merchant, category, date, and created_at columns
4. THE Aurora_Database SHALL have a savings_goals table with id, user_id, name, target_amount, current_amount, target_date, and created_at columns
5. THE Aurora_Database SHALL enforce foreign key constraints between user_id columns and users table
6. THE Aurora_Database SHALL have indexes on user_id and date columns for efficient querying
7. THE Aurora_Database SHALL use UUID type for all id columns

### Requirement 12: Demo Readiness

**User Story:** As a presenter, I want a fully functional demo scenario, so that I can showcase all features during the Friday presentation.

#### Acceptance Criteria

1. THE Demo SHALL include a seeded user account with sample income, expense, and savings goal data
2. THE Demo SHALL demonstrate adding a new expense via Claude Desktop MCP client with automatic categorization
3. THE Demo SHALL demonstrate asking "How much did I spend this month?" and receiving an accurate answer from Insights_Agent
4. THE Demo SHALL demonstrate asking "Am I on track for my vacation goal?" and receiving a prediction from Savings_Goal_Agent
5. THE Demo SHALL demonstrate real-time dashboard updates when a new income entry is added
6. THE Demo SHALL complete all operations within 5 seconds to maintain presentation flow
7. THE Demo SHALL include a simple React frontend with charts showing income, expenses, and savings goal progress
8. THE Demo SHALL demonstrate a failure scenario: Bedrock categorization fallback (category defaults to "Other" and system continues)
9. THE Demo SHALL demonstrate invalid input handling: submitting a negative expense amount returns HTTP 400 with a clear error message

---

### Requirement 13: Non-Functional Requirements

**User Story:** As a system operator, I want defined performance, security, and cost boundaries, so that the system behaves predictably under load and within budget.

#### Acceptance Criteria

1. THE API_Gateway SHALL respond to non-AI endpoints (income, expenses, goals CRUD) within 500ms at the 95th percentile
2. THE API_Gateway SHALL respond to AI endpoints (insights query, expense categorization) within 3 seconds at the 95th percentile
3. THE system SHALL support 50–100 concurrent users for the MVP demo; architecture SHALL be horizontally scalable to 1,000 concurrent users without code changes
4. ALL data stored in Aurora_Database SHALL be encrypted at rest using AWS KMS
5. ALL data in transit between clients and API_Gateway SHALL use HTTPS/TLS 1.2+
6. THE Bedrock_Service usage SHALL be throttled to a maximum of 100 requests per minute per user to control costs
7. THE WebSocket fan-out latency from event creation to client receipt SHALL be under 1 second
8. THE system operational cost SHALL not exceed $10/day during the demo period

---

### Requirement 14: AI Guardrails

**User Story:** As a developer, I want AI outputs validated before returning to users, so that hallucinated or malformed responses do not corrupt financial data.

#### Acceptance Criteria

1. THE Expense_Agent SHALL use a fixed prompt template for Bedrock categorization: "Categorize this expense into exactly one of: Groceries, Transportation, Entertainment, Utilities, Healthcare, Shopping, Dining, Other. Merchant: {merchant}, Amount: {amount}. Respond with only the category name."
2. THE Expense_Agent SHALL validate that Bedrock_Service returns exactly one value from the predefined category list; if not, SHALL default to "Other"
3. THE Insights_Agent SHALL use a structured prompt template that includes: system role definition, financial context as JSON, user query, and instruction to base answers only on provided data
4. THE Insights_Agent SHALL validate that Bedrock_Service response is non-empty before returning to the user; if empty, SHALL return the fallback message
5. THE Insights_Agent SHALL NOT return raw Bedrock errors or internal stack traces to the user
6. THE system SHALL log all Bedrock prompt inputs and outputs for auditability

---

### Requirement 15: API Contract

**User Story:** As a frontend developer or MCP client integrator, I want defined request/response schemas, so that I can build against a stable interface.

#### Acceptance Criteria

1. THE Income_Agent POST /income endpoint SHALL accept: `{"amount": number, "source": string, "date": "YYYY-MM-DD", "notes": string (optional)}` and return HTTP 201 with the created `IncomeEntry` object
2. THE Expense_Agent POST /expenses endpoint SHALL accept: `{"amount": number, "merchant": string, "date": "YYYY-MM-DD"}` and return HTTP 201 with the created `ExpenseEntry` object including assigned `category`
3. THE Savings_Goal_Agent POST /goals endpoint SHALL accept: `{"name": string, "target_amount": number, "target_date": "YYYY-MM-DD"}` and return HTTP 201 with the created `SavingsGoal` object
4. THE Insights_Agent POST /insights/query endpoint SHALL accept: `{"question": string}` and return HTTP 200 with `{"answer": string, "query": string, "generated_at": "ISO8601"}`
5. ALL error responses SHALL follow the format: `{"error": string, "detail": string, "status": number}`
6. THE MCP_Server tool `create_expense_entry` SHALL accept: `{"amount": number, "merchant": string, "date": "YYYY-MM-DD"}` and return the created `ExpenseEntry` with category
7. ALL API endpoints SHALL be versioned under `/v1/` prefix

---

### Requirement 16: Observability

**User Story:** As a developer, I want metrics and alerts configured, so that I can detect and respond to issues during and after the demo.

#### Acceptance Criteria

1. THE CloudWatch SHALL track the following metrics per Lambda function: invocation count, error count, duration (p50, p95), and throttle count
2. THE CloudWatch SHALL track Bedrock_Service latency as a custom metric emitted by Expense_Agent and Insights_Agent
3. THE CloudWatch SHALL create an alarm when error rate exceeds 5% over a 5-minute window for any Lambda function
4. THE CloudWatch SHALL create an alarm when Insights_Agent p95 latency exceeds 5 seconds
5. THE API_Gateway SHALL emit access logs to CloudWatch with request ID, path, method, status code, and latency
6. THE system SHALL use AWS X-Ray tracing on all Lambda functions to enable end-to-end request tracing

---

### Known Limitations (MVP Scope)

The following are intentional simplifications for the 3-day MVP:

- **Savings goal progress** uses a simplified formula: `current_amount = SUM(all income) - SUM(all expenses)` since goal creation. This does not account for multiple overlapping goals or explicit goal contributions. This is documented as MVP logic and will be replaced with per-goal allocation tracking in a future version.
- **Expense categorization** uses Bedrock for the live demo. In automated tests, Bedrock is mocked to avoid cost and latency.
- **Multi-currency** is not supported. All amounts are treated as a single currency (USD or ETB based on user context).
- **Investment tracking**, **receipt OCR**, and **fraud detection** are out of scope for this MVP.
