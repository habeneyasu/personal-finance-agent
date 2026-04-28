"""
Local MCP server runner for Claude Desktop testing.

This script runs the MCP server in stdio mode, calling agents directly
in-process (no Lambda, no AWS needed). Uses the local Docker Postgres.

Usage:
    python3 scripts/run_mcp_local.py

Claude Desktop config (~/.config/claude/claude_desktop_config.json):
{
  "mcpServers": {
    "pfip": {
      "command": "python3",
      "args": ["/absolute/path/to/scripts/run_mcp_local.py"],
      "env": {}
    }
  }
}
"""
import asyncio
import json
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set local environment before importing anything
os.environ.setdefault("ENVIRONMENT", "local")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5433")
os.environ.setdefault("DB_NAME", "pfip")
os.environ.setdefault("DB_USER", "pfip_admin")

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Resource, TextContent, Tool

from src.shared.db import get_connection, get_cursor
from src.shared.logger import Logger

server = Server("pfip-financial-assistant")
_logger = Logger(service="mcp-local")

# ---------------------------------------------------------------------------
# Import agent logic directly (no Lambda invocation)
# ---------------------------------------------------------------------------

from src.income_agent.models import IncomeEntryCreate
from src.expense_agent.models import ExpenseEntryCreate
from src.expense_agent.categorizer import categorize_expense
from src.savings_agent.models import SavingsGoalCreate
from src.savings_agent.calculator import calculate_progress, calculate_monthly_rate, predict_completion
from src.insights_agent.context_builder import build_financial_context

from decimal import Decimal
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="create_income_entry",
            description="Add a new income entry to track earnings",
            inputSchema={
                "type": "object",
                "properties": {
                    "amount": {"type": "number", "description": "Income amount (must be > 0)"},
                    "source": {"type": "string", "description": "Income source (e.g. Salary, Freelance)"},
                    "date": {"type": "string", "description": "Date in YYYY-MM-DD format (not in future)"},
                    "notes": {"type": "string", "description": "Optional notes"},
                },
                "required": ["amount", "source", "date"],
            },
        ),
        Tool(
            name="list_income_entries",
            description="List all income entries sorted by date descending",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="create_expense_entry",
            description="Add a new expense entry — automatically categorized using AI",
            inputSchema={
                "type": "object",
                "properties": {
                    "amount": {"type": "number", "description": "Expense amount (must be > 0)"},
                    "merchant": {"type": "string", "description": "Merchant or vendor name"},
                    "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                },
                "required": ["amount", "merchant", "date"],
            },
        ),
        Tool(
            name="list_expense_entries",
            description="List all expense entries with AI-assigned categories",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="create_savings_goal",
            description="Create a new savings goal with a target amount and deadline",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Goal name (e.g. Vacation Fund)"},
                    "target_amount": {"type": "number", "description": "Target savings amount (must be > 0)"},
                    "target_date": {"type": "string", "description": "Target date in YYYY-MM-DD format (must be future)"},
                },
                "required": ["name", "target_amount", "target_date"],
            },
        ),
        Tool(
            name="list_savings_goals",
            description="List savings goals with progress percentage and predicted completion dates",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="query_insights",
            description="Ask a natural language question about your finances (e.g. 'How much did I spend this month?')",
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "Your financial question"},
                },
                "required": ["question"],
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Tool dispatcher — calls agents directly in-process
# ---------------------------------------------------------------------------

USER_ID = "00000000-0000-0000-0000-000000000001"  # Fixed UUID for local dev user


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    timestamp = datetime.now(timezone.utc).isoformat()
    _logger.info("MCP tool invoked", user_id=USER_ID, operation=name, status="ok",
                 tool_name=name, timestamp=timestamp)
    try:
        result = await _dispatch(name, arguments)
        return [TextContent(type="text", text=json.dumps({"result": result}, default=str))]
    except Exception as exc:
        _logger.error("MCP tool error", user_id=USER_ID, operation=name, status="error",
                      tool_name=name, timestamp=timestamp, error=str(exc))
        return [TextContent(type="text", text=json.dumps({"error": {"code": "tool_error", "message": str(exc)}}))]


