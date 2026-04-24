# PFIP Developer Guide
## Personal Financial Intelligence Platform — End-to-End Technical Reference

**Read time: ~25 minutes**

---

## 1. What This System Does

PFIP is an AI-native personal finance platform. Users track income, expenses, and savings goals. An LLM (Cerebras/Bedrock) automatically categorizes expenses and answers natural language questions about finances.

The key architectural decision: **everything is exposed via Model Context Protocol (MCP)**, meaning any AI assistant (Claude, GPT, etc.) can interact with the system as a tool-using agent — not just through the web dashboard.

---

## 2. System Architecture (5 minutes)

```
┌─────────────────────────────────────────────────────────┐
│                      CLIENTS                            │
│  React Dashboard (port 5173)  │  MCP Inspector          │
└──────────────┬────────────────┴──────────┬──────────────┘
               │ HTTP REST                  │ MCP stdio
               ▼                            ▼
┌─────────────────────────┐    ┌────────────────────────┐
│   FastAPI (port 8000)   │    │   MCP Server           │
│   run_api_local.py      │    │   run_mcp_local.py     │
└──────────┬──────────────┘    └──────────┬─────────────┘
           │                              │ calls agents directly
           ▼                              ▼
┌──────────────────────────────────────────────────────────┐
│                    5 AGENTS (FastAPI)                    │
│  Income  │  Expense  │  Savings  │  Insights  │  Metrics │
└──────────┴─────┬─────┴───────────┴─────┬──────┴──────────┘
                 │ bcrypt/psycopg2        │ Cerebras API
                 ▼                        ▼
┌───────────────────────┐    ┌────────────────────────────┐
│  PostgreSQL (port 5433)│    │  Cerebras LLM (cloud)      │
│  Docker container      │    │  llama3.1-8b               │
└───────────────────────┘    └────────────────────────────┘
```

**In production (AWS):**
- FastAPI → AWS Lambda (one function per agent)
- PostgreSQL → Aurora Serverless v2
- Cerebras → AWS Bedrock (fallback)
- React → S3 static website
- Auth → AWS Cognito

---

## 3. Project Structure (3 minutes)

```
personal-finance-agent/
│
├── src/                          # All Python backend code
│   ├── shared/                   # Shared utilities used by all agents
│   │   ├── auth.py               # JWT verification + user_id extraction
│   │   ├── db.py                 # psycopg2 connection (Secrets Manager or env vars)
│   │   ├── llm.py                # LLM client (Cerebras → Bedrock fallback)
│   │   ├── logger.py             # Structured JSON logging (aws-lambda-powertools)
│   │   ├── exceptions.py         # handle_unhandled_exception decorator → HTTP 500
│   │   └── validation.py         # Pydantic validators (amount > 0, date guards)
│   │
│   ├── income_agent/             # POST/GET /v1/income
│   ├── expense_agent/            # POST/GET /v1/expenses + Cerebras categorization
│   ├── savings_agent/            # POST/GET /v1/goals + progress calculation
│   ├── insights_agent/           # POST /v1/insights/query + LLM reasoning
│   ├── metrics_agent/            # GET /v1/metrics + quality baselines
│   ├── mcp_server/               # MCP protocol server (7 tools, 3 resources)
│   └── auth_api/                 # POST /auth/login, /auth/register, GET /auth/me
│
├── frontend/                     # React + Vite + TypeScript
│   └── src/
│       ├── App.tsx               # Tab navigation + auth gate
│       ├── api.ts                # Axios client with JWT interceptor
│       └── components/
│           ├── Overview.tsx      # Charts + stat cards (3s polling)
│           ├── Transactions.tsx  # Income/expense add forms
│           ├── Goals.tsx         # Progress bars + predictions
│           ├── Insights.tsx      # Chat UI → LLM
│           ├── Metrics.tsx       # Quality evaluation dashboard
│           └── Login.tsx         # JWT auth form
│
├── infra/                        # Terraform IaC
│   ├── main.tf                   # All AWS resources wired together
│   ├── variables.tf              # Configurable values
│   ├── outputs.tf                # API URL, bucket name, etc.
│   └── modules/
│       ├── aurora/               # Aurora Serverless v2
│       ├── cognito/              # User pool + app client
│       ├── iam/                  # Per-Lambda least-privilege roles
│       ├── lambda/               # Reusable Lambda module
│       └── api_gateway/          # REST API + Cognito authorizer
│
├── scripts/
│   ├── run_api_local.py          # Unified FastAPI server for local dev
│   ├── run_mcp_local.py          # MCP server for local dev (calls agents directly)
│   ├── migrate.py                # DB schema creation (idempotent DDL)
│   ├── seed_demo.py              # Populate DB with demo data
│   ├── demo_script.md            # Friday presentation flow
│   └── package_lambdas.sh        # Bundle agents for AWS Lambda deployment
│
├── tests/unit/                   # 126 unit tests, 88% coverage
├── docker-compose.yml            # Local PostgreSQL on port 5433
├── .env.local                    # Local dev environment variables
├── .env.example                  # Template for all env vars
├── DEPLOY.md                     # Step-by-step AWS deployment guide
└── pyproject.toml                # Python dependencies
```

