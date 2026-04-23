"""MCP Server Lambda handler — exposes all 4 agents as MCP tools for Claude Desktop."""
import asyncio
import json
import os
from datetime import datetime, timezone

import boto3
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Resource, TextContent, Tool

from src.shared.exceptions import handle_unhandled_exception
from src.shared.logger import Logger

server = Server("pfip-financial-assistant")
_logger = Logger(service="mcp-server")

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _authenticate(arguments: dict) -> str:
    """Return user_id or raise ValueError on auth failure.

    Local dev (ENVIRONMENT=local) skips all auth checks.
    Otherwise validates PFIP_API_KEY against the api_key argument.
    Reads env vars at call time so tests can patch os.environ.
    """
    environment = os.environ.get("ENVIRONMENT", "").lower()
    if environment == "local":
        return "local-dev-user"

    api_key = os.environ.get("PFIP_API_KEY", "")
    provided = arguments.get("api_key", "")
    if not api_key or provided != api_key:
        raise ValueError("Unauthorized: invalid or missing api_key")

    return arguments.get("user_id", "mcp-user")


# ---------------------------------------------------------------------------
# Lambda invocation helper
# ---------------------------------------------------------------------------

def _invoke_lambda(function_env: str, http_method: str, path: str, body: dict, user_id: str) -> dict:
    """Invoke a downstream agent Lambda and return its parsed response body."""
    function_name = os.environ.get(function_env, "")
    if not function_name:
        raise ValueError(f"Environment variable {function_env} is not set")

    event = {
        "httpMethod": http_method,
        "path": path,
        "body": json.dumps(body),
        "headers": {},
        "requestContext": {
            "authorizer": {
                "claims": {"sub": user_id}
            }
        },
    }

    lambda_client = boto3.client("lambda")
    response = lambda_client.invoke(
        FunctionName=function_name,
        InvocationType="RequestResponse",
        Payload=json.dumps(event).encode(),
    )

    payload_bytes = response["Payload"].read()
    result = json.loads(payload_bytes)

    # Agent Lambdas return API Gateway-style responses
    body_str = result.get("body", "{}")
    return json.loads(body_str) if isinstance(body_str, str) else body_str


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
                    "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                    "notes": {"type": "string", "description": "Optional notes"},
                    "api_key": {"type": "string", "description": "API key for authentication"},
                },
                "required": ["amount", "source", "date"],
            },
        ),
        Tool(
            name="list_income_entries",
            description="List all income entries for the authenticated user",
            inputSchema={
                "type": "object",
                "properties": {
                    "api_key": {"type": "string", "description": "API key for authentication"},
                },
                "required": [],
            },
        ),
        Tool(
            name="create_expense_entry",
            description="Add a new expense entry with AI-powered categorization",
            inputSchema={
                "type": "object",
                "properties": {
                    "amount": {"type": "number", "description": "Expense amount (must be > 0)"},
                    "merchant": {"type": "string", "description": "Merchant or vendor name"},
                    "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                    "api_key": {"type": "string", "description": "API key for authentication"},
                },
                "required": ["amount", "merchant", "date"],
            },
        ),
        Tool(
            name="list_expense_entries",
            description="List all expense entries with categories for the authenticated user",
            inputSchema={
                "type": "object",
                "properties": {
                    "api_key": {"type": "string", "description": "API key for authentication"},
                },
                "required": [],
            },
        ),
        Tool(
            name="create_savings_goal",
            description="Create a new savings goal with a target amount and date",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Goal name (e.g. Vacation Fund)"},
                    "target_amount": {"type": "number", "description": "Target savings amount (must be > 0)"},
                    "target_date": {"type": "string", "description": "Target date in YYYY-MM-DD format"},
                    "api_key": {"type": "string", "description": "API key for authentication"},
                },
                "required": ["name", "target_amount", "target_date"],
            },
        ),
        Tool(
            name="list_savings_goals",
            description="List all savings goals with progress and predicted completion dates",
            inputSchema={
                "type": "object",
                "properties": {
                    "api_key": {"type": "string", "description": "API key for authentication"},
                },
                "required": [],
            },
        ),
        Tool(
            name="query_insights",
            description="Ask a natural language question about your finances",
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "Natural language financial question"},
                    "api_key": {"type": "string", "description": "API key for authentication"},
                },
                "required": ["question"],
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Tool call dispatcher
# ---------------------------------------------------------------------------

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    timestamp = datetime.now(timezone.utc).isoformat()

    # Authenticate
    try:
        user_id = _authenticate(arguments)
    except ValueError as exc:
        _logger.error(
            "MCP auth failure",
            user_id="unknown",
            operation=name,
            status="error",
            tool_name=name,
            timestamp=timestamp,
        )
        return [TextContent(type="text", text=json.dumps({"error": {"code": "unauthorized", "message": str(exc)}}))]

    # Log invocation
    _logger.info(
        "MCP tool invoked",
        user_id=user_id,
        operation=name,
        status="ok",
        tool_name=name,
        timestamp=timestamp,
    )

    try:
        result = await _dispatch(name, arguments, user_id)
        return [TextContent(type="text", text=json.dumps({"result": result}))]
    except Exception as exc:  # noqa: BLE001
        _logger.error(
            "MCP tool error",
            user_id=user_id,
            operation=name,
            status="error",
            tool_name=name,
            timestamp=timestamp,
            error=str(exc),
        )
        return [TextContent(type="text", text=json.dumps({"error": {"code": "tool_error", "message": str(exc)}}))]