async def _dispatch(name: str, args: dict) -> dict:
    conn = get_connection()
    try:
        with get_cursor(conn) as cur:
            # Ensure local-dev-user exists in users table
            cur.execute(
                "INSERT INTO users (id, email) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (USER_ID, "dev@local.test"),
            )

        if name == "create_income_entry":
            entry = IncomeEntryCreate(**args)
            with get_cursor(conn) as cur:
                cur.execute(
                    "INSERT INTO income_entries (user_id, amount, source, date, notes) "
                    "VALUES (%s, %s, %s, %s, %s) RETURNING id, user_id, amount, source, date, notes, created_at",
                    (USER_ID, str(entry.amount), entry.source, entry.date, entry.notes),
                )
                row = cur.fetchone()
            return {"id": str(row[0]), "amount": float(row[2]), "source": row[3],
                    "date": str(row[4]), "notes": row[5], "created_at": str(row[6])}

        elif name == "list_income_entries":
            with get_cursor(conn) as cur:
                cur.execute(
                    "SELECT id, amount, source, date, notes, created_at FROM income_entries "
                    "WHERE user_id = %s ORDER BY date DESC", (USER_ID,),
                )
                rows = cur.fetchall()
            return [{"id": str(r[0]), "amount": float(r[1]), "source": r[2],
                     "date": str(r[3]), "notes": r[4]} for r in rows]

        elif name == "create_expense_entry":
            entry = ExpenseEntryCreate(**args)
            category = categorize_expense(entry.merchant, entry.amount)
            with get_cursor(conn) as cur:
                cur.execute(
                    "INSERT INTO expense_entries (user_id, amount, merchant, category, date) "
                    "VALUES (%s, %s, %s, %s, %s) RETURNING id, amount, merchant, category, date, created_at",
                    (USER_ID, str(entry.amount), entry.merchant, category, entry.date),
                )
                row = cur.fetchone()
            return {"id": str(row[0]), "amount": float(row[1]), "merchant": row[2],
                    "category": row[3], "date": str(row[4])}

        elif name == "list_expense_entries":
            with get_cursor(conn) as cur:
                cur.execute(
                    "SELECT id, amount, merchant, category, date FROM expense_entries "
                    "WHERE user_id = %s ORDER BY date DESC", (USER_ID,),
                )
                rows = cur.fetchall()
            return [{"id": str(r[0]), "amount": float(r[1]), "merchant": r[2],
                     "category": r[3], "date": str(r[4])} for r in rows]

        elif name == "create_savings_goal":
            goal = SavingsGoalCreate(**args)
            with get_cursor(conn) as cur:
                cur.execute(
                    "INSERT INTO savings_goals (user_id, name, target_amount, current_amount, target_date) "
                    "VALUES (%s, %s, %s, %s, %s) RETURNING id, name, target_amount, current_amount, target_date",
                    (USER_ID, goal.name, str(goal.target_amount), "0", goal.target_date),
                )
                row = cur.fetchone()
            return {"id": str(row[0]), "name": row[1], "target_amount": float(row[2]),
                    "current_amount": float(row[3]), "target_date": str(row[4])}

        elif name == "list_savings_goals":
            with get_cursor(conn) as cur:
                cur.execute(
                    "SELECT id, name, target_amount, current_amount, target_date, created_at "
                    "FROM savings_goals WHERE user_id = %s", (USER_ID,),
                )
                goal_rows = cur.fetchall()
                results = []
                for row in goal_rows:
                    cur.execute("SELECT amount FROM income_entries WHERE user_id = %s AND date >= %s",
                                (USER_ID, row[5].date() if hasattr(row[5], 'date') else row[5]))
                    inc = cur.fetchall()
                    cur.execute("SELECT amount FROM expense_entries WHERE user_id = %s AND date >= %s",
                                (USER_ID, row[5].date() if hasattr(row[5], 'date') else row[5]))
                    exp = cur.fetchall()
                    current = calculate_progress(row[5], inc, exp)
                    target = Decimal(str(row[2]))
                    cur.execute("SELECT amount, date FROM income_entries WHERE user_id = %s", (USER_ID,))
                    all_inc = cur.fetchall()
                    cur.execute("SELECT amount, date FROM expense_entries WHERE user_id = %s", (USER_ID,))
                    all_exp = cur.fetchall()
                    rate = calculate_monthly_rate(all_inc, all_exp)
                    predicted = predict_completion(current, target, rate)
                    pct = min(100.0, float(current / target * 100)) if target > 0 else 0.0
                    results.append({"id": str(row[0]), "name": row[1], "target_amount": float(target),
                                    "current_amount": float(current), "target_date": str(row[4]),
                                    "progress_pct": round(pct, 2),
                                    "predicted_completion_date": str(predicted) if predicted else None})
            return results

        elif name == "query_insights":
            question = args.get("question", "")
            if not question.strip():
                raise ValueError("question must not be empty")
            context = build_financial_context(USER_ID, conn)
            # Local mode: return summary without Bedrock
            answer = (f"Based on your data (last 90 days): "
                      f"total income ${context['total_income']:.2f}, "
                      f"total expenses ${context['total_expenses']:.2f}, "
                      f"net savings ${context['net_savings']:.2f}. "
                      f"Spending by category: {context['expenses_by_category']}. "
                      f"Active goals: {[g['name'] for g in context['savings_goals']]}.")
            return {"answer": answer, "query": question,
                    "generated_at": datetime.now(timezone.utc).isoformat()}

        else:
            raise ValueError(f"Unknown tool: {name}")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------

@server.list_resources()
async def list_resources() -> list[Resource]:
    return [
        Resource(uri="income://entries", name="Income Entries",
                 description="All income entries", mimeType="application/json"),
        Resource(uri="expenses://entries", name="Expense Entries",
                 description="All expense entries with categories", mimeType="application/json"),
        Resource(uri="goals://active", name="Active Savings Goals",
                 description="Savings goals with progress", mimeType="application/json"),
    ]


@server.read_resource()
async def read_resource(uri: str) -> str:
    result = await _dispatch({"income://entries": "list_income_entries",
                               "expenses://entries": "list_expense_entries",
                               "goals://active": "list_savings_goals"}.get(str(uri), ""), {})
    return json.dumps(result, default=str)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    async def main():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )

    asyncio.run(main())
