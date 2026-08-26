"""Lightweight trace context propagation and span management."""

from __future__ import annotations

import time
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from marketing_mcp.observability.logging import get_structured_logger
from marketing_mcp.observability.metrics import GLOBAL_METRICS

logger = get_structured_logger(__name__)

current_trace_id: ContextVar[str | None] = ContextVar("current_trace_id", default=None)
current_span_id: ContextVar[str | None] = ContextVar("current_span_id", default=None)


@contextmanager
def trace_span(
    name: str,
    attributes: dict[str, Any] | None = None,
) -> Generator[str, None, None]:
    """Context manager for tracing operations with timing and context propagation."""
    trace_id = current_trace_id.get() or f"trace_{uuid.uuid4().hex[:16]}"
    token_trace = current_trace_id.set(trace_id)

    span_id = f"span_{uuid.uuid4().hex[:12]}"
    token_span = current_span_id.set(span_id)

    start_time = time.perf_counter()
    status = "success"
    try:
        yield span_id
    except Exception as e:
        status = "error"
        logger.warning(
            "Span %s failed: %s",
            name,
            str(e),
            extra={"structured_data": {"span_id": span_id, "trace_id": trace_id, "error": str(e)}},
        )
        raise
    finally:
        duration = time.perf_counter() - start_time
        GLOBAL_METRICS.observe_duration("span_duration_seconds", duration, labels={"span": name, "status": status})
        current_span_id.reset(token_span)
        current_trace_id.reset(token_trace)


__all__ = ["current_span_id", "current_trace_id", "trace_span"]