async def _dispatch(name: str, arguments: dict, user_id: str) -> dict:
    """Route tool name to the correct agent Lambda invocation."""
    if name == "create_income_entry":
        body = {
            "amount": arguments["amount"],
            "source": arguments["source"],
            "date": arguments["date"],
        }
        if "notes" in arguments:
            body["notes"] = arguments["notes"]
        return _invoke_lambda("INCOME_FUNCTION", "POST", "/v1/income", body, user_id)

    elif name == "list_income_entries":
        return _invoke_lambda("INCOME_FUNCTION", "GET", "/v1/income", {}, user_id)

    elif name == "create_expense_entry":
        body = {
            "amount": arguments["amount"],
            "merchant": arguments["merchant"],
            "date": arguments["date"],
        }
        return _invoke_lambda("EXPENSE_FUNCTION", "POST", "/v1/expenses", body, user_id)

    elif name == "list_expense_entries":
        return _invoke_lambda("EXPENSE_FUNCTION", "GET", "/v1/expenses", {}, user_id)

    elif name == "create_savings_goal":
        body = {
            "name": arguments["name"],
            "target_amount": arguments["target_amount"],
            "target_date": arguments["target_date"],
        }
        return _invoke_lambda("SAVINGS_FUNCTION", "POST", "/v1/goals", body, user_id)

    elif name == "list_savings_goals":
        return _invoke_lambda("SAVINGS_FUNCTION", "GET", "/v1/goals", {}, user_id)

    elif name == "query_insights":
        body = {"question": arguments["question"]}
        return _invoke_lambda("INSIGHTS_FUNCTION", "POST", "/v1/insights/query", body, user_id)

    else:
        raise ValueError(f"Unknown tool: {name}")


# ---------------------------------------------------------------------------
# MCP Resources
# ---------------------------------------------------------------------------

@server.list_resources()
async def list_resources() -> list[Resource]:
    return [
        Resource(
            uri="income://entries",
            name="Income Entries",
            description="All income entries for the authenticated user",
            mimeType="application/json",
        ),
        Resource(
            uri="expenses://entries",
            name="Expense Entries",
            description="All expense entries with categories for the authenticated user",
            mimeType="application/json",
        ),
        Resource(
            uri="goals://active",
            name="Active Savings Goals",
            description="Active savings goals with progress and predicted completion dates",
            mimeType="application/json",
        ),
    ]


@server.read_resource()
async def read_resource(uri: str) -> str:
    environment = os.environ.get("ENVIRONMENT", "").lower()
    user_id = "local-dev-user" if environment == "local" else "mcp-user"

    if str(uri) == "income://entries":
        data = _invoke_lambda("INCOME_FUNCTION", "GET", "/v1/income", {}, user_id)
    elif str(uri) == "expenses://entries":
        data = _invoke_lambda("EXPENSE_FUNCTION", "GET", "/v1/expenses", {}, user_id)
    elif str(uri) == "goals://active":
        data = _invoke_lambda("SAVINGS_FUNCTION", "GET", "/v1/goals", {}, user_id)
    else:
        raise ValueError(f"Unknown resource URI: {uri}")

    return json.dumps(data)


# ---------------------------------------------------------------------------
# Lambda entry point
# ---------------------------------------------------------------------------

@handle_unhandled_exception
def lambda_handler(event: dict, context) -> dict:
    """Entry point for Lambda invocation from Claude Desktop."""
    async def main():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )
    asyncio.run(main())
