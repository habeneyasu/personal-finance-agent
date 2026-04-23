# PFIP Demo Script — Friday Presentation

**Duration:** ~10 minutes  
**Setup:** Both servers running, browser open at http://localhost:5173, MCP Inspector open

> **Opening line:** *"70% of people abandon expense tracking because it's manual and boring. PFIP makes it conversational — you talk to your finances using AI agents over the Model Context Protocol."*

---

## Pre-Demo Setup (5 min before)

```bash
# Terminal 1 — Backend API
uvicorn scripts.run_api_local:app --port 8000 --reload

# Terminal 2 — Seed demo data (run once)
python3 scripts/seed_demo.py --env local --reset

# Terminal 3 — MCP Inspector
npx @modelcontextprotocol/inspector python3 scripts/run_mcp_local.py
```

Open in browser:
- Dashboard: http://localhost:5173
- MCP Inspector: http://localhost:6274 (token from terminal)

---

## Demo Flow

### 1. Architecture Overview (1 min)

> "This is PFIP — a Personal Financial Intelligence Platform built on AWS serverless architecture with MCP integration. Four specialized AI agents handle income, expenses, savings goals, and natural language insights."

Show the architecture diagram briefly.

---

### 2. Dashboard Overview (2 min)

Open http://localhost:5173 → Overview tab.

> "The dashboard shows real-time financial data — total income, expenses, and net savings. The bar chart shows monthly trends, and the pie chart breaks down spending by category."

Point out:
- 3 stat cards (income green, expenses red, net savings)
- Bar chart with 3 months of data
- Pie chart with 8 expense categories
- "Auto-refreshes every 3s" — no page reload needed

---

### 3. Add a New Expense via MCP (2 min)

Switch to MCP Inspector.

> "Now I'll show the MCP integration — this is how AI assistants like Claude would interact with the system using the Model Context Protocol."

Click `create_expense_entry`:
```json
{
  "amount": 85,
  "merchant": "Whole Foods",
  "date": "2026-04-25"
}
```

Click Run Tool. Show result:
```json
{
  "result": {
    "category": "Groceries",
    ...
  }
}
```

> "Notice the category was automatically assigned as 'Groceries' — that's the AI categorization engine. In production, this calls AWS Bedrock."

Switch back to dashboard → Transactions tab. The new expense appears immediately.

---

### 4. Natural Language Insights (2 min)

Switch to dashboard → Insights tab.

> "Now the most powerful feature — natural language queries over your financial data."

Click suggestion: **"How much did I spend this month?"**

Show the AI response with spending breakdown.

Then type manually: **"Am I on track to meet my savings goals?"**

Show the response with goal progress analysis.

> "This is powered by AWS Bedrock — the system assembles your financial context and sends it to Claude/Nova for reasoning."

---

### 5. Savings Goals (1 min)

Switch to Goals tab.

> "The savings goal tracker shows progress bars and predicted completion dates based on your current savings rate."

Point out:
- Vacation Fund: progress bar + predicted date
- Emergency Fund: progress bar + predicted date

---

### 6. Failure Scenario Demo (1 min)

Switch to Transactions tab → Expenses → Add.

> "Let me show how the system handles errors gracefully."

Enter amount: `-50`, merchant: `Test`, date: today.

Show the validation error: "Amount must be greater than 0"

> "The system validates all inputs and returns clear error messages — no silent failures."

---

### 7. Architecture Highlights (1 min)

> "To summarize the technical architecture:"

- **4 MCP Agents** — Income, Expense, Savings, Insights — each a separate AWS Lambda
- **AWS Bedrock** — Claude/Nova for categorization and NL insights
- **Aurora Serverless v2** — PostgreSQL, scales to zero
- **Terraform IaC** — entire infrastructure as code, reproducible
- **GitHub Actions CI/CD** — automated test + deploy pipeline
- **MCP Protocol** — AI-native interface, works with any MCP client

---

## Known Limitations (be upfront)

- Savings goal progress uses simplified formula: `income - expenses since creation` (not per-goal allocation)
- Local demo uses rule-based categorization; production uses AWS Bedrock
- No multi-currency support in MVP
- No receipt OCR or fraud detection (out of scope)

---

## Backup Plan (if something breaks)

If the API is down:
```bash
uvicorn scripts.run_api_local:app --port 8000
```

If the DB is empty:
```bash
python3 scripts/seed_demo.py --env local --reset
```

If MCP Inspector won't connect:
```bash
# Test directly
python3 -c "
import sys, asyncio, json
sys.path.insert(0, '.')
from scripts.run_mcp_local import call_tool
async def t():
    r = await call_tool('list_expense_entries', {})
    print(json.loads(r[0].text))
asyncio.run(t())
"
```
