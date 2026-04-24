"""Simple MCP Server handler for deployment testing."""
import json
import os
from datetime import datetime, timezone

def lambda_handler(event, context):
    """Simple health check handler for MCP server."""
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'service': 'pfip-mcp-server',
            'status': 'healthy',
            'environment': os.environ.get('ENVIRONMENT', 'unknown'),
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'available_functions': {
                'income': os.environ.get('INCOME_FUNCTION', 'not-configured'),
                'expense': os.environ.get('EXPENSE_FUNCTION', 'not-configured'),
                'savings': os.environ.get('SAVINGS_FUNCTION', 'not-configured'),
                'insights': os.environ.get('INSIGHTS_FUNCTION', 'not-configured')
            }
        })
    }
