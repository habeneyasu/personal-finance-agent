"""Unit tests for MCP Server handler."""
import json
import os
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_lambda_response(body: dict, status_code: int = 200) -> dict:
    """Build a mock boto3 Lambda invoke response."""
    payload_bytes = json.dumps({"statusCode": status_code, "body": json.dumps(body)}).encode()
    mock_response = {"Payload": MagicMock()}
    mock_response["Payload"].read.return_value = payload_bytes
    return mock_response


# ---------------------------------------------------------------------------
# list_tools
# ---------------------------------------------------------------------------

class TestListTools:
    def test_returns_all_seven_tools(self):
        """list_tools must return exactly 7 tools with correct names."""
        from src.mcp_server.handler import list_tools

        import asyncio
        tools = asyncio.run(list_tools())

        names = [t.name for t in tools]
        assert len(tools) == 7
        assert "create_income_entry" in names
        assert "list_income_entries" in names
        assert "create_expense_entry" in names
        assert "list_expense_entries" in names
        assert "create_savings_goal" in names
        assert "list_savings_goals" in names
        assert "query_insights" in names

    def test_tools_have_input_schema(self):
        """Every tool must have a non-empty inputSchema."""
        from src.mcp_server.handler import list_tools

        import asyncio
        tools = asyncio.run(list_tools())

        for tool in tools:
            assert tool.inputSchema is not None
            assert "type" in tool.inputSchema


# ---------------------------------------------------------------------------
# call_tool — successful invocation
# ---------------------------------------------------------------------------

class TestCallTool:
    @patch.dict(os.environ, {"ENVIRONMENT": "local", "EXPENSE_FUNCTION": "expense-fn"})
    @patch("boto3.client")
    def test_create_expense_entry_invokes_expense_lambda(self, mock_boto_client):
        """call_tool('create_expense_entry') should invoke the expense Lambda."""
        expense_data = {"id": "abc", "amount": 50.0, "merchant": "Uber", "category": "Transportation", "date": "2026-04-22"}
        mock_lambda = MagicMock()
        mock_lambda.invoke.return_value = _make_lambda_response(expense_data, 201)
        mock_boto_client.return_value = mock_lambda

        from src.mcp_server.handler import call_tool
        import asyncio
        results = asyncio.run(call_tool("create_expense_entry", {
            "amount": 50.0,
            "merchant": "Uber",
            "date": "2026-04-22",
        }))

        assert len(results) == 1
        payload = json.loads(results[0].text)
        assert "result" in payload
        assert payload["result"]["merchant"] == "Uber"

        mock_lambda.invoke.assert_called_once()
        call_kwargs = mock_lambda.invoke.call_args[1]
        assert call_kwargs["FunctionName"] == "expense-fn"

    @patch.dict(os.environ, {"ENVIRONMENT": "local", "INCOME_FUNCTION": "income-fn"})
    @patch("boto3.client")
    def test_list_income_entries_invokes_income_lambda(self, mock_boto_client):
        """call_tool('list_income_entries') should invoke the income Lambda with GET."""
        income_data = [{"id": "1", "amount": 1000.0, "source": "Salary", "date": "2026-04-01"}]
        mock_lambda = MagicMock()
        mock_lambda.invoke.return_value = _make_lambda_response(income_data)
        mock_boto_client.return_value = mock_lambda

        from src.mcp_server.handler import call_tool
        import asyncio
        results = asyncio.run(call_tool("list_income_entries", {}))

        payload = json.loads(results[0].text)
        assert "result" in payload
        assert isinstance(payload["result"], list)

    @patch.dict(os.environ, {"ENVIRONMENT": "local", "SAVINGS_FUNCTION": "savings-fn"})
    @patch("boto3.client")
    def test_create_savings_goal_invokes_savings_lambda(self, mock_boto_client):
        """call_tool('create_savings_goal') should invoke the savings Lambda."""
        goal_data = {"id": "g1", "name": "Vacation", "target_amount": 2000.0, "target_date": "2026-12-01"}
        mock_lambda = MagicMock()
        mock_lambda.invoke.return_value = _make_lambda_response(goal_data, 201)
        mock_boto_client.return_value = mock_lambda

        from src.mcp_server.handler import call_tool
        import asyncio
        results = asyncio.run(call_tool("create_savings_goal", {
            "name": "Vacation",
            "target_amount": 2000.0,
            "target_date": "2026-12-01",
        }))

        payload = json.loads(results[0].text)
        assert "result" in payload
        assert payload["result"]["name"] == "Vacation"

    @patch.dict(os.environ, {"ENVIRONMENT": "local", "INSIGHTS_FUNCTION": "insights-fn"})
    @patch("boto3.client")
    def test_query_insights_invokes_insights_lambda(self, mock_boto_client):
        """call_tool('query_insights') should invoke the insights Lambda."""
        insight_data = {"answer": "You spent $500 this month.", "query": "How much did I spend?"}
        mock_lambda = MagicMock()
        mock_lambda.invoke.return_value = _make_lambda_response(insight_data)
        mock_boto_client.return_value = mock_lambda

        from src.mcp_server.handler import call_tool
        import asyncio
        results = asyncio.run(call_tool("query_insights", {"question": "How much did I spend?"}))

        payload = json.loads(results[0].text)
        assert "result" in payload
        assert "answer" in payload["result"]


