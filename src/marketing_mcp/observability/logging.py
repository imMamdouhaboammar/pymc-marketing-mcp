"""Structured JSON logging with automatic secret redaction and context binding (Wave 6 Task 1)."""

from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from typing import Any

from marketing_mcp.security.redaction import redact_secrets

current_request_id: ContextVar[str | None] = ContextVar("current_request_id", default=None)
current_tenant_id: ContextVar[str | None] = ContextVar("current_tenant_id", default=None)


class StructuredJSONFormatter(logging.Formatter):
    """Formats log records as single-line redacted JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Bind context variables
        req_id = current_request_id.get()
        if req_id:
            log_data["request_id"] = req_id
        tenant = current_tenant_id.get()
        if tenant:
            log_data["tenant_id"] = tenant

        # Attach extra structured fields if present
        if hasattr(record, "structured_data") and isinstance(record.structured_data, dict):
            log_data.update(record.structured_data)

        if record.exc_info and not record.exc_text:
            record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            log_data["exception"] = record.exc_text

        # Ensure all secrets/tokens are automatically scrubbed
        sanitized = redact_secrets(log_data)
        return json.dumps(sanitized)


def get_structured_logger(name: str) -> logging.Logger:
    """Get or configure a logger with JSON formatting."""
    logger = logging.getLogger(name)
    return logger