---

## 4. How a Request Flows (5 minutes)

### Example: User adds an expense via the dashboard

```
1. User fills form: merchant="Uber", amount=50, date="2026-04-22"

2. React (Transactions.tsx)
   → POST http://localhost:8000/v1/expenses
   → Authorization: Bearer <JWT>

3. run_api_local.py (middleware)
   → Reads JWT from header
   → Decodes user_id from JWT claims
   → Injects mock AWS event into request.scope["aws.event"]

4. expense_agent/handler.py
   → get_user_id_from_event(event) → "00000000-0000-0000-0000-000000000001"
   → Validates: amount > 0 ✓, date not in future ✓
   → Calls categorize_expense("Uber", 50)

5. expense_agent/categorizer.py
   → ENVIRONMENT=local + CEREBRAS_API_KEY set → calls Cerebras
   → Prompt: "Categorize: Merchant: Uber, Amount: 50. Reply with one word..."
   → Cerebras returns: "Transportation"
   → Validates category is in ALLOWED_CATEGORIES ✓

6. DB insert
   → INSERT INTO expense_entries (user_id, amount, merchant, category, date)
   → Returns: {id, amount, merchant, category="Transportation", date}

7. Response → React
   → 201 {"id": "...", "category": "Transportation", ...}
   → Dashboard re-fetches expenses (3s polling)
```

### Example: User asks "How much did I spend last month?"

```
1. React (Insights.tsx)
   → POST /v1/insights/query {"question": "How much did I spend last month?"}

2. insights_agent/handler.py
   → Calls build_financial_context(user_id, conn)

3. insights_agent/context_builder.py
   → Queries last 90 days of income + expenses + goals
   → Computes: expenses_last_month, expenses_this_month, monthly breakdowns
   → Returns structured JSON context

4. handler.py
   → Builds prompt: system role + context JSON + user question
   → Calls call_llm(prompt) via src/shared/llm.py

5. shared/llm.py
   → CEREBRAS_API_KEY set → Cerebras API
   → Returns: "$989.19. This is the total amount spent last month."

6. Response → React chat bubble
```

---

## 5. Authentication Flow (2 minutes)

**Local dev:**
```
POST /auth/login {"email": "demo@pfip.dev", "password": "Demo1234!"}
→ auth_api/handler.py
→ SELECT hashed_password FROM users WHERE email = ?
→ bcrypt.checkpw(password, hashed) ✓
→ Returns JWT (HS256, 24h expiry, signed with JWT_SECRET)

All subsequent requests:
→ Authorization: Bearer <JWT>
→ run_api_local.py middleware decodes JWT → extracts user_id
→ Injects into request.scope["aws.event"]["requestContext"]["authorizer"]["claims"]["sub"]
→ Each agent calls get_user_id_from_event(event) → user_id
```

**Production (AWS):**
```
→ API Gateway Cognito authorizer validates JWT before Lambda is invoked
→ Lambda receives event with claims already validated
→ Same get_user_id_from_event() call works identically
```

---

## 6. Database Schema (2 minutes)

```sql
users
  id UUID PK, email TEXT UNIQUE, hashed_password TEXT

income_entries
  id UUID PK, user_id UUID FK→users, amount NUMERIC(12,2),
  source TEXT, date DATE, notes TEXT, created_at TIMESTAMPTZ
  INDEX: (user_id, date DESC)

expense_entries
  id UUID PK, user_id UUID FK→users, amount NUMERIC(12,2),
  merchant TEXT, category TEXT DEFAULT 'Other', date DATE, created_at TIMESTAMPTZ
  INDEX: (user_id, date DESC)

savings_goals
  id UUID PK, user_id UUID FK→users, name TEXT,
  target_amount NUMERIC(12,2), current_amount NUMERIC(12,2),
  target_date DATE, created_at TIMESTAMPTZ
  INDEX: (user_id)
```

All tables have `ON DELETE CASCADE` on `user_id` FK.

---

## 7. MCP Server (3 minutes)

The MCP server exposes the 4 agents as tools that any AI assistant can call.

**7 tools:**
| Tool | Maps to |
|------|---------|
| `create_income_entry` | POST /v1/income |
| `list_income_entries` | GET /v1/income |
| `create_expense_entry` | POST /v1/expenses |
| `list_expense_entries` | GET /v1/expenses |
| `create_savings_goal` | POST /v1/goals |
| `list_savings_goals` | GET /v1/goals |
| `query_insights` | POST /v1/insights/query |

**3 resources:** `income://entries`, `expenses://entries`, `goals://active`

**Local runner (`run_mcp_local.py`):**
- Calls agents directly in-process (no Lambda, no HTTP)
- Uses fixed UUID `00000000-0000-0000-0000-000000000001` as local user
- Start: `npx @modelcontextprotocol/inspector python3 scripts/run_mcp_local.py`