# ---------------------------------------------------------------------------
# call_tool — error cases
# ---------------------------------------------------------------------------

class TestCallToolErrors:
    @patch.dict(os.environ, {"ENVIRONMENT": "local"})
    def test_unknown_tool_returns_error_response(self):
        """call_tool with an unknown tool name must return an error response."""
        from src.mcp_server.handler import call_tool
        import asyncio
        results = asyncio.run(call_tool("nonexistent_tool", {}))

        assert len(results) == 1
        payload = json.loads(results[0].text)
        assert "error" in payload
        assert payload["error"]["code"] == "tool_error"

    @patch.dict(os.environ, {"ENVIRONMENT": "production", "PFIP_API_KEY": "secret-key"})
    def test_missing_api_key_returns_unauthorized(self):
        """call_tool without api_key in non-local env must return unauthorized error."""
        from src.mcp_server.handler import call_tool
        import asyncio

        results = asyncio.run(call_tool("list_income_entries", {}))

        payload = json.loads(results[0].text)
        assert "error" in payload
        assert payload["error"]["code"] == "unauthorized"

    @patch.dict(os.environ, {"ENVIRONMENT": "production", "PFIP_API_KEY": "secret-key"})
    def test_wrong_api_key_returns_unauthorized(self):
        """call_tool with wrong api_key must return unauthorized error."""
        from src.mcp_server.handler import call_tool
        import asyncio
        results = asyncio.run(call_tool("list_income_entries", {"api_key": "wrong-key"}))

        payload = json.loads(results[0].text)
        assert "error" in payload
        assert payload["error"]["code"] == "unauthorized"


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

class TestCallToolLogging:
    @patch.dict(os.environ, {"ENVIRONMENT": "local", "EXPENSE_FUNCTION": "expense-fn"})
    @patch("boto3.client")
    def test_call_tool_logs_user_id_tool_name_timestamp(self, mock_boto_client):
        """call_tool must log user_id, tool_name, and timestamp for each invocation."""
        expense_data = {"id": "x", "amount": 10.0, "merchant": "Shop", "category": "Shopping", "date": "2026-04-22"}
        mock_lambda = MagicMock()
        mock_lambda.invoke.return_value = _make_lambda_response(expense_data, 201)
        mock_boto_client.return_value = mock_lambda

        import asyncio
        import src.mcp_server.handler as mcp_handler

        log_calls = []

        original_info = mcp_handler._logger.info

        def capture_info(message, **kwargs):
            log_calls.append({"message": message, **kwargs})
            return original_info(message, **kwargs)

        mcp_handler._logger.info = capture_info

        try:
            asyncio.run(mcp_handler.call_tool("create_expense_entry", {
                "amount": 10.0,
                "merchant": "Shop",
                "date": "2026-04-22",
            }))
        finally:
            mcp_handler._logger.info = original_info

        # Find the invocation log entry
        invocation_logs = [c for c in log_calls if c.get("tool_name") == "create_expense_entry"]
        assert len(invocation_logs) >= 1
        log = invocation_logs[0]
        assert "user_id" in log
        assert "tool_name" in log
        assert "timestamp" in log
        assert log["tool_name"] == "create_expense_entry"


# ---------------------------------------------------------------------------
# list_resources
# ---------------------------------------------------------------------------

class TestListResources:
    def test_returns_all_three_resource_uris(self):
        """list_resources must return all 3 resource URIs."""
        from src.mcp_server.handler import list_resources
        import asyncio
        resources = asyncio.run(list_resources())

        uris = [str(r.uri) for r in resources]
        assert len(resources) == 3
        assert "income://entries" in uris
        assert "expenses://entries" in uris
        assert "goals://active" in uris


# ---------------------------------------------------------------------------
# Local dev mode
# ---------------------------------------------------------------------------

class TestLocalDevMode:
    @patch.dict(os.environ, {"ENVIRONMENT": "local", "INCOME_FUNCTION": "income-fn"})
    @patch("boto3.client")
    def test_local_env_skips_api_key_check(self, mock_boto_client):
        """In ENVIRONMENT=local, tool calls succeed without api_key."""
        income_data = []
        mock_lambda = MagicMock()
        mock_lambda.invoke.return_value = _make_lambda_response(income_data)
        mock_boto_client.return_value = mock_lambda

        from src.mcp_server.handler import call_tool
        import asyncio
        # No api_key provided — should succeed in local mode
        results = asyncio.run(call_tool("list_income_entries", {}))

        payload = json.loads(results[0].text)
        assert "result" in payload
        assert "error" not in payload
