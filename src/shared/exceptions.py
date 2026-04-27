"""Decorator for catching unhandled Lambda exceptions and returning HTTP 500."""
import functools
import json
import traceback
from typing import Callable

from aws_lambda_powertools import Logger
from src.shared.cors import cors_headers

_logger = Logger(service="pfip-mvp")


def handle_unhandled_exception(func: Callable) -> Callable:
    """Decorator that catches all unhandled exceptions in a Lambda handler.

    On exception:
    - Logs the full traceback via logger.exception
    - Returns HTTP 500 JSON: {"error": "internal_server_error", "request_id": "<id>", "status": 500}
    """

    @functools.wraps(func)
    def wrapper(event: dict, context) -> dict:
        try:
            return func(event, context)
        except Exception:
            raw_headers = event.get("headers") if isinstance(event, dict) else None
            headers = raw_headers if isinstance(raw_headers, dict) else {}
            origin = headers.get("origin") or headers.get("Origin")
            tb = traceback.format_exc()
            request_id = getattr(context, "aws_request_id", "unknown")
            _logger.exception(
                "Unhandled exception",
                extra={
                    "user_id": "unknown",
                    "operation": func.__name__,
                    "status": "error",
                    "traceback": tb,
                    "request_id": request_id,
                },
            )
            return {
                "statusCode": 500,
                "headers": {
                    "Content-Type": "application/json",
                    **cors_headers(origin),
                },
                "body": json.dumps(
                    {
                        "error": "internal_server_error",
                        "request_id": request_id,
                        "status": 500,
                    }
                ),
            }

    return wrapper
