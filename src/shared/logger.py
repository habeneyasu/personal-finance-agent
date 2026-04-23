"""Structured JSON logger using aws-lambda-powertools."""
from aws_lambda_powertools import Logger as _PowertoolsLogger
from aws_lambda_powertools.utilities.typing import LambdaContext

_logger = _PowertoolsLogger(service="pfip-mvp")


class Logger:
    """Thin wrapper around aws-lambda-powertools Logger.

    Ensures every log record includes the required fields:
    user_id, operation, timestamp, status.
    """

    def __init__(self, service: str = "pfip-mvp") -> None:
        self._logger = _PowertoolsLogger(service=service)

    def _build_extra(
        self,
        user_id: str,
        operation: str,
        status: str,
        **kwargs,
    ) -> dict:
        return {"user_id": user_id, "operation": operation, "status": status, **kwargs}

    def info(self, message: str, *, user_id: str, operation: str, status: str = "ok", **kwargs) -> None:
        self._logger.info(message, extra=self._build_extra(user_id, operation, status, **kwargs))

    def warning(self, message: str, *, user_id: str, operation: str, status: str = "warning", **kwargs) -> None:
        self._logger.warning(message, extra=self._build_extra(user_id, operation, status, **kwargs))

    def error(self, message: str, *, user_id: str, operation: str, status: str = "error", **kwargs) -> None:
        self._logger.error(message, extra=self._build_extra(user_id, operation, status, **kwargs))

    def exception(self, message: str, *, user_id: str, operation: str, status: str = "error", **kwargs) -> None:
        self._logger.exception(message, extra=self._build_extra(user_id, operation, status, **kwargs))


# Module-level default logger instance
logger = Logger()