**Production (`mcp_server/handler.py`):**
- Calls agents via `boto3.client("lambda").invoke()`
- Auth via `PFIP_API_KEY` env var

---

## 8. AI Integration (2 minutes)

**Expense categorization** (`src/expense_agent/categorizer.py`):
```python
# Priority: Cerebras → Bedrock → local rules
if CEREBRAS_API_KEY:
    category = cerebras.chat.completions.create(model="llama3.1-8b", ...)
elif ENVIRONMENT != "local":
    category = bedrock.converse(modelId="amazon.nova-lite-v1:0", ...)
else:
    category = rule_based_categorize(merchant)  # keyword matching
# Always validates category ∈ ALLOWED_CATEGORIES, defaults to "Other"
```

**Insights** (`src/insights_agent/`):
```python
# context_builder.py assembles:
context = {
    "today": "2026-04-23",
    "expenses_last_month": 989.19,   # March total
    "expenses_this_month": 750.47,   # April so far
    "expense_entries": [...],         # all 90-day entries
    "savings_goals": [...],
    ...
}
# handler.py sends context + question to LLM
# LLM reasons over structured data → natural language answer
```

---

## 9. Running Locally (2 minutes)

```bash
# 1. Start database
docker start pfip-postgres
# (first time: docker-compose up -d)

# 2. Start backend API
uvicorn scripts.run_api_local:app --port 8000 --reload

# 3. Start frontend
cd frontend && npm run dev
# → http://localhost:5173

# 4. Login: demo@pfip.dev / Demo1234!

# 5. Optional: MCP Inspector
npx @modelcontextprotocol/inspector python3 scripts/run_mcp_local.py
# → http://localhost:6274
```

**Environment variables** (`.env.local`):
```
DB_HOST=localhost, DB_PORT=5433, DB_NAME=pfip
DB_USER=pfip_admin, DB_PASSWORD=pfip_local_password
CEREBRAS_API_KEY=csk-...   # enables real AI
ENVIRONMENT=local           # bypasses Cognito auth
```

---

## 10. Testing (1 minute)

```bash
# Run all unit tests
ENVIRONMENT=local pytest tests/unit/ --cov=src -q

# 126 tests, 88% coverage
# Key test files:
# tests/unit/test_income_agent.py   — 11 tests
# tests/unit/test_expense_agent.py  — 15 tests (incl. Cerebras mock)
# tests/unit/test_savings_agent.py  — 17 tests (incl. calculator)
# tests/unit/test_insights_agent.py — 13 tests
# tests/unit/test_mcp_server.py     — 12 tests
# tests/unit/test_auth_api.py       — 12 tests
```

---

## 11. AWS Deployment (2 minutes)

See `DEPLOY.md` for full steps. Summary:

```bash
# 1. Fill in infra/terraform.tfvars (vpc_id, subnet_ids, passwords)

# 2. Deploy infrastructure
cd infra && terraform init && terraform apply

# 3. Package and deploy Lambda functions
bash scripts/package_lambdas.sh
for agent in income expense savings insights mcp auth; do
  aws lambda update-function-code --function-name pfip-production-${agent}-agent \
    --zip-file fileb://dist/${agent}_agent.zip
done

# 4. Run DB migration on Aurora
DB_SECRET_ARN=$(terraform output -raw aurora_secret_arn) \
  python3 scripts/migrate.py --env production

# 5. Build and deploy frontend
echo "VITE_API_URL=$(terraform output -raw api_gateway_url)" > frontend/.env.production
cd frontend && npm run build
aws s3 sync dist/ s3://pfip-production-frontend/ --delete
```

**Key outputs after apply:**
- `api_gateway_url` → set as `VITE_API_URL` for frontend build
- `aurora_secret_arn` → set as `DB_SECRET_ARN` for Lambda env vars
- `frontend_url` → S3 static website URL

---

## 12. Key Design Decisions

| Decision | Why |
|----------|-----|
| MCP over REST for AI interface | Any LLM client connects without custom integration |
| HTTP polling over WebSocket | Eliminates connection state management; sufficient for demo |
| Cerebras over Bedrock locally | Bedrock blocked by org SCP; Cerebras is faster + free tier |
| Simplified savings formula | `income - expenses since creation` — documented known limitation |
| Aurora over DynamoDB | Financial aggregations are naturally relational; SQL > scan-filter |
| FastAPI + Mangum | Same code runs locally (uvicorn) and on Lambda (Mangum adapter) |
| bcrypt + HS256 JWT locally | No Cognito setup needed for local dev; same JWT format as Cognito |

---

## 13. Common Issues & Fixes

| Error | Fix |
|-------|-----|
| `Connection refused port 5433` | `docker start pfip-postgres` |
| `404 /v1/metrics` | Restart uvicorn — new route not loaded |
| `CORS blocked` | Ensure uvicorn is running on port 8000 |
| `LLM fallback answer` | Check `CEREBRAS_API_KEY` in `.env.local` |
| `NaN in totals` | Amount is string from API — use `Number(e.amount)` |
| `double /v1/v1/` | `VITE_API_URL` should not end with `/v1` |
